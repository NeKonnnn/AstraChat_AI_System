# Зависимости: БД, клиент RAG-MODELS, RagService, KbService, ProjectRagService
import logging
from typing import Optional

from app.clients.rag_models_client import RagModelsClient
from app.database.connection import PostgreSQLConnection, get_postgres_connection
from app.database.kb_repository import KbDocumentRepository, KbVectorRepository
from app.database.memory_rag_repository import (
    MemoryRagDocumentRepository,
    MemoryRagVectorRepository,
)
from app.database.project_rag_repository import (
    ProjectRagDocumentRepository,
    ProjectRagVectorRepository,
)
from app.database.graph_repository import GraphRepository
from app.database.repository import DocumentRepository, VectorRepository
from app.services.kb_service import KbService
from app.services.memory_rag_service import MemoryRagService
from app.services.project_rag_service import ProjectRagService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)

_pg: Optional[PostgreSQLConnection] = None
_doc_repo: Optional[DocumentRepository] = None
_vector_repo: Optional[VectorRepository] = None
_rag_service: Optional[RagService] = None
_kb_doc_repo: Optional[KbDocumentRepository] = None
_kb_vector_repo: Optional[KbVectorRepository] = None
_rag_client: Optional[RagModelsClient] = None
_kb_service: Optional[KbService] = None
_mem_doc_repo: Optional[MemoryRagDocumentRepository] = None
_mem_vector_repo: Optional[MemoryRagVectorRepository] = None
_memory_rag_service: Optional[MemoryRagService] = None
_proj_doc_repo: Optional[ProjectRagDocumentRepository] = None
_proj_vector_repo: Optional[ProjectRagVectorRepository] = None
_project_rag_service: Optional[ProjectRagService] = None
_graph_repo: Optional[GraphRepository] = None

async def get_db():
    """Подключение к PostgreSQL (один раз при старте)."""
    global _pg, _doc_repo, _vector_repo, _kb_doc_repo, _kb_vector_repo
    global _mem_doc_repo, _mem_vector_repo, _proj_doc_repo, _proj_vector_repo
    global _graph_repo
    if _pg is None:
        _pg = get_postgres_connection()
        ok = await _pg.connect()
        if not ok:
            raise RuntimeError("Не удалось подключиться к PostgreSQL")
        from app.core.config import get_settings

        dim = get_settings().postgresql.embedding_dim
        _doc_repo = DocumentRepository(_pg)
        _vector_repo = VectorRepository(_pg, embedding_dim=dim)
        _kb_doc_repo = KbDocumentRepository(_pg)
        _kb_vector_repo = KbVectorRepository(_pg, embedding_dim=dim)
        _mem_doc_repo = MemoryRagDocumentRepository(_pg)
        _mem_vector_repo = MemoryRagVectorRepository(_pg, embedding_dim=dim)
        _proj_doc_repo = ProjectRagDocumentRepository(_pg)
        _proj_vector_repo = ProjectRagVectorRepository(_pg, embedding_dim=dim)
        _graph_repo = GraphRepository(_pg)
        await _doc_repo.create_tables()
        await _vector_repo.create_tables()
        await _kb_doc_repo.create_tables()
        await _kb_vector_repo.create_tables()
        await _mem_doc_repo.create_tables()
        await _mem_vector_repo.create_tables()
        await _proj_doc_repo.create_tables()
        await _proj_vector_repo.create_tables()
        await _graph_repo.create_tables()
    return _pg

# Текущий выбор источника моделей ПО ТИПАМ. provider=None - «ещё не
# инициализировано из конфига». Persist не нужен: источник истины - backend,
# после рестарта svc-rag он запушит выбор заново (reconcile по /v1/health).
_model_choice = {
    "embedding": {"provider": None, "model": None},
    "reranker": {"provider": None, "model": None},
}

def _init_model_choice_from_config() -> None:
    from app.core.config import get_settings

    cfg = get_settings()
    section = getattr(cfg, "rag_models", None)
    provider = (getattr(section, "provider", "") or "native").strip()
    emb_model = None
    rer_model = None
    if provider.lower() != "native":
        for entry in getattr(section, "providers", None) or []:
            if entry.id == provider:
                emb_model = entry.embedding_model or None
                rer_model = entry.reranker_model or None
                break
    if _model_choice["embedding"]["provider"] is None:
        _model_choice["embedding"] = {"provider": provider, "model": emb_model}
    if _model_choice["reranker"]["provider"] is None:
        _model_choice["reranker"] = {"provider": provider, "model": rer_model}

