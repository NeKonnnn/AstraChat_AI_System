"""Оценка сегментов контекста чата (системные промпты, RAG, MCP)."""

from __future__ import annotations

import json
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app_state import context_prompt_manager, model_settings, rag_system_prompt
from backend.realtime.helpers import _resolve_agent_chat_params
from backend.rag_query.prompts import merge_strict_rag_system_prompt

_MCP_TOKENS_CACHE: Dict[str, Tuple[int, float]] = {}
_MCP_CACHE_TTL_SEC = 120.0


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    base = math.ceil(len(text) / 4)
    special = len(re.findall(r"[^\w\sа-яё]", text, flags=re.IGNORECASE))
    newlines = text.count("\n")
    return base + math.ceil(special / 2) + math.ceil(newlines / 2)


def _resolve_max_context_tokens() -> int:
    configured = None
    if model_settings:
        try:
            configured = int(model_settings.get("context_size") or 0) or None
        except (TypeError, ValueError):
            configured = None
    return configured or 8192


async def _estimate_mcp_tools_tokens(tool_ids: Optional[List[str]], user: Optional[dict]) -> int:
    if not tool_ids or not user:
        return 0

    cache_key = "|".join(sorted(str(t) for t in tool_ids))
    cached = _MCP_TOKENS_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and (now - cached[1]) < _MCP_CACHE_TTL_SEC:
        return cached[0]

    try:
        from backend.mcp.chat_integration import build_mcp_context_from_user
        from backend.mcp.platform import get_mcp_platform
        from backend.mcp.prompt_fc_handler import _render_tools_prompt
        from backend.mcp.resolvers import parse_mcp_server_ids
    except ImportError:
        return 0

    platform = get_mcp_platform()
    if not platform.enabled or not platform.initialized:
        return 0

    mcp_ctx = build_mcp_context_from_user(user)
    server_ids = parse_mcp_server_ids(tool_ids)
    if not server_ids:
        return 0

    all_tools = []
    for sid in server_ids:
        try:
            specs = await platform.list_tools_for_server(sid, mcp_ctx)
            all_tools.extend(specs)
        except Exception:
            continue
    all_tools = platform.filter_tools_by_context(all_tools, mcp_ctx, enabled_server_ids=server_ids)
    if not all_tools:
        _MCP_TOKENS_CACHE[cache_key] = (0, now)
        return 0

    try:
        prompt_text = _render_tools_prompt(all_tools)
    except Exception:
        payload = json.dumps(
            [
                {
                    "name": t.qualified_name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in all_tools
            ],
            ensure_ascii=False,
        )
        prompt_text = payload
    tokens = estimate_tokens(prompt_text)
    _MCP_TOKENS_CACHE[cache_key] = (tokens, now)
    return tokens


async def build_context_overhead(
    *,
    model_path: Optional[str] = None,
    project_instructions: Optional[str] = None,
    agent_id: Optional[int] = None,
    use_kb_rag: bool = False,
    tool_ids: Optional[List[str]] = None,
    user: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Сегменты «скрытого» контекста, как в realtime/handlers.py (без истории и черновика).
    """
    segments: List[Dict[str, Any]] = []

    agent_profile = await _resolve_agent_chat_params(agent_id)
    agent_prompt = (agent_profile.get("system_prompt") or "").strip()
    project_text = (project_instructions or "").strip()

    if project_text:
        segments.append(
            {
                "id": "project",
                "label": "Проект",
                "tokens": estimate_tokens(project_text),
                "active": True,
            }
        )

    if agent_prompt:
        segments.append(
            {
                "id": "agent",
                "label": "Агент",
                "tokens": estimate_tokens(agent_prompt),
                "active": True,
            }
        )

    context_eff = ""
    if context_prompt_manager and model_path:
        try:
            context_eff = (context_prompt_manager.get_effective_prompt(model_path) or "").strip()
        except Exception:
            context_eff = ""
    elif context_prompt_manager:
        try:
            context_eff = (context_prompt_manager.get_global_prompt() or "").strip()
        except Exception:
            context_eff = ""

    if context_eff:
        segments.append(
            {
                "id": "context_instructions",
                "label": "Системный промпт",
                "tokens": estimate_tokens(context_eff),
                "active": not agent_prompt,
            }
        )

    if use_kb_rag:
        rag_block = merge_strict_rag_system_prompt("", rag_override=rag_system_prompt)
        segments.append(
            {
                "id": "rag_rules",
                "label": "RAG (правила)",
                "tokens": estimate_tokens(rag_block),
                "active": True,
            }
        )

    mcp_tokens = await _estimate_mcp_tools_tokens(tool_ids, user)
    if mcp_tokens > 0:
        segments.append(
            {
                "id": "mcp_tools",
                "label": "MCP (инструменты)",
                "tokens": mcp_tokens,
                "active": True,
            }
        )

    overhead_active = sum(s["tokens"] for s in segments if s.get("active", True))
    overhead_all = sum(s["tokens"] for s in segments)

    return {
        "max_tokens": _resolve_max_context_tokens(),
        "segments": segments,
        "overhead_tokens_active": overhead_active,
        "overhead_tokens_configured": overhead_all,
    }
