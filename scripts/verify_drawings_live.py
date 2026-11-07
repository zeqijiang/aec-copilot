"""真机验证：建模 + 一键出图（revit_drawings full_set）→ 产物清单。"""
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, "src")
from aec_copilot.drawings import drawings_tool
from aec_copilot.engines.registry import create_engine
from aec_copilot.runner import Runner
from aec_mcp.engines import get_engine

out = "out/drawings-demo"
model_engine = create_engine("revit", "direct")
runner = Runner(engine=model_engine, output_root=out + "/runs", max_attempts=2)

t0 = time.time()
r = runner.run("生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm", engine="revit")
print(f"[1/3] 建模: {r.status} {len(r.elements)}构件 {int((time.time()-t0)*1000)}ms", flush=True)
assert r.status == "passed", [d.message for a in r.attempts for d in a.verification.differences]

t1 = time.time()
bridge = get_engine("revit")  # 桥级原语执行出图工作流（与 mcp_full 生产路径一致）
d = drawings_tool({"workflow": "full_set", "levels": ["F1", "F2"], "export_formats": ["png"], "output_dir": out},
                  execute=lambda steps, preview: bridge.execute(steps, preview=preview))
print(f"[2/3] 出图: {d['main_steps']}步主计划 + {d['exports']}导出 {int((time.time()-t1)*1000)}ms", flush=True)

arts = sorted(str(p.relative_to(out)) for p in Path(out).rglob("*")
              if p.is_file() and p.suffix in (".png", ".rvt"))
print("[3/3] 产物:", json.dumps(arts, ensure_ascii=False, indent=1), flush=True)
