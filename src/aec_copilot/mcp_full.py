"""AEC Copilot 全量 MCP server（录阶式插件形态）。

挂进 DSH / Claude / Cursor 后，Agent 可用自然语言完成整个闭环：
一句中文 → DSL 计划 → 真实引擎事务执行 → 截图 → 校验 → 自动重试 → 审图 → 报告。

启动：python -m aec_copilot.mcp_full（stdio）
工具：
  aec_health        三引擎心跳 + 版本
  aec_preview       中文 → 计划 + 原子调用（零副作用）
  aec_run           全闭环执行（simulation / direct 真机）
  aec_audit         构件清单 → 规则审图 → Excel/PDF/JSON
  aec_recent_runs   最近运行一览
  revit_execute_plan / revit_new_project   桥级原语透传
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Windows 中文报告字体与桥等待的合理默认（环境变量优先）
if sys.platform == "win32":
    _simhei = r"C:\Windows\Fonts\simhei.ttf"
    if not os.environ.get("REPORTLAB_CJK_REGULAR_FONT") and Path(_simhei).is_file():
        os.environ["REPORTLAB_CJK_REGULAR_FONT"] = _simhei
os.environ.setdefault("AEC_REVIT_WAIT", "240")

from . import __version__  # noqa: E402
from .audit import audit_model  # noqa: E402
from .compiler import compile_plan  # noqa: E402
from .engines.registry import create_engine  # noqa: E402
from .errors import AECError  # noqa: E402
from .models import Plan  # noqa: E402
from .planner import Planner  # noqa: E402
from .reports import write_audit_reports  # noqa: E402
from .runner import Runner  # noqa: E402

# 关键：openpyxl / reportlab / PIL 在 worker 线程里首次导入会与主线程 import
# 机制死锁（faulthandler 堆栈实锤卡在 reports.py:13 import openpyxl）。
# 必须在事件循环启动前、主线程内完成预导入，worker 线程从此零首次导入。
import openpyxl  # noqa: F401,E402
import reportlab  # noqa: F401,E402
from PIL import Image  # noqa: F401,E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or []}


def tool_defs() -> list[dict[str, Any]]:
    return [
        {"name": "aec_health", "description": "三引擎（Revit桥/AutoCAD/SolidWorks）健康检查与版本", "inputSchema": _obj({})},
        {"name": "aec_preview", "description": "中文指令 → 建模计划与原子调用清单（零副作用，先看后干）", "inputSchema": _obj(
            {"instruction": {"type": "string"}, "engine": {"enum": ["revit", "acad", "sw"]}}, ["instruction"])},
        {"name": "aec_run", "description": "全闭环：中文 → 计划 → 事务执行 → 截图 → 校验 → 最多3轮重试 → Excel/PDF 报告。"
            "backend=simulation 无需工业软件；direct 为真机（Revit 需桥在线）", "inputSchema": _obj(
            {"instruction": {"type": "string"}, "engine": {"enum": ["revit", "acad", "sw"]},
             "backend": {"enum": ["simulation", "direct"]}, "max_attempts": {"type": "integer", "minimum": 1, "maximum": 3},
             "output_root": {"type": "string"}}, ["instruction"])},
        {"name": "aec_audit", "description": "构件清单 JSON 路径（通常取某次 run 的 elements.json）→ 规则审图 → 问题清单 + 报告", "inputSchema": _obj(
            {"path": {"type": "string"}, "output": {"type": "string"}}, ["path"])},
        {"name": "aec_recent_runs", "description": "最近运行一览（run_id/状态/构件数/产物目录）", "inputSchema": _obj(
            {"limit": {"type": "integer", "minimum": 1, "maximum": 50}, "output_root": {"type": "string"}})},
        {"name": "revit_execute_plan", "description": "桥级原语：直接下发 RevitCommandBridge 2.0 计划步骤（preview=true 只校验）", "inputSchema": _obj(
            {"steps": {"type": "array", "items": {"type": "object"}}, "preview": {"type": "boolean"}, "document_title": {"type": "string"}}, ["steps"])},
        {"name": "revit_new_project", "description": "桥级原语：新建（并可另存）Revit 项目文档", "inputSchema": _obj(
            {"save_path": {"type": "string"}, "overwrite_file": {"type": "boolean"}})},
    ]


def _summary(result) -> dict[str, Any]:
    last = result.attempts[-1].verification if result.attempts else None
    return {
        "run_id": result.run_id,
        "status": result.status,
        "backend": result.backend,
        "engine": result.engine,
        "instruction": result.instruction,
        "elements": len(result.elements),
        "attempts": len(result.attempts),
        "passed": bool(last.passed) if last else False,
        "differences": [d.message for d in (last.differences if last else [])][:10],
        "screenshot": result.screenshot,
        "reports": result.reports,
        "output_dir": result.output_dir,
    }


def call_tool(name: str, args: dict[str, Any]) -> str:
    try:
        if name == "aec_health":
            from aec_mcp.engines import engine_health_all

            return json.dumps({"version": __version__, "engines": engine_health_all()}, ensure_ascii=False, default=str)
        if name == "aec_preview":
            plan = Planner().parse(args["instruction"], args.get("engine", "revit"))
            calls = [{"name": c.name, "arguments": c.arguments} for c in compile_plan(plan)]
            return json.dumps({"plan": plan.model_dump(), "calls": calls, "n_calls": len(calls)}, ensure_ascii=False)
        if name == "aec_run":
            engine = create_engine(args.get("engine", "revit"), args.get("backend", "simulation"))
            runner = Runner(engine=engine, output_root=args.get("output_root") or str(REPO_ROOT / "runs"),
                            max_attempts=args.get("max_attempts", 3))
            result = runner.run(args["instruction"], engine=engine.name)
            return json.dumps(_summary(result), ensure_ascii=False)
        if name == "aec_audit":
            data = json.loads(Path(args["path"]).read_text(encoding="utf-8"))
            elements = data.get("elements") if isinstance(data, dict) else data
            report = audit_model(elements)
            files = write_audit_reports(report, elements, args.get("output") or str(REPO_ROOT / "runs" / "audit"))
            return json.dumps({"issue_count": report.issue_count,
                               "by_severity": {s: sum(1 for i in report.issues if i.severity == s) for s in ("error", "warning", "info")},
                               "issues": [f"[{i.severity}] {i.rule_id}: {i.message}" for i in report.issues][:20],
                               "reports": files, "disclaimer": report.disclaimer}, ensure_ascii=False)
        if name == "aec_recent_runs":
            root = Path(args.get("output_root") or (REPO_ROOT / "runs"))
            rows = []
            for run_json in sorted(root.glob("*/run.json"), key=lambda p: p.stat().st_mtime, reverse=True)[: args.get("limit", 10)]:
                r = json.loads(run_json.read_text(encoding="utf-8"))
                rows.append({"run_id": r["run_id"], "status": r["status"], "engine": r["engine"],
                             "elements": len(r.get("elements", [])), "instruction": r["instruction"][:60],
                             "output_dir": r["output_dir"]})
            return json.dumps({"runs": rows}, ensure_ascii=False)
        if name == "revit_execute_plan":
            from aec_mcp.engines import get_engine

            res = get_engine("revit").send({"operation": "execute_plan",
                                            "args": {"steps": args["steps"]},
                                            "preview": bool(args.get("preview", False)),
                                            "document_title": args.get("document_title")})
            return json.dumps(res, ensure_ascii=False, default=str)
        if name == "revit_new_project":
            from aec_mcp.engines import get_engine

            res = get_engine("revit").send({"operation": "new_project",
                                            "args": {"save_path": args.get("save_path"), "overwrite_file": bool(args.get("overwrite_file", False))}})
            return json.dumps(res, ensure_ascii=False, default=str)
        raise AECError("E_NOT_FOUND", f"未知工具 {name!r}")
    except AECError as e:
        return json.dumps({"ok": False, "code": e.code, "message": e.message}, ensure_ascii=False, default=str)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"ok": False, "code": "E_INTERNAL", "message": f"{type(e).__name__}: {e}"}, ensure_ascii=False, default=str)


def main() -> None:  # pragma: no cover - 需要 MCP 客户端
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    server = Server("aec-copilot")

    @server.list_tools()
    async def _list() -> list[Tool]:
        return [Tool(**t) for t in tool_defs()]

    @server.call_tool()
    async def _call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        import anyio

        text = await anyio.to_thread.run_sync(lambda: call_tool(name, arguments or {}))
        return [TextContent(type="text", text=text)]

    import asyncio

    # 挂死诊断开关：AEC_FAULT_DUMP=1 时每 40s dump 全进程线程堆栈到 server_fault.log
    if os.environ.get("AEC_FAULT_DUMP") == "1":
        try:
            import faulthandler

            _fault_log = open("server_fault.log", "w", encoding="utf-8")
            faulthandler.dump_traceback_later(40, repeat=True, file=_fault_log)
        except Exception:  # noqa: BLE001
            pass

    async def _run() -> None:
        async with stdio_server() as (r, w):
            await server.run(r, w, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
