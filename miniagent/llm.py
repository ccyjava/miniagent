"""LLM client: OpenAI-compatible /chat/completions via stdlib urllib.
Works with OpenAI, OpenRouter, DeepSeek, Ollama, vLLM, etc."""
import json
import time
import urllib.request


class LLMClient:
    def __init__(self, model, base_url, api_key, timeout=180):
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, messages, tools):
        """Returns the assistant message dict (may contain 'tool_calls')."""
        body = {
            "model": self.model,
            "messages": messages,
            "tools": tools or None,
            "tool_choice": "auto" if tools else "none",
        }
        data = json.dumps({k: v for k, v in body.items() if v is not None}).encode()
        req = urllib.request.Request(
            self.url, data=data,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        last_err = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.load(r)["choices"][0]["message"]
            except Exception as e:  # retry transient errors
                last_err = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM request failed after 3 attempts: {last_err}")


class MockLLM:
    """Scripted LLM for tests/demos: returns the queued messages in order."""

    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools):
        if self.script:
            return self.script.pop(0)
        return {"role": "assistant", "content": "Done."}


def tool_call(name, arguments, call_id="call_1"):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)},
        }],
    }
