"""
routes/rag.py - настройки RAG, База Знаний (KB), библиотека памяти (memory-rag)
"""

import os
from typing import Annotated, Optional
import asyncio
import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import backend.app_state as state
from backend.app_state import (
    minio_client,
    rag_client,
    rag_models_client,
    save_app_settings,
    settings,
    get_library_chunk_index_params,
    get_rag_chunk_index_params,
)
from backend.auth.jwt_handler import get_current_user
from backend.rag_query.semantic_cache import bump_rag_semantic_cache
from backend.schemas import RAGSettings, RagModelSelectRequest
from backend.services.user_rag_settings import (
    chunk_params_from_rag_settings,
    default_rag_settings_snapshot,
    get_user_rag_settings,
    save_user_rag_settings,
    settings_response_dict,
)
from backend.settings.logging import get_logger
from backend.settings.logging.errors import logged_suppress
from backend.settings.service_toggles import require_service
from backend.realtime.rag_evidence import build_reindex_status_message
from backend.storage.rag_pvc import (
    RAG_PVC_BUCKET_MARKER,
    RAG_PVC_DIR_ENV,
    delete_rag_pvc_file,
    is_rag_pvc_bucket,
    save_rag_bytes_to_pvc,
    use_rag_pvc,
)

logger = get_logger(__name__)


def _model_row_from_path(model_path: str, kind: str) -> dict:
    path = str(model_path or "").strip()
    name = path.split("/")[-1] if path else ""
    source = path.split("/")[0] if "/" in path else "local"
    return {
        "path": path,
        "name": name,
        "display_name": name,
        "source": source,
        "kind": kind,
    }


def _overlay_user_model_current(data: dict, user_rag: dict) -> dict:
    """В UI current — персональный выбор пользователя, не только runtime кластера."""
    out = dict(data or {})
    cluster = dict(out.get("cluster_default") or out.get("current") or {})
    current = dict(cluster)
    saved_emb = str(user_rag.get("rag_embedding_model_path") or "").strip()
    saved_rer = str(user_rag.get("rag_reranker_model_path") or "").strip()
    if saved_emb:
        current["embedding"] = _model_row_from_path(saved_emb, "embedding")
    if saved_rer:
        current["reranker"] = _model_row_from_path(saved_rer, "reranker")
    out["current"] = current
    out["cluster_default"] = cluster
    return out


async def _validate_local_model_path(model_type: str, model_path: str) -> None:
    data = await rag_models_client.list_models(model_type)
    rows = (data.get("models") or {}).get(model_type) or []
    paths = {str((r or {}).get("path") or "").strip() for r in rows}
    if model_path not in paths:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Модель {model_path!r} не найдена в каталоге. "
                "Доступны только папки из RAG_MODELS_DIR / ConfigMap RAG_*_MODEL*."
            ),
        )


def _rag_upload_username(current_user: dict) -> str:
    return current_user.get("username") or current_user.get("user_id") or "anonymous"


def _delete_rag_source_file(object_name: Optional[str], bucket: Optional[str]) -> None:
    """Удаляет исходник из PVC или MinIO по metadata документа."""
    if not object_name or not bucket:
        return
    if is_rag_pvc_bucket(bucket):
        delete_rag_pvc_file(object_name, bucket)
        return
    if minio_client:
        try:
            minio_client.delete_file(object_name, bucket_name=bucket)
        except Exception:
            logger.exception("MinIO delete RAG source object=%s bucket=%s", object_name, bucket)


router = APIRouter(tags=["rag"])
_VALID_STRATEGIES = {"auto", "hierarchical", "hybrid", "vector", "lexical", "raw_cosine", "graph"}
_VALID_CHUNKING_STRATEGIES = {"hierarchical", "fixed", "markdown", "separators", "semantic"}


def _is_upstream_httpx_timeout(exc: BaseException) -> bool:
    seen = set()
    cur = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, httpx.TimeoutException):
            return True
        cur = cur.__cause__
    return False


def _rag_settings_response_dict() -> dict:
    """Дефолты кластера (settings.json / env) — seed для новых пользователей."""
    return settings_response_dict(default_rag_settings_snapshot())


