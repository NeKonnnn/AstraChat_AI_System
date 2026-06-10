"""
Генерация изображений через ComfyUI: конфиг, intent из чата, вызов workflow.
"""

from __future__ import annotations

import copy
import logging
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.services.comfyui_image_generation import (
    ComfyImageGenError,
    apply_checkpoint_to_workflow,
    bytes_to_data_uri,
    fetch_comfyui_checkpoint_names,
    generate_images_via_comfyui,
    inject_workflow_inputs,
    load_workflow_template,
    resolve_workflow_file,
)

logger = logging.getLogger(__name__)

_DRAW_VERBS = (
    r"нарисуй|нарисуйте|нарисовать|сгенерируй|сгенерируйте|создай|создайте|"
    r"сделай|сделайте|покажи|отрисуй|draw|generate|create|make|paint"
)
_DRAW_NOUNS = r"картинку|картину|изображение|picture|image|art|арт"

_INTENT_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"(?i)^(?:/image|/img)\s+(.+)$"),
    re.compile(
        rf"(?i)^(?:пожалуйста\s+)?(?:{_DRAW_VERBS})\s+(?:мне\s+)?(?:{_DRAW_NOUNS})\s*"
        rf"(?:[:—\-–,]\s*|\s+)(.+)$"
    ),
    re.compile(rf"(?i)^(?:пожалуйста\s+)?(?:{_DRAW_VERBS})\s+(.+)$"),
]


def _workflow_base_dir() -> Path:
    routes_dir = Path(__file__).resolve().parent.parent / "routes"
    backend_dir = routes_dir.parent
    if (backend_dir / "config").is_dir():
        return backend_dir
    return backend_dir.parent


