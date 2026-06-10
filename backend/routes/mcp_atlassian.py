"""Atlassian-specific MCP API extensions (тонкий слой поверх generic /api/mcp/*)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt_handler import get_current_user
from backend.mcp.credentials.store import credentials_metadata
from backend.settings.config import get_settings

router = APIRouter(tags=["mcp-atlassian"])

SERVER_ID = "atlassian"

# Fallback если в образ попала старая credentials/atlassian.py без константы
_DEFAULT_ATLASSIAN_CREDENTIAL_FIELDS = (
    "jira_url",
    "jira_pat",
    "confluence_url",
    "confluence_pat",
)


def _atlassian_credential_fields() -> list[str]:
    try:
        from backend.mcp.credentials.atlassian import ATLASSIAN_CREDENTIAL_FIELDS

        return list(ATLASSIAN_CREDENTIAL_FIELDS)
    except ImportError:
        try:
            from backend.mcp.credentials.atlassian import AtlassianCredentialProvider

            return list(AtlassianCredentialProvider.credential_field_names)
        except ImportError:
            return list(_DEFAULT_ATLASSIAN_CREDENTIAL_FIELDS)


@router.get("/api/mcp/servers/atlassian/config")
async def get_atlassian_config(current_user: dict = Depends(get_current_user)):
    settings = get_settings()
    server = settings.get_mcp_server_config(SERVER_ID)
    if not server:
        raise HTTPException(status_code=404, detail="Atlassian MCP server not configured")
    return {
        "success": True,
        "server_id": SERVER_ID,
        "config": {
            "display_name": server.display_name,
            "enabled": server.enabled,
            "transport": server.transport,
            "auth_mode": server.auth_mode,
            "tool_name_prefix": server.tool_name_prefix,
            "read_only": False,
            "toolsets": {
                "jira": True,
                "confluence": True,
            },
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.put("/api/mcp/servers/atlassian/config")
async def update_atlassian_config(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    raise HTTPException(
        status_code=501,
        detail="Atlassian runtime config update not implemented yet (MVP uses service_account in Pod)",
    )


@router.get("/api/mcp/servers/atlassian/credentials")
async def get_atlassian_credentials(current_user: dict = Depends(get_current_user)):
    settings = get_settings()
    server = settings.get_mcp_server_config(SERVER_ID)
    if not server:
        raise HTTPException(status_code=404, detail="Atlassian MCP server not configured")
    user_id = str(current_user.get("user_id") or current_user.get("username") or "")
    meta = await credentials_metadata(user_id, SERVER_ID)
    return {
        "success": True,
        "server_id": SERVER_ID,
        "auth_mode": server.auth_mode,
        "credential_fields": _atlassian_credential_fields(),
        **meta,
        "timestamp": datetime.now().isoformat(),
    }