@router.get("/api/rag/settings")
async def get_rag_settings(current_user: Annotated[dict, Depends(get_current_user)]):
    """Персональные RAG-настройки пользователя (PostgreSQL)."""
    user_id = str(current_user.get("user_id") or "").strip()
    settings_data = await get_user_rag_settings(user_id)
    return settings_response_dict(settings_data)


def _build_reindex_status_message(
    *,
    memory_reindexing: bool,
    project_reindexing: bool,
    kb_reindexing: bool,
) -> str:
    return build_reindex_status_message(
        memory_reindexing=memory_reindexing,
        project_reindexing=project_reindexing,
        kb_reindexing=kb_reindexing,
    )


async def _resolve_agent_has_kb_documents(agent_id: int, user_id: Optional[str]) -> bool:
    """Агент реально использует KB-RAG: file_search + id документов, существующих в сторе."""
    from backend.realtime.helpers import _resolve_agent_chat_params

    profile = await _resolve_agent_chat_params(agent_id, user_id)
    if not bool(profile.get("file_search_enabled")):
        return False
    kb_ids = profile.get("kb_document_ids") or []
    if not isinstance(kb_ids, list) or len(kb_ids) == 0:
        return False
    if not rag_client:
        return False
    try:
        rows = list(await rag_client.kb_list_documents() or [])
    except Exception:
        logger.warning("[RAG] kb_list_documents failed for reindex-status", exc_info=True)
        return len(kb_ids) > 0
    existing = {int(d.get("id")) for d in rows if d.get("id") is not None}
    return any(int(doc_id) in existing for doc_id in kb_ids)


async def _resolve_project_has_rag_documents(project_id: str) -> bool:
    if not rag_client or not project_id:
        return False
    try:
        docs = list(await rag_client.project_rag_list_documents(project_id) or [])
    except Exception:
        logger.warning("[RAG] project_rag_list_documents failed for reindex-status", exc_info=True)
        return False
    return len(docs) > 0


@router.get("/api/rag/reindex-status")
async def get_rag_reindex_status(
    current_user: Annotated[dict, Depends(get_current_user)],
    agent_id: Optional[int] = None,
    project_id: Optional[str] = None,
):
    """Агрегированный статус перечанковки RAG для UI (плашка и стоппер)."""
    empty_payload = {
        "memory": {"reindexing": False},
        "project": {"reindexing": False},
        "kb": {"reindexing": False},
        "any_reindexing": False,
        "agent_has_kb": False,
        "project_has_documents": False,
        "message": "",
    }
    if not rag_client:
        return empty_payload
    try:
        status = await rag_client.get_reindex_status()
    except Exception as exc:
        logger.warning("[RAG] reindex-status poll failed: %s", exc)
        return empty_payload

    user_id = current_user.get("user_id") if current_user else None
    agent_has_kb = False
    if agent_id is not None:
        agent_has_kb = await _resolve_agent_has_kb_documents(agent_id, user_id)

    project_has_documents = False
    if project_id:
        project_has_documents = await _resolve_project_has_rag_documents(str(project_id).strip())

    memory_flag = bool(status.get("memory", {}).get("reindexing"))
    project_flag = bool(status.get("project", {}).get("reindexing"))
    kb_flag = bool(status.get("kb", {}).get("reindexing"))
    message = _build_reindex_status_message(
        memory_reindexing=memory_flag,
        project_reindexing=project_flag,
        kb_reindexing=kb_flag,
    )
    return {
        "memory": {"reindexing": memory_flag},
        "project": {"reindexing": project_flag},
        "kb": {"reindexing": kb_flag},
        "any_reindexing": memory_flag or project_flag or kb_flag,
        "agent_has_kb": agent_has_kb,
        "project_has_documents": project_has_documents,
        "message": message,
    }


