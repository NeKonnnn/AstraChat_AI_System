# Зависимости: БД, клиент RAG-MODELS, RagService, KbService
import logging
from typing import Optional

from app.clients.rag_models_client import RagModelsClient
from app.database.connection import PostgreSQLConnection, get_postgres_connection
from app.database.repository import DocumentRepository, VectorRepository
from app.database.kb_repository import KbDocumentRepository, KbVectorRepository
from app.services.rag_service import RagService
from app.services.kb_service import KbService

logger = logging.getLogger(__name__)

_pg: Optional[PostgreSQLConnection] = None
_doc_repo: Optional[DocumentRepository] = None
_vector_repo: Optional[VectorRepository] = None
_kb_doc_repo: Optional[KbDocumentRepository] = None
_kb_vector_repo: Optional[KbVectorRepository] = None
_rag_client: Optional[RagModelsClient] = None
_rag_service: Optional[RagService] = None
_kb_service: Optional[KbService] = None


async def get_db():
    """Подключение к PostgreSQL (один раз при старте)."""
    global _pg, _doc_repo, _vector_repo, _kb_doc_repo, _kb_vector_repo
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
        await _doc_repo.create_tables()
        await _vector_repo.create_tables()
        await _kb_doc_repo.create_tables()
        await _kb_vector_repo.create_tables()
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


async def get_kb_service() -> KbService:
    """KbService для постоянной Базы Знаний."""
    global _kb_service, _rag_client
    if _kb_service is None:
        await get_db()
        if _rag_client is None:
            _rag_client = RagModelsClient()
        _kb_service = KbService(_kb_doc_repo, _kb_vector_repo, _rag_client)
    return _kb_service
