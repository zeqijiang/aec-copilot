"""Deterministic compiler from intent-level JSON DSL to atomic engine calls."""
from __future__ import annotations

import math
from typing import Any

from .errors import AECError, require
from .models import Plan, ToolCall
from .units import distance, mm, point

ENGINE_OPS = {
    "revit": {"create_level","create_grid","create_wall","create_column","create_slab","create_door","create_window","create_room","create_frame","create_building"},
    "acad": {"draw_polyline"},
    "sw": {"create_part","create_assembly"},
}


def _mm(data: dict[str, Any], key: str, default: Any = None, *, positive: bool = False) -> float:
    return mm(data.get(key, default), field=key, positive=positive)


def _rectangle(origin: list[float], width: float, depth: float, z: float = 0) -> list[list[float]]:
    x,y = origin[:2]
    return [[x,y,z],[x+width,y,z],[x+width,y+depth,z],[x,y+depth,z]]


def _wall(prefix: str, label: str, start: list[float], end: list[float], data: dict[str, Any], *, height: float | None = None, base_z: float | None = None) -> ToolCall:
    if base_z is not None:
        start = [start[0],start[1],base_z]
        end = [end[0],end[1],base_z]
    return ToolCall(name="revit_create_wall",arguments={
        "id":f"{prefix}_wall_{label}","start":start,"end":end,
        "height":height if height is not None else _mm(data,"height",3600,positive=True),
        "thickness":_mm(data,"thickness",data.get("wall_thickness",200),positive=True),
        "level_id":data.get("level_id"),
    })


def _room(op: dict[str, Any]) -> list[ToolCall]:
    width,depth = _mm(op,"width",positive=True),_mm(op,"depth",positive=True)
    origin = point(op.get("origin",[0,0,0]),field="origin")
    rect = _rectangle(origin,width,depth)
    prefix = op["id"]
    calls = [_wall(prefix,label,rect[i],rect[(i+1)%4],op) for i,label in enumerate(("s","e","n","w"))]
    if op.get("include_slab",False):
        calls.append(ToolCall(name="revit_create_slab",arguments={"id":f"{prefix}_slab","boundary":rect,"thickness":_mm(op,"slab_thickness",120,positive=True),"elevation":origin[2]}))
    return calls


def _frame(op: dict[str, Any]) -> list[ToolCall]:
    width,depth = _mm(op,"width",positive=True),_mm(op,"depth",positive=True)
    height = _mm(op,"height",op.get("floor_height",3600),positive=True)
    size = _mm(op,"column_size",400,positive=True)
    origin = point(op.get("origin",[0,0,0]),field="origin")
    bx,by = op.get("bays_x",1),op.get("bays_y",1)
    require(isinstance(bx,int) and isinstance(by,int) and 1<=bx<=50 and 1<=by<=50,"E_GEOM","bays_x/bays_y must be integers from 1 to 50")
    rect = _rectangle(origin,width,depth)
    prefix,calls = op["id"] ,[]
    xs = [origin[0]+width*i/bx for i in range(bx+1)]
    ys = [origin[1]+depth*i/by for i in range(by+1)]
    for i,x in enumerate(xs):
        calls.append(ToolCall(name="revit_create_grid",arguments={"id":f"{prefix}_grid_x{i}","start":[x,origin[1],origin[2]],"end":[x,origin[1]+depth,origin[2]],"name":str(i+1)}))
    for j,y in enumerate(ys):
        calls.append(ToolCall(name="revit_create_grid",arguments={"id":f"{prefix}_grid_y{j}","start":[origin[0],y,origin[2]],"end":[origin[0]+width,y,origin[2]],"name":chr(65+j)}))
    for i,x in enumerate(xs):
        for j,y in enumerate(ys):
            calls.append(ToolCall(name="revit_create_column",arguments={"id":f"{prefix}_column_{i}_{j}","center":[x,y,origin[2]],"width":size,"depth":size,"height":height}))
    if op.get("include_slab",True):
        calls.append(ToolCall(name="revit_create_slab",arguments={"id":f"{prefix}_slab","boundary":rect,"thickness":_mm(op,"slab_thickness",120,positive=True),"elevation":origin[2]}))
    return calls


