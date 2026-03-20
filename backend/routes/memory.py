"""
routes/memory.py - история диалогов и настройки памяти
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

import backend.app_state as state
from backend.app_state import (
    get_recent_dialog_history, clear_dialog_history, save_app_settings,
)
from backend.schemas import MemorySettings

router = APIRouter(tags=["memory"])
logger = logging.getLogger(__name__)


@router.get("/api/history")
async def get_chat_history(limit: int = None):
    if limit is None:
        limit = state.memory_max_messages
    if not get_recent_dialog_history:
        raise HTTPException(status_code=503, detail="Memory service недоступен")
    try:
        history = await get_recent_dialog_history(max_entries=limit)
        return {"history": history, "count": len(history), "max_messages": state.memory_max_messages,
                "timestamp": datetime.now().isoformat(), "source": "memory_service"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/history")
async def clear_chat_history():
    if not clear_dialog_history:
        raise HTTPException(status_code=503, detail="Memory service недоступен")
    try:
        await clear_dialog_history()
        return {"message": "История очищена", "success": True, "source": "memory_service"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/settings")
async def get_memory_settings():
    return {
        "max_messages": state.memory_max_messages,
        "include_system_prompts": state.memory_include_system_prompts,
        "clear_on_restart": state.memory_clear_on_restart,
    }


@router.put("/api/memory/settings")
async def update_memory_settings(settings_data: MemorySettings):
    try:
        state.memory_max_messages = settings_data.max_messages
        state.memory_include_system_prompts = settings_data.include_system_prompts
        state.memory_clear_on_restart = settings_data.clear_on_restart
        save_app_settings({
            "memory_max_messages": state.memory_max_messages,
            "memory_include_system_prompts": state.memory_include_system_prompts,
            "memory_clear_on_restart": state.memory_clear_on_restart,
        })
        return {"message": "Настройки памяти обновлены", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/status")
async def get_memory_status():
    if not get_recent_dialog_history:
        raise HTTPException(status_code=503, detail="Memory service недоступен")
    try:
        history = await get_recent_dialog_history(max_entries=state.memory_max_messages)
        return {"message_count": len(history), "max_messages": state.memory_max_messages, "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory/clear")
async def clear_memory():
    if not clear_dialog_history:
        raise HTTPException(status_code=503, detail="Memory service недоступен")
    try:
        result = await clear_dialog_history()
        return {"message": "Память успешно очищена", "success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка очистки памяти: {str(e)}")
