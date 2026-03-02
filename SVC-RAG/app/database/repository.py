# Репозитории документов и векторов (таблицы documents, document_vectors)
import json
import logging
from typing import List, Optional, Tuple

from app.database.connection import PostgreSQLConnection
from app.database.models import Document, DocumentVector

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, db: PostgreSQLConnection):
        self.db = db

    async def create_tables(self):
        async with await self.db.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename)")
        logger.info("Таблицы documents готовы")

    async def create_document(self, document: Document) -> Optional[int]:
        meta = json.dumps(document.metadata) if document.metadata else "{}"
        async with await self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO documents (filename, content, metadata, created_at, updated_at)
                VALUES ($1, $2, $3::jsonb, $4, $5)
                RETURNING id
                """,
                document.filename,
                document.content,
                meta,
                document.created_at,
                document.updated_at,
            )
        return row["id"] if row else None

    async def get_document(self, document_id: int) -> Optional[Document]:
        async with await self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, filename, content, metadata, created_at, updated_at FROM documents WHERE id = $1",
                document_id,
            )
        if not row:
            return None
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}
        return Document(
            id=row["id"],
            filename=row["filename"],
            content=row["content"],
            metadata=meta or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_document_by_filename(self, filename: str) -> Optional[Document]:
        async with await self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, filename, content, metadata, created_at, updated_at FROM documents WHERE filename = $1",
                filename,
            )
        if not row:
            return None
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}
        return Document(
            id=row["id"],
            filename=row["filename"],
            content=row["content"],
            metadata=meta or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_all_documents(self) -> List[Document]:
        async with await self.db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, filename, content, metadata, created_at, updated_at FROM documents ORDER BY id"
            )
        out = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta) if meta else {}
            out.append(
                Document(
                    id=row["id"],
                    filename=row["filename"],
                    content=row["content"],
                    metadata=meta or {},
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return out

    async def delete_document(self, document_id: int) -> bool:
        async with await self.db.acquire() as conn:
            await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
        return True


class VectorRepository:
    def __init__(self, db: PostgreSQLConnection, embedding_dim: int = 384):
        self.db = db
        self.embedding_dim = embedding_dim

    async def create_tables(self):
        async with await self.db.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS document_vectors (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    embedding vector({self.embedding_dim}) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(document_id, chunk_index)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_vectors_embedding_hnsw
                ON document_vectors USING hnsw (embedding vector_cosine_ops)
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_document_vectors_document_id ON document_vectors(document_id)")
        logger.info("Таблицы document_vectors готовы (dim=%s)", self.embedding_dim)

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
            placeholders.append(f"(${base+1}, ${base+2}, ${base+3}, ${base+4}, ${base+5}::jsonb)")
            flat.extend([doc_id, idx, emb, content, meta])
        async with await self.db.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO document_vectors (document_id, chunk_index, embedding, content, metadata)
                VALUES {", ".join(placeholders)}
                """,
                *flat,
            )
        return len(vectors)

    async def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        document_id: Optional[int] = None,
    ) -> List[Tuple[DocumentVector, float]]:
        emb_str = str(query_embedding)
        if document_id:
            q = """
                SELECT id, document_id, chunk_index, embedding::text, content, metadata,
                       1 - (embedding <=> $1::vector) as similarity
                FROM document_vectors WHERE document_id = $2
                ORDER BY embedding <=> $1::vector LIMIT $3
            """
            rows = None
            async with await self.db.acquire() as conn:
                rows = await conn.fetch(q, emb_str, document_id, limit)
        else:
            q = """
                SELECT id, document_id, chunk_index, embedding::text, content, metadata,
                       1 - (embedding <=> $1::vector) as similarity
                FROM document_vectors
                ORDER BY embedding <=> $1::vector LIMIT $2
            """
            async with await self.db.acquire() as conn:
                rows = await conn.fetch(q, emb_str, limit)
        result = []
        for row in rows:
            emb = [float(x.strip()) for x in row["embedding"].strip("[]").split(",")]
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta) if meta else {}
            result.append(
                (
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
            )
        return result

    async def get_vectors_by_document(self, document_id: int) -> List[DocumentVector]:
        async with await self.db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, document_id, chunk_index, embedding::text, content, metadata FROM document_vectors WHERE document_id = $1 ORDER BY chunk_index",
                document_id,
            )
        out = []
        for row in rows:
            emb = [float(x.strip()) for x in row["embedding"].strip("[]").split(",")]
            meta = row["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta) if meta else {}
            out.append(
                DocumentVector(
                    id=row["id"],
                    document_id=row["document_id"],
                    chunk_index=row["chunk_index"],
                    embedding=emb,
                    content=row["content"],
                    metadata=meta or {},
                )
            )
        return out

    async def delete_vectors_by_document(self, document_id: int) -> bool:
        async with await self.db.acquire() as conn:
            await conn.execute("DELETE FROM document_vectors WHERE document_id = $1", document_id)
        return True

    async def get_all_contents_for_bm25(self) -> List[Tuple[int, int, str]]:
        """Возвращает (document_id, chunk_index, content) для всех чанков — для построения BM25."""
        async with await self.db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT document_id, chunk_index, content FROM document_vectors ORDER BY document_id, chunk_index"
            )
        return [(r["document_id"], r["chunk_index"], r["content"]) for r in rows]
