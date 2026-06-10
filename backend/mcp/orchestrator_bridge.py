"""Мост LangGraph orchestrator ↔ MCP platform / ProviderRegistry (B-27)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Callable, Dict, List, Optional

from backend.llm_providers.routing import build_chat_messages

log = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def sync_chat_via_registry(
    prompt: str,
    *,
    history: Optional[List[Dict[str, Any]]] = None,
    model_path: Optional[str] = None,
    streaming: bool = False,
    stream_callback: Optional[Callable] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    system_prompt: Optional[str] = None,
    enable_thinking: bool = False,
) -> Optional[str]:
    """Синхронный LLM-вызов через ProviderRegistry (planner / aggregator)."""

    async def _call():
        from backend.llm_providers import get_registry

        try:
            from backend.app_state import get_current_model_path
        except Exception:
            get_current_model_path = lambda: None  # type: ignore

        registry = await get_registry()
        effective_path = (model_path or get_current_model_path() or "").strip()
        provider, model_id = registry.resolve(effective_path)
        if not model_id:
            models = await provider.list_models()
            model_id = models[0].model_id if models else ""
        if not model_id:
            return None

        messages = build_chat_messages(prompt, history=history, system_prompt=system_prompt)

        req_extra = {"enable_thinking": enable_thinking} if enable_thinking else None

        if streaming and stream_callback:
            acc = ""
            async for chunk in provider.stream_chat(
                messages,
                model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                request_extra=req_extra,
            ):
                if chunk:
                    acc += chunk
                    cont = stream_callback(chunk, acc, "content")
                    if cont is False:
                        return acc or None
            return acc or None

        return await provider.chat(
            messages,
            model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            request_extra=req_extra,
        )

    try:
        return _run_async(_call())
    except Exception as exc:
        log.error("sync_chat_via_registry failed: %s", exc, exc_info=True)
        return None


async def attach_mcp_tools_to_orchestrator(orchestrator, context: Dict[str, Any]) -> int:
    """Подключает MCP tools из tool_ids к orchestrator (tier-3, generic)."""
    from backend.mcp.langgraph_tools import load_mcp_langgraph_tools
    from backend.mcp.resolvers import parse_mcp_server_ids

    tool_ids = context.get("tool_ids") or context.get("mcp_tool_ids") or []
    server_ids = parse_mcp_server_ids(tool_ids if isinstance(tool_ids, list) else [tool_ids])
    if not server_ids:
        return 0

    dynamic: set = getattr(orchestrator, "_dynamic_mcp_tool_names", set())
    for name in list(dynamic):
        orchestrator.tools_by_name.pop(name, None)
        orchestrator.tool_status.pop(name, None)
    orchestrator.tools = [t for t in orchestrator.tools if t.name not in dynamic]
    dynamic.clear()

    mcp_tools = await load_mcp_langgraph_tools(server_ids=server_ids, context=context)
    for tool in mcp_tools:
        name = tool.name
        orchestrator.tools.append(tool)
        orchestrator.tools_by_name[name] = tool
        orchestrator.tool_status[name] = True
        dynamic.add(name)

    orchestrator._dynamic_mcp_tool_names = dynamic
    if mcp_tools:
        log.info("Orchestrator: attached %s MCP tools from servers=%s", len(mcp_tools), server_ids)
    return len(mcp_tools)
