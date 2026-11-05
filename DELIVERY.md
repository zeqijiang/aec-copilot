# 交付清单

## 源码包含

- Python 包：规划、DSL、编译、事务、模拟引擎、真实 MCP 适配、验证、审图、知识检索、报告、CLI、MCP server、HTTP API。
- Web 源码：Next.js App Router、React、TypeScript、three.js、完整样式与锁文件。
- 规格：`spec/plan.schema.json`。
- 测试：30 项 pytest；真实 stdio 进程与 HTTP 进程另做联调。
- 数据：50 个建模 case、50 个 golden、20 个审图 case、知识库样例、缺陷模型示例。
- 文档：中英 README、架构、工具目录、本机联调、LLM/VLM、知识库、API、评测与交付说明。
- 实测汇总：evaluation.json / xlsx / pdf、audit-results.json、模拟预览图。

## 不包含

- `node_modules`、`.next`、虚拟环境、缓存、密钥、本机私有工程文件。
- 你的 Windows 原有 CAD-MCP / revit_2024 / SolidWorks MCP 源码；交付提供的是统一服务与配置驱动适配层。
- 未经授权的规范全文。

## 完成状态

| 方案阶段 | 当前状态 |
|---|---|
| P0 统一引擎层 | 模拟后端与统一 MCP 已验证；真实三引擎待本机联调 |
| P1 DSL 与事务 | 已实现并通过自动测试 |
| P2 视觉闭环 | 模拟截图、确定性校验、三轮回滚重试已实现；外部 VLM 未实调 |
| P3 审图 Agent | 项目规则与 PDF/Excel 已实现；LLM 语义审图未完成 |
| P4 知识库 | 本地 few-shot 与 LightRAG 适配器；完整部署及提升对照实验未完成 |
| P5 交付发布 | CLI/API/Web/报告/文档完成；剪映视频与 GitHub 发布未执行 |

## 最重要的边界

这份源码可运行、可测试、可继续开发，但不能据此声称“已经在真实 Revit / AutoCAD / SolidWorks 中完成项目”。实机验收、VLM 实测、RAG 提升、语义审图、视频和发布仍需对应环境与证据。
