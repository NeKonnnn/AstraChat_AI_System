"""Интеграция MCP в chat pipeline (B-40)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from backend.context_prompts import merge_context_prompt_into_system
from backend.mcp.agent_loop import get_mcp_agent_loop
from backend.mcp.events import McpEventCallback
from backend.mcp.platform import get_mcp_platform
from backend.mcp.resolvers import build_chat_messages, parse_mcp_server_ids, resolve_chat_tool_ids
from backend.mcp.types import AgentLoopResult, McpCallContext
from backend.settings.logging import get_logger

log = get_logger(__name__)


async def _ensure_mcp_model_loaded(model_path: str) -> bool:
    """MCP FC требует готовую модель; иначе llm-svc отвечает 503 и чат падает в plain LLM."""
    from backend.llm_providers import get_registry

    registry = await get_registry()
    provider, model_id = registry.resolve(model_path)
    if not model_id:
        models = await provider.list_models()
        model_id = models[0].model_id if models else ""
    if not model_id:
        log.warning("MCP: не удалось определить model_id для %s", model_path)
        return False
    if not await provider.ensure_model_loaded(model_id):
        log.warning("MCP: модель %s недоступна на провайдере %s", model_id, provider.id)
        return False
    return True


def build_mcp_context_from_user(
    user: dict,
    *,
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> McpCallContext:
    return McpCallContext(
        user_id=str(user.get("user_id") or user.get("username") or ""),
        username=str(user.get("username") or ""),
        chat_id=chat_id,
        message_id=message_id,
        email=user.get("email"),
        is_admin=bool(user.get("is_admin")),
        groups=list(user.get("groups") or user.get("ldap_groups") or []),
        ldap_groups=list(user.get("ldap_groups") or user.get("groups") or []),
    )


async def maybe_run_mcp_agent(
    *,
    tool_ids: Optional[List[str]],
    user_message: str,
    history: Optional[List[Dict[str, Any]]],
    system_prompt: Optional[str],
    model_path: str,
    mcp_context: McpCallContext,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    enable_thinking: bool = False,
    event_callback: Optional[McpEventCallback] = None,
) -> Optional[AgentLoopResult]:
    platform = get_mcp_platform()
    if not platform.enabled or not platform.initialized:
        return None

    from backend.mcp.policy import is_mcp_provider_allowed

    if not is_mcp_provider_allowed(model_path):
        log.warning("MCP blocked: provider not in MCP_LLM_PROVIDER_ALLOWLIST model=%s", model_path)
        return None

    resolved_tool_ids = resolve_chat_tool_ids(tool_ids)
    if resolved_tool_ids and resolved_tool_ids != (tool_ids or []):
        log.info("MCP chat_default applied: %s", resolved_tool_ids)

    if not await _ensure_mcp_model_loaded(model_path):
        return None

    server_ids = parse_mcp_server_ids(resolved_tool_ids)
    if not server_ids:
        return None

    enabled_ids = platform.list_enabled_server_ids(server_ids)
    if not enabled_ids:
        return None

    all_tools = []
    for sid in enabled_ids:
        try:
            all_tools.extend(await platform.list_tools_for_server(sid, mcp_context))
        except Exception as exc:
            log.warning("MCP list_tools failed server=%s: %s", sid, exc)

    all_tools = platform.filter_tools_by_context(all_tools, mcp_context, enabled_server_ids=enabled_ids)
    if not all_tools:
        log.info("MCP enabled but no tools available for servers=%s", enabled_ids)
        return None

    messages = build_chat_messages(
        user_message=user_message,
        history=history,
        system_prompt=system_prompt,
    )
    request_extra = {"enable_thinking": enable_thinking} if enable_thinking else None
    loop = get_mcp_agent_loop()
    return await loop.run(
        messages=messages,
        model_path=model_path,
        mcp_tools=all_tools,
        mcp_context=mcp_context,
        enabled_server_ids=enabled_ids,
        temperature=temperature,
        max_tokens=max_tokens,
        request_extra=request_extra,
        event_callback=event_callback,
    )


async def run_mcp_for_chat(
    *,
    tool_ids: Optional[List[str]],
    user_message: str,
    history: Optional[List[Dict[str, Any]]],
    system_prompt: Optional[str],
    model_path: str,
    user: dict,
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    enable_thinking: bool = False,
    emit_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Optional[AgentLoopResult]:
    """
    Единая точка входа MCP для socket и REST chat (B-40).

    Multi-LLM: вызывается параллельно per-model с разным ``model_path``
    (CORSUR/… vs Phoenix/…). События ``chat_mcp_event`` — добавляйте
    ``model`` в ``emit_event`` callback на стороне handler.
    """
    mcp_ctx = build_mcp_context_from_user(user, chat_id=chat_id, message_id=message_id)
    eff_system_prompt = merge_context_prompt_into_system(system_prompt, model_path=model_path)
    return await maybe_run_mcp_agent(
        tool_ids=tool_ids,
        user_message=user_message,
        history=history,
        system_prompt=eff_system_prompt,
        model_path=model_path,
        mcp_context=mcp_ctx,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
        event_callback=emit_event,
    )
