"""In-process semantic cache для ответов поиска RAG (ключ: нормализованный запрос + параметры + версия индекса)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_store: Dict[str, Tuple[float, List[Tuple[str, float, Optional[int], Optional[int]]]]] = {}
_index_version = 0


def _env_bool(name: str) -> bool:
    v = os.getenv(name, "").strip().lower()
    return v in ("1", "true", "yes", "on")


def semantic_cache_enabled() -> bool:
    return _env_bool("RAG_SEMANTIC_CACHE")


def bump_rag_semantic_cache() -> None:
    """Сброс кэша при загрузке/удалении документов (новая версия индекса)."""
    global _index_version
    with _lock:
        _index_version += 1
        _store.clear()
    logger.debug("[RAG cache] bump: version=%s", _index_version)


def _ttl_seconds() -> float:
    try:
        return max(30.0, float(os.getenv("RAG_SEMANTIC_CACHE_TTL", "300")))
    except ValueError:
        return 300.0


def make_cache_key(
    path: str,
    normalized_query: str,
    k: int,
    strategy: Optional[str],
    document_id: Optional[int],
    use_reranking: Optional[bool],
    filters: Optional[Dict[str, Any]],
    project_id: Optional[str],
    *,
    rag_fix_typos: bool = False,
    rag_multi_query: bool = False,
    rag_hyde: bool = False,
) -> str:
    payload = {
        "v": _index_version,
        "path": path,
        "q": normalized_query,
        "k": k,
        "strategy": strategy,
        "document_id": document_id,
        "use_reranking": use_reranking,
        "filters": filters or {},
        "project_id": project_id,
        "rag_fix_typos": rag_fix_typos,
        "rag_multi_query": rag_multi_query,
        "rag_hyde": rag_hyde,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(key: str) -> Optional[List[Tuple[str, float, Optional[int], Optional[int]]]]:
    if not semantic_cache_enabled():
        return None
    now = time.monotonic()
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        exp, val = item
        if exp < now:
            del _store[key]
            return None
        return list(val)


def cache_set(
    key: str,
    hits: List[Tuple[str, float, Optional[int], Optional[int]]],
) -> None:
    if not semantic_cache_enabled():
        return
    ttl = _ttl_seconds()
    exp = time.monotonic() + ttl
    with _lock:
        _store[key] = (exp, list(hits))
        if len(_store) > 2000:
            for k in list(_store.keys())[:500]:
                _store.pop(k, None)
