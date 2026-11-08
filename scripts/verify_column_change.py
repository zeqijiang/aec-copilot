"""设计变更→造价联动演示：9 根柱网落模型 → 造价自动含矩形柱项。"""
import json
import sys

sys.path.insert(0, "src")
from aec_copilot.mcp_full import call_tool
from aec_mcp.engines import get_engine

eng = get_engine("revit")
steps = []
i = 0
for x in (0, 6000, 12000):
    for y in (0, 4000, 8000):
        i += 1
        steps.append({"id": f"col_{i}", "operation": "create_direct_shape", "args": {
            "name": f"柱 500x500_{i}", "category": "OST_GenericModel",
            "geometry": [{"kind": "box",
                          "min": {"x": x - 250, "y": y - 250, "z": 0},
                          "max": {"x": x + 250, "y": y + 250, "z": 6600}}]}})
r = eng.send({"operation": "execute_plan", "args": {"steps": steps}, "preview": False}, wait_seconds=240)
ok = r.get("data", {}).get("steps", [])
done = sum(1 for s in ok if s.get("state") == "completed")
print(f"[1/2] 柱网落模型: {done}/{len(steps)} 完成", flush=True)

d = json.loads(call_tool("aec_cost_estimate", {"gfa": 192}))
print(f"[2/2] 造价更新: 清单项 {d.get('清单项数')} | 汇总 {json.dumps(d.get('汇总'), ensure_ascii=False)}", flush=True)
