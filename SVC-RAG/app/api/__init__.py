from fastapi import APIRouter
from .endpoints import documents, search, health, kb, memory_rag, project_rag

router = APIRouter()
router.include_router(documents.router, prefix="/documents", tags=["Документы"])
router.include_router(search.router, prefix="/search", tags=["Поиск"])
router.include_router(health.router, tags=["Здоровье"])
router.include_router(kb.router, prefix="/kb", tags=["База Знаний"])
router.include_router(memory_rag.router, prefix="/memory-rag", tags=["Библиотека памяти RAG"])
router.include_router(project_rag.router, prefix="/project-rag", tags=["RAG проектов"])
