from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Engine
from .mcp import MCPEngine
from .sim import SimulationEngine


def create_engine(name: str = "revit", backend: str = "simulation", mcp_config: str | Path | None = None) -> Engine:
    if backend == "simulation":
        return SimulationEngine(name)
    if backend == "mcp":
        if not mcp_config:
            raise ValueError("--mcp-config is required for the live MCP backend")
        return MCPEngine.from_config(name, mcp_config)
    raise ValueError(f"Unknown backend: {backend}")
