"""
routes/agents.py - агентная архитектура, оркестратор, multi-llm
"""

import os
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from backend.app_state import get_agent_orchestrator
from backend.auth.jwt_handler import get_current_user
from backend.schemas import AgentModeRequest, AgentStatusResponse
from backend.settings.cef_logger.cef_logger import domain_from_ldap_base_dn, log_cef_event
from backend.settings.logging import get_logger

router = APIRouter(prefix="/api/agent", tags=["agents"])
logger = get_logger(__name__)


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
        o.set_mode(request.mode)
        return {"message": f"Режим изменён на: {request.mode}", "success": True, "timestamp": datetime.now().isoformat()}
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
        from backend.mcp.platform import get_mcp_platform
        from backend.mcp.types import McpCallContext

        platform = get_mcp_platform()
        if not platform.initialized:
            return {
                "mcp_status": {
                    "initialized": False,
                    "servers_connected": 0,
                    "total_servers": 0,
                    "tools": 0,
                    "message": "MCP platform not initialized",
                },
                "success": True,
                "timestamp": datetime.now().isoformat(),
            }
        ctx = McpCallContext(user_id="system", username="system", is_admin=True)
        health = await platform.health(ctx)
        return {
            "mcp_status": {
                "initialized": health.get("initialized", False),
                "enabled": health.get("enabled", False),
                "servers_connected": health.get("servers_connected", 0),
                "total_servers": health.get("servers_total", 0),
                "tools": health.get("tools_total", 0),
                "servers": health.get("servers", []),
                "pool": health.get("pool", {}),
                "message": health.get("message"),
            },
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/status")
async def set_agent_status(
    request: Request,
    agent_id: str,
    body: ToolToggleBody,
    current_user: dict = Depends(get_current_user),
):
    try:
        o = _get_orchestrator_or_503()
        is_active = body.is_active
        o.set_agent_status(agent_id.strip(), is_active)
        _dom = domain_from_ldap_base_dn(os.getenv("LDAP_USER_SEARCH_BASE", ""))
        log_cef_event(
            "SEC004",
            request=request,
            current_user=current_user,
            status_code=200,
            extra={
                "cs1": agent_id.strip(),
                "cs1Label": "AgentName",
                "cs2": agent_id.strip(),
                "cs2Label": "AgentId",
                "duser": "all-users",
                "dntdom": _dom or None,
                "cs3": "agent_user" if is_active else "agent_disabled",
                "cs3Label": "AccessRole",
            },
        )
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
