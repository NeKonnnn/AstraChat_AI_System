# Проверка готовности: сам сервис, SVC-RAG-MODELS, PostgreSQL
from fastapi import APIRouter
from pydantic import BaseModel

from app.clients.rag_models_client import RagModelsClient
from app.dependencies import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    rag_models: bool
    postgresql: bool


@router.get("/health", response_model=HealthResponse)
async def health():
    """Готовность сервиса и зависимостей (RAG-MODELS, PostgreSQL)."""
    pg_ok = False
    try:
        db = await get_db()
        pg_ok = await db.health_check()
    except Exception:
        pass

    rag_ok = False
    try:
        rag_ok = await RagModelsClient().health()
    except Exception:
        pass

    status = "healthy" if (pg_ok and rag_ok) else "degraded"
    return HealthResponse(status=status, rag_models=rag_ok, postgresql=pg_ok)
