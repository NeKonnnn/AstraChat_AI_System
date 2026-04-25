"""
JWT токены для аутентификации
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from threading import RLock
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()
logger = logging.getLogger(__name__)

# Настройки JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "dev-refresh-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# --- Единственная активная сессия на пользователя ---
_active_sessions_lock = RLock()
_active_sessions_by_user: dict[str, str] = {}


def create_session_id() -> str:
    """Создать новый идентификатор сессии."""
    return str(uuid.uuid4())


def register_user_session(user_id: str, session_id: str) -> None:
    """Сделать session_id единственной активной сессией пользователя."""
    with _active_sessions_lock:
        _active_sessions_by_user[user_id] = session_id


def revoke_user_session(user_id: str, session_id: Optional[str] = None) -> None:
    """Отозвать активную сессию пользователя.

    Если session_id передан, отзыв выполняется только при совпадении
    с текущей активной сессией.
    """
    with _active_sessions_lock:
        current_session = _active_sessions_by_user.get(user_id)
        if current_session is None:
            return
        if session_id and current_session != session_id:
            return
        _active_sessions_by_user.pop(user_id, None)


def _is_active_session(user_id: str, session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    with _active_sessions_lock:
        return _active_sessions_by_user.get(user_id) == session_id


def create_access_token(username: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
    """Создать JWT токен"""
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    sid = session_id or create_session_id()
    to_encode = {
        "sub": username,
        "user_id": user_id or username,  # Используем username как user_id, если не передан
        "sid": sid,
        "token_type": "access",
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(username: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
    """Создать refresh JWT токен."""
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    sid = session_id or create_session_id()
    to_encode = {
        "sub": username,
        "user_id": user_id or username,
        "sid": sid,
        "token_type": "refresh",
        "exp": expire,
    }
    return jwt.encode(to_encode, JWT_REFRESH_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Декодировать JWT токен и вернуть данные пользователя"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_type: str = payload.get("token_type")
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        session_id: str = payload.get("sid")

        if token_type and token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный тип токена"
            )

        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )

        effective_user_id = user_id or username
        if session_id and not _is_active_session(effective_user_id, session_id):
            logger.warning(
                "JWT access validate: session revoked username=%s user_id=%s sid=%s",
                username, effective_user_id, session_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Сессия завершена: выполнен вход с другого устройства/окна"
            )

        return {
            "username": username,
            "user_id": effective_user_id,  # Fallback на username если user_id нет
            "session_id": session_id,
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось валидировать токен"
        )


def decode_refresh_token(token: str) -> dict:
    """Декодировать refresh JWT токен и вернуть данные пользователя."""
    try:
        payload = jwt.decode(token, JWT_REFRESH_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_type: str = payload.get("token_type")
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        session_id: str = payload.get("sid")

        if token_type and token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный тип токена"
            )

        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный refresh токен"
            )

        effective_user_id = user_id or username
        if session_id and not _is_active_session(effective_user_id, session_id):
            logger.warning(
                "JWT refresh validate: session revoked username=%s user_id=%s sid=%s",
                username, effective_user_id, session_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Сессия завершена: выполнен вход с другого устройства/окна"
            )

        return {
            "username": username,
            "user_id": effective_user_id,
            "session_id": session_id,
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось валидировать refresh токен"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Получить текущего пользователя из токена (обязательная авторизация)"""
    token = credentials.credentials
    user_data = decode_token(token)
    
    # Простая реализация - возвращаем данные из токена
    # В продакшене здесь бы был запрос к БД
    return {
        "username": user_data["username"],
        "user_id": user_data["user_id"],
        "session_id": user_data.get("session_id"),
        "email": None,
        "full_name": None,
        "is_active": True,
        "is_admin": False
    }


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[dict]:
    """Получить текущего пользователя из токена (опциональная авторизация)"""
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        user_data = decode_token(token)
        
        return {
            "username": user_data["username"],
            "user_id": user_data["user_id"],
            "session_id": user_data.get("session_id"),
            "email": None,
            "full_name": None,
            "is_active": True,
            "is_admin": False
        }
    except HTTPException:
        # Если токен невалидный, возвращаем None вместо ошибки
        return None