class SplitRagClient:
    """Составной клиент: embed-часть и rerank-часть от разных провайдеров.

    Контракт как у RagModelsClient: embed, embed_single, rerank, health.
    """

    def __init__(self, embed_client, rerank_client):
        self.embed_client = embed_client
        self.rerank_client = rerank_client

    async def embed(self, texts):
        return await self.embed_client.embed(texts)

    async def embed_single(self, text):
        return await self.embed_client.embed_single(text)

    async def rerank(self, query, passages, top_k=20):
        return await self.rerank_client.rerank(query, passages, top_k=top_k)

    async def health(self) -> bool:
        # embed-часть первична: без эмбеддингов RAG нежизнеспособен,
        # без реранка - только хуже ранжирование.
        return await self.embed_client.health()

def _provider_entry(provider_id: str):
    from app.core.config import get_settings

    for entry in getattr(get_settings().rag_models, "providers", None) or []:
        if entry.id == provider_id:
            return entry
    return None

def _client_for(model_type: str):
    from app.core.config import get_settings

    choice = _model_choice[model_type]
    provider = (choice["provider"] or "native").strip()
    if provider.lower() == "native":
        return RagModelsClient()
    entry = _provider_entry(provider)
    if entry is None:
        logger.error(
            "[RAG-MODELS] провайдер '%s' (%s) не найден в rag_models.providers - откат на native",
            provider,
            model_type,
        )
        return RagModelsClient()
    from app.clients.openai_models_compat_client import OpenAICompatModelsClient

    return OpenAICompatModelsClient(
        provider_id=entry.id,
        base_url=entry.base_url,
        api_key_env=entry.api_key_env or None,
        embedding_model=choice["model"] if model_type == "embedding" else None,
        reranker_model=choice["model"] if model_type == "reranker" else None,
        timeout=entry.timeout,
        embed_batch_size=get_settings().rag_models_client.embed_batch_size,
    )

def _make_rag_client():
    """Клиент моделей RAG по текущему выбору (_model_choice).

    Оба типа native (дефолт) - обычный RagModelsClient, ровно как всегда.
    Иначе - SplitRagClient из независимых embed- и rerank-частей.
    """
    _init_model_choice_from_config()
    e_provider = (_model_choice["embedding"]["provider"] or "native").lower()
    r_provider = (_model_choice["reranker"]["provider"] or "native").lower()
    if e_provider == "native" and r_provider == "native":
        logger.info("[RAG-MODELS] провайдер: native (svc-rag-models)")
        return RagModelsClient()
    logger.info(
        "[RAG-MODELS] провайдеры: embedding=%s(%s) reranker=%s(%s)",
        _model_choice["embedding"]["provider"],
        _model_choice["embedding"]["model"],
        _model_choice["reranker"]["provider"],
        _model_choice["reranker"]["model"],
    )
    return SplitRagClient(_client_for("embedding"), _client_for("reranker"))

async def get_rag_service() -> RagService:
    """Legacy global RagService (/v1/documents, /v1/search)."""
    global _rag_service, _rag_client
    if _rag_service is None:
        await get_db()
        if _rag_client is None:
            _rag_client = _make_rag_client()
        _rag_service = RagService(_doc_repo, _vector_repo, _rag_client, _graph_repo)
    return _rag_service

async def get_kb_service() -> KbService:
    """KbService для постоянной Базы Знаний."""
    global _kb_service, _rag_client
    if _kb_service is None:
        await get_db()
        if _rag_client is None:
            _rag_client = _make_rag_client()
        _kb_service = KbService(_kb_doc_repo, _kb_vector_repo, _rag_client, _graph_repo)
    return _kb_service

async def get_memory_rag_service() -> MemoryRagService:
    global _memory_rag_service, _rag_client
    if _memory_rag_service is None:
        await get_db()
        if _rag_client is None:
            _rag_client = _make_rag_client()
        _memory_rag_service = MemoryRagService(
            _mem_doc_repo, _mem_vector_repo, _rag_client, _graph_repo
        )
    return _memory_rag_service

async def get_project_rag_service() -> ProjectRagService:
    global _project_rag_service, _rag_client
    if _project_rag_service is None:
        await get_db()
        if _rag_client is None:
            _rag_client = _make_rag_client()
        _project_rag_service = ProjectRagService(
            _proj_doc_repo, _proj_vector_repo, _rag_client, _graph_repo
        )
    return _project_rag_service

async def ensure_embedding_dim(embedding_dim: int) -> dict:
    """Синхронизировать размерность pgvector и in-memory репозиториев с моделью."""
    await get_db()
    from app.core.config import get_settings
    from app.database.embedding_schema import migrate_vector_tables

    dim = int(embedding_dim)
    settings = get_settings()
    async with await _pg.acquire() as conn:
        async with conn.transaction():
            result = await migrate_vector_tables(conn, dim)
    settings.postgresql.embedding_dim = dim
    for repo in (_vector_repo, _kb_vector_repo, _mem_vector_repo, _proj_vector_repo):
        if repo is not None:
            repo.embedding_dim = dim
    if result.get("migrated"):
        logger.warning(
            "embedding_dim=%s: миграция schema завершена, cleared_rows=%s tables=%s",
            dim,
            result.get("cleared_rows"),
            result.get("changed_tables"),
        )
    return result

