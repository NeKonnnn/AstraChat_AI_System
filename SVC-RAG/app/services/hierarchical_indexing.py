"""
app/services/hierarchical_indexing.py — переиспользуемая иерархическая индексация.
Один помощник для memory / project / kb: строит многоуровневую иерархию документа
(DocumentSummarizer) и раскладывает её в векторную таблицу стора
(OptimizedDocumentIndex). LLM для Level-2 summary — строго через backend
(app.services.llm_chat → POST backend /api/internal/rag/llm, Задача 3).
Машинерия store-agnostic: работает с любым vector_repo (create_vectors_batch)
и rag_client (embed / embed_single).
"""

from __future__ import annotations
from typing import Any, Optional
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.hierarchical import DocumentSummarizer, OptimizedDocumentIndex

logger = get_logger(__name__)

async def _summarize_via_backend(prompt: str) -> str:
    """LLM-суммаризация через backend. При сбое — пустая строка (fallback внутри summarizer)."""
    from app.services import llm_chat

    try:
        return await llm_chat.chat(
            prompt,
            purpose="summarize",
            temperature=0.3,
            max_tokens=2000,
        )
    except Exception as e:
        logger.warning("[hierarchical] LLM summary не удалась: %s", e)
        return ""

async def index_document_hierarchically(
    text: str,
    doc_id: int,
    *,
    filename: str,
    vector_repo: Any,
    rag_client: Any,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> int:
    """
    Иерархически проиндексировать УЖЕ СОЗДАННЫЙ документ (doc_id) в вектора стора.
    Документ в БД должен быть создан заранее (content=text сохранён вызывающим кодом).
    Возвращает число level-0 чанков. Кидает исключение при ошибке индексации —
    вызывающий код решает, удалять ли документ.
    """
    cfg = get_settings().rag
    cs = max(200, int(chunk_size)) if chunk_size else cfg.hierarchical_chunk_size
    co = (
        max(0, int(chunk_overlap))
        if chunk_overlap is not None
        else cfg.hierarchical_chunk_overlap
    )
    if co >= cs:
        co = max(0, cs // 4)
    summarizer = DocumentSummarizer(
        llm_function=_summarize_via_backend,
        max_chunk_size=cs,
        chunk_overlap=co,
        intermediate_summary_chunks=cfg.intermediate_summary_chunks,
    )
    hierarchical_doc = await summarizer.create_hierarchical_summary_async(
        text,
        filename,
        create_full_summary=bool(cfg.create_full_summary_via_llm),
    )
    optimized = OptimizedDocumentIndex(rag_client, vector_repo)
    ok = await optimized.index_document_hierarchical_async(hierarchical_doc, doc_id)
    if not ok:
        raise RuntimeError("иерархическая индексация не сохранила вектора")
    count = int(hierarchical_doc["metadata"]["total_chunks"])
    logger.info(
        "[hierarchical] doc_id=%s '%s': level-0 чанков=%s (+ summary L1/L2)",
        doc_id,
        filename,
        count,
    )
    return count