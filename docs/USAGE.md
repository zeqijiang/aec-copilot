# 使用说明 · 蓝图智匠 AEC Copilot

> 一句中文 → Revit/AutoCAD/SolidWorks 里的真实模型 → 自动校验 → Excel/PDF 报告。
> 不是聊天机器人，是有手有眼的工业软件 Agent。

- 仓库：https://github.com/zeqijiang/aec-copilot （main 已含真机后端）
- 状态：**Revit 2024 真机全链路已验证**（2026-11-07，50 例评测 48/50，Revit 类 46/46=100%）

---

## 一、这一天都干了什么（时间线）

| 阶段 | 内容 | 结果 |
|---|---|---|
| P0 引擎层 | 新建 `aec-mcp`：统一 mm 单位、9 类错误码、preview/commit/rollback 事务、三引擎适配器（Revit 桥 / AutoCAD COM+ezdxf / SolidWorks COM）、工具目录 | 本地仓库 `D:\...\aec-copilot`，35 测试全绿 |
| M1 合并 | 与 GitHub 上「蓝图智匠」仿真全功能框架（规划器/审图/报告/50 例评测/Web）合流：写契约兼容层，框架**零改动**接入真机 | Revit 真机房间 4 墙通过，1161ms |
| M2 深化 | 门窗洞口（桥 create_opening）、提交后真实几何复核（1mm 容差）、每例文档隔离、评测批跑工程化 | 50 例真机 48/50；审图 20/20；合 main 推送 |
| 压轴（未完） | IFC 导出演示（打"二次建模"痛点） | 建模通过，桥 IFC 分支缺事务，补丁被源码树两处历史 API 不兼容卡住（见"限制"） |

顺手修掉的真 Bug：桥结果契约误判（假成功）、中式样板墙类型、Windows 完整性级别分层、ezdxf 毒化 stdio、跨用例文档重名污染、SW 静默拉起。

## 二、现在能干什么（全部真机验证过）

| 能力 | 说明 | 验证 |
|---|---|---|
| **中文建模** | "生成一栋30m×20m的两层小楼，层高3.6m，外墙200mm，中间加一道隔墙，四个角放柱子" → Revit 真实标高/轴网/墙/柱/板/门窗 | 建筑 10/10、框架 6/6、房间 8/8、墙 8/8 … Revit 合计 **46/46** |
| **自动校验** | 三道关：意图快照逐字段比对（0.01mm）→ 截图存档 → **提交后读回真实构件比对几何**（墙长/高/厚，漂移>1mm 自动删除重建） | 内建在每次 run |
| **失败回滚** | 任一步失败整体回滚（Revit 桥内 all-or-nothing 事务），绝不污染工程 | 回滚用例覆盖 |
| **智能审图** | 构件清单 → 规则引擎（墙厚/墙高/门窗尺寸与宿主/孤儿门窗/重名/标高轴网冲突…）→ 问题清单 | 预埋缺陷检出 **20/20** |
| **报告产出** | 每次执行自动出 Excel 构件明细 + 中文 PDF 报告 + run.json（机读） | 每次运行 |
| **CAD 出图** | 多段线等 → 真实 DXF 文件（ezdxf 离线，无需 AutoCAD） | polyline 2/2 |
| **评测基准** | 50 例指令真机跑批，通过率/耗时/差异落盘，可复现 | `eval/results-live/report.md` |
| **MCP 工具化** | aec-mcp 可挂进 DSH / Claude / Cursor 当工具用 | DSH 已挂载（`mcp__aec__*`） |

## 三、你自己怎么用（Windows 本机）

### 环境要求
- Revit 2024 + RevitCommandBridge 插件（已装）；跑批时 Revit 保持打开
- Python 3.11+ / uv；两个仓库：`aec-copilot`（引擎层）、`aec-copilot-merged`（框架）

### 一次性设置
```powershell
# 1) 桥队列目录完整性分级（低完整性 Python 写入 + DLL 可加载，缺一不可）
$root = "$env:LOCALAPPDATA\RevitCommandBridge\2024"
icacls $root /setintegritylevel "(OI)(CI)M"
icacls "$root\inbox","$root\outbox","$root\processing" /setintegritylevel "(OI)(CI)L"

# 2) 依赖
cd D:\admin\Documents\deepseek-harness\default-workspace\aec-copilot; uv sync
cd ..\aec-copilot-merged; uv sync --extra all
```

### 日常使用（框架仓库 aec-copilot-merged）
```powershell
$env:REPORTLAB_CJK_REGULAR_FONT = "C:\Windows\Fonts\simhei.ttf"  # 中文 PDF
$env:AEC_REVIT_WAIT = "240"        # 桥等待（骑过偶发空转窗口）
$env:AEC_REVIT_FRESH_DOC = "1"     # 每例自动新文档（批跑防重名污染）

# 看计划不下笔
uv run aec preview "生成一个6m×4m的房间" --engine revit

# 真机建模（全自动：计划→事务→执行→截图→校验→报告）
uv run aec run "生成一栋12m×8m的两层建筑，层高3.3m，墙厚200mm" `
     --engine revit --backend mcp --mcp-config config/mcp.live.json --output runs/demo

