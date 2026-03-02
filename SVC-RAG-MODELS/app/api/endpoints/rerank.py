from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from app.dependencies.rag_models_handler import get_rag_models_handler
from app.core.config import settings

router = APIRouter()


class RerankRequest(BaseModel):
    query: str
    passages: List[str]
    top_k: int = 20


class RerankResponse(BaseModel):
    indices: List[int]
    scores: List[float]


@router.post("/rerank", response_model=RerankResponse)
async def rerank_passages(request: RerankRequest):
    # Переранжируем пассажи по релевантности к запросу. Возвращаем top_k индексов и скоры.
    if not settings.rag_models.enabled:
        raise HTTPException(status_code=503, detail="Сервис RAG-моделей выключен")
    if not request.passages:
        return RerankResponse(indices=[], scores=[])
    handler = await get_rag_models_handler()
    if handler is None:
        raise HTTPException(status_code=503, detail="Реранкер не загружен")
    model = handler["reranker_model"]
    pairs = [[request.query, p] for p in request.passages]
    scores = model.predict(pairs)
    if hasattr(scores, "__len__") and len(scores) != len(request.passages):
        scores = list(scores)
    else:
        scores = scores.tolist() if hasattr(scores, "tolist") else list(scores)
    top_k = min(request.top_k, len(scores))
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    top = indexed[:top_k]
    return RerankResponse(
        indices=[i for i, _ in top],
        scores=[float(s) for _, s in top],
    )
