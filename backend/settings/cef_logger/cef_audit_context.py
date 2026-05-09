"""
Контекст для CEF: пользователь и диалог при вызовах LLM/памяти без явной передачи request.
Используется contextvars (корректно в async; при sync+ThreadPoolExecutor может быть пусто).
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class _Tokens:
    """Пары (ContextVar, Token) для сброса."""

    pairs: Tuple[Tuple[contextvars.ContextVar, contextvars.Token], ...]


_request: contextvars.ContextVar = contextvars.ContextVar("cef_audit_request", default=None)
_user: contextvars.ContextVar = contextvars.ContextVar("cef_audit_user", default=None)
_conversation_id: contextvars.ContextVar = contextvars.ContextVar("cef_audit_conversation_id", default=None)


def cef_audit_set(
    *,
    request: Any = None,
    user: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
) -> _Tokens:
    """Сохранить контекст; вернуть токены для cef_audit_reset."""
    pairs: List[Tuple[contextvars.ContextVar, contextvars.Token]] = []
    if request is not None:
        pairs.append((_request, _request.set(request)))
    if user is not None:
        pairs.append((_user, _user.set(user)))
    if conversation_id is not None:
        pairs.append((_conversation_id, _conversation_id.set(conversation_id)))
    return _Tokens(tuple(pairs))


def cef_audit_reset(tokens: _Tokens) -> None:
    for var, tok in reversed(tokens.pairs):
        var.reset(tok)


def cef_audit_peek() -> tuple[Optional[Any], Optional[Dict[str, Any]], Optional[str]]:
    return _request.get(), _user.get(), _conversation_id.get()
