"""Plugin registry для server-specific расширений MCP."""

from __future__ import annotations

from typing import Any, Dict, Optional


def get_server_plugin(server_id: str) -> Optional[Dict[str, Any]]:
    if server_id == "atlassian":
        return {
            "id": "atlassian",
            "display_name": "Jira / Confluence",
            "supports_credentials_api": False,
            "supports_config_api": True,
        }
    return None
