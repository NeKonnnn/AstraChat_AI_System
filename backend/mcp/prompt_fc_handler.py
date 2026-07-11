"""Lightweight prompt+JSON function calling fallback (порт OWUI B-42)."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from backend.llm_providers import get_registry
from backend.mcp.connection import McpServerSession
from backend.mcp.events import McpEventCallback, emit_mcp_tool_end, emit_mcp_tool_start
from backend.mcp.platform import McpPlatformService
from backend.mcp.result_parser import compact_tool_result_for_llm, format_parsed_for_llm, parse_mcp_result_to_struct, preview_parsed_for_ui
from backend.mcp.tool_adapter import to_openai_tools
from backend.mcp.types import AgentLoopResult, McpCallContext, McpToolInfo
from backend.settings.config import get_settings
from backend.settings.logging import get_logger

log = get_logger(__name__)

DEFAULT_PROMPT_TEMPLATE = """Available Tools: {{TOOLS}}

Your task is to choose and return the correct tool(s) from the list of available tools based on the query.

- Return only the JSON object, without any additional text.
- If the query asks about current weather, news, prices, dates, or any real-time / up-to-date facts, you MUST call the search tool first.
- If the query is already answered by the tool results in History, return: {"tool_calls": []}
- If search results already contain enough facts (snippets/descriptions), do NOT fetch full pages — return {"tool_calls": []}
- Format:
{
  "tool_calls": [
    {"name": "toolName1", "parameters": {"key1": "value1"}}
  ]
}
"""

SYNTHESIS_SYSTEM_PROMPT = (
    "Ты помощник, который отвечает пользователю на основе результатов веб-поиска (MCP tools). "
    "Используй ТОЛЬКО факты из блока «Результаты инструментов». "
    "Дай конкретный, понятный ответ на русском языке. "
    "Не говори, что у тебя нет доступа к интернету или актуальным данным, если они есть в результатах."
)


def _compact_history_for_fc(messages: List[Dict[str, Any]], *, max_chars: int = 12000) -> str:
    """Короткая история для prompt_json_fc — без гигантских HTML."""
    rows = []
    for msg in messages[-6:]:
        role = msg.get("role")
        content = str(msg.get("content") or "")
        if role == "user" and content.startswith("Tool results:"):
            body = content.split("Tool results:\n", 1)[-1]
            content = "Tool results:\n" + compact_tool_result_for_llm(body, max_chars=4000)
        elif role == "assistant" and content.startswith("{"):
            content = _truncate_fc_text(content, 800)
        else:
            content = _truncate_fc_text(content, 1500)
        rows.append({"role": role, "content": content})
    payload = json.dumps(rows, ensure_ascii=False)
    if len(payload) <= max_chars:
        return payload
    return payload[: max_chars - 1] + "…"


def _truncate_fc_text(text: str, limit: int) -> str:
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def _build_synthesis_messages(
    *,
    user_query: str,
    chat_messages: List[Dict[str, Any]],
    tool_summaries: List[str],
) -> List[Dict[str, Any]]:
    """Финальный ответ: компактные tool results + исходный вопрос."""
    base_system = ""
    for msg in chat_messages:
        if msg.get("role") == "system" and msg.get("content"):
            base_system = str(msg["content"]).strip()
            break
    system_parts = [SYNTHESIS_SYSTEM_PROMPT]
    if base_system:
        system_parts.append(base_system)
    tool_block = "\n\n---\n\n".join(tool_summaries) if tool_summaries else "(нет данных)"
    return [
        {"role": "system", "content": "\n\n".join(system_parts)},
        {
            "role": "user",
            "content": (
                f"Вопрос пользователя: {user_query}\n\n"
                f"Результаты инструментов:\n{tool_block}\n\n"
                "Сформулируй ответ пользователю."
            ),
        },
    ]


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


def _pick_search_tool(tools: List[McpToolInfo]) -> Optional[McpToolInfo]:
    for tool in tools:
        if tool.name == "search" or tool.qualified_name.endswith("_search"):
            return tool
    return None


def _should_force_web_search(query: str) -> bool:
    q = (query or "").lower()
    if not q:
        return False
    markers = (
        "погод", "weather", "новост", "news", "курс", "цена", "price",
        "сегодня", "сейчас", "актуаль", "latest", "current", "сколько стоит",
        "когда", "где", "who is", "what is",
    )
    return any(m in q for m in markers)


async def _execute_tool_calls(
    *,
    calls: List[dict],
    tools: List[McpToolInfo],
    platform: McpPlatformService,
    sessions: Dict[str, McpServerSession],
    context: McpCallContext,
    event_callback: Optional[McpEventCallback],
) -> tuple[List[str], List[str], int]:
    """Выполняет tool_calls; возвращает (tool_results, tool_summaries, executed_count)."""
    tool_results: List[str] = []
    tool_summaries: List[str] = []
    executed = 0
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
            formatted = format_parsed_for_llm(parsed) or str(raw)
            tool_results.append(formatted)
            tool_summaries.append(formatted)
            executed += 1
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
    return tool_results, tool_summaries, executed


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
    tool_summaries: List[str] = []
    req_extra = dict(request_extra or {})

    for iteration in range(max(1, max_iterations)):
        prompt = _render_tools_prompt(tools)
        fc_messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"History:\n{_compact_history_for_fc(working_messages)}\nQuery: {user_query}"
                ),
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
            if tool_summaries:
                final = await provider.chat(
                    _build_synthesis_messages(
                        user_query=user_query,
                        chat_messages=messages,
                        tool_summaries=tool_summaries,
                    ),
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
            return AgentLoopResult(
                content=result.content or "Не удалось распознать вызов инструмента.",
                tool_calls_executed=tool_calls_executed,
                mode="prompt_json_fc",
                iterations=iteration + 1,
            )
        calls = payload.get("tool_calls") or []
        if not calls:
            if iteration == 0 and not tool_summaries and _should_force_web_search(user_query):
                search_tool = _pick_search_tool(tools)
                if search_tool:
                    log.info("MCP prompt_json_fc: auto search query=%s", user_query[:120])
                    calls = [
                        {
                            "name": search_tool.qualified_name,
                            "parameters": {"query": user_query[:500]},
                        }
                    ]
            if not calls:
                final = await provider.chat(
                    _build_synthesis_messages(
                        user_query=user_query,
                        chat_messages=messages,
                        tool_summaries=tool_summaries,
                    ),
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

        tool_results, new_summaries, executed = await _execute_tool_calls(
            calls=calls,
            tools=tools,
            platform=platform,
            sessions=sessions,
            context=context,
            event_callback=event_callback,
        )
        tool_summaries.extend(new_summaries)
        tool_calls_executed += executed

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
        _build_synthesis_messages(
            user_query=user_query,
            chat_messages=messages,
            tool_summaries=tool_summaries,
        ),
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
