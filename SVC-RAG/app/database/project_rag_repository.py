# Репозиторий для RAG-файлов проектов: project_rag_documents + project_rag_vectors
# Каждый документ привязан к project_id; при удалении проекта все его данные удаляются каскадом.
import json
import logging
from typing import List, Optional, Tuple

from app.database.connection import PostgreSQLConnection
from app.database.models import Document, DocumentVector

logger = logging.getLogger(__name__)


class ProjectRagDocumentRepository:
    def __init__(self, db: PostgreSQLConnection):
        self.db = db

    async def create_tables(self):
        async with await self.db.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS project_rag_documents (
                    id SERIAL PRIMARY KEY,
                    project_id VARCHAR(128) NOT NULL,
                    filename VARCHAR(512) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proj_rag_docs_project_id ON project_rag_documents(project_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proj_rag_docs_created ON project_rag_documents(created_at DESC)"
            )
        logger.info("Таблица project_rag_documents готова")

    async def create_document(self, project_id: str, document: Document) -> Optional[int]:
        meta = json.dumps(document.metadata) if document.metadata else "{}"
        async with await self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO project_rag_documents
                    (project_id, filename, content, metadata, created_at, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                RETURNING id
                """,
                project_id,
                document.filename,
                document.content,
                meta,
                document.created_at,
                document.updated_at,
            )
        return row["id"] if row else None

    async def get_document(self, document_id: int) -> Optional[dict]:
        async with await self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, project_id, filename, content, metadata, created_at, updated_at "
                "FROM project_rag_documents WHERE id = $1",
                document_id,
            )
        if not row:
            return None
        return self._row_to_dict(row)

    async def get_documents_by_project(self, project_id: str) -> List[dict]:
        async with await self.db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, project_id, filename, content, metadata, created_at, updated_at "
                "FROM project_rag_documents WHERE project_id = $1 ORDER BY created_at DESC",
                project_id,
            )
        return [self._row_to_dict(r) for r in rows]

    async def delete_document(self, document_id: int) -> bool:
        async with await self.db.acquire() as conn:
            await conn.execute("DELETE FROM project_rag_documents WHERE id = $1", document_id)
        return True

    async def delete_documents_by_project(self, project_id: str) -> int:
        """Удаляет все документы проекта. Возвращает количество удалённых."""
        async with await self.db.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM project_rag_documents WHERE project_id = $1", project_id
            )
        # asyncpg возвращает "DELETE N"
        try:
            return int(result.split()[-1])
        except Exception:
            return 0

    def _row_to_dict(self, row) -> dict:
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "filename": row["filename"],
            "content": row["content"],
            "metadata": meta or {},
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


class ProjectRagVectorRepository:
    def __init__(self, db: PostgreSQLConnection, embedding_dim: int = 384):
        self.db = db
        self.embedding_dim = embedding_dim

    async def create_tables(self):
        async with await self.db.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS project_rag_vectors (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER NOT NULL
                        REFERENCES project_rag_documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    embedding vector({self.embedding_dim}) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(document_id, chunk_index)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proj_rag_vectors_embedding_hnsw
                ON project_rag_vectors USING hnsw (embedding vector_cosine_ops)
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proj_rag_vectors_doc_id ON project_rag_vectors(document_id)"
            )
        logger.info("Таблица project_rag_vectors готова (dim=%s)", self.embedding_dim)

    async def create_vectors_batch(self, vectors: List[DocumentVector]) -> int:
        if not vectors:
            return 0
        values = []
        for v in vectors:
            meta = json.dumps(v.metadata) if v.metadata else "{}"
            values.append((v.document_id, v.chunk_index, str(v.embedding), v.content, meta))
        placeholders = []
        flat = []
        for i, (doc_id, idx, emb, content, meta) in enumerate(values):
            base = i * 5
            placeholders.append(
                f"(${base+1}, ${base+2}, ${base+3}::vector, ${base+4}, ${base+5}::jsonb)"
            )
            flat.extend([doc_id, idx, emb, content, meta])
        async with await self.db.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO project_rag_vectors
                    (document_id, chunk_index, embedding, content, metadata)
                VALUES {", ".join(placeholders)}
                ON CONFLICT (document_id, chunk_index) DO NOTHING
                """,
                *flat,
            )
        return len(vectors)

    async def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        project_id: Optional[str] = None,
        document_id: Optional[int] = None,
    ) -> List[Tuple[DocumentVector, float]]:
        emb_str = str(query_embedding)
        if document_id is not None:
            q = """
                SELECT v.id, v.document_id, v.chunk_index, v.embedding::text, v.content, v.metadata,
                       1 - (v.embedding <=> $1::vector) as similarity
                FROM project_rag_vectors v
                WHERE v.document_id = $2
                ORDER BY v.embedding <=> $1::vector LIMIT $3
            """
            async with await self.db.acquire() as conn:
                rows = await conn.fetch(q, emb_str, document_id, limit)
        elif project_id is not None:
            q = """
                SELECT v.id, v.document_id, v.chunk_index, v.embedding::text, v.content, v.metadata,
                       1 - (v.embedding <=> $1::vector) as similarity
                FROM project_rag_vectors v
                JOIN project_rag_documents d ON d.id = v.document_id
                WHERE d.project_id = $2
                ORDER BY v.embedding <=> $1::vector LIMIT $3
            """
            async with await self.db.acquire() as conn:
                rows = await conn.fetch(q, emb_str, project_id, limit)
        else:
            q = """
                SELECT id, document_id, chunk_index, embedding::text, content, metadata,
                       1 - (embedding <=> $1::vector) as similarity
                FROM project_rag_vectors
                ORDER BY embedding <=> $1::vector LIMIT $2
            """
            async with await self.db.acquire() as conn:
                rows = await conn.fetch(q, emb_str, limit)
        return [self._row_to_dv(row) for row in rows]

    def _row_to_dv(self, row) -> Tuple[DocumentVector, float]:
        emb = [float(x.strip()) for x in row["embedding"].strip("[]").split(",")]
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}
        return (
            DocumentVector(
                id=row["id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                embedding=emb,
                content=row["content"],
                metadata=meta or {},
            ),
            float(row["similarity"]),
        )

    async def delete_vectors_by_document(self, document_id: int) -> bool:
        async with await self.db.acquire() as conn:
            await conn.execute(
                "DELETE FROM project_rag_vectors WHERE document_id = $1", document_id
            )
        return True
