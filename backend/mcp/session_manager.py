"""Per-request lifecycle MCP sessions + pool integration."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

import httpx

from backend.mcp.client import McpClient
from backend.mcp.connection import McpServerSession
from backend.mcp.server_auth import build_server_auth_headers
from backend.mcp.context_headers import build_context_headers, merge_server_custom_headers
from backend.mcp.credentials.base import get_credential_provider
from backend.mcp.exceptions import McpConnectionError, McpServerNotFoundError
from backend.mcp.registry import McpRegistry
from backend.mcp.session_pool import McpSessionPool
from backend.mcp.transports.stdio import connect_stdio
from backend.mcp.transports.streamable_http import build_mcp_http_url, connect_streamable_http
from backend.mcp.types import McpCallContext, McpTransport
from backend.settings.config import McpServerConfig, Settings
from backend.settings.logging import get_logger

log = get_logger(__name__)


def _headers_fingerprint(headers: Dict[str, str]) -> str:
    payload = json.dumps(headers or {}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class McpSessionManager:
    def __init__(self, settings: Settings, registry: McpRegistry, pool: Optional[McpSessionPool] = None):
        self._settings = settings
        self._registry = registry
        self._pool = pool
        self._active: List[McpServerSession] = []

    async def connect_server(
        self,
        server_id: str,
        context: McpCallContext,
        *,
        use_pool: bool = True,
        ephemeral: bool = False,
    ) -> McpServerSession:
        server = self._registry.require_server(server_id)
        if not server.enabled:
            raise McpServerNotFoundError(f"MCP server '{server_id}' is disabled")

        provider = get_credential_provider(server.credential_provider)
        generic_auth = build_server_auth_headers(server)
        auth_headers = await provider.build_headers(server, context)
        ctx_headers = build_context_headers(context)
        custom_headers = merge_server_custom_headers(getattr(server, "custom_headers", None), context)
        headers = {**generic_auth, **auth_headers, **ctx_headers, **custom_headers}
        fingerprint = _headers_fingerprint(headers)

        if (
            use_pool
            and not ephemeral
            and self._pool is not None
            and server.transport == McpTransport.STREAMABLE_HTTP.value
        ):
            session = await self._pool.acquire(
                server_id,
                server=server,
                context=context,
                headers=headers,
                fingerprint=fingerprint,
            )
            if session.headers_fingerprint != fingerprint:
                await self._pool.discard(session)
                session = await self._create_session(server, context, headers, fingerprint)
            session.ephemeral = ephemeral
            self._track(session)
            return session

        session = await self._create_session(server, context, headers, fingerprint)
        session.ephemeral = ephemeral
        self._track(session)
        return session

    async def connect_servers(
        self,
        server_ids: List[str],
        context: McpCallContext,
        *,
        use_pool: bool = True,
        ephemeral: bool = False,
    ) -> Dict[str, McpServerSession]:
        sessions: Dict[str, McpServerSession] = {}
        for sid in server_ids:
            try:
                sessions[sid] = await self.connect_server(
                    sid, context, use_pool=use_pool, ephemeral=ephemeral
                )
            except Exception as exc:
                log.warning("MCP connect failed server=%s: %s", sid, exc)
        return sessions

    async def disconnect_all(self) -> None:
        for session in reversed(self._active):
            try:
                if (
                    self._pool
                    and not session.ephemeral
                    and session.config.transport == "streamable-http"
                ):
                    await self._pool.release(session)
                else:
                    await session.close()
            except Exception as exc:
                log.debug("MCP disconnect error server=%s: %s", session.server_id, exc)
        self._active.clear()

    async def discard_session(self, session: McpServerSession) -> None:
        if session in self._active:
            self._active.remove(session)
        if self._pool:
            await self._pool.discard(session)
        else:
            await session.close()

    def _track(self, session: McpServerSession) -> None:
        self._active.append(session)

    async def _create_session(
        self,
        server: McpServerConfig,
        context: McpCallContext,
        headers: Dict[str, str],
        fingerprint: str,
    ) -> McpServerSession:
        client = McpClient()
        timeout = float(server.timeout_seconds or 120)
        try:
            if server.transport == McpTransport.STDIO.value:
                if not server.command:
                    raise McpConnectionError(f"stdio transport requires command for server '{server.id}'")
                await connect_stdio(
                    client,
                    command=server.command,
                    args=server.args,
                    cwd=server.cwd,
                    env=getattr(server, "env", None) or None,
                    timeout=timeout,
                )
            else:
                base = str(server.base_url or "").strip() or self._settings.resolve_mcp_server_base_url(server.id)
                url = build_mcp_http_url(base, server.base_path)
                await connect_streamable_http(
                    client,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    verify_ssl=bool(server.verify_ssl),
                )
        except Exception as exc:
            await client.disconnect()
            raise McpConnectionError(f"Failed to connect MCP server '{server.id}': {exc}") from exc

        return McpServerSession(
            server_id=server.id,
            config=server,
            client=client,
            context=context,
            headers_fingerprint=fingerprint,
        )

    async def create_pooled_session(
        self,
        server_id: str,
        *,
        server: McpServerConfig,
        context: McpCallContext,
        headers: Dict[str, str],
        fingerprint: str,
    ) -> McpServerSession:
        return await self._create_session(server, context, headers, fingerprint)

    async def probe_http_health(self, server: McpServerConfig) -> bool:
        if server.transport != McpTransport.STREAMABLE_HTTP.value:
            return True
        base = str(server.base_url or "").strip() or self._settings.resolve_mcp_server_base_url(server.id)
        health_path = str(server.health_path or "/healthz").strip()
        if not health_path.startswith("/"):
            health_path = f"/{health_path}"
        url = f"{base.rstrip('/')}{health_path}"
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=bool(server.verify_ssl)) as client:
                resp = await client.get(url)
                return resp.status_code < 500
        except Exception:
            return False
