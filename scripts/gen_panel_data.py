"""面板数据生成器：汇总评测/运行/桥状态，内联进 DSH 插件的 client.js。

数据快照直接替换 client.js 的 /*__AEC_DATA__*/ 占位行 —— 插件面板（只读展示）
刷新页面即可看到最新数据；host 路由（/aec/api/*）生效后自动升级为实时态。

用法：uv run python scripts/gen_panel_data.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "dsh-plugin" / "aec-copilot-dsh"
CLIENT = PLUGIN / "client.js"
EVAL_LIVE = REPO / "eval" / "results-live"


def bridge_status() -> dict:
    import os

    root = Path(os.environ.get("LOCALAPPDATA", "")) / "RevitCommandBridge" / "2024"
    status = root / "status.json"
    if not status.exists():
        return {"state": "unknown", "document": None}
    try:
        data = json.loads(status.read_text(encoding="utf-8"))
        return {"state": data.get("state", "unknown"), "document": data.get("data", {}).get("document_title")}
    except Exception:
        return {"state": "read-error", "document": None}


def eval_summary() -> dict | None:
    res = EVAL_LIVE / "results.json"
    if not res.exists():
        return None
    rows = json.loads(res.read_text(encoding="utf-8"))["results"]
    merged: dict[str, dict] = {}
    for r in rows:
        merged[r["id"]] = r  # 最近一次结果
    vals = list(merged.values())
    revit = [v for v in vals if v.get("engine") == "revit"]
    return {
        "total": len(vals),
        "passed": sum(1 for v in vals if v["status"] == "passed"),
        "rate": round(sum(1 for v in vals if v["status"] == "passed") / max(len(vals), 1) * 100),
        "revit_total": len(revit),
        "revit_passed": sum(1 for v in revit if v["status"] == "passed"),
    }


def runs_table(limit: int = 15) -> list[dict]:
    rows: list[dict] = []
    for run_json in (EVAL_LIVE / "runs").glob("*/run.json"):
        try:
            r = json.loads(run_json.read_text(encoding="utf-8"))
            rows.append({"run_id": r.get("run_id"), "status": r.get("status"), "engine": r.get("engine"),
                         "elements": len(r.get("elements", [])), "attempts": len(r.get("attempts", [])),
                         "instruction": str(r.get("instruction", ""))[:60],
                         "mtime": run_json.stat().st_mtime})
        except Exception:
            continue
    return sorted(rows, key=lambda x: -x["mtime"])[:limit]


def report_markdown() -> str:
    f = EVAL_LIVE / "report.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def main() -> int:
    snapshot = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "eval": eval_summary(),
        "bridge": bridge_status(),
        "runs": runs_table(),
        "report_md": report_markdown(),
    }
    payload = "window.__AEC_DATA__ = " + json.dumps(snapshot, ensure_ascii=True) + ";"
    text = CLIENT.read_text(encoding="utf-8")
    marker = "/*__AEC_DATA__*/"
    if marker not in text:
        print("client.js 缺少占位标记 /*__AEC_DATA__*/")
        return 1
    updated = re.sub(
        re.escape(marker) + r"[\s\S]*?(?=\n    // host 路由)",
        lambda m: payload + "\n    // host 路由",  # lambda 防止 re 解释 JSON 里的 \n 转义
        text, count=1,
    )
    CLIENT.write_text(updated, encoding="utf-8")
    # 同步 pnpm node_modules 里的插件副本（host 加载路径）
    nm = Path.home() / ".dsh" / "profiles" / "desktop" / "node_modules" / "aec-copilot-dsh"
    if nm.exists():
        (nm / "client.js").write_text(updated, encoding="utf-8")
    print(f"快照已内联：eval={snapshot['eval']}, runs={len(snapshot['runs'])}, bridge={snapshot['bridge']['state']}")
    print("刷新 DSH 页面即可生效（无需重启）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
