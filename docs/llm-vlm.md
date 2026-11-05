# LLM 与 VLM 配置

本次交付的基准没有调用外部模型，`reported_llm_tokens=0`。默认中文规划器是确定性的；只有确定性解析失败且环境变量齐全时，才调用 OpenAI-compatible Chat Completions JSON 接口。

## 受约束规划回退

```bash
export AEC_LLM_API_KEY='...'
export AEC_LLM_MODEL='your-json-capable-model'
export AEC_LLM_BASE_URL='https://api.openai.com/v1'  # 或兼容服务
```

LLM 只能返回本项目 DSL；返回后仍经过 Pydantic、编译器、宿主/几何约束和事务。它不能直接执行工具。密钥只从环境变量读取，不要写入 `mcp-config.json`、README 或提交到 Git。

## 可选视觉复核

```python
from aec_copilot.runner import Runner
from aec_copilot.verifier import VLMReviewer

runner = Runner(vlm=VLMReviewer(enforce=False))  # 默认 advisory
result = runner.run("生成一个6m×4m的房间")
```

环境变量：

```bash
export AEC_VLM_API_KEY='...'
export AEC_VLM_MODEL='your-vision-model'
export AEC_VLM_BASE_URL='https://api.openai.com/v1'
```

- 输入为原始指令与本次生成的 PNG。
- 返回 JSON 差异，存到 `vlm_advisory`。
- 默认 `enforce=False`，视觉判断不覆盖确定性几何。
- 未用独立缺陷集测定假阳性前，不建议启用 `enforce=True`。
- `attempts[].token_usage` 汇总规划器与每轮 VLM 的供应商 usage；未调用则为 0，不估算 Token。

## 尚未完成

当前没有可验证的外部 VLM 调用日志，也没有“三轮 × 5–8 次多模态调用”或“累计 10M+ Token”的实测依据。自动重试采用原始 canonical DSL 回滚重放；它可以恢复故障注入中的瞬态漏构件，但不能据此声称任意 VLM 语义偏差都能自动修复。
