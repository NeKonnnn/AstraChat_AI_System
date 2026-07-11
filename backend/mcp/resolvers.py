"""Хелперы разбора tool_ids и сборки сообщений для MCP agent loop."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def mcp_server_tool_id(server_id: str) -> str:
    return f"server:mcp:{server_id}"


def resolve_chat_tool_ids(payload_tool_ids: Optional[List[str]] = None) -> List[str]:
    """
    Явные tool_ids с клиента + fallback на ``mcp.chat_default`` из config.

    ``chat_default``: ``none`` | ``all`` | ``websearch`` | ``id1,id2``
    """
    explicit: List[str] = []
    for raw in payload_tool_ids or []:
        tid = str(raw or "").strip()
        if tid:
            explicit.append(tid)
    if explicit:
        return explicit

    from backend.settings.config import get_settings

    default_raw = (get_settings().mcp.chat_default or "none").strip().lower()
    if not default_raw or default_raw == "none":
        return []

    if default_raw == "all":
        server_ids = [
            str(s.id).strip()
            for s in (get_settings().mcp.servers or [])
            if getattr(s, "enabled", False) and str(getattr(s, "id", "")).strip()
        ]
    else:
        server_ids = [p.strip() for p in default_raw.replace(",", " ").split() if p.strip()]

    return [mcp_server_tool_id(sid) for sid in server_ids if sid]


def parse_mcp_server_ids(tool_ids: Optional[List[str]]) -> List[str]:
    """OWUI-compatible: ``server:mcp:{id}`` | ``mcp:{id}`` | plain ``{id}``."""
    result: List[str] = []
    for raw in tool_ids or []:
        tid = str(raw or "").strip()
        if not tid:
            continue
        if tid.startswith("server:mcp:"):
            sid = tid.split(":", 2)[2].strip()
        elif tid.startswith("mcp:"):
            sid = tid.split(":", 1)[1].strip()
        else:
            sid = tid
        if sid and sid not in result:
            result.append(sid)
    return result


def build_chat_messages(
    *,
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if system_prompt and str(system_prompt).strip():
        messages.append({"role": "system", "content": str(system_prompt).strip()})
    for entry in history or []:
        role = str(entry.get("role") or "").strip()
        content = entry.get("content")
        if role in ("user", "assistant", "system") and content is not None:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages
