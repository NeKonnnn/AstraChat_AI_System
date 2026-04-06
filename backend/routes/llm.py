"""
Статус подключения к LLM (llm-svc) — для UI без знания URL на фронте.
"""

import logging
import os

from fastapi import APIRouter

router = APIRouter(prefix="/api/llm", tags=["llm"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def llm_connection_status():
    """
    Агрегированное состояние всех настроенных LLM-хостов.
    Фронт использует только этот эндпоинт (и /api/models), не URL llm-svc.
    """
    use_llm_svc = os.getenv("USE_LLM_SVC", "false").lower() == "true"
    if not use_llm_svc:
        return {
            "use_llm_svc": False,
            "connected": True,
            "hosts": [],
            "default_host_id": None,
            "message": None,
        }

    try:
        from backend.llm_client import get_llm_service

        service = await get_llm_service()
        hosts_out = []
        any_healthy = False
        for hid, base_url in service.client.llm_hosts.items():
            h = await service.client.health_check(host_id=hid)
            healthy = h.get("status") == "healthy"
            if healthy:
                any_healthy = True
            err = None if healthy else (h.get("error") or "unhealthy")
            hosts_out.append(
                {
                    "id": hid,
                    "healthy": healthy,
                    "error": err,
                }
            )

        msg = None
        if not any_healthy:
            msg = (
                "Подключиться к LLM не удалось. Проверьте, что сервис моделей запущен "
                "и настройки llm-svc на бэкенде (config / переменные окружения) указаны верно."
            )

        return {
            "use_llm_svc": True,
            "connected": any_healthy,
            "default_host_id": service.client.default_llm_host,
            "hosts": hosts_out,
            "message": msg,
        }
    except Exception as e:
        logger.exception("llm status: %s", e)
        return {
            "use_llm_svc": True,
            "connected": False,
            "hosts": [],
            "default_host_id": None,
            "message": f"Ошибка проверки LLM: {e}",
        }
