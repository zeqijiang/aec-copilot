# Live 后端（真机）接入指南

把「蓝图智匠」框架的仿真后端换成 Revit / AutoCAD / SolidWorks 真机，核心是 `config/mcp.live.json`：
`MCPEngine`（src/aec_copilot/engines/mcp.py）按配置拉起统一 aec-mcp server（stdio），并把
契约工具映射过去。**调用、校验、重试、审图、报告的框架代码零改动。**

## 架构

```
aec run "生成一个6m×4m的房间" --backend mcp --mcp-config config/mcp.live.json
  └ Runner（不改）
     └ MCPEngine（契约适配，不改）
        └ stdio → aec-mcp server（契约兼容层 src/aec_mcp/contract.py）
           ├ 缓冲式事务：call 只缓冲，commit 一次性打给 Revit 桥（all-or-nothing）
           ├ manifest：事务内返回规范意图快照（与 sim 同口径），verify 不过即回滚
           └ 引擎通道：revit=桥2.0 文件队列 / acad=ezdxf 离线 DXF / sw=COM
```

## 前置条件（踩坑实录，缺一不可）

1. **Revit 桥在线**：启动 Revit 2024，`%LOCALAPPDATA%\RevitCommandBridge\2024\status.json`
   心跳 180s 内为 running。
2. **完整性级别分层**（本机 uv 托管 Python 跑在低完整性令牌下）：
   ```powershell
   $root = "$env:LOCALAPPDATA\RevitCommandBridge\2024"
   icacls $root /setintegritylevel "(OI)(CI)M"          # 根目录必须 Medium（DLL 加载）
   icacls "$root\inbox"  /setintegritylevel "(OI)(CI)L"  # 队列目录 Low（低完整性写入手）
   icacls "$root\outbox" /setintegritylevel "(OI)(CI)L"
   icacls "$root\processing" /setintegritylevel "(OI)(CI)L"
   ```
   整个根目录降 Low 会导致 Revit 报「无法运行外部应用程序 Revit Command Bridge」。
3. **中文 PDF 报告字体**：
   ```powershell
   $env:REPORTLAB_CJK_REGULAR_FONT = "C:\Windows\Fonts\simhei.ttf"
   ```
4. **墙类型**：桥的 create_wall 默认类型解析依赖英文 "Basic Wall" 命名；aec-mcp 引擎层已
   自动查 `list_wall_types` 补第一个真实类型（中式样板「墙 1」无关化），无需手填。

## 验收实录（2026-11-07）

```
uv run aec run "生成一个6m×4m的房间" --engine revit --backend mcp ^
     --mcp-config config/mcp.live.json --attempts 2 --output runs/live-smoke
→ status=passed · elements=4 · attempt 1 · 1161ms · 0 差异
→ Revit 内 query_elements(OST_Walls).count = 4（独立核对）
→ 产物：modeling-report.pdf + model-schedule.xlsx + attempt-1.png + run.json
```

## M1 边界（已知限制 → M2）

| 项 | 状态 |
|---|---|
| revit: level / grid / wall / column(→DirectShape 方柱) / slab(→floor) | ✅ 真机 |
| revit: door / window | ⏳ M2（桥 create_opening 语义确认） |
| manifest 逐字段比对 | 事务内=意图快照（防呆门禁）；**真实几何漂移比对 M2**（读真实构件参数复核） |
| acad: draw_polyline | ✅ 真实 DXF |
| sw: create_part(box 拉伸) | ✅；assembly ⏳ M2 |
| 门/窗宿主、审图真机化、50 例评测真机跑批 | ⏳ M2 |
