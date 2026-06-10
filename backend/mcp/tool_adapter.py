"""Адаптер MCP tools → OpenAI function calling format (для McpAgentLoop, M3)."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.mcp.types import McpToolInfo


def to_openai_tools(tools: List[McpToolInfo]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.qualified_name,
                "description": tool.description or tool.name,
                "parameters": tool.parameters or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def qualify_tool_name(server_id: str, tool_name: str, prefix: str = "") -> str:
    base = f"{prefix}{tool_name}" if prefix else tool_name
    if base.startswith(f"{server_id}_") or base.startswith(f"mcp_{server_id}_"):
        return base
    if prefix:
        return base
    return f"mcp_{server_id}_{tool_name}"
