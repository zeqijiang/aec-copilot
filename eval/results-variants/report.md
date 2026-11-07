# 双规划器对比评测（planner 级，golden 口径）

- 用例: 11

| 规划器 | 通过 | 通过率 | 规则回退 | LLM tokens | 总耗时 |
|---|---|---|---|---|---|
| 规则版（确定性） | 4 | 36% | – | 0 | 4ms |

| case | category | 规则版 | LLM 版 |
|---|---|---|---|
| v01_wall | wall | ✅ | – |
| v02_wall | wall | ✅ | – |
| v09_room | room | ❌ | – |
| v17_frame | frame | ❌ | – |
| v23_building | building | ❌ | – |
| v33_level | level | ❌ | – |
| v37_column | column | ✅ | – |
| v41_slab | slab | ❌ | – |
| v45_opening | opening | ❌ | – |
| v47_polyline | polyline | ✅ | – |
| v49_part | part | ❌ | – |

> LLM 列未运行：配 `AEC_LLM_API_KEY` + `AEC_LLM_MODEL`（OpenAI 兼容端点）后加 `--llm` 重跑。
