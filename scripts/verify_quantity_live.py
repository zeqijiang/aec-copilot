"""端到端验证：新文档 → 两层楼建模 → aec_quantity 真模型工程量指标。"""
import json

import sys
sys.path.insert(0, "src")
from aec_copilot.engines.registry import create_engine
from aec_copilot.mcp_full import call_tool
from aec_copilot.runner import Runner
from aec_mcp.engines import get_engine

eng = get_engine("revit")
eng.send({"operation": "new_project",
          "args": {"save_path": r"D:\admin\Documents\deepseek-harness\default-workspace\aec-copilot-merged\out\qty-demo.rvt",
                   "overwrite_file": True}}, wait_seconds=240)
print("[1/3] 新文档 OK", flush=True)

runner = Runner(engine=create_engine("revit", "direct"), output_root="runs/qty-demo", max_attempts=2)
r = runner.run("生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm", engine="revit")
print(f"[2/3] 建模: {r.status} {len(r.elements)}构件", flush=True)
assert r.status == "passed", [d.message for a in r.attempts for d in a.verification.differences]

d = json.loads(call_tool("aec_quantity", {}))
print(f"[3/3] 工程量指标（真模型，{d.get('walls_count')} 面墙逐个溯源）:", flush=True)
print("  汇总:", json.dumps(d.get("totals"), ensure_ascii=False), flush=True)
print("  单方指标:", json.dumps(d.get("indicators"), ensure_ascii=False), flush=True)
print("  样例墙:", json.dumps((d.get("walls") or [{}])[0], ensure_ascii=False), flush=True)
