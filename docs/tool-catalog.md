# 统一工具目录

运行 `aec tools` 获取机器可读 JSON；MCP 客户端调用 `tools/list`。当前共 **15 个工具**。所有长度均为 mm，字符串可写 `3.6m`、`25cm`、`200mm`。

## Revit（模拟实现；真实后端需映射）

| 工具 | 必要参数 | 常用可选参数 |
|---|---|---|
| `revit_create_level` | `id`, `elevation` | `name` |
| `revit_create_grid` | `id`, `start`, `end` | `name` |
| `revit_create_wall` | `id`, `start`, `end` | `height=3600`, `thickness=200`, `level_id` |
| `revit_create_column` | `id`, `center` | `width=400`, `depth=width`, `height=3600`, `level_id` |
| `revit_create_slab` | `id`, `boundary`（至少三点） | `thickness=120`, `elevation=0`, `level_id` |
| `revit_create_door` | `id`, `host_id` | `width=900`, `height=2100`, `bottom=0`, `offset=居中` |
| `revit_create_window` | `id`, `host_id` | `width=1500`, `height=1500`, `bottom=900`, `offset=居中` |

坐标格式为 `[x, y, z]`，也接受 `[x, y]` 并自动补 `z=0`。门窗宿主必须在同一 Plan 内；宽度和位置不能超过宿主墙。

## AutoCAD

| 工具 | 必要参数 | 常用可选参数 |
|---|---|---|
| `acad_draw_polyline` | `id`, `points`（至少两点） | `closed=false` |

## SolidWorks

| 工具 | 必要参数 | 常用可选参数 |
|---|---|---|
| `sw_create_part` | `id` | `shape=box`, `width/depth/height=100`；或 `shape=cylinder`, `diameter/height=100`, `origin=[0,0,0]` |
| `sw_create_assembly` | `id`, `parts` | `parts` 必须是当前模型中已有零件 ID |

当前装配模拟只校验零件引用并记录装配关系，不实现真实配合约束、 mate 求解或干涉分析。

## 编排与读取

| 工具 | 作用 | 写入语义 |
|---|---|---|
| `aec_plan` | 中文转 DSL | 不写模型 |
| `aec_execute_plan` | 校验并编译 Plan；`preview=true` 返回调用序列，`false` 原子执行 | 默认不写；显式 false 才写 |
| `aec_run` | 规划、执行、截图、校验和最多三轮重试 | 运行目录与所选模型后端 |
| `aec_audit` | 对通用构件清单运行项目规则 | 不写模型 |
| `aec_snapshot` | 读取某引擎的通用清单 | 只读 |

## 统一错误

| 错误码 | 含义 |
|---|---|
| `E_UNIT` | 无法解析单位、非有限数值、错误长度类型 |
| `E_GEOM` | 零长度、非正尺寸、门窗越界等几何问题 |
| `E_NOT_FOUND` | 工具、构件或宿主不存在 |
| `E_CONSTRAINT` | 操作不支持、ID 重复、跨引擎或装配约束失败 |
| `E_ENGINE_DOWN` | MCP 进程、事务、截图、外部模型或适配器失败 |

MCP 工具失败使用 `isError=true`，文本载荷中保留 `error.code/message/details`。具体上游错误位于适配器 details，不扩张公共错误码。
