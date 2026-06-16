"""
Генерация изображений через ComfyUI: конфиг, intent из чата, вызов workflow.
"""

from __future__ import annotations

import copy
import logging
import os
import random
import re
import uuid
from datetime import datetime
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
    preset_id: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    cfg: Optional[float] = None,
    denoise: Optional[float] = None,
    reference_image_bytes: Optional[bytes] = None,
    reference_image_filename: str = "reference.png",
) -> List[Tuple[bytes, str]]:
    from backend.services.comfyui_image_generation import upload_image_to_comfyui
    from backend.services.image_generation_presets import (
        apply_preset_to_generation_params,
        resolve_preset,
    )

    cfg_settings = get_image_generation_settings()
    if not cfg_settings or not cfg_settings.enabled:
        raise ComfyImageGenError("Генерация изображений отключена (image_generation.enabled)")

    preset = resolve_preset(preset_id)
    gen = apply_preset_to_generation_params(preset, width=width, height=height, steps=steps)
    resolved_preset_id = str(gen.get("preset_id") or "")
    if preset_id and resolved_preset_id and str(preset_id).strip() != resolved_preset_id:
        logger.warning(
            "Пресет %r не найден, используем %r (%s)",
            preset_id,
            resolved_preset_id,
            gen.get("preset_label"),
        )

    url = _resolve_comfyui_url(cfg_settings)
    wf_rel = (gen.get("workflow_path") or "").strip()
    node_map = _node_map_plain(gen.get("node_map") or cfg_settings.node_map)
    if not url or not wf_rel:
        raise ComfyImageGenError("Задайте comfyui_base_url и workflow_path")
    if not node_map:
        raise ComfyImageGenError("Задайте image_generation.node_map или node_map в пресете")

    wf_path = resolve_workflow_file(wf_rel, _workflow_base_dir())
    workflow = copy.deepcopy(load_workflow_template(wf_path))

    inject: Dict[str, Any] = {"prompt": prompt.strip()}
    width = int(gen["width"])
    height = int(gen["height"])
    steps = int(gen["steps"])
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    inject["width"] = width
    inject["height"] = height
    inject["steps"] = steps
    inject["seed"] = seed
    if negative_prompt is not None and str(negative_prompt).strip():
        inject["negative_prompt"] = str(negative_prompt).strip()
    if cfg is not None:
        inject["cfg"] = float(cfg)
    if denoise is not None:
        inject["denoise"] = float(denoise)

    if reference_image_bytes and node_map.get("reference_image"):
        uploaded_name = await upload_image_to_comfyui(
            url,
            reference_image_bytes,
            reference_image_filename,
        )
        inject["reference_image"] = uploaded_name

    inject_workflow_inputs(workflow, node_map, inject)

    ckpt_pref = str(gen.get("checkpoint_name") or getattr(cfg_settings, "checkpoint_name", None) or "").strip()
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
        chosen_ckpt = apply_checkpoint_to_workflow(
            workflow,
            available_ckpts,
            preferred=ckpt_pref,
            strict_preferred=bool(ckpt_pref),
        )
    except httpx.HTTPError as exc:
        raise ComfyImageGenError(f"Не удалось получить список моделей ComfyUI: {exc}") from exc

    logger.info(
        "ComfyUI image gen: preset=%s (%s) workflow=%s checkpoint=%s size=%sx%s steps=%s",
        resolved_preset_id or preset_id,
        gen.get("preset_label"),
        wf_rel,
        chosen_ckpt,
        width,
        height,
        steps,
    )

    return await generate_images_via_comfyui(
        comfyui_base_url=url,
        workflow=workflow,
        timeout_sec=float(cfg_settings.request_timeout_sec),
        poll_interval_sec=float(cfg_settings.poll_interval_sec),
    )


def resolve_comfyui_public_url(cfg=None) -> str:
    if cfg is None:
        cfg = get_image_generation_settings()
    env_pub = (os.getenv("IMAGE_GEN_COMFYUI_PUBLIC_URL") or "").strip().rstrip("/")
    if env_pub:
        return env_pub
    pub = (getattr(cfg, "comfyui_public_url", None) or "").strip().rstrip("/")
    if pub:
        return pub
    return _resolve_comfyui_url(cfg)


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


