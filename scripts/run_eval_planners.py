"""双规划器对比评测：规则版 vs LLM 版（planner 级，与 golden 同口径比对）。

判定：parse → compile_plan → expected_manifest(calls) 与 eval/golden/<id>.json
逐字段比对（复用 verifier._equal，0.01mm 容差）。

用法：
    uv run python scripts/run_eval_planners.py                    # 规则版基线
    $env:AEC_LLM_API_KEY="sk-.."; $env:AEC_LLM_MODEL="deepseek-chat"
    uv run python scripts/run_eval_planners.py --llm              # 加跑 LLM 列
    uv run python scripts/run_eval_planners.py --llm --limit 10   # 快速验证
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from aec_copilot.compiler import compile_plan, expected_manifest  # noqa: E402
from aec_copilot.errors import AECError  # noqa: E402
from aec_copilot.models import ToolCall  # noqa: E402
from aec_copilot.planner import Planner  # noqa: E402
from aec_copilot.planner_llm import LLMPlanner  # noqa: E402
from aec_copilot.verifier import _equal  # noqa: E402


def compare_with_golden(calls: list[ToolCall], golden: list[dict], loose: bool = False) -> list[str]:
    """expected_manifest(calls) vs golden。loose=True 忽略 id/host_id（同义变体：LLM 生成的
    元素命名可能与 golden 不同，按 type 排序配对后只比几何/参数字段）。"""
    expected = expected_manifest(calls)
    if loose:
        def strip(e: dict) -> dict:
            return {k: v for k, v in e.items() if k not in ("id", "host_id")}
        expected = sorted((strip(e) for e in expected), key=lambda e: (e.get("type", ""), json.dumps(e, sort_keys=True, default=str)))
        golden = sorted((strip(e) for e in golden if isinstance(e, dict)), key=lambda e: (e.get("type", ""), json.dumps(e, sort_keys=True, default=str)))
        if len(expected) != len(golden):
            return [f"COUNT {len(expected)} != {len(golden)}"]
        diffs: list[str] = []
        for want, found in zip(expected, golden):
            if want.get("type") != found.get("type"):
                diffs.append(f"TYPE {want.get('type')} != {found.get('type')}")
                continue
            for key, value in want.items():
                if key not in found:
                    diffs.append(f"MISSING_FIELD {want.get('type')}.{key}")
                elif not _equal(value, found[key]):
                    diffs.append(f"VALUE {want.get('type')}.{key}: {value} != {found[key]}")
        return diffs
    actual = {e.get("id"): e for e in golden if isinstance(e, dict)}
    diffs = []
    for wanted in expected:
        found = actual.get(wanted["id"])
        if found is None:
            diffs.append(f"MISSING {wanted['id']}")
            continue
        for key, value in wanted.items():
            if key not in found:
                diffs.append(f"MISSING_FIELD {wanted['id']}.{key}")
            elif not _equal(value, found[key]):
                diffs.append(f"VALUE {wanted['id']}.{key}: {value} != {found[key]}")
    return diffs


def run_side(name: str, cases: list[dict], golden_dir: Path, llm: LLMPlanner | None, loose: bool = False) -> list[dict]:
    rows: list[dict] = []
    for case in cases:
        cid, engine = case["id"], case.get("engine", "revit")
        golden_id = case.get("original", cid)  # 变体用例取原例 golden
        golden = json.loads((golden_dir / f"{golden_id}.json").read_text(encoding="utf-8"))
        if not isinstance(golden, list):
            golden = golden.get("elements", [])
        planner = llm if (name == "llm") else Planner()
        if isinstance(planner, LLMPlanner):
            planner.fallback_to_rules = False
        t0 = time.perf_counter()
        row = {"id": cid, "category": case.get("category", "?"), "status": "error", "ms": 0,
               "fallback": False, "tokens": 0, "diffs": []}
        try:
            plan = planner.parse(case["instruction"], engine)
            calls = compile_plan(plan)
            row["diffs"] = compare_with_golden(calls, golden, loose=loose)[:4]
            row["status"] = "passed" if not row["diffs"] else "failed"
        except AECError as e:
            row["status"] = "failed"
            row["diffs"] = [f"{e.code}: {e.message}"][:2]
        except Exception as e:  # noqa: BLE001
            row["status"] = "error"
            row["diffs"] = [f"{type(e).__name__}: {e}"][:2]
        row["ms"] = int((time.perf_counter() - t0) * 1000)
        row["fallback"] = bool(getattr(planner, "fallback_to_rules", False))
        row["tokens"] = planner.last_usage.get("total_tokens", 0)
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(REPO / "eval" / "cases"))
    ap.add_argument("--golden", default=str(REPO / "eval" / "golden"))
    ap.add_argument("--output", default=str(REPO / "eval" / "results-planners"))
    ap.add_argument("--llm", action="store_true", help="加跑 LLM 列（需 AEC_LLM_API_KEY/MODEL）")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default=None, help="只跑指定 category")
    ap.add_argument("--llm-key", default=None)
    ap.add_argument("--llm-model", default=None)
    ap.add_argument("--llm-base", default=None)
    ap.add_argument("--loose", action="store_true", help="宽松比对（忽略 id/host_id，用于同义变体集）")
    args = ap.parse_args()

    cases = sorted(Path(args.cases).glob("*.json"))
    if args.only:
        cases = [c for c in cases if json.loads(c.read_text(encoding="utf-8")).get("category") == args.only]
    if args.limit:
        cases = cases[: args.limit]
    case_data = [json.loads(c.read_text(encoding="utf-8")) for c in cases]
    golden_dir = Path(args.golden)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    rule_rows = run_side("rules", case_data, golden_dir, None, loose=args.loose)
    llm_rows: list[dict] | None = None
    llm = LLMPlanner(api_key=args.llm_key, model=args.llm_model, base_url=args.llm_base) if args.llm else None
    if llm is not None:
        if not llm.configured:
            print("⚠️  LLM 凭证缺失（AEC_LLM_API_KEY / AEC_LLM_MODEL）——LLM 列跳过")
        else:
            llm_rows = run_side("llm", case_data, golden_dir, llm, loose=args.loose)

    def stat(rows: list[dict]) -> tuple[int, int, int, int]:
        p = sum(1 for r in rows if r["status"] == "passed")
        fb = sum(1 for r in rows if r["fallback"])
        tk = sum(r["tokens"] for r in rows)
        ms = sum(r["ms"] for r in rows)
        return p, len(rows), fb, tk

    rp, rn, _, _ = stat(rule_rows)
    lines = ["# 双规划器对比评测（planner 级，golden 口径）", "",
             f"- 用例: {rn}", "",
             f"| 规划器 | 通过 | 通过率 | 规则回退 | LLM tokens | 总耗时 |",
             "|---|---|---|---|---|---|",
             f"| 规则版（确定性） | {rp} | {rp / rn:.0%} | – | 0 | {sum(r['ms'] for r in rule_rows)}ms |"]
    if llm_rows:
        lp, ln, lfb, ltk = stat(llm_rows)
        lines.append(f"| LLM-first | {lp} | {lp / ln:.0%} | {lfb} | {ltk} | {sum(r['ms'] for r in llm_rows)}ms |")
    lines += ["", "| case | category | 规则版 | LLM 版 |", "|---|---|---|---|"]
    llm_by_id = {r["id"]: r for r in (llm_rows or [])}
    for r in rule_rows:
        mark = lambda s: {"passed": "✅", "failed": "❌", "error": "💥"}.get(s, "·")
        lcell = "–"
        if llm_rows is not None:
            lr = llm_by_id.get(r["id"])
            lcell = f"{mark(lr['status'])}{'(回退)' if lr['fallback'] else ''}" if lr else "–"
        lines.append(f"| {r['id']} | {r['category']} | {mark(r['status'])} | {lcell} |")
    if llm_rows is None:
        lines += ["", "> LLM 列未运行：配 `AEC_LLM_API_KEY` + `AEC_LLM_MODEL`（OpenAI 兼容端点）后加 `--llm` 重跑。"]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {"rules": rule_rows, "llm": llm_rows}
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"报告: {out / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
