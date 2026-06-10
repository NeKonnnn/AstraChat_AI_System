"""Lightweight prompt+JSON function calling fallback (порт OWUI B-42)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from backend.llm_providers import get_registry
from backend.mcp.connection import McpServerSession
from backend.mcp.events import McpEventCallback, emit_mcp_tool_end, emit_mcp_tool_start
from backend.mcp.platform import McpPlatformService
from backend.mcp.result_parser import format_parsed_for_llm, parse_mcp_result_to_struct, preview_parsed_for_ui
from backend.mcp.tool_adapter import to_openai_tools
from backend.mcp.types import AgentLoopResult, McpCallContext, McpToolInfo
from backend.settings.config import get_settings

log = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """Available Tools: {{TOOLS}}

Your task is to choose and return the correct tool(s) from the list of available tools based on the query.

- Return only the JSON object, without any additional text.
- If no tools match, return: {"tool_calls": []}
- Format:
{
  "tool_calls": [
    {"name": "toolName1", "parameters": {"key1": "value1"}}
  ]
}
"""


def _render_tools_prompt(tools: List[McpToolInfo]) -> str:
    specs = []
    for tool in tools:
        specs.append(
            {
                "name": tool.qualified_name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
        )
    tools_json = json.dumps(specs, ensure_ascii=False)
    return DEFAULT_PROMPT_TEMPLATE.replace("{{TOOLS}}", tools_json)


def _extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _find_tool(name: str, tools: List[McpToolInfo]) -> Optional[McpToolInfo]:
    for tool in tools:
        if tool.qualified_name == name or tool.name == name:
            return tool
    return None


async def run_prompt_json_fc(
    *,
    messages: List[Dict[str, Any]],
    model_path: str,
    tools: List[McpToolInfo],
    context: McpCallContext,
    platform: McpPlatformService,
    sessions: Dict[str, McpServerSession],
    fc_model_path: Optional[str] = None,
    max_iterations: int = 3,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    request_extra: Optional[Dict[str, Any]] = None,
    event_callback: Optional[McpEventCallback] = None,
) -> AgentLoopResult:
    settings = get_settings()
    effective_model_path = fc_model_path or model_path or settings.mcp.fc_task_model or model_path
    registry = await get_registry()
    provider, model_id = registry.resolve(effective_model_path)
    if not model_id:
        models = await provider.list_models()
        model_id = models[0].model_id if models else ""

    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = str(msg.get("content") or "")
            break

    tool_calls_executed = 0
    working_messages = list(messages)
    req_extra = dict(request_extra or {})

    for iteration in range(max(1, max_iterations)):
        prompt = _render_tools_prompt(tools)
        fc_messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"History:\n{json.dumps(working_messages[-4:], ensure_ascii=False)}\nQuery: {user_query}",
            },
        ]
        result = await provider.chat_completion(
            fc_messages,
            model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            request_extra=req_extra,
        )
        payload = _extract_json_object(result.content)
        if not payload:
            return AgentLoopResult(
                content=result.content or "Не удалось распознать вызов инструмента.",
                tool_calls_executed=tool_calls_executed,
                mode="prompt_json_fc",
                iterations=iteration + 1,
            )
        calls = payload.get("tool_calls") or []
        if not calls:
            final = await provider.chat(
                working_messages,
                model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                request_extra=req_extra,
            )
            return AgentLoopResult(
                content=final,
                tool_calls_executed=tool_calls_executed,
                mode="prompt_json_fc",
                iterations=iteration + 1,
            )

        tool_results: List[str] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            params = call.get("parameters") or call.get("arguments") or {}
            tool_info = _find_tool(name, tools)
            if not tool_info:
                tool_results.append(f"Tool {name} not found")
                continue
            session = sessions.get(tool_info.server_id)
            if not session:
                tool_results.append(f"MCP session for {tool_info.server_id} unavailable")
                continue
            try:
                started = time.perf_counter()
                await emit_mcp_tool_start(
                    event_callback,
                    server_id=tool_info.server_id,
                    tool=tool_info.name,
                    qualified_name=tool_info.qualified_name,
                )
                raw = await platform.call_tool(
                    tool_info.server_id,
                    tool_info.name,
                    params if isinstance(params, dict) else {},
                    context,
                    session,
                )
                parsed = parse_mcp_result_to_struct(raw)
                tool_results.append(format_parsed_for_llm(parsed) or str(raw))
                tool_calls_executed += 1
                duration_ms = int((time.perf_counter() - started) * 1000)
                await emit_mcp_tool_end(
                    event_callback,
                    server_id=tool_info.server_id,
                    tool=tool_info.name,
                    qualified_name=tool_info.qualified_name,
                    success=True,
                    duration_ms=duration_ms,
                    result_preview=preview_parsed_for_ui(parsed),
                    has_image=bool(parsed.images),
                    has_audio=bool(parsed.audio),
                    has_resource=bool(parsed.resources),
                )
            except Exception as exc:
                duration_ms = int((time.perf_counter() - started) * 1000) if "started" in locals() else 0
                await emit_mcp_tool_end(
                    event_callback,
                    server_id=tool_info.server_id,
                    tool=tool_info.name,
                    qualified_name=tool_info.qualified_name,
                    success=False,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                tool_results.append(f"Error calling {name}: {exc}")

        working_messages.append(
            {
                "role": "assistant",
                "content": json.dumps({"tool_calls": calls}, ensure_ascii=False),
            }
        )
        working_messages.append(
            {
                "role": "user",
                "content": "Tool results:\n" + "\n".join(tool_results),
            }
        )

    final = await provider.chat(
        working_messages,
        model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        request_extra=req_extra,
    )
    return AgentLoopResult(
        content=final,
        tool_calls_executed=tool_calls_executed,
        mode="prompt_json_fc",
        iterations=max_iterations,
    )
