"""In-process live backend: drives the vendored aec_mcp contract layer directly.

Unlike the subprocess MCPEngine (config/mcp.live.json + stdio), this engine runs
the contract layer in the same process — no stdio transport to deadlock, no
machine-specific absolute paths in config, no per-engine server processes.

Transaction semantics are the contract layer's buffered model:
call → buffer only; commit → one bridge execute_plan (all-or-nothing);
rollback → discard (nothing was ever written).
"""

from __future__ import annotations

import copy
from typing import Any

from ..errors import AECError
from .base import CallbackTransaction, Engine

_ALLOWED = {
    "revit": {"create_level", "create_grid", "create_wall", "create_column", "create_slab", "create_door", "create_window"},
    "acad": {"draw_polyline"},
    "sw": {"create_part", "create_assembly"},
}


class DirectEngine(Engine):
    backend = "direct"

    def __init__(self, name: str = "revit") -> None:
        if name not in _ALLOWED:
            raise ValueError(name)
        self.name = name

    # -- contract layer import is deferred so simulation-only installs still work
    def _contract(self):
        from aec_mcp import contract as _contract

        return _contract

    def _map(self, exc: Exception) -> Exception:
        """aec_mcp.AecError → framework AECError（保留统一错误码）。"""
        if isinstance(exc, AECError):
            return exc
        try:
            from aec_mcp.errors import AecError as _A

            if isinstance(exc, _A):
                return AECError(exc.code, exc.message)
        except ImportError:
            pass
        return exc

    def transaction(self) -> CallbackTransaction:
        c = self._contract()

        def begin() -> None:
            c.handle_contract_tool("aec_txn_begin", {"engine": self.name})

        def commit() -> None:
            c.handle_contract_tool("aec_txn_commit", {"engine": self.name})

        def rollback() -> None:
            c.handle_contract_tool("aec_txn_rollback", {"engine": self.name})

        return CallbackTransaction(begin, commit, rollback)

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        prefix = f"{self.name}_"
        if not tool_name.startswith(prefix):
            raise AECError("E_CONSTRAINT", f"Tool {tool_name} does not belong to {self.name}")
        op = tool_name[len(prefix):]
        if op not in _ALLOWED[self.name]:
            raise AECError("E_CONSTRAINT", f"{self.name} live backend does not support {op}")
        try:
            # deep copy keeps the replayable plan arguments immutable
            return self._contract().handle_contract_tool(tool_name, copy.deepcopy(arguments))
        except Exception as exc:  # noqa: BLE001
            raise self._map(exc) from exc

    def snapshot(self) -> list[dict[str, Any]]:
        try:
            return self._contract().handle_contract_tool("aec_manifest", {"engine": self.name})["elements"]
        except Exception as exc:  # noqa: BLE001
            raise self._map(exc) from exc

    def last_commit_result(self) -> dict[str, Any]:
        """最近一次提交的引擎级元信息（dxf 路径 / 桥步骤数 / SW created）。"""
        session = self._contract()._SESSIONS.get(self.name) or {}
        return dict(session.get("last_meta", {}))
