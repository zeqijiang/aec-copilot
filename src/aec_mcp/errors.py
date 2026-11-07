"""统一错误码与异常类型。

所有引擎适配器（revit / acad / sw）对外只抛 ``AecError``，
``code`` 必须取自 :class:`ErrorCode`，保证上层编排可以按码重试或降级。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class ErrorCode:
    """统一错误码（方案 §3.1①）。"""

    E_UNIT = "E_UNIT"                  # 单位/数值非法
    E_GEOM = "E_GEOM"                  # 几何非法（零长度、不闭合、越界）
    E_NOT_FOUND = "E_NOT_FOUND"        # 引用的类型/族/视图/文件不存在
    E_CONSTRAINT = "E_CONSTRAINT"      # 约束冲突（标高不存在、轴网重合等）
    E_ENGINE_DOWN = "E_ENGINE_DOWN"    # 引擎未运行/未连接
    E_ENGINE_TIMEOUT = "E_ENGINE_TIMEOUT"
    E_PLAN_INVALID = "E_PLAN_INVALID"  # 计划/schema 校验失败
    E_ROLLBACK = "E_ROLLBACK"          # 回滚失败或部分失败
    E_INTERNAL = "E_INTERNAL"          # 其他内部错误


@dataclass
class AecError(Exception):
    """带统一错误码的异常。"""

    code: str
    message: str
    detail: dict = field(default_factory=dict)
    cause: Optional[BaseException] = None

    def __str__(self) -> str:  # pragma: no cover - 展示用
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        d = {"code": self.code, "message": self.message}
        if self.detail:
            d["detail"] = self.detail
        return d

    @classmethod
    def wrap(cls, err: BaseException, code: str = ErrorCode.E_INTERNAL, message: str = "") -> "AecError":
        return cls(code=code, message=message or f"{type(err).__name__}: {err}", cause=err)


def from_bridge_result(result: dict) -> Optional["AecError"]:
    """把 Revit 桥返回的失败结果映射为统一错误码。

    桥协议 2.0 的结果字段是 ``ok`` / ``state`` / ``message``；
    兼容 ``success`` 写法。``state == "failed"`` 一律视为失败。
    """
    ok = result.get("ok")
    if ok is None:
        ok = result.get("success")
    if ok is None and "state" in result:
        ok = result.get("state") != "failed"
    if ok is None:
        ok = not result.get("error")
    if ok:
        return None
    msg = str(result.get("message") or result.get("error") or "bridge command failed")
    text = (msg + " " + str(result.get("data") or "")).lower()
    if "walltype" in text or "类型" in msg and "只支持" in msg:
        code = ErrorCode.E_NOT_FOUND
    elif "单位" in msg or "unit" in text:
        code = ErrorCode.E_UNIT
    elif "几何" in msg or "geometry" in text or "boundary" in text:
        code = ErrorCode.E_GEOM
    elif "找不到" in msg or "not found" in text or "unknown" in text:
        code = ErrorCode.E_NOT_FOUND
    elif "标高" in msg or "level" in text or "constraint" in text:
        code = ErrorCode.E_CONSTRAINT
    elif "timeout" in text or "超时" in msg:
        code = ErrorCode.E_ENGINE_TIMEOUT
    else:
        code = ErrorCode.E_INTERNAL
    return cls_err(code, msg, result)


def cls_err(code: str, msg: str, detail: Any = None) -> "AecError":
    d = detail if isinstance(detail, dict) else {"raw": detail}
    return AecError(code=code, message=msg, detail=d)
