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
from .drawing_reader import read_drawing  # noqa: E402
from .drawings import drawings_tool  # noqa: E402
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
            "backend=simulation 无需工业软件；direct 为真机（Revit 需桥在线）；use_vlm=true 时启用视觉复核（需 AEC_VLM_* 凭证）", "inputSchema": _obj(
            {"instruction": {"type": "string"}, "engine": {"enum": ["revit", "acad", "sw"]},
             "backend": {"enum": ["simulation", "direct"]}, "max_attempts": {"type": "integer", "minimum": 1, "maximum": 3},
             "output_root": {"type": "string"}, "use_vlm": {"type": "boolean"}}, ["instruction"])},
        {"name": "aec_audit", "description": "构件清单 JSON 路径（通常取某次 run 的 elements.json）→ 规则审图 → 问题清单 + 报告", "inputSchema": _obj(
            {"path": {"type": "string"}, "output": {"type": "string"}}, ["path"])},
        {"name": "aec_recent_runs", "description": "最近运行一览（run_id/状态/构件数/产物目录）", "inputSchema": _obj(
            {"limit": {"type": "integer", "minimum": 1, "maximum": 50}, "output_root": {"type": "string"}})},
        {"name": "revit_execute_plan", "description": "桥级原语：直接下发 RevitCommandBridge 2.0 计划步骤（preview=true 只校验）", "inputSchema": _obj(
            {"steps": {"type": "array", "items": {"type": "object"}}, "preview": {"type": "boolean"}, "document_title": {"type": "string"}}, ["steps"])},
        {"name": "revit_new_project", "description": "桥级原语：新建（并可另存）Revit 项目文档", "inputSchema": _obj(
            {"save_path": {"type": "string"}, "overwrite_file": {"type": "boolean"}})},
        {"name": "revit_drawings", "description": "一键出图工作流：平面+剖面+立面+3D → 图纸排布(A-101/A-201) → 门窗明细表 → 可选 DWG/PNG 导出。"
            "args: {workflow:'full_set', levels:['F1','F2'], include_schedule:true, export_formats:['dwg','png'], output_dir, preview}", "inputSchema": _obj(
            {"workflow": {"type": "string"}, "levels": {"type": "array", "items": {"type": "string"}},
             "include_schedule": {"type": "boolean"}, "export_formats": {"type": "array", "items": {"type": "string"}},
             "output_dir": {"type": "string"}, "preview": {"type": "boolean"}, "sheet_number_prefix": {"type": "string"}})},
        {"name": "aec_export", "description": "导出当前文档：format = png/dwg/dxf/ifc（ifc 走演示脚本更完整），指定 view_ids 或 active_view", "inputSchema": _obj(
            {"format": {"enum": ["png", "jpg", "dwg", "dxf", "ifc"]}, "view_ids": {"type": "array", "items": {"type": "number"}},
             "active_view": {"type": "boolean"}, "output_dir": {"type": "string"}}, ["format"])},
        {"name": "aec_import_drawing", "description": "图纸识别：DWG/DXF → 图层/实体统计/文字/标注/边界 的结构化报告（Agent 由此『看懂』一张图）。DWG 需本机 AutoCAD 运行", "inputSchema": _obj(
            {"path": {"type": "string"}}, ["path"])},
        {"name": "aec_review_image", "description": "VLM 看图：效果图(PNG) + 原始需求 → 视觉模型比对，返回结构化差异（passed/differences）。"
            "需环境变量 AEC_VLM_API_KEY + AEC_VLM_MODEL（OpenAI 兼容端点）；advisory 模式——几何复核仍是权威", "inputSchema": _obj(
            {"image_path": {"type": "string"}, "instruction": {"type": "string"}}, ["image_path"])},
        {"name": "aec_quantity", "description": "真模型工程量指标：从 Revit 构件读墙体长度/厚/高 → 汇总砌体体积、模板面积、各层统计，"
            "并按建筑面积(gfa，可传或按首层墙外包推算)出单方含量指标（对标造价开项指标）", "inputSchema": _obj(
            {"gfa": {"type": "number"}, "categories": {"type": "array", "items": {"type": "string"}}})},
        {"name": "aec_cost_estimate", "description": "设计→造价：真模型工程量 → GB50854 清单映射 → 组价（演示价目，可导入真实定额）"
            "→ 费用结构分析 → 总造价报告（JSON + Markdown + Excel）。gfa 可传或按楼板推算", "inputSchema": _obj(
            {"gfa": {"type": "number"}, "price_table": {"type": "string"}, "output_dir": {"type": "string"}})},
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
            from aec_mcp.engines.revit.engine import RevitEngine
            from pathlib import Path as _P
            import os as _os

            # 多版本桥探测：扫描 %LOCALAPPDATA%\RevitCommandBridge\<year> 全部年份
            versions = {}
            bridge_base = _P(_os.environ.get("LOCALAPPDATA", "")) / "RevitCommandBridge"
            if bridge_base.exists():
                for year_dir in sorted(bridge_base.iterdir()):
                    if year_dir.is_dir() and year_dir.name.isdigit():
                        st = year_dir / "status.json"
                        data = None
                        try:
                            data = json.loads(st.read_text(encoding="utf-8"))
                        except Exception:  # noqa: BLE001
                            pass
                        versions[year_dir.name] = {"state": (data or {}).get("state", "no_status"),
                                                   "document": (data or {}).get("data", {}).get("document_title")}
            return json.dumps({"version": __version__, "engines": engine_health_all(),
                               "revit_bridges": versions}, ensure_ascii=False, default=str)
        if name == "aec_preview":
            plan = Planner().parse(args["instruction"], args.get("engine", "revit"))
            calls = [{"name": c.name, "arguments": c.arguments} for c in compile_plan(plan)]
            return json.dumps({"plan": plan.model_dump(), "calls": calls, "n_calls": len(calls)}, ensure_ascii=False)
        if name == "aec_run":
            engine = create_engine(args.get("engine", "revit"), args.get("backend", "simulation"))
            vlm = None
            if args.get("use_vlm"):
                from .verifier import VLMReviewer

                candidate = VLMReviewer()
                if candidate.configured:
                    vlm = candidate
            runner = Runner(engine=engine, output_root=args.get("output_root") or str(REPO_ROOT / "runs"),
                            max_attempts=args.get("max_attempts", 3), vlm=vlm)
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
        if name == "revit_drawings":
            from aec_mcp.engines import get_engine

            eng = get_engine("revit")
            out = drawings_tool(args, execute=lambda steps, preview: eng.execute(steps, preview=preview))
            return json.dumps(out, ensure_ascii=False, default=str)
        if name == "aec_export":
            from aec_mcp.engines import get_engine

            fmt = args["format"].lower()
            out_dir = args.get("output_dir") or "out/export"
            step_args: dict[str, Any] = {"format": fmt, "output_path": out_dir}
            if args.get("view_ids"):
                step_args["view_ids"] = args["view_ids"]
            elif fmt in ("png", "jpg"):
                step_args["active_view"] = bool(args.get("active_view", True))
            res = get_engine("revit").send({"operation": "execute_plan",
                                            "args": {"steps": [{"id": "aec_export", "operation": "export", "args": step_args}]},
                                            "preview": False})
            return json.dumps(res, ensure_ascii=False, default=str)
        if name == "aec_review_image":
            from .verifier import VLMReviewer

            vlm = VLMReviewer()
            if not vlm.configured:
                return json.dumps({"ok": False, "code": "E_ENGINE_DOWN",
                                   "message": "VLM 未配置：设置 AEC_VLM_API_KEY + AEC_VLM_MODEL（OpenAI 兼容端点）"}, ensure_ascii=False)
            diffs, advisory, usage = vlm.review(args.get("instruction", ""), args["image_path"])
            return json.dumps({"passed": advisory.get("passed", not diffs), "differences": [d.message for d in diffs],
                               "advisory": advisory, "token_usage": usage,
                               "note": "advisory 模式：视觉观察仅供参考，确定性几何复核仍是权威"}, ensure_ascii=False)
        if name == "aec_import_drawing":
            report = read_drawing(args["path"])
            try:
                report["preview_png"] = render_preview(args["path"])
            except Exception as e:  # noqa: BLE001
                report["preview_png"] = None
                report["preview_error"] = str(e)[:200]
            return json.dumps(report, ensure_ascii=False)
        if name == "aec_quantity":
            from aec_mcp.engines import get_engine

            eng = get_engine("revit")
            q = eng.send({"operation": "execute_plan", "args": {"steps": [
                {"id": "qw", "operation": "query_elements", "args": {"category": "OST_Walls", "limit": 200}},
                {"id": "qf", "operation": "query_elements", "args": {"category": "OST_Floors", "limit": 100}},
                {"id": "qc", "operation": "query_elements", "args": {"category": "OST_GenericModel", "limit": 100}},
            ]}, "preview": False}, wait_seconds=120)
            walls, floors, generics = [], [], []
            for s in (q.get("data") or {}).get("steps", []):
                sid, elements = s.get("id"), (s.get("data") or {}).get("elements", [])
                if sid == "qw":
                    walls = elements
                elif sid == "qf":
                    floors = elements
                elif sid == "qc":
                    generics = elements

            def _bbox_span(el, axis):
                bb = el.get("bounding_box") or {}
                mn, mx = bb.get("min") or {}, bb.get("max") or {}
                return abs((mx.get(axis) or 0) - (mn.get(axis) or 0))

            walls_detail, total_volume, total_formwork, total_len = [], 0.0, 0.0, 0.0
            for w in walls:
                cs, ce, bb = w.get("curve_start"), w.get("curve_end"), w.get("bounding_box")
                if not (cs and ce and bb):
                    continue
                length = ((ce["x"] - cs["x"]) ** 2 + (ce["y"] - cs["y"]) ** 2) ** 0.5
                thickness = min(_bbox_span(w, "x"), _bbox_span(w, "y"))
                height = bb["max"]["z"] - bb["min"]["z"]
                volume = length * thickness * height / 1e9  # mm³ → m³
                formwork = (2 * length * height + 2 * length * thickness) / 1e6  # m²（两侧大面 + 顶面）
                total_len += length
                total_volume += volume
                total_formwork += formwork
                walls_detail.append({"name": w.get("name"), "length_mm": round(length, 1),
                                     "thickness_mm": round(thickness, 1), "height_mm": round(height, 1),
                                     "volume_m3": round(volume, 2)})
            # DirectShape 方柱（OST_GenericModel 中近立方柱体）
            columns_detail, column_volume = [], 0.0
            for g in generics:
                bb = g.get("bounding_box")
                if not bb:
                    continue
                dx = _bbox_span(g, "x"); dy = _bbox_span(g, "y"); dz = _bbox_span(g, "z")
                if 400 <= dx <= 700 and 400 <= dy <= 700 and dz > 2000:  # 柱形判据
                    v = dx * dy * dz / 1e9
                    column_volume += v
                    columns_detail.append({"name": g.get("name"), "section_mm": f"{round(dx)}x{round(dy)}",
                                           "height_mm": round(dz, 1), "volume_m3": round(v, 2)})
            floor_area = sum((_bbox_span(f, "x") * _bbox_span(f, "y")) / 1e6 for f in floors)
            gfa = float(args.get("gfa") or 0) or round(floor_area, 1) or None
            return json.dumps({
                "walls_count": len(walls_detail), "walls": walls_detail[:40],
                "columns_count": len(columns_detail), "columns": columns_detail[:20],
                "column_volume_m3": round(column_volume, 2),
                "totals": {"wall_length_m": round(total_len / 1000, 1),
                           "wall_volume_m3": round(total_volume, 2),
                           "wall_formwork_m2": round(total_formwork, 1),
                           "column_volume_m3": round(column_volume, 2),
                           "floor_area_m2": round(floor_area, 1),
                           "floors_count": len(floors)},
                "indicators": ({"per_gfa_wall_volume_m3_per_m2": round(total_volume / gfa, 3),
                                "per_gfa_wall_formwork_m2_per_m2": round(total_formwork / gfa, 2)} if gfa else None),
                "gfa_source": "provided" if args.get("gfa") else ("derived_from_floors" if floor_area else None),
                "note": "混凝土体积按构件几何推算（墙/柱逐个溯源）；钢筋/砌体量需构件参数读取（M3 扩展）",
            }, ensure_ascii=False)
        if name == "aec_cost_estimate":
            from . import costing

            qty = json.loads(call_tool("aec_quantity", {"gfa": args.get("gfa")}))
            if qty.get("walls_count") in (None, 0):
                return json.dumps({"ok": False, "code": "E_NOT_FOUND",
                                   "message": "当前 Revit 文档没有可计量的墙体（先建模或打开含墙模型）"}, ensure_ascii=False)
            prices = costing.load_prices(Path(args["price_table"])) if args.get("price_table") else None
            report = costing.estimate(qty, gfa=args.get("gfa"), prices=prices)
            out_dir = Path(args.get("output_dir") or (REPO_ROOT / "runs" / "cost"))
            md_path = out_dir / "cost-report.md"
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(costing.to_markdown(report), encoding="utf-8")
            (out_dir / "cost-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            xlsx_path = costing.to_excel(report, out_dir / "cost-report.xlsx")
            return json.dumps({"ok": True, "汇总": report["汇总"], "费用结构": report["费用结构"],
                               "清单项数": len(report["清单明细"]),
                               "markdown": str(md_path), "excel": str(xlsx_path),
                               "免责声明": report["免责声明"]}, ensure_ascii=False)
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
