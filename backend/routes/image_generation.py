"""
Генерация изображений через ComfyUI (HTTP API). См. docs Open WebUI + ComfyUI.

Фронт и внешние клиенты вызывают только бэкенд; диффузия крутится в ComfyUI.
Из чата: «нарисуй кота» → backend/services/image_generation_service.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.comfyui_image_generation import (
    ComfyImageGenError,
    bytes_to_data_uri,
    resolve_workflow_file,
)
from backend.services.comfyui_image_generation import fetch_comfyui_checkpoint_names
from backend.services.image_generation_service import (
    _resolve_comfyui_url,
    _workflow_base_dir,
    generate_images,
    get_image_generation_settings,
    is_image_generation_configured,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image-generation", tags=["image-generation"])


class ImageGenStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    comfyui_reachable: Optional[bool] = None
    comfyui_error: Optional[str] = None
    workflow_resolved: Optional[str] = None
    has_node_map: bool
    chat_triggers_enabled: bool = True
    available_checkpoints: List[str] = Field(default_factory=list)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16000)
    width: Optional[int] = Field(default=None, ge=64, le=8192)
    height: Optional[int] = Field(default=None, ge=64, le=8192)
    steps: Optional[int] = Field(default=None, ge=1, le=200)
    seed: Optional[int] = None


class ImageGenerateResponse(BaseModel):
    images: List[Dict[str, str]] = Field(
        ...,
        description="Список объектов с полем data_uri (data:image/...;base64,...)",
    )


@router.get("/status", response_model=ImageGenStatusResponse)
async def image_generation_status():
    s = get_image_generation_settings()
    url = _resolve_comfyui_url(s)
    wf_path = (s.workflow_path or "").strip()
    configured = is_image_generation_configured()

    reachable: Optional[bool] = None
    err: Optional[str] = None
    if url:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
                r = await client.get(f"{url}/queue")
                reachable = r.status_code < 500
                if not reachable:
                    err = f"HTTP {r.status_code}"
        except Exception as e:
            reachable = False
            err = str(e)

    checkpoints: List[str] = []
    if url and reachable:
        try:
            checkpoints = await fetch_comfyui_checkpoint_names(url)
        except Exception:
            checkpoints = []

    return ImageGenStatusResponse(
        enabled=bool(s.enabled),
        configured=configured,
        comfyui_reachable=reachable,
        comfyui_error=err,
        workflow_resolved=str(resolve_workflow_file(wf_path, _workflow_base_dir())) if wf_path else None,
        has_node_map=bool(s.node_map),
        chat_triggers_enabled=bool(getattr(s, "chat_triggers_enabled", True)),
        available_checkpoints=checkpoints,
    )


@router.post("/generate", response_model=ImageGenerateResponse)
async def image_generation_generate(body: ImageGenerateRequest):
    s = get_image_generation_settings()
    if not s.enabled:
        raise HTTPException(status_code=503, detail="Генерация изображений отключена (image_generation.enabled)")

    try:
        pairs = await generate_images(
            prompt=body.prompt,
            width=body.width,
            height=body.height,
            steps=body.steps,
            seed=body.seed,
        )
    except ComfyImageGenError as e:
        logger.warning("ComfyUI image gen failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e

    out: List[Dict[str, str]] = []
    for data, mime in pairs:
        out.append({"mime": mime, "data_uri": bytes_to_data_uri(data, mime)})
    return ImageGenerateResponse(images=out)
