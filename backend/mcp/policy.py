"""MCP policy helpers (B-29 allowlist)."""

from __future__ import annotations

from typing import List, Optional

from backend.settings.config import get_settings


def get_llm_provider_allowlist() -> Optional[List[str]]:
    allowlist = get_settings().mcp.llm_provider_allowlist
    if not allowlist:
        return None
    return [str(x).strip() for x in allowlist if str(x).strip()]


def extract_provider_id(model_path: Optional[str]) -> str:
    raw = str(model_path or "").strip()
    if not raw:
        return ""
    if "/" in raw:
        return raw.split("/", 1)[0].strip()
    return raw


def is_mcp_provider_allowed(model_path: Optional[str]) -> bool:
    allowlist = get_llm_provider_allowlist()
    if not allowlist:
        return True
    provider_id = extract_provider_id(model_path)
    if not provider_id:
        return True
    return provider_id in allowlist
