"""Generate the checked-in, human-readable benchmark fixtures deterministically."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def modeling_cases() -> list[dict]:
    specs=[]
    def add(category,instruction,engine="revit",plan=None): specs.append({"id":f"{len(specs)+1:02d}_{category}","category":category,"instruction":instruction,"engine":engine,**({"plan":plan} if plan else {})})
    add("wall","在0,0画一面6m长的墙")
    add("wall","画一面8000mm长、层高3m、墙厚200mm的墙")
    add("wall","生成一面4.5m长的墙，高度3.3m，厚度180mm")
    add("wall","在1000,2000画一面5m长的墙，层高3.6m")
    add("wall","创建一面长度7200mm的墙，高度3600mm，墙厚240mm")
    add("wall","画一面3m长的墙，层高2.8m，墙厚100mm")
    add("wall","生成一面10m长的墙，高度4.2m，厚度250mm")
    add("wall","创建一面650cm长的墙，层高3.6m，墙厚200mm")
    add("room","生成一个6m×4m的房间")
    add("room","创建一个8m×5m的房间，层高3.3m，墙厚200mm")
    add("room","生成一个4m×3m的房间，高度2.8m，厚度120mm")
    add("room","生成一个7.5m×6m的房间，层高3.6m，包含楼板")
    add("room","创建一个5m×5m的房间，层高3m，墙厚240mm，包含楼板")
    add("room","生成一个9m×6m的房间，高度4m，厚度200mm")
    add("room","创建6000mm×4000mm的房间，层高3m，墙厚200mm")
    add("room","生成一个6.6m×4.2m的房间，层高3.15m，包含楼板")
    add("frame","创建一个12m×8m的带柱框架，层高3.6m")
    add("frame","生成9m×6m的柱网框架，高度4.2m，柱宽400mm")
    add("frame","创建15m×10m的带柱框架，层高4.5m，柱尺寸500mm")
    add("frame","生成6m×6m的框架，高度3m，无楼板")
    add("frame","创建18m×12m的排柱框架，层高5m，柱宽450mm")
    add("frame","生成10m×8m的带柱框架，高度3.9m")
    add("building","生成一栋30m×20m的两层小楼，层高3.6m，外墙200mm，中间加一道隔墙，四个角放柱子")
    add("building","生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm")
    add("building","创建一栋15m×10m的三层小楼，层高3m，外墙240mm，四个角放柱子")
    add("building","生成一栋20m×12m的一层建筑，层高4.2m，中间加一道隔墙")
    add("building","创建一栋8m×6m的两层小楼，层高2.8m，无轴网")
    add("building","生成一栋18m×9m的四层建筑，层高3.6m，四角放柱")
    add("building","创建一栋25m×15m的两层建筑，层高3.9m，南墙加一扇900mm宽的门")
    add("building","生成一栋10m×10m的三层小楼，层高3.2m，外墙180mm，中间加隔墙")
    add("building","创建一栋16m×12m的一层建筑，层高5m，四个角放柱子，柱宽500mm")
    add("building","生成一栋24m×16m的两层小楼，层高3.6m，中间加一道隔墙，四个角放柱子，南墙加一扇1000mm宽的门")
    add("level","创建标高0m")
    add("level","创建标高0m和3.6m")
    add("level","生成标高-0.45m和4.2m")
    add("level","创建标高0m、3.3m和6.6m")
    add("column","生成一根400mm×400mm、高度3.6m的柱")
    add("column","创建一根500mm×500mm、高度4.2m的柱")
    add("column","生成300mm×600mm的柱，高3m")
    add("column","创建一根450mm×450mm、高5m的柱")
    add("slab","生成8m×5m的楼板，板厚150mm，标高0m")
    add("slab","创建6m×4m的楼板，厚度120mm，标高3.6m")
    add("slab","生成10m×8m的楼板，板厚200mm，标高-0.1m")
    add("slab","创建4.5m×3.5m的楼板，厚100mm，标高0m")
    add("opening","生成一个8m×6m的房间，层高3.3m，南墙设置900mm宽、高度2100mm的门")
    add("opening","创建一个10m×8m的房间，层高3.6m，北墙设置1500mm×1200mm的窗，窗台900mm")
    add("polyline","在AutoCAD中绘制(0,0),(6000,0),(6000,4000)的闭合多段线",engine="acad")
    add("polyline","在AutoCAD中绘制6000mm×4000mm的闭合矩形多段线",engine="acad")
    add("part","在SolidWorks中生成100mm×50mm×20mm的零件",engine="sw")
    assembly_plan={"schema_version":"1.0","instruction":"在SolidWorks中创建两个零件并组成装配体","engine":"sw","units":"mm","operations":[{"op":"create_part","id":"p1","shape":"box","width":100,"depth":60,"height":20},{"op":"create_part","id":"p2","shape":"cylinder","diameter":40,"height":80},{"op":"create_assembly","id":"assembly_1","parts":["p1","p2"]}]}
    add("assembly","在SolidWorks中创建两个零件并组成装配体",engine="sw",plan=assembly_plan)
    assert len(specs)==50,len(specs)
    return specs


def audit_cases() -> list[dict]:
    wall={"id":"wall_s","type":"wall","start":[0,0,0],"end":[6000,0,0],"height":3600,"thickness":200}
    door={"id":"door_1","type":"door","host_id":"wall_s","width":900,"height":2100,"bottom":0,"offset":1000}
    window={"id":"window_1","type":"window","host_id":"wall_s","width":1500,"height":1500,"bottom":900,"offset":1000}
    column={"id":"column_1","type":"column","center":[0,0,0],"width":400,"depth":400,"height":3600}
    slab={"id":"slab_1","type":"slab","boundary":[[0,0,0],[6000,0,0],[6000,4000,0],[0,4000,0]],"thickness":120,"elevation":0}
    level={"id":"level_1","type":"level","name":"F1","elevation":0}
    grid={"id":"grid_1","type":"grid","name":"1","start":[0,0,0],"end":[0,6000,0]}
    specs=[]
    def case(name,elements,rules): specs.append({"id":f"{len(specs)+1:02d}_{name}","elements":elements,"seeded_rules":rules})
    e=copy.deepcopy(wall);e["thickness"]=80;case("thin_wall",[e],["AEC-WALL-002"])
    e=copy.deepcopy(wall);e["end"]=e["start"];case("zero_wall",[e],["AEC-GEOM-001"])
    e=copy.deepcopy(wall);e["height"]=-1;case("wall_height",[e],["AEC-WALL-003"])
    e=copy.deepcopy(wall);e["thickness"]=-200;case("wall_thickness",[e],["AEC-WALL-001"])
    e=copy.deepcopy(door);e["height"]=1800;case("low_door",[wall,e],["AEC-DOOR-001"])
    e=copy.deepcopy(door);e["width"]=600;case("narrow_door",[wall,e],["AEC-DOOR-002"])
    e=copy.deepcopy(door);e["host_id"]="missing";case("orphan_door",[wall,e],["AEC-HOST-001"])
    e=copy.deepcopy(door);e["width"]=7000;case("wide_door",[wall,e],["AEC-HOST-002"])
    e=copy.deepcopy(door);e["bottom"]=2000;e["height"]=2100;case("high_door",[wall,e],["AEC-HOST-003"])
    e=copy.deepcopy(window);e["bottom"]=-100;case("negative_sill",[wall,e],["AEC-HOST-003"])
    case("duplicate_id",[wall,copy.deepcopy(wall)],["AEC-ID-001"])
    e=copy.deepcopy(wall);e["id"]="wall south bad";case("bad_name",[e],["AEC-NAME-001"])
    other=copy.deepcopy(level);other["id"]="level_2";other["name"]="F2";case("duplicate_levels",[level,other],["AEC-LEVEL-001"])
    e=copy.deepcopy(level);e["name"]="";case("unnamed_level",[e],["AEC-LEVEL-002"])
    other=copy.deepcopy(grid);other["id"]="grid_2";case("duplicate_grids",[grid,other],["AEC-GRID-002"])
    e=copy.deepcopy(grid);e["name"]="";case("unnamed_grid",[e],["AEC-GRID-001"])
    e=copy.deepcopy(column);e["width"]=0;case("column_width",[e],["AEC-COL-WIDTH"])
    e=copy.deepcopy(slab);e["thickness"]=0;case("slab_thickness",[e],["AEC-SLAB-001"])
    e=copy.deepcopy(wall);e["start"]=None;case("malformed_wall",[e],["AEC-GEOM-002"])
    e=copy.deepcopy(window);e["offset"]=5500;case("window_outside",[wall,e],["AEC-HOST-002"])
    assert len(specs)==20
    return specs


def main() -> None:
    for directory in ("cases","golden","audit_cases"): (ROOT/directory).mkdir(exist_ok=True)
    for case in modeling_cases():
        (ROOT/"cases"/f"{case['id']}.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
    for case in audit_cases():
        (ROOT/"audit_cases"/f"{case['id']}.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Generated 50 modeling cases and 20 seeded-defect audit cases")


if __name__=="__main__": main()
