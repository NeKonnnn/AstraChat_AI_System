# Модели документов и векторов для RAG
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Document(BaseModel):
    id: Optional[int] = None
    filename: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentVector(BaseModel):
    id: Optional[int] = None
    document_id: int
    chunk_index: int
    embedding: List[float]
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
