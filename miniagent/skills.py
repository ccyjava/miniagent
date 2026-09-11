"""Skills: a skill is a folder with SKILL.md + an executable entrypoint.

SKILL.md frontmatter:
    ---
    name: my_skill            # tool name exposed to the model
    description: what it does
    parameters:               # optional JSON schema for arguments
      type: object
      properties: {...}
    run: ./run               # optional entrypoint, default ./run
    ---
    ...markdown docs for the model...

Tool call -> entrypoint runs with the arguments JSON on stdin,
cwd set to the skill folder. stdout is the tool result
(if stdout is JSON with an "output" key, that value is used).
"""
import json
import os
import subprocess

from .tools import Tool


def _frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta, doc = {}, text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            # tiny YAML-subset parser: flat key: value only, stdlib only
            for line in text[3:end].strip().splitlines():
                if ":" in line and not line.startswith((" ", "\t")):
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip("'\"")
            doc = text[end + 3:].strip()
    return meta, doc


def load_skills(skills_dir, timeout=120):
    tools = []
    if not skills_dir or not os.path.isdir(skills_dir):
        return tools
    for entry in sorted(os.listdir(skills_dir)):
        sdir = os.path.join(skills_dir, entry)
        md = os.path.join(sdir, "SKILL.md")
        if not os.path.isdir(sdir) or not os.path.isfile(md):
            continue
        meta, doc = _frontmatter(md)
        name = meta.get("name", entry)
        desc = meta.get("description", doc.splitlines()[0] if doc else name)
        if doc and doc not in desc:
            desc = f"{desc}\n\n{doc[:1500]}"
        params = {"type": "object", "properties": {},
                  "additionalProperties": True}
        entrypoint = meta.get("run", "./run")

        def make_run(sdir=sdir, entrypoint=entrypoint, timeout=timeout):
            def run(args):
                p = subprocess.run(
                    entrypoint, shell=True, capture_output=True, text=True,
                    input=json.dumps(args), cwd=sdir, timeout=timeout)
                out = (p.stdout or "").strip()
                if p.returncode != 0:
                    return f"[exit {p.returncode}] {out} {(p.stderr or '').strip()}".strip()
                try:
                    maybe = json.loads(out)
                    if isinstance(maybe, dict) and "output" in maybe:
                        return str(maybe["output"])
                except (json.JSONDecodeError, ValueError):
                    pass
                return out or "(no output)"
            return run

        tools.append(Tool(f"skill__{name}", desc, params, make_run()))
    return tools
