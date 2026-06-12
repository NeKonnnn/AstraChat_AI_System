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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.comfyui_image_generation import (
    ComfyImageGenError,
    bytes_to_data_uri,
    resolve_workflow_file,
)
from backend.services.comfyui_image_generation import fetch_comfyui_checkpoint_names
from backend.services.image_generation_presets import list_configured_presets, resolve_preset
from backend.services.image_generation_service import (
    _resolve_comfyui_url,
    _workflow_base_dir,
    generate_images,
    get_image_generation_settings,
    is_image_generation_configured,
    list_user_image_creations,
)
from backend.auth.jwt_handler import get_current_user

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


class ImagePresetItem(BaseModel):
    id: str
    label: str
    description: str = ""
    workflow_path: str = ""
    checkpoint_name: str = ""
    default_width: int = 1024
    default_height: int = 1024
    default_steps: int = 4
    available: bool = True


class ImagePresetsResponse(BaseModel):
    default_preset_id: str = ""
    presets: List[ImagePresetItem] = Field(default_factory=list)
    available_checkpoints: List[str] = Field(default_factory=list)


class ImageCreationItem(BaseModel):
    id: str
    message_id: str = ""
    conversation_id: str = ""
    conversation_title: str = ""
    prompt: str = ""
    name: str = ""
    created_at: str = ""
    minio_object: Optional[str] = None
    minio_bucket: Optional[str] = None
    has_data_uri: bool = False
    image_gen_preset_label: Optional[str] = None
    preview_url: Optional[str] = None


class ImageCreationsResponse(BaseModel):
    items: List[ImageCreationItem] = Field(default_factory=list)
    total: int = 0


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=16000)
    width: Optional[int] = Field(default=None, ge=64, le=8192)
    height: Optional[int] = Field(default=None, ge=64, le=8192)
    steps: Optional[int] = Field(default=None, ge=1, le=200)
    seed: Optional[int] = None
    preset_id: Optional[str] = None


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


@router.get("/presets", response_model=ImagePresetsResponse)
async def image_generation_presets():
    s = get_image_generation_settings()
    url = _resolve_comfyui_url(s)
    checkpoints: List[str] = []
    if url:
        try:
            checkpoints = await fetch_comfyui_checkpoint_names(url)
        except Exception:
            checkpoints = []

    ckpt_set = set(checkpoints)
    items: List[ImagePresetItem] = []
    for row in list_configured_presets():
        ckpt = str(row.get("checkpoint_name") or "").strip()
        available = not ckpt or ckpt in ckpt_set or any(
            c == ckpt or c.endswith(f"/{ckpt}") for c in checkpoints
        )
        items.append(
            ImagePresetItem(
                id=str(row.get("id") or ""),
                label=str(row.get("label") or row.get("id") or ""),
                description=str(row.get("description") or ""),
                workflow_path=str(row.get("workflow_path") or ""),
                checkpoint_name=ckpt,
                default_width=int(row.get("default_width") or 1024),
                default_height=int(row.get("default_height") or 1024),
                default_steps=int(row.get("default_steps") or 4),
                available=available,
            )
        )

    default_id = str(getattr(s, "default_preset_id", None) or "").strip()
    if not default_id and items:
        default_id = items[0].id
    resolved = resolve_preset(default_id)
    if resolved:
        default_id = str(resolved.get("id") or default_id)

    return ImagePresetsResponse(
        default_preset_id=default_id,
        presets=items,
        available_checkpoints=checkpoints,
    )


@router.get("/creations", response_model=ImageCreationsResponse)
async def image_generation_creations(
    limit: int = 200,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user.get("user_id") or "")
    username = str(current_user.get("username") or "")
    raw = await list_user_image_creations(
        user_id, username=username, limit=limit, offset=offset
    )
    items: List[ImageCreationItem] = []
    for row in raw:
        preview_url = row.get("preview_url")
        if not preview_url:
            mo = row.get("minio_object")
            mb = row.get("minio_bucket")
            if mo and mb:
                preview_url = f"/api/documents/inline-file?bucket={mb}&object={mo}"
        items.append(
            ImageCreationItem(
                id=str(row.get("id") or ""),
                message_id=str(row.get("message_id") or ""),
                conversation_id=str(row.get("conversation_id") or ""),
                conversation_title=str(row.get("conversation_title") or ""),
                prompt=str(row.get("prompt") or ""),
                name=str(row.get("name") or ""),
                created_at=str(row.get("created_at") or ""),
                minio_object=str(row.get("minio_object")) if row.get("minio_object") else None,
                minio_bucket=str(row.get("minio_bucket")) if row.get("minio_bucket") else None,
                has_data_uri=bool(row.get("has_data_uri")),
                image_gen_preset_label=row.get("image_gen_preset_label"),
                preview_url=preview_url,
            )
        )
    return ImageCreationsResponse(items=items, total=len(items))


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
            preset_id=body.preset_id,
        )
    except ComfyImageGenError as e:
        logger.warning("ComfyUI image gen failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e

    out: List[Dict[str, str]] = []
    for data, mime in pairs:
        out.append({"mime": mime, "data_uri": bytes_to_data_uri(data, mime)})
    return ImageGenerateResponse(images=out)
