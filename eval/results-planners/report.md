# 双规划器对比评测（planner 级，golden 口径）

- 用例: 50

| 规划器 | 通过 | 通过率 | 规则回退 | LLM tokens | 总耗时 |
|---|---|---|---|---|---|
| 规则版（确定性） | 49 | 98% | – | 0 | 9ms |

| case | category | 规则版 | LLM 版 |
|---|---|---|---|
| 01_wall | wall | ✅ | – |
| 02_wall | wall | ✅ | – |
| 03_wall | wall | ✅ | – |
| 04_wall | wall | ✅ | – |
| 05_wall | wall | ✅ | – |
| 06_wall | wall | ✅ | – |
| 07_wall | wall | ✅ | – |
| 08_wall | wall | ✅ | – |
| 09_room | room | ✅ | – |
| 10_room | room | ✅ | – |
| 11_room | room | ✅ | – |
| 12_room | room | ✅ | – |
| 13_room | room | ✅ | – |
| 14_room | room | ✅ | – |
| 15_room | room | ✅ | – |
| 16_room | room | ✅ | – |
| 17_frame | frame | ✅ | – |
| 18_frame | frame | ✅ | – |
| 19_frame | frame | ✅ | – |
| 20_frame | frame | ✅ | – |
| 21_frame | frame | ✅ | – |
| 22_frame | frame | ✅ | – |
| 23_building | building | ✅ | – |
| 24_building | building | ✅ | – |
| 25_building | building | ✅ | – |
| 26_building | building | ✅ | – |
| 27_building | building | ✅ | – |
| 28_building | building | ✅ | – |
| 29_building | building | ✅ | – |
| 30_building | building | ✅ | – |
| 31_building | building | ✅ | – |
| 32_building | building | ✅ | – |
| 33_level | level | ✅ | – |
| 34_level | level | ✅ | – |
| 35_level | level | ✅ | – |
| 36_level | level | ✅ | – |
| 37_column | column | ✅ | – |
| 38_column | column | ✅ | – |
| 39_column | column | ✅ | – |
| 40_column | column | ✅ | – |
| 41_slab | slab | ✅ | – |
| 42_slab | slab | ✅ | – |
| 43_slab | slab | ✅ | – |
| 44_slab | slab | ✅ | – |
| 45_opening | opening | ✅ | – |
| 46_opening | opening | ✅ | – |
| 47_polyline | polyline | ✅ | – |
| 48_polyline | polyline | ✅ | – |
| 49_part | part | ✅ | – |
| 50_assembly | assembly | ❌ | – |

> LLM 列未运行：配 `AEC_LLM_API_KEY` + `AEC_LLM_MODEL`（OpenAI 兼容端点）后加 `--llm` 重跑。
