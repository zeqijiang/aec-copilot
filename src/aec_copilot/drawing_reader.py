"""图纸识别：DWG/DXF → 结构化报告，让 Agent「看懂」一张图。

管线：DWG →（AutoCAD COM 转换，可选）→ DXF → ezdxf 解析 →
{图层清单, 实体统计, 文字内容, 标注, 边界尺寸}。

解析走一次性子进程（与 acad_builder 同款隔离，ezdxf 导入的怪癖伤不到调用方）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

_READER = '''"""DWG/DXF → JSON 结构化报告（ezdxf 子进程）。"""
import json, sys
import ezdxf

path = sys.argv[1]
doc = ezdxf.readfile(path)
msp = doc.modelspace()

layers = [{"name": l.dxf.name, "color": l.color} for l in doc.layers]
stats = {}
texts = []
dims = []
extmin, extmax = None, None
try:
    ext = msp.bounding_box()
    extmin = [round(v, 1) for v in (ext.extmin.x, ext.extmin.y)]
    extmax = [round(v, 1) for v in (ext.extmax.x, ext.extmax.y)]
except Exception:
    pass

for e in msp:
    t = e.dxftype()
    stats[t] = stats.get(t, 0) + 1
    if t in ("TEXT", "MTEXT"):
        texts.append(e.text.strip()[:120])
    elif t in ("DIMENSION",):
        try:
            dims.append(e.dxf.text or "<auto>")
        except Exception:
            dims.append("<dim>")

print(json.dumps({
    "file": path,
    "dxf_version": doc.dxfversion,
    "extent": {"min": extmin, "max": extmax},
    "layers": layers[:40],
    "entity_stats": stats,
    "texts": texts[:80],
    "dimensions": dims[:40],
}, ensure_ascii=False))
'''


def dwg_to_dxf(dwg_path: str, *, timeout: int = 180) -> str:
    """DWG → DXF（需本机 AutoCAD 运行；COM 转换）。返回 DXF 路径。"""
    import os

    try:
        import win32com.client  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError(f"DWG 转换需要 pywin32 + AutoCAD：{e}") from e
    dwg = Path(dwg_path).resolve()
    if not dwg.exists():
        raise FileNotFoundError(dwg)
    out = dwg.with_suffix(".dxf")
    acad = win32com.client.GetActiveObject("AutoCAD.Application")
    doc = acad.Documents.Open(str(dwg), True)  # 只读打开
    try:
        doc.SaveAs(str(out), 13)  # ac2018_dxf = 13（兼容 2018 DXF）
    finally:
        doc.Close(False)
    if not out.exists():
        raise RuntimeError("AutoCAD 未产出 DXF")
    _ = os  # noqa
    return str(out)


def read_drawing(path: str, *, timeout: int = 120) -> dict:
    """DXF/DWG → 结构化报告 dict。DWG 自动尝试 COM 转换。"""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(path)
    if src.suffix.lower() == ".dwg":
        path = dwg_to_dxf(str(src))
    with tempfile.NamedTemporaryFile("w", suffix="_reader.py", delete=False, encoding="utf-8") as f:
        f.write(_READER)
        reader = f.name
    try:
        proc = subprocess.run([sys.executable, reader, str(path)],
                              capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
    finally:
        Path(reader).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"图纸解析失败: {proc.stderr[-300:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])
