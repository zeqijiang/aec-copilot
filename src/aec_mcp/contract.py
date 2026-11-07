"""契约兼容层：让「蓝图智匠」框架（aec_copilot.MCPEngine）把本 server 当 live 后端用。

对端契约（src/aec_copilot/engines/mcp.py）：
- 事务钩子   transactions.begin/commit/rollback，各收 ``{"engine": name}``
- 原子调用   tools 映射：``revit_create_wall`` 等，参数为旧契约格式（mm 数值、[x,y,z] 数组点）
- 元素清单   manifest_tool → ``{"elements": [{id, type, **请求参数}, ...]}``（按契约 id 键）
- 截图       capture_tool 可选；M1 不配置（runner 循环内回退为 manifest 渲染）

事务语义（与原生钩子的差异，已在对端 verify 门禁内自洽）：
- call  阶段只**缓冲**已翻译的调用，不触碰引擎
- commit 阶段把整段缓冲作为**一次**桥 execute_plan 提交（Revit 桥 all-or-nothing，
  acad/SW 以文件为边界）——回滚 = 缓冲丢弃 = 从未写出，比逐 call 写入更安全
- manifest 在 commit 前返回「规范意图快照」（与 sim 后端同口径：请求回显）；
  commit 后记录引擎真实 element_id；读取真实几何值做漂移比对属 M2

M1 支持矩阵：
- revit: create_level / create_grid / create_wall / create_column(→DirectShape 方柱) /
  create_slab(→create_floor)；create_door / create_window 待 M2（桥 create_opening 语义确认）
- acad : draw_polyline（ezdxf 离线，真实 DXF）
- sw   : create_part(box 拉伸)；create_assembly 待 M2
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .errors import AecError, ErrorCode
from .units import parse_length

# ezdxf 不在本进程导入：首次导入做系统字体扫描（25s~数分钟不可控）且警告写 fd 2，
# 在 stdio server 内联导入会污染传输层/挂死响应。提交时以一次性子进程隔离执行。
try:
    import importlib.util

    _EZDXF_READY = importlib.util.find_spec("ezdxf") is not None
except Exception:  # noqa: BLE001
    _EZDXF_READY = False

from .errors import AecError, ErrorCode
from .units import parse_length

_SESSIONS: dict[str, dict[str, Any]] = {}

REVIT_OPS = ("create_level", "create_grid", "create_wall", "create_column", "create_slab", "create_door", "create_window")
_OP_TYPES = {
    "create_level": "level", "create_grid": "grid", "create_wall": "wall",
    "create_column": "column", "create_slab": "slab", "create_door": "door",
    "create_window": "window", "draw_polyline": "polyline",
    "create_part": "part", "create_assembly": "assembly",
}
CONTRACT_TOOL_NAMES = frozenset(
    ["aec_txn_begin", "aec_txn_commit", "aec_txn_rollback", "aec_manifest"]
    + [f"revit_{o}" for o in REVIT_OPS]
    + ["acad_draw_polyline", "sw_create_part", "sw_create_assembly"]
)


def contract_tool_defs() -> list[dict[str, Any]]:
    """统一 schema：契约参数由对端编译器保证，这里宽松接收。"""
    loose = {"type": "object", "properties": {}, "additionalProperties": True}
    eng = {"type": "object", "properties": {"engine": {"enum": ["revit", "acad", "sw"]}}, "required": ["engine"]}
    defs = [
        {"name": "aec_txn_begin", "description": "开启缓冲式事务（契约 begin 钩子）", "inputSchema": eng},
        {"name": "aec_txn_commit", "description": "整段缓冲一次提交（契约 commit 钩子；revit=桥 all-or-nothing）", "inputSchema": eng},
        {"name": "aec_txn_rollback", "description": "丢弃缓冲（契约 rollback 钩子）", "inputSchema": eng},
        {"name": "aec_manifest", "description": "最近一次提交的元素清单（契约 manifest_tool）", "inputSchema": eng},
    ]
    for name in sorted(CONTRACT_TOOL_NAMES - {"aec_txn_begin", "aec_txn_commit", "aec_txn_rollback", "aec_manifest"}):
        defs.append({"name": name, "description": f"契约原子调用 {name}（旧参数格式，mm）", "inputSchema": loose})
    return defs


# --------------------------------------------------------------------- 会话
def _session(engine: str) -> dict[str, Any]:
    s = _SESSIONS.get(engine)
    if not s or not s.get("open"):
        raise AecError(ErrorCode.E_CONSTRAINT, f"{engine}: 事务未开启（先 aec_txn_begin）")
    return s


def _reset(engine: str) -> dict[str, Any]:
    s = _SESSIONS.get(engine) or {}
    s.update({"open": True, "calls": [], "level_names": {}})
    _SESSIONS[engine] = s
    return s


def _manifest_entry(tool: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    """清单条目必须回显**原始契约格式**（数组点），对端 verifier 与渲染都按下标取值。"""
    op = tool.split("_", 1)[1]
    raw = dict(raw_args)
    if op in ("create_door", "create_window") and "offset" not in raw:
        raw["offset"] = 0  # 渲染器无条件读 offset；verifier 只比对 expected 侧的键，多键安全
    if op == "create_part":
        shape = raw.get("shape", "box")
        raw["shape"] = shape
        raw["size"] = [raw.get(k, 100) for k in ("width", "depth", "height")] if shape == "box" else [raw.get("diameter", 100), raw.get("height", 100)]
    return {"id": raw["id"], "type": _OP_TYPES[op], **raw}


# ---------------------------------------------------------------- 点位换算
def _pt(v: Any) -> dict[str, float]:
    if isinstance(v, dict):
        return {"x": parse_length(v.get("x", 0)), "y": parse_length(v.get("y", 0)), "z": parse_length(v.get("z", 0))}
    if isinstance(v, (list, tuple)):
        z = v[2] if len(v) > 2 else 0
        return {"x": parse_length(v[0]), "y": parse_length(v[1]), "z": parse_length(z)}
    raise AecError(ErrorCode.E_UNIT, f"无法解析点 {v!r}")


def _num(args: dict[str, Any], key: str, default: float, *, positive: bool = False) -> float:
    v = parse_length(args.get(key, default), field=key)
    if positive and v <= 0:
        raise AecError(ErrorCode.E_UNIT, f"{key} 必须为正，收到 {v}")
    return v


# ---------------------------------------------------------------- 提交路径
def _dist(a: dict[str, float], b: dict[str, float]) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5


def _translate_revit(calls: list[dict[str, Any]], level_names: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """缓冲调用 → 桥 execute_plan steps（纯函数，可离线测试）。

    返回 (steps, wall_raw_by_id)；门/窗按 host 墙几何换算 NewOpening 对角点。
    """
    wall_raw = {c["args"]["id"]: c["raw"] for c in calls if c["op"] == "create_wall"}
    steps: list[dict[str, Any]] = []
    for call in calls:
        op, a = call["op"], call["args"]
        if op == "create_level":
            steps.append({"id": a["id"], "operation": "create_level", "args": {"name": a.get("name"), "elevation": a["elevation"]}})
        elif op == "create_grid":
            steps.append({"id": a["id"], "operation": "create_grid", "args": {"start": _pt(a["start"]), "end": _pt(a["end"]), "name": a.get("name")}})
        elif op == "create_wall":
            args: dict[str, Any] = {"start": _pt(a["start"]), "end": _pt(a["end"]), "height_mm": a["height"], "thickness_mm": a["thickness"]}
            level = level_names.get(a.get("level_id"))
            if level:
                args["level"] = level
            steps.append({"id": a["id"], "operation": "create_wall", "args": args})
        elif op == "create_column":
            c, w, d, h = _pt(a["center"]), a["width"], a["depth"], a["height"]
            steps.append({
                "id": a["id"], "operation": "create_direct_shape",
                "args": {
                    "name": f"柱 {w:g}x{d:g}", "category": "OST_GenericModel",
                    "geometry": [{"kind": "box", "min": {"x": c["x"] - w / 2, "y": c["y"] - d / 2, "z": c["z"]},
                                 "max": {"x": c["x"] + w / 2, "y": c["y"] + d / 2, "z": c["z"] + h}}],
                },
            })
        elif op == "create_slab":
            steps.append({"id": a["id"], "operation": "create_floor", "args": {"boundary": [_pt(p) for p in a["boundary"]]}})
        elif op in ("create_door", "create_window"):
            host = wall_raw.get(a.get("host_id"))
            if host is None:
                raise AecError(ErrorCode.E_NOT_FOUND, f"{op}.host_id 在本计划内找不到宿主墙: {a.get('host_id')}")
            ha, hb = _pt(host["start"]), _pt(host["end"])
            ux, uy = hb["x"] - ha["x"], hb["y"] - ha["y"]
            length = (ux * ux + uy * uy) ** 0.5 or 1.0
            ux, uy = ux / length, uy / length
            off, bot, w, h = float(a.get("offset", 0)), float(a.get("bottom", 0)), a["width"], a["height"]
            p1 = {"x": ha["x"] + ux * off, "y": ha["y"] + uy * off, "z": ha["z"] + bot}
            p2 = {"x": ha["x"] + ux * (off + w), "y": ha["y"] + uy * (off + w), "z": ha["z"] + bot + h}
            steps.append({"id": a["id"], "operation": "create_opening", "args": {"host_id": f"${a['host_id']}", "start": p1, "end": p2}})
        else:
            raise AecError(ErrorCode.E_CONSTRAINT, f"live 后端暂不支持 revit {op}")
    return steps, wall_raw


# 提交后真实几何漂移容差（mm）
_DRIFT_TOL_MM = 1.0


def _postcheck_revit(engine: Any, manifest: list[dict[str, Any]], created_ids: list[int]) -> None:
    """提交后读回真实构件复核（墙：定位线长度/高度/轴对齐厚度）；漂移即删除本次构件并快速失败。"""
    wall_entries = [e for e in manifest if e["type"] == "wall" and e.get("element_id") is not None]
    if not wall_entries:
        return
    q = engine.send({"operation": "execute_plan", "args": {"steps": [{
        "id": "postcheck", "operation": "query_elements",
        "args": {"element_ids": [int(e["element_id"]) for e in wall_entries]},
    }]}, "preview": False}, wait_seconds=90)
    elements: dict[int, dict[str, Any]] = {}
    for s in (q.get("data") or {}).get("steps", []):
        for e in (s.get("data") or {}).get("elements", []):
            elements[e.get("id")] = e
    problems: list[str] = []
    for e in wall_entries:
        real = elements.get(e["element_id"])
        if real is None:
            problems.append(f"{e['id']}: 提交后查不到真实构件 (element_id={e['element_id']})")
            continue
        cs, ce, bb = real.get("curve_start"), real.get("curve_end"), real.get("bounding_box")
        s_pt, e_pt = _pt(e["start"]), _pt(e["end"])
        expected_len = _dist(s_pt, e_pt)
        real_len = _dist(cs, ce) if cs and ce else None
        if real_len is None or abs(real_len - expected_len) > _DRIFT_TOL_MM:
            problems.append(f"{e['id']}: 墙长漂移 expected={expected_len:.1f} real={real_len}")
            continue
        real_h = (bb["max"]["z"] - bb["min"]["z"]) if bb else None
        if real_h is None or abs(real_h - e["height"]) > _DRIFT_TOL_MM:
            problems.append(f"{e['id']}: 墙高漂移 expected={e['height']} real={real_h}")
            continue
        e["real"] = {"length_mm": round(real_len, 1), "height_mm": round(real_h, 1)}
        span_x, span_y = bb["max"]["x"] - bb["min"]["x"], bb["max"]["y"] - bb["min"]["y"]
        if abs(e_pt["x"] - s_pt["x"]) < 0.5:  # 沿 Y 轴墙：厚度=X 向跨度
            real_t = span_x
        elif abs(e_pt["y"] - s_pt["y"]) < 0.5:  # 沿 X 轴墙：厚度=Y 向跨度
            real_t = span_y
        else:
            real_t = None  # 斜墙：跨度含长度分量，后续再解
        if real_t is not None:
            if abs(real_t - e["thickness"]) > _DRIFT_TOL_MM:
                problems.append(f"{e['id']}: 墙厚漂移 expected={e['thickness']} real={real_t}")
                continue
            e["real"]["thickness_mm"] = round(real_t, 1)
    if problems:
        if created_ids:
            engine.send({"operation": "execute_plan", "args": {"steps": [{
                "id": "rollback_drift", "operation": "delete_elements", "args": {"targets": created_ids},
            }]}, "preview": False}, wait_seconds=90)
        raise AecError(ErrorCode.E_GEOM, "提交后真实几何漂移，已删除本次构件（回滚语义）", {"problems": problems})


def _commit_revit(session: dict[str, Any]) -> dict[str, Any]:
    from .engines import get_engine

    steps, _ = _translate_revit(session["calls"], session.get("level_names", {}))
    result = get_engine("revit").execute(steps)
    # 桥返回的每步结果里带真实 element_id，回填进 manifest（存在才回填）
    step_results: dict[str, int] = {}
    data = result.get("data") if isinstance(result, dict) else None
    for s in (data or {}).get("steps", []):
        sid = s.get("id")
        element_id = (s.get("data") or {}).get("element_id") or ((s.get("data") or {}).get("element_ids") or [None])[0]
        if sid and element_id is not None:
            step_results[sid] = int(element_id)
    manifest = []
    created_ids: list[int] = []
    for call in session["calls"]:
        entry = _manifest_entry(call["tool"], call["raw"])
        if entry["id"] in step_results:
            entry["element_id"] = step_results[entry["id"]]
            created_ids.append(entry["element_id"])
        manifest.append(entry)
    _postcheck_revit(get_engine("revit"), manifest, created_ids)
    return {"ok": True, "engine": "revit", "elements": len(manifest), "manifest": manifest,
            "bridge": {"steps": len(steps), "message": result.get("message", "") if isinstance(result, dict) else ""}}


def _commit_acad(session: dict[str, Any]) -> dict[str, Any]:
    """ezdxf 隔离进一次性子进程：server 响应有界，ezdxf 的任何怪癖都炸不到传输层。"""
    import json as _json

    if not _EZDXF_READY:
        raise AecError(ErrorCode.E_INTERNAL, "acad 契约提交需要 ezdxf（本 venv 未安装）")
    spec_calls = [{"op": c["op"], "args": c["args"]} for c in session["calls"]]
    out_dir = Path.cwd() / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"contract_spec_{time.strftime('%Y%m%d_%H%M%S')}.json"
    dxf_path = out_dir / f"contract_acad_{time.strftime('%Y%m%d_%H%M%S')}.dxf"
    spec_path.write_text(_json.dumps({"calls": spec_calls}, ensure_ascii=False), encoding="utf-8")

    builder = Path(__file__).with_name("acad_builder.py")
    devnull = subprocess.DEVNULL
    try:
        proc = subprocess.run(
            [sys.executable, str(builder), str(spec_path), str(dxf_path)],
            cwd=str(Path.cwd()), stdin=devnull, stdout=devnull, stderr=devnull,
            timeout=300, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise AecError(ErrorCode.E_ENGINE_TIMEOUT, "acad builder 子进程超时（300s）", {"spec": str(spec_path)}) from e
    if proc.returncode != 0 or not dxf_path.exists():
        raise AecError(ErrorCode.E_INTERNAL, "acad builder 子进程失败", {"returncode": proc.returncode, "spec": str(spec_path)})
    manifest = [_manifest_entry(c["tool"], c["raw"]) for c in session["calls"]]
    return {"ok": True, "engine": "acad", "elements": len(manifest), "manifest": manifest, "dxf": str(dxf_path)}


def _commit_sw(session: dict[str, Any]) -> dict[str, Any]:
    from .engines import get_engine
    from .compiler import compile_sw
    from .plan import Plan, Step, validate_plan

    calls: list[dict[str, Any]] = []
    for c in session["calls"]:
        a = c["args"]
        if c["op"] == "create_part":
            shape = a.get("shape", "box")
            if shape != "box":
                raise AecError(ErrorCode.E_CONSTRAINT, f"sw live M1 仅支持 box，收到 {shape!r}")
            w = _num(a, "width", 100, positive=True); d = _num(a, "depth", 100, positive=True); h = _num(a, "height", 100, positive=True)
            o = _pt(a.get("origin", [0, 0, 0]))
            calls.append({"op": "create_model_curve", "args": {"start": [o["x"], o["y"]], "end": [o["x"] + w, o["y"]]}})
            calls.append({"op": "create_direct_shape", "args": {"geometry": [{"kind": "box",
                        "min": {"x": o["x"], "y": o["y"], "z": o["z"]},
                        "max": {"x": o["x"] + w, "y": o["y"] + d, "z": o["z"] + h}}]}})
        else:
            raise AecError(ErrorCode.E_CONSTRAINT, "sw live 后端 M1 暂不支持 create_assembly（M2）")
    plan = validate_plan({"version": "0.1", "engine": "sw", "intent": "contract", "instruction": "", "steps": calls})
    result = get_engine("sw").execute(compile_sw(plan))
    manifest = [_manifest_entry(c["tool"], c["raw"]) for c in session["calls"]]
    return {"ok": True, "engine": "sw", "elements": len(manifest), "manifest": manifest, "sw": result.get("created", [])}


# ---------------------------------------------------------------- 调用入口
def handle_contract_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """契约工具分发。异常直接抛出 → MCP isError=true → 对端 runner 快速失败。"""
    if name == "aec_txn_begin":
        engine = args.get("engine", "revit")
        # 批跑隔离：AEC_REVIT_FRESH_DOC=1 时每例自动新建文档副本，
        # 杜绝多例同文档导致的轴网/标高重名冲突（Revit 名称全局唯一）
        if engine == "revit" and os.environ.get("AEC_REVIT_FRESH_DOC") == "1":
            from .engines import get_engine

            doc_dir = Path.cwd() / "runs" / "fresh_docs"
            doc_dir.mkdir(parents=True, exist_ok=True)
            doc_path = doc_dir / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.rvt"
            get_engine("revit").send({
                "operation": "new_project",
                "args": {"save_path": str(doc_path), "overwrite_file": True},
            }, wait_seconds=240)
        _reset(engine)
        return {"ok": True, "engine": engine, "state": "open"}
    if name == "aec_txn_rollback":
        engine = args.get("engine", "revit")
        s = _SESSIONS.get(engine)
        if s:
            s["open"] = False
            s["calls"] = []
        return {"ok": True, "engine": engine, "state": "rolled_back"}
    if name == "aec_txn_commit":
        engine = args.get("engine", "revit")
        s = _session(engine)
        if not s["calls"]:
            raise AecError(ErrorCode.E_CONSTRAINT, f"{engine}: 事务内没有可提交的调用")
        committer = {"revit": _commit_revit, "acad": _commit_acad, "sw": _commit_sw}[engine]
        out = committer(s)
        s["open"] = False
        s["calls"] = []
        s["last_manifest"] = out.pop("manifest")
        s["last_meta"] = {k: v for k, v in out.items() if k != "manifest"}  # dxf 路径/桥步骤数等
        return out
    if name == "aec_manifest":
        engine = args.get("engine", "revit")
        s = _SESSIONS.get(engine) or {}
        if s.get("open"):
            # 框架在事务内（commit 前）做 verify：返回缓冲调用的规范意图快照
            return {"elements": [_manifest_entry(c["tool"], c["raw"]) for c in s["calls"]]}
        return {"elements": list(s.get("last_manifest", []))}

    # ---- 契约原子调用 ----
    engine, _, op = name.partition("_")
    if engine not in ("revit", "acad", "sw"):
        raise AecError(ErrorCode.E_NOT_FOUND, f"未知契约工具 {name!r}")
    a = dict(args)
    element_id = a.get("id")
    if not isinstance(element_id, str) or not element_id:
        raise AecError(ErrorCode.E_CONSTRAINT, f"{name}: 缺少字符串 id")
    # 规范化（数字/点），level 记名
    if op == "create_level":
        a["elevation"] = _num(a, "elevation", 0)
        session = _SESSIONS.setdefault(engine, {"open": False, "calls": [], "level_names": {}})
        session["level_names"][element_id] = str(a.get("name") or element_id)
    elif op in ("create_wall", "create_grid"):
        a["start"], a["end"] = _pt(a.get("start")), _pt(a.get("end"))
        if op == "create_wall":
            a["height"] = _num(a, "height", 3600, positive=True)
            a["thickness"] = _num(a, "thickness", 200, positive=True)
    elif op == "create_column":
        a["center"] = _pt(a.get("center"))
        a["width"] = _num(a, "width", 400, positive=True)
        a["depth"] = _num(a, "depth", a.get("width", 400), positive=True)
        a["height"] = _num(a, "height", 3600, positive=True)
    elif op == "create_slab":
        a["boundary"] = [_pt(p) for p in a.get("boundary", [])]
        if len(a["boundary"]) < 3:
            raise AecError(ErrorCode.E_GEOM, "create_slab: boundary 至少 3 个点")
        a["thickness"] = _num(a, "thickness", 120, positive=True)
        a["elevation"] = _num(a, "elevation", 0)
    elif op == "draw_polyline":
        a["points"] = [_pt(p) for p in a.get("points", [])]
        if len(a["points"]) < 2:
            raise AecError(ErrorCode.E_GEOM, "draw_polyline: 至少 2 个点")
    elif op == "create_part":
        a["origin"] = _pt(a.get("origin", [0, 0, 0]))
        for k in ("width", "depth", "height", "diameter"):
            if k in a:
                a[k] = _num(a, k, 100, positive=True)

    s = _SESSIONS.get(engine)
    if s and s.get("open"):
        s["calls"].append({"tool": name, "op": op, "args": a, "raw": dict(args)})
        return {"ok": True, "buffered": len(s["calls"]), "element": _manifest_entry(name, dict(args))}
    # 无事务：单调用自动开→提→关（等价一次原子事务）
    _reset(engine)
    s = _SESSIONS[engine]
    s["calls"].append({"tool": name, "op": op, "args": a, "raw": dict(args)})
    committer = {"revit": _commit_revit, "acad": _commit_acad, "sw": _commit_sw}[engine]
    out = committer(s)
    s["open"] = False
    s["calls"] = []
    s["last_manifest"] = out.pop("manifest")
    return out
