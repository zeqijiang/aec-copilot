"""引擎适配器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..errors import AecError, ErrorCode


class BaseEngine(ABC):
    """所有引擎实现同一接口；capabilities 声明支持的 op 列表。"""

    name: str = "base"
    capabilities: tuple[str, ...] = ()

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """返回 {"ok": bool, ...}；引擎不可用时不抛异常，ok=False 并给 hint。"""

    @abstractmethod
    def execute(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """在一个事务内执行编译后的调用序列；失败时引擎负责回滚并抛 AecError。"""

    def dry_run(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        return {"steps": steps, "warnings": []}

    def ensure_up(self) -> None:
        h = self.health()
        if not h.get("ok"):
            raise AecError(
                ErrorCode.E_ENGINE_DOWN,
                f"{self.name} 引擎不可用: {h.get('state', h.get('message', 'unknown'))}",
                h,
            )