@router.post("/api/rag/settings/reset")
async def reset_rag_settings(current_user: Annotated[dict, Depends(get_current_user)]):
    """Сброс персональных RAG-настроек пользователя к дефолтам кластера."""
    try:
        user_id = str(current_user.get("user_id") or "").strip()
        if not user_id:
            raise HTTPException(status_code=401, detail="Требуется авторизация")
        logger.debug("[RAG-CFG] сброс персональных RAG-настроек user=%s", user_id)
        defaults = default_rag_settings_snapshot()
        defaults.update(
            {
                "rag_strategy": "auto",
                "agentic_rag_enabled": True,
                "agentic_max_iterations": 2,
                "rag_query_fix_typos": False,
                "rag_multi_query_enabled": False,
                "rag_hyde_enabled": False,
                "rag_chat_top_k": 8,
                "rag_chunking_strategy": "hierarchical",
                "rag_chunk_size": 1000,
                "rag_chunk_overlap": 200,
                "rag_similarity_threshold": 0.0,
                "rag_reranking_enabled": True,
                "rag_rerank_top_n": 12,
                "rag_embedding_model_path": "",
                "rag_reranker_model_path": "",
                "rag_system_prompt": (
                    "Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты."
                ),
            }
        )
        merged = await save_user_rag_settings(user_id, defaults)
        bump_rag_semantic_cache()
        return {"message": "Настройки RAG сброшены", "success": True, **settings_response_dict(merged)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _rechunk_on_settings_change() -> bool:
    v = os.getenv("RAG_RECHUNK_ON_SETTINGS_CHANGE", "").strip().lower()
    return v in ("1", "true", "yes", "on")


async def _run_background_rechunk(chunk_params: Optional[dict] = None) -> None:
    """Фоновая перечанкировка project + kb (memo single-tenant: весь кластер)."""
    if not rag_client:
        return
    params = chunk_params or get_rag_chunk_index_params()
    cs = params.get("chunk_size")
    co = params.get("chunk_overlap")
    strat = params.get("chunking_strategy")
    logger.info("[RECHUNK] старт: strategy=%s chunk_size=%s overlap=%s", strat, cs, co)
    try:
        kb_res = await rag_client.kb_reindex(chunk_size=cs, chunk_overlap=co, chunking_strategy=strat)
        logger.info("[RECHUNK] kb готово: %s", kb_res)
    except Exception:
        logger.exception("[RECHUNK] kb ошибка")
    try:
        proj_res = await rag_client.project_rag_reindex_all(chunk_size=cs, chunk_overlap=co, chunking_strategy=strat)
        logger.info("[RECHUNK] projects готово: %s", proj_res)
    except Exception:
        logger.exception("[RECHUNK] projects ошибка")
    logger.info("[RECHUNK] финиш")


def _reindex_on_model_change() -> bool:
    # Дефолт true: после смены embedding-модели вектора стёрты миграцией,
    # без реиндекса поиск мёртв до ручного перезалива
    v = os.getenv("RAG_REINDEX_ON_MODEL_CHANGE", "true").strip().lower()
    return v in ("1", "true", "yes", "on")


async def _run_background_reindex_after_model_change() -> None:
    """Восстановление векторов всех сторов из сохранённого текста после смены эмбеддера."""
    if not rag_client:
        return
    params = get_rag_chunk_index_params()
    cs = params.get("chunk_size")
    co = params.get("chunk_overlap")
    strat = params.get("chunking_strategy")
    logger.info(
        "[REINDEX-AUTO] старт после смены embedding-модели: strategy=%s size=%s overlap=%s",
        strat,
        cs,
        co,
    )
    for name, call in (
        ("kb", rag_client.kb_reindex),
        ("projects", rag_client.project_rag_reindex_all),
        ("memory", rag_client.memory_rag_reindex),
    ):
        try:
            res = await call(chunk_size=cs, chunk_overlap=co, chunking_strategy=strat)
            logger.info("[REINDEX-AUTO] %s готово: %s", name, res)
        except Exception:
            logger.exception("[REINDEX-AUTO] %s ошибка", name)
    logger.info("[REINDEX-AUTO] финиш")


@router.put("/api/rag/settings")
async def update_rag_settings(
    settings_data: RAGSettings,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Обновить персональные RAG-настройки пользователя."""
    user_id = str(current_user.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    strat = settings_data.strategy
    if strat is not None and strat == "reranking":
        strat = "hybrid"
    if strat is not None and strat == "standard":
        # Миграция старых сохранённых настроек; API больше не публикует standard.
        strat = "vector"
    if strat is not None and strat == "lexical":
        strat = "lexical"
    if strat is not None and strat not in _VALID_STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Недопустимая стратегия. Допустимые: {_VALID_STRATEGIES}")
    chunking = settings_data.rag_chunking_strategy
    if chunking is not None:
        chunking = str(chunking).strip().lower()
        if chunking not in _VALID_CHUNKING_STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимая стратегия чанкования. Допустимые: {_VALID_CHUNKING_STRATEGIES}",
            )
    if (
        settings_data.strategy is None
        and settings_data.agentic_rag_enabled is None
        and (settings_data.agentic_max_iterations is None)
        and (settings_data.rag_query_fix_typos is None)
        and (settings_data.rag_multi_query_enabled is None)
        and (settings_data.rag_hyde_enabled is None)
        and (settings_data.rag_chat_top_k is None)
        and (settings_data.rag_chunking_strategy is None)
        and (settings_data.rag_chunk_size is None)
        and (settings_data.rag_chunk_overlap is None)
        and (settings_data.rag_similarity_threshold is None)
        and (settings_data.rag_reranking_enabled is None)
        and (settings_data.rag_rerank_top_n is None)
        and (settings_data.rag_system_prompt is None)
        and (settings_data.rag_embedding_model_path is None)
        and (settings_data.rag_reranker_model_path is None)
    ):
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    try:
        before = await get_user_rag_settings(user_id)
        # Фронт шлёт весь набор настроек всегда, поэтому «поле пришло» != «значение
        # изменилось». Речанковку запускаем только при фактическом изменении нарезки.
        _chunk_before = (
            str(before.get("rag_chunking_strategy") or ""),
            int(before.get("rag_chunk_size") or 0),
            int(before.get("rag_chunk_overlap") or 0),
        )
        updates: dict = {}
        if strat is not None:
            updates["rag_strategy"] = strat
        if settings_data.agentic_rag_enabled is not None:
            updates["agentic_rag_enabled"] = bool(settings_data.agentic_rag_enabled)
        if settings_data.agentic_max_iterations is not None:
            ami = int(settings_data.agentic_max_iterations)
            updates["agentic_max_iterations"] = max(1, min(ami, 5))
        if settings_data.rag_query_fix_typos is not None:
            updates["rag_query_fix_typos"] = bool(settings_data.rag_query_fix_typos)
        if settings_data.rag_multi_query_enabled is not None:
            updates["rag_multi_query_enabled"] = bool(settings_data.rag_multi_query_enabled)
        if settings_data.rag_hyde_enabled is not None:
            updates["rag_hyde_enabled"] = bool(settings_data.rag_hyde_enabled)
        if settings_data.rag_chat_top_k is not None:
            try:
                rk = int(settings_data.rag_chat_top_k)
                updates["rag_chat_top_k"] = max(1, min(rk, 64))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_chat_top_k: ожидается целое число 1–64") from e
        if chunking is not None:
            updates["rag_chunking_strategy"] = chunking
        if settings_data.rag_chunk_size is not None:
            try:
                size = int(settings_data.rag_chunk_size)
                updates["rag_chunk_size"] = max(200, min(size, 8000))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_chunk_size: ожидается целое число 200–8000") from e
        if settings_data.rag_chunk_overlap is not None:
            try:
                overlap = int(settings_data.rag_chunk_overlap)
                updates["rag_chunk_overlap"] = max(0, min(overlap, 2000))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_chunk_overlap: ожидается целое число 0–2000") from e
        if settings_data.rag_similarity_threshold is not None:
            try:
                threshold = float(settings_data.rag_similarity_threshold)
                updates["rag_similarity_threshold"] = max(0.0, min(threshold, 1.0))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_similarity_threshold: ожидается число 0..1") from e
        if settings_data.rag_reranking_enabled is not None:
            updates["rag_reranking_enabled"] = bool(settings_data.rag_reranking_enabled)
        if settings_data.rag_rerank_top_n is not None:
            try:
                top_n = int(settings_data.rag_rerank_top_n)
                updates["rag_rerank_top_n"] = max(1, min(top_n, 64))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_rerank_top_n: ожидается целое число 1–64") from e
        if settings_data.rag_system_prompt is not None:
            prompt = str(settings_data.rag_system_prompt or "").strip()
            updates["rag_system_prompt"] = (
                prompt
                if prompt
                else "Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты."
            )
        if settings_data.rag_embedding_model_path is not None:
            updates["rag_embedding_model_path"] = str(settings_data.rag_embedding_model_path or "").strip()
        if settings_data.rag_reranker_model_path is not None:
            updates["rag_reranker_model_path"] = str(settings_data.rag_reranker_model_path or "").strip()

        if not updates:
            raise HTTPException(status_code=400, detail="Нет полей для обновления")

        logger.debug("[RAG-CFG] персональные настройки user=%s: %s", user_id, updates)
        merged = await save_user_rag_settings(user_id, updates)

        if "rag_chat_top_k" in updates or "rag_rerank_top_n" in updates:
            bump_rag_semantic_cache()

        _chunk_after = (
            str(merged.get("rag_chunking_strategy") or ""),
            int(merged.get("rag_chunk_size") or 0),
            int(merged.get("rag_chunk_overlap") or 0),
        )
        if _rechunk_on_settings_change() and _chunk_after != _chunk_before:
            logger.info(
                "[RECHUNK] настройки чанкинга изменились user=%s → фоновая перечанкировка",
                user_id,
            )
            asyncio.create_task(_run_background_rechunk(chunk_params_from_rag_settings(merged)))
        return {"message": "Настройки RAG обновлены", "success": True, **settings_response_dict(merged)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


PHOENIX_PROVIDER_ID = os.getenv("RAG_PHOENIX_PROVIDER_ID", "PHOENIX")

def _phoenix_guess_kind(model_id: str) -> Optional[str]:
    n = (model_id or "").lower()
    if "rerank" in n:
        return "reranker"
    if "embed" in n:
        return "embedding"
    return None  # LLM и прочее в RAG-селекторе не показываем

async def _phoenix_rag_models(model_type: Optional[str] = None) -> list:
    """Модели Phoenix (GET /v1/models через llm_providers) для селектора RAG.

    Это и есть discovery без curl: реальные id моделей видны в UI и в логе.
    """
    from backend.llm_providers.registry import get_registry

    registry = await get_registry()
    if not registry.contains(PHOENIX_PROVIDER_ID):
        logger.warning(
            "[PHOENIX] провайдер %r не найден в реестре LLM — phoenix-модели в каталоге не появятся",
            PHOENIX_PROVIDER_ID,
        )
        return []
    provider = registry.get(PHOENIX_PROVIDER_ID)
    infos = await provider.list_models()
    rows: list = []
    logger.info("[PHOENIX] сырые модели: %s", [getattr(i, "model_id", "") for i in (infos or [])])
    for info in infos or []:
        model_id = str(getattr(info, "model_id", "") or "").strip()
        if not model_id:
            continue
        kind = _phoenix_guess_kind(model_id)
        if kind is None or (model_type and kind != model_type):
            continue
        rows.append(
            {
                "path": f"phoenix/{model_id}",
                "name": model_id,
                "display_name": model_id,
                "source": "phoenix",
                "kind": kind,
                "description": "Модель Phoenix (LiteLLM)",
                "available": True,
            }
        )
    logger.info("[PHOENIX] RAG-каталог: %s", [r["path"] for r in rows])
    return rows


@router.get("/api/rag/models")
async def list_rag_models(
    current_user: Annotated[dict, Depends(get_current_user)],
    type: str | None = None,
):
    """Список моделей эмбеддингов и cross-encoder из SVC-RAG-MODELS."""
    require_service("rag_models")
    if not rag_models_client:
        raise HTTPException(status_code=503, detail="RAG-models service недоступен")
    try:
        data = await rag_models_client.list_models(type)
        # Только local (+ phoenix ниже); внешние каталоги отфильтровываем
        models = data.get("models") or {}
        for kind_key in ("embedding", "reranker"):
            rows = models.get(kind_key) or []
            models[kind_key] = [
                r
                for r in rows
                if str((r or {}).get("source") or "").lower() in ("local", "")
                or str((r or {}).get("path") or "").lower().startswith("local/")
            ]
        data["models"] = models
        try:
            phoenix_rows = await _phoenix_rag_models(type)
            if phoenix_rows:
                models = data.get("models") or {}
                for row in phoenix_rows:
                    models.setdefault(row["kind"], []).append(row)
                data["models"] = models
        except Exception:
            logger.exception("Каталог Phoenix недоступен - показываю только локальные")
        user_id = str(current_user.get("user_id") or "").strip()
        user_rag = await get_user_rag_settings(user_id) if user_id else {}
        return _overlay_user_model_current(data, user_rag)
    except Exception as e:
        logger.exception("list_rag_models error")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/api/rag/models/current")
async def get_rag_models_current(current_user: Annotated[dict, Depends(get_current_user)]):
    require_service("rag_models")
    if not rag_models_client:
        raise HTTPException(status_code=503, detail="RAG-models service недоступен")
    try:
        data = await rag_models_client.get_current()
        user_id = str(current_user.get("user_id") or "").strip()
        user_rag = await get_user_rag_settings(user_id) if user_id else {}
        return _overlay_user_model_current(data, user_rag)
    except Exception as e:
        logger.exception("get_rag_models_current error")
        raise HTTPException(status_code=502, detail=str(e)) from e


async def _select_phoenix_rag_model(model_type: str, model_path: str, user_id: str):
    """Выбор модели Phoenix: НЕ грузим локально, переключаем svc-rag.

    reranker: только переключение, dim не участвует.
    embedding: переключение -> probe dim -> явная миграция схемы
    (ensure_embedding_dim, тот же путь, что у native). При неудаче probe
    выбор откатывается на прежний - корпус в безопасности.
    Путь всегда сохраняется в персональных rag_settings пользователя.
    """
    from backend.settings.rag_client import rag_model_path_to_provider

    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    model_id = model_path.split("/", 1)[1].strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="Пустой id модели Phoenix")
    try:
        result = await rag_client.set_models_provider(
            model_type, PHOENIX_PROVIDER_ID, model_id
        )
    except Exception as e:
        logger.exception("Phoenix select error")
        raise HTTPException(status_code=502, detail=str(e)) from e
    path_key = (
        "rag_embedding_model_path"
        if model_type == "embedding"
        else "rag_reranker_model_path"
    )
    if model_type == "embedding":
        emb_dim = result.get("embedding_dim") if isinstance(result, dict) else None
        if not emb_dim:
            # probe не удался (сеть/ключ/модель) - откатываем выбор в svc-rag
            with logged_suppress(logger):
                user_rag = await get_user_rag_settings(user_id)
                prev_path = str(
                    user_rag.get("rag_embedding_model_path")
                    or getattr(state, "rag_embedding_model_path", "")
                    or ""
                )
                prev_provider, prev_model = rag_model_path_to_provider(prev_path)
                await rag_client.set_models_provider(
                    "embedding", prev_provider, prev_model
                )
            detail = (
                result.get("probe_error") if isinstance(result, dict) else None
            ) or "не удалось определить размерность модели"
            raise HTTPException(
                status_code=502,
                detail=f"Phoenix-эмбеддер не подключён: {detail}",
            )
        try:
            schema = await rag_client.ensure_embedding_dim(int(emb_dim))
            if isinstance(result, dict):
                result = {**result, "schema": schema, "embedding_dim": emb_dim}
            if (
                _reindex_on_model_change()
                and isinstance(schema, dict)
                and schema.get("migrated")
            ):
                logger.info(
                    "[REINDEX-AUTO] миграция dim очистила вектора -> фоновое восстановление"
                )
                asyncio.create_task(_run_background_reindex_after_model_change())
        except Exception:
            logger.exception(
                "Не удалось синхронизировать embedding_dim=%s в SVC-RAG", emb_dim
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Провайдер переключён, но схема БД не перешла на dim={emb_dim}. "
                    "Индексация/поиск будут падать до миграции."
                ),
            ) from None
    await save_user_rag_settings(user_id, {path_key: model_path})
    # Seed для новых пользователей / fallback без runtime
    state_attr = path_key
    setattr(state, state_attr, model_path)
    save_app_settings({path_key: model_path})
    bump_rag_semantic_cache()
    if isinstance(result, dict):
        result = {
            **result,
            "success": True,
            "model_type": model_type,
            "model_path": model_path,
            "path_saved": True,
        }
    return result


@router.post("/api/rag/models/select")
async def select_rag_model(
    body: RagModelSelectRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Выбор модели: сохранение в персональных rag_settings + загрузка в кластер (memo).

    Local: rag_models_client.select_model + dim migrate при embedding.
    Phoenix: set_models_provider + dim migrate.
    Путь всегда пишется в user_llm_settings.rag_settings.
    """
    require_service("rag_models")
    if not rag_models_client:
        raise HTTPException(status_code=503, detail="RAG-models service недоступен")
    user_id = str(current_user.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    model_type = str(body.model_type or "").strip().lower()
    if model_type not in ("embedding", "reranker"):
        raise HTTPException(status_code=400, detail="model_type должен быть embedding или reranker")
    model_path = str(body.model_path or "").strip()
    if not model_path:
        raise HTTPException(status_code=400, detail="model_path обязателен")
    logger.debug(
        "[RAG-CFG] Выбор RAG-модели user=%s: type=%s, path=%s",
        user_id,
        model_type,
        model_path,
    )
    if model_path.lower().startswith("huggingface/"):
        raise HTTPException(
            status_code=400,
            detail="Источник huggingface отключён: выберите local/<папка> из models/rag",
        )
    if model_path.lower().startswith("phoenix/"):
        return await _select_phoenix_rag_model(model_type, model_path, user_id)
    try:
        await _validate_local_model_path(model_type, model_path)
        result = await rag_models_client.select_model(model_type, model_path)
        # Выбрана локальная модель: если svc-rag был на Phoenix - вернуть native
        with logged_suppress(logger):
            if rag_client:
                await rag_client.set_models_provider(model_type, "native", None)
        path_key = (
            "rag_embedding_model_path"
            if model_type == "embedding"
            else "rag_reranker_model_path"
        )
        # Размерность/миграция/реиндекс касаются ТОЛЬКО эмбеддера.
        # Реранкер не создаёт векторы — его смена не трогает схему БД.
        if model_type == "embedding":
            # Колонки pgvector создаются один раз (CREATE IF NOT EXISTS) —
            # при смене эмбеддера нужно привести vector(N) к фактической dim.
            emb_dim = result.get("embedding_dim") if isinstance(result, dict) else None
            if emb_dim is None and rag_models_client:
                try:
                    health = await rag_models_client.health()
                    emb_dim = (
                        health.get("embedding_dim") if isinstance(health, dict) else None
                    )
                except Exception:
                    logger.exception("Не удалось получить embedding_dim из health")
            if emb_dim and rag_client:
                try:
                    schema = await rag_client.ensure_embedding_dim(int(emb_dim))
                    if isinstance(result, dict):
                        result = {**result, "schema": schema}
                except Exception:
                    logger.exception(
                        "Не удалось синхронизировать embedding_dim=%s в SVC-RAG",
                        emb_dim,
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            f"Модель загружена, но схема БД не перешла на dim={emb_dim}. "
                            "Переиндексация может падать с expected N dimensions."
                        ),
                    ) from None
            if (
                _reindex_on_model_change()
                and isinstance(result, dict)
                and isinstance(result.get("schema"), dict)
                and result["schema"].get("migrated")
            ):
                logger.info(
                    "[REINDEX-AUTO] миграция dim очистила вектора → фоновое восстановление"
                )
                asyncio.create_task(_run_background_reindex_after_model_change())
        await save_user_rag_settings(user_id, {path_key: model_path})
        setattr(state, path_key, model_path)
        save_app_settings({path_key: model_path})
        bump_rag_semantic_cache()
        if isinstance(result, dict):
            result = {
                **result,
                "success": True,
                "model_type": model_type,
                "model_path": model_path,
                "path_saved": True,
            }
            return result
        return {
            "success": True,
            "message": "Модель загружена, путь сохранён в настройках",
            "model_type": model_type,
            "model_path": model_path,
            "path_saved": True,
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("select_rag_model error")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/api/kb/documents")
async def kb_upload_document(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    chunking_strategy: Annotated[Optional[str], Form()] = None,
):
    """Загрузка в KB (агентный RAG / библиотека KB).

    Библиотека (страница KB / memory): без strategy → universal.
    Агент (конструктор): передаёт chunking_strategy из настроек RAG.
    При RAG_USE_PVC=true исходник пишется в /ragdb/agent/{user}/{date}/.
    """
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    username = _rag_upload_username(current_user)
    file_object_name = None
    file_bucket = None
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пустой")
        fn = file.filename or "unknown"
        strategy = (chunking_strategy or "").strip().lower()
        if strategy and strategy in _VALID_CHUNKING_STRATEGIES | {"universal"}:
            chunk_params = get_rag_chunk_index_params()
            chunk_params["chunking_strategy"] = strategy
        else:
            # Библиотека: всегда universal, UI-стратегия не применяется
            chunk_params = get_library_chunk_index_params()
        if use_rag_pvc():
            file_object_name = save_rag_bytes_to_pvc(
                content,
                fn,
                scope="agent",
                username=username,
                prefix="kb_",
                content_type=file.content_type or "application/octet-stream",
            )
            if not file_object_name:
                raise HTTPException(
                    status_code=500,
                    detail=f"Не удалось сохранить файл в PVC — проверьте {RAG_PVC_DIR_ENV} и mount /ragdb",
                )
            file_bucket = RAG_PVC_BUCKET_MARKER
        try:
            out = await rag_client.kb_upload_document(
                file_bytes=content,
                filename=fn,
                minio_object=file_object_name,
                minio_bucket=file_bucket,
                **chunk_params,
            )
        except Exception as e:
            if file_object_name and file_bucket:
                with logged_suppress(logger):
                    _delete_rag_source_file(file_object_name, file_bucket)
            raise
        bump_rag_semantic_cache()
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/kb/documents")
async def kb_list_documents():
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.kb_list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/kb/documents/{document_id}")
async def kb_delete_document(document_id: int):
    require_service("rag")  # FEATURE-FLAG
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.kb_delete_document(document_id)
        if isinstance(out, dict) and out.get("ok") is False:
            raise HTTPException(status_code=404, detail="Документ не найден")
        if isinstance(out, dict):
            _delete_rag_source_file(out.get("minio_object"), out.get("minio_bucket"))
        bump_rag_semantic_cache()
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/memory-rag/documents")
async def memory_rag_upload(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Глобальный / memory RAG (Настройки → RAG). MinIO или PVC — по флагу RAG_USE_PVC."""
    require_service("rag")  # FEATURE-FLAG
    if not use_rag_pvc():
        require_service("minio")  # FEATURE-FLAG
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    username = _rag_upload_username(current_user)
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пустой")
        fn = file.filename or "unknown"
        ext = os.path.splitext(fn)[1] or ".bin"
        file_object_name = None
        memory_bucket = None
        if use_rag_pvc():
            file_object_name = save_rag_bytes_to_pvc(
                content,
                fn,
                scope="memory",
                username=username,
                prefix="memrag_",
                content_type=file.content_type or "application/octet-stream",
            )
            if not file_object_name:
                raise HTTPException(
                    status_code=500,
                    detail=f"Не удалось сохранить файл в PVC — проверьте {RAG_PVC_DIR_ENV} и mount /ragdb",
                )
            memory_bucket = RAG_PVC_BUCKET_MARKER
        else:
            memory_bucket = settings.minio.memory_rag_bucket_name
            if minio_client:
                try:
                    minio_client.ensure_bucket(memory_bucket)
                    file_object_name = minio_client.generate_object_name(prefix="memrag_", extension=ext)
                    minio_client.upload_file(
                        content,
                        file_object_name,
                        content_type=file.content_type or "application/octet-stream",
                        bucket_name=memory_bucket,
                    )
                except Exception as e:
                    logger.exception("MinIO memory-rag upload")
                    raise HTTPException(status_code=500, detail=f"MinIO: {e}") from e
        try:
            # Библиотека памяти: всегда universal chunking
            chunk_params = get_library_chunk_index_params()
            result = await rag_client.memory_rag_index_document(
                file_bytes=content,
                filename=fn,
                minio_object=file_object_name,
                minio_bucket=memory_bucket if file_object_name else None,
                **chunk_params,
            )
        except Exception as e:
            logger.exception("Ошибка операции")
            if file_object_name and memory_bucket:
                with logged_suppress(logger):
                    _delete_rag_source_file(file_object_name, memory_bucket)
            if _is_upstream_httpx_timeout(e):
                raise HTTPException(
                    status_code=504,
                    detail="Таймаут ответа SVC-RAG при индексации (большой файл или медленный embed). Увеличьте SVC_RAG_INDEX_READ_TIMEOUT (секунды) для backend, по умолчанию 900.",
                ) from e
            raise HTTPException(status_code=502, detail=str(e)) from e
        bump_rag_semantic_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/memory-rag/documents")
async def memory_rag_list():
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.memory_rag_list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/memory-rag/documents/{document_id}")
async def memory_rag_delete(document_id: int):
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.memory_rag_delete_document(document_id)
        if not out.get("ok"):
            raise HTTPException(status_code=404, detail="Документ не найден")
        _delete_rag_source_file(out.get("minio_object"), out.get("minio_bucket"))
        bump_rag_semantic_cache()
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e
