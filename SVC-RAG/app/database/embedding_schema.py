"""Синхронизация размерности pgvector с текущей embedding-моделью.

CREATE TABLE IF NOT EXISTS не меняет уже созданный vector(N).
При смене модели (384 → 1536 и т.п.) нужно ALTER + очистка старых векторов.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VECTOR_TABLES: Tuple[str, ...] = (
    "document_vectors",
    "kb_vectors",
    "memory_rag_vectors",
    "project_rag_vectors",
)

_INDEX_BY_TABLE = {
    "document_vectors": "idx_document_vectors_embedding_hnsw",
    "kb_vectors": "idx_kb_vectors_embedding_hnsw",
    "memory_rag_vectors": "idx_memory_rag_vectors_embedding_hnsw",
    "project_rag_vectors": "idx_proj_rag_vectors_embedding_hnsw",
}


async def get_column_vector_dim(conn, table: str) -> Optional[int]:
    """Текущая размерность колонки embedding или None, если таблицы нет."""
    row = await conn.fetchrow(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS ft
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'public'
          AND c.relname = $1
          AND a.attname = 'embedding'
          AND NOT a.attisdropped
        """,
        table,
    )
    if not row or not row["ft"]:
        return None
    m = re.search(r"vector\((\d+)\)", str(row["ft"]))
    return int(m.group(1)) if m else None


async def migrate_vector_tables(conn, target_dim: int) -> Dict[str, Any]:
    """Привести все vector-таблицы к target_dim. Старые векторы очищаются."""
    if target_dim < 1:
        raise ValueError(f"Некорректная embedding_dim: {target_dim}")

    changed: List[str] = []
    unchanged: List[str] = []
    cleared_rows = 0

    for table in VECTOR_TABLES:
        exists = await conn.fetchval(
            "SELECT to_regclass($1) IS NOT NULL",
            f"public.{table}",
        )
        if not exists:
            continue

        current = await get_column_vector_dim(conn, table)
        if current == target_dim:
            unchanged.append(table)
            continue

        count = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}") or 0)
        index_name = _INDEX_BY_TABLE.get(table)
        if index_name:
            await conn.execute(f"DROP INDEX IF EXISTS {index_name}")

        # Пустая таблица: ALTER TYPE. С данными — TRUNCATE, иначе ALTER не сконвертирует.
        if count > 0:
            await conn.execute(f"TRUNCATE TABLE {table}")
            cleared_rows += count

        await conn.execute(
            f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({int(target_dim)})"
        )
        if index_name:
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {table} USING hnsw (embedding vector_cosine_ops)
                """
            )
        changed.append(table)
        logger.warning(
            "Миграция %s: vector(%s) → vector(%s), очищено строк=%s",
            table,
            current,
            target_dim,
            count,
        )

    return {
        "embedding_dim": target_dim,
        "changed_tables": changed,
        "unchanged_tables": unchanged,
        "cleared_rows": cleared_rows,
        "migrated": bool(changed),
    }
