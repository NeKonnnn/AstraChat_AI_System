"""
Персональные RAG-настройки пользователя.

Глобальный settings.json / app_state — только seed/defaults.
Чанкинг/модели/top_k/rerank/strategy для project + agent RAG — PostgreSQL
user_llm_settings.rag_settings. На время обработки чата настройки
прокидываются через ContextVar (см. bind_user_rag_runtime).
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from typing import Any, Dict, Optional

from backend.settings.logging import get_logger

logger = get_logger(__name__)

_RAG_SETTING_KEYS = (
    "rag_strategy",
    "agentic_rag_enabled",
    "agentic_max_iterations",
    "rag_query_fix_typos",
    "rag_multi_query_enabled",
    "rag_hyde_enabled",
    "rag_chat_top_k",
    "rag_chunking_strategy",
    "rag_chunk_size",
    "rag_chunk_overlap",
    "rag_similarity_threshold",
    "rag_reranking_enabled",
    "rag_rerank_top_n",
    "rag_system_prompt",
    "rag_embedding_model_path",
    "rag_reranker_model_path",
)

# Персональные настройки текущего запроса чата/поиска (не глобальный app_state).
_user_rag_runtime: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "user_rag_runtime", default=None
)


def _defaults_from_app_state() -> Dict[str, Any]:
    try:
        from backend import app_state as state

        return {
            "rag_strategy": str(getattr(state, "current_rag_strategy", "auto") or "auto"),
            "agentic_rag_enabled": bool(getattr(state, "agentic_rag_enabled", True)),
            "agentic_max_iterations": int(getattr(state, "agentic_max_iterations", 2) or 2),
            "rag_query_fix_typos": bool(getattr(state, "rag_query_fix_typos", False)),
            "rag_multi_query_enabled": bool(getattr(state, "rag_multi_query_enabled", False)),
            "rag_hyde_enabled": bool(getattr(state, "rag_hyde_enabled", False)),
            "rag_chat_top_k": int(getattr(state, "rag_chat_top_k", 12) or 12),
            "rag_chunking_strategy": str(getattr(state, "rag_chunking_strategy", "hierarchical") or "hierarchical"),
            "rag_chunk_size": int(getattr(state, "rag_chunk_size", 1000) or 1000),
            "rag_chunk_overlap": int(getattr(state, "rag_chunk_overlap", 200) or 200),
            "rag_similarity_threshold": float(getattr(state, "rag_similarity_threshold", 0.0) or 0.0),
            "rag_reranking_enabled": bool(getattr(state, "rag_reranking_enabled", True)),
            "rag_rerank_top_n": int(getattr(state, "rag_rerank_top_n", 12) or 12),
            "rag_system_prompt": str(
                getattr(
                    state,
                    "rag_system_prompt",
                    "Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.",
                )
                or ""
            ),
            "rag_embedding_model_path": str(getattr(state, "rag_embedding_model_path", "") or ""),
            "rag_reranker_model_path": str(getattr(state, "rag_reranker_model_path", "") or ""),
        }
    except Exception:
        logger.exception("user_rag_settings: defaults from app_state failed")
        return {
            "rag_strategy": "auto",
            "agentic_rag_enabled": True,
            "agentic_max_iterations": 2,
            "rag_query_fix_typos": False,
            "rag_multi_query_enabled": False,
            "rag_hyde_enabled": False,
            "rag_chat_top_k": 12,
            "rag_chunking_strategy": "hierarchical",
            "rag_chunk_size": 1000,
            "rag_chunk_overlap": 200,
            "rag_similarity_threshold": 0.0,
            "rag_reranking_enabled": True,
            "rag_rerank_top_n": 12,
            "rag_system_prompt": (
                "Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты."
            ),
            "rag_embedding_model_path": "",
            "rag_reranker_model_path": "",
        }


def _merge(stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = _defaults_from_app_state()
    if not isinstance(stored, dict):
        return merged
    for key in _RAG_SETTING_KEYS:
        if key in stored and stored[key] is not None:
            merged[key] = stored[key]
    return merged


def _get_repo():
    try:
        from backend.database.init_db import get_user_settings_repository

        return get_user_settings_repository()
    except Exception:
        logger.debug("user rag settings repository недоступен", exc_info=True)
        return None


async def get_user_rag_settings(user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        return _defaults_from_app_state()
    repo = _get_repo()
    if repo is None:
        return _defaults_from_app_state()
    row = await repo.get(user_id)
    if not row:
        return _defaults_from_app_state()
    return _merge(row.get("rag_settings"))


async def save_user_rag_settings(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Частичное обновление персональных RAG-настроек. Возвращает полный merged snapshot."""
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id обязателен")
    current = await get_user_rag_settings(uid)
    patch = {k: updates[k] for k in _RAG_SETTING_KEYS if k in updates and updates[k] is not None}
    merged = {**current, **patch}
    repo = _get_repo()
    if repo is None:
        logger.warning("user_rag_settings: repo недоступен — сохранение только в памяти ответа")
        return merged
    # Храним только явные пользовательские значения (без шума дефолтов — полный snapshot проще)
    await repo.upsert(uid, rag_settings=merged)
    return merged


