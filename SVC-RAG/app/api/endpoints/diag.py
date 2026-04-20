"""Диагностический endpoint: покажи, что реально происходит при поиске.

Зачем нужен
-----------
Когда пользователь задаёт факт-запрос ("кто такой X?", "какой скилл у X?") и
получает «не нашёл в базе», где-то по пайплайну тёряется контекст. Возможные
места:

1. Документ не распарсен (PDF → OCR не сработал) — искомого имени нет в чанках.
2. tsvector-колонка ещё не заполнена / токенизатор разобрал имя нестандартно.
3. Векторный поиск выдал другие чанки (слабые эмбеддинги parapharse-MiniLM).
4. Реранкер (ms-marco, англоязычный) переставил русские чанки в хвост.
5. min_vector_similarity / low_signal_filter отбросил нужный чанк.

Этот endpoint за один вызов проверяет все пять мест и возвращает разбивку
по этапам. Пользователь (или ты, агент) видит: "содержит 'Константин' в БД — 4
чанка, FTS по 'константин' вернул 0 (проблема токенизации!), ILIKE нашёл 4,
vector cosine с запросом — 0.08 у лучшего (эмбеддинги слабые)". Дальше понятно,
что чинить.

Endpoint readonly — только чтение.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database.fts import (
    build_fts_or_query,
    extract_filenames,
    extract_proper_nouns,
    query_has_searchable_content,
)
from app.dependencies import (
    get_kb_service,
    get_memory_rag_service,
    get_project_rag_service,
    get_rag_service,
)
from app.services.kb_service import KbService
from app.services.memory_rag_service import MemoryRagService
from app.services.project_rag_service import ProjectRagService
from app.services.rag_search_helpers import (
    reranker_is_english_only,
    should_disable_rerank_for_query,
)
from app.services.rag_service import RagService

router = APIRouter()


class DiagRequest(BaseModel):
    query: str
    store: str = "global"  # "global" | "kb" | "memory" | "project"
    project_id: Optional[str] = None
    document_id: Optional[int] = None
    top_k: int = 12
    # Ограничение, сколько чанков показывать в раскладке (чтобы ответ не разрастался).
    sample_limit: int = 5


class StageHit(BaseModel):
    document_id: Optional[int]
    chunk_index: Optional[int]
    score: float
    content_preview: str


class DiagResponse(BaseModel):
    query: str
    store: str
    query_analysis: Dict[str, Any]
    reranker: Dict[str, Any]
    corpus: Dict[str, Any]
    filename_anchor: Dict[str, Any]
    vector_search: Dict[str, Any]
    keyword_fts: Dict[str, Any]
    entity_ilike_fallback: Dict[str, Any]
    suggestions: List[str]


def _preview(s: str, n: int = 200) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _as_stage_hit(dv, score: float) -> StageHit:
    return StageHit(
        document_id=getattr(dv, "document_id", None),
        chunk_index=getattr(dv, "chunk_index", None),
        score=float(score or 0.0),
        content_preview=_preview(getattr(dv, "content", "") or ""),
    )


async def _get_repo_for_store(
    store: str,
    rag: RagService,
    kb: KbService,
    mem: MemoryRagService,
    prj: ProjectRagService,
):
    """Вернуть vector_repo для запрошенного стора (без вызова поиска — только доступ к БД)."""
    s = (store or "").lower()
    if s == "global":
        return rag.vector_repo
    if s == "kb":
        return kb.vector_repo
    if s == "memory":
        return mem.vector_repo
    if s == "project":
        return prj.vector_repo
    raise HTTPException(status_code=400, detail=f"Неизвестный store: {store}")


@router.post("/search", response_model=DiagResponse)
async def diag_search(
    body: DiagRequest,
    rag: RagService = Depends(get_rag_service),
    kb: KbService = Depends(get_kb_service),
    mem: MemoryRagService = Depends(get_memory_rag_service),
    prj: ProjectRagService = Depends(get_project_rag_service),
):
    """Разложи поиск по стадиям и верни, что получилось на каждой.

    Смотреть что чинить:
      * ``corpus.substring_hit_count == 0`` → документ НЕ содержит искомой
        сущности (проверь парсинг PDF / OCR).
      * ``corpus.substring_hit_count > 0`` и ``keyword_fts.count == 0``
        → токенизация tsvector сломалась (пересоздай tsvector-колонки).
      * ``vector_search.top_scores`` все < 0.2 → эмбеддинги слабые, нужен bge-m3 / e5.
      * ``reranker.active_for_this_query == false, but expected`` → проверь
        RAG_RERANKER_ENGLISH_ONLY / RAG_FORCE_RERANK_CYRILLIC.
    """
    store = (body.store or "global").lower()
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query пустой")

    fts_or = build_fts_or_query(q)
    entities = extract_proper_nouns(q)
    filenames_in_query = extract_filenames(q)
    analysis = {
        "has_searchable_content": query_has_searchable_content(q),
        "fts_or_query": fts_or,
        "entities": entities,
        "filenames_detected": filenames_in_query,
        "length": len(q),
    }

    reranker_info = {
        "english_only": reranker_is_english_only(),
        "disabled_for_this_query": should_disable_rerank_for_query(q),
        "note": (
            "reranker_is_english_only=true → cross-encoder ms-marco-MiniLM шумит на "
            "кириллических запросах. Для русского корпуса установите "
            "bge-reranker-v2-m3 и выставите RAG_RERANKER_ENGLISH_ONLY=0."
        ) if reranker_is_english_only() else None,
    }

    vector_repo = await _get_repo_for_store(store, rag, kb, mem, prj)

    # ── Filename anchor: упоминал ли пользователь конкретный файл, и что мы про него знаем ──
    doc_repo = None
    if store == "global":
        doc_repo = rag.doc_repo
    elif store == "kb":
        doc_repo = kb.doc_repo
    elif store == "memory":
        doc_repo = mem.doc_repo
    elif store == "project":
        doc_repo = prj.doc_repo

    filename_entries: List[Dict[str, Any]] = []
    if filenames_in_query and doc_repo is not None and hasattr(doc_repo, "find_document_ids_by_filename"):
        for fn in filenames_in_query:
            try:
                if store == "project":
                    doc_ids = await doc_repo.find_document_ids_by_filename(
                        fn, project_id=body.project_id
                    )
                else:
                    doc_ids = await doc_repo.find_document_ids_by_filename(fn)
            except Exception as e:
                filename_entries.append({"filename": fn, "error": str(e), "document_ids": [], "chunk_counts": {}})
                continue
            # Для каждого найденного документа — сколько у него чанков в БД.
            chunk_counts: Dict[int, int] = {}
            for did in doc_ids:
                try:
                    chunks = await vector_repo.get_vectors_by_document(did)
                    chunk_counts[int(did)] = len(chunks)
                except Exception as e:
                    chunk_counts[int(did)] = -1
                    filename_entries.append(
                        {"filename": fn, "error": f"get_vectors_by_document({did}): {e}"}
                    )
            filename_entries.append(
                {"filename": fn, "document_ids": doc_ids, "chunk_counts": chunk_counts}
            )
    filename_anchor_info = {
        "filenames_detected": filenames_in_query,
        "resolved": filename_entries,
        "interpretation": (
            None
            if not filenames_in_query
            else (
                "Имя файла в запросе не резолвится ни в один документ — либо файл "
                "не загружен, либо имя написано с ошибкой (проверьте точное совпадение, "
                "регистр не важен — ILIKE)."
                if filenames_in_query and not any(e.get("document_ids") for e in filename_entries)
                else (
                    "Документ найден, но у него 0 чанков в БД → парсинг / эмбеддинг "
                    "провалились во время загрузки. Переиндексируйте документ."
                    if any(
                        e.get("document_ids") and not any(c > 0 for c in e.get("chunk_counts", {}).values())
                        for e in filename_entries
                    )
                    else "Документ(ы) найдены и чанки в БД присутствуют. Если LLM всё "
                    "равно отвечает «нет информации» — вопрос в retrieval (смотрите "
                    "vector_search/keyword_fts) или промпте."
                )
            )
        ),
    }

    # ── ILIKE по каждому токену (самое главное: есть ли вообще такая строка в корпусе) ──
    tokens_for_probe = entities if entities else q.split()[:5]
    substring_kwargs: Dict[str, Any] = {"limit": body.sample_limit * 4}
    if store == "project":
        substring_kwargs["project_id"] = body.project_id
    if body.document_id is not None:
        substring_kwargs["document_id"] = body.document_id
    try:
        ilike_hits = await vector_repo.substring_search(tokens_for_probe, **substring_kwargs)
    except Exception as e:
        ilike_hits = []
        substring_error = str(e)
    else:
        substring_error = None

    corpus_info = {
        "probe_tokens": tokens_for_probe,
        "substring_hit_count": len(ilike_hits),
        "samples": [_as_stage_hit(dv, s).dict() for dv, s in ilike_hits[: body.sample_limit]],
        "error": substring_error,
        "interpretation": (
            "0 чанков содержат искомые токены буквально — либо документ не проиндексирован, "
            "либо текст в нём не парсится (OCR)."
            if not ilike_hits
            else f"В БД {len(ilike_hits)} чанков с искомыми токенами. Значит проблема не в парсинге."
        ),
    }

    # ── Векторный поиск (без реранка, без фильтров) ──
    emb_hits: List = []
    vec_error = None
    try:
        emb = await rag.rag_client.embed_single(q) if rag.rag_client else None
        if emb is None:
            vec_error = "rag_client недоступен / не вернул эмбеддинг"
        else:
            vs_kwargs: Dict[str, Any] = {"query_embedding": emb, "limit": body.sample_limit * 2}
            if store == "project":
                vs_kwargs["project_id"] = body.project_id
            if body.document_id is not None:
                vs_kwargs["document_id"] = body.document_id
            emb_hits = await vector_repo.similarity_search(**vs_kwargs)
    except Exception as e:
        vec_error = str(e)

    vector_info = {
        "hit_count": len(emb_hits),
        "top_scores": [round(float(s), 4) for _, s in emb_hits[:10]],
        "samples": [_as_stage_hit(dv, s).dict() for dv, s in emb_hits[: body.sample_limit]],
        "error": vec_error,
        "interpretation": (
            "Все скоры < 0.25 — эмбеддинг-модель слабо различает запрос и чанки "
            "(paraphrase-MiniLM не для query-passage QA). Поставьте "
            "paraphrase-multilingual-mpnet-base-v2 или multilingual-e5-base."
            if emb_hits and all(float(s) < 0.25 for _, s in emb_hits)
            else None
        ),
    }

    # ── FTS (OR-to_tsquery) ──
    kw_hits: List = []
    kw_error = None
    if fts_or:
        try:
            kw_kwargs: Dict[str, Any] = {"limit": body.sample_limit * 4}
            if store == "project":
                kw_kwargs["project_id"] = body.project_id
            if body.document_id is not None:
                kw_kwargs["document_id"] = body.document_id
            kw_hits = await vector_repo.keyword_search(q, **kw_kwargs)
        except Exception as e:
            kw_error = str(e)
    else:
        kw_error = "build_fts_or_query вернул None (все токены — стоп-слова или слишком короткие)"

    keyword_info = {
        "fts_or_query": fts_or,
        "hit_count": len(kw_hits),
        "samples": [_as_stage_hit(dv, s).dict() for dv, s in kw_hits[: body.sample_limit]],
        "error": kw_error,
        "interpretation": (
            "FTS не нашёл ни одного чанка, но ILIKE нашёл — токенизатор tsvector "
            "разобрал эти токены как-то иначе. Пересоздайте tsvector-колонки "
            "(ensure_fts_columns) или проверьте словарь (russian vs simple)."
            if not kw_hits and ilike_hits
            else None
        ),
    }

    # ── Entity ILIKE (то же, что corpus, но явно как стадия пайплайна) ──
    entity_info = {
        "entities": entities,
        "used_as_safety_net": bool(entities and not kw_hits and ilike_hits),
        "count_if_used": len(ilike_hits) if (entities and not kw_hits) else 0,
    }

    # ── Итоговые подсказки ──
    suggestions: List[str] = []
    if not ilike_hits:
        suggestions.append(
            "В корпусе НЕТ чанков с искомыми токенами. Проверьте: "
            "(1) документ реально загружен? (2) PDF распарсился или OCR сработал? "
            "(3) правильный ли store/project_id?"
        )
    if ilike_hits and not kw_hits:
        suggestions.append(
            "FTS/tsvector пустой, хотя ILIKE находит. Запустите ensure_fts_columns "
            "или пересоздайте content_tsv колонки на всех _vectors таблицах."
        )
    if emb_hits and all(float(s) < 0.25 for _, s in emb_hits):
        suggestions.append(
            "Векторные скоры очень низкие. Текущая модель paraphrase-multilingual-MiniLM-L12 "
            "не подходит для факт-запросов на русском. Замените на multilingual-e5-base или "
            "bge-m3 и переиндексируйте (переиндексация обязательна — размерность может отличаться)."
        )
    if reranker_is_english_only():
        suggestions.append(
            "Ваш reranker англоязычный (ms-marco-MiniLM). На русских запросах он "
            "автоматически отключён. После замены на bge-reranker-v2-m3 выставите "
            "RAG_RERANKER_ENGLISH_ONLY=0."
        )
    if not suggestions:
        suggestions.append("Пайплайн выглядит здоровым для этого запроса.")

    # Добавочные подсказки по filename-anchor — самые важные для кейса «саммари по X.docx».
    if filenames_in_query and filename_entries:
        no_resolve = [e for e in filename_entries if e.get("filename") and not e.get("document_ids")]
        if no_resolve:
            suggestions.append(
                f"Имя файла {[e['filename'] for e in no_resolve]} не нашлось в БД. "
                "Проверьте, что документ реально загружен в этот store/project_id."
            )
        zero_chunks = [
            e for e in filename_entries
            if e.get("document_ids") and not any(c > 0 for c in (e.get("chunk_counts") or {}).values())
        ]
        if zero_chunks:
            suggestions.append(
                f"Для {[e['filename'] for e in zero_chunks]} есть запись в таблице документов, "
                "но 0 чанков в _vectors. Парсинг или эмбеддинг упал при загрузке. "
                "Переиндексируйте документ (удалите и загрузите заново)."
            )

    return DiagResponse(
        query=q,
        store=store,
        query_analysis=analysis,
        reranker=reranker_info,
        corpus=corpus_info,
        filename_anchor=filename_anchor_info,
        vector_search=vector_info,
        keyword_fts=keyword_info,
        entity_ilike_fallback=entity_info,
        suggestions=suggestions,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /diag/document — проверка чанкинга конкретного файла.
#
# Зачем отдельный endpoint: чтобы глазами увидеть, **как документ реально лежит
# в БД**. Если у 100-страничного .docx в БД 6 чанков по 50 символов — ясно,
# что парсинг/чанкинг этот файл разломал, и retrieval тут бессилен. Это первый
# вопрос, который надо закрыть перед тюнингом поиска.
# ─────────────────────────────────────────────────────────────────────────────

class DocDiagRequest(BaseModel):
    filename: str  # точное или частичное имя файла (ILIKE %name%)
    store: str = "memory"
    project_id: Optional[str] = None
    show_chunks: bool = False  # включить список всех чанков с превью (может быть большим)
    chunk_preview_len: int = 120


class ChunkInfo(BaseModel):
    chunk_index: int
    content_length: int
    content_preview: str


class DocDiagEntry(BaseModel):
    document_id: int
    filename: str
    chunk_count: int
    total_chars: int
    lengths: Dict[str, int]  # min, max, avg, median
    very_short_chunks: int  # чанков < 80 символов
    empty_like_chunks: int  # < 30 символов — почти наверняка мусор (заголовок, пустая строка)
    verdict: str
    chunks: Optional[List[ChunkInfo]] = None


class DocDiagResponse(BaseModel):
    filename_query: str
    store: str
    matches: List[DocDiagEntry]
    overall_suggestion: Optional[str] = None


def _chunk_verdict(chunk_count: int, lengths: Dict[str, int], very_short: int, empty_like: int) -> str:
    """Человекочитаемый диагноз по чанкингу одного документа."""
    if chunk_count == 0:
        return "КРИТИЧНО: в БД нет ни одного чанка этого документа. Парсинг упал при загрузке, документ не проиндексирован. Переиндексируйте."
    if chunk_count <= 2:
        return (
            "ПОДОЗРИТЕЛЬНО: всего 1-2 чанка. Либо документ короткий, либо парсер упал в середине. "
            "Если это >10 страниц — переиндексируйте."
        )
    avg = lengths.get("avg", 0)
    if avg < 120:
        return (
            f"ПЛОХОЙ ЧАНКИНГ: средняя длина чанка {avg} симв. Парсер режет документ по заголовкам/"
            "коротким абзацам, у LLM не будет достаточного контекста. Нужен chunker с min_chunk_size ≥300."
        )
    if empty_like > chunk_count * 0.3:
        return (
            f"ПЛОХОЙ ЧАНКИНГ: {empty_like} из {chunk_count} чанков короче 30 симв (почти наверняка "
            "заголовки/пустые строки). Парсер не агрегирует абзацы. Переиндексируйте с новым chunker'ом."
        )
    if very_short > chunk_count * 0.4:
        return (
            f"СОМНИТЕЛЬНО: {very_short} чанков короче 80 симв из {chunk_count}. Много «мусорных» "
            "фрагментов. Ретривал будет их отбрасывать, эффективный корпус меньше заявленного."
        )
    return f"OK: {chunk_count} чанков, средняя длина {avg} симв — нормальный чанкинг."


@router.post("/document", response_model=DocDiagResponse)
async def diag_document(
    body: DocDiagRequest,
    rag: RagService = Depends(get_rag_service),
    kb: KbService = Depends(get_kb_service),
    mem: MemoryRagService = Depends(get_memory_rag_service),
    prj: ProjectRagService = Depends(get_project_rag_service),
):
    """Проверка: как документ {filename} лежит в {store}.

    Пример запроса::

        POST /v1/diag/document
        { "filename": "Ларькина_Анна.docx", "store": "memory" }

    В ответе — по каждому совпавшему файлу: число чанков, min/max/avg длина,
    список коротких чанков (< 80 симв) и человекочитаемый вердикт («плохой
    чанкинг», «не проиндексирован», «ОК»).
    """
    fname = (body.filename or "").strip()
    if not fname:
        raise HTTPException(status_code=400, detail="filename пустой")
    store = (body.store or "memory").lower()

    if store == "global":
        doc_repo = rag.doc_repo
        vector_repo = rag.vector_repo
    elif store == "kb":
        doc_repo = kb.doc_repo
        vector_repo = kb.vector_repo
    elif store == "memory":
        doc_repo = mem.doc_repo
        vector_repo = mem.vector_repo
    elif store == "project":
        doc_repo = prj.doc_repo
        vector_repo = prj.vector_repo
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестный store: {store}")

    if not hasattr(doc_repo, "find_document_ids_by_filename"):
        raise HTTPException(status_code=501, detail="doc_repo не поддерживает поиск по имени файла")

    try:
        if store == "project":
            doc_ids = await doc_repo.find_document_ids_by_filename(fname, project_id=body.project_id)
        else:
            doc_ids = await doc_repo.find_document_ids_by_filename(fname)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"find_document_ids_by_filename: {e}")

    matches: List[DocDiagEntry] = []
    for did in doc_ids:
        try:
            doc = await doc_repo.get_document(did) if hasattr(doc_repo, "get_document") else None
        except Exception:
            doc = None
        # filename из БД (может быть None, если get_document не поддерживается — тогда отдаём запрос).
        real_filename = (
            (doc.get("filename") if isinstance(doc, dict) else getattr(doc, "filename", None))
            if doc is not None else fname
        ) or fname
        try:
            chunks = await vector_repo.get_vectors_by_document(did)
        except Exception as e:
            matches.append(
                DocDiagEntry(
                    document_id=int(did),
                    filename=real_filename,
                    chunk_count=0,
                    total_chars=0,
                    lengths={"min": 0, "max": 0, "avg": 0, "median": 0},
                    very_short_chunks=0,
                    empty_like_chunks=0,
                    verdict=f"ОШИБКА get_vectors_by_document: {e}",
                    chunks=None,
                )
            )
            continue
        lens = [len((getattr(c, "content", "") or "")) for c in chunks]
        total = sum(lens)
        if lens:
            lens_sorted = sorted(lens)
            length_stats = {
                "min": lens_sorted[0],
                "max": lens_sorted[-1],
                "avg": total // len(lens),
                "median": lens_sorted[len(lens_sorted) // 2],
            }
        else:
            length_stats = {"min": 0, "max": 0, "avg": 0, "median": 0}
        very_short = sum(1 for ln in lens if ln < 80)
        empty_like = sum(1 for ln in lens if ln < 30)
        verdict = _chunk_verdict(len(chunks), length_stats, very_short, empty_like)
        chunks_out: Optional[List[ChunkInfo]] = None
        if body.show_chunks:
            prev_len = max(30, int(body.chunk_preview_len or 120))
            chunks_sorted = sorted(chunks, key=lambda c: int(getattr(c, "chunk_index", 0) or 0))
            chunks_out = [
                ChunkInfo(
                    chunk_index=int(getattr(c, "chunk_index", 0) or 0),
                    content_length=len(getattr(c, "content", "") or ""),
                    content_preview=_preview(getattr(c, "content", "") or "", n=prev_len),
                )
                for c in chunks_sorted
            ]
        matches.append(
            DocDiagEntry(
                document_id=int(did),
                filename=real_filename,
                chunk_count=len(chunks),
                total_chars=total,
                lengths=length_stats,
                very_short_chunks=very_short,
                empty_like_chunks=empty_like,
                verdict=verdict,
                chunks=chunks_out,
            )
        )

    overall: Optional[str] = None
    if not matches:
        overall = "Файлов с таким именем не найдено — проверьте, что документ действительно загружен в этот store."
    elif any("ПЛОХОЙ ЧАНКИНГ" in m.verdict or "КРИТИЧНО" in m.verdict for m in matches):
        overall = (
            "Документ проиндексирован плохо — парсер/chunker дал слишком мелкие чанки. "
            "Это и есть корневая причина пустых/бедных ответов LLM. "
            "Удалите документ и переиндексируйте ПОСЛЕ правки chunker'а (min_chunk_size ≥300-400 симв)."
        )

    return DocDiagResponse(
        filename_query=fname,
        store=store,
        matches=matches,
        overall_suggestion=overall,
    )
