"""DSL → 引擎调用序列的确定性编译器。

compile_plan(plan, engine) 返回引擎原生步骤列表：
- revit：Revit Command Bridge ``execute_plan`` 的 steps（协议 revit-command-bridge/2.0）
- acad ：离线/COM 绘图调用字典（由 acad 引擎执行）
- sw   ：SolidWorks COM 调用字典

编译是纯函数：同样的 Plan 永远编译出同样的序列（可缓存、可评测）。
"""

from __future__ import annotations

from typing import Any

from .errors import AecError, ErrorCode
from .plan import Plan, Step
from .units import fmt_mm, point_dict

# revit 桥原生 op 与 DSL op 几乎同名的直接映射
_REVIT_DIRECT = {
    "query_document": "query_document",
    "query_catalog": "query_catalog",
    "query_elements": "query_elements",
    "select_elements": "select_elements",
    "create_level": "create_level",
    "create_grid": "create_grid",
    "create_wall": "create_wall",
    "create_floor": "create_floor",
    "create_room": "create_room",
    "create_model_curve": "create_model_curve",
}


def _wall_args(step: Step, index: int) -> dict[str, Any]:
    """create_wall → revit 桥 args（长度统一 mm）。"""
    from .units import parse_length

    a = step.args
    out: dict[str, Any] = {
        "start": point_dict(a["start"], field=f"steps[{index}].start"),
        "end": point_dict(a["end"], field=f"steps[{index}].end"),
    }
    if "level" in a:
        out["level"] = a["level"]
    if "height" in a:
        out["height_mm"] = parse_length(a["height"], field=f"steps[{index}].height")
    if "thickness" in a:
        out["thickness_mm"] = parse_length(a["thickness"], field=f"steps[{index}].thickness")
    if "type" in a:
        out["type"] = a["type"]
    return out


def compile_revit(plan: Plan) -> list[dict[str, Any]]:
    steps_out: list[dict[str, Any]] = []
    for i, s in enumerate(plan.steps):
        if s.op in _REVIT_DIRECT:
            args = dict(s.args)
            if s.op == "create_wall":
                args = _wall_args(s, i)
            elif s.op in ("create_grid", "create_model_curve"):
                args = dict(args)
                args["start"] = point_dict(args["start"], field=f"steps[{i}].start")
                args["end"] = point_dict(args["end"], field=f"steps[{i}].end")
            steps_out.append({"id": s.id or f"s{i}", "operation": _REVIT_DIRECT[s.op], "args": args})
        elif s.op == "create_column":
            # 确定性实现：DirectShape 方柱（避免依赖项目里是否载入结构柱族）
            from .units import parse_length

            size = parse_length(s.args.get("size", 400), field=f"steps[{i}].size")
            height = parse_length(s.args.get("height", 3600), field=f"steps[{i}].height")
            p = point_dict(s.args["point"], field=f"steps[{i}].point")
            h = s.args.get("level")  # level 名原样透传（DirectShape 不吃 level，靠 z）
            z = p["z"] + (0.0 if not h else 0.0)
            steps_out.append({
                "id": s.id or f"s{i}",
                "operation": "create_direct_shape",
                "args": {
                    "name": f"柱 {size:g}x{size:g}",
                    "category": "OST_GenericModel",
                    "geometry": [{
                        "kind": "box",
                        "min": {"x": p["x"] - size / 2, "y": p["y"] - size / 2, "z": z},
                        "max": {"x": p["x"] + size / 2, "y": p["y"] + size / 2, "z": z + height},
                    }],
                },
            })
        elif s.op == "create_direct_shape":
            steps_out.append({"id": s.id or f"s{i}", "operation": "create_direct_shape", "args": dict(s.args)})
        elif s.op == "create_text":
            args = dict(s.args)
            args["point"] = point_dict(args["point"], field=f"steps[{i}].point")
            steps_out.append({"id": s.id or f"s{i}", "operation": "create_text_note", "args": args})
        elif s.op == "export_image":
            args = {"format": "png", "output_path": str(s.args["output_path"])}
            if s.args.get("view_ids"):
                args["view_ids"] = s.args["view_ids"]
            if s.args.get("active_view", True):
                args["active_view"] = True
            steps_out.append({"id": s.id or f"s{i}", "operation": "export", "args": args})
        elif s.op == "save_document":
            steps_out.append({"id": s.id or f"s{i}", "operation": "save_document", "args": dict(s.args)})
        else:
            raise AecError(
                ErrorCode.E_PLAN_INVALID,
                f"revit 引擎不支持 op={s.op!r}（步骤 {i}）",
                {"supported": sorted(_REVIT_DIRECT | {"create_column", "create_direct_shape", "create_text", "export_image", "save_document"})},
            )
    return steps_out


