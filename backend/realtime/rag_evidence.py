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

    ВАЖНО: по умолчанию backend НЕ отсекает по score (min_sim=0), потому что SVC-RAG уже
    применил ``min_vector_similarity`` + rescue top-N, и результат может быть в разных
    шкалах (чистый cosine / смесь cross-encoder+cosine / BM25 RRF). Любой дополнительный
    порог здесь снова обнуляет recall. Включать RAG_MIN_SIMILARITY>0 имеет смысл только
    когда вы умышленно отключили rescue и все шкалы приведены к [0, 1].

    RAG_BLOCK_ON_NO_EVIDENCE=1 (по умолчанию) — если после всех фильтров контекст действительно
    пуст, backend сам отвечает канонической фразой без вызова LLM. Чтобы ВСЕГДА звать LLM
    (даже без опоры на документы), поставьте RAG_BLOCK_ON_NO_EVIDENCE=0.
    """
    try:
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


def _format_single_fragment(
    row: Tuple[str, float, Optional[int], Optional[int]],
    *,
    number: int,
    id_to_name: Dict[int, str],
    include_chunk_meta: bool,
) -> Optional[str]:
    try:
        content, score, doc_id, chunk_idx = row
    except (TypeError, ValueError):
        return None
    title = rag_document_label(doc_id, id_to_name)
    if include_chunk_meta:
        try:
            sc = float(score)
        except (TypeError, ValueError):
            sc = 0.0
        return (
            f"Фрагмент {number} (документ «{title}», чанк {chunk_idx}, "
            f"релевантность: {sc:.2f}):\n{content}\n"
        )
    return f"Фрагмент {number} (документ «{title}»): {content}\n"


def format_rag_fragments(
    hits: Optional[List[Tuple[str, float, Optional[int], Optional[int]]]],
    id_to_name: Dict[int, str],
    *,
    max_chars: int,
    store_label: str,
    include_chunk_meta: bool = True,
    truncate_marker: str = "\n... [обрезано]\n",
) -> Tuple[List[str], Dict[str, int]]:
    """Единая формализация RAG-хитов в текстовые фрагменты с бюджетом длины.

    Два фундаментальных свойства:

    1. **Round-robin по документам**. Раньше обход был линейный: брали чанки
       в порядке SVC-RAG, и как только бюджет кончался — break. Если первые
       несколько документов были крупными (по 6 жирных чанков), остальные
       документы ВООБЩЕ не попадали в промпт — даже если были семантически
       самыми релевантными. Пользователь видел это как «SVC-RAG нашёл 3
       документа, но LLM ответил будто видел только один».

       Теперь: сначала по одному чанку от каждого document_id (в порядке
       первого появления в hits) — это гарантирует coverage всех документов.
       Затем второй проход берёт следующие чанки документов по порядку, пока
       не кончится бюджет. Итоговая нумерация фрагментов сохраняет исходный
       порядок hits (важно для подписей `Фрагмент N`).

    2. **Явный лог согласования метрик** SVC-RAG ↔ LLM-промпт:

           [RAG/fragments] store=memory: получено=17, попало_в_промпт_целиком=12,
           документов_в_промпт=3/3, последний_обрезан=1, отброшено=4, длина=9873

    Возвращает:
      * parts — готовые строки для `"\\n".join(parts)`;
      * metrics — dict для верхнего лога и, при желании, для ответа API.
    """
    hits = hits or []
    metrics: Dict[str, int] = {
        "received": len(hits),
        "used_full": 0,
        "truncated_last": 0,
        "dropped": 0,
        "total_chars": 0,
        "documents_input": 0,
        "documents_in_prompt": 0,
    }
    if not hits:
        return [], metrics

    # Стабильный порядок документов по первому появлению в hits.
    # dict в Python 3.7+ сохраняет порядок вставки — используем это.
    doc_order: List[Optional[int]] = []
    doc_seen: set = set()
    for row in hits:
        try:
            _, _, d_id, _ = row
        except (TypeError, ValueError):
            continue
        if d_id not in doc_seen:
            doc_seen.add(d_id)
            doc_order.append(d_id)
    metrics["documents_input"] = len(doc_order)

    # Индексированный список: [(номер_1based, document_id, row_idx, row), ...].
    # row_idx — стабильный индекс hit в исходном списке, используется как ключ
    # «добавлен ли уже в выборку». Это безопаснее, чем id(row): хиты могут быть
    # дубликатами-кортежами, у которых id() совпадает.
    indexed: List[Tuple[int, Optional[int], Tuple[str, float, Optional[int], Optional[int]]]] = []
    for i, row in enumerate(hits):
        try:
            _, _, d_id, _ = row
        except (TypeError, ValueError):
            continue
        indexed.append((i + 1, d_id, row))

    by_doc: Dict[Optional[int], List[int]] = {}
    for num, d_id, _row in indexed:
        by_doc.setdefault(d_id, []).append(num - 1)  # 0-based index

    # selected_entries[idx] = готовая текстовая часть (или None, если не выбрана).
    selected_entries: List[Optional[str]] = [None] * len(indexed)
    selected_doc_ids: set = set()
    total = 0
    truncated_last = False
    reserve_for_marker = len(truncate_marker)

    def _try_add(idx: int) -> bool:
        nonlocal total
        if selected_entries[idx] is not None:
            return True
        num, d_id, row = indexed[idx]
        frag = _format_single_fragment(
            row, number=num, id_to_name=id_to_name,
            include_chunk_meta=include_chunk_meta,
        )
        if frag is None:
            return False
        if total + len(frag) + reserve_for_marker > max_chars:
            return False
        selected_entries[idx] = frag
        selected_doc_ids.add(d_id)
        total += len(frag)
        return True

    # Проход 1: по одному чанку на каждый документ (coverage).
    for d_id in doc_order:
        idxs = by_doc.get(d_id) or []
        for idx in idxs:
            if _try_add(idx):
                break  # один на документ в этом проходе
            # Если первый чанк документа не влез — пробуем следующий того же
            # документа (он может быть короче). Это полезно, когда у первого
            # чанка огромный текст, а у второго — компактный заголовок.

    # Проход 2: добираем остальное по исходному порядку hits.
    for idx, (num, d_id, row) in enumerate(indexed):
        if selected_entries[idx] is not None:
            continue
        if _try_add(idx):
            continue
        # Бюджет кончился на этом кандидате: обрежем и вставим маркер.
        if total + reserve_for_marker < max_chars:
            frag = _format_single_fragment(
                row, number=num, id_to_name=id_to_name,
                include_chunk_meta=include_chunk_meta,
            )
            if frag is not None:
                tail = max(0, max_chars - total - reserve_for_marker)
                selected_entries[idx] = frag[:tail] + truncate_marker
                selected_doc_ids.add(d_id)
                total += len(selected_entries[idx])
                truncated_last = True
        break

    parts: List[str] = [p for p in selected_entries if p is not None]
    used_count = len(parts)

    metrics["used_full"] = used_count - (1 if truncated_last else 0)
    metrics["truncated_last"] = 1 if truncated_last else 0
    metrics["dropped"] = max(0, len(indexed) - used_count)
    metrics["total_chars"] = total
    metrics["documents_in_prompt"] = len(selected_doc_ids)

    logger.info(
        "[RAG/fragments] store=%s: получено=%d, попало_в_промпт_целиком=%d, "
        "документов_в_промпт=%d/%d, последний_обрезан=%d, "
        "отброшено_после_лимита=%d, длина=%d/%d",
        store_label,
        metrics["received"],
        metrics["used_full"],
        metrics["documents_in_prompt"],
        metrics["documents_input"],
        metrics["truncated_last"],
        metrics["dropped"],
        metrics["total_chars"],
        max_chars,
    )
    return parts, metrics


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
