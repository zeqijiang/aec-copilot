# 知识库与 few-shot

## 本地可复现索引

`knowledge/successful_plans.jsonl` 每行包含：

```json
{"id":"01_wall","instruction":"...","plan":{},"source":"eval/cases; simulation-verified"}
```

检索使用字符、英文 token 与中文 bigram 的归一化重合度，无外部依赖：

```python
from aec_copilot.knowledge import LocalKnowledgeBase
kb = LocalKnowledgeBase("knowledge/successful_plans.jsonl")
for hit in kb.search("创建一个6米×4米房间", limit=3):
    print(hit.score, hit.instruction, hit.plan)
```

`prompt_examples()` 可生成 few-shot 文本。该实现不是 LightRAG，也不自动保证规划通过率提升。

## LightRAG 适配器

```bash
export LIGHTRAG_BASE_URL='http://127.0.0.1:9621'
export LIGHTRAG_API_KEY='...'  # 若部署启用认证
```

```python
from aec_copilot.knowledge import LightRAGClient
client = LightRAGClient()
print(client.query("6m×4m 房间的历史 DSL", mode="hybrid"))
```

适配器调用 `/query`，请求 `include_references=true`。你的 resume-rag 若修改过路由或响应结构，需要在 `knowledge.py` 中适配；不要假定未核对的接口形状。

## 完整的 P4 还需做

1. 灌入已获授权且版本明确的制图标准、Revit 建模规范和历史成功案例。
2. 把检索示例注入规划 prompt，并对输出继续执行同一 DSL 校验。
3. 固定训练/验证/测试划分，防止相似指令泄漏造成虚高。
4. 在独立测试集上比较 P2 与 P4，计算通过率差值及置信区间。
5. 保存每次检索引用、模型版本和供应商 Token。

本交付没有执行上述提升实验，因此不声称“相似指令通过率提升 15%”。
