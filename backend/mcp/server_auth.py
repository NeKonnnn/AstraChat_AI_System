"""Generic MCP server auth matrix (B-34) — не привязан к Atlassian."""

from __future__ import annotations

import os
from typing import Dict

from backend.settings.config import McpServerConfig


def _env_prefix(server_id: str) -> str:
    return f"MCP_SERVER_{server_id.upper().replace('-', '_')}_"


def _resolve_auth_token(server: McpServerConfig) -> str:
    env_val = os.getenv(f"{_env_prefix(server.id)}AUTH_TOKEN")
    if env_val is not None:
        return env_val.strip()
    return str(server.auth_token or "").strip()


def build_server_auth_headers(server: McpServerConfig) -> Dict[str, str]:
    """
    OWUI auth matrix: none | bearer | headers | session | oauth_2.1.
    Credential plugins (Atlassian PAT и т.д.) — отдельный слой в session_manager.
    """
    auth_type = str(server.auth_type or "none").strip().lower()
    if auth_type in ("", "none"):
        return {}

    if auth_type == "bearer":
        token = _resolve_auth_token(server)
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    if auth_type == "headers":
        prefix = _env_prefix(server.id)
        name = (os.getenv(f"{prefix}AUTH_HEADER_NAME") or server.auth_header_name or "").strip()
        value = (os.getenv(f"{prefix}AUTH_HEADER_VALUE") or server.auth_header_value or "").strip()
        if name and value:
            return {name: value}
        return {}

    if auth_type == "session":
        # Фаза 2: cookie/session propagation
        return {}

    if auth_type == "oauth_2.1":
        # Фаза 3: DCR + token refresh
        return {}

    return {}
