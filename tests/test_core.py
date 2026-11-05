from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_copilot.audit import audit_model
from aec_copilot.compiler import compile_plan
from aec_copilot.engines.sim import SimulationEngine
from aec_copilot.errors import AECError
from aec_copilot.models import Plan
from aec_copilot.planner import Planner
from aec_copilot.runner import Runner
from aec_copilot.units import mm, point
from aec_copilot.verifier import compare_manifest


def test_units_accept_mixed_notation():
    assert mm("3.6m")==3600
    assert mm("25cm")==250
    assert mm("200毫米")==200
    assert mm(200)==200
    assert point([1,2])==[1,2,0]


@pytest.mark.parametrize("value",["3 feet","abc",True,None,float("inf")])
def test_units_reject_invalid(value):
    with pytest.raises(AECError) as error: mm(value)
    assert error.value.code in {"E_UNIT","E_GEOM"}


def test_wall_chinese_instruction():
    plan=Planner().parse("在0,0画一面6m长的墙")
    calls=compile_plan(plan)
    assert calls[0].name=="revit_create_wall"
    assert calls[0].arguments["end"]==[6000,0,0]


def test_building_mvp_expands_all_requested_elements():
    plan=Planner().parse("生成一栋30m×20m的两层小楼，层高3.6m，外墙200mm，中间加一道隔墙，四个角放柱子")
    calls=compile_plan(plan)
    names=[c.name for c in calls]
    assert names.count("revit_create_level")==3
    assert names.count("revit_create_wall")==10
    assert names.count("revit_create_column")==8
    assert names.count("revit_create_slab")==2
    assert names.count("revit_create_grid")==6


def test_room_door_and_window_hosts():
    plan=Planner().parse("生成一个8m×6m的房间，南墙设置900mm宽、高度2100mm的门，北墙设置1500mm×1200mm的窗，窗台900mm")
    calls=compile_plan(plan)
    assert {c.name for c in calls}>={"revit_create_door","revit_create_window"}
    assert next(c for c in calls if c.name=="revit_create_door").arguments["host_id"]=="room_wall_s"


def test_plan_rejects_unknown_operation():
    with pytest.raises(ValidationError): Plan.model_validate({"instruction":"x","operations":[{"op":"delete_everything","id":"x"}]})


def test_plan_rejects_duplicate_ids():
    with pytest.raises(ValidationError): Plan.model_validate({"instruction":"x","operations":[{"op":"create_level","id":"x","elevation":0},{"op":"create_level","id":"x","elevation":1}]})


def test_compile_rejects_cross_engine_operation():
    plan=Plan(instruction="x",engine="acad",operations=[{"op":"create_wall","id":"w","start":[0,0],"end":[1,0]}])
    with pytest.raises(AECError) as error: compile_plan(plan)
    assert error.value.code=="E_CONSTRAINT"


def test_compile_rejects_missing_opening_host():
    plan=Plan(instruction="x",operations=[{"op":"create_door","id":"d","host_id":"missing","width":900,"height":2100}])
    with pytest.raises(AECError) as error: compile_plan(plan)
    assert error.value.code=="E_NOT_FOUND"


def test_simulation_end_to_end(tmp_path):
    result=Runner(output_root=tmp_path).run("生成一个6m×4m的房间，包含楼板")
    assert result.status=="passed"
    assert len(result.elements)==5
    assert Path(result.screenshot).stat().st_size>1000
    assert Path(result.reports["excel"]).stat().st_size>1000
    assert Path(result.reports["pdf"]).stat().st_size>1000


def test_zero_length_wall_fails_without_polluting_engine():
    engine=SimulationEngine()
    plan=Plan(instruction="bad",operations=[{"op":"create_wall","id":"w","start":[0,0,0],"end":[0,0,0]}])
    # Reject invalid geometry before any engine write; the engine also guards its SPI.
    with pytest.raises(AECError) as error: compile_plan(plan)
    assert error.value.code=="E_GEOM"
    valid_call=compile_plan(Plan(instruction="ok",operations=[{"op":"create_wall","id":"w","start":[0,0,0],"end":[1000,0,0]}]))[0]
    with pytest.raises(AECError): engine.call("revit_create_wall",valid_call.arguments | {"end":[0,0,0]})
    assert engine.snapshot()==[]


def test_atomic_rollback_on_second_operation():
    engine=SimulationEngine()
    plan=Plan(instruction="bad host",operations=[{"op":"create_wall","id":"w","start":[0,0],"end":[6000,0]},{"op":"create_door","id":"d","host_id":"w","width":900,"height":2100,"offset":5999}])
    calls=compile_plan(plan)
    with pytest.raises(AECError):
        with engine.transaction():
            for call in calls: engine.call(call.name,call.arguments)
    assert engine.snapshot()==[]


def test_manifest_comparison_does_not_mutate_expectation():
    plan=Plan(instruction="x",operations=[{"op":"create_wall","id":"w","start":[0,0],"end":[6000,0]}])
    calls=compile_plan(plan); before=[c.model_dump() for c in calls]
    actual=[{"id":"w","type":"wall","start":[0,0,0],"end":[5000,0,0],"height":3600,"thickness":200,"level_id":None}]
    differences=compare_manifest(calls,actual)
    assert any(d.path=="end" for d in differences)
    assert [c.model_dump() for c in calls]==before


def test_audit_project_rules_and_disclaimer():
    report=audit_model([{"id":"w","type":"wall","start":[0,0,0],"end":[6000,0,0],"height":3600,"thickness":80}])
    assert "AEC-WALL-002" in {i.rule_id for i in report.issues}
    assert "不构成" in report.disclaimer


def test_solidworks_part_and_assembly(tmp_path):
    result=Runner(output_root=tmp_path).run("在SolidWorks中生成100mm×50mm×20mm的零件",engine="sw")
    assert result.status=="passed"
    assert result.elements[0]["size"]==[100,50,20]


def test_acad_polyline(tmp_path):
    result=Runner(output_root=tmp_path).run("在AutoCAD中绘制(0,0),(6000,0),(6000,4000)的闭合多段线",engine="acad")
    assert result.status=="passed"
    assert result.elements[0]["closed"] is True
