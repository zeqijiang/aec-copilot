"""建模 DSL（中间层）数据结构与校验。

设计原则（方案 §3.1②）：模型只输出意图级 JSON（本模块的 Plan/Step），
由 compiler 翻译成具体引擎调用。好处：可校验、可重放、可缓存、可评测。

机器可读 schema 见仓库 ``spec/plan.schema.json``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import AecError, ErrorCode
from .units import point_dict

DSL_VERSION = "0.1"

# 规范化原子操作（引擎中立）。各引擎声明自己支持哪些 op。
OPS: dict[str, dict[str, Any]] = {
    # op: {required args, optional args}
    "query_document":     {"req": [], "opt": []},
    "query_catalog":      {"req": ["kind"], "opt": []},
    "query_elements":     {"req": [], "opt": ["category", "element_ids", "name_contains", "limit"]},
    "select_elements":    {"req": ["targets"], "opt": ["show"]},
    "create_level":       {"req": ["elevation"], "opt": ["name"]},
    "create_grid":        {"req": ["start", "end"], "opt": ["name"]},
    "create_wall":        {"req": ["start", "end"], "opt": ["level", "height", "thickness", "type"]},
    "create_floor":       {"req": ["boundary"], "opt": ["level", "offset", "structural", "type"]},
    "create_room":        {"req": ["point"], "opt": ["level", "name", "number"]},
    "create_column":      {"req": ["point"], "opt": ["level", "height", "size"]},
    "create_model_curve": {"req": ["start", "end"], "opt": ["layer"]},
    "create_direct_shape":{"req": ["geometry"], "opt": ["name", "category"]},
    "create_text":        {"req": ["point", "text"], "opt": ["height", "view_id"]},
    "export_image":       {"req": ["output_path"], "opt": ["view_ids", "active_view"]},
    "save_document":      {"req": [], "opt": ["path", "overwrite_file"]},
}


@dataclass
class Step:
    """一个原子建模步骤。args 中的长度/点允许任何受支持写法，编译时统一成 mm。"""

    op: str
    args: dict[str, Any] = field(default_factory=dict)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"op": self.op, "args": self.args}
        if self.id:
            d["id"] = self.id
        return d


@dataclass
class Plan:
    version: str = DSL_VERSION
    engine: str = "revit"          # revit | acad | sw（hint，可被 CLI 覆盖）
    intent: str = "unknown"        # 人类可读意图标签
    instruction: str = ""          # 原始中文指令（评测与追溯用）
    steps: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "engine": self.engine,
            "intent": self.intent,
            "instruction": self.instruction,
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _validate_step(raw: dict[str, Any], index: int) -> Step:
    if not isinstance(raw, dict):
        raise AecError(ErrorCode.E_PLAN_INVALID, f"steps[{index}] 必须是对象", {"raw": raw})
    op = raw.get("op") or raw.get("operation")
    if op not in OPS:
        raise AecError(
            ErrorCode.E_PLAN_INVALID,
            f"steps[{index}]: 未知操作 {op!r}",
            {"supported": sorted(OPS)},
        )
    args = dict(raw.get("args") or {})
    spec = OPS[op]
    for k in spec["req"]:
        if k not in args:
            raise AecError(ErrorCode.E_PLAN_INVALID, f"steps[{index}] op={op}: 缺少必填参数 {k!r}", {"args": args})
    unknown = set(args) - set(spec["req"]) - set(spec["opt"])
    if unknown:
        raise AecError(ErrorCode.E_PLAN_INVALID, f"steps[{index}] op={op}: 未知参数 {sorted(unknown)}", {"args": args})
    step = Step(op=op, args=args, id=raw.get("id"))
    # 关键参数的单位与几何预检（不真正执行）
    if op in ("create_wall", "create_grid", "create_model_curve") or "start" in args:
        if "start" in args:
            point_dict(args["start"], field=f"steps[{index}].start")
        if "end" in args:
            point_dict(args["end"], field=f"steps[{index}].end")
    return step


def validate_plan(data: dict[str, Any]) -> Plan:
    """从 dict 构建并校验 Plan；同时若安装了 jsonschema 则对照 spec/plan.schema.json。"""
    if not isinstance(data, dict):
        raise AecError(ErrorCode.E_PLAN_INVALID, "计划必须是 JSON 对象")
    version = str(data.get("version", DSL_VERSION))
    if not version.startswith("0."):
        raise AecError(ErrorCode.E_PLAN_INVALID, f"DSL 版本不兼容: {version}")
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise AecError(ErrorCode.E_PLAN_INVALID, "计划至少需要一个 step")
    steps = [_validate_step(r, i) for i, r in enumerate(steps_raw)]
    plan = Plan(
        version=version,
        engine=str(data.get("engine", "revit")),
        intent=str(data.get("intent", "unknown")),
        instruction=str(data.get("instruction", "")),
        steps=steps,
    )
    _schema_check(plan.to_dict())
    return plan


def load_plan(path: str | Path) -> Plan:
    return validate_plan(json.loads(Path(path).read_text(encoding="utf-8")))


_SCHEMA_CACHE: dict[str, Any] = {}


def _schema_check(plan_dict: dict[str, Any]) -> None:
    schema_path = Path(__file__).resolve().parents[4] / "spec" / "plan.schema.json"
    if not schema_path.exists():
        return
    try:
        import jsonschema
    except ImportError:
        return
    schema = _SCHEMA_CACHE.get("schema")
    if schema is None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        _SCHEMA_CACHE["schema"] = schema
    try:
        jsonschema.validate(plan_dict, schema)
    except jsonschema.ValidationError as e:
        raise AecError(ErrorCode.E_PLAN_INVALID, f"schema 校验失败: {e.message}", {"path": list(e.absolute_path)})
