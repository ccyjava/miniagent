"""MCP bridge: expose tools from MCP stdio servers as agent tools.

Requires the optional `mcp` package (pip install mcp). If it is missing,
this module degrades gracefully to zero tools with a warning.
Each remote tool becomes `mcp__<server>__<tool>`.
"""
import asyncio
import json

from .tools import Tool


def load_mcp_tools(servers, timeout=120):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        if servers:
            print("[miniagent] 'mcp' package not installed; "
                  "skipping MCP servers (pip install mcp to enable)")
        return []

    tools = []
    for srv in servers or []:
        name = srv["name"]
        params = StdioServerParameters(
            command=srv["command"], args=srv.get("args", []),
            env=srv.get("env"))

        async def _list():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as s:
                    await s.initialize()
                    return (await s.list_tools()).tools

        try:
            remote = asyncio.run(_list())
        except Exception as e:
            print(f"[miniagent] MCP server '{name}' failed: {e}")
            continue

        for t in remote:
            schema = t.inputSchema or {"type": "object", "properties": {}}

            def make_call(srv_name=name, tool_name=t.name,
                          params=params, timeout=timeout):
                def call(args):
                    async def _call():
                        async with stdio_client(params) as (read, write):
                            async with ClientSession(read, write) as s:
                                await s.initialize()
                                return await s.call_tool(tool_name, args)
                    res = asyncio.run(_call())
                    parts = []
                    for c in res.content or []:
                        parts.append(getattr(c, "text", json.dumps(
                            c.model_dump() if hasattr(c, "model_dump") else str(c))))
                    return "\n".join(parts) or "(no output)"
                return call

            tools.append(Tool(
                f"mcp__{name}__{t.name}",
                f"[MCP:{name}] {t.description or t.name}",
                schema, make_call()))
    return tools
