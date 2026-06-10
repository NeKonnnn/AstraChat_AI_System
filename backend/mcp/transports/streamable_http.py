"""Streamable HTTP transport (MCP SDK streamablehttp_client)."""

from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urljoin

from backend.mcp.sdk import import_mcp_sdk_submodule

streamablehttp_client = import_mcp_sdk_submodule("mcp.client.streamable_http").streamablehttp_client

from backend.mcp.client import create_httpx_client, create_insecure_httpx_client


def build_mcp_http_url(base_url: str, base_path: str) -> str:
    root = str(base_url or "").strip().rstrip("/")
    path = str(base_path or "/mcp").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return urljoin(f"{root}/", path.lstrip("/"))


async def connect_streamable_http(
    client,
    *,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 120.0,
    verify_ssl: bool = True,
) -> None:
    factory = create_httpx_client if verify_ssl else create_insecure_httpx_client
    streams_context = streamablehttp_client(
        url,
        headers=headers,
        httpx_client_factory=factory,
    )
    await client.connect_streams(streams_context, init_timeout=min(timeout, 30.0))
