"""
routes/context_prompts.py - управление контекстными промптами для моделей
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.app_state import context_prompt_manager

router = APIRouter(prefix="/api/context-prompts", tags=["context-prompts"])
logger = logging.getLogger(__name__)


@router.get("/global")
async def get_global_prompt():
    try:
        return {"prompt": context_prompt_manager.get_global_prompt(), "success": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/global")
async def update_global_prompt(request: dict):
    try:
        if not context_prompt_manager.set_global_prompt(request.get("prompt", "")):
            raise HTTPException(status_code=500, detail="Ошибка при сохранении промпта")
        return {"message": "Глобальный промпт обновлен", "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_models_with_prompts():
    try:
        return {"models": context_prompt_manager.get_models_list(), "success": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/{model_path:path}")
async def get_model_prompt(model_path: str):
    try:
        return {"model_path": model_path, "prompt": context_prompt_manager.get_model_prompt(model_path),
                "success": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/model/{model_path:path}")
async def update_model_prompt(model_path: str, request: dict):
    try:
        if not context_prompt_manager.set_model_prompt(model_path, request.get("prompt", "")):
            raise HTTPException(status_code=500, detail="Ошибка при сохранении промпта")
        return {"message": f"Промпт для модели {model_path} обновлен", "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/custom")
async def get_custom_prompts():
    try:
        return {"prompts": context_prompt_manager.get_all_custom_prompts(), "success": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
async def create_custom_prompt(request: dict):
    try:
        prompt_id = request.get("id", "").strip()
        prompt = request.get("prompt", "").strip()
        if not prompt_id or not prompt:
            raise HTTPException(status_code=400, detail="ID и промпт обязательны")
        if not context_prompt_manager.set_custom_prompt(prompt_id, prompt, request.get("description", "")):
            raise HTTPException(status_code=500, detail="Ошибка при создании промпта")
        return {"message": f"Промпт '{prompt_id}' создан", "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/custom/{prompt_id}")
async def delete_custom_prompt(prompt_id: str):
    try:
        if not context_prompt_manager.delete_custom_prompt(prompt_id):
            raise HTTPException(status_code=404, detail="Промпт не найден")
        return {"message": f"Промпт '{prompt_id}' удален", "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/effective/{model_path:path}")
async def get_effective_prompt(model_path: str, custom_prompt_id: Optional[str] = None):
    try:
        prompt = context_prompt_manager.get_effective_prompt(model_path, custom_prompt_id)
        return {"model_path": model_path, "custom_prompt_id": custom_prompt_id, "prompt": prompt,
                "success": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
