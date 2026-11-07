"""SolidWorks 引擎：COM 自动化（收编 Desktop\\mcp\\Solidworks-MCP 的骨架）。

注意：SolidWorks COM API 长度单位是米；本引擎对外仍统一 mm（编译层已换算）。
P0 提供 part + 草图 + 拉伸的最小闭环；装配/钣金等 P3+ 再补。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ..base import BaseEngine
from ...errors import AecError, ErrorCode


class SwEngine(BaseEngine):
    name = "sw"
    capabilities = ("create_model_curve", "create_direct_shape", "save_document")

    def __init__(self) -> None:
        self.app = None
        self.doc = None

    def health(self) -> dict[str, Any]:
        # 进程预检：不在后台悄悄拉起 SolidWorks（启动数分钟且可能有授权对话框）
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe"], capture_output=True, text=True, timeout=15)
            if "SLDWORKS.EXE" not in (out.stdout or "").upper():
                return {"ok": False, "state": "not_running", "message": "SOLIDWORKS 未运行", "hint": "先启动 SOLIDWORKS 2026 再重试"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "state": "probe_error", "message": f"进程预检失败: {e}"}
        try:
            import win32com.client  # noqa: PLC0415
        except ImportError as e:
            return {"ok": False, "state": "missing_dep", "message": f"缺少 pywin32: {e}"}
        try:
            self.app = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            try:
                self.app = win32com.client.Dispatch("SldWorks.Application")
                self.app.Visible = True
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "state": "not_running", "message": f"SOLIDWORKS 未运行: {e}", "hint": "启动 SOLIDWORKS 2026 后重试"}
        try:
            self.doc = self.app.ActiveDoc
            state = "running" if self.doc else "no_document"
            if not self.doc:
                self.doc = self.app.NewPart()
                state = "running"
            return {"ok": True, "state": state}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "state": "com_error", "message": str(e)}

    def execute(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        self.ensure_up()
        created: list[str] = []
        for s in steps:
            op = s["op"]
            if op == "sketch_line":
                doc = self.doc
                doc.SketchManager.InsertSketch(True)
                doc.SketchManager.AddToDB = True
                doc.SketchManager.CreateLine(
                    float(s["start_m"][0]), float(s["start_m"][1]), 0.0,
                    float(s["end_m"][0]), float(s["end_m"][1]), 0.0,
                )
                doc.SketchManager.AddToDB = False
                created.append("sketch_line")
            elif op == "extrude_box":
                x1, y1, z1 = s["min_m"]; x2, y2, z2 = s["max_m"]
                doc = self.doc
                doc.SketchManager.InsertSketch(True)
                doc.SketchManager.AddToDB = True
                corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
                for (ax, ay), (bx, by) in zip(corners, corners[1:]):
                    doc.SketchManager.CreateLine(ax, ay, z1, bx, by, z1)
                doc.SketchManager.AddToDB = False
                doc.SketchManager.InsertSketch(True)
                feat = doc.FeatureManager.FeatureExtrusion2(
                    True, False, False, 0, 0, abs(z2 - z1), 0,
                    False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False,
                )
                if not feat:
                    raise AecError(ErrorCode.E_GEOM, "FeatureExtrusion2 失败（SW 2025+ 需 23 参签名，见 Solidworks-MCP v4 修复）")
                created.append("extrude_box")
            elif op == "save":
                path = s.get("path")
                if path:
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
                    errors = 0
                    ok = bool(self.doc.Extension.SaveAs(str(path), 0, 1, None, errors, 0))
                    if not ok:
                        raise AecError(ErrorCode.E_INTERNAL, f"SW 保存失败: {path}")
                    created.append(f"saved:{path}")
            else:
                raise AecError(ErrorCode.E_PLAN_INVALID, f"sw 引擎不支持 op={op!r}")
        return {"ok": True, "engine": self.name, "created": created}
