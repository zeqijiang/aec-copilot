from __future__ import annotations

import json
from pathlib import Path

from aec_copilot.engines.sim import SimulationEngine
from aec_copilot.knowledge import LocalKnowledgeBase
from aec_copilot.mcp_server import UnifiedMCPServer
from aec_copilot.runner import Runner
from aec_copilot.tool_catalog import catalog


class OmissionEngine(SimulationEngine):
    def __init__(self,failures=1):
        super().__init__("revit"); self.failures=failures
    def call(self,name,args):
        if self.failures and name=="revit_create_wall":
            self.failures-=1
            return {"ok":True,"note":"silent test omission"}
        return super().call(name,args)


def test_transient_omission_recovers_in_second_attempt(tmp_path):
    engine=OmissionEngine(1)
    result=Runner(engine,output_root=tmp_path).run("在0,0画一面6m长的墙")
    assert result.status=="passed"
    assert len(result.attempts)==2
    assert result.attempts[0].status=="rolled_back"
    assert result.attempts[1].verification.passed


def test_permanent_omission_rolls_back_every_attempt(tmp_path):
    engine=OmissionEngine(9)
    result=Runner(engine,output_root=tmp_path).run("在0,0画一面6m长的墙")
    assert result.status=="failed"
    assert len(result.attempts)==3
    assert engine.snapshot()==[]
    assert result.elements==[]
    assert result.plan.metadata["repair_history"][-1]["action"]=="rollback_and_reexecute_canonical_dsl"


def test_mcp_initialize_and_catalog():
    server=UnifiedMCPServer()
    initialized=server.handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}})
    assert initialized["result"]["serverInfo"]["name"]=="aec-copilot"
    tools=server.handle({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})["result"]["tools"]
    names={t["name"] for t in tools}
    assert {"revit_create_wall","acad_draw_polyline","sw_create_part","aec_execute_plan"}<=names


def test_mcp_three_engines_in_one_server():
    server=UnifiedMCPServer()
    cases=[("revit_create_level",{"id":"l1","elevation":"3.6m"}),("acad_draw_polyline",{"id":"p1","points":[[0,0],[100,0]]}),("sw_create_part",{"id":"s1","shape":"box","width":10,"depth":20,"height":30})]
    for index,(name,args) in enumerate(cases,1):
        response=server.handle({"jsonrpc":"2.0","id":index,"method":"tools/call","params":{"name":name,"arguments":args}})
        assert response["result"]["isError"] is False
    assert len(server.engines["revit"].snapshot())==1
    assert len(server.engines["acad"].snapshot())==1
    assert len(server.engines["sw"].snapshot())==1


def test_mcp_preview_does_not_write():
    server=UnifiedMCPServer()
    plan={"schema_version":"1.0","instruction":"wall","engine":"revit","units":"mm","operations":[{"op":"create_wall","id":"w","start":[0,0],"end":[6000,0]}]}
    payload=server.call_tool("aec_execute_plan",{"plan":plan,"preview":True})
    assert payload["preview"] is True
    assert server.engines["revit"].snapshot()==[]


def test_local_knowledge_retrieval(tmp_path):
    from aec_copilot.planner import Planner
    plan=Planner().parse("生成一个6m×4m的房间").model_dump()
    path=tmp_path/"cases.jsonl"
    path.write_text(json.dumps({"id":"room-1","instruction":"生成一个6m×4m的房间","plan":plan},ensure_ascii=False)+"\n",encoding="utf-8")
    hits=LocalKnowledgeBase(path).search("创建一个6米×4米房间")
    assert hits and hits[0].plan["operations"][0]["op"]=="create_room"


def test_tool_catalog_has_stable_public_names():
    names=[t["name"] for t in catalog()]
    assert len(names)==len(set(names))
    assert "revit_create_wall" in names and "sw_create_assembly" in names
