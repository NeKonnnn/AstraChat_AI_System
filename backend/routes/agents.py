"""
routes/agents.py - агентная архитектура, оркестратор, multi-llm
"""

import logging
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, HTTPException

from backend.app_state import get_agent_orchestrator
from backend.schemas import AgentModeRequest, AgentStatusResponse, MultiLLMModelsRequest

router = APIRouter(prefix="/api/agent", tags=["agents"])
logger = logging.getLogger(__name__)


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
        o.set_mode(request.mode)
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
async def set_agent_status(agent_id: str, status: Dict[str, bool]):
    try:
        o = _get_orchestrator_or_503()
        is_active = status.get("is_active", True)
        o.set_agent_status(agent_id, is_active)
        return {"agent_id": agent_id, "is_active": is_active, "success": True,
                "message": f"Агент '{agent_id}' {'активирован' if is_active else 'деактивирован'}",
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
