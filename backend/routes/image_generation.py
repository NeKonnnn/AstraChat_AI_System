"""
Генерация изображений через ComfyUI (HTTP API). См. docs Open WebUI + ComfyUI.

Фронт и внешние клиенты вызывают только бэкенд; GGUF-диффузия крутится в ComfyUI с нодой Unet Loader (GGUF).
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.settings import get_settings
from backend.services.comfyui_image_generation import (
    ComfyImageGenError,
    bytes_to_data_uri,
    inject_workflow_inputs,
    load_workflow_template,
    generate_images_via_comfyui,
    resolve_workflow_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image-generation", tags=["image-generation"])


def _workflow_base_dir() -> Path:
    """
    Каталог, относительно которого задан workflow_path в config.
    В репозитории: папка backend/ (там лежит config/comfy_workflows).
    В Docker (backend смонтирован в /app): /app.
    """
    routes_dir = Path(__file__).resolve().parent
    backend_dir = routes_dir.parent
    if (backend_dir / "config").is_dir():
        return backend_dir
    return backend_dir.parent


_workflow_mtime: float = 0.0
_workflow_cached_path: Optional[str] = None
_workflow_cached: Optional[Dict[str, Any]] = None


def _node_map_plain(cfg) -> Dict[str, tuple]:
    out: Dict[str, tuple] = {}
    for k, v in (cfg.node_map or {}).items():
        out[str(k)] = (str(v.node), str(v.input))
    return out


def _get_workflow_dict(workflow_rel: str) -> Dict[str, Any]:
    global _workflow_mtime, _workflow_cached_path, _workflow_cached
    path = resolve_workflow_file(workflow_rel, _workflow_base_dir())
    try:
        mt = path.stat().st_mtime
    except OSError:
        mt = 0.0
    key = str(path)
    if _workflow_cached is not None and _workflow_cached_path == key and mt == _workflow_mtime:
        return _workflow_cached
    wf = load_workflow_template(path)
    _workflow_cached = wf
    _workflow_cached_path = key
    _workflow_mtime = mt
    return wf


class ImageGenStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    comfyui_reachable: Optional[bool] = None
    comfyui_error: Optional[str] = None
    workflow_resolved: Optional[str] = None
    has_node_map: bool


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
    s = get_settings().image_generation
    url = (s.comfyui_base_url or "").strip().rstrip("/")
    wf_path = (s.workflow_path or "").strip()
    configured = bool(
        s.enabled
        and url
        and wf_path
        and s.node_map
        and resolve_workflow_file(wf_path, _workflow_base_dir()).exists()
    )

    reachable: Optional[bool] = None
    err: Optional[str] = None
    if url:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
                r = await client.get(f"{url}/queue")
                reachable = r.status_code < 500
                if not reachable:
                    err = f"HTTP {r.status_code}"
        except Exception as e:
            reachable = False
            err = str(e)

    return ImageGenStatusResponse(
        enabled=bool(s.enabled),
        configured=configured,
        comfyui_reachable=reachable,
        comfyui_error=err,
        workflow_resolved=str(resolve_workflow_file(wf_path, _workflow_base_dir())) if wf_path else None,
        has_node_map=bool(s.node_map),
    )


@router.post("/generate", response_model=ImageGenerateResponse)
async def image_generation_generate(body: ImageGenerateRequest):
    s = get_settings().image_generation
    if not s.enabled:
        raise HTTPException(status_code=503, detail="Генерация изображений отключена (image_generation.enabled)")
    url = (s.comfyui_base_url or "").strip().rstrip("/")
    wf_rel = (s.workflow_path or "").strip()
    if not url or not wf_rel:
        raise HTTPException(
            status_code=503,
            detail="Задайте image_generation.comfyui_base_url и workflow_path в config.yml или через IMAGE_GEN_*",
        )
    if not s.node_map:
        raise HTTPException(
            status_code=503,
            detail="Задайте image_generation.node_map (сопоставление prompt/width/height/steps с нодами workflow)",
        )

    try:
        wf = _get_workflow_dict(wf_rel)
    except ComfyImageGenError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    wf_work = copy.deepcopy(wf)
    nm = _node_map_plain(s)
    inject: Dict[str, Any] = {"prompt": body.prompt}
    if body.width is not None:
        inject["width"] = body.width
    if body.height is not None:
        inject["height"] = body.height
    if body.steps is not None:
        inject["steps"] = body.steps
    if body.seed is not None:
        inject["seed"] = body.seed

    try:
        inject_workflow_inputs(wf_work, nm, inject)
    except ComfyImageGenError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        pairs = await generate_images_via_comfyui(
            comfyui_base_url=url,
            workflow=wf_work,
            timeout_sec=float(s.request_timeout_sec),
            poll_interval_sec=float(s.poll_interval_sec),
        )
    except ComfyImageGenError as e:
        logger.warning("ComfyUI image gen failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e

    out: List[Dict[str, str]] = []
    for data, mime in pairs:
        out.append({"mime": mime, "data_uri": bytes_to_data_uri(data, mime)})
    return ImageGenerateResponse(images=out)
