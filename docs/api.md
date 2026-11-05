# 本地 HTTP API

启动：

```bash
aec serve --host 127.0.0.1 --port 8000 --output runs
```

默认 CORS Origin 为 `http://localhost:3000`，可用 `AEC_WEB_ORIGIN` 修改。服务没有生产认证、多租户隔离或云端安全控制，不应直接暴露公网。

## GET `/api/health`

返回版本、模拟后端状态和 `live_engines_verified=false`。

## POST `/api/plan`

```json
{"instruction":"生成一个6m×4m的房间","engine":"revit"}
```

返回 `plan` 和编译后的 `calls`，不写模型。

## POST `/api/run`

```json
{"instruction":"在0,0画一面6m长的墙","engine":"revit","max_attempts":3,"write_reports":true}
```

Web API 只接受 `simulation`；真实 MCP 必须走 CLI 并完成本机联调。成功返回完整 `RunResult`；建模最终失败返回 HTTP 422 与同一结构，请求格式错误返回 400。

## POST `/api/audit`

```json
{"elements":[{"id":"w","type":"wall","start":[0,0,0],"end":[6000,0,0],"height":3600,"thickness":80}],"write_reports":false}
```

返回问题项、建议和项目规则免责声明。`write_reports=true` 时保存到 `runs/audits/latest`，会覆盖该演示目录中的上一份报告。

## GET `/api/runs/{run_id}`

读取一次运行记录。`run_id` 只允许字母、数字、连字符和下划线。

## GET `/api/artifacts/{run_id}/{filename}`

仅允许白名单文件：`plan.json`、`elements.json`、`run.json`、`attempt-1.png` 至 `attempt-3.png`、`model-schedule.xlsx`、`modeling-report.pdf`。服务使用固定输出根目录、文件名白名单和路径父级检查，避免任意文件读取。
