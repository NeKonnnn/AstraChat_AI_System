"""MCP agent loop — provider-agnostic фасад (B-24, B-32)."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend.llm_providers import get_registry
from backend.llm_providers.base import ToolCall  # noqa: F401 — re-exported via agent_loop consumers
from backend.mcp.connection import McpServerSession
from backend.mcp.platform import McpPlatformService, get_mcp_platform
from backend.mcp.prompt_fc_handler import run_prompt_json_fc
from backend.mcp.result_parser import format_parsed_for_llm, parse_mcp_result_to_struct, preview_parsed_for_ui
from backend.mcp.tool_adapter import to_openai_tools
from backend.mcp.tool_calling import resolve_tool_calling_mode
from backend.mcp.types import AgentLoopResult, McpCallContext, McpToolInfo
from backend.mcp.events import McpEventCallback, emit_mcp_tool_end, emit_mcp_tool_start
from backend.settings.config import get_settings
from backend.settings.cef_logger.cef_logger import log_cef_event
from backend.settings.logging import get_logger

log = get_logger(__name__)

_agent_loop: Optional["McpAgentLoop"] = None


def _find_tool(name: str, tools: List[McpToolInfo]) -> Optional[McpToolInfo]:
    for tool in tools:
        if tool.qualified_name == name or tool.name == name:
            return tool
    return None


class McpAgentLoop:
    def __init__(self, platform: Optional[McpPlatformService] = None):
        self._platform = platform or get_mcp_platform()

    async def run(
        self,
        *,
        messages: List[Dict[str, Any]],
        model_path: str,
        mcp_tools: List[McpToolInfo],
        mcp_context: McpCallContext,
        enabled_server_ids: List[str],
        max_iterations: int = 10,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        request_extra: Optional[Dict[str, Any]] = None,
        event_callback: Optional[McpEventCallback] = None,
    ) -> AgentLoopResult:
        if not mcp_tools:
            registry = await get_registry()
            provider, model_id = registry.resolve(model_path)
            if not model_id:
                models = await provider.list_models()
                model_id = models[0].model_id if models else ""
            content = await provider.chat(
                messages,
                model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                request_extra=request_extra,
            )
            return AgentLoopResult(content=content or "", mode="plain")

        async with self._platform.request_sessions(enabled_server_ids, mcp_context) as sessions:
            registry = await get_registry()
            provider, model_id = registry.resolve(model_path)
            if not model_id:
                models = await provider.list_models()
                model_id = models[0].model_id if models else ""
            mode = resolve_tool_calling_mode(provider)
            fc_model = (get_settings().mcp.fc_task_model or "").strip() or None
            if mode == "prompt_json_fc":
                return await run_prompt_json_fc(
                    messages=messages,
                    model_path=model_path,
                    tools=mcp_tools,
                    context=mcp_context,
                    platform=self._platform,
                    sessions=sessions,
                    fc_model_path=fc_model,
                    max_iterations=min(3, max_iterations),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request_extra=request_extra,
                    event_callback=event_callback,
                )
            return await self._run_native(
                messages=messages,
                provider=provider,
                model_id=model_id,
                tools=mcp_tools,
                context=mcp_context,
                sessions=sessions,
                max_iterations=max_iterations,
                temperature=temperature,
                max_tokens=max_tokens,
                request_extra=request_extra,
                event_callback=event_callback,
            )

    async def _run_native(
        self,
        *,
        messages: List[Dict[str, Any]],
        provider,
        model_id: str,
        tools: List[McpToolInfo],
        context: McpCallContext,
        sessions: Dict[str, McpServerSession],
        max_iterations: int,
        temperature: float,
        max_tokens: int,
        request_extra: Optional[Dict[str, Any]],
        event_callback: Optional[McpEventCallback] = None,
    ) -> AgentLoopResult:
        openai_tools = to_openai_tools(tools)
        working = list(messages)
        tool_calls_executed = 0
        req_extra = dict(request_extra or {})

        for iteration in range(max(1, max_iterations)):
            try:
                result = await provider.chat_completion(
                    working,
                    model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=openai_tools,
                    request_extra=req_extra,
                )
            except Exception as exc:
                log.warning("Native MCP FC failed, fallback prompt_json_fc: %s", exc)
                return await run_prompt_json_fc(
                    messages=messages,
                    model_path=f"{provider.id}/{model_id}",
                    tools=tools,
                    context=context,
                    platform=self._platform,
                    sessions=sessions,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request_extra=request_extra,
                    event_callback=event_callback,
                )

            if not result.tool_calls:
                return AgentLoopResult(
                    content=result.content or "",
                    tool_calls_executed=tool_calls_executed,
                    mode="native_openai_tools",
                    iterations=iteration + 1,
                )

            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": __import__("json").dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in result.tool_calls
                ],
            }
            working.append(assistant_msg)

            for tc in result.tool_calls:
                tool_info = _find_tool(tc.name, tools)
                if not tool_info:
                    working.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"Unknown tool: {tc.name}",
                        }
                    )
                    continue
                session = sessions.get(tool_info.server_id)
                if not session:
                    working.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"MCP session unavailable: {tool_info.server_id}",
                        }
                    )
                    continue
                started = time.perf_counter()
                await emit_mcp_tool_start(
                    event_callback,
                    server_id=tool_info.server_id,
                    tool=tool_info.name,
                    qualified_name=tool_info.qualified_name,
                )
                log_cef_event(
                    "INT001",
                    extra={
                        "cs1": tool_info.qualified_name,
                        "cs1Label": "ToolName",
                        "cs2": context.chat_id or "-",
                        "cs2Label": "ChatId",
                        "cs3": tool_info.server_id,
                        "cs3Label": "McpServer",
                        "duser": context.username,
                    },
                )
                try:
                    raw = await self._platform.call_tool(
                        tool_info.server_id,
                        tool_info.name,
                        tc.arguments,
                        context,
                        session,
                    )
                    parsed = parse_mcp_result_to_struct(raw)
                    content = format_parsed_for_llm(parsed) or str(raw)
                    outcome = "success"
                    preview = preview_parsed_for_ui(parsed)
                    has_image = bool(parsed.images)
                    has_audio = bool(parsed.audio)
                    has_resource = bool(parsed.resources)
                except Exception as exc:
                    content = f"MCP tool error: {exc}"
                    outcome = "failure"
                    preview = None
                    has_image = has_audio = has_resource = False
                duration_ms = int((time.perf_counter() - started) * 1000)
                log_cef_event(
                    "INT002",
                    extra={
                        "cs1": tool_info.qualified_name,
                        "cs1Label": "ToolName",
                        "cs3": tool_info.server_id,
                        "cs3Label": "McpServer",
                        "cn1": duration_ms,
                        "outcome": outcome,
                    },
                )
                await emit_mcp_tool_end(
                    event_callback,
                    server_id=tool_info.server_id,
                    tool=tool_info.name,
                    qualified_name=tool_info.qualified_name,
                    success=(outcome == "success"),
                    duration_ms=duration_ms,
                    error=None if outcome == "success" else content,
                    result_preview=preview if outcome == "success" else None,
                    has_image=has_image if outcome == "success" else False,
                    has_audio=has_audio if outcome == "success" else False,
                    has_resource=has_resource if outcome == "success" else False,
                )
                tool_calls_executed += 1
                working.append({"role": "tool", "tool_call_id": tc.id, "content": content})

        final = await provider.chat(
            working,
            model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            request_extra=req_extra,
        )
        return AgentLoopResult(
            content=final or "",
            tool_calls_executed=tool_calls_executed,
            mode="native_openai_tools",
            iterations=max_iterations,
        )


def get_mcp_agent_loop() -> McpAgentLoop:
    global _agent_loop
    if _agent_loop is None:
        _agent_loop = McpAgentLoop()
    return _agent_loop
