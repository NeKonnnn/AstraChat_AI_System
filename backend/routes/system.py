"""
routes/system.py - health-check, системный статус, socket-test
"""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter

from backend.app_state import (
    ask_agent, save_dialog_entry, get_recent_dialog_history, clear_dialog_history,
    speak_text, recognize_speech, recognize_speech_from_file, check_stt_available,
    rag_client, model_settings, update_model_settings, reload_model_by_path,
    get_model_info, initialize_model, minio_client, UniversalTranscriber,
    settings,
)
import backend.app_state as state

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)

_urls = settings.urls


@router.get("/")
async def root():
    return {"message": "astrachat Web API", "status": "active", "version": "1.0.0"}


@router.get("/socket-test")
async def socket_test():
    return {
        "socketio_status": "active",
        "endpoint": "/socket.io/",
        "cors_origins": [
            getattr(_urls, "frontend_port_1", None),
            getattr(_urls, "frontend_port_1_ipv4", None),
            getattr(_urls, "frontend_port_2", None),
            getattr(_urls, "frontend_port_3", None),
        ],
        "ping_timeout": 300,
        "ping_interval": 15,
    }


@router.get("/health")
async def health_check():
    try:
        model_info = get_model_info() if get_model_info else {"loaded": False}
        stt_status = check_stt_available() if check_stt_available else False

        rag_available = False
        if rag_client:
            try:
                health = await rag_client.health()
                rag_available = bool(health)
            except Exception:
                pass

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "llm_model": model_info.get("loaded", False),
                "stt_whisperx": stt_status,
                "rag_service": rag_available,
                "transcriber": UniversalTranscriber is not None,
            },
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}


@router.get("/api/system/status")
async def get_system_status():
    module_status = {
        "ai_agent": {
            "available": ask_agent is not None,
            "functions": {
                "ask_agent": ask_agent is not None,
                "model_settings": model_settings is not None,
                "update_model_settings": update_model_settings is not None,
                "reload_model_by_path": reload_model_by_path is not None,
                "get_model_info": get_model_info is not None,
                "initialize_model": initialize_model is not None,
            },
        },
        "memory": {
            "available": save_dialog_entry is not None,
            "functions": {
                "save_dialog_entry": save_dialog_entry is not None,
                "load_dialog_history": get_recent_dialog_history is not None,
                "clear_dialog_history": clear_dialog_history is not None,
            },
        },
        "voice": {
            "available": speak_text is not None and recognize_speech_from_file is not None,
            "functions": {
                "speak_text": speak_text is not None,
                "recognize_speech": recognize_speech is not None,
                "recognize_speech_from_file": recognize_speech_from_file is not None,
                "check_stt_available": check_stt_available is not None,
            },
        },
        "transcription": {
            "available": state.transcriber is not None,
            "functions": {"universal_transcriber": UniversalTranscriber is not None},
        },
        "rag_service": {"available": rag_client is not None},
    }

    services_health = {}
    try:
        from backend.llm_client import get_llm_service
        import httpx

        service = await get_llm_service()

        async def check_diar():
            try:
                async with httpx.AsyncClient(timeout=2.0) as c:
                    r = await c.get(f"{service.client.diarization_url}/health")
                    return r.json() if r.status_code == 200 else {"status": "error"}
            except Exception:
                return {"status": "unreachable"}

        tasks = [
            service.client.health_check(),
            service.client.get_transcription_health(),
            service.client.get_tts_health(),
            service.client.get_ocr_health(),
            check_diar(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        keys = ["llm", "stt", "tts", "ocr", "diarization"]
        services_health = {k: (results[i] if not isinstance(results[i], Exception) else {"status": "error"})
                           for i, k in enumerate(keys)}
    except Exception as e:
        services_health = {"error": str(e)}

    return {"modules": module_status, "microservices": services_health, "timestamp": datetime.now().isoformat()}
