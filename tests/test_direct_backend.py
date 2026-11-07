"""DirectEngine（进程内 live 后端）离线真跑：acad 多段线 → 真实 DXF。"""

from __future__ import annotations

import json
from pathlib import Path

from aec_copilot.engines.registry import create_engine
from aec_copilot.runner import Runner

REPO = Path(__file__).resolve().parents[1]


def test_direct_acad_polyline_run(tmp_path: Path) -> None:
    engine = create_engine("acad", "direct")
    assert engine.backend == "direct"
    runner = Runner(engine=engine, output_root=str(tmp_path), max_attempts=2)
    result = runner.run("在AutoCAD中绘制6000mm×4000mm的闭合矩形多段线", engine="acad")
    assert result.status == "passed", [d.message for a in result.attempts for d in a.verification.differences]
    assert len(result.elements) == 1
    meta = engine.last_commit_result()
    dxf = Path(meta["dxf"])
    assert dxf.exists() and dxf.stat().st_size > 1000  # 真实 DXF 落盘


def test_direct_rejects_foreign_tool() -> None:
    from aec_copilot.errors import AECError

    engine = create_engine("acad", "direct")
    try:
        engine.call("revit_create_wall", {"id": "w", "start": [0, 0, 0], "end": [6000, 0, 0]})
    except AECError as e:
        assert e.code == "E_CONSTRAINT"
    else:
        raise AssertionError("跨引擎工具必须被拒绝")
