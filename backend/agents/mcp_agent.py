"""
Generic MCP agent — делегирует в McpPlatformService / McpAgentLoop (B-19).

Не содержит Atlassian- или filesystem-specific логики: любой MCP-сервер
из ``mcp.servers[]`` доступен через ``tool_ids`` в context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.agents.base_agent import BaseAgent
from backend.mcp.chat_integration import build_mcp_context_from_user, run_mcp_for_chat
from backend.mcp.platform import get_mcp_platform
from backend.mcp.resolvers import parse_mcp_server_ids
from backend.settings.logging import get_logger

logger = get_logger(__name__)


class MCPAgent(BaseAgent):
    """Универсальный агент для MCP-серверов из конфигурации платформы."""

    def __init__(self):
        super().__init__(
            name="mcp",
            description="Агент для работы с внешними сервисами через MCP",
        )
        self.capabilities = ["mcp_tools", "external_integrations"]

    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        context = context or {}
        platform = get_mcp_platform()
        if not platform.enabled:
            return "MCP-платформа отключена (MCP_ENABLED=false)."
        if not platform.initialized:
            return "MCP-платформа ещё не инициализирована."

        tool_ids = self._resolve_tool_ids(context)
        if not tool_ids:
            return self._no_servers_hint()

        user = context.get("current_user") or {}
        model_path = (
            context.get("selected_model")
            or context.get("model_path")
            or ""
        )
        if not model_path:
            try:
                from backend.app_state import get_current_model_path

                model_path = get_current_model_path()
            except Exception:
                model_path = ""

        try:
            result = await run_mcp_for_chat(
                tool_ids=tool_ids,
                user_message=message,
                history=context.get("history"),
                system_prompt=context.get("system_prompt"),
                model_path=model_path,
                user=user,
                chat_id=context.get("conversation_id"),
                message_id=context.get("message_id"),
                temperature=float(context.get("temperature") or 0.7),
                max_tokens=int(context.get("max_tokens") or 1024),
                enable_thinking=bool(context.get("enable_thinking")),
            )
            if result is not None:
                return result.content or ""
            return "MCP-инструменты недоступны для выбранных серверов или нет прав доступа."
        except Exception as exc:
            logger.error("MCPAgent error: %s", exc, exc_info=True)
            return f"Ошибка MCP: {exc}"

    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        context = context or {}
        if self._resolve_tool_ids(context):
            return True

        platform = get_mcp_platform()
        if not platform.enabled:
            return False

        msg = (message or "").lower()
        for srv in platform.list_servers_public():
            if not srv.get("enabled"):
                continue
            sid = str(srv.get("id") or "")
            display = str(srv.get("display_name") or "").lower()
            if sid and sid.lower() in msg:
                return True
            if display and display in msg:
                return True
        return "mcp" in msg

    def get_mcp_status(self) -> Dict[str, Any]:
        platform = get_mcp_platform()
        if not platform.initialized:
            return {"initialized": False, "enabled": platform.enabled, "servers": 0, "tools": 0}
        return {
            "initialized": True,
            "enabled": platform.enabled,
            "servers": len(platform.list_servers_public()),
        }

    def _resolve_tool_ids(self, context: Dict[str, Any]) -> List[str]:
        raw = context.get("tool_ids") or context.get("mcp_tool_ids") or []
        return parse_mcp_server_ids(raw if isinstance(raw, list) else [raw])

    def _no_servers_hint(self) -> str:
        platform = get_mcp_platform()
        servers = [s for s in platform.list_servers_public() if s.get("enabled")]
        if not servers:
            return "Нет включённых MCP-серверов. Добавьте сервер в mcp.servers[] конфигурации."
        ids = ", ".join(f"server:mcp:{s['id']}" for s in servers[:5])
        return (
            "Укажите MCP-серверы через tool_ids в запросе, например: "
            f"[{ids}]. Доступные серверы: {', '.join(s['id'] for s in servers)}."
        )
