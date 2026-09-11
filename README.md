# miniagent

最轻量的 agent 系统：**一个循环 + 工具调用 + 永不停止**。

```
task → [ model → tool → model → tool → … ] → done → 下一个 task → …
```

支持 **tool**（内置 shell/read/write/fetch）、**skill**（`SKILL.md` + 可执行脚本）、
**MCP**（stdio server 桥接）、**hook**（生命周期事件触发 shell 命令）。
**零第三方依赖**（标准库 only；MCP 可选 `pip install mcp`）。

## 快速开始

```bash
python -m miniagent --init mybot   # 生成示例项目
cd mybot
export OPENAI_API_KEY=sk-...       # 或任何 OpenAI 兼容 endpoint
python -m miniagent --config miniagent.json "用 hello skill 问候 Ada，并把结果写入 greeting.txt"
```

## 永不停止：daemon 模式

```bash
python -m miniagent --config miniagent.json --daemon
```

daemon 死循环监听 `tasks/` 目录：丢一个 `xxx.task` 文件进去（纯文本即任务），
agent 自动执行，结果追加后移到 `tasks/done/xxx.task.done`。单个任务抛异常
也不会杀死 daemon——它永远运行。

## 结构

```
miniagent/
  agent.py       # 核心循环：prompt → tool_calls → 执行 → 回填 → …
  llm.py         # OpenAI 兼容 /chat/completions 客户端（urllib）
  tools.py       # Tool 抽象 + 内置工具：shell / read / write / fetch
  skills.py      # skill 加载器：SKILL.md frontmatter + 可执行 run
  mcp_bridge.py  # MCP stdio server → mcp__<server>__<tool>
  hooks.py       # 事件钩子：shell 命令，stdin 收 JSON，可拦截/改写
  daemon.py      # 永不停止的任务队列模式
  __main__.py    # CLI
```

## Skill

一个文件夹 = 一个 skill：

```
skills/upper/
  SKILL.md      # frontmatter: name / description / run
  run           # 可执行文件，stdin 收 JSON 参数，stdout 即结果
```

SKILL.md 示例：

```markdown
---
name: upper
description: 把文本转成大写
run: ./run
---

（给模型的补充说明…）
```

调用时在模型侧显示为 `skill__upper` 工具。

## MCP

`miniagent.json` 里加：

```json
"mcp_servers": [
  {"name": "fs", "command": "npx",
   "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]}
]
```

需要 `pip install mcp`。远程工具自动变成 `mcp__fs__read_file` 等。

## Hook

事件：`SessionStart` `TaskStart` `PreToolUse` `PostToolUse` `TaskEnd` `SessionEnd`。

```json
"hooks": {
  "PreToolUse": ["./hooks/guard.sh"]
}
```

每个 hook 是 shell 命令：stdin 收到事件 JSON，环境变量有
`MINIAGENT_EVENT`。约定：

- exit 0 → 放行；stdout 若为 JSON 会被合并为 patch（如 `{"tool_input": {...}}` 改写参数）
- exit 2（仅 `PreToolUse`）→ 拦截工具调用，stderr 作为原因返回给模型
- 其他非零 → 警告但继续

示例 `hooks/guard.sh`：拦截含 `rm -rf /` 的 shell 调用。

## 配置

`miniagent.json`（`--init` 会生成）：model / base_url / api_key(_env) /
system_prompt / skills_dir / tasks_dir / workdir / max_steps /
daemon_poll / tool_timeout / hooks / mcp_servers。

任何 OpenAI 兼容的 endpoint 都能用：OpenAI、OpenRouter、DeepSeek、
本地 Ollama / vLLM，只需改 `base_url` + `model`。

## 测试

```bash
python tests/test_miniagent.py
```

用 scripted MockLLM 跑通：工具循环写文件、skill 加载执行、
hook 拦截危险调用、hook 改写参数、max_steps 熔断。