def compile_acad(plan: Plan) -> list[dict[str, Any]]:
    """acad 调用字典序列；acad 引擎（COM 或 ezdxf 离线）按 op 执行。"""
    calls: list[dict[str, Any]] = []
    for i, s in enumerate(plan.steps):
        if s.op == "create_wall":
            from .units import parse_length

            start = point_dict(s.args["start"], field=f"steps[{i}].start")
            end = point_dict(s.args["end"], field=f"steps[{i}].end")
            t = parse_length(s.args.get("thickness", 200), field=f"steps[{i}].thickness")
            calls.append({"op": "wall_footprint", "layer": s.args.get("type", "A-WALL"), "start": start, "end": end, "thickness": t})
        elif s.op in ("create_grid", "create_model_curve"):
            calls.append({
                "op": "line",
                "layer": s.args.get("layer", "A-GRID" if s.op == "create_grid" else "A-LINE"),
                "start": point_dict(s.args["start"], field=f"steps[{i}].start"),
                "end": point_dict(s.args["end"], field=f"steps[{i}].end"),
            })
        elif s.op == "create_column":
            from .units import parse_length

            size = parse_length(s.args.get("size", 400), field=f"steps[{i}].size")
            p = point_dict(s.args["point"], field=f"steps[{i}].point")
            calls.append({"op": "rect", "layer": "A-COLS", "center": p, "width": size, "height": size})
        elif s.op == "create_direct_shape":
            for g in s.args.get("geometry", []):
                if g.get("kind") == "box":
                    calls.append({"op": "rect", "layer": s.args.get("name", "GEN"), "min": point_dict(g["min"]), "max": point_dict(g["max"])})
                else:
                    raise AecError(ErrorCode.E_PLAN_INVALID, f"acad 引擎仅支持 box 原语，收到 {g.get('kind')!r}")
        elif s.op == "create_text":
            calls.append({"op": "text", "layer": "A-ANNO", "point": point_dict(s.args["point"]), "text": str(s.args["text"]), "height": float(s.args.get("height", 2.5))})
        elif s.op == "save_document":
            calls.append({"op": "save", "path": s.args.get("path")})
        else:
            raise AecError(ErrorCode.E_PLAN_INVALID, f"acad 引擎不支持 op={s.op!r}", {"step": i})
    return calls


def compile_sw(plan: Plan) -> list[dict[str, Any]]:
    """sw：mm → m（SolidWorks COM API 用米）。"""
    calls: list[dict[str, Any]] = []
    for i, s in enumerate(plan.steps):
        if s.op == "create_model_curve":
            a = point_dict(s.args["start"]); b = point_dict(s.args["end"])
            calls.append({"op": "sketch_line", "start_m": [a["x"] / 1000, a["y"] / 1000], "end_m": [b["x"] / 1000, b["y"] / 1000]})
        elif s.op == "create_direct_shape":
            for g in s.args.get("geometry", []):
                if g.get("kind") == "box":
                    mn = point_dict(g["min"]); mx = point_dict(g["max"])
                    calls.append({"op": "extrude_box", "min_m": [mn["x"] / 1000, mn["y"] / 1000, mn["z"] / 1000], "max_m": [mx["x"] / 1000, mx["y"] / 1000, mx["z"] / 1000]})
                else:
                    raise AecError(ErrorCode.E_PLAN_INVALID, f"sw 引擎仅支持 box 原语，收到 {g.get('kind')!r}")
        elif s.op == "save_document":
            calls.append({"op": "save", "path": s.args.get("path")})
        else:
            raise AecError(ErrorCode.E_PLAN_INVALID, f"sw 引擎 P0 仅支持 create_model_curve / create_direct_shape / save_document，收到 {s.op!r}")
    return calls


COMPILERS = {"revit": compile_revit, "acad": compile_acad, "sw": compile_sw}


def compile_plan(plan: Plan, engine: str) -> list[dict[str, Any]]:
    if engine not in COMPILERS:
        raise AecError(ErrorCode.E_PLAN_INVALID, f"未知引擎 {engine!r}", {"supported": sorted(COMPILERS)})
    return COMPILERS[engine](plan)
