---
name: aec-copilot
description: 用自然语言在 Revit/AutoCAD/SolidWorks 里真实建模、出图、审图、算量、算造价。当用户要求"建一栋楼/生成房间/出平面剖面立面图/审图/算工程量/出造价/导出 IFC/DWG"或任何 BIM/CAD 建模出图任务时使用。优先走 MCP 工具（aec_*）；无 MCP 时回退到本仓库 CLI。
---

# AEC Copilot（蓝图智匠）

自然语言驱动的 BIM/CAD 建模与智能审图。一句中文 → 真模型 → 出图 → 审图 → 造价 → IFC。

## 何时用

- 用户要**建模**：房间/墙/柱/板/门窗/多层建筑/标高轴网
- 用户要**出图**：平面、剖面、立面、详图、图纸排布、DWG/PNG 导出
- 用户要**审图**：砌体/门窗/构件/命名/标高冲突检查
- 用户要**算量或造价**：真模型工程量、GB50854 清单、总造价报告
- 用户要**识别图纸**：读 DWG/DXF 结构
- 用户要**数据交换**：导出 IFC

## 怎么调（按优先级）

### 1) 有 MCP（首选）
装了 `aec` MCP server 时，直接调这些工具：
`aec_health` `aec_preview` `aec_run` `aec_audit` `aec_recent_runs` `revit_execute_plan`
`revit_new_project` `revit_drawings` `aec_export` `aec_import_drawing` `aec_review_image`
`aec_quantity` `aec_cost_estimate`

典型：`aec_run(instruction="生成一栋12m×8m的两层建筑，层高3.3m", engine="revit", backend="direct")`

### 2) 无 MCP → 用 CLI
```powershell
$env:REPORTLAB_CJK_REGULAR_FONT = "C:\Windows\Fonts\simhei.ttf"
uv run aec preview "生成一个6m×4m的房间" --engine revit
uv run aec run "生成一栋12m×8m的两层建筑" --engine revit --backend direct --output runs/demo
uv run aec audit runs\demo\<run_id>\elements.json
```

### 3) 连 MCP（如果没装）
配置 `mcpServers.aec`：
```json
{ "mcpServers": { "aec": {
  "command": "uv",
  "args": ["run", "--project", "<仓库>", "python", "-m", "aec_copilot.mcp_full"],
  "cwd": "<仓库>"
} } }
```

## 硬性约定（重要）

- **先 preview 再 run**：`aec_run` 会先校验意图再动手；写操作失败整体回滚，不会污染工程。
- **真机前置**：Revit 必须先打开一个项目文档，否则桥明确报「请先打开项目文档」——这是错误不是挂起，可重试。
- **单位**：默认 mm，可写 `"3.6m"`。
- **失败码**：`E_UNIT` `E_GEOM` `E_NOT_FOUND` `E_CONSTRAINT` `E_ENGINE_DOWN` `E_ENGINE_TIMEOUT` `E_PLAN_INVALID` `E_ROLLBACK` `E_INTERNAL`——按码判断是重试还是改指令。
- **造价口径**：综合单价为演示价目；钢筋/土方为指标与假设推算；导入真实定额后替换。报告里都写明来源，别当成正式结算。

## 产出物在哪

- 运行记录：`runs/<run_id>/run.json` + 截图 `attempt-N.png`
- 出图/导出：`runs/<run_id>/`
- 造价报告：`runs/cost/cost-report.{md,xlsx,json}`

## 限制

- SolidWorks 需 SW 已启动；P0 仅 box 零件
- 门窗"按樘计价"需补装 Revit 门窗族库；当前用洞口 + m² 合法口径
- 多版本 Revit：2020-2024 就绪；2025+ 需 .NET 8 适配器
