"""查中式样板可用门窗族 + 尝试放置门窗到当前文档。"""
import json
import sys

sys.path.insert(0, "src")
from aec_mcp.engines import get_engine

eng = get_engine("revit")
q = eng.send({"operation": "execute_plan", "args": {"steps": [
    {"id": "q", "operation": "query_catalog", "args": {"kind": "families"}}]}, "preview": False}, wait_seconds=120)
d = json.dumps(q.get("data", {}), ensure_ascii=False)
fams = [f for f in json.loads(d.replace('"name":', '"name":')) .get("steps", [{}])[0].get("data", {}).get("items", [])
        if any(k in str(f) for k in ("窗", "门"))]
print("门窗相关族:", json.dumps(fams[:15], ensure_ascii=False))