def _truthy_env(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None:
        return None
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _node_map_plain(node_map: Any) -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    if not node_map:
        return out
    for key, val in node_map.items():
        if isinstance(val, dict):
            node_id = val.get("node")
            field = val.get("input")
        else:
            node_id = getattr(val, "node", None)
            field = getattr(val, "input", None)
        if node_id is not None and field is not None:
            out[str(key)] = (str(node_id), str(field))
    return out


def get_image_generation_settings():
    from backend.settings import get_settings

    return get_settings().image_generation


def is_image_generation_configured() -> bool:
    try:
        cfg = get_image_generation_settings()
    except Exception:
        return False
    if not cfg or not cfg.enabled:
        return False
    url = (cfg.comfyui_base_url or "").strip()
    wf_rel = (cfg.workflow_path or "").strip()
    if not url or not wf_rel:
        return False
    if not _node_map_plain(cfg.node_map):
        return False
    try:
        return resolve_workflow_file(wf_rel, _workflow_base_dir()).exists()
    except Exception:
        return False


def extract_image_prompt_from_chat(message: str) -> Optional[str]:
    text = (message or "").strip()
    if not text:
        return None
    for pattern in _INTENT_PATTERNS:
        m = pattern.match(text)
        if m:
            prompt = (m.group(1) or "").strip()
            if prompt:
                return prompt
    return None


def is_image_generation_chat_request(message: str) -> bool:
    cfg = get_image_generation_settings()
    if not cfg or not cfg.enabled or not cfg.chat_triggers_enabled:
        return False
    return extract_image_prompt_from_chat(message) is not None


def _resolve_comfyui_url(cfg) -> str:
    env_url = (os.getenv("IMAGE_GEN_COMFYUI_URL") or "").strip().rstrip("/")
    if env_url:
        return env_url
    return (cfg.comfyui_base_url or "").strip().rstrip("/")


async def generate_images(
    *,
    prompt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    steps: Optional[int] = None,
    seed: Optional[int] = None,
) -> List[Tuple[bytes, str]]:
    cfg = get_image_generation_settings()
    if not cfg or not cfg.enabled:
        raise ComfyImageGenError("Генерация изображений отключена (image_generation.enabled)")

    url = _resolve_comfyui_url(cfg)
    wf_rel = (cfg.workflow_path or "").strip()
    node_map = _node_map_plain(cfg.node_map)
    if not url or not wf_rel:
        raise ComfyImageGenError("Задайте comfyui_base_url и workflow_path")
    if not node_map:
        raise ComfyImageGenError("Задайте image_generation.node_map")

    wf_path = resolve_workflow_file(wf_rel, _workflow_base_dir())
    workflow = copy.deepcopy(load_workflow_template(wf_path))

    inject: Dict[str, Any] = {"prompt": prompt.strip()}
    if width is None:
        width = int(getattr(cfg, "default_width", 512) or 512)
    if height is None:
        height = int(getattr(cfg, "default_height", 512) or 512)
    if steps is None:
        steps = int(getattr(cfg, "default_steps", 20) or 20)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    inject["width"] = width
    inject["height"] = height
    inject["steps"] = steps
    inject["seed"] = seed

    inject_workflow_inputs(workflow, node_map, inject)

    ckpt_pref = str(getattr(cfg, "checkpoint_name", None) or "").strip()
    ckpt_node = node_map.get("checkpoint")
    if ckpt_node and not ckpt_pref:
        node_id, field = ckpt_node
        node = workflow.get(str(node_id))
        if isinstance(node, dict):
            inputs = node.get("inputs") or {}
            if field in inputs:
                ckpt_pref = str(inputs[field] or "").strip()

    try:
        available_ckpts = await fetch_comfyui_checkpoint_names(url)
        apply_checkpoint_to_workflow(workflow, available_ckpts, preferred=ckpt_pref)
    except httpx.HTTPError as exc:
        raise ComfyImageGenError(f"Не удалось получить список моделей ComfyUI: {exc}") from exc

    return await generate_images_via_comfyui(
        comfyui_base_url=url,
        workflow=workflow,
        timeout_sec=float(cfg.request_timeout_sec),
        poll_interval_sec=float(cfg.poll_interval_sec),
    )


def build_generated_image_attachments(
    pairs: List[Tuple[bytes, str]],
    *,
    prompt: str,
) -> Tuple[str, Dict[str, Any]]:
    """Текст ответа + metadata.inline_attachments для MongoDB и сокета."""
    items: List[Dict[str, Any]] = []
    for idx, (data, mime) in enumerate(pairs, 1):
        data_uri = bytes_to_data_uri(data, mime)
        items.append(
            {
                "name": f"generated_{idx}.png",
                "contentType": "image",
                "data_uri": data_uri,
                "generated": True,
                "prompt": prompt[:500],
            }
        )

    if not items:
        return "Не удалось получить изображение от ComfyUI.", {}

    text = f"Готово! Сгенерировал изображение по запросу: «{prompt}»"
    return text, {"inline_attachments": items}


async def try_upload_generated_images_to_minio(
    pairs: List[Tuple[bytes, str]],
    *,
    prompt: str,
) -> List[Dict[str, Any]]:
    """Загружает PNG в MinIO и возвращает inline_attachments (с data_uri для мгновенного показа)."""
    from backend.app_state import minio_client

    _text, meta = build_generated_image_attachments(pairs, prompt=prompt)
    attachments = list(meta.get("inline_attachments") or [])
    if not minio_client or not attachments:
        return attachments

    bucket = os.getenv("MINIO_DOCUMENTS_BUCKET_NAME", "astrachat-documents")
    for idx, (data, mime) in enumerate(pairs):
        if idx >= len(attachments):
            break
        ext = ".png" if "png" in mime else ".jpg"
        object_name = minio_client.generate_object_name(prefix="gen_img_", extension=ext)
        try:
            minio_client.upload_file(data, object_name, content_type=mime, bucket_name=bucket)
            attachments[idx]["minio_object"] = object_name
            attachments[idx]["minio_bucket"] = bucket
        except Exception as exc:
            logger.warning("MinIO upload for generated image failed: %s", exc)
    return attachments


async def handle_chat_image_generation(user_message: str) -> Dict[str, Any]:
    """
    Возвращает {response, metadata, inline_attachments} или бросает ComfyImageGenError.
    """
    prompt = extract_image_prompt_from_chat(user_message)
    if not prompt:
        raise ComfyImageGenError("Не удалось извлечь промпт из сообщения")

    if not is_image_generation_configured():
        raise ComfyImageGenError(
            "Генерация изображений не настроена: включите image_generation.enabled, "
            "укажите node_map, workflow и запустите ComfyUI"
        )

    pairs = await generate_images(prompt=prompt)
    attachments = await try_upload_generated_images_to_minio(pairs, prompt=prompt)
    text, meta = build_generated_image_attachments(pairs, prompt=prompt)
    if attachments:
        meta = {"inline_attachments": attachments}
    return {
        "response": text,
        "metadata": meta,
        "inline_attachments": meta.get("inline_attachments") or [],
    }
