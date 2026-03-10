from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Union

from app.dependencies.rag_models_handler import get_rag_models_handler
from app.core.config import settings

router = APIRouter()


class EmbedRequest(BaseModel):
    text: Union[str, None] = None
    texts: Union[List[str], None] = None

    def get_texts(self) -> List[str]:
        if self.texts:
            return self.texts
        if self.text is not None:
            return [self.text]
        return []


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    embedding_dim: int


@router.post("/embed", response_model=EmbedResponse)
async def embed_texts(request: EmbedRequest):
    # Считаем эмбеддинги для одного или нескольких текстов. На выходе - векторы
    if not settings.rag_models.enabled:
        raise HTTPException(status_code=503, detail="Сервис RAG-моделей выключен")
    texts = request.get_texts()
    if not texts:
        raise HTTPException(status_code=400, detail="Нужно передать text или texts в теле запроса")
    handler = await get_rag_models_handler()
    if handler is None:
        raise HTTPException(status_code=503, detail="Эмбеддинг-модель не загружена")
    model = handler["embedding_model"]
    embeddings = model.encode(texts, convert_to_numpy=True)
    if hasattr(embeddings, "ndim") and embeddings.ndim == 1:
        embeddings = [embeddings.tolist()]
    else:
        embeddings = embeddings.tolist()
    dim = handler.get("embedding_dim", len(embeddings[0]) if embeddings else 384)
    return EmbedResponse(embeddings=embeddings, embedding_dim=int(dim))
