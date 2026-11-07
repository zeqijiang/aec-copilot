"""引擎注册表。"""

from __future__ import annotations

import os
from typing import Any

from .base import BaseEngine
from ..errors import AecError, ErrorCode

_ENGINE_CACHE: dict[str, BaseEngine] = {}


def get_engine(name: str, **kwargs: Any) -> BaseEngine:
    """构造（带缓存的）引擎实例。acad 支持 offline=True 强制 ezdxf 离线。"""
    key = f"{name}:{sorted(kwargs.items())}"
    if key in _ENGINE_CACHE:
        return _ENGINE_CACHE[key]
    if name == "revit":
        from .revit.engine import RevitEngine

        kwargs.pop("offline", None)
        kwargs.pop("output_dir", None)
        eng: BaseEngine = RevitEngine(**kwargs)
    elif name == "acad":
        if kwargs.get("offline") or os.environ.get("AEC_ACAD_OFFLINE") == "1":
            from .acad.engine import AcadOfflineEngine

            kwargs.pop("offline", None)
            eng = AcadOfflineEngine(**kwargs)
        else:
            from .acad.engine import AcadComEngine

            kwargs.pop("offline", None)
            eng = AcadComEngine(**kwargs)
    elif name == "sw":
        from .sw.engine import SwEngine

        eng = SwEngine(**kwargs)
    else:
        raise AecError(ErrorCode.E_PLAN_INVALID, f"未知引擎 {name!r}", {"supported": ["revit", "acad", "sw"]})
    _ENGINE_CACHE[key] = eng
    return eng


def engine_health_all() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in ("revit", "acad", "sw"):
        try:
            out[n] = get_engine(n).health()
        except Exception as e:  # noqa: BLE001
            out[n] = {"ok": False, "state": "error", "message": str(e)}
    return out
