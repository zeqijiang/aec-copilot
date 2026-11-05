"""Strict unit parsing. Internal and serialized DSL lengths are always mm."""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Any

from .errors import AECError

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
_LENGTH = re.compile(rf"^\s*({_NUMBER})\s*(mm|毫米|cm|厘米|m|米)?\s*$", re.IGNORECASE)
_FACTORS = {"mm": 1.0, "毫米": 1.0, "cm": 10.0, "厘米": 10.0, "m": 1000.0, "米": 1000.0, None: 1.0}


def mm(value: Any, *, field: str = "length", positive: bool = False) -> float:
    """Convert a number or strings such as ``3.6m`` to finite millimetres."""
    if isinstance(value, bool):
        raise AECError("E_UNIT", f"{field} must be a length, not a boolean", value=value)
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        match = _LENGTH.match(value)
        if not match:
            raise AECError("E_UNIT", f"Invalid length for {field}: {value!r}", value=value)
        result = float(match.group(1)) * _FACTORS[match.group(2).lower() if match.group(2) else None]
    else:
        raise AECError("E_UNIT", f"Invalid length type for {field}", value=repr(value))
    if not math.isfinite(result):
        raise AECError("E_UNIT", f"{field} must be finite", value=value)
    if positive and result <= 0:
        raise AECError("E_GEOM", f"{field} must be greater than zero", value=result, unit="mm")
    # Integers make JSON stable and readable; sub-millimetre precision is kept.
    return round(result, 6)


def point(value: Any, *, field: str = "point", dimensions: int = 3) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) not in (2, 3):
        raise AECError("E_GEOM", f"{field} must contain two or three coordinates", value=value)
    values = [mm(v, field=f"{field}[{i}]") for i, v in enumerate(value)]
    if len(values) == 2:
        values.append(0.0)
    if dimensions == 2:
        return values[:2]
    return values


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def fmt_mm(value: float) -> str:
    return f"{value:g}mm"
