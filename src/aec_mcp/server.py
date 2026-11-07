"""统一 MCP server（``python -m aec_mcp.server`` 或 ``uv run aec-mcp-server``）。

工具命名：``{engine}_{verb}_{noun}``（方案 §3.1①）。
- revit_* ：代理 Revit Command Bridge（文件队列协议 2.0）
- acad_*  ：COM / ezdxf 离线
- sw_*    ：SolidWorks COM
- aec_*   ：编排级（健康、意图→计划、计划→执行）

mcp 依赖为可选（``pip install aec-mcp[server]``），CLI 不需要它。
"""

from __future__ import annotations

import json
from typing import Any

from .engines import get_engine
from .errors import AecError, ErrorCode
from .plan import Plan, Step, validate_plan
from .transaction import Transaction


def _run_steps(engine_name: str, steps: list[dict[str, Any]], *, preview: bool = False, run_dir: str | None = None) -> dict[str, Any]:
    """把引擎原生步骤包成 Plan 执行（供 MCP 工具直接下发步骤）。"""
    plan = validate_plan({"version": "0.1", "engine": engine_name, "intent": "mcp_direct", "instruction": "", "steps": steps})
    engine = get_engine(engine_name)
    txn = Transaction(engine, run_dir)
    return txn.run(plan, engine_name, preview_only=preview)


def _tool(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": schema}


def tool_defs() -> list[dict[str, Any]]:
    from .contract import contract_tool_defs

    obj = {"type": "object", "properties": {}, "required": []}
    return [
        _tool("aec_health", "三引擎健康检查（revit/acad/sw）", obj),
        _tool("aec_plan", "中文指令 → 建模 DSL 计划（不执行）", {
            "type": "object",
            "properties": {"instruction": {"type": "string"}, "engine": {"enum": ["revit", "acad", "sw"]}},
            "required": ["instruction"],
        }),
        _tool("aec_run", "中文指令 → 计划 → preview → commit（含事务与审计日志）", {
            "type": "object",
            "properties": {
                "instruction": {"type": "string"},
                "engine": {"enum": ["revit", "acad", "sw"]},
                "preview": {"type": "boolean", "default": False},
            },
            "required": ["instruction"],
        }),
        _tool("revit_health", "Revit Command Bridge 心跳", obj),
        _tool("revit_execute_plan", "执行 Revit 建模计划（bridge 2.0 steps，preview=true 只校验）", {
            "type": "object",
            "properties": {
                "steps": {"type": "array", "items": {"type": "object"}},
                "preview": {"type": "boolean", "default": False},
                "document_title": {"type": ["string", "null"]},
            },
            "required": ["steps"],
        }),
        _tool("revit_new_project", "新建并保存 Revit 项目（测试副本落盘）", {
            "type": "object",
            "properties": {"save_path": {"type": "string"}, "overwrite_file": {"type": "boolean", "default": False}},
        }),
        _tool("acad_run_plan", "acad 引擎执行计划步骤（AutoCAD COM 或 ezdxf 离线）", {
            "type": "object",
            "properties": {"steps": {"type": "array", "items": {"type": "object"}}, "offline": {"type": "boolean", "default": False}, "preview": {"type": "boolean", "default": False}},
            "required": ["steps"],
        }),
        _tool("sw_run_plan", "SolidWorks 引擎执行计划步骤（mm 入参，编译层换算）", {
            "type": "object",
            "properties": {"steps": {"type": "array", "items": {"type": "object"}}, "preview": {"type": "boolean", "default": False}},
            "required": ["steps"],
        }),
        *contract_tool_defs(),
    ]


def call_tool(name: str, args: dict[str, Any]) -> str:
    """工具分发（server 与 CLI 共用）。返回 JSON 文本。

    契约工具（蓝图智匠框架 MCPEngine）单独路由：异常不吞，抛出 → isError=true，
    让对端 runner 快速失败进入回滚。
    """
    from .contract import CONTRACT_TOOL_NAMES, handle_contract_tool

    if name in CONTRACT_TOOL_NAMES:
        return json.dumps(handle_contract_tool(name, args or {}), ensure_ascii=False, default=str)
    try:
        if name == "aec_health":
            from .engines import engine_health_all

            return json.dumps(engine_health_all(), ensure_ascii=False)
        if name == "aec_plan":
            from aec_planner import parse_intent

            return parse_intent(args["instruction"], engine=args.get("engine")).to_json()
        if name == "aec_run":
            from aec_planner import parse_intent

            plan = parse_intent(args["instruction"], engine=args.get("engine"))
            engine_name = plan.engine
            engine = get_engine(engine_name)
            txn = Transaction(engine)
            out = txn.run(plan, engine_name, preview_only=bool(args.get("preview")))
            return json.dumps(out, ensure_ascii=False, default=str)
        if name == "revit_health":
            return json.dumps(get_engine("revit").health(), ensure_ascii=False)
        if name == "revit_execute_plan":
            eng = get_engine("revit")
            result = eng.send({
                "operation": "execute_plan",
                "args": {"steps": args["steps"]},
                "preview": bool(args.get("preview", False)),
                "document_title": args.get("document_title"),
            })
            return json.dumps(result, ensure_ascii=False, default=str)
        if name == "revit_new_project":
            eng = get_engine("revit")
            result = eng.send({
                "operation": "new_project",
                "args": {"save_path": args.get("save_path"), "overwrite_file": bool(args.get("overwrite_file", False))},
            })
            return json.dumps(result, ensure_ascii=False, default=str)
        if name == "acad_run_plan":
            steps = args["steps"]
            if bool(args.get("preview", False)):
                plan = validate_plan({"version": "0.1", "engine": "acad", "steps": steps})
                return json.dumps({"steps": compile_preview(plan)}, ensure_ascii=False)
            engine = get_engine("acad", offline=bool(args.get("offline", False)))
            return json.dumps(engine.execute(steps), ensure_ascii=False, default=str)
        if name == "sw_run_plan":
            steps = args["steps"]
            if bool(args.get("preview", False)):
                plan = validate_plan({"version": "0.1", "engine": "sw", "steps": steps})
                from .compiler import compile_sw

                return json.dumps({"steps": compile_sw(plan)}, ensure_ascii=False)
            return json.dumps(get_engine("sw").execute(steps), ensure_ascii=False, default=str)
        raise AecError(ErrorCode.E_NOT_FOUND, f"未知工具 {name!r}")
    except AecError as e:
        return json.dumps({"ok": False, **e.to_dict()}, ensure_ascii=False)


def compile_preview(plan: Plan) -> list[dict[str, Any]]:
    from .compiler import compile_plan

    return compile_plan(plan, plan.engine)


def main() -> None:  # pragma: no cover - 需要 mcp 运行时
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    server = Server("aec-mcp")

    @server.list_tools()
    async def _list() -> list[Tool]:
        return [Tool(**t) for t in tool_defs()]

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # 重活（桥往返 20-120s、ezdxf 渲染）不能阻塞事件循环，否则响应卡死在队列里
        import anyio

        text = await anyio.to_thread.run_sync(lambda: call_tool(name, arguments))
        return [TextContent(type="text", text=text)]

    import asyncio

    async def _run() -> None:
        async with stdio_server() as (r, w):
            await server.run(r, w, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
