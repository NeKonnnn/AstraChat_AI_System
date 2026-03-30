"""
routes/models.py - управление моделями
"""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

import backend.app_state as state
from backend.app_state import (
    model_settings, update_model_settings, reload_model_by_path,
    get_model_info, get_current_model_path, save_app_settings, load_app_settings,
)
from backend.schemas import ModelSettings, ModelLoadRequest, ModelLoadResponse

router = APIRouter(prefix="/api/models", tags=["models"])
logger = logging.getLogger(__name__)


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
    try:
        use_llm_svc = os.getenv("USE_LLM_SVC", "false").lower() == "true"
        if use_llm_svc:
            try:
                from backend.llm_client import get_llm_service
                service = await get_llm_service()
                data = await service.client.get_models()
                models = [{"name": m.get("id"), "path": f"llm-svc://{m.get('id','unknown')}",
                           "size": m.get("size", 0), "size_mb": m.get("size_mb", 0),
                           "object": m.get("object", "model"), "owned_by": m.get("owned_by", "llm-svc")} for m in data]
                return {"models": models}
            except Exception as e:
                logger.error(f"llm-svc models error: {e}")
                return {"models": [], "error": str(e), "warning": "llm-svc недоступен"}
        else:
            models_dir = "models"
            if not os.path.exists(models_dir):
                return {"models": []}
            models = []
            for f in os.listdir(models_dir):
                if f.endswith(".gguf"):
                    fp = os.path.join(models_dir, f)
                    sz = os.path.getsize(fp)
                    models.append({"name": f, "path": fp, "size": sz, "size_mb": round(sz / 1024 / 1024, 2)})
            return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load", response_model=ModelLoadResponse)
async def load_model(request: ModelLoadRequest):
    if not reload_model_by_path:
        return ModelLoadResponse(message="Функция загрузки модели недоступна", success=False)
    try:
        if os.path.isdir(request.model_path):
            return ModelLoadResponse(message=f"Передан путь к директории: {request.model_path}", success=False)

        success = reload_model_by_path(request.model_path)
        if success:
            name = request.model_path.replace("llm-svc://", "") if request.model_path.startswith("llm-svc://") else os.path.basename(request.model_path)
            save_app_settings({"current_model_path": request.model_path, "current_model_name": name, "current_model_status": "loaded"})
            return ModelLoadResponse(message="Модель успешно загружена", success=True)
        return ModelLoadResponse(message="Не удалось загрузить модель", success=False)
    except Exception as e:
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