# 审图（拿任意 run 的 elements.json）
uv run aec audit runs\demo\<run_id>\elements.json --output runs/audit

# 50 例评测批跑 / 重建报告
uv run python scripts/run_eval_live.py --output eval/results-live
uv run python scripts/rebuild_live_report.py

# 模拟后端（不开 Revit 也能跑全流程） / Web API / MCP server
uv run aec run "生成一个6m×4m的房间" --backend simulation
uv run aec serve --port 8000
uv run aec mcp
```

### 引擎层仓库（aec-copilot）独立 CLI
```powershell
uv run aec health                        # 三引擎心跳
uv run aec tools                         # 工具目录
uv run aec run "在 0,0 画一面 6m 长的墙" --engine acad --offline   # 出 DXF+PNG
```

### 在 DSH 里直接对话（已挂载，全局 `aec` 前缀）
新开会话直接说：
> 在 Revit 里生成一个 6m×4m 的房间，先给我看计划，确认后执行并导出明细表

Agent 会调 `mcp__aec__aec_plan` / `aec_run` / `revit_execute_plan` 等真工具。

## 四、别人怎么用（从 GitHub 拉下来）

```powershell
git clone https://github.com/zeqijiang/aec-copilot.git
cd aec-copilot
uv sync --extra all
uv run aec run "生成一个6m×4m的房间" --backend simulation   # 任何机器立即可跑
uv run pytest          # 30 项测试
uv run aec eval        # 50 例模拟基准
```

**真机后端**（需要 Revit 2024）额外三步：
1. 安装 RevitCommandBridge 插件（本仓库 `docs/live-backend.md` 有坑位手册）；
2. 拿到 aec-mcp 引擎层（当前在作者本机仓库 `D:\...\aec-copilot`，**尚未 vendor 进 monorepo**——这是第一个待办）；
3. 改 `config/mcp.live.json` 里两个绝对路径为本机路径，然后 `--backend mcp --mcp-config config/mcp.live.json`。

**Claude / Cursor 用户**：把 aec-mcp 挂成 MCP server（stdio，`uv run --project <引擎层路径> aec-mcp-server`），即可用自然语言驱动三引擎。

## 五、安全边界（为什么敢让它碰工程文件）

```
指令 → DSL 计划（可校验/可重放） → preview（只读校验）
     → commit（桥内单事务 all-or-nothing） → 真实几何复核
     → 任一环失败：整体回滚 + journal.json 审计留痕
```
- 模型永远不直接吐 API 调用：幻觉族名/单位错乱在 DSL 层就被拦；
- query 先行：写之前先查项目真实的族/类型/标高，不猜名字；
- 批跑一律在新文档副本上执行（`AEC_REVIT_FRESH_DOC`），用户工程零接触。

## 六、常见问题（今天的坑，全记录在案）

| 症状 | 原因 | 解法 |
|---|---|---|
| Revit 弹"无法运行外部应用程序" | 桥根目录被降到 Low 完整性，.NET 拒载 DLL | 根目录 M + 队列目录 L（见上） |
| Python 写 inbox 被拒 Errno 13 | uv 托管 Python 是低完整性令牌 | 同上，队列目录降 L |
| "create_wall 只支持 Basic WallType" | 中式样板墙类型名不同 | 引擎已自动 list_wall_types 补全 |
| 中文 PDF 报错 RuntimeError | reportlab 缺 CJK 字体 | `$env:REPORTLAB_CJK_REGULAR_FONT="C:\Windows\Fonts\simhei.ttf"` |
| 批跑第 N 例轴网/标高重名失败 | 多例同文档，Revit 名称全局唯一 | `AEC_REVIT_FRESH_DOC=1` |
| acad 提交挂死无响应 | ezdxf 导入扫描字体 25s~4min + 警告塞满 stderr 管道 | 已改子进程隔离（acad_builder.py） |
| 批跑偶发 2-8 分钟空转 | Revit 空闲事件调度停摆 | `AEC_REVIT_WAIT=240` 骑过去；重跑即过 |

## 七、当前限制与下一步

**限制（诚实清单）**
- IFC 导出：建模链路通，桥的 ifc 分支缺事务包裹；补丁已写但桥源码树有两处**历史遗留** API 不兼容（`Revision.NumberType`、`NewFloor`，与补丁无关），需按 2024 API 移植后重编译；
- SolidWorks：需 SW 已启动；P0 仅 box 拉伸零件；装配需"将p1和p2创建装配体"句式；
- acad 真机 = ezdxf 离线 DXF（COM 直连路径在引擎层仓库，未接契约层）；
- `config/mcp.live.json` 内是本机绝对路径，他人需手改；
- 引擎层与框架分属两个仓库，未 vendor。

**下一步优先级**
1. aec-mcp vendor 进 monorepo（别人 clone 即全套）；
2. 桥源码移植到 2024 API → 重编译 → IFC 导出闭环（打"二次建模"）；
3. LLM planner 接入与规则版对比评测（token 主战场）；
4. SW 零件/装配真机用例补跑；
5. Web 控制台接 live 后端 + 60s 演示视频。
