"""
routes/agents.py - агентная архитектура, оркестратор, multi-llm
"""

import logging
import os
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app_state import get_agent_orchestrator
from backend.schemas import AgentModeRequest, AgentStatusResponse, MultiLLMModelsRequest

router = APIRouter(prefix="/api/agent", tags=["agents"])
logger = logging.getLogger(__name__)


class ToolToggleBody(BaseModel):
    """Тело POST …/status: строгий bool (не str)."""
    is_active: bool = Field(default=False, description="Включить или выключить")


def _get_orchestrator_or_503():
    o = get_agent_orchestrator()
    if not o:
        raise HTTPException(status_code=503, detail="Агентная архитектура не инициализирована")
    return o


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status():
    try:
        o = get_agent_orchestrator()
        if o:
            return AgentStatusResponse(**o.get_status())
        return AgentStatusResponse(is_initialized=False, mode="unknown", available_agents=0, orchestrator_active=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode")
async def set_agent_mode(request: AgentModeRequest):
    try:
        o = _get_orchestrator_or_503()
        prev_mode = o.get_mode()
        o.set_mode(request.mode)
        # Выход из multi-LLM: выгрузить лишние GGUF из пула llm-svc 
        if prev_mode == "multi-llm" and request.mode != "multi-llm":
            try:
                try:
                    from backend.agent_llm_svc import USE_LLM_SVC
                    from backend.llm_client import get_llm_service
                except ModuleNotFoundError:
                    from agent_llm_svc import USE_LLM_SVC
                    from llm_client import get_llm_service
                if USE_LLM_SVC:
                    svc = await get_llm_service()
                    ok = await svc.client.unload_excess_llm_models()
                    await svc._sync_loaded_model_name_from_health()
                    logger.info(f"llm-svc pool trim после выхода из multi-llm: success={ok}")
            except Exception as e:
                logger.warning(f"Не удалось очистить пул llm-svc после multi-llm: {e}")
        return {"message": f"Режим изменён на: {request.mode}", "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-llm/models")
async def set_multi_llm_models(request: MultiLLMModelsRequest):
    try:
        o = _get_orchestrator_or_503()
        o.set_multi_llm_models(request.models)
        # Без фонового POST /v1/models/load: он гонялся параллельно с первым multi-LLM чатом и
        # давал двойную загрузку одной GGUF в llm-svc → обрыв соединения / падение процесса.
        # Догрузка второй модели — только в realtime.handlers._gen_one (asyncio.to_thread).
        return {"message": f"Модели установлены: {', '.join(request.models)}", "success": True,
                "models": request.models, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-llm/models")
async def get_multi_llm_models():
    try:
        o = _get_orchestrator_or_503()
        return {"models": o.get_multi_llm_models(), "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def get_available_agents():
    try:
        o = _get_orchestrator_or_503()
        agents = o.get_available_agents()
        return {"agents": agents, "count": len(agents), "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp/status")
async def get_mcp_status():
    try:
        _get_orchestrator_or_503()
        return {"mcp_status": {"initialized": False, "servers": 0, "tools": 0, "message": "MCP в разработке"},
                "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/status")
async def set_agent_status(agent_id: str, body: ToolToggleBody):
    try:
        o = _get_orchestrator_or_503()
        is_active = body.is_active
        o.set_agent_status(agent_id.strip(), is_active)
        return {"agent_id": agent_id, "is_active": is_active, "success": True,
                "message": f"Агент '{agent_id}' {'активирован' if is_active else 'деактивирован'}",
                "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tool/{tool_name}/status")
async def set_single_tool_status(tool_name: str, body: ToolToggleBody):
    """Вкл/выкл одного инструмента по имени (как в LangGraph tool_status)."""
    try:
        o = _get_orchestrator_or_503()
        is_active = body.is_active
        o.set_tool_status(tool_name, is_active)
        return {"tool_name": tool_name, "is_active": is_active, "success": True,
                "message": f"Инструмент '{tool_name}' {'включён' if is_active else 'выключен'}",
                "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/statuses")
async def get_all_agent_statuses():
    try:
        o = _get_orchestrator_or_503()
        return {"statuses": o.get_all_agent_statuses(), "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langgraph/status")
async def get_langgraph_status():
    try:
        o = _get_orchestrator_or_503()
        tools = o.get_available_tools()
        return {"langgraph_status": {"is_active": o.is_initialized, "initialized": o.is_initialized,
                "tools_available": len(tools), "memory_enabled": True, "orchestrator_type": "LangGraph",
                "orchestrator_active": o.is_orchestrator_active()},
                "success": True, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrator/toggle")
async def toggle_orchestrator(status: Dict[str, bool]):
    try:
        o = _get_orchestrator_or_503()
        is_active = status.get("is_active", True)
        o.set_orchestrator_status(is_active)
        return {"success": True, "orchestrator_active": is_active,
                "message": f"Оркестратор {'включен' if is_active else 'отключен'}",
                "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
