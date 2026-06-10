"""Маршрутизация LLM: ProviderRegistry vs legacy llm-svc (B-27)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def should_use_llm_svc_direct(
    *,
    model_path: Optional[str] = None,
    images: Optional[List[Any]] = None,
) -> bool:
    """
    True → ``ask_agent_llm_svc`` / ``generate_response`` (legacy llm-svc HTTP, vision).

    - Изображения: только llm-svc path (vision в generate_response).
    - ``llm-svc://…``: legacy URI — полная логика host/swap в llm_client.
    """
    if images:
        return True
    raw = str(model_path or "").strip().lower()
    if raw.startswith("llm-svc://"):
        return True
    return False


def registry_response_usable(response: Optional[str]) -> bool:
    if response is None:
        return False
    return bool(str(response).strip())


def build_chat_messages(
    prompt: str,
    *,
    history: Optional[List[Dict[str, Any]]] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if system_prompt and str(system_prompt).strip():
        messages.append({"role": "system", "content": str(system_prompt).strip()})
    for entry in history or []:
        role = str(entry.get("role") or "").strip()
        content = entry.get("content")
        if role in ("user", "assistant", "system") and content is not None:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    return messages


async def describe_llm_routes() -> dict:
    """Диагностика: какие провайдеры в registry (для /api/system/status)."""
    try:
        from backend.llm_providers import get_registry

        registry = await get_registry()
        providers = []
        for p in registry.all():
            providers.append(
                {
                    "id": p.id,
                    "kind": p.kind,
                    "enabled": p.enabled,
                    "function_calling": p.supports_native_function_calling(),
                    "mcp_mode": p.mcp_tool_calling_mode(),
                }
            )
        return {
            "default_provider": registry.default_id,
            "providers": providers,
            "legacy_llm_svc_direct": "llm-svc:// URIs and vision (images) use ask_agent_llm_svc",
            "mcp_agent_loop": "always ProviderRegistry",
        }
    except Exception as exc:
        return {"error": str(exc)}
