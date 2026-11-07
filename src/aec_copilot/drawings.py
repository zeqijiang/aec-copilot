"""Revit 出图工作流封装：把「视图 → 图纸排布 → 明细表 → 导出」的 10+ 步
桥原子操作封装成 Agent 一次可调的工作流。

设计依据：RevitCommandBridge PROTOCOL.md 的出图原子操作全集
（create_view / create_section_view / create_elevation_view / create_sheet /
place_view_on_sheet / create_schedule / place_schedule_on_sheet / export）。

工作流（revit_drawings）：
  full_set —— 一套图：平面 F1/F2 + 剖面 A-A + 立面 E1-E4 + 3D 总览
              → A-101 图纸排布（平面+3D）→ A-201（剖面+立面）
              → 门窗明细表 → （可选）DWG/PNG 导出
"""

from __future__ import annotations

from typing import Any


def full_set_steps(*, levels: list[str] | None = None, include_schedule: bool = True,
                   export_formats: list[str] | None = None, output_dir: str | None = None,
                   sheet_number_prefix: str = "A") -> list[dict[str, Any]]:
    """组装一套施工图工作流的桥原子步骤。levels 为标高名列表（如 ["F1","F2"]）。"""
    levels = levels or ["F1", "F2"]
    steps: list[dict[str, Any]] = []
    view_ids: dict[str, str] = {}

    # 1) 各层平面视图
    for i, lv in enumerate(levels, 1):
        sid = f"dwg_plan_{i}"
        steps.append({"id": sid, "operation": "create_view", "args": {"kind": "floor_plan", "level": lv}})
        view_ids[f"plan_{lv}"] = f"${sid}"

    # 2) 剖面 A-A（横向）+ B-B（纵向）+ 南立面（index 0——新建项目自带 4 个默认立面
    #    marker，自建 marker 的 origin 易与默认 marker 撞槽位 "index is occupied"，故只建 1 个）
    steps.append({"id": "dwg_section", "operation": "create_section_view",
                  "args": {"origin": {"x": 0, "y": 0, "z": 1200}, "direction": {"x": 0, "y": 1, "z": 0},
                           "width_mm": 20000, "height_mm": 12000, "depth_mm": 600}})
    view_ids["section"] = "$dwg_section"
    steps.append({"id": "dwg_section_bb", "operation": "create_section_view",
                  "args": {"origin": {"x": 0, "y": 0, "z": 1200}, "direction": {"x": 1, "y": 0, "z": 0},
                           "width_mm": 20000, "height_mm": 12000, "depth_mm": 600}})
    view_ids["section_bb"] = "$dwg_section_bb"
    steps.append({"id": "dwg_elev_1", "operation": "create_elevation_view",
                  "args": {"plan_view_id": view_ids[f"plan_{levels[0]}"], "origin": {"x": 6000, "y": 0, "z": 1200}, "index": 0}})
    view_ids["elev_E1"] = "$dwg_elev_1"

    # 3) 3D 总览
    steps.append({"id": "dwg_3d", "operation": "create_view", "args": {"kind": "3d"}})
    view_ids["overview"] = "$dwg_3d"

    # 4) 图纸排布：A-101（平面+3D）、A-201（剖面 A-A + 立面）、A-202（剖面 B-B + 明细表）
    steps.append({"id": "sheet_101", "operation": "create_sheet", "args": {"sheet_number": f"{sheet_number_prefix}-101", "name": "一层平面图"}})
    steps.append({"id": "sheet_201", "operation": "create_sheet", "args": {"sheet_number": f"{sheet_number_prefix}-201", "name": "剖面与立面"}})
    steps.append({"id": "place_p101", "operation": "place_view_on_sheet",
                  "args": {"sheet_id": "$sheet_101", "view_id": view_ids[f"plan_{levels[0]}"], "point": {"x": 0, "y": 0}}})
    steps.append({"id": "place_3d101", "operation": "place_view_on_sheet",
                  "args": {"sheet_id": "$sheet_101", "view_id": view_ids["overview"], "point": {"x": 420000, "y": 0}}})
    steps.append({"id": "place_sec201", "operation": "place_view_on_sheet",
                  "args": {"sheet_id": "$sheet_201", "view_id": view_ids["section"], "point": {"x": 0, "y": 0}}})
    steps.append({"id": "place_elev201", "operation": "place_view_on_sheet",
                  "args": {"sheet_id": "$sheet_201", "view_id": view_ids["elev_E1"], "point": {"x": 420000, "y": 0}}})

    # 5) 门窗明细表 + 放置
    if include_schedule:
        steps.append({"id": "sched_doorwin", "operation": "create_schedule",
                      "args": {"kind": "regular", "category": "OST_Windows", "fields": ["类型", "宽度", "高度", "合计"]}})
        steps.append({"id": "place_sched", "operation": "place_schedule_on_sheet",
                      "args": {"sheet_id": "$sheet_201", "schedule_id": "$sched_doorwin", "point": {"x": 840000, "y": 0}}})

    # 6) 导出（DWG/PNG 按需；ifc 走 export_ifc 演示脚本）
    for k, fmt in enumerate(export_formats or []):
        fmt = fmt.lower()
        if fmt == "dwg":
            steps.append({"id": f"export_dwg_{k}", "operation": "export",
                          "args": {"format": "dwg", "view_ids": [view_ids[f"plan_{levels[0]}"]], "output_path": (output_dir or "out") + "/dwg"}})
        elif fmt == "png":
            steps.append({"id": f"export_png_{k}", "operation": "export",
                          "args": {"format": "png", "active_view": True, "output_path": (output_dir or "out") + "/png"}})
    return steps


def drawings_tool(args: dict[str, Any], execute) -> dict[str, Any]:
    """revit_drawings 工具实现。execute(steps, preview) → 桥结果。

    桥要求 export 单独成计划：主计划（视图+图纸+明细表）先提交，
    导出步骤随后逐条独立执行。
    """
    workflow = args.get("workflow", "full_set")
    if workflow != "full_set":
        raise ValueError(f"未知出图工作流 {workflow!r}（当前支持 full_set）")
    steps = full_set_steps(
        levels=args.get("levels") or ["F1", "F2"],
        include_schedule=args.get("include_schedule", True),
        export_formats=args.get("export_formats") or [],
        output_dir=args.get("output_dir"),
        sheet_number_prefix=args.get("sheet_number_prefix", "A"),
    )
    preview = bool(args.get("preview", False))
    export_steps = [s for s in steps if s["operation"] == "export"]
    main_steps = [s for s in steps if s["operation"] != "export"]
    main_result = execute(main_steps, preview)
    exports = []
    for es in export_steps:
        exports.append(execute([es], preview))
    return {"workflow": workflow, "preview": preview, "main_steps": len(main_steps),
            "exports": len(exports), "result": main_result, "export_results": exports}
