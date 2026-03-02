# Индексация, список и удаление документов
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.dependencies import get_rag_service
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)
router = APIRouter()


class IndexResponse(BaseModel):
    ok: bool
    document_id: int | None
    filename: str | None
    chunks_count: int | None
    error: str | None = None


class DocumentItem(BaseModel):
    id: int
    filename: str
    created_at: str | None


class ConfidenceDocumentItem(BaseModel):
    filename: str
    confidence: float
    text_length: int
    file_type: str
    words_count: int


class ConfidenceFormattedText(BaseModel):
    filename: str
    formatted_text: str
    words: List[dict]


class ConfidenceReport(BaseModel):
    total_documents: int
    documents: List[ConfidenceDocumentItem]
    average_confidence: float
    overall_confidence: float
    total_words: int
    formatted_texts: List[ConfidenceFormattedText]


class ImageMinioInfo(BaseModel):
    filename: str
    minio_object: Optional[str] = None
    minio_bucket: Optional[str] = None
    path: Optional[str] = None


@router.post("", response_model=IndexResponse)
async def index_document(
    file: UploadFile = File(...),
    minio_object: Optional[str] = Form(None),
    minio_bucket: Optional[str] = Form(None),
    original_path: Optional[str] = Form(None),
    rag: RagService = Depends(get_rag_service),
):
    """Загрузить файл (PDF, DOCX, XLSX, TXT), распарсить, нарезать чанки, получить эмбеддинги и сохранить в БД.

    Дополнительно можно передать информацию о MinIO/пути файла:
    - minio_object: имя объекта в MinIO
    - minio_bucket: имя бакета в MinIO
    - original_path: исходный путь к файлу (если есть)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Нужно имя файла")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Файл пустой")

    image_meta = None
    if minio_object or minio_bucket or original_path:
        image_meta = {
            "minio_object": minio_object,
            "minio_bucket": minio_bucket,
            "path": original_path,
        }

    result = await rag.index_document(data, file.filename, image_meta=image_meta)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("error", "Ошибка индексации"))
    return IndexResponse(
        ok=True,
        document_id=result.get("document_id"),
        filename=result.get("filename"),
        chunks_count=result.get("chunks_count"),
    )


@router.get("", response_model=List[DocumentItem])
async def list_documents(rag: RagService = Depends(get_rag_service)):
    """Список проиндексированных документов."""
    docs = await rag.list_documents()
    return [
        DocumentItem(id=d["id"], filename=d["filename"], created_at=d.get("created_at"))
        for d in docs
    ]


@router.get("/report/confidence", response_model=ConfidenceReport)
async def confidence_report(rag: RagService = Depends(get_rag_service)):
    """Агрегированный отчёт об уверенности (как в backend get_confidence_report_data)."""
    data = await rag.get_confidence_report()
    return ConfidenceReport(**data)


@router.get("/minio-info/{filename}", response_model=ImageMinioInfo | None)
async def get_minio_info(
    filename: str,
    rag: RagService = Depends(get_rag_service),
):
    """Получить информацию о MinIO/пути для изображения по имени файла."""
    info = await rag.get_image_minio_info(filename)
    if not info:
        return None
    return ImageMinioInfo(
        filename=filename,
        minio_object=info.get("minio_object"),
        minio_bucket=info.get("minio_bucket"),
        path=info.get("path"),
    )


@router.delete("/by-filename/{filename}")
async def delete_document_by_filename(
    filename: str,
    rag: RagService = Depends(get_rag_service),
):
    """Удалить документ по имени файла (для обратной совместимости с backend DocumentProcessor)."""
    ok = await rag.delete_document_by_filename(filename)
    if not ok:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {"ok": True, "filename": filename}


class DocumentChunkHit(BaseModel):
    content: str
    document_id: int
    chunk_index: int


class DocumentChunksResponse(BaseModel):
    chunks: List[DocumentChunkHit]


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    document_id: int,
    start: int = Query(0, ge=0),
    limit: int = Query(3, ge=1, le=10),
    rag: RagService = Depends(get_rag_service),
):
    """Получить первые (или с заданного смещения) чанки документа по порядку. Нужно для запросов про оглавление/структуру."""
    result = await rag.get_document_chunks(document_id, start=start, limit=limit)
    return DocumentChunksResponse(
        chunks=[
            DocumentChunkHit(content=c, document_id=doc_id, chunk_index=idx)
            for c, doc_id, idx in result
        ]
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    rag: RagService = Depends(get_rag_service),
):
    """Удалить документ и все его чанки из БД."""
    await rag.delete_document(document_id)
    return {"ok": True, "document_id": document_id}
