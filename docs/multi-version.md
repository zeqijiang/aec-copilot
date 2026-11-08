# 多版本 Revit 兼容方案（2018 – 2027）

> 目标：让所有低版本（与未来版本）Revit 都能用上 aec-copilot 全套能力。

## 一、分层兼容性（关键认知）

| 层 | 版本无关？ | 说明 |
|---|---|---|
| aec-mcp 客户端（Python） | ✅ 天然全版本 | 文件队列协议按年份目录隔离（`%LOCALAPPDATA%\RevitCommandBridge\<year>`），构造参数 `year` / env `AEC_REVIT_YEAR` 已支持 |
| MCP 工具面 / 面板 / CLI | ✅ 全版本 | 只是把命令投到对应年份的队列 |
| 通信协议（JSON/队列/REST） | ✅ 全版本 | 桥官方文档明确"protocol、JSON schema、MCP tool names、REST contract 版本无关" |
| **RevitCommandBridge DLL** | ❌ 每版本一个 | 必须针对该版本 `RevitAPI.dll` 编译；每版本独立 add-in 目录与 REST 端口（2020=8765 … 2024=8769） |

## 二、桥官方支持矩阵（VERSION-SUPPORT.md）

| Revit 版本 | 状态 | 说明 |
|---|---|---|
| 2020 | ✅ 真机回归 | 核心工作流 live-regressed |
| 2021–2024 | 🔶 已实现待验证 | 安装器扫描本机各版本，用本地 RevitAPI 自动编译年份匹配 DLL（无需 Visual Studio） |
| 2025–2026 | ❌ 未实现 | **需要 .NET 8 add-in 适配器**；当前构建脚本遇到 2025+ 故意停止 |
| 2027 | ❌ 未实现 | 已上架 Autodesk 官网；同 2025+ 通道 |

本机实测（2024）：`Revision.NumberType` 已移除、`NewFloor` 已移除（→ `Floor.Create`）——API 逐年迁移，跨版本编译必须逐版本处理差异。

## 三、行动计划

### 阶段 1：aec-mcp 多版本路由（已具备，补探测）
- `aec_health` 扫描 `%LOCALAPPDATA%\RevitCommandBridge\*` 全部年份桥的心跳，返回版本矩阵
- `aec_run`/`revit_*` 工具加 `revit_version` 参数 → 路由到对应年份队列
- 多版本同时在线时按端口（8765-8769）或队列目录分流

### 阶段 2：2025–2027 .NET 8 适配器（核心工程）
桥源码当前面向 .NET Framework 4.8（csc 编译）。2025+ RevitAPI 迁移到 .NET 8：
1. 建独立 `dotnet` SDK 工程引用 2025+ RevitAPI.dll（`dotnet build` 替代 csc）
2. API 差异处理（与已踩坑同款模式：反射探测属性存在性，缺失时降级）
3. 产物部署到 `%LOCALAPPDATA%\RevitCommandBridge\<year>\` + 对应端口
4. 真机验证需装有 2025+ 的机器

### 阶段 3：逐版本真机回归
2020-2024 每个版本跑同一条冒烟指令（单墙+房间+出图），产出版本兼容矩阵报告。

## 四、本机现状

- 本机仅装 Revit 2024（`D:\Revit 2024`）→ 2024 通道已真机验证 ✅
- 多版本真机验证需要对应版本安装环境（虚拟机/多机）
- aec-mcp 侧无需改动即可服务任何装好桥的版本 ✅

## 五、桥稳定性：watchdog 与后台节流（2024 实测）

**症状**：请求被桥领取（inbox→processing）后永不执行，客户端等到超时；数分钟到数十分钟不定期出现，偶发自愈。

**根因**：Revit 在后台被 Windows EcoQoS 节流时，ExternalEvent.Raise 偶发丢失——请求文件已领取但主线程回调从未触发。

**已部署的双重修复**（桥 DLL 已重编译部署）：
1. **processing watchdog**（BridgeFileQueue.RequeueStaleProcessing，90s 阈值）：领取后未完成的请求自动写失败响应并归档——客户端秒收失败可重试，不再傻等；日志留痕 `watchdog requeued stale processing requests=N`
2. **客户端重试**：aec_run 的 max_attempts 自动消化单次丢失

**部署建议**（管理员一次执行，永久解除节流）：
```powershell
powercfg /powerthrottling disable /path "D:\Revit 2024\Revit.exe"
```
