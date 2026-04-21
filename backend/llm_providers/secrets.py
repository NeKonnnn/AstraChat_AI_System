"""
Управление секретами LLM-провайдеров.

Политика: **только ENV**. Никаких JSON-файлов с ключами на диске
(согласовано с пользователем). UI в настройках показывает, какой
именно ``api_key_env`` ожидается провайдером и выставлен ли он.

Соглашение об именах ENV:

- Если в конфиге провайдера явно задано ``api_key_env: MY_VAR`` —
  используется эта переменная.
- Иначе для провайдеров external kind (openai/anthropic/openrouter)
  подставляется дефолтное имя ``LLM_PROVIDER_<ID_UPPER>_API_KEY``.
"""

from __future__ import annotations

import os
import re
from typing import Optional


_API_KEY_KINDS = {"openai", "anthropic", "openrouter"}


def default_env_name_for_provider(provider_id: str) -> str:
    """``<id>`` → ``LLM_PROVIDER_<ID_UPPER>_API_KEY`` (non-alnum → ``_``)."""
    pid = (provider_id or "").strip().upper()
    pid = re.sub(r"[^A-Z0-9]+", "_", pid).strip("_") or "DEFAULT"
    return f"LLM_PROVIDER_{pid}_API_KEY"


def read_api_key(
    *,
    api_key_env: Optional[str],
    provider_id: str,
    provider_kind: str,
) -> Optional[str]:
    """
    Возвращает API-ключ из ENV.

    - Если задан ``api_key_env`` — читает оттуда.
    - Если kind ∈ external и явного env нет — fallback на
      ``LLM_PROVIDER_<ID>_API_KEY``.
    - Иначе (llm-svc/vllm/ollama/litellm — ключ не обязателен) возвращает
      то, что в явно указанной env (может быть None).
    """
    name = (api_key_env or "").strip()
    if not name and provider_kind in _API_KEY_KINDS:
        name = default_env_name_for_provider(provider_id)
    if not name:
        return None
    val = os.getenv(name)
    return val.strip() if val else None


def mask_api_key(value: Optional[str]) -> Optional[str]:
    """Маска ``sk-abc...xyz`` для безопасного отображения в UI."""
    if not value:
        return None
    s = value.strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}…{s[-4:]}"


def describe_secret_status(
    *,
    api_key_env: Optional[str],
    provider_id: str,
    provider_kind: str,
) -> dict:
    """
    Диагностика для UI: какой ENV ожидается и выставлен ли он.
    """
    expected_env = (api_key_env or "").strip()
    if not expected_env and provider_kind in _API_KEY_KINDS:
        expected_env = default_env_name_for_provider(provider_id)
    value = os.getenv(expected_env) if expected_env else None
    is_required = provider_kind in _API_KEY_KINDS
    return {
        "api_key_env": expected_env or None,
        "api_key_required": is_required,
        "api_key_set": bool(value),
        "api_key_preview": mask_api_key(value) if value else None,
    }
