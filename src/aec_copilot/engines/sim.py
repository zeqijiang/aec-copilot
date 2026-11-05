"""Deterministic in-memory engine used for development, evaluation, and UI demos.

It is NOT a Revit/AutoCAD/SolidWorks implementation. It deliberately models the
same tool contract so real adapters can be substituted without changing the DSL.
"""
from __future__ import annotations

import copy
import math
import threading
from typing import Any

from ..errors import AECError, require
from ..units import distance, mm, point
from .base import Engine, Transaction


class _SimTransaction(Transaction):
    def __init__(self, engine: "SimulationEngine") -> None:
        self.engine = engine
        self.before: list[dict[str, Any]] = []
        self.finished = False

    def __enter__(self) -> "_SimTransaction":
        self.engine._lock.acquire()
        self.before = copy.deepcopy(self.engine._elements)
        return self

    def commit(self) -> None:
        if not self.finished:
            self.finished = True
            self.engine._lock.release()

    def rollback(self) -> None:
        if not self.finished:
            self.engine._elements = self.before
            self.finished = True
            self.engine._lock.release()


class SimulationEngine(Engine):
    backend = "simulation"

    def __init__(self, name: str = "revit") -> None:
        if name not in {"revit", "acad", "sw"}:
            raise ValueError(name)
        self.name = name
        self._elements: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def transaction(self) -> Transaction:
        return _SimTransaction(self)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._elements)

    def reset(self) -> None:
        with self._lock:
            self._elements = []

    def load(self, elements: list[dict[str, Any]]) -> None:
        with self._lock:
            self._elements = copy.deepcopy(elements)

    def _get(self, element_id: str, expected_type: str | None = None) -> dict[str, Any]:
        for element in self._elements:
            if element["id"] == element_id:
                if expected_type and element["type"] != expected_type:
                    raise AECError("E_CONSTRAINT", f"{element_id} is not a {expected_type}", actual=element["type"])
                return element
        raise AECError("E_NOT_FOUND", f"Element not found: {element_id}", element_id=element_id)

    def _add(self, element: dict[str, Any]) -> dict[str, Any]:
        require(all(e["id"] != element["id"] for e in self._elements), "E_CONSTRAINT", "Duplicate element ID", element_id=element["id"])
        element.update({"engine": self.name})
        self._elements.append(element)
        return {"ok": True, "element": copy.deepcopy(element)}

    @staticmethod
    def _validate_wall(args: dict[str, Any]) -> tuple[list[float], list[float], float, float]:
        start, end = point(args.get("start"), field="start"), point(args.get("end"), field="end")
        height = mm(args.get("height", 3600), field="height", positive=True)
        thickness = mm(args.get("thickness", 200), field="thickness", positive=True)
        require(distance(start, end) > 0, "E_GEOM", "Wall start and end must differ")
        require(thickness < distance(start, end), "E_GEOM", "Wall thickness must be smaller than wall length")
        return start, end, height, thickness

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        prefix = f"{self.name}_"
        require(tool_name.startswith(prefix), "E_CONSTRAINT", f"Tool {tool_name} does not belong to {self.name}")
        op = tool_name[len(prefix):]
        args = copy.deepcopy(arguments)
        element_id = args.get("id")
        require(isinstance(element_id, str) and bool(element_id), "E_CONSTRAINT", "Every operation needs a string id")
        with self._lock:
            if op == "create_level":
                elevation = mm(args.get("elevation", 0), field="elevation")
                return self._add({**args, "id": element_id, "type": "level", "elevation": elevation})
            if op == "create_grid":
                start, end = point(args.get("start"), field="start"), point(args.get("end"), field="end")
                require(distance(start, end) > 0, "E_GEOM", "Grid start and end must differ")
                return self._add({**args, "id": element_id, "type": "grid", "start": start, "end": end})
            if op == "create_wall":
                start, end, height, thickness = self._validate_wall(args)
                return self._add({**args, "id": element_id, "type": "wall", "start": start, "end": end, "height": height, "thickness": thickness})
            if op == "create_column":
                center = point(args.get("center"), field="center")
                width = mm(args.get("width", 400), field="width", positive=True)
                depth = mm(args.get("depth", width), field="depth", positive=True)
                height = mm(args.get("height", 3600), field="height", positive=True)
                return self._add({**args, "id": element_id, "type": "column", "center": center, "width": width, "depth": depth, "height": height})
            if op == "create_slab":
                raw = args.get("boundary")
                require(isinstance(raw, list) and len(raw) >= 3, "E_GEOM", "Slab boundary needs at least three points")
                boundary = [point(p, field="boundary") for p in raw]
                area = abs(sum(boundary[i][0] * boundary[(i+1) % len(boundary)][1] - boundary[(i+1) % len(boundary)][0] * boundary[i][1] for i in range(len(boundary)))) / 2
                require(area > 0, "E_GEOM", "Slab boundary area must be non-zero")
                thickness = mm(args.get("thickness", 120), field="thickness", positive=True)
                elevation = mm(args.get("elevation", 0), field="elevation")
                return self._add({**args, "id": element_id, "type": "slab", "boundary": boundary, "thickness": thickness, "elevation": elevation})
            if op in {"create_door", "create_window"}:
                host = self._get(args.get("host_id", ""), "wall")
                width = mm(args.get("width", 900 if op == "create_door" else 1500), field="width", positive=True)
                height = mm(args.get("height", 2100 if op == "create_door" else 1500), field="height", positive=True)
                bottom = mm(args.get("bottom", 0 if op == "create_door" else 900), field="bottom")
                wall_length = distance(host["start"], host["end"])
                require(width <= wall_length, "E_GEOM", "Opening is wider than its host wall", width=width, wall_length=wall_length)
                require(bottom >= 0 and bottom + height <= host["height"], "E_GEOM", "Opening exceeds host wall height")
                offset = mm(args.get("offset", (wall_length - width) / 2), field="offset")
                require(offset >= 0 and offset + width <= wall_length, "E_GEOM", "Opening exceeds host wall length")
                return self._add({**args, "id": element_id, "type": "door" if op == "create_door" else "window", "host_id": host["id"], "width": width, "height": height, "bottom": bottom, "offset": offset})
            if op == "draw_polyline":
                raw = args.get("points")
                require(isinstance(raw, list) and len(raw) >= 2, "E_GEOM", "Polyline needs at least two points")
                points = [point(p, field="points") for p in raw]
                require(any(distance(points[i], points[i+1]) > 0 for i in range(len(points)-1)), "E_GEOM", "Polyline has zero length")
                return self._add({**args, "id": element_id, "type": "polyline", "points": points, "closed": bool(args.get("closed", False))})
            if op == "create_part":
                shape = args.get("shape", "box")
                require(shape in {"box", "cylinder"}, "E_CONSTRAINT", "Part shape must be box or cylinder")
                if shape == "box":
                    size = [mm(args.get(k, 100), field=k, positive=True) for k in ("width", "depth", "height")]
                else:
                    size = [mm(args.get("diameter", 100), field="diameter", positive=True), mm(args.get("height", 100), field="height", positive=True)]
                return self._add({**args, "id": element_id, "type": "part", "shape": shape, "size": size, "origin": point(args.get("origin", [0, 0, 0]), field="origin")})
            if op == "create_assembly":
                parts = args.get("parts", [])
                require(isinstance(parts, list) and len(parts) > 0, "E_CONSTRAINT", "Assembly requires part IDs")
                for part_id in parts:
                    self._get(part_id, "part")
                return self._add({**args, "id": element_id, "type": "assembly", "parts": parts})
            raise AECError("E_NOT_FOUND", f"Unknown simulation tool: {tool_name}")