def _building(op: dict[str, Any]) -> list[ToolCall]:
    width,depth = _mm(op,"width",positive=True),_mm(op,"depth",positive=True)
    floors,floor_height = op.get("floors",2),_mm(op,"floor_height",op.get("height",3600),positive=True)
    require(isinstance(floors,int) and 1<=floors<=20,"E_GEOM","floors must be an integer from 1 to 20")
    origin = point(op.get("origin",[0,0,0]),field="origin")
    prefix,calls = op["id"],[]
    for f in range(floors+1):
        z = origin[2]+f*floor_height
        calls.append(ToolCall(name="revit_create_level",arguments={"id":f"{prefix}_level_{f}","name":f"F{f+1}","elevation":z}))
    if op.get("include_grids",True):
        for i,x in enumerate((origin[0],origin[0]+width/2,origin[0]+width)):
            calls.append(ToolCall(name="revit_create_grid",arguments={"id":f"{prefix}_grid_x{i}","start":[x,origin[1],origin[2]],"end":[x,origin[1]+depth,origin[2]],"name":str(i+1)}))
        for j,y in enumerate((origin[1],origin[1]+depth/2,origin[1]+depth)):
            calls.append(ToolCall(name="revit_create_grid",arguments={"id":f"{prefix}_grid_y{j}","start":[origin[0],y,origin[2]],"end":[origin[0]+width,y,origin[2]],"name":chr(65+j)}))
    wall_data = {**op,"height":floor_height,"thickness":op.get("wall_thickness",op.get("thickness",200))}
    for f in range(floors):
        z = origin[2]+f*floor_height
        floor_prefix = f"{prefix}_f{f+1}"
        rect = _rectangle(origin,width,depth,z)
        for i,label in enumerate(("s","e","n","w")):
            wall = _wall(floor_prefix,label,rect[i],rect[(i+1)%4],wall_data,base_z=z)
            wall.arguments["level_id"] = f"{prefix}_level_{f}"
            calls.append(wall)
        if op.get("partition",False):
            x = origin[0]+width/2
            calls.append(_wall(floor_prefix,"partition",[x,origin[1],z],[x,origin[1]+depth,z],{**wall_data,"thickness":op.get("partition_thickness",100)},base_z=z))
        if op.get("corner_columns",False):
            size = _mm(op,"column_size",400,positive=True)
            for i,(x,y) in enumerate(((origin[0],origin[1]),(origin[0]+width,origin[1]),(origin[0]+width,origin[1]+depth),(origin[0],origin[1]+depth))):
                calls.append(ToolCall(name="revit_create_column",arguments={"id":f"{floor_prefix}_column_{i}","center":[x,y,z],"width":size,"depth":size,"height":floor_height,"level_id":f"{prefix}_level_{f}"}))
        calls.append(ToolCall(name="revit_create_slab",arguments={"id":f"{floor_prefix}_slab","boundary":rect,"thickness":_mm(op,"slab_thickness",120,positive=True),"elevation":z,"level_id":f"{prefix}_level_{f}"}))
        if f == 0 and op.get("entrance_door",False):
            host = f"{floor_prefix}_wall_s"
            door_width = _mm(op,"door_width",900,positive=True)
            calls.append(ToolCall(name="revit_create_door",arguments={"id":f"{prefix}_entrance","host_id":host,"width":door_width,"height":_mm(op,"door_height",2100,positive=True),"bottom":0,"offset":(width-door_width)/2}))
    return calls


