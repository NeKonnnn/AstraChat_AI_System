"""
Репозиторий персональных LLM-настроек и контекстных промптов пользователя.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend.database.postgresql.connection import PostgreSQLConnection
from backend.settings.logging import get_logger

logger = get_logger(__name__)


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            logger.exception("user_llm_settings: не удалось распарсить JSONB")
    return {}


class UserSettingsRepository:
    """CRUD для таблицы user_llm_settings."""

    def __init__(self, db_connection: PostgreSQLConnection):
        self.db_connection = db_connection

    async def create_tables(self) -> None:
        try:
            async with await self.db_connection.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_llm_settings (
                        user_id VARCHAR(100) PRIMARY KEY,
                        model_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
                        context_prompts JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_llm_settings_updated ON user_llm_settings(updated_at DESC)"
                )
            logger.info("Таблица user_llm_settings готова")
        except Exception:
            logger.exception("Ошибка при создании таблицы user_llm_settings")
            raise

    async def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        uid = (user_id or "").strip().lower()
        if not uid:
            return None
        try:
            async with await self.db_connection.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT user_id, model_settings, context_prompts, created_at, updated_at
                    FROM user_llm_settings
                    WHERE user_id = $1
                    """,
                    uid,
                )
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "model_settings": _as_dict(row["model_settings"]),
                "context_prompts": _as_dict(row["context_prompts"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        except Exception:
            logger.exception("user_llm_settings.get failed user_id=%s", uid)
            return None

    async def upsert(
        self,
        user_id: str,
        *,
        model_settings: Optional[Dict[str, Any]] = None,
        context_prompts: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        uid = (user_id or "").strip().lower()
        if not uid:
            return None
        ms = model_settings if isinstance(model_settings, dict) else {}
        cp = context_prompts if isinstance(context_prompts, dict) else {}
        try:
            async with await self.db_connection.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO user_llm_settings (user_id, model_settings, context_prompts, updated_at)
                    VALUES ($1, $2::jsonb, $3::jsonb, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        model_settings = CASE
                            WHEN $4::boolean THEN EXCLUDED.model_settings
                            ELSE user_llm_settings.model_settings
                        END,
                        context_prompts = CASE
                            WHEN $5::boolean THEN EXCLUDED.context_prompts
                            ELSE user_llm_settings.context_prompts
                        END,
                        updated_at = NOW()
                    RETURNING user_id, model_settings, context_prompts, created_at, updated_at
                    """,
                    uid,
                    json.dumps(ms, ensure_ascii=False),
                    json.dumps(cp, ensure_ascii=False),
                    model_settings is not None,
                    context_prompts is not None,
                )
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "model_settings": _as_dict(row["model_settings"]),
                "context_prompts": _as_dict(row["context_prompts"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        except Exception:
            logger.exception("user_llm_settings.upsert failed user_id=%s", uid)
            return None

    async def delete(self, user_id: str) -> bool:
        uid = (user_id or "").strip().lower()
        if not uid:
            return False
        try:
            async with await self.db_connection.acquire() as conn:
                result = await conn.execute("DELETE FROM user_llm_settings WHERE user_id = $1", uid)
            return result.endswith("1")
        except Exception:
            logger.exception("user_llm_settings.delete failed user_id=%s", uid)
            return False
