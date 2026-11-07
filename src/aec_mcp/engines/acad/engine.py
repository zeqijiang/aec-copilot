"""acad 引擎：AutoCAD COM（迁移自 CAD-MCP/cad_controller.py）+ ezdxf 离线兜底。

- AutoCAD 2026 在运行 → AcadComEngine（真窗口、真 DWG）
- 否则 AcadOfflineEngine（ezdxf 写真实 DXF；可 matplotlib 导出 PNG）
两者对外行为一致：execute(steps) / save / export，均以文件为事务边界。
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from ..base import BaseEngine
from ...errors import AecError, ErrorCode

VALID_LINEWEIGHTS = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211]


def _pt(p: dict[str, float]) -> tuple[float, float, float]:
    return (float(p["x"]), float(p["y"]), float(p.get("z", 0.0)))


class AcadComEngine(BaseEngine):
    """AutoCAD COM 引擎（迁移自 C:\\Users\\admin\\CAD-MCP\\src\\cad_controller.py）。"""

    name = "acad"
    capabilities = ("create_wall", "create_grid", "create_model_curve", "create_column", "create_direct_shape", "create_text", "save_document")

    def __init__(self) -> None:
        self.app = None
        self.doc = None

    def health(self) -> dict[str, Any]:
        try:
            import win32com.client  # noqa: PLC0415

            self.app = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "state": "not_running", "message": f"AutoCAD 未运行: {e}", "hint": "启动 AutoCAD 2026，或用 --offline 走 ezdxf 离线引擎"}
        try:
            self.doc = self.app.ActiveDocument if self.app.Documents.Count else self.app.Documents.Add()
            return {"ok": True, "state": "running", "document": self.doc.Name}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "state": "no_document", "message": str(e)}

    def _variant(self, p: tuple[float, float, float]):
        import win32com.client
        import pythoncom

        return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, list(p))

    def _ensure_layer(self, layer: str) -> None:
        if not layer:
            return
        for i in range(self.doc.Layers.Count):
            if self.doc.Layers.Item(i).Name == layer:
                return
        self.doc.Layers.Add(layer)

    def _add(self, obj, layer: str):
        if layer:
            self._ensure_layer(layer)
            obj.Layer = layer
        return obj

    def execute(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        self.ensure_up()
        created: list[str] = []
        try:
            for s in steps:
                op = s["op"]
                if op == "wall_footprint":
                    x1, y1, _ = _pt(s["start"]); x2, y2, _ = _pt(s["end"])
                    t = float(s["thickness"]) / 2.0
                    dx, dy = x2 - x1, y2 - y1
                    L = math.hypot(dx, dy) or 1.0
                    nx, ny = -dy / L * t, dx / L * t
                    pts = [(x1 + nx, y1 + ny, 0), (x2 + nx, y2 + ny, 0), (x2 - nx, y2 - ny, 0), (x1 - nx, y1 - ny, 0), (x1 + nx, y1 + ny, 0)]
                    arr = self._variant([c for p in pts for c in p])
                    pl = self.doc.ModelSpace.AddPolyline(arr)
                    pl.Closed = True
                    self._add(pl, s.get("layer", "A-WALL"))
                    created.append("wall_footprint")
                elif op == "line":
                    a = self._variant(_pt(s["start"])); b = self._variant(_pt(s["end"]))
                    line = self.doc.ModelSpace.AddLine(a, b)
                    self._add(line, s.get("layer"))
                    created.append("line")
                elif op == "rect":
                    if "center" in s:
                        w = float(s["width"]) / 2; h = float(s["height"]) / 2
                        cx, cy, _ = _pt(s["center"])
                        mn = (cx - w, cy - h, 0); mx = (cx + w, cy + h, 0)
                    else:
                        mn = _pt(s["min"]); mx = _pt(s["max"])
                    pts = [(mn[0], mn[1], 0), (mx[0], mn[1], 0), (mx[0], mx[1], 0), (mn[0], mx[1], 0), (mn[0], mn[1], 0)]
                    arr = self._variant([c for p in pts for c in p])
                    pl = self.doc.ModelSpace.AddPolyline(arr)
                    pl.Closed = True
                    self._add(pl, s.get("layer"))
                    created.append("rect")
                elif op == "text":
                    pos = self._variant(_pt(s["point"]))
                    txt = self.doc.ModelSpace.AddText(str(s["text"]), pos, float(s.get("height", 2.5)))
                    self._add(txt, s.get("layer"))
                    created.append("text")
                elif op == "save":
                    path = s.get("path")
                    if path:
                        Path(path).parent.mkdir(parents=True, exist_ok=True)
                        self.doc.SaveAs(str(path))
                        created.append(f"saved:{path}")
                else:
                    raise AecError(ErrorCode.E_PLAN_INVALID, f"acad COM 不支持 op={op!r}")
            self.doc.Regen(1)
            return {"ok": True, "engine": self.name, "created": created, "document": self.doc.Name}
        except AecError:
            raise
        except Exception as e:  # noqa: BLE001 - COM 错误统一收口；已绘实体留在 AutoCAD 撤销栈（一次 U 撤回）
            raise AecError.wrap(e, ErrorCode.E_INTERNAL, f"AutoCAD COM 执行失败: {e}")


class AcadOfflineEngine(BaseEngine):
    """ezdxf 离线引擎：写真实 DXF；matplotlib 在场时可导出 PNG。文件即事务边界。"""

    name = "acad-offline"
    capabilities = AcadComEngine.capabilities + ("export_image",)

    def __init__(self, output_dir: str | Path = "out") -> None:
        self.output_dir = Path(output_dir)
        self.doc = None
        self._msp = None

    def health(self) -> dict[str, Any]:
        try:
            import ezdxf  # noqa: PLC0415,F401

            return {"ok": True, "state": "offline", "message": "ezdxf 离线模式可用（输出真实 DXF）"}
        except ImportError as e:
            return {"ok": False, "state": "missing_dep", "message": f"缺少 ezdxf: {e}", "hint": "uv sync 安装 dev 依赖"}

    # ---- 步骤构建（内存）----
    def execute(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        import ezdxf

        self.doc = ezdxf.new("R2018", setup=True)
        self._msp = self.doc.modelspace()
        created: list[str] = []
        for s in steps:
            op = s["op"]
            layer = s.get("layer") or "A-WALL"
            if layer not in self.doc.layers:
                self.doc.layers.add(name=layer, color=7)
            if op == "wall_footprint":
                x1, y1, _ = _pt(s["start"]); x2, y2, _ = _pt(s["end"])
                t = float(s["thickness"]) / 2.0
                dx, dy = x2 - x1, y2 - y1
                L = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / L * t, dx / L * t
                pts = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
                self._msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
                created.append("wall_footprint")
            elif op == "line":
                self._msp.add_line(_pt(s["start"])[:2], _pt(s["end"])[:2], dxfattribs={"layer": layer})
                created.append("line")
            elif op == "rect":
                if "center" in s:
                    w = float(s["width"]) / 2; h = float(s["height"]) / 2
                    cx, cy, _ = _pt(s["center"])
                    mn = (cx - w, cy - h); mx = (cx + w, cy + h)
                else:
                    mn = _pt(s["min"])[:2]; mx = _pt(s["max"])[:2]
                self._msp.add_lwpolyline([mn, (mx[0], mn[1]), mx, (mn[0], mx[1])], close=True, dxfattribs={"layer": layer})
                created.append("rect")
            elif op == "text":
                self._msp.add_text(str(s["text"]), dxfattribs={"layer": layer, "height": float(s.get("height", 2.5))}).set_placement(_pt(s["point"])[:2])
                created.append("text")
            elif op == "save":
                path = Path(s.get("path") or (self.output_dir / f"acad_{time.strftime('%H%M%S')}.dxf"))
                path.parent.mkdir(parents=True, exist_ok=True)
                self.doc.saveas(path)
                created.append(f"saved:{path}")
            else:
                raise AecError(ErrorCode.E_PLAN_INVALID, f"acad 离线引擎不支持 op={op!r}")
        return {"ok": True, "engine": self.name, "created": created, "dxf_preview": True}

    def export_png(self, dxf_path: str | Path, png_path: str | Path, dpi: int = 150) -> Path:
        """DXF → PNG（matplotlib 后端）。P2 视觉闭环的喂图入口。"""
        try:
            import ezdxf
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib.pyplot as plt
        except ImportError as e:
            raise AecError(ErrorCode.E_INTERNAL, "导出 PNG 需要 ezdxf + matplotlib（uv sync dev 组）", {"cause": str(e)})
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp, finalize=True)
        png = Path(png_path)
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=dpi)
        plt.close(fig)
        return png
