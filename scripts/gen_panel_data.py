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


def cost_snapshot() -> dict | None:
    f = REPO / "runs" / "cost" / "cost-report.json"
    if not f.exists():
        return None
    try:
        report = json.loads(f.read_text(encoding="utf-8"))
        return {"汇总": report.get("汇总"), "费用结构": report.get("费用结构"),
                "概况": report.get("项目概况"), "清单项数": len(report.get("清单明细", [])),
                "excel": str(REPO / "runs" / "cost" / "cost-report.xlsx"),
                "markdown": str(REPO / "runs" / "cost" / "cost-report.md")}
    except Exception:
        return None


def report_markdown() -> str:
    f = EVAL_LIVE / "report.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def main() -> int:
    snapshot = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "eval": eval_summary(),
        "bridge": bridge_status(),
        "runs": runs_table(),
        "cost": cost_snapshot(),
        "report_md": report_markdown(),
    }
    payload = "window.__AEC_DATA__ = " + json.dumps(snapshot, ensure_ascii=True) + ";"
    text = CLIENT.read_text(encoding="utf-8")
    # 幂等替换：命中占位标记（首跑）或已有数据行（重跑），直到 // host 路由 注释为止
    pattern = r"(?:/\*__AEC_DATA__\*/|window\.__AEC_DATA__ = .*?;)\n?(?=\s*// host 路由)"
    updated, n = re.subn(pattern, lambda m: payload, text, count=1, flags=re.S)
    if n == 0:
        print("client.js 缺少占位标记 /*__AEC_DATA__*/")
        return 1
    CLIENT.write_text(updated, encoding="utf-8")
    # 同步 pnpm node_modules 里的插件副本（低完整性令牌可能写不了 .dsh —— 失败仅警告）
    nm = Path.home() / ".dsh" / "profiles" / "desktop" / "node_modules" / "aec-copilot-dsh"
    if nm.exists():
        try:
            (nm / "client.js").write_text(updated, encoding="utf-8")
        except PermissionError:
            print("提示：node_modules 副本同步被拒（低完整性令牌），请手动复制 client.js 到")
            print(f"  {nm}")
    print(f"快照已内联：eval={snapshot['eval']}, runs={len(snapshot['runs'])}, bridge={snapshot['bridge']['state']}")
    print("刷新 DSH 页面即可生效（无需重启）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
