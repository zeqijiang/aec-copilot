"""IFC 数据互通演示：中文指令 → Revit 真模型 → IFC 标准格式落盘。

直击行业槽点「二次建模」（Revit 模型算不了量，广联达 GTJ 里再建一遍）——
先把模型数据以 IFC（ISO 16739）标准格式交出去，下游造价/算量/施工软件才
有对接的地基。

用法（仓库根目录）：
    $env:REPORTLAB_CJK_REGULAR_FONT = "C:\\Windows\\Fonts\\simhei.ttf"
    $env:AEC_REVIT_FRESH_DOC = "1"
    uv run python scripts/export_ifc.py "生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm"

流程：新建文档副本 → Runner(mcp live) 建模 → 桥 export(format=ifc) →
校验 ISO-10303-21 文件头 → 输出产物清单。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from aec_copilot.engines.mcp import MCPEngine  # noqa: E402
from aec_copilot.runner import Runner  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="中文建模 → IFC 导出演示")
    ap.add_argument("instruction", nargs="?", default="生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm")
    ap.add_argument("--out", default=str(REPO / "out" / f"ifc-demo-{time.strftime('%Y%m%d_%H%M%S')}"))
    ap.add_argument("--config", default=str(REPO / "config" / "mcp.live.json"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 1) 建模（每例新文档副本，由 AEC_REVIT_FRESH_DOC 控制）
    engine = MCPEngine.from_config("revit", args.config)
    runner = Runner(engine=engine, output_root=str(out / "runs"), max_attempts=2)
    t0 = time.perf_counter()
    result = runner.run(args.instruction, engine="revit")
    build_ms = int((time.perf_counter() - t0) * 1000)
    if result.status != "passed":
        print(json.dumps({"status": result.status, "output_dir": result.output_dir}, ensure_ascii=False))
        return 1
    print(f"[1/2] 建模通过：{len(result.elements)} 构件，{build_ms}ms")

    # 2) IFC 导出（桥 export 单独成计划）
    ifc_path = out / "model.ifc"
    res = engine.client.call_tool("revit_execute_plan", {
        "steps": [{"id": "export_ifc", "operation": "export", "args": {"format": "ifc", "output_path": str(out / "ifc-export")}}],
        "preview": False,
    })
    content = next((c.get("text", "") for c in (res.get("content") or []) if c.get("type") == "text"), "{}")
    payload = json.loads(content)
    if payload.get("ok") is False or payload.get("isError"):
        print("IFC 导出失败:", content[:300])
        return 1

    # 3) 校验 IFC 文件（ISO-10303-21 头 + 体量）
    candidates = sorted(out.glob("ifc-export*/**/*.ifc")) + sorted(out.glob("ifc-export*/**/*.ifc")) + sorted(out.glob("**/*.ifc"))
    ifc_file = next((p for p in candidates if p.stat().st_size > 1000), None)
    if ifc_file is None:
        print("未找到 IFC 文件，检查:", out)
        return 1
    head = ifc_file.read_text(encoding="utf-8", errors="ignore")[:200]
    ok_header = "ISO-10303-21" in head
    schema = next((line for line in head.splitlines() if "FILE_SCHEMA" in line), "") or "(schema 在数据段)"

    print(f"[2/2] IFC 落盘：{ifc_file.name}  {ifc_file.stat().st_size / 1024:.0f} KB  头部校验 {'✅' if ok_header else '❌'}")
    print("产物：")
    for f in sorted(out.rglob("*")):
        if f.is_file() and f.suffix in {".ifc", ".rvt", ".png", ".pdf", ".xlsx"}:
            print(f"  - {f.relative_to(out)}  {f.stat().st_size / 1024:.0f} KB")
    print(f"schema 行: {schema[:120]}")
    return 0 if ok_header else 1


if __name__ == "__main__":
    raise SystemExit(main())
