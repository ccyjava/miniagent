"""Tool abstraction + builtin tools. Every tool is: name, description,
JSON-schema parameters, and a callable(args) -> str."""
import json
import os
import subprocess
import urllib.request


class Tool:
    def __init__(self, name, description, parameters, func):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, args):
        try:
            out = self.func(args)
            return str(out)
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"


def _sh(args, workdir, timeout):
    p = subprocess.run(
        args["command"], shell=True, capture_output=True, text=True,
        cwd=workdir, timeout=timeout,
    )
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        out = f"[exit {p.returncode}] " + out
    return out.strip()[:20000] or "(no output)"


def builtins(workdir, timeout=120):
    os.makedirs(workdir, exist_ok=True)

    def read(args):
        path = os.path.join(workdir, args["path"])
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()[:20000]

    def write(args):
        path = os.path.join(workdir, args["path"])
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(args["content"])
        return f"wrote {len(args['content'])} chars to {args['path']}"

    def fetch(args):
        req = urllib.request.Request(
            args["url"], headers={"User-Agent": "miniagent/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")[:20000]

    obj = {"type": "object", "properties": {}, "required": []}
    return [
        Tool("shell",
             "Run a shell command in the workdir. Returns combined stdout/stderr.",
             {"type": "object",
              "properties": {"command": {"type": "string"}},
              "required": ["command"]},
             lambda a: _sh(a, workdir, timeout)),
        Tool("read",
             "Read a text file (path relative to workdir).",
             {"type": "object",
              "properties": {"path": {"type": "string"}},
              "required": ["path"]},
             read),
        Tool("write",
             "Write/create a text file (path relative to workdir).",
             {"type": "object",
              "properties": {"path": {"type": "string"},
                             "content": {"type": "string"}},
              "required": ["path", "content"]},
             write),
        Tool("fetch",
             "HTTP GET a URL, return text.",
             {"type": "object",
              "properties": {"url": {"type": "string"}},
              "required": ["url"]},
             fetch),
    ]
