"""Deterministic isometric renderer for the simulation backend and web fallback."""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

COLORS = {"wall": "#90a4ae", "column": "#546e7a", "slab": "#b0bec5", "door": "#ef8354", "window": "#4cc9f0", "part": "#80ed99", "assembly": "#80ed99"}
FONT_CANDIDATES = [
    "/usr/local/share/fonts/tabbit/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (["/usr/local/share/fonts/tabbit/NotoSansSC-Bold.ttf"] if bold else []) + FONT_CANDIDATES
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _shade(color: str, factor: float) -> tuple[int, int, int]:
    rgb = tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    return tuple(max(0, min(255, int(v * factor))) for v in rgb)


def _cuboid(x: float, y: float, z: float, w: float, d: float, h: float) -> list[list[list[float]]]:
    p = [[x,y,z],[x+w,y,z],[x+w,y+d,z],[x,y+d,z],[x,y,z+h],[x+w,y,z+h],[x+w,y+d,z+h],[x,y+d,z+h]]
    return [[p[i] for i in face] for face in ([0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7])]


def _element_geometry(e: dict[str, Any]) -> tuple[list[list[list[float]]], list[tuple[list[float], list[float], str]]]:
    """Return solid faces and line features in model coordinates."""
    typ = e.get("type")
    if typ == "wall":
        a, b = e["start"], e["end"]
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy/length*e["thickness"]/2, dx/length*e["thickness"]/2
        # A rotated wall is represented by a four-sided prism, not an AABB.
        z = a[2]
        low = [[a[0]+nx,a[1]+ny,z],[b[0]+nx,b[1]+ny,z],[b[0]-nx,b[1]-ny,z],[a[0]-nx,a[1]-ny,z]]
        high = [[p[0],p[1],z+e["height"]] for p in low]
        return [[low[i],low[(i+1)%4],high[(i+1)%4],high[i]] for i in range(4)] + [high], []
    if typ == "column":
        x,y,z = e["center"]
        return _cuboid(x-e["width"]/2,y-e["depth"]/2,z,e["width"],e["depth"],e["height"]), []
    if typ == "slab":
        boundary, z, h = e["boundary"], e.get("elevation",0), e["thickness"]
        low = [[p[0],p[1],z] for p in boundary]
        high = [[p[0],p[1],z+h] for p in boundary]
        n = len(boundary)
        return [[low[i],low[(i+1)%n],high[(i+1)%n],high[i]] for i in range(n)] + [high], []
    if typ in {"door", "window"}:
        # Position derived from host wall is injected by ``prepare`` before calling.
        host = e.get("_host")
        if host:
            a,b = host["start"],host["end"]
            dx,dy = b[0]-a[0],b[1]-a[1]
            length = math.hypot(dx,dy)
            ux,uy = dx/length,dy/length
            start = [a[0]+ux*e["offset"],a[1]+uy*e["offset"],a[2]+e["bottom"]]
            end = [start[0]+ux*e["width"],start[1]+uy*e["width"],start[2]]
            fake = {"start":start,"end":end,"thickness":host["thickness"]*1.08,"height":e["height"]}
            return _element_geometry({**fake,"type":"wall"})
    if typ == "part":
        x,y,z = e.get("origin",[0,0,0])
        if e.get("shape") == "box":
            w,d,h = e["size"]
            return _cuboid(x,y,z,w,d,h), []
        d,h = e["size"]
        return _cuboid(x,y,z,d,d,h), []
    if typ == "grid":
        return [], [(e["start"],e["end"],"grid")]
    if typ == "polyline":
        pts = e["points"] + ([e["points"][0]] if e.get("closed") else [])
        return [], [(pts[i],pts[i+1],"polyline") for i in range(len(pts)-1)]
    return [], []


def prepare(elements: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    items = list(elements)
    by_id = {e.get("id"):e for e in items}
    result = []
    for e in items:
        copied = dict(e)
        if e.get("type") in {"door","window"}:
            copied["_host"] = by_id.get(e.get("host_id"))
        result.append(copied)
    return result


def render_elements(elements: list[dict[str, Any]], output: str | Path, *, title: str = "AEC Copilot · SIMULATION", width: int = 1400, height: int = 900) -> str:
    """Render geometry to PNG and return the path. No external renderer is needed."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width,height), "#f5f7fa")
    draw = ImageDraw.Draw(image)
    title_font, body_font, small_font = _font(30,True), _font(18), _font(14)
    draw.rectangle((0,0,width,82), fill="#12263a")
    draw.text((36,22), title, font=title_font, fill="white")
    draw.text((width-310,29), "SIMULATION · NOT A CAD SCREENSHOT", font=small_font, fill="#ffd166")
    items = prepare(elements)
    geometries = [_element_geometry(e) for e in items]
    all_points = [p for faces,lines in geometries for face in faces for p in face]
    all_points += [p for _,lines in geometries for a,b,_ in lines for p in (a,b)]
    if not all_points:
        all_points = [[0,0,0],[1000,1000,1000]]
    def raw(p: list[float]) -> tuple[float,float]:
        return ((p[0]-p[1])*math.cos(math.pi/6), (p[0]+p[1])*0.5-p[2])
    projected = [raw(p) for p in all_points]
    minx,maxx = min(p[0] for p in projected),max(p[0] for p in projected)
    miny,maxy = min(p[1] for p in projected),max(p[1] for p in projected)
    view = (55,125,width-330,height-70)
    scale = min((view[2]-view[0])/max(maxx-minx,1),(view[3]-view[1])/max(maxy-miny,1))
    scale = min(scale, 1.5)
    ox = view[0]+(view[2]-view[0]-(maxx-minx)*scale)/2-minx*scale
    oy = view[1]+(view[3]-view[1]-(maxy-miny)*scale)/2-miny*scale
    def project(p: list[float]) -> tuple[float,float]:
        x,y = raw(p)
        return ox+x*scale, oy+y*scale
    # restrained ground grid
    draw.rectangle(view, fill="#edf2f4", outline="#d6dee3")
    features = []
    for e,(faces,lines) in zip(items,geometries):
        color = COLORS.get(e.get("type"),"#90a4ae")
        for a,b,kind in lines:
            features.append((sum(p[2] for p in (a,b))/2,"line",project(a),project(b),color,kind,e))
        for face in faces:
            depth = sum(p[0]+p[1]+p[2]*0.25 for p in face)/len(face)
            features.append((depth,"face",face,color,None,None,e))
    features.sort(key=lambda x:x[0])
    for feature in features:
        if feature[1] == "line":
            _,_,a,b,color,kind,_ = feature
            draw.line((a,b),fill="#90a4ae" if kind=="grid" else "#355070",width=2)
        else:
            _,_,face,color,_,_,e = feature
            points = [project(p) for p in face]
            draw.polygon(points, fill=_shade(color,0.92), outline=_shade(color,0.55))
    counts = Counter(e.get("type") for e in elements)
    panel_x = width-295
    draw.rounded_rectangle((panel_x,125,width-40,height-70),radius=14,fill="white",outline="#d6dee3")
    draw.text((panel_x+22,150),"Model manifest / 构件清单",font=body_font,fill="#12263a")
    y=195
    draw.text((panel_x+22,y),f"Elements: {len(elements)}",font=body_font,fill="#355070"); y+=42
    for typ,count in sorted(counts.items()):
        draw.ellipse((panel_x+24,y+5,panel_x+36,y+17),fill=COLORS.get(typ,"#adb5bd"))
        draw.text((panel_x+48,y),f"{typ:<10} {count}",font=body_font,fill="#415a77"); y+=34
    y+=12
    draw.text((panel_x+22,y),"Units: mm",font=small_font,fill="#6c757d"); y+=28
    draw.text((panel_x+22,y),"Projection: isometric",font=small_font,fill="#6c757d")
    draw.text((55,height-45),"Generated deterministically from the executed model manifest.",font=small_font,fill="#6c757d")
    image.save(output,format="PNG",optimize=True)
    return str(output)
