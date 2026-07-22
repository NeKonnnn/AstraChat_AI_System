"""Синхронизация размерности pgvector с текущей embedding-моделью.

CREATE TABLE IF NOT EXISTS не меняет уже созданный vector(N).
При смене модели (384 → 1536 и т.п.) нужно ALTER + очистка старых векторов.

Размерность всегда берётся из выбранной модели (get_sentence_embedding_dimension).
HNSW в pgvector ограничен 2000 измерениями — при большем dim индекс не создаём
(поиск по <=> всё равно работает, но без ANN).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# https://github.com/pgvector/pgvector#hnsw — max dimensions for HNSW/IVFFlat on vector
HNSW_MAX_DIM = 2000

VECTOR_TABLES: Tuple[str, ...] = (
    "kb_vectors",
    "memory_rag_vectors",
    "project_rag_vectors",
)

_INDEX_BY_TABLE = {
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

async def drop_embedding_index(conn, table: str) -> None:
    index_name = _INDEX_BY_TABLE.get(table)
    if index_name:
        await conn.execute(f"DROP INDEX IF EXISTS {index_name}")

async def create_embedding_index(conn, table: str, dim: int) -> bool:
    """Создать HNSW, если фактическая размерность колонки позволяет.

    Важно проверять колонку в БД, а не только requested dim из конфига:
    после смены модели колонка уже может быть vector(2560), а RAG_EMBEDDING_DIM
    ещё 1536 — CREATE INDEX тогда падает.
    """
    index_name = _INDEX_BY_TABLE.get(table)
    if not index_name:
        return False

    column_dim = await get_column_vector_dim(conn, table)
    effective_dim = int(column_dim or dim or 0)
    if effective_dim > HNSW_MAX_DIM:
        logger.warning(
            "%s: dim=%s > %s — HNSW не создаём (лимит pgvector), поиск без ANN-индекса",
            table,
            effective_dim,
            HNSW_MAX_DIM,
        )
        await conn.execute(f"DROP INDEX IF EXISTS {index_name}")
        return False
    await conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table} USING hnsw (embedding vector_cosine_ops)
        """
    )
    return True

async def migrate_vector_tables(conn, target_dim: int) -> Dict[str, Any]:
    """Привести все vector-таблицы к target_dim. Старые векторы очищаются."""
    if target_dim < 1:
        raise ValueError(f"Некорректная embedding_dim: {target_dim}")

    changed: List[str] = []
    unchanged: List[str] = []
    cleared_rows = 0
    hnsw_enabled = target_dim <= HNSW_MAX_DIM

    for table in VECTOR_TABLES:
        exists = await conn.fetchval(
            "SELECT to_regclass($1) IS NOT NULL",
            f"public.{table}",
        )
        if not exists:
            continue

        current = await get_column_vector_dim(conn, table)
        if current == target_dim:
            # Dim совпала, но индекс мог отсутствовать после прошлой неудачной миграции
            await drop_embedding_index(conn, table)
            await create_embedding_index(conn, table, target_dim)
            unchanged.append(table)
            continue

        count = int(await conn.fetchval(f"SELECT COUNT(*) FROM {table}") or 0)
        await drop_embedding_index(conn, table)

        # Пустая таблица: ALTER TYPE. С данными — TRUNCATE, иначе ALTER не сконвертирует.
        if count > 0:
            await conn.execute(f"TRUNCATE TABLE {table}")
            cleared_rows += count

        await conn.execute(
            f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({int(target_dim)})"
        )
        await create_embedding_index(conn, table, target_dim)
        changed.append(table)
        logger.warning(
            "Миграция %s: vector(%s) → vector(%s), очищено строк=%s, hnsw=%s",
            table,
            current,
            target_dim,
            count,
            hnsw_enabled,
        )

    return {
        "embedding_dim": target_dim,
        "changed_tables": changed,
        "unchanged_tables": unchanged,
        "cleared_rows": cleared_rows,
        "migrated": bool(changed),
        "hnsw_enabled": hnsw_enabled,
        "hnsw_max_dim": HNSW_MAX_DIM,
    }