# Windows 本机真实引擎联调

> 这一步尚未在交付沙箱中执行。你的 Revit 2024、AutoCAD 2026、SOLIDWORKS 2026、CAD-MCP、revit_2024 与 SolidWorks MCP 都没有挂载到当前环境。以下是接入层和验收流程，不是实机通过声明。

## 1. 先保护工程

1. 关闭其他会修改测试文档的插件与会话。
2. 复制 `.rvt` / `.dwg` / `.sldprt` / `.sldasm` 到独立测试目录。
3. 只用副本做写入测试；保留原始工程快照。
4. 先在 CLI 中运行模拟后端，确认 DSL 和预期清单正确。
5. 不在生产模型中测试回滚，不把 `preview=false` 当作无风险操作。

## 2. 映射现有 MCP

复制 `examples/mcp-config.example.json`，按实际上游工具名修改：

- `command`：参数数组，不使用 shell 字符串；建议 Python 虚拟环境绝对路径。
- `tools`：统一工具名 → 你的现有 MCP 工具名。
- `transactions.begin/commit/rollback`：三个原生事务工具都必须存在。
- `manifest_tool`：只读返回本项目的通用构件 JSON 数组，不能只返回“调用成功”。
- `capture_tool`：可选，接收 `output` 和 `format=png`，实际生成原生截图。

现有 `revit_2024 execute_plan` 不能自动等价为这里的事务接口。你需要写一个薄适配层，把本项目的原子参数转换成上游参数，并把真实读取结果规范化为 `id/type/start/end/height/thickness/...`。坐标系、Revit 内部英尺与项目 mm 的转换必须在适配器中显式处理并测试。

## 3. 真实写入的硬性保护

- 缺任一事务钩子：`E_ENGINE_DOWN`，拒绝执行。
- 缺只读清单工具：可以执行底层适配器调用，但无法完成 Runner 的语义校验；不建议用于真实写入。
- 工具返回 `isError=true`：转换为 `E_ENGINE_DOWN` 并回滚。
- 未配置 `capture_tool`：只能生成带 `MANIFEST RENDER` 标识的清单图，不冒充软件原生截图。
- 标准库 stdio client 是一请求一响应的最小实现，不支持服务器主动请求或复杂通知；需要完整 MCP 能力时改用官方 SDK 并实现同一 `MCPClient` 协议。

## 4. 分引擎最小验收序列

### Revit

1. `revit_create_level`：创建 0mm 与 3600mm，读取标高验证。
2. `revit_create_wall`：在副本创建 6000mm 单墙，读取起终点、厚度、高度。
3. 门窗：验证宿主、开洞、offset 和底部标高，不只检查门族实例存在。
4. 事务：第二步故意失败，重新打开副本确认第一步也不存在。
5. 原生截图：激活约定视图、导出 PNG，再由人工与 VLM 分别检查。

### AutoCAD

1. 绘制三点闭合多段线，读取顶点数量、坐标、闭合状态与图层。
2. 注入非法第二点，验证第一点也被回滚。
3. 核对当前空间（模型/布局）、单位与坐标系。

### SolidWorks

1. 创建 box/cylinder 测试零件，读取几何尺寸。
2. 创建装配并读取零件引用；本项目通用契约尚未覆盖 mate 求解。
3. 验证失败事务不会遗留临时文件、只读锁或未保存文档修改。

## 5. 实机验收记录模板

```text
日期 / 操作者：
软件版本与插件 commit：
测试工程副本 SHA-256：
MCP 配置（脱敏）：
指令与 plan.json：
预期 golden manifest：
实际 manifest 差异：
原生截图路径：
事务回滚证据：
每轮耗时 / 供应商 Token：
人工结论与签名：
```

只有上述证据齐全后，才能把 `docs/evaluation.md` 中的模拟指标替换为实机指标，或填写简历中的一次通过率、收敛率和成本降低比例。
