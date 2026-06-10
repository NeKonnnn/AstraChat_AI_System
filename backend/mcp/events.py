"""MCP streaming events для Socket.IO (B-22)."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict, Optional

McpEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


async def emit_mcp_tool_start(
    callback: Optional[McpEventCallback],
    *,
    server_id: str,
    tool: str,
    qualified_name: str,
) -> None:
    if not callback:
        return
    await callback(
        {
            "type": "mcp_tool_start",
            "server_id": server_id,
            "tool": tool,
            "qualified_name": qualified_name,
            "timestamp": time.time(),
        }
    )


async def emit_mcp_tool_end(
    callback: Optional[McpEventCallback],
    *,
    server_id: str,
    tool: str,
    qualified_name: str,
    success: bool,
    duration_ms: int,
    error: Optional[str] = None,
    result_preview: Optional[str] = None,
    has_image: bool = False,
    has_audio: bool = False,
    has_resource: bool = False,
) -> None:
    if not callback:
        return
    payload: Dict[str, Any] = {
        "type": "mcp_tool_end",
        "server_id": server_id,
        "tool": tool,
        "qualified_name": qualified_name,
        "success": success,
        "duration_ms": duration_ms,
        "timestamp": time.time(),
    }
    if error:
        payload["error"] = error
    if result_preview:
        payload["result_preview"] = result_preview
    if has_image:
        payload["has_image"] = True
    if has_audio:
        payload["has_audio"] = True
    if has_resource:
        payload["has_resource"] = True
    await callback(payload)
