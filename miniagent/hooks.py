"""Hooks: shell commands fired on agent lifecycle events.

Events: SessionStart, TaskStart, PreToolUse, PostToolUse, TaskEnd, SessionEnd.
Each hook command receives the event payload as JSON on stdin and sees
MINIAGENT_EVENT / MINIAGENT_WORKDIR in the environment.
Exit 0 = allow. Exit code 2 on PreToolUse = block the tool call
(stderr becomes the reason). A hook may print JSON to stdout to patch the
payload, e.g. {"tool_input": {...}} to rewrite tool arguments.
"""
import json
import os
import subprocess

EVENTS = ("SessionStart", "TaskStart", "PreToolUse",
          "PostToolUse", "TaskEnd", "SessionEnd")

BLOCK_EXIT = 2


class HookResult:
    def __init__(self, allowed=True, patch=None, message=""):
        self.allowed = allowed
        self.patch = patch or {}
        self.message = message


class HookRunner:
    def __init__(self, hooks, workdir="."):
        self.hooks = hooks or {}
        self.workdir = workdir

    def fire(self, event, payload):
        """Run all hooks for event. Returns HookResult (blocked if any hook exits 2)."""
        result = HookResult()
        for cmd in self.hooks.get(event, []):
            r = self._run_one(cmd, event, payload)
            if r.patch:
                result.patch.update(r.patch)
                payload = {**payload, **r.patch}
            if not r.allowed:
                result.allowed = False
                result.message = r.message
                break  # first blocker wins
        return result

    def _run_one(self, cmd, event, payload):
        env = dict(os.environ, MINIAGENT_EVENT=event,
                   MINIAGENT_WORKDIR=os.path.abspath(self.workdir))
        try:
            p = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                input=json.dumps(payload), cwd=self.workdir,
                env=env, timeout=60,
            )
        except Exception as e:
            return HookResult(allowed=False, message=f"hook crashed: {e}")
        if p.returncode == BLOCK_EXIT:
            return HookResult(allowed=False,
                              message=(p.stderr or p.stdout).strip() or "blocked by hook")
        if p.returncode != 0:
            # non-blocking hook failure: surface as message, keep going
            return HookResult(message=f"hook warning: {(p.stderr or '').strip()}")
        patch = {}
        if p.stdout.strip():
            try:
                maybe = json.loads(p.stdout)
                if isinstance(maybe, dict):
                    patch = maybe
            except json.JSONDecodeError:
                pass
        return HookResult(patch=patch)
