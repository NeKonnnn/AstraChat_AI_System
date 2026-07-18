"""
routes/models.py - управление моделями
"""

import asyncio
import os
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException

import backend.app_state as state
from backend.app_state import (
    model_settings, update_model_settings,
    get_model_info, get_current_model_path, save_app_settings, load_app_settings,
)
from backend.schemas import ModelSettings, ModelLoadRequest, ModelLoadResponse
from backend.settings.logging import get_logger

router = APIRouter(prefix="/api/models", tags=["models"])
logger = get_logger(__name__)


@router.get("/current")
async def get_current_model():
    if get_model_info:
        try:
            result = get_model_info()
            if result and "path" in result:
                save_app_settings({
                    "current_model_path": result["path"],
                    "current_model_name": result.get("name", "Unknown"),
                    "current_model_status": result.get("status", "loaded"),
                })
            return result
        except Exception as e:
            logger.error(f"get_model_info error: {e}")

    try:
        s = load_app_settings()
        p = s.get("current_model_path")
        if p and os.path.exists(p):
            sz = os.path.getsize(p)
            return {"name": s.get("current_model_name", os.path.basename(p)), "path": p,
                    "status": "loaded_from_settings", "size": sz, "size_mb": round(sz / 1024 / 1024, 2), "type": "gguf"}
    except Exception:
        pass

    return {"name": "Модель не загружена", "path": "", "status": "not_loaded"}


@router.get("")
@router.get("/")
async def list_models():
    return await get_available_models()


@router.get("/available")
async def get_available_models():
    """
    Список моделей, доступных пользователю, из ВСЕХ зарегистрированных
    LLM-провайдеров. Формат path — новый: ``<provider_id>/<model_id>``.
    Поле ``provider`` содержит описание провайдера (kind, capabilities).
    """
    try:
        from backend.llm_providers import get_registry

        registry = await get_registry()
        default_id = registry.default_id

        async def _rows_for_provider(provider) -> Tuple[List[dict], Optional[str]]:
            try:
                models = await provider.list_models()
            except Exception as he:
                logger.warning("provider=%s list_models error: %s", provider.id, he)
                return [], f"{provider.id}: {he}"
            is_default = provider.id == default_id
            rows: List[dict] = []
            for m in models:
                extra = dict(m.extra or {})
                rows.append({
                    "name": m.model_id,
                    "display_name": m.display_name or m.model_id,
                    "path": m.path,  # "<provider_id>/<model_id>"
                    "provider_id": provider.id,
                    "provider_kind": provider.kind,
                    "provider_default": is_default,
                    "capabilities": {
                        "hot_swap": provider.capabilities.hot_swap,
                        "multi_loaded": provider.capabilities.multi_loaded,
                        "streaming": provider.capabilities.streaming,
                        "vision": provider.capabilities.vision,
                    },
                    "context_size": m.context_size,
                    "size": extra.pop("size", 0),
                    "size_mb": extra.pop("size_mb", 0),
                    "object": extra.pop("object", "model"),
                    "owned_by": extra.pop("owned_by", provider.id),
                    # Legacy-alias для старых клиентов: llm_host_id == provider_id.
                    "llm_host_id": provider.id,
                    "extra": extra,
                })
            return rows, None

        pairs = await asyncio.gather(*(_rows_for_provider(p) for p in registry.all()))
        result_models: List[dict] = []
        warnings: List[str] = []
        for rows, warn in pairs:
            result_models.extend(rows)
            if warn:
                warnings.append(warn)
        response = {"models": result_models}
        if warnings:
            response["warning"] = "; ".join(warnings)
        return response
    except Exception as e:
        logger.error(f"get_available_models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load", response_model=ModelLoadResponse)
async def load_model(request: ModelLoadRequest):
    """Загрузка весов модели.

    Ответ (и снятие UI-спиннера) — только после реального ensure_model_loaded.
    Без sync/to_thread/asyncio.run: иначе ответ может «залипнуть» после успеха в логах.
    """
    model_path = (request.model_path or "").strip()
    if not model_path:
        return ModelLoadResponse(message="model_path пуст", success=False)
    if os.path.isdir(model_path):
        return ModelLoadResponse(message=f"Передан путь к директории: {model_path}", success=False)

    try:
        from backend.llm_providers import get_registry

        registry = await get_registry()
        provider, model_id = registry.resolve(model_path)
        if not model_id:
            # Пришёл только id провайдера — берём первую доступную модель.
            if registry.contains(model_path):
                provider = registry.get(model_path)
                candidates = await provider.list_models()
                model_id = str((candidates[0].model_id if candidates else "") or "").strip()
            if not model_id:
                return ModelLoadResponse(message="Не удалось определить model_id", success=False)

        ok = await provider.ensure_model_loaded(model_id)
        if not ok:
            return ModelLoadResponse(message="Не удалось загрузить модель", success=False)

        selected = f"{provider.id}/{model_id}"
        try:
            from backend import agent_llm_svc

            agent_llm_svc._selected_model_name = selected
        except Exception:
            pass

        save_app_settings(
            {
                "current_model_path": selected,
                "current_model_name": model_id,
                "current_model_status": "loaded",
            }
        )
        logger.info("POST /api/models/load OK: %s", selected)
        return ModelLoadResponse(message="Модель успешно загружена", success=True)
    except Exception as e:
        logger.exception("POST /api/models/load error")
        return ModelLoadResponse(message=f"Ошибка: {str(e)}", success=False)


@router.get("/settings")
async def get_model_settings():
    defaults = {"context_size": 2048, "output_tokens": 512, "temperature": 0.7, "top_p": 0.95,
                "repeat_penalty": 1.05, "top_k": 40, "min_p": 0.05, "frequency_penalty": 0.0,
                "presence_penalty": 0.0, "use_gpu": False, "streaming": True, "streaming_speed": 20}
    if not model_settings:
        return defaults
    try:
        return model_settings.get_all()
    except Exception as e:
        logger.error(f"model_settings.get_all error: {e}")
        return defaults


@router.put("/settings")
async def update_model_settings_api(settings_data: ModelSettings):
    if not update_model_settings:
        raise HTTPException(status_code=503, detail="AI agent не доступен")
    try:
        if update_model_settings(settings_data.dict()):
            return {"message": "Настройки обновлены", "success": True}
        raise HTTPException(status_code=400, detail="Не удалось обновить настройки")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/reset")
async def reset_model_settings():
    if not model_settings:
        raise HTTPException(status_code=503, detail="AI agent не доступен")
    try:
        model_settings.reset_to_defaults()
        return {"message": "Настройки сброшены", "success": True, "settings": model_settings.get_all()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/recommended")
async def get_recommended_settings():
    if not model_settings:
        raise HTTPException(status_code=503, detail="AI agent не доступен")
    try:
        return {"recommended": model_settings.get_recommended_settings(), "max_values": model_settings.get_max_values()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
