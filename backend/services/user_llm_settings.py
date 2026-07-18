"""
Персональные LLM-настройки и контекстные промпты пользователя.

Глобальные llm_settings.json / context_prompts.json остаются seed/defaults.
Персистентность — PostgreSQL user_llm_settings по user_id.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from backend.context_prompts import ContextPromptManager
from backend.settings.logging import get_logger

logger = get_logger(__name__)


def _default_model_settings() -> Dict[str, Any]:
    try:
        from backend.app_state import model_settings

        if model_settings and hasattr(model_settings, "default_settings"):
            return deepcopy(model_settings.default_settings)
        if model_settings and hasattr(model_settings, "get_all"):
            return model_settings.get_all()
    except Exception:
        logger.exception("default model settings: app_state unavailable")
    return {
        "context_size": 8192,
        "output_tokens": 1024,
        "batch_size": 512,
        "n_threads": 12,
        "use_mmap": True,
        "use_mlock": False,
        "verbose": True,
        "temperature": 0.7,
        "top_p": 0.95,
        "repeat_penalty": 1.05,
        "top_k": 40,
        "min_p": 0.05,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "use_gpu": True,
        "streaming": True,
        "legacy_api": False,
    }


def _default_context_prompts() -> Dict[str, Any]:
    return {"global_prompt": "", "model_prompts": {}, "custom_prompts": {}}


def _merge_model_settings(stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = _default_model_settings()
    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in merged and value is not None:
                merged[key] = value
    return merged


def _merge_context_prompts(stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = _default_context_prompts()
    if not isinstance(stored, dict):
        return base
    out = {
        "global_prompt": stored.get("global_prompt", base.get("global_prompt", "")),
        "model_prompts": dict(base.get("model_prompts") or {}),
        "custom_prompts": dict(base.get("custom_prompts") or {}),
    }
    if isinstance(stored.get("model_prompts"), dict):
        out["model_prompts"].update(stored["model_prompts"])
    if isinstance(stored.get("custom_prompts"), dict):
        out["custom_prompts"] = dict(stored["custom_prompts"])
    if "global_prompt" in stored:
        out["global_prompt"] = stored.get("global_prompt") or ""
    return out


def _get_repo():
    try:
        from backend.database.init_db import get_user_settings_repository

        return get_user_settings_repository()
    except Exception:
        logger.debug("user settings repository недоступен", exc_info=True)
        return None


def prompt_manager_from_data(data: Dict[str, Any]) -> ContextPromptManager:
    """In-memory ContextPromptManager без записи в глобальный файл."""
    mgr = ContextPromptManager.__new__(ContextPromptManager)
    mgr.prompts_file = ""
    mgr._prompts_path = None
    mgr.context_prompts = _merge_context_prompts(data)
    # save_* пишут только в память — API сохраняет через сервис
    mgr.save_context_prompts = lambda prompts=None: _memory_save(mgr, prompts)  # type: ignore[method-assign]
    return mgr


def _memory_save(mgr: ContextPromptManager, prompts: Optional[Dict[str, Any]] = None) -> bool:
    if prompts is not None:
        mgr.context_prompts = prompts
    return True


async def get_user_model_settings(user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        return _default_model_settings()
    repo = _get_repo()
    if repo is None:
        return _default_model_settings()
    row = await repo.get(user_id)
    if not row:
        return _default_model_settings()
    return _merge_model_settings(row.get("model_settings"))


async def save_user_model_settings(user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    merged = _merge_model_settings(settings)
    repo = _get_repo()
    if repo is None:
        raise RuntimeError("Хранилище пользовательских настроек недоступно")
    row = await repo.get(user_id)
    existing_prompts = (row or {}).get("context_prompts") if row else None
    # При первом сохранении настроек также зафиксируем seed промптов,
    # чтобы строка пользователя была полной.
    prompts_to_store = _merge_context_prompts(existing_prompts) if not row else None
    saved = await repo.upsert(
        user_id,
        model_settings=merged,
        context_prompts=prompts_to_store,
    )
    if not saved:
        raise RuntimeError("Не удалось сохранить настройки модели")
    return _merge_model_settings(saved.get("model_settings"))


async def reset_user_model_settings(user_id: str) -> Dict[str, Any]:
    defaults = _default_model_settings()
    return await save_user_model_settings(user_id, defaults)


async def get_user_context_prompts(user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        return _default_context_prompts()
    repo = _get_repo()
    if repo is None:
        return _default_context_prompts()
    row = await repo.get(user_id)
    if not row:
        return _default_context_prompts()
    return _merge_context_prompts(row.get("context_prompts"))


async def get_user_prompt_manager(user_id: Optional[str]) -> ContextPromptManager:
    data = await get_user_context_prompts(user_id)
    return prompt_manager_from_data(data)


async def save_user_context_prompts(user_id: str, prompts: Dict[str, Any]) -> Dict[str, Any]:
    merged = _merge_context_prompts(prompts)
    repo = _get_repo()
    if repo is None:
        raise RuntimeError("Хранилище пользовательских настроек недоступно")
    row = await repo.get(user_id)
    existing_settings = (row or {}).get("model_settings") if row else None
    settings_to_store = _merge_model_settings(existing_settings) if not row else None
    saved = await repo.upsert(
        user_id,
        model_settings=settings_to_store,
        context_prompts=merged,
    )
    if not saved:
        raise RuntimeError("Не удалось сохранить контекстные промпты")
    return _merge_context_prompts(saved.get("context_prompts"))


async def set_user_global_prompt(user_id: str, prompt: str) -> Dict[str, Any]:
    data = await get_user_context_prompts(user_id)
    data["global_prompt"] = prompt or ""
    return await save_user_context_prompts(user_id, data)


async def set_user_model_prompt(user_id: str, model_path: str, prompt: str) -> Dict[str, Any]:
    data = await get_user_context_prompts(user_id)
    model_prompts = dict(data.get("model_prompts") or {})
    if prompt and prompt.strip():
        model_prompts[model_path] = prompt
    else:
        model_prompts.pop(model_path, None)
    data["model_prompts"] = model_prompts
    return await save_user_context_prompts(user_id, data)


async def set_user_custom_prompt(
    user_id: str, prompt_id: str, prompt: str, description: str = ""
) -> Dict[str, Any]:
    from datetime import datetime

    data = await get_user_context_prompts(user_id)
    custom = dict(data.get("custom_prompts") or {})
    custom[prompt_id] = {
        "prompt": prompt,
        "description": description,
        "created_at": datetime.now().isoformat(),
    }
    data["custom_prompts"] = custom
    return await save_user_context_prompts(user_id, data)


async def delete_user_custom_prompt(user_id: str, prompt_id: str) -> bool:
    data = await get_user_context_prompts(user_id)
    custom = dict(data.get("custom_prompts") or {})
    if prompt_id not in custom:
        return False
    del custom[prompt_id]
    data["custom_prompts"] = custom
    await save_user_context_prompts(user_id, data)
    return True


async def enrich_agent_profile_with_user_settings(
    agent_profile: Optional[Dict[str, Any]], user_id: Optional[str]
) -> Dict[str, Any]:
    """Подставляет temperature/max_tokens из персональных настроек, если агент их не задал."""
    profile = dict(agent_profile or {})
    user_ms = await get_user_model_settings(user_id)
    if profile.get("max_tokens") is None:
        try:
            profile["max_tokens"] = int(user_ms.get("output_tokens") or 1024)
        except (TypeError, ValueError):
            profile["max_tokens"] = 1024
    if profile.get("temperature") is None:
        try:
            profile["temperature"] = float(
                user_ms.get("temperature") if user_ms.get("temperature") is not None else 0.7
            )
        except (TypeError, ValueError):
            profile["temperature"] = 0.7
    return profile