def compile_plan(plan: Plan | dict[str, Any]) -> list[ToolCall]:
    """Validate and expand a plan. No model calls or engine side effects occur."""
    if isinstance(plan,dict):
        plan = Plan.model_validate(plan)
    calls: list[ToolCall] = []
    for operation in plan.operations:
        op = operation.model_dump()
        name = op["op"]
        require(name in ENGINE_OPS[plan.engine],"E_CONSTRAINT",f"Operation {name} is not supported by {plan.engine}",operation=operation.id)
        if plan.engine == "revit" and name == "create_room": expanded = _room(op)
        elif plan.engine == "revit" and name == "create_frame": expanded = _frame(op)
        elif plan.engine == "revit" and name == "create_building": expanded = _building(op)
        else:
            # Normalize every public numeric field before it reaches an engine.
            normalized = dict(op)
            normalized.pop("op",None)
            if name in {"create_wall"}:
                normalized.update(start=point(op.get("start"),field="start"),end=point(op.get("end"),field="end"),height=_mm(op,"height",3600,positive=True),thickness=_mm(op,"thickness",200,positive=True))
                length=distance(normalized["start"],normalized["end"])
                require(length>0,"E_GEOM","Wall start and end must differ",element_id=op["id"])
                require(normalized["thickness"]<length,"E_GEOM","Wall thickness must be smaller than wall length",element_id=op["id"])
            elif name == "create_column":
                normalized.update(center=point(op.get("center"),field="center"),width=_mm(op,"width",400,positive=True),depth=_mm(op,"depth",op.get("width",400),positive=True),height=_mm(op,"height",3600,positive=True))
            elif name == "create_level": normalized["elevation"] = _mm(op,"elevation",0)
            elif name == "create_grid":
                normalized.update(start=point(op.get("start"),field="start"),end=point(op.get("end"),field="end"))
                require(distance(normalized["start"],normalized["end"])>0,"E_GEOM","Grid start and end must differ",element_id=op["id"])
            elif name == "create_slab":
                require(isinstance(op.get("boundary"),list) and len(op["boundary"])>=3,"E_GEOM","Slab boundary needs at least three points")
                normalized.update(boundary=[point(p,field="boundary") for p in op["boundary"]],thickness=_mm(op,"thickness",120,positive=True),elevation=_mm(op,"elevation",0))
            elif name in {"create_door","create_window"}:
                normalized.update(width=_mm(op,"width",900 if name=="create_door" else 1500,positive=True),height=_mm(op,"height",2100 if name=="create_door" else 1500,positive=True),bottom=_mm(op,"bottom",0 if name=="create_door" else 900))
                if "offset" in op: normalized["offset"] = _mm(op,"offset")
            elif name == "draw_polyline":
                require(isinstance(op.get("points"),list) and len(op["points"])>=2,"E_GEOM","Polyline needs at least two points")
                normalized["points"] = [point(p,field="points") for p in op["points"]]
                points=normalized["points"]
                require(any(distance(points[i],points[i+1])>0 for i in range(len(points)-1)),"E_GEOM","Polyline has zero length",element_id=op["id"])
            elif name == "create_part":
                for key in ("width","depth","height","diameter"):
                    if key in op: normalized[key] = _mm(op,key,positive=True)
                normalized["origin"] = point(op.get("origin",[0,0,0]),field="origin")
            expanded = [ToolCall(name=f"{plan.engine}_{name}",arguments=normalized)]
        calls.extend(expanded)
    ids = [call.arguments["id"] for call in calls]
    require(len(ids)==len(set(ids)),"E_CONSTRAINT","Expanded element IDs must be unique")
    known_walls = {c.arguments["id"] for c in calls if c.name=="revit_create_wall"}
    for call in calls:
        if call.name in {"revit_create_door","revit_create_window"}:
            host = call.arguments.get("host_id")
            require(host in known_walls,"E_NOT_FOUND",f"Opening host wall does not exist in this plan: {host}",element_id=call.arguments["id"])
    return calls


def expected_manifest(calls: list[ToolCall]) -> list[dict[str, Any]]:
    types = {"create_level":"level","create_grid":"grid","create_wall":"wall","create_column":"column","create_slab":"slab","create_door":"door","create_window":"window","draw_polyline":"polyline","create_part":"part","create_assembly":"assembly"}
    result=[]
    for call in calls:
        op = call.name.split("_",1)[1]
        args = dict(call.arguments)
        if op == "create_part":
            shape = args.get("shape","box")
            args["shape"] = shape
            args["size"] = [args.get(k,100) for k in ("width","depth","height")] if shape=="box" else [args.get("diameter",100),args.get("height",100)]
        result.append({"id":args["id"],"type":types[op],**args})
    return result
