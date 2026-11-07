# 真机评测报告（live backend, 2026-11-07）

- 总用例: 50  通过: 48  通过率: 96%
- 说明：49_part / 50_assembly 为 SOLIDWORKS 引擎，本机 SW 未启动，按设计快速失败（E_ENGINE_DOWN）；50_assembly 另需零件 ID 语法（规划器约束）。

| 用例 | engine | 状态 | 尝试 | 指令 |
|---|---|---|---|---|
| 01_wall | revit | ✅ passed | 1 | 01_wall |
| 02_wall | revit | ✅ passed | 1 | 02_wall |
| 03_wall | revit | ✅ passed | 1 | 03_wall |
| 04_wall | revit | ✅ passed | 1 | 04_wall |
| 05_wall | revit | ✅ passed | 1 | 05_wall |
| 06_wall | revit | ✅ passed | 1 | 06_wall |
| 07_wall | revit | ✅ passed | 1 | 07_wall |
| 08_wall | revit | ✅ passed | 1 | 08_wall |
| 09_room | revit | ✅ passed | 1 | 09_room |
| 10_room | revit | ✅ passed | 1 | 10_room |
| 11_room | revit | ✅ passed | 1 | 11_room |
| 12_room | revit | ✅ passed | 1 | 12_room |
| 13_room | revit | ✅ passed | 1 | 13_room |
| 14_room | revit | ✅ passed | 1 | 14_room |
| 15_room | revit | ✅ passed | 1 | 15_room |
| 16_room | revit | ✅ passed | 1 | 16_room |
| 17_frame | revit | ✅ passed | 1 | 17_frame |
| 18_frame | revit | ✅ passed | 1 | 18_frame |
| 19_frame | revit | ✅ passed | 1 | 19_frame |
| 20_frame | revit | ✅ passed | 1 | 20_frame |
| 21_frame | revit | ✅ passed | 1 | 21_frame |
| 22_frame | revit | ✅ passed | 1 | 22_frame |
| 23_building | revit | ✅ passed | 1 | 23_building |
| 24_building | revit | ✅ passed | 1 | 24_building |
| 25_building | revit | ✅ passed | 1 | 25_building |
| 26_building | revit | ✅ passed | 1 | 26_building |
| 27_building | revit | ✅ passed | 1 | 27_building |
| 28_building | revit | ✅ passed | 1 | 28_building |
| 29_building | revit | ✅ passed | 1 | 29_building |
| 30_building | revit | ✅ passed | 1 | 30_building |
| 31_building | revit | ✅ passed | 1 | 31_building |
| 32_building | revit | ✅ passed | 1 | 32_building |
| 33_level | revit | ✅ passed | 1 | 33_level |
| 34_level | revit | ✅ passed | 1 | 34_level |
| 35_level | revit | ✅ passed | 1 | 35_level |
| 36_level | revit | ✅ passed | 1 | 36_level |
| 37_column | revit | ✅ passed | 1 | 37_column |
| 38_column | revit | ✅ passed | 1 | 38_column |
| 39_column | revit | ✅ passed | 1 | 39_column |
| 40_column | revit | ✅ passed | 1 | 40_column |
| 41_slab | revit | ✅ passed | 1 | 41_slab |
| 42_slab | revit | ✅ passed | 1 | 42_slab |
| 43_slab | revit | ✅ passed | 1 | 43_slab |
| 44_slab | revit | ✅ passed | 1 | 44_slab |
| 45_opening | revit | ✅ passed | 1 | 45_opening |
| 46_opening | revit | ✅ passed | 1 | 46_opening |
| 47_polyline | acad | ✅ passed | 1 | 47_polyline |
| 48_polyline | acad | ✅ passed | 1 | 48_polyline |
| 49_part | sw | ❌ failed | 2 | 49_part |
| 50_assembly | sw | 💥 error | 0 | 50_assembly |
