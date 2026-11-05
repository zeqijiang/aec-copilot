"""Stable public error contract shared by every engine."""
from __future__ import annotations

from typing import Any


class AECError(Exception):
    """An expected, machine-readable failure.

    Error codes are deliberately small and stable; adapter-specific details live
    in ``details['engine_error']`` rather than leaking into the public contract.
    """

    def __init__(self, code: str, message: str, **details: Any) -> None:
        if code not in {"E_UNIT", "E_GEOM", "E_NOT_FOUND", "E_CONSTRAINT", "E_ENGINE_DOWN"}:
            raise ValueError(f"Unsupported public error code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": self.message, "details": self.details}}


def require(condition: bool, code: str, message: str, **details: Any) -> None:
    if not condition:
        raise AECError(code, message, **details)
