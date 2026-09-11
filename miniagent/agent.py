"""The loop: prompt -> model -> tools -> model -> ... until done."""
import json


class Agent:
    def __init__(self, llm, tools, hooks, system_prompt,
                 max_steps=30, verbose=True):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.tool_schemas = [t.schema() for t in tools]
        self.hooks = hooks
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.verbose = verbose

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    def run(self, task):
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]
        self.hooks.fire("TaskStart", {"task": task})
        final = ""
        try:
            for step in range(1, self.max_steps + 1):
                msg = self.llm.chat(messages, self.tool_schemas)
                messages.append(_clean(msg))
                calls = msg.get("tool_calls") or []
                if not calls:
                    final = msg.get("content") or ""
                    self.log(f"[done] {final[:500]}")
                    break
                self.log(f"[step {step}] {len(calls)} tool call(s)")
                for call in calls:
                    messages.append(self._execute(call))
            else:
                final = f"Stopped after {self.max_steps} steps without finishing."
                self.log("[max_steps] " + final)
        finally:
            self.hooks.fire("TaskEnd", {"task": task, "result": final})
        return final

    def _execute(self, call):
        fn = call["function"]
        name, call_id = fn["name"], call["id"]
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        self.log(f"  -> {name} {json.dumps(args)[:200]}")

        pre = self.hooks.fire("PreToolUse",
                              {"tool": name, "tool_input": args})
        if not pre.allowed:
            self.log(f"  !! blocked by hook: {pre.message}")
            return {"role": "tool", "tool_call_id": call_id,
                    "content": f"BLOCKED by hook: {pre.message}"}
        if "tool_input" in pre.patch:
            args = pre.patch["tool_input"]

        tool = self.tools.get(name)
        result = (tool.run(args) if tool
                  else f"ERROR: unknown tool '{name}'")
        self.log(f"  <- {str(result)[:300]}")

        self.hooks.fire("PostToolUse",
                        {"tool": name, "tool_input": args,
                         "tool_output": str(result)[:4000]})
        return {"role": "tool", "tool_call_id": call_id,
                "content": str(result)}


def _clean(msg):
    """Keep only the fields the API needs for the next turn."""
    out = {"role": msg.get("role", "assistant"),
           "content": msg.get("content") or ""}
    if msg.get("tool_calls"):
        out["tool_calls"] = msg["tool_calls"]
    return out
