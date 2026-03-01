# Зависимости: БД, клиент RAG-MODELS, RagService
import logging
from typing import Optional

from app.clients.rag_models_client import RagModelsClient
from app.database.connection import PostgreSQLConnection, get_postgres_connection
from app.database.repository import DocumentRepository, VectorRepository
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)

_pg: Optional[PostgreSQLConnection] = None
_doc_repo: Optional[DocumentRepository] = None
_vector_repo: Optional[VectorRepository] = None
_rag_client: Optional[RagModelsClient] = None
_rag_service: Optional[RagService] = None


async def get_db():
    """Подключение к PostgreSQL (один раз при старте)."""
    global _pg, _doc_repo, _vector_repo
    if _pg is None:
        _pg = get_postgres_connection()
        ok = await _pg.connect()
        if not ok:
            raise RuntimeError("Не удалось подключиться к PostgreSQL")
        from app.core.config import get_settings
        dim = get_settings().postgresql.embedding_dim
        _doc_repo = DocumentRepository(_pg)
        _vector_repo = VectorRepository(_pg, embedding_dim=dim)
        await _doc_repo.create_tables()
        await _vector_repo.create_tables()
    return _pg


async def get_rag_service() -> RagService:
    """RagService с репозиториями и клиентом к RAG-MODELS."""
    global _rag_service, _rag_client
    if _rag_service is None:
        await get_db()
        if _rag_client is None:
            _rag_client = RagModelsClient()
        _rag_service = RagService(_doc_repo, _vector_repo, _rag_client)
    return _rag_service
