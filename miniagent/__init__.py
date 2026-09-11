"""miniagent: the most minimal agent system.

Tool-calling loop + skills + MCP + hooks + never-stopping daemon.
Zero third-party dependencies (MCP support needs `pip install mcp`).
"""
from .agent import Agent

__version__ = "0.1.0"
__all__ = ["Agent"]