def chunk_params_from_rag_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    try:
        size = int(settings.get("rag_chunk_size") or 1000)
    except (TypeError, ValueError):
        size = 1000
    try:
        overlap = int(settings.get("rag_chunk_overlap") or 200)
    except (TypeError, ValueError):
        overlap = 200
    strategy = str(settings.get("rag_chunking_strategy") or "hierarchical").strip().lower()
    if strategy not in {"hierarchical", "fixed", "markdown", "separators", "semantic", "universal"}:
        strategy = "hierarchical"
    return {
        "chunk_size": max(200, min(size, 8000)),
        "chunk_overlap": max(0, min(overlap, 2000)),
        "chunking_strategy": strategy,
    }


def settings_response_dict(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Формат ответа /api/rag/settings (как раньше из app_state)."""
    strategy = str(settings.get("rag_strategy") or "auto")
    return {
        "strategy": strategy,
        "applied_method": strategy,
        "method_description": {
            "auto": "Автоматический выбор стратегии.",
            "hierarchical": "Иерархический поиск по суммаризациям.",
            "hybrid": "Гибридный поиск: вектор + BM25 (weighted RRF по рангам).",
            "vector": "Чистый поиск по cosine distance без изменения порядка результатов.",
            "lexical": "Лексический поиск BM25 (без семантического расширения).",
            "raw_cosine": "Сырой cosine-поиск (без постобработки).",
            "graph": "Графовый RAG: расширение по связям между чанками.",
        }.get(strategy, ""),
        "agentic_rag_enabled": bool(settings.get("agentic_rag_enabled", True)),
        "agentic_max_iterations": int(settings.get("agentic_max_iterations") or 2),
        "rag_query_fix_typos": bool(settings.get("rag_query_fix_typos", False)),
        "rag_multi_query_enabled": bool(settings.get("rag_multi_query_enabled", False)),
        "rag_hyde_enabled": bool(settings.get("rag_hyde_enabled", False)),
        "rag_chat_top_k": int(settings.get("rag_chat_top_k") or 12),
        "rag_chunking_strategy": str(settings.get("rag_chunking_strategy") or "hierarchical"),
        "rag_chunk_size": int(settings.get("rag_chunk_size") or 1000),
        "rag_chunk_overlap": int(settings.get("rag_chunk_overlap") or 200),
        "rag_similarity_threshold": float(settings.get("rag_similarity_threshold") or 0.0),
        "rag_reranking_enabled": bool(settings.get("rag_reranking_enabled", True)),
        "rag_rerank_top_n": int(settings.get("rag_rerank_top_n") or 12),
        "rag_system_prompt": str(settings.get("rag_system_prompt") or ""),
        "rag_embedding_model_path": str(settings.get("rag_embedding_model_path") or ""),
        "rag_reranker_model_path": str(settings.get("rag_reranker_model_path") or ""),
    }


def default_rag_settings_snapshot() -> Dict[str, Any]:
    return deepcopy(_defaults_from_app_state())


def bind_user_rag_runtime(settings: Optional[Dict[str, Any]]) -> Token:
    """Привязать персональные RAG-настройки к текущему async-контексту (чат/поиск)."""
    payload = dict(settings) if isinstance(settings, dict) else None
    return _user_rag_runtime.set(payload)


def reset_user_rag_runtime(token: Token) -> None:
    _user_rag_runtime.reset(token)


def get_runtime_rag_settings() -> Dict[str, Any]:
    """Настройки текущего запроса или seed/defaults, если контекст не задан."""
    cur = _user_rag_runtime.get()
    if isinstance(cur, dict) and cur:
        return cur
    return _defaults_from_app_state()


def runtime_rag_top_k() -> int:
    try:
        v = int(get_runtime_rag_settings().get("rag_chat_top_k") or 12)
    except (TypeError, ValueError):
        v = 12
    return max(1, min(v, 64))


def runtime_rag_strategy() -> str:
    return str(get_runtime_rag_settings().get("rag_strategy") or "auto")


def runtime_rag_system_prompt() -> str:
    return str(get_runtime_rag_settings().get("rag_system_prompt") or "")


def runtime_agentic_rag_enabled() -> bool:
    return bool(get_runtime_rag_settings().get("agentic_rag_enabled", True))


def runtime_agentic_max_iterations() -> int:
    try:
        v = int(get_runtime_rag_settings().get("agentic_max_iterations") or 2)
    except (TypeError, ValueError):
        v = 2
    return max(1, min(v, 5))


def runtime_rag_similarity_threshold() -> float:
    try:
        v = float(get_runtime_rag_settings().get("rag_similarity_threshold") or 0.0)
    except (TypeError, ValueError):
        v = 0.0
    return max(0.0, min(v, 1.0))
