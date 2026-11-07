"""acad DXF 构建子进程：由 contract._commit_acad 以一次性进程方式调用。

用法：python acad_builder.py spec.json out.dxf
spec.json: {"calls": [{"op": "draw_polyline", "args": {...}}, ...]}（归一化后的 mm 字典点）

与 server 进程隔离的原因：ezdxf 首次导入做系统字体扫描（25s~数分钟不可控），
且警告写 fd 2——在 stdio server 内联导入会污染传输层/阻塞响应。
"""

from __future__ import annotations

import json
import sys


def build(spec_path: str, out_path: str) -> None:
    import ezdxf

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    doc = ezdxf.new("R2018", setup=True)
    msp = doc.modelspace()
    for call in spec["calls"]:
        op, a = call["op"], call["args"]
        if op == "draw_polyline":
            pts = [(float(p["x"]), float(p["y"])) for p in a["points"]]
            layer = str(a.get("layer") or "A-LINE")
            if layer not in doc.layers:
                doc.layers.add(name=layer, color=7)
            msp.add_lwpolyline(pts, close=bool(a.get("closed")), dxfattribs={"layer": layer})
        else:
            raise ValueError(f"acad builder 不支持 {op}")
    doc.saveas(out_path)
    print(out_path)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
