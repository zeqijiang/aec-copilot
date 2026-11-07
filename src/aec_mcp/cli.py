"""aec 命令行：plan / run / tools / health。

示例：
    aec plan "在 0,0 画一面 6m 长的墙"
    aec run  "在 0,0 画一面 6m 长的墙" --engine acad --offline
    aec run  "生成一栋 30m×20m 的两层小楼" --engine revit --preview
    aec tools
    aec health
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from aec_mcp.compiler import compile_plan
from aec_mcp.engines import engine_health_all, get_engine
from aec_mcp.errors import AecError
from aec_mcp.plan import Plan, Step, validate_plan
from aec_mcp.transaction import Transaction

REPO_ROOT = Path(__file__).resolve().parents[4]


def _auto_engine() -> str:
    h = get_engine("revit").health()
    return "revit" if h.get("ok") else "acad"


def _ensure_save_step(plan: Plan, path: Path) -> Plan:
    if any(s.op == "save_document" for s in plan.steps):
        return plan
    plan.steps.append(Step(op="save_document", id="save", args={"path": str(path)}))
    return plan


def cmd_plan(args: argparse.Namespace) -> int:
    from aec_planner import parse_intent

    plan = parse_intent(args.instruction, engine=args.engine)
    print(plan.to_json())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from aec_planner import parse_intent

    t_start = time.perf_counter()
    plan = parse_intent(args.instruction, engine=args.engine)
    engine_name = args.engine or _auto_engine()
    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = (Path(args.out) if args.out else REPO_ROOT / "runs" / f"{run_id}_{engine_name}").resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    engine = get_engine(engine_name, offline=args.offline, output_dir=str(run_dir))

    # acad 离线/COM：自动补 save 步骤（文件即交付物与事务边界）
    if engine_name == "acad":
        plan = _ensure_save_step(plan, run_dir / "model.dxf")

    txn = Transaction(engine, run_dir)
    result = txn.run(plan, engine_name, preview_only=args.preview)
    (run_dir / "plan.json").write_text(plan.to_json(), encoding="utf-8")

    artifacts: list[str] = []
    if not args.preview and engine_name == "revit":
        # revit 桥要求 export 单独成计划
        export_plan = Plan(engine="revit", intent="export", instruction="[auto] export png",
                           steps=[Step(op="export_image", id="export", args={"output_path": str(run_dir / "revit_view.png"), "active_view": True})])
        try:
            txn2 = Transaction(engine, run_dir)
            export_out = txn2.run(export_plan, "revit")
            if not export_out["committed"]["result"].get("ok", True):
                raise AecError("E_INTERNAL", "导出失败")
            artifacts.append("revit_view.png")
        except AecError as e:
            print(f"[warn] PNG 导出失败（不阻塞建模）: {e}", file=sys.stderr)

    if not args.preview and engine_name == "acad":
        dxf = run_dir / "model.dxf"
        if dxf.exists() and hasattr(engine, "export_png"):
            try:
                engine.export_png(dxf, run_dir / "model.png")
                artifacts.append("model.png")
            except AecError as e:
                print(f"[warn] PNG 导出失败: {e}", file=sys.stderr)
        if dxf.exists():
            artifacts.append("model.dxf")

    (run_dir / "result.json").write_text(
        json.dumps(result["committed"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    dur_ms = int((time.perf_counter() - t_start) * 1000)

    report = {
        "run_id": run_id,
        "instruction": plan.instruction,
        "intent": plan.intent,
        "engine": engine_name,
        "preview_only": args.preview,
        "n_steps": len(plan.steps),
        "duration_ms": dur_ms,
        "run_dir": str(run_dir),
        "artifacts": artifacts,
    }
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_tools(_: argparse.Namespace) -> int:
    from aec_mcp.plan import OPS

    for name, eng in (("revit", get_engine("revit")), ("acad", get_engine("acad")), ("sw", get_engine("sw"))):
        h = eng.health()
        print(f"== {name} == ok={h.get('ok')} state={h.get('state')}")
        for op in eng.capabilities:
            spec = OPS.get(op, {})
            print(f"  {name}_{op}  args={spec.get('req', [])} opt={spec.get('opt', [])}")
    return 0


def cmd_health(_: argparse.Namespace) -> int:
    print(json.dumps(engine_health_all(), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aec", description="AI 建筑师 Copilot CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan", help="中文指令 → DSL 计划（不执行）")
    sp.add_argument("instruction")
    sp.add_argument("--engine", choices=["revit", "acad", "sw"], default=None)
    sp.set_defaults(func=cmd_plan)

    sr = sub.add_parser("run", help="中文指令 → 计划 → 执行（preview→commit）")
    sr.add_argument("instruction")
    sr.add_argument("--engine", choices=["revit", "acad", "sw"], default=None)
    sr.add_argument("--offline", action="store_true", help="acad 走 ezdxf 离线引擎（无需 AutoCAD）")
    sr.add_argument("--preview", action="store_true", help="只出计划与校验，不写引擎")
    sr.add_argument("--out", default=None, help="输出目录（默认 runs/<ts>_<engine>）")
    sr.set_defaults(func=cmd_run)

    st = sub.add_parser("tools", help="列出工具目录（引擎 × op）")
    st.set_defaults(func=cmd_tools)

    sh = sub.add_parser("health", help="三引擎健康检查")
    sh.set_defaults(func=cmd_health)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except AecError as e:
        print(json.dumps(e.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
