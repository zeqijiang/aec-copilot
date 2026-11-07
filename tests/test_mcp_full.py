"""mcp_full server 生成测试：与 DSH 挂载完全相同的启动方式。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="需要 live extra（pip install 'mcp>=1,<2'）")

REPO = Path(__file__).resolve().parents[1]


async def test_mcp_full_tools_and_simulation_run():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "aec_copilot.mcp_full"],
        cwd=str(REPO),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            assert init.serverInfo.name == "aec-copilot"

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"aec_health", "aec_preview", "aec_run", "aec_audit", "revit_execute_plan"} <= names

            prev = json.loads((await session.call_tool("aec_preview", {"instruction": "生成一个6m×4m的房间"})).content[0].text)
            assert prev["n_calls"] == 4  # 四面墙

            run = json.loads((await session.call_tool("aec_run", {
                "instruction": "生成一个6m×4m的房间", "backend": "simulation", "max_attempts": 1,
                "output_root": "runs-mcp-test",
            })).content[0].text)
            assert run["status"] == "passed" and run["elements"] == 4
            assert run["reports"].get("pdf") and run["reports"].get("excel")