def metadata_for_mongodb_storage(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Убирает тяжёлые data_uri из metadata перед записью в MongoDB (остаются MinIO-ссылки)."""
    if not metadata:
        return {}
    meta = dict(metadata)
    attachments = meta.get("inline_attachments")
    if not isinstance(attachments, list):
        return meta
    stored: List[Dict[str, Any]] = []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        item = dict(att)
        if item.get("minio_object") and item.get("minio_bucket"):
            item.pop("data_uri", None)
        stored.append(item)
    meta["inline_attachments"] = stored
    return meta


def build_initial_image_variant_metadata(stored_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Первый вариант сгенерированного изображения в metadata сообщения."""
    meta = dict(stored_meta or {})
    attachments = list(meta.get("inline_attachments") or [])
    meta["image_variants"] = [{"inline_attachments": attachments}]
    meta["current_image_variant_index"] = 0
    meta["inline_attachments"] = attachments
    return meta


def append_image_variant_metadata(
    existing_meta: Dict[str, Any],
    new_stored_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Добавляет новый вариант изображения к существующему сообщению."""
    meta = dict(existing_meta or {})
    new_attachments = list((new_stored_meta or {}).get("inline_attachments") or [])
    variants = meta.get("image_variants")
    if not isinstance(variants, list) or not variants:
        old = meta.get("inline_attachments") or []
        variants = [{"inline_attachments": old}] if old else []
    else:
        variants = list(variants)
    variants.append({"inline_attachments": new_attachments})
    meta["image_variants"] = variants
    meta["current_image_variant_index"] = len(variants) - 1
    meta["inline_attachments"] = new_attachments
    for key in ("image_gen_preset_id", "image_gen_preset_label"):
        if new_stored_meta.get(key):
            meta[key] = new_stored_meta[key]
    return metadata_for_mongodb_storage(meta)


def _restore_data_uri_in_variant_metadata(
    merged_meta: Dict[str, Any],
    raw_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Восстанавливает data_uri из сырого metadata для сохранения в image_creations."""
    meta = copy.deepcopy(merged_meta)
    raw_atts = raw_metadata.get("inline_attachments") or []
    if not isinstance(raw_atts, list) or not raw_atts:
        return meta
    current_idx = int(meta.get("current_image_variant_index") or 0)
    variants = meta.get("image_variants")
    if not isinstance(variants, list) or current_idx >= len(variants):
        return meta
    block = variants[current_idx]
    if not isinstance(block, dict):
        return meta
    stored_atts = block.get("inline_attachments")
    if not isinstance(stored_atts, list):
        return meta
    for i, att in enumerate(stored_atts):
        if not isinstance(att, dict) or i >= len(raw_atts):
            continue
        raw_att = raw_atts[i]
        if isinstance(raw_att, dict) and raw_att.get("data_uri"):
            att["data_uri"] = raw_att["data_uri"]
    inline_atts = meta.get("inline_attachments")
    if isinstance(inline_atts, list):
        for i, att in enumerate(inline_atts):
            if not isinstance(att, dict) or i >= len(raw_atts):
                continue
            raw_att = raw_atts[i]
            if isinstance(raw_att, dict) and raw_att.get("data_uri"):
                att["data_uri"] = raw_att["data_uri"]
    return meta


IMAGE_CREATIONS_COLLECTION = "image_creations"
_creations_indexes_ready = False


def _build_user_id_filter(user_ids: List[str]) -> Dict[str, Any]:
    if len(user_ids) == 1:
        uid = user_ids[0]
        return {
            "$or": [
                {"user_id": uid},
                {"user_id": {"$regex": f"^{re.escape(uid)}$", "$options": "i"}},
            ]
        }
    or_clauses: List[Dict[str, Any]] = []
    for uid in user_ids:
        or_clauses.append({"user_id": uid})
        or_clauses.append({"user_id": {"$regex": f"^{re.escape(uid)}$", "$options": "i"}})
    return {"$or": or_clauses}


async def _get_image_creations_collection():
    from backend.database.init_db import get_conversation_repository

    repo = get_conversation_repository()
    return repo.db_connection.get_collection(IMAGE_CREATIONS_COLLECTION)


async def _ensure_image_creations_indexes() -> None:
    global _creations_indexes_ready
    if _creations_indexes_ready:
        return
    collection = await _get_image_creations_collection()
    await collection.create_index("id", unique=True)
    await collection.create_index("user_id")
    await collection.create_index([("user_id", 1), ("created_at", -1)])
    _creations_indexes_ready = True


def _prompt_from_attachment(att: Dict[str, Any], msg_content: str) -> str:
    prompt = str(att.get("prompt") or "").strip()
    if prompt:
        return prompt
    m = re.search(r"по запросу:\s*«([^»]+)»", msg_content, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _creation_dict_from_attachment(
    *,
    user_id: str,
    message_id: str,
    conversation_id: str,
    conversation_title: str,
    msg_content: str,
    att: Dict[str, Any],
    vidx: int,
    idx: int,
    created_at: str = datetime.utcnow().isoformat(),
    preset_label: Optional[str] = None,
) -> Dict[str, Any]:
    data_uri = att.get("data_uri")
    stored_att = dict(att)
    return {
        "id": f"{message_id}:{vidx}:{idx}",
        "user_id": user_id,
        "message_id": message_id,
        "conversation_id": conversation_id,
        "conversation_title": conversation_title,
        "prompt": _prompt_from_attachment(att, msg_content),
        "name": str(att.get("name") or f"generated_{idx + 1}.png"),
        "created_at": created_at or datetime.utcnow().isoformat(),
        "minio_object": att.get("minio_object"),
        "minio_bucket": att.get("minio_bucket"),
        "attachment": stored_att,
        "has_data_uri": bool(data_uri),
        "image_gen_preset_label": preset_label,
    }


def _public_creation_row(row: Dict[str, Any]) -> Dict[str, Any]:
    att = row.get("attachment") if isinstance(row.get("attachment"), dict) else {}
    data_uri = att.get("data_uri")
    preview_url: Optional[str] = None
    mo = row.get("minio_object") or att.get("minio_object")
    mb = row.get("minio_bucket") or att.get("minio_bucket")
    if data_uri:
        preview_url = str(data_uri)
    elif mo and mb:
        from urllib.parse import quote

        preview_url = (
            f"/api/documents/inline-file?bucket={quote(str(mb), safe='')}"
            f"&object={quote(str(mo), safe='')}"
        )
    return {
        "id": str(row.get("id") or ""),
        "message_id": str(row.get("message_id") or ""),
        "conversation_id": str(row.get("conversation_id") or ""),
        "conversation_title": str(row.get("conversation_title") or ""),
        "prompt": str(row.get("prompt") or ""),
        "name": str(row.get("name") or ""),
        "created_at": str(row.get("created_at") or ""),
        "minio_object": str(mo) if mo else None,
        "minio_bucket": str(mb) if mb else None,
        "has_data_uri": bool(data_uri),
        "image_gen_preset_label": row.get("image_gen_preset_label"),
        "preview_url": preview_url,
    }


async def _scan_conversations_for_creations(
    user_ids: List[str],
    *,
    limit: int = 5000,
) -> List[Dict[str, Any]]:
    from backend.database.init_db import get_conversation_repository

    repo = get_conversation_repository()
    collection = repo._get_collection()
    cursor = collection.find(
        _build_user_id_filter(user_ids),
        {"conversation_id": 1, "title": 1, "messages": 1, "updated_at": 1, "user_id": 1},
    ).sort("updated_at", -1)

    creations: List[Dict[str, Any]] = []
    async for doc in cursor:
        if len(creations) >= limit:
            break
        conv_id = str(doc.get("conversation_id") or "")
        conv_title = str(doc.get("title") or "")
        owner_id = str(doc.get("user_id") or user_ids[0])
        for msg in doc.get("messages") or []:
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            msg_content = str(msg.get("content") or "")
            meta = msg.get("metadata") or {}
            if not isinstance(meta, dict):
                continue
            msg_id = str(msg.get("message_id") or "")
            ts = msg.get("timestamp")
            ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")

            variant_blocks: List[List[Dict[str, Any]]] = []
            raw_variants = meta.get("image_variants")
            if isinstance(raw_variants, list) and raw_variants:
                for block in raw_variants:
                    if isinstance(block, dict):
                        atts = block.get("inline_attachments") or []
                        if isinstance(atts, list):
                            variant_blocks.append([a for a in atts if isinstance(a, dict)])
            else:
                atts = meta.get("inline_attachments") or []
                if isinstance(atts, list):
                    variant_blocks.append([a for a in atts if isinstance(a, dict)])

            for vidx, attachments in enumerate(variant_blocks):
                for idx, att in enumerate(attachments):
                    if not _is_generated_image_attachment(att, msg_content):
                        continue
                    creations.append(
                        _creation_dict_from_attachment(
                            user_id=owner_id,
                            message_id=msg_id,
                            conversation_id=conv_id,
                            conversation_title=conv_title,
                            msg_content=msg_content,
                            att=att,
                            vidx=vidx,
                            idx=idx,
                            created_at=ts_iso,
                            preset_label=meta.get("image_gen_preset_label"),
                        )
                    )
    creations.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return creations


async def _upsert_creation_rows(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    await _ensure_image_creations_indexes()
    collection = await _get_image_creations_collection()
    for row in rows:
        creation_id = str(row.get("id") or "")
        user_id = str(row.get("user_id") or "")
        if not creation_id or not user_id:
            continue
        await collection.replace_one({"id": creation_id, "user_id": user_id}, row, upsert=True)


async def _maybe_backfill_image_creations(user_ids: List[str]) -> None:
    collection = await _get_image_creations_collection()
    count = await collection.count_documents(_build_user_id_filter(user_ids))
    if count > 0:
        return
    rows = await _scan_conversations_for_creations(user_ids)
    await _upsert_creation_rows(rows)


async def _repair_missing_creation_data_uris(user_ids: List[str], *, limit: int = 100) -> None:
    """Подтягивает data_uri из MinIO для старых записей image_creations без превью."""
    from backend.app_state import minio_client

    if not minio_client:
        return
    collection = await _get_image_creations_collection()
    user_filter = _build_user_id_filter(user_ids)
    query = {
        "$and": [
            user_filter,
            {"minio_object": {"$exists": True, "$ne": None}},
            {"minio_bucket": {"$exists": True, "$ne": None}},
            {
                "$or": [
                    {"attachment.data_uri": {"$exists": False}},
                    {"attachment.data_uri": None},
                    {"attachment.data_uri": ""},
                ]
            },
        ]
    }
    cursor = collection.find(query).limit(limit)
    async for doc in cursor:
        att = doc.get("attachment") if isinstance(doc.get("attachment"), dict) else {}
        mo = str(doc.get("minio_object") or att.get("minio_object") or "")
        mb = str(doc.get("minio_bucket") or att.get("minio_bucket") or "")
        if not mo or not mb:
            continue
        try:
            data = minio_client.download_file(mo, bucket_name=mb)
            repaired_att = dict(att)
            repaired_att["data_uri"] = bytes_to_data_uri(data, "image/png")
            await collection.update_one(
                {"id": doc.get("id"), "user_id": doc.get("user_id")},
                {"$set": {"attachment": repaired_att, "has_data_uri": True}},
            )
        except Exception as exc:
            logger.debug("repair image creation preview %s/%s: %s", mb, mo, exc)


async def persist_image_creations_from_metadata(
    *,
    user_id: str,
    conversation_id: Optional[str],
    message_id: str,
    content: str,
    metadata: Dict[str, Any],
    conversation_title: str = "",
    only_variant_index: Optional[int] = None,
    created_at: Optional[str] = None,
) -> None:
    """Сохраняет сгенерированные картинки в отдельную коллекцию (не удаляются с чатом)."""
    uid = str(user_id or "").strip()
    mid = str(message_id or "").strip()
    if not uid or not mid:
        return

    raw_variants = metadata.get("image_variants")
    variant_blocks: List[List[Dict[str, Any]]] = []
    if isinstance(raw_variants, list) and raw_variants:
        for block in raw_variants:
            if isinstance(block, dict):
                atts = block.get("inline_attachments") or []
                if isinstance(atts, list):
                    variant_blocks.append([a for a in atts if isinstance(a, dict)])
    else:
        atts = metadata.get("inline_attachments") or []
        if isinstance(atts, list):
            variant_blocks.append([a for a in atts if isinstance(a, dict)])

    created_at_value = created_at or datetime.utcnow().isoformat()
    rows: List[Dict[str, Any]] = []
    for vidx, attachments in enumerate(variant_blocks):
        if only_variant_index is not None and vidx != only_variant_index:
            continue
        for idx, att in enumerate(attachments):
            if not _is_generated_image_attachment(att, content):
                continue
            rows.append(
                _creation_dict_from_attachment(
                    user_id=uid,
                    message_id=mid,
                    conversation_id=str(conversation_id or ""),
                    conversation_title=conversation_title,
                    msg_content=content,
                    att=att,
                    vidx=vidx,
                    idx=idx,
                    created_at=created_at_value,
                    preset_label=metadata.get("image_gen_preset_label"),
                )
            )
    await _upsert_creation_rows(rows)


async def persist_image_creations_from_conversation(conv: Any) -> None:
    """Перед удалением чата сохраняет его картинки в image_creations."""
    user_id = str(getattr(conv, "user_id", None) or "")
    conv_id = str(getattr(conv, "conversation_id", None) or "")
    conv_title = str(getattr(conv, "title", None) or "")
    if not user_id:
        return
    for msg in getattr(conv, "messages", None) or []:
        if getattr(msg, "role", None) != "assistant":
            continue
        meta = getattr(msg, "metadata", None) or {}
        if not isinstance(meta, dict):
            continue
        content = str(getattr(msg, "content", None) or "")
        msg_id = str(getattr(msg, "message_id", None) or "")
        if not msg_id:
            continue
        ts = getattr(msg, "timestamp", None)
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
        try:
            await persist_image_creations_from_metadata(
                user_id=user_id,
                conversation_id=conv_id,
                message_id=msg_id,
                content=content,
                metadata=meta,
                conversation_title=conv_title,
                created_at=ts_iso or None,
            )
        except Exception as exc:
            logger.warning("Не удалось сохранить creations из чата %s: %s", conv_id, exc)


async def save_image_generation_assistant_message(
    *,
    content: str,
    metadata: Dict[str, Any],
    conversation_id: Optional[str],
    project_id: Optional[str],
    user_id: Optional[str],
    message_id: Optional[str] = None,
    regenerate: bool = False,
    assistant_message_id: Optional[str] = None,
) -> bool:
    """Сохраняет или обновляет сообщение ассистента с вариантами изображений."""
    from backend.database.init_db import get_conversation_repository
    from backend.database.memory_service import save_dialog_entry, save_dialog_entry_to_project

    stored_meta = metadata_for_mongodb_storage(metadata)

    if regenerate and assistant_message_id and conversation_id:
        try:
            repo = get_conversation_repository()
        except RuntimeError:
            logger.warning("MongoDB недоступен для обновления варианта image gen")
            return False
        conv = await repo.get_conversation(conversation_id)
        if not conv:
            logger.warning("Диалог %s не найден для image regen", conversation_id)
            return False
        existing = None
        for msg in conv.messages or []:
            if msg.message_id == assistant_message_id:
                existing = msg
                break
        if not existing:
            logger.warning("Сообщение %s не найдено для image regen", assistant_message_id)
            return False
        merged = append_image_variant_metadata(existing.metadata or {}, stored_meta)
        ok = await repo.update_assistant_message(
            conversation_id,
            assistant_message_id,
            content=content,
            metadata=merged,
        )
        if ok:
            try:
                persist_meta = _restore_data_uri_in_variant_metadata(merged, metadata)
                await persist_image_creations_from_metadata(
                    user_id=str(user_id or ""),
                    conversation_id=conversation_id,
                    message_id=assistant_message_id,
                    content=content,
                    metadata=persist_meta,
                    conversation_title=str(conv.title or ""),
                    only_variant_index=int(merged.get("current_image_variant_index") or 0),
                )
            except Exception as exc:
                logger.warning("Не удалось сохранить image creation: %s", exc)
        return ok

    effective_message_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
    full_meta = build_initial_image_variant_metadata(stored_meta)
    persist_meta = build_initial_image_variant_metadata(dict(metadata or {}))
    conv_title = ""
    try:
        if conversation_id:
            conv = await get_conversation_repository().get_conversation(conversation_id)
            conv_title = str(conv.title or "") if conv else ""
    except Exception:
        pass
    try:
        if project_id:
            ok = await save_dialog_entry_to_project(
                "assistant",
                content,
                project_id,
                conversation_id,
                message_id=effective_message_id,
                metadata=full_meta,
                user_id=user_id,
            )
        else:
            await save_dialog_entry(
                "assistant",
                content,
                full_meta,
                effective_message_id,
                conversation_id,
                user_id=user_id,
            )
            ok = True
        if ok:
            try:
                await persist_image_creations_from_metadata(
                    user_id=str(user_id or ""),
                    conversation_id=conversation_id,
                    message_id=effective_message_id,
                    content=content,
                    metadata=persist_meta,
                    conversation_title=conv_title,
                )
            except Exception as exc:
                logger.warning("Не удалось сохранить image creation: %s", exc)
        return ok
    except Exception as exc:
        logger.warning("Не удалось сохранить image gen сообщение: %s", exc)
        return False


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


async def handle_chat_image_generation(
    user_message: str,
    *,
    preset_id: Optional[str] = None,
) -> Dict[str, Any]:
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

    from backend.services.image_generation_presets import apply_preset_to_generation_params, resolve_preset

    effective_preset = resolve_preset(preset_id)
    gen_plan = apply_preset_to_generation_params(effective_preset, width=None, height=None, steps=None)

    pairs = await generate_images(prompt=prompt, preset_id=preset_id or gen_plan.get("preset_id"))
    attachments = await try_upload_generated_images_to_minio(pairs, prompt=prompt)
    text, meta = build_generated_image_attachments(pairs, prompt=prompt)
    if attachments:
        meta = {"inline_attachments": attachments}
    if effective_preset:
        meta = dict(meta)
        meta["image_gen_preset_id"] = effective_preset.get("id")
        meta["image_gen_preset_label"] = effective_preset.get("label")
        meta["image_gen_workflow_path"] = gen_plan.get("workflow_path")
        meta["image_gen_checkpoint"] = gen_plan.get("checkpoint_name")
        meta["image_gen_width"] = gen_plan.get("width")
        meta["image_gen_height"] = gen_plan.get("height")
        meta["image_gen_steps"] = gen_plan.get("steps")
        plan_label = gen_plan.get("preset_label") or effective_preset.get("label")
        if plan_label:
            text = (
                f"{text}\n\n_Пресет: {plan_label} · {gen_plan.get('width')}×{gen_plan.get('height')} · "
                f"{gen_plan.get('checkpoint_name') or 'checkpoint из workflow'}_"
            )
    return {
        "response": text,
        "metadata": meta,
        "inline_attachments": meta.get("inline_attachments") or [],
    }


def _is_generated_image_attachment(att: Dict[str, Any], msg_content: str) -> bool:
    if att.get("contentType") != "image":
        return False
    if att.get("generated") is True:
        return True
    name = str(att.get("name") or "")
    if name.startswith("generated_"):
        return True
    if str(att.get("prompt") or "").strip():
        return True
    content = msg_content or ""
    return "Сгенерировал изображение" in content or "image_generation" in content


async def list_user_image_creations(
    user_id: str,
    *,
    username: str = "",
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Сгенерированные изображения пользователя из отдельной коллекции (переживают удаление чата)."""
    user_ids = [x for x in {str(user_id or "").strip(), str(username or "").strip()} if x]
    if not user_ids:
        return []

    try:
        await _maybe_backfill_image_creations(user_ids)
        await _repair_missing_creation_data_uris(user_ids)
        await _ensure_image_creations_indexes()
        collection = await _get_image_creations_collection()
    except RuntimeError:
        return []

    user_filter = _build_user_id_filter(user_ids)
    cursor = collection.find(user_filter).sort("created_at", -1).skip(offset).limit(limit)
    rows: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        rows.append(_public_creation_row(doc))
    return rows