async def ensure_memory_chunk_consistency() -> None:
    """Автоперенарезка Библиотеки при смене RAG_MEMORY_* (зовётся на старте)."""
    import asyncio
    import os

    v = (os.getenv("RAG_MEMORY_RECHUNK_ON_CHANGE", "true") or "").strip().lower()
    if v not in ("1", "true", "yes", "on"):
        return
    from app.services.chunker import (
        normalize_chunking_strategy,
        resolve_chunk_params,
    )
    from app.services.memory_rag_service import _memory_chunk_params

    cs_env, co_env, strat_env = _memory_chunk_params()
    cs, co = resolve_chunk_params(cs_env, co_env)
    strat = normalize_chunking_strategy(strat_env)

    pg = await get_db()
    async with await pg.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_chunk_state (
                id INT PRIMARY KEY CHECK (id = 1),
                strategy TEXT NOT NULL,
                chunk_size INT NOT NULL,
                chunk_overlap INT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        row = await conn.fetchrow(
            "SELECT strategy, chunk_size, chunk_overlap FROM memory_chunk_state WHERE id = 1"
        )
        if row is None:
            await conn.execute(
                "INSERT INTO memory_chunk_state (id, strategy, chunk_size, chunk_overlap) "
                "VALUES (1, $1, $2, $3)",
                strat,
                cs,
                co,
            )
            logger.info(
                "[MEMORY-CHUNK] настройки нарезки Библиотеки зафиксированы: %s/%s/%s",
                strat,
                cs,
                co,
            )
            return
        if (row["strategy"], int(row["chunk_size"]), int(row["chunk_overlap"])) == (
            strat,
            cs,
            co,
        ):
            return
        await conn.execute(
            "UPDATE memory_chunk_state SET strategy=$1, chunk_size=$2, "
            "chunk_overlap=$3, updated_at=now() WHERE id=1",
            strat,
            cs,
            co,
        )
    logger.warning(
        "[MEMORY-CHUNK] нарезка Библиотеки изменилась (%s/%s/%s -> %s/%s/%s) — автоперенарезка",
        row["strategy"],
        row["chunk_size"],
        row["chunk_overlap"],
        strat,
        cs,
        co,
    )
    svc = await get_memory_rag_service()
    from app.api.endpoints.memory_rag import _memory_reindex_bg

    asyncio.create_task(_memory_reindex_bg(svc, None, None, None))

def get_current_rag_client():
    """Текущий клиент моделей RAG (None до первого обращения к сервисам)."""
    return _rag_client

def get_model_choice() -> dict:
    """Копия текущего выбора провайдеров/моделей по типам (для /v1/health)."""
    _init_model_choice_from_config()
    return {
        "embedding": dict(_model_choice["embedding"]),
        "reranker": dict(_model_choice["reranker"]),
    }

async def set_rag_models_provider(
    model_type: str,
    provider: str,
    model: Optional[str] = None,
) -> dict:
    """Переключить источник моделей ОДНОГО типа на лету (дёргает backend).

    Выбор живёт в памяти процесса: после рестарта svc-rag вернётся к конфигу,
    backend увидит это по /v1/health и запушит выбор заново (reconcile).
    """
    global _rag_client
    from app.core.config import get_settings

    mt = (model_type or "").strip().lower()
    if mt not in ("embedding", "reranker"):
        raise ValueError("model_type должен быть embedding или reranker")
    target = (provider or "").strip()
    section = get_settings().rag_models
    known = ["native"] + [e.id for e in section.providers]
    if target not in known:
        raise ValueError(f"Неизвестный провайдер '{target}'. Доступны: {known}")

    _init_model_choice_from_config()
    _model_choice[mt] = {
        "provider": target,
        "model": (model or "").strip() or None,
    }

    new_client = _make_rag_client()
    _rag_client = new_client
    replaced = 0
    for svc_name in (
        "_rag_service",
        "_kb_service",
        "_memory_rag_service",
        "_project_rag_service",
    ):
        svc = globals().get(svc_name)
        if svc is not None:
            svc.rag_client = new_client
            replaced += 1

    result = {
        "model_type": mt,
        "provider": target,
        "model": _model_choice[mt]["model"],
        "services_updated": replaced,
    }
    # Для внешнего эмбеддера сразу узнаём размерность: backend по ней решает,
    # нужна ли миграция схемы (сам svc-rag НИЧЕГО не мигрирует - дим-гард).
    if mt == "embedding" and target != "native":
        embed_part = getattr(new_client, "embed_client", new_client)
        probe = getattr(embed_part, "probe_dim", None)
        if probe is not None:
            try:
                result["embedding_dim"] = await probe()
            except Exception as e:
                logger.error("[RAG-MODELS] probe_dim не удался: %s", e)
                result["embedding_dim"] = None
                result["probe_error"] = str(e)
    logger.warning("[RAG-MODELS] переключение: %s", result)
    return result