"""真机评测跑批：eval/cases 全量跑 Revit/AutoCAD/SolidWorks live 后端。

用法（在仓库根目录）：
    $env:REPORTLAB_CJK_REGULAR_FONT = "C:\\Windows\\Fonts\\simhei.ttf"
    uv run python scripts/run_eval_live.py --engine revit --output eval/results-live
    uv run python scripts/run_eval_live.py --limit 5          # 冒烟
    uv run python scripts/run_eval_live.py --only opening     # 单类

每例独立 Runner 事务；MCP server 进程按引擎复用（一次拉起，50 例共用）。
输出：eval/results-live/report.md + results.json（逐例状态/耗时/差异）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from aec_copilot.engines.mcp import MCPEngine  # noqa: E402
from aec_copilot.runner import Runner  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(REPO / "config" / "mcp.live.json"))
    ap.add_argument("--output", default=str(REPO / "eval" / "results-live"))
    ap.add_argument("--engine", choices=["revit", "acad", "sw"], default=None, help="只跑指定引擎")
    ap.add_argument("--only", default=None, help="只跑指定 category")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--attempts", type=int, default=2)
    args = ap.parse_args()

    cases_dir = REPO / "eval" / "cases"
    cases = sorted(cases_dir.glob("*.json"))
    if args.engine:
        cases = [c for c in cases if json.loads(c.read_text(encoding="utf-8")).get("engine") == args.engine]
    if args.only:
        cases = [c for c in cases if json.loads(c.read_text(encoding="utf-8")).get("category") == args.only]
    if args.limit:
        cases = cases[: args.limit]

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    engines: dict[str, MCPEngine] = {}

    def get_engine(name: str) -> MCPEngine:
        if name not in engines:
            engines[name] = MCPEngine.from_config(name, args.config)
        return engines[name]

    results: list[dict] = []
    t_all = time.perf_counter()
    for i, case_path in enumerate(cases, 1):
        case = json.loads(case_path.read_text(encoding="utf-8"))
        cid, engine, category = case["id"], case.get("engine", "revit"), case.get("category", "?")
        t0 = time.perf_counter()
        row = {"id": cid, "category": category, "engine": engine, "status": "error", "attempts": 0, "ms": 0, "error": None}
        try:
            runner = Runner(output_root=str(out_dir / "runs"), max_attempts=args.attempts)
            result = runner.run(case["instruction"], engine=engine, backend="mcp", mcp_config=args.config)
            row["status"] = result.status
            row["attempts"] = len(result.attempts)
            row["elements"] = len(result.elements)
        except Exception as e:  # noqa: BLE001
            row["error"] = f"{type(e).__name__}: {e}"[:300]
            if "--debug" in sys.argv:
                traceback.print_exc()
        row["ms"] = int((time.perf_counter() - t0) * 1000)
        results.append(row)
        mark = {"passed": "✅", "failed": "❌", "error": "💥"}.get(row["status"], "·")
        print(f"[{i}/{len(cases)}] {mark} {cid} ({category}/{engine}) {row['status']} {row['ms']}ms {row['error'] or ''}")

    n_pass = sum(1 for r in results if r["status"] == "passed")
    n_unsupported = sum(1 for r in results if r["status"] != "passed" and r["error"] and "M2" in str(r["error"]))
    total_ms = int((time.perf_counter() - t_all) * 1000)

    lines = [
        "# 真机评测报告（live backend）", "",
        f"- 用例: {len(results)}  通过: {n_pass}  通过率: {n_pass / max(len(results), 1):.0%}"
        f"  预期不支持(M2): {n_unsupported}  总耗时: {total_ms / 1000:.0f}s", "",
        "| case | category | engine | 状态 | 尝试 | 耗时 | 错误 |", "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = {"passed": "✅", "failed": "❌"}.get(r["status"], "💥")
        lines.append(f"| {r['id']} | {r['category']} | {r['engine']} | {mark} {r['status']} | {r['attempts']} | {r['ms']}ms | {(r['error'] or '')[:120]} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "results.json").write_text(json.dumps({"results": results, "total_ms": total_ms}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n通过 {n_pass}/{len(results)}，报告: {out_dir / 'report.md'}")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
