"""Config loading. JSON file, stdlib only, zero dependencies."""
import json
import os

DEFAULTS = {
    "model": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1",   # any OpenAI-compatible endpoint
    "api_key": "",                              # or set api_key_env
    "api_key_env": "OPENAI_API_KEY",
    "system_prompt": (
        "You are miniagent, a minimal autonomous agent. "
        "You solve the user's task by calling tools in a loop. "
        "Think step by step, call one or more tools per turn, "
        "and when the task is fully done, reply with a concise summary and stop calling tools."
    ),
    "skills_dir": "skills",
    "mcp_servers": [],        # [{"name": "...", "command": "npx", "args": [...], "env": {}}]
    "hooks": {},              # {"PreToolUse": ["./hooks/log.sh"], ...}
    "workdir": ".",
    "max_steps": 30,          # per-task safety cap; the daemon itself never stops
    "daemon_poll": 5,         # seconds between task-queue scans
    "tasks_dir": "tasks",
    "tool_timeout": 120,
}


def load(path):
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    if not cfg["api_key"] and cfg.get("api_key_env"):
        cfg["api_key"] = os.environ.get(cfg["api_key_env"], "")
    # resolve relative dirs against the config file location
    base = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()
    for key in ("skills_dir", "tasks_dir", "workdir"):
        if not os.path.isabs(cfg[key]):
            cfg[key] = os.path.join(base, cfg[key])
    return cfg
