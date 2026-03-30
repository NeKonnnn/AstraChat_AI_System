"""
Порог релевантности RAG и короткий ответ без вызова LLM, если в документах нет опоры.

Скоры из SVC-RAG: cosine similarity ≈ 1 - (embedding <=> query), обычно в [0, 1].
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.rag_query.prompts import RAG_STRICT_NOT_FOUND_MESSAGE

logger = logging.getLogger(__name__)

# Единая формулировка с strict-промптом и REST/агентами
RAG_NO_RELEVANT_CONTEXT_MESSAGE = RAG_STRICT_NOT_FOUND_MESSAGE


def build_rag_id_to_filename(rows: Optional[List[Any]]) -> Dict[int, str]:
    """Сопоставление id документа в SVC-RAG с именем файла для подписей в промпте (без вывода числового id)."""
    out: Dict[int, str] = {}
    if not rows:
        return out
    for d in rows:
        if not isinstance(d, dict):
            continue
        raw_id = d.get("id")
        if raw_id is None:
            continue
        try:
            key = int(raw_id)
        except (TypeError, ValueError):
            continue
        name = d.get("filename")
        label = (str(name).strip() if name else "") or str(key)
        out[key] = label
    return out


def rag_document_label(doc_id: Optional[Any], id_to_name: Dict[int, str]) -> str:
    """Подпись источника фрагмента для LLM: имя файла, не внутренний document_id."""
    if doc_id is None:
        return "неизвестный документ"
    try:
        key = int(doc_id)
    except (TypeError, ValueError):
        return "неизвестный документ"
    name = id_to_name.get(key)
    if name and str(name).strip():
        return str(name).strip()
    return "документ без имени"


def rag_guard_env() -> Tuple[float, bool]:
    """(min_similarity, block_on_no_evidence).

    Порог имеет смысл для шкалы **cosine** (~0…1), которую отдаёт pgvector до реранка.
    После реранка в SVC-RAG скор = 0.7×логит_cross_encoder + 0.3×cosine (логиты MS MARCO часто < 0);
    тогда см. ``filter_rag_hits_by_score`` — при отрицательной шкале порог не применяется, иначе контекст
    обнулялся бы. Ужесточать: ``RAG_MIN_SIMILARITY`` (backend) и/или ``RAG_RERANK_MIN_SCORE`` (svc-rag).
    """
    try:
        # 0 = не отсекать по скору на backend (рекомендуется при реранке и смешанных шкалах).
        min_sim = float(os.getenv("RAG_MIN_SIMILARITY", "0"))
    except ValueError:
        min_sim = 0.0
    min_sim = max(0.0, min(min_sim, 1.0))
    block = os.getenv("RAG_BLOCK_ON_NO_EVIDENCE", "1").strip().lower() not in ("0", "false", "no", "off")
    return min_sim, block


def filter_rag_hits_by_score(
    hits: Optional[List[Tuple[str, float, Optional[int], Optional[int]]]],
    min_score: float,
) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
    if not hits:
        return []
    if min_score <= 0.0:
        return list(hits)
    out: List[Tuple[str, float, Optional[int], Optional[int]]] = []
    raw_scores: List[float] = []
    for h in hits:
        try:
            s = float(h[1])
            raw_scores.append(s)
            if s >= min_score:
                out.append(h)
        except (TypeError, ValueError):
            continue
    if not out and raw_scores:
        mx = max(raw_scores)
        if mx < min_score and mx < 0.0:
            logger.info(
                "[RAG] Порог RAG_MIN_SIMILARITY=%s не применён: шкала похожа на реранк (max score=%.4f < 0). "
                "Оставляем хиты как отдал SVC-RAG; при необходимости задайте RAG_RERANK_MIN_SCORE в svc-rag.",
                min_score,
                mx,
            )
            return list(hits)
        # Слабый cosine: всё ниже порога, но скоры положительные — отдаём лучшие N (иначе «тишина» в чате).
        if 0.0 <= mx < min_score:
            try:
                rescue = int(os.getenv("RAG_RESCUE_LOW_SCORE_TOP", "10"))
            except ValueError:
                rescue = 10
            rescue = max(4, min(rescue, 24))
            ranked = sorted(
                [h for h in hits if len(h) > 1],
                key=lambda h: float(h[1]),
                reverse=True,
            )
            if ranked:
                logger.info(
                    "[RAG] max score=%.4f < RAG_MIN_SIMILARITY=%s — спасение recall: топ-%s чанков.",
                    mx,
                    min_score,
                    rescue,
                )
                return ranked[:rescue]
        logger.info(
            "[RAG] Все %s хитов отсечены порогом RAG_MIN_SIMILARITY=%s (макс. score до фильтра: %.4f). "
            "Уменьшите RAG_MIN_SIMILARITY в окружении, если ответы есть в документах, но контекст пуст.",
            len(hits),
            min_score,
            mx,
        )
    return out


async def fetch_rag_store_counts(
    rag_client: Any,
    *,
    project_id: Optional[str],
    use_kb_rag: bool,
    use_agent_scoped_kb: bool,
    agent_kb_doc_ids: Optional[List[Any]],
    use_memory_library_rag: bool,
) -> Dict[str, int]:
    """Число документов по хранилищам (для решения, ожидались ли ответы из корпуса)."""
    out: Dict[str, int] = {"global": 0, "project": 0, "kb": 0, "memory": 0, "agent_kb": 0}
    if not rag_client:
        return out
    try:
        docs = await rag_client.list_documents()
        out["global"] = len(docs) if isinstance(docs, list) else 0
    except Exception as e:
        logger.debug("list_documents: %s", e)
    if project_id:
        try:
            docs = await rag_client.project_rag_list_documents(project_id)
            out["project"] = len(docs) if isinstance(docs, list) else 0
        except Exception as e:
            logger.debug("project_rag_list_documents: %s", e)
    kb_list: List[dict] = []
    if use_kb_rag or use_agent_scoped_kb:
        try:
            kb_list = await rag_client.kb_list_documents()
            if not isinstance(kb_list, list):
                kb_list = []
            out["kb"] = len(kb_list)
        except Exception as e:
            logger.debug("kb_list_documents: %s", e)
    if use_agent_scoped_kb and agent_kb_doc_ids and kb_list:
        want = {int(x) for x in agent_kb_doc_ids if str(x).isdigit() or isinstance(x, int)}
        n = 0
        for d in kb_list:
            try:
                if int(d.get("id", -1)) in want:
                    n += 1
            except (TypeError, ValueError):
                continue
        out["agent_kb"] = n
    if use_memory_library_rag:
        try:
            docs = await rag_client.memory_rag_list_documents()
            out["memory"] = len(docs) if isinstance(docs, list) else 0
        except Exception as e:
            logger.debug("memory_rag_list_documents: %s", e)
    return out


async def maybe_rag_no_evidence_message(
    rag_client: Any,
    *,
    block_when_no_evidence: bool,
    context_added: bool,
    global_attempted: bool,
    project_id: Optional[str],
    use_kb_rag: bool,
    use_memory_library_rag: bool,
    use_agent_scoped_kb: bool,
    agent_kb_doc_ids: Optional[List[Any]],
    implicit_global_corpus: bool,
) -> Optional[str]:
    """
    Если включён блок и в промпт не попал ни один фрагмент, но при этом был непустой
    корпус в задействованных хранилищах — возвращает готовый текст ответа (без LLM).
    implicit_global_corpus: True для REST /api/chat (всегда опора на глобальную библиотеку при её наличии).
    """
    if not block_when_no_evidence or context_added or not rag_client:
        return None

    counts = await fetch_rag_store_counts(
        rag_client,
        project_id=project_id,
        use_kb_rag=use_kb_rag,
        use_agent_scoped_kb=use_agent_scoped_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
        use_memory_library_rag=use_memory_library_rag,
    )

    doc_backed = (
        (project_id and counts["project"] > 0)
        or (use_kb_rag and counts["kb"] > 0)
        or (use_agent_scoped_kb and counts.get("agent_kb", 0) > 0)
        or (use_memory_library_rag and counts["memory"] > 0)
        or (implicit_global_corpus and counts["global"] > 0)
        or (
            global_attempted
            and counts["global"] > 0
            and (project_id or use_kb_rag or use_agent_scoped_kb or use_memory_library_rag)
        )
    )

    if not doc_backed:
        return None
    logger.info(
        "[RAG] Блок ответа без опоры: корпус непустой, но после порога релевантности контекст пуст"
    )
    return RAG_NO_RELEVANT_CONTEXT_MESSAGE
