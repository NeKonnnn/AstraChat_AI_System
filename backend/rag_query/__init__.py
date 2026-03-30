"""Пайплайн запросов RAG: нормализация, HyDE, multi-query, постобработка."""

from backend.rag_query.pipeline import ProcessedQuery, process_user_query
from backend.rag_query.preprocess import normalize_query
from backend.rag_query.semantic_cache import bump_rag_semantic_cache, semantic_cache_enabled

__all__ = [
    "ProcessedQuery",
    "process_user_query",
    "normalize_query",
    "bump_rag_semantic_cache",
    "semantic_cache_enabled",
]
