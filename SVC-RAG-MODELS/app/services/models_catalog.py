"""Каталог моделей эмбеддингов и cross-encoder для UI выбора."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.core.config import settings

ModelKind = Literal["embedding", "reranker"]

# Известные модели HuggingFace (источник «huggingface»), если нет локальной копии.
_HF_EMBEDDING_CATALOG: List[Dict[str, str]] = [
    {
        "path": "huggingface/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "name": "paraphrase-multilingual-MiniLM-L12-v2",
        "display_name": "paraphrase-multilingual-MiniLM-L12-v2",
        "description": "Мультиязычные эмбеддинги MiniLM-L12 (по умолчанию).",
    },
    {
        "path": "huggingface/intfloat/multilingual-e5-small",
        "name": "multilingual-e5-small",
        "display_name": "multilingual-e5-small",
        "description": "Компактные мультиязычные эмбеддинги E5.",
    },
    {
        "path": "huggingface/BAAI/bge-small-en-v1.5",
        "name": "bge-small-en-v1.5",
        "display_name": "bge-small-en-v1.5",
        "description": "BGE small — эффективные англоязычные эмбеддинги.",
    },
]

_HF_RERANKER_CATALOG: List[Dict[str, str]] = [
    {
        "path": "huggingface/cross-encoder/ms-marco-MiniLM-L-6-v2",
        "name": "ms-marco-MiniLM-L-6-v2",
        "display_name": "ms-marco-MiniLM-L-6-v2",
        "description": "Cross-encoder MS MARCO MiniLM-L6 (по умолчанию).",
    },
    {
        "path": "huggingface/cross-encoder/ms-marco-MiniLM-L-12-v2",
        "name": "ms-marco-MiniLM-L-12-v2",
        "display_name": "ms-marco-MiniLM-L-12-v2",
        "description": "Cross-encoder MS MARCO MiniLM-L12 — точнее, но медленнее.",
    },
    {
        "path": "huggingface/cross-encoder/ms-marco-TinyBERT-L-6-v2",
        "name": "ms-marco-TinyBERT-L-6-v2",
        "display_name": "ms-marco-TinyBERT-L-6-v2",
        "description": "Лёгкий cross-encoder для быстрого реранкинга.",
    },
]

_RERANKER_HINTS = ("marco", "cross-encoder", "rerank", "ms-marco", "tinybert")
_EMBEDDING_HINTS = (
    "paraphrase",
    "embedding",
    "e5-",
    "bge-",
    "multilingual-minilm",
    "minilm-l12",
    "frida",
    "giga-",
)


def _guess_kind(folder_name: str, model_dir: str) -> Optional[ModelKind]:
    n = folder_name.lower()
    if any(h in n for h in _RERANKER_HINTS):
        return "reranker"
    if any(h in n for h in _EMBEDDING_HINTS):
        return "embedding"
    # sentence-transformers layout (modules.json) — почти всегда embedding,
    # даже если имя модели не из белого списка (например FRIDA).
    if os.path.isfile(os.path.join(model_dir, "modules.json")):
        return "embedding"
    if os.path.isfile(os.path.join(model_dir, "config_sentence_transformers.json")):
        return "embedding"
    return None


def _is_model_dir(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    for marker in ("config.json", "modules.json", "pytorch_model.bin", "model.safetensors"):
        if os.path.isfile(os.path.join(path, marker)):
            return True
    snap = os.path.join(path, "snapshots")
    if os.path.isdir(snap):
        for h in os.listdir(snap):
            if os.path.isfile(os.path.join(snap, h, "config.json")):
                return True
    return False


def _scan_local_models(models_dir: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not os.path.isdir(models_dir):
        return rows
    try:
        entries = sorted(os.listdir(models_dir))
    except OSError:
        return rows
    for entry in entries:
        full = os.path.join(models_dir, entry)
        if not _is_model_dir(full):
            continue
        kind = _guess_kind(entry, full)
        if kind is None:
            continue
        rows.append(
            {
                "path": f"local/{entry}",
                "name": entry,
                "display_name": entry,
                "source": "local",
                "kind": kind,
                "description": f"Локальная модель в {models_dir}",
                "available": True,
            }
        )
    return rows


def _hf_catalog(kind: ModelKind) -> List[Dict[str, Any]]:
    catalog = _HF_EMBEDDING_CATALOG if kind == "embedding" else _HF_RERANKER_CATALOG
    rows: List[Dict[str, Any]] = []
    for item in catalog:
        rows.append(
            {
                **item,
                "source": "huggingface",
                "kind": kind,
                "available": not settings.rag_models.offline,
            }
        )
    return rows


def _path_key(path: str) -> str:
    return (path or "").strip().lower()


def list_models(kind: Optional[ModelKind] = None) -> Dict[str, List[Dict[str, Any]]]:
    models_dir = os.path.abspath(settings.rag_models.models_dir)
    local_rows = _scan_local_models(models_dir)
    by_kind: Dict[str, List[Dict[str, Any]]] = {"embedding": [], "reranker": []}

    for row in local_rows:
        by_kind[row["kind"]].append(row)

    for hf_kind in ("embedding", "reranker"):
        local_paths = {_path_key(r["path"]) for r in by_kind[hf_kind]}
        for hf_row in _hf_catalog(hf_kind):  # type: ignore[arg-type]
            if _path_key(hf_row["path"]) not in local_paths:
                by_kind[hf_kind].append(hf_row)

    if kind is not None:
        return {kind: by_kind[kind]}
    return by_kind


def parse_model_path(model_path: str) -> Tuple[str, str]:
    raw = (model_path or "").strip()
    if not raw:
        raise ValueError("model_path пуст")
    if raw.startswith("local/"):
        return "local", raw[len("local/") :]
    if raw.startswith("huggingface/"):
        return "huggingface", raw[len("huggingface/") :]
    return "local", raw


def config_value_for_path(model_path: str) -> str:
    source, model_id = parse_model_path(model_path)
    if source == "huggingface":
        return model_id
    return model_id


def current_model_paths() -> Dict[str, Dict[str, str]]:
    models_dir = os.path.abspath(settings.rag_models.models_dir)
    emb_cfg = settings.rag_models.embedding_model or settings.rag_models.embedding_model_default
    rer_cfg = settings.rag_models.reranker_model or settings.rag_models.reranker_model_default

    def row(value: str, kind: ModelKind) -> Dict[str, str]:
        folder = value.split("/")[-1] if "/" in value else value
        local_path = os.path.join(models_dir, folder)
        if os.path.isdir(local_path):
            return {
                "path": f"local/{folder}",
                "name": folder,
                "display_name": folder,
                "source": "local",
                "kind": kind,
            }
        hf_id = value if "/" in value else (
            f"sentence-transformers/{value}" if kind == "embedding" else f"cross-encoder/{value}"
        )
        return {
            "path": f"huggingface/{hf_id}",
            "name": folder,
            "display_name": folder,
            "source": "huggingface",
            "kind": kind,
        }

    return {"embedding": row(emb_cfg, "embedding"), "reranker": row(rer_cfg, "reranker")}
