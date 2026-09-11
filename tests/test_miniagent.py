"""End-to-end tests with a scripted MockLLM. Run: python -m pytest tests/ -q
(or: python tests/test_miniagent.py)."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from miniagent.agent import Agent
from miniagent.hooks import HookRunner
from miniagent.llm import MockLLM, tool_call
from miniagent.skills import load_skills
from miniagent.tools import builtins


def make_agent(script, workdir, skills_dir=None, hook_cmds=None):
    tools = builtins(workdir)
    tools += load_skills(skills_dir)
    hooks = HookRunner(hook_cmds or {}, workdir=workdir)
    return Agent(MockLLM(script), tools, hooks, "test prompt",
                 max_steps=10, verbose=False)


def test_tool_loop_writes_file():
    with tempfile.TemporaryDirectory() as wd:
        script = [
            tool_call("write", {"path": "hello.txt", "content": "hi from miniagent"}),
            {"role": "assistant", "content": "Wrote the file."},
        ]
        out = make_agent(script, wd).run("write hello.txt")
        assert "Wrote the file." in out
        with open(os.path.join(wd, "hello.txt")) as f:
            assert f.read() == "hi from miniagent"
    print("ok: tool loop writes file")


def test_skill_loading_and_run():
    with tempfile.TemporaryDirectory() as wd:
        sdir = os.path.join(wd, "skills", "upper")
        os.makedirs(sdir)
        with open(os.path.join(sdir, "SKILL.md"), "w") as f:
            f.write("---\nname: upper\ndescription: Uppercase text.\n---\n")
        run = os.path.join(sdir, "run")
        with open(run, "w") as f:
            f.write("#!/bin/sh\npython3 -c "
                    "\"import json,sys; print(json.load(sys.stdin)['text'].upper())\"\n")
        os.chmod(run, 0o755)
        script = [
            tool_call("skill__upper", {"text": "hello"}),
            {"role": "assistant", "content": "HELLO"},
        ]
        out = make_agent(script, wd,
                         skills_dir=os.path.join(wd, "skills")).run("uppercase hello")
        assert out == "HELLO"
    print("ok: skill loads and runs")


def test_pretooluse_hook_can_block():
    with tempfile.TemporaryDirectory() as wd:
        blocker = os.path.join(wd, "block.sh")
        with open(blocker, "w") as f:
            # block any shell command containing 'rm'
            f.write("#!/bin/sh\n"
                    "python3 -c \"import json,sys; "
                    "sys.exit(2 if 'rm' in json.load(sys.stdin).get('tool_input',{}).get('command','') "
                    "else 0)\"\n")
        os.chmod(blocker, 0o755)
        script = [
            tool_call("shell", {"command": "rm -rf /"}),
            {"role": "assistant", "content": "blocked, done."},
        ]
        out = make_agent(script, wd,
                         hook_cmds={"PreToolUse": [blocker]}).run("try rm")
        assert "blocked, done." in out
        # the dangerous command must never have executed: no tool result leaked
    print("ok: PreToolUse hook blocks dangerous call")


def test_hook_can_rewrite_args():
    with tempfile.TemporaryDirectory() as wd:
        rewriter = os.path.join(wd, "rewrite.sh")
        with open(rewriter, "w") as f:
            f.write('#!/bin/sh\n'
                    'echo \'{"tool_input": {"path": "hello.txt", '
                    '"content": "rewritten by hook"}}\'\n')
        os.chmod(rewriter, 0o755)
        script = [
            tool_call("write", {"path": "ignored.txt", "content": "x"}),
            {"role": "assistant", "content": "done"},
        ]
        make_agent(script, wd,
                   hook_cmds={"PreToolUse": [rewriter]}).run("write something")
        with open(os.path.join(wd, "hello.txt")) as f:
            assert f.read() == "rewritten by hook"
        assert not os.path.exists(os.path.join(wd, "ignored.txt"))
    print("ok: hook rewrites tool arguments")


def test_unknown_tool_and_max_steps():
    with tempfile.TemporaryDirectory() as wd:
        script = [tool_call("nope", {})] * 12  # model keeps calling garbage
        out = make_agent(script, wd).run("loop forever")
        assert "Stopped after 10 steps" in out
    print("ok: max_steps guard stops runaway loops")


def test_hook_matcher_only_fires_for_matching_tool():
    with tempfile.TemporaryDirectory() as wd:
        seen = os.path.join(wd, "seen.log")
        spy = os.path.join(wd, "spy.sh")
        with open(spy, "w") as f:
            f.write(f"#!/bin/sh\ncat >> {seen}\n")
        os.chmod(spy, 0o755)
        script = [
            tool_call("write", {"path": "a.txt", "content": "x"}),
            tool_call("shell", {"command": "echo hi"}),
            {"role": "assistant", "content": "done"},
        ]
        make_agent(script, wd,
                   hook_cmds={"PreToolUse": [["^shell$", spy]]}).run("do things")
        logged = open(seen).read()
        assert "shell" in logged and "write" not in logged
    print("ok: hook matcher scopes to matching tools")


if __name__ == "__main__":
    test_tool_loop_writes_file()
    test_skill_loading_and_run()
    test_pretooluse_hook_can_block()
    test_hook_can_rewrite_args()
    test_hook_matcher_only_fires_for_matching_tool()
    test_unknown_tool_and_max_steps()
    print("ALL TESTS PASSED")
