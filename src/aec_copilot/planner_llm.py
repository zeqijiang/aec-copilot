"""LLM-first 规划器：中文指令 → 受约束建模 DSL（对比评测的 LLM 侧）。

与规则版 Planner 的关系：LLM-first，规则版仅作回退（回退计入 fallback 指标）。
响应经过三重校验：json.loads → Plan.model_validate → compile_plan 试编译，
任何一环失败记规划失败（绝不把未校验的 LLM 输出交给引擎）。

凭证（OpenAI 兼容端点，env 或构造参数）：
    AEC_LLM_API_KEY / AEC_LLM_MODEL / AEC_LLM_BASE_URL(默认 https://api.deepseek.com/v1)
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from .compiler import compile_plan
from .errors import AECError
from .models import Plan
from .planner import Planner

SCHEMA_HINT = {
    "schema_version": "1.0",
    "engine": "revit",
    "units": "mm",
    "operations": [],
}

OP_RULES = (
    "Allowed ops — intents (compiler expands them): "
    'create_room{width,depth,height?,thickness?,include_slab?}, '
    'create_frame{width,depth,height?,column_size?,include_slab?,bays_x?,bays_y?}, '
    'create_building{width,depth,floors,floor_height?,wall_thickness?,partition?,corner_columns?,entrance_door?,include_grids?,include_slab?}. '
    "Atomic ops: create_level{name,elevation}, create_wall{start:[x,y,z],end:[x,y,z],height,thickness,level_id?}, "
    "create_column{center,width,depth,height}, create_slab{boundary:[[x,y,z]×4],thickness,elevation}, "
    "create_grid{start,end,name}, create_door/create_window{host_id,width,height,bottom,offset?}, "
    'draw_polyline{points,closed?} (acad), create_part{shape,width,depth,height} / create_assembly{parts:[ids]} (sw).'
)

FEWSHOT = [
    {
        "instruction": "生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm",
        "output": {
            "schema_version": "1.0", "engine": "revit", "units": "mm",
            "operations": [{"op": "create_building", "id": "bld", "width": "12m", "depth": "8m",
                            "floors": 2, "floor_height": "3.3m", "wall_thickness": "200mm"}],
        },
    },
    {
        "instruction": "生成一个6m×4m的房间，南墙加一扇900mm宽2100mm高的门",
        "output": {
            "schema_version": "1.0", "engine": "revit", "units": "mm",
            "operations": [{"op": "create_room", "id": "room", "width": "6m", "depth": "4m"},
                           {"op": "create_door", "id": "door_1", "host_id": "room_wall_s", "width": "900mm", "height": "2100mm", "bottom": 0}],
        },
    },
]


class LLMPlanner:
    """LLM-first 规划器：usage 计量 + 规则版回退统计。"""

    def __init__(self, *, api_key: str | None = None, model: str | None = None, base_url: str | None = None,
                 timeout: float = 90.0) -> None:
        self.api_key = api_key or os.getenv("AEC_LLM_API_KEY", "")
        self.model = model or os.getenv("AEC_LLM_MODEL", "")
        self.base_url = (base_url or os.getenv("AEC_LLM_BASE_URL", "https://api.deepseek.com/v1")).rstrip("/")
        self.timeout = timeout
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.fallback_to_rules = False

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def _request(self, instruction: str, engine: str) -> dict[str, Any]:
        shots = "\n\n".join(
            f"指令：{s['instruction']}\n输出：{json.dumps(s['output'], ensure_ascii=False)}" for s in FEWSHOT
        )
        prompt = (
            f"把中文建筑工程指令翻译成受约束的建模 DSL JSON。只输出 JSON。\n"
            f"目标引擎：{engine}。单位 mm（可写 '6m'/'200mm'）。\n{OP_RULES}\n"
            f"要求：每个 operation 必须有唯一 id；门窗必须引用本计划内已存在的墙体 id 作 host_id；"
            f"不要发明白名单之外的 op；不要输出解释。\n\n示例：\n{shots}\n\n指令：{instruction}\n输出："
        )
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You output only validated AEC modeling DSL JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.load(response)
        usage = payload.get("usage", {})
        self.last_usage = {k: int(usage.get(k, 0)) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        return json.loads(payload["choices"][0]["message"]["content"])

    def parse(self, instruction: str, engine: str | None = None) -> Plan:
        """LLM-first；LLM 不可用/校验失败 → 规则版回退（fallback_to_rules 置位）。"""
        self.fallback_to_rules = False
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        engine = engine or "revit"
        if not self.configured:
            self.fallback_to_rules = True
            return Planner().parse(instruction, engine)
        try:
            data = self._request(instruction, engine)
            data.update({"instruction": instruction, "engine": engine, "units": "mm", "schema_version": "1.0"})
            data["metadata"] = {**data.get("metadata", {}), "planner": "llm-first"}
            plan = Plan.model_validate(data)
            compile_plan(plan)  # 三重校验之三：必须能编译成合法原子调用
            return plan
        except (AECError, ValueError, KeyError, json.JSONDecodeError):
            # 网络/格式/校验失败 → 规则版兜底，保证评测管道不中断
            self.fallback_to_rules = True
            self.last_usage = self.last_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            return Planner().parse(instruction, engine)
