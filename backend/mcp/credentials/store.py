"""Generic per-user MCP credentials storage (B-12)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from backend.settings.logging import get_logger

log = get_logger(__name__)

COLLECTION_NAME = "user_mcp_credentials"


def _get_fernet() -> Optional[Fernet]:
    key = (os.getenv("MCP_CREDENTIALS_ENCRYPTION_KEY") or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        log.error("Invalid MCP_CREDENTIALS_ENCRYPTION_KEY: %s", exc)
        return None


def _get_collection():
    try:
        from backend.database.init_db import get_mongodb_connection

        conn = get_mongodb_connection()
        if conn is None:
            return None
        return conn.get_collection(COLLECTION_NAME)
    except Exception as exc:
        log.debug("MongoDB unavailable for MCP credentials: %s", exc)
        return None


async def ensure_indexes() -> None:
    collection = _get_collection()
    if collection is None:
        return
    try:
        await collection.create_index(
            [("user_id", 1), ("server_id", 1)],
            unique=True,
            name="user_server_unique",
        )
    except Exception as exc:
        log.warning("MCP credentials index creation failed: %s", exc)


def _encrypt_payload(payload: Dict[str, Any]) -> bytes:
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError(
            "MCP_CREDENTIALS_ENCRYPTION_KEY is not configured; cannot store credentials"
        )
    return fernet.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _decrypt_payload(blob: bytes) -> Dict[str, Any]:
    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("MCP_CREDENTIALS_ENCRYPTION_KEY is not configured")
    try:
        raw = fernet.decrypt(blob)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise RuntimeError("Failed to decrypt MCP credentials") from exc


async def get_credentials(user_id: str, server_id: str) -> Optional[Dict[str, Any]]:
    collection = _get_collection()
    if collection is None:
        return None
    doc = await collection.find_one({"user_id": user_id, "server_id": server_id})
    if not doc or not doc.get("encrypted_payload"):
        return None
    return _decrypt_payload(doc["encrypted_payload"])


async def save_credentials(user_id: str, server_id: str, payload: Dict[str, Any]) -> bool:
    collection = _get_collection()
    if collection is None:
        return False
    encrypted = _encrypt_payload(payload)
    now = datetime.utcnow()
    await collection.update_one(
        {"user_id": user_id, "server_id": server_id},
        {
            "$set": {
                "encrypted_payload": encrypted,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return True


async def delete_credentials(user_id: str, server_id: str) -> bool:
    collection = _get_collection()
    if collection is None:
        return False
    result = await collection.delete_one({"user_id": user_id, "server_id": server_id})
    return result.deleted_count > 0


async def credentials_metadata(user_id: str, server_id: str) -> Dict[str, Any]:
    """Метаданные без секретов — для GET API."""
    try:
        payload = await get_credentials(user_id, server_id)
    except RuntimeError:
        return {"configured": False, "fields": {}, "storage_available": False}
    if not payload:
        return {"configured": False, "fields": {}, "storage_available": _get_fernet() is not None}
    fields = {k: bool(v) for k, v in payload.items() if k and v}
    return {
        "configured": bool(fields),
        "fields": fields,
        "storage_available": True,
    }
