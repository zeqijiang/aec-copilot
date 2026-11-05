from __future__ import annotations

from PIL import Image

from aec_copilot.compiler import compile_plan
from aec_copilot.engines.sim import SimulationEngine
from aec_copilot.planner import Planner
from aec_copilot.render import render_elements


def test_rendered_geometry_stays_out_of_header_and_inside_view(tmp_path):
    plan = Planner().parse("生成一个6m×4m的房间，层高3.6m，包含楼板")
    engine = SimulationEngine("revit")
    with engine.transaction():
        for call in compile_plan(plan):
            engine.call(call.name, call.arguments)
    output = tmp_path / "room.png"
    render_elements(engine.snapshot(), output)
    image = Image.open(output).convert("RGB")
    # These header pixels contain neither title nor warning text. The historical
    # max-y/min-y offset bug painted a wall here, above the model viewport.
    for x in (600, 700, 800, 900):
        for y in (20, 45, 70):
            assert image.getpixel((x, y)) == (18, 38, 58)
    # The room must have visible geometry in the designated viewport center.
    viewport_colors = {image.getpixel((x, y)) for x in range(55, 1070, 5) for y in range(125, 830, 5)}
    assert (132, 150, 160) in viewport_colors  # shaded wall fill #90a4ae * 0.92


def test_empty_model_render_is_valid(tmp_path):
    output = tmp_path / "empty.png"
    render_elements([], output, width=800, height=600)
    image = Image.open(output)
    assert image.size == (800, 600)
    assert output.stat().st_size > 1000
