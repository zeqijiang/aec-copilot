"""统一单位体系：内部一律毫米（mm）。

长度参数接受：
- 裸数字（int/float）→ 按 mm 解释
- ``"3600"`` / ``"3600mm"`` / ``"3.6m"`` / ``"3600毫米"`` / ``"120cm"`` / ``"12ft"``
- ``{"value": 3.6, "unit": "m"}``

点统一 ``{"x": 0, "y": 0, "z": 0}``，缺省 z=0，坐标同样按 mm。
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .errors import AecError, ErrorCode

_LEN_RE = re.compile(
    r"^\s*(?P<val>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m|ft|毫米|厘米|米|英尺)?\s*$",
    re.IGNORECASE,
)

_FACTORS: dict[str, float] = {
    "mm": 1.0,
    "毫米": 1.0,
    "cm": 10.0,
    "厘米": 10.0,
    "m": 1000.0,
    "米": 1000.0,
    "ft": 304.8,
    "英尺": 304.8,
    "": 1.0,
    None: 1.0,
}


def parse_length(value: Any, *, field: str = "length") -> float:
    """把任意长度写法解析成毫米（float）。非法输入抛 ``E_UNIT``。"""
    if isinstance(value, bool):
        raise AecError(ErrorCode.E_UNIT, f"{field}: 布尔值不是长度", {"value": value})
    if isinstance(value, (int, float)):
        v = float(value)
        if v != v or v in (float("inf"), float("-inf")):
            raise AecError(ErrorCode.E_UNIT, f"{field}: 非法数值 {value!r}")
        return v
    if isinstance(value, dict):
        if "value" in value:
            unit = str(value.get("unit", "mm")).strip().lower()
            if unit not in _FACTORS:
                raise AecError(ErrorCode.E_UNIT, f"{field}: 未知单位 {unit!r}", {"value": value})
            return float(value["value"]) * _FACTORS[unit]
        raise AecError(ErrorCode.E_UNIT, f"{field}: 缺少 value 字段", {"value": value})
    if isinstance(value, str):
        m = _LEN_RE.match(value)
        if not m:
            raise AecError(ErrorCode.E_UNIT, f"{field}: 无法解析长度 {value!r}", {"value": value})
        unit = (m.group("unit") or "").lower()
        return float(m.group("val")) * _FACTORS[unit]
    raise AecError(ErrorCode.E_UNIT, f"{field}: 不支持的长度类型 {type(value).__name__}", {"value": value})


def parse_point(point: Any, *, field: str = "point") -> tuple[float, float, float]:
    """把 ``{"x":..,"y":..,"z":..}`` 或 ``[x, y(, z)]`` 解析成毫米三元组。"""
    if isinstance(point, dict):
        if "x" not in point or "y" not in point:
            raise AecError(ErrorCode.E_UNIT, f"{field}: 需要 x/y 字段", {"value": point})
        z = point.get("z", 0)
        return (
            parse_length(point["x"], field=f"{field}.x"),
            parse_length(point["y"], field=f"{field}.y"),
            parse_length(z, field=f"{field}.z"),
        )
    if isinstance(point, (list, tuple)):
        if len(point) not in (2, 3):
            raise AecError(ErrorCode.E_GEOM, f"{field}: 点需要 2 或 3 个分量", {"value": point})
        vals = [parse_length(v, field=f"{field}[{i}]") for i, v in enumerate(point)]
        if len(vals) == 2:
            vals.append(0.0)
        return (vals[0], vals[1], vals[2])
    raise AecError(ErrorCode.E_UNIT, f"{field}: 不支持的点类型 {type(point).__name__}", {"value": point})


def point_dict(point: Any, *, field: str = "point") -> dict[str, float]:
    """解析并输出规范化的 ``{"x","y","z"}`` 毫米字典。"""
    x, y, z = parse_point(point, field=field)
    return {"x": x, "y": y, "z": z}


def fmt_mm(v: float) -> str:
    """毫米 → 人类可读（自动选 mm/m）。"""
    if abs(v) >= 1000 and abs(v) % 1 == 0:
        return f"{v:g}mm"
    if abs(v) >= 1000:
        return f"{v / 1000:g}m"
    return f"{v:g}mm"


def normalize_points(points: Iterable[Any], *, field: str = "points") -> list[dict[str, float]]:
    return [point_dict(p, field=field) for p in points]
