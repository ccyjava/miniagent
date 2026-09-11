"""miniagent CLI."""
import argparse
import os
import sys

from .agent import Agent
from .config import load as load_config
from .daemon import serve
from .hooks import HookRunner
from .llm import LLMClient
from .mcp_bridge import load_mcp_tools
from .skills import load_skills
from .tools import builtins


def build_agent(cfg, llm=None, verbose=True):
    hooks = HookRunner(cfg["hooks"], workdir=cfg["workdir"])
    tools = builtins(cfg["workdir"], cfg["tool_timeout"])
    tools += load_skills(cfg["skills_dir"], cfg["tool_timeout"])
    tools += load_mcp_tools(cfg["mcp_servers"], cfg["tool_timeout"])
    if llm is None:
        if not cfg["api_key"]:
            sys.exit("No API key: set 'api_key' in config or "
                     f"{cfg['api_key_env']} in the environment.")
        llm = LLMClient(cfg["model"], cfg["base_url"], cfg["api_key"])
    return Agent(llm, tools, hooks, cfg["system_prompt"],
                 max_steps=cfg["max_steps"], verbose=verbose), hooks


def cmd_init(args):
    root = os.path.abspath(args.init)
    os.makedirs(os.path.join(root, "skills", "hello"), exist_ok=True)
    os.makedirs(os.path.join(root, "hooks"), exist_ok=True)
    os.makedirs(os.path.join(root, "tasks"), exist_ok=True)

    import json
    cfg = {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "skills_dir": "skills",
        "tasks_dir": "tasks",
        "workdir": ".",
        "max_steps": 30,
        "hooks": {
            "PreToolUse": ["./hooks/log.sh"],
            "PostToolUse": ["./hooks/log.sh"],
        },
        "mcp_servers": [
            # {"name": "fs", "command": "npx",
            #  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]}
        ],
    }
    with open(os.path.join(root, "miniagent.json"), "w") as f:
        json.dump(cfg, f, indent=2)

    with open(os.path.join(root, "skills", "hello", "SKILL.md"), "w") as f:
        f.write("---\nname: hello\ndescription: Greet someone by name.\n"
                "run: ./run\n---\n\nReplies with a friendly greeting.\n")
    run = os.path.join(root, "skills", "hello", "run")
    with open(run, "w") as f:
        f.write('#!/usr/bin/env python3\nimport json, sys\n'
                'args = json.load(sys.stdin)\n'
                'print(f"Hello, {args.get(\'name\', \'world\')}!")\n')
    os.chmod(run, 0o755)

    log = os.path.join(root, "hooks", "log.sh")
    with open(log, "w") as f:
        f.write('#!/bin/sh\n# Logs every tool call; exit 2 to block.\n'
                'echo "[$MINIAGENT_EVENT] $(cat)" >> hooks/events.log\n')
    os.chmod(log, 0o755)

    with open(os.path.join(root, "tasks", "example.task"), "w") as f:
        f.write("Use the hello skill to greet Ada, then write the greeting to greeting.txt.\n")

    print(f"Initialized miniagent project at {root}")
    print("  1. export OPENAI_API_KEY=... (or edit miniagent.json)")
    print("  2. python -m miniagent --config miniagent.json 'your task'")
    print("  3. python -m miniagent --config miniagent.json --daemon")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="miniagent",
                                 description="Minimal agent: tools, skills, MCP, hooks, never stops.")
    ap.add_argument("--config", default="miniagent.json")
    ap.add_argument("--daemon", action="store_true",
                    help="run forever, executing tasks dropped into tasks_dir")
    ap.add_argument("--init", metavar="DIR",
                    help="scaffold an example project and exit")
    ap.add_argument("task", nargs="?", help="task to run once")
    args = ap.parse_args(argv)

    if args.init:
        return cmd_init(args)

    cfg = load_config(args.config if os.path.exists(args.config) else None)
    agent, hooks = build_agent(cfg)
    if args.daemon:
        serve(lambda: agent, cfg["tasks_dir"],
              poll=cfg["daemon_poll"], hooks=hooks)
    elif args.task:
        hooks.fire("SessionStart", {"mode": "once"})
        try:
            print(agent.run(args.task))
        finally:
            hooks.fire("SessionEnd", {"mode": "once"})
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
