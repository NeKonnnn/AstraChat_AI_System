from fastapi import APIRouter
from .endpoints import documents, search, health

router = APIRouter()
router.include_router(documents.router, prefix="/documents", tags=["Документы"])
router.include_router(search.router, prefix="/search", tags=["Поиск"])
router.include_router(health.router, tags=["Здоровье"])
