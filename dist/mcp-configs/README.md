# AEC Copilot 接入其它 Agent（MCP / Skill）

> AEC Copilot 原生形态是 **MCP Server**（`python -m aec_copilot.mcp_full`，13 个工具）。
> 任何支持 MCP 的 agent 加一条配置即可直接调用。另附一份 **Skill**，用于只认技能包的 agent。

## 零、先决条件（本机已装好）

```powershell
# 依赖（一次性）
uv sync --extra all
# 真机模式需要：Revit 2024 + RevitCommandBridge 桥；纯模拟/离线不需要
```

服务端信息（供下面所有客户端复用）：

```text
command : <仓库>\\.venv\\Scripts\\python.exe       # 或 uv run python
args    : -m aec_copilot.mcp_full
cwd     : <仓库>
env     : REPORTLAB_CJK_REGULAR_FONT=C:\\Windows\\Fonts\\simhei.ttf
          AEC_REVIT_WAIT=240
```

---

## 一、Codex CLI（OpenAI）

编辑 `~/.codex/config.toml`，追加：

```toml
[mcp_servers.aec]
command = "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged\\.venv\\Scripts\\python.exe"
args = ["-m", "aec_copilot.mcp_full"]
cwd = "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged"
env = { REPORTLAB_CJK_REGULAR_FONT = "C:\\Windows\\Fonts\\simhei.ttf", AEC_REVIT_WAIT = "240" }
```

之后在 Codex 里直接说「用 aec 生成一栋两层小楼」即可。查看：`codex mcp list`。

## 二、Claude Code

项目根或 `~/.claude` 下新建 `.mcp.json`：

```json
{
  "mcpServers": {
    "aec": {
      "command": "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged\\.venv\\Scripts\\python.exe",
      "args": ["-m", "aec_copilot.mcp_full"],
      "cwd": "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged",
      "env": {
        "REPORTLAB_CJK_REGULAR_FONT": "C:\\Windows\\Fonts\\simhei.ttf",
        "AEC_REVIT_WAIT": "240"
      }
    }
  }
}
```

或一条命令：`claude mcp add aec -- <python.exe> -m aec_copilot.mcp_full`

## 三、Cursor

`~/.cursor/mcp.json`（或项目 `.cursor/mcp.json`）：

```json
{
  "mcpServers": {
    "aec": {
      "command": "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged\\.venv\\Scripts\\python.exe",
      "args": ["-m", "aec_copilot.mcp_full"],
      "cwd": "D:\\admin\\Documents\\deepseek-harness\\default-workspace\\aec-copilot-merged",
      "env": { "REPORTLAB_CJK_REGULAR_FONT": "C:\\Windows\\Fonts\\simhei.ttf", "AEC_REVIT_WAIT": "240" }
    }
  }
}
```

## 四、通用 / Cline / Windsurf / Continue

```json
{
  "mcpServers": {
    "aec": {
      "command": "python",
      "args": ["-m", "aec_copilot.mcp_full"],
      "cwd": "<克隆后的仓库路径>",
      "env": { "REPORTLAB_CJK_REGULAR_FONT": "C:\\Windows\\Fonts\\simhei.ttf", "AEC_REVIT_WAIT": "240" }
    }
  }
}
```

## 五、别人从 GitHub 克隆后的最简写法（跨机器可移植）

```json
{
  "mcpServers": {
    "aec": {
      "command": "uv",
      "args": ["run", "--project", "<克隆路径>", "python", "-m", "aec_copilot.mcp_full"],
      "cwd": "<克隆路径>",
      "env": { "REPORTLAB_CJK_REGULAR_FONT": "C:\\Windows\\Fonts\\simhei.ttf" }
    }
  }
}
```

---

## 提供的 13 个工具

`aec_health` · `aec_preview` · `aec_run` · `aec_audit` · `aec_recent_runs` ·
`revit_execute_plan` · `revit_new_project` · `revit_drawings` · `aec_export` ·
`aec_import_drawing` · `aec_review_image` · `aec_quantity` · `aec_cost_estimate`

## 与 Skill 的区别（一句话）

- **MCP**：工具在服务端真实执行，agent 通过协议调用 → 能建模、能出图、能算量。**首选。**
- **Skill**：只是给模型读的说明书 + 脚本约定，模型自己决定怎么调 → 适合没有 MCP 能力或不希望常驻进程的 agent。见 `skill/aec-copilot/SKILL.md`。
