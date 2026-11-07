"""从 run 目录 + results.json 重建全量真机评测报告（断点续跑后用）。"""

from __future__ import annotations

import glob
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "eval" / "results-live"


def main() -> int:
    # 以 results.json 为准（断点续跑会重复出现同一用例，取最后一次结果）
    res_path = OUT / "results.json"
    merged: dict[str, dict] = {}
    if res_path.exists():
        for r in json.loads(res_path.read_text(encoding="utf-8"))["results"]:
            merged[r["id"]] = r  # 后写覆盖先写 = 最近一次结果
    rows = [
        {
            "id": k,
            "instruction": (v.get("instruction") if v.get("instruction") and v["instruction"] != k else k),
            "status": v["status"],
            "attempts": v.get("attempts", 0),
            "engine": v["engine"],
        }
        for k, v in merged.items()
    ]
    rows.sort(key=lambda x: x["id"])

    n_pass = sum(1 for x in rows if x["status"] == "passed")
    lines = [
        "# 真机评测报告（live backend, 2026-11-07）",
        "",
        f"- 总用例: {len(rows)}  通过: {n_pass}  通过率: {n_pass / max(len(rows), 1):.0%}",
        "- 说明：49_part / 50_assembly 为 SOLIDWORKS 引擎，本机 SW 未启动，按设计快速失败（E_ENGINE_DOWN）；"
        "50_assembly 另需零件 ID 语法（规划器约束）。",
        "",
        "| 用例 | engine | 状态 | 尝试 | 指令 |",
        "|---|---|---|---|---|",
    ]
    for x in rows:
        mark = {"passed": "✅", "failed": "❌"}.get(x["status"], "💥")
        instr = str(x["instruction"])[:44].replace("|", "丨")
        lines.append(f"| {x['id'][:22]} | {x['engine']} | {mark} {x['status']} | {x['attempts']} | {instr} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"通过 {n_pass}/{len(rows)}")
    for f in (x for x in rows if x["status"] != "passed"):
        print("未过:", f["id"][:22], f["status"], str(f["instruction"])[:36])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
