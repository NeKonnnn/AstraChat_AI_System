"""
Абсолютный таймаут сессии с момента входа (AUTH_SESSION_TIMEOUT_SECONDS из ConfigMap).
Активность пользователя срок не продлевает.
"""
from __future__ import annotations


def _get_session_timeout_config():
    from backend.settings.config import get_settings

    return get_settings().auth.session_timeout


def get_session_policy() -> dict:
    """Публичные параметры таймаута сессии (для UI и /api/auth/session-policy)."""
    cfg = _get_session_timeout_config()
    timeout_seconds = max(0, int(cfg.timeout_seconds))
    return {
        "timeout_seconds": timeout_seconds,
        "enabled": timeout_seconds > 0,
    }
