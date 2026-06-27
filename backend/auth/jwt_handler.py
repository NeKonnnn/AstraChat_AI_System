"""
JWT токены для аутентификации
"""

import os
import uuid
from datetime import datetime, timedelta
from threading import RLock
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.settings.cef_logger.cef_logger import log_cef_event
from backend.settings.logging import get_logger

security = HTTPBearer()
logger = get_logger(__name__)

# Настройки JWT
JWT_ACCESS_SECRET = os.getenv("JWT_SECRET")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET")
JWT_ALGORITHM = "HS256"


def _required_env_int(name: str) -> int:
    """Обязательная целочисленная переменная окружения (TTL в секундах)."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        raise RuntimeError(f"Missing required JWT env var: {name}")
    value = int(str(raw).strip())
    if value <= 0:
        raise RuntimeError(f"JWT env var {name} must be a positive integer (seconds), got {raw!r}")
    return value


# TTL JWT (секунды) и лимит одновременных сессий на пользователя.
JWT_ACCESS_TOKEN_EXPIRE_SECONDS = _required_env_int("JWT_ACCESS_TOKEN_EXPIRE_SECONDS")
JWT_REFRESH_TOKEN_EXPIRE_SECONDS = _required_env_int("JWT_REFRESH_TOKEN_EXPIRE_SECONDS")
AUTH_MAX_ACTIVE_SESSION = _required_env_int("AUTH_MAX_ACTIVE_SESSION")


def get_max_active_sessions() -> int:
    return AUTH_MAX_ACTIVE_SESSION


def _log_jwt_configuration() -> None:
    access_from_env = bool(JWT_ACCESS_SECRET)
    refresh_from_env = bool(JWT_REFRESH_SECRET)
    logger.info(
        "JWT config: access_secret_source=%s refresh_secret_source=%s algorithm=%s "
        "access_ttl_sec=%s refresh_ttl_sec=%s max_active_sessions=%s",
        "env" if access_from_env else "missing",
        "env" if refresh_from_env else "missing",
        JWT_ALGORITHM,
        JWT_ACCESS_TOKEN_EXPIRE_SECONDS,
        JWT_REFRESH_TOKEN_EXPIRE_SECONDS,
        AUTH_MAX_ACTIVE_SESSION,
    )
    if not access_from_env or not refresh_from_env:
        missing_vars = []
        if not access_from_env:
            missing_vars.append("JWT_SECRET")
        if not refresh_from_env:
            missing_vars.append("JWT_REFRESH_SECRET")
        logger.error("JWT config: отсутствуют обязательные переменные: %s", ", ".join(missing_vars))
        raise RuntimeError(f"Missing required JWT env vars: {', '.join(missing_vars)}")


_log_jwt_configuration()

_active_sessions_lock = RLock()
# user_id -> список sid (FIFO: старые в начале, новые в конце)
_active_sessions_by_user: dict[str, List[str]] = {}
# Меняется при каждом старте процесса — frontend сверяет с сохранённым значением после login.
SERVER_INSTANCE_ID = str(uuid.uuid4())


def jwt_token_byte_length(token: Any) -> int:
    """Размер JWT в байтах (без логирования самого токена)."""
    if isinstance(token, bytes):
        return len(token)
    if isinstance(token, str):
        return len(token.encode("utf-8"))
    return len(str(token).encode("utf-8"))


def _parse_bearer_token(request: Request) -> Optional[str]:
    """Bearer-токен из заголовка Authorization (без проверки)."""
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _session_is_active(user_id: str, session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    with _active_sessions_lock:
        sessions = _active_sessions_by_user.get(user_id)
        return bool(sessions and session_id in sessions)


def try_user_from_request(request: Request) -> Optional[dict]:
    """Тихое извлечение пользователя из access JWT для CEF (без SEC007 и HTTPException)."""
    token = _parse_bearer_token(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_ACCESS_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("token_type") != "access":
            return None
        username = payload.get("sub")
        if not username:
            return None
        user_id = payload.get("user_id") or username
        session_id = payload.get("sid")
        if not _session_is_active(user_id, session_id):
            return None
        return {
            "username": username,
            "user_id": user_id,
            "session_id": session_id,
            "email": None,
            "full_name": None,
            "is_active": True,
            "is_admin": False,
        }
    except (JWTError, ExpiredSignatureError):
        return None


def _peek_jwt_subject(token: str, token_type: str) -> tuple[Optional[str], Optional[str]]:
    """Извлечь sub/user_id из JWT для CEF (без проверки exp)."""
    secret = JWT_REFRESH_SECRET if token_type == "refresh" else JWT_ACCESS_SECRET
    if not secret:
        return None, None
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        username = payload.get("sub")
        user_id = payload.get("user_id") or username
        return username, user_id
    except Exception:
        return None, None


def _log_jwt_validation_failure(
    *,
    reason: str,
    token_type: str = "access",
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    request: Any = None,
) -> None:
    """CEF SEC007: неуспешная проверка JWT (п. 31.14)."""
    effective_username = username or "anonymous"
    effective_user_id = user_id or username or "anonymous"
    log_cef_event(
        "SEC007",
        request=request,
        current_user={"username": effective_username, "user_id": effective_user_id},
        status_code=status.HTTP_401_UNAUTHORIZED,
        extra={
            "reason": reason,
            "cs1": token_type,
            "cs1Label": "TokenType",
        },
    )


def _jwt_auth_error(
    detail: str,
    *,
    reason: str,
    token_type: str = "access",
    token: Optional[str] = None,
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    request: Any = None,
) -> HTTPException:
    if username is None and user_id is None and token:
        username, user_id = _peek_jwt_subject(token, token_type)
    _log_jwt_validation_failure(
        reason=reason,
        token_type=token_type,
        username=username,
        user_id=user_id,
        request=request,
    )
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_server_instance_id() -> str:
    return SERVER_INSTANCE_ID


def create_session_id() -> str:
    """Создать новый идентификатор сессии."""
    return str(uuid.uuid4())


def register_user_session(
    user_id: str,
    session_id: str,
    username: Optional[str] = None,
    request: Any = None,
) -> Dict[str, Any]:
    """Зарегистрировать session_id среди активных сессий пользователя (до AUTH_MAX_ACTIVE_SESSION).

    При превышении лимита отзываются самые старые sid (SEC006).
    Returns:
        dict with keys:
        - invalidated_count: int
        - first_seen: bool
    """
    invalidated_count = 0
    first_seen = False
    with _active_sessions_lock:
        sessions = _active_sessions_by_user.get(user_id)
        if sessions is None:
            first_seen = True
            sessions = []
            _active_sessions_by_user[user_id] = sessions

        if session_id in sessions:
            sessions.remove(session_id)
        sessions.append(session_id)

        while len(sessions) > AUTH_MAX_ACTIVE_SESSION:
            sessions.pop(0)
            invalidated_count += 1

        if not sessions:
            _active_sessions_by_user.pop(user_id, None)

    if invalidated_count:
        log_cef_event(
            "SEC006",
            request=request,
            current_user={"username": username or user_id, "user_id": user_id},
            status_code=200,
            extra={"cn1": invalidated_count, "cn1Label": "InvalidatedSessionCount"},
        )
    return {"invalidated_count": invalidated_count, "first_seen": first_seen}


def revoke_user_session(user_id: str, session_id: Optional[str] = None) -> None:
    """Отозвать сессию пользователя.

    Если session_id передан — удаляется только он.
    Если не передан — удаляются все активные сессии пользователя.
    """
    with _active_sessions_lock:
        sessions = _active_sessions_by_user.get(user_id)
        if not sessions:
            return
        if session_id:
            if session_id not in sessions:
                return
            sessions.remove(session_id)
            if not sessions:
                _active_sessions_by_user.pop(user_id, None)
            return
        _active_sessions_by_user.pop(user_id, None)


def _assert_active_session(
    user_id: str,
    session_id: Optional[str],
    *,
    request: Any = None,
    token_type: str = "access",
    username: Optional[str] = None,
) -> None:
    """Проверить, что session_id — текущая активная сессия пользователя."""
    if not session_id:
        logger.warning(
            "JWT session validate: missing sid user_id=%s",
            user_id,
        )
        raise _jwt_auth_error(
            "Сессия завершена",
            reason="missing session id (sid)",
            token_type=token_type,
            username=username or user_id,
            user_id=user_id,
            request=request,
        )
    with _active_sessions_lock:
        sessions = _active_sessions_by_user.get(user_id)
        if sessions and session_id in sessions:
            return
        if not sessions:
            logger.warning(
                "JWT session validate: сессия отсутствует (logout или рестарт pod) user_id=%s sid=%s",
                user_id,
                session_id,
            )
            raise _jwt_auth_error(
                "Сессия завершена: сервер перезапущен",
                reason="session not found in memory (logout or pod restart)",
                token_type=token_type,
                username=username or user_id,
                user_id=user_id,
                request=request,
            )
        logger.warning(
            "JWT session validate: session revoked user_id=%s sid=%s active_count=%s max=%s",
            user_id,
            session_id,
            len(sessions),
            AUTH_MAX_ACTIVE_SESSION,
        )
        detail = (
            "Сессия завершена: выполнен вход с другого устройства/окна"
            if AUTH_MAX_ACTIVE_SESSION <= 1
            else f"Сессия завершена: превышен лимит активных сессий ({AUTH_MAX_ACTIVE_SESSION})"
        )
        raise _jwt_auth_error(
            detail,
            reason="session superseded (login elsewhere or max active sessions exceeded)",
            token_type=token_type,
            username=username or user_id,
            user_id=user_id,
            request=request,
        )


def _apply_user_profile_claims(to_encode: dict, user_profile: Optional[dict]) -> None:
    """LDAP profile → compact JWT claims (groups/is_admin/email)."""
    if not user_profile:
        return
    if user_profile.get("is_admin"):
        to_encode["adm"] = True
    groups = user_profile.get("groups") or []
    if isinstance(groups, list) and groups:
        to_encode["grp"] = [str(g) for g in groups[:64] if g]
    email = user_profile.get("email")
    if email:
        to_encode["email"] = str(email)
    full_name = user_profile.get("full_name")
    if full_name:
        to_encode["name"] = str(full_name)
    ldap_groups = user_profile.get("ldap_groups") or []
    if isinstance(ldap_groups, list) and ldap_groups:
        to_encode["ldap_grp"] = [str(g) for g in ldap_groups[:32] if g]


def _user_dict_from_payload(payload: dict) -> dict:
    groups = payload.get("grp") or []
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    ldap_groups = payload.get("ldap_grp") or []
    if not isinstance(ldap_groups, list):
        ldap_groups = [ldap_groups] if ldap_groups else []
    return {
        "username": payload.get("sub"),
        "user_id": payload.get("user_id") or payload.get("sub"),
        "session_id": payload.get("sid"),
        "email": payload.get("email"),
        "full_name": payload.get("name"),
        "is_active": True,
        "is_admin": bool(payload.get("adm")),
        "groups": groups,
        "ldap_groups": ldap_groups,
    }


def create_access_token(
    username: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    *,
    user_profile: Optional[dict] = None,
) -> str:
    """Создать JWT токен"""
    expire = datetime.utcnow() + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRE_SECONDS)
    sid = session_id or create_session_id()
    to_encode = {
        "sub": username,
        "user_id": user_id or username,
        "sid": sid,
        "token_type": "access",
        "exp": expire,
    }
    _apply_user_profile_claims(to_encode, user_profile)
    token = jwt.encode(to_encode, JWT_ACCESS_SECRET, algorithm=JWT_ALGORITHM)
    logger.info(
        "JWT: выдан access-токен user_id=%s размер=%s байт",
        user_id or username,
        jwt_token_byte_length(token),
    )
    return token


def create_refresh_token(
    username: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    *,
    user_profile: Optional[dict] = None,
) -> str:
    """Создать refresh JWT токен."""
    expire = datetime.utcnow() + timedelta(seconds=JWT_REFRESH_TOKEN_EXPIRE_SECONDS)
    sid = session_id or create_session_id()
    to_encode = {
        "sub": username,
        "user_id": user_id or username,
        "sid": sid,
        "token_type": "refresh",
        "exp": expire,
    }
    _apply_user_profile_claims(to_encode, user_profile)
    token = jwt.encode(to_encode, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)
    logger.info(
        "JWT: выдан refresh-токен user_id=%s размер=%s байт",
        user_id or username,
        jwt_token_byte_length(token),
    )
    return token


def decode_token_signature_only(token: str, *, request: Any = None) -> dict:
    """Декодировать JWT и вернуть данные пользователя БЕЗ проверки активной сессии.

    Используется при WebSocket-подключении: JWT может быть валиден,
    но сессия потеряна в памяти (рестарт пода). Позволить соединиться,
    проверку сессии делаем при обработке каждого сообщения.
    """
    try:
        payload = jwt.decode(token, JWT_ACCESS_SECRET, algorithms=[JWT_ALGORITHM])
        token_type: str = payload.get("token_type")
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        session_id: str = payload.get("sid")

        if token_type != "access":
            logger.warning("JWT ws-connect validate: неверный token_type=%s", token_type)
            raise _jwt_auth_error(
                "Неверный тип токена",
                reason=f"invalid token_type={token_type!r}",
                token_type="access",
                token=token,
                username=username,
                user_id=user_id,
                request=request,
            )
        if username is None:
            logger.warning("JWT ws-connect validate: отсутствует sub claim")
            raise _jwt_auth_error(
                "Неверный токен",
                reason="missing sub claim",
                token_type="access",
                token=token,
                request=request,
            )
        effective_user_id = user_id or username
        logger.info(
            "JWT ws-connect validate (signature-only): успех username=%s user_id=%s sid=%s",
            username, effective_user_id, session_id,
        )
        return {
            **_user_dict_from_payload(payload),
        }
    except HTTPException:
        raise
    except ExpiredSignatureError:
        logger.warning("JWT ws-connect validate: токен просрочен (exp)")
        raise _jwt_auth_error(
            "Не удалось валидировать токен",
            reason="token expired (exp)",
            token_type="access",
            token=token,
            request=request,
        )
    except JWTError as exc:
        logger.warning("JWT ws-connect validate: ошибка JWT (%s)", type(exc).__name__)
        raise _jwt_auth_error(
            "Не удалось валидировать токен",
            reason=f"JWT error ({type(exc).__name__})",
            token_type="access",
            token=token,
            request=request,
        )


def decode_token(token: str, *, request: Any = None) -> dict:
    """Декодировать JWT токен и вернуть данные пользователя"""
    try:
        payload = jwt.decode(token, JWT_ACCESS_SECRET, algorithms=[JWT_ALGORITHM])
        token_type: str = payload.get("token_type")
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        session_id: str = payload.get("sid")

        if token_type != "access":
            logger.warning("JWT access validate: неверный token_type=%s", token_type)
            raise _jwt_auth_error(
                "Неверный тип токена",
                reason=f"invalid token_type={token_type!r}",
                token_type="access",
                token=token,
                username=username,
                user_id=user_id,
                request=request,
            )

        if username is None:
            logger.warning("JWT access validate: отсутствует sub claim")
            raise _jwt_auth_error(
                "Неверный токен",
                reason="missing sub claim",
                token_type="access",
                token=token,
                request=request,
            )
        effective_user_id = user_id or username
        _assert_active_session(
            effective_user_id,
            session_id,
            request=request,
            token_type="access",
            username=username,
        )
        logger.info("JWT access validate: успех username=%s user_id=%s", username, user_id or username)
        return _user_dict_from_payload(payload)
    except HTTPException:
        raise
    except ExpiredSignatureError:
        logger.warning("JWT access validate: токен просрочен (exp)")
        raise _jwt_auth_error(
            "Не удалось валидировать токен",
            reason="token expired (exp)",
            token_type="access",
            token=token,
            request=request,
        )
    except JWTError as exc:
        logger.warning("JWT access validate: ошибка JWT (%s)", type(exc).__name__)
        raise _jwt_auth_error(
            "Не удалось валидировать токен",
            reason=f"JWT error ({type(exc).__name__})",
            token_type="access",
            token=token,
            request=request,
        )

        
def decode_refresh_token(token: str, *, request: Any = None) -> dict:
    """Декодировать refresh JWT токен и вернуть данные пользователя."""
    try:
        payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
        token_type: str = payload.get("token_type")
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        session_id: str = payload.get("sid")

        if token_type != "refresh":
            logger.warning("JWT refresh validate: неверный token_type=%s", token_type)
            raise _jwt_auth_error(
                "Неверный тип токена",
                reason=f"invalid token_type={token_type!r}",
                token_type="refresh",
                token=token,
                username=username,
                user_id=user_id,
                request=request,
            )

        if username is None:
            logger.warning("JWT refresh validate: отсутствует sub claim")
            raise _jwt_auth_error(
                "Неверный refresh токен",
                reason="missing sub claim",
                token_type="refresh",
                token=token,
                request=request,
            )
        effective_user_id = user_id or username
        _assert_active_session(
            effective_user_id,
            session_id,
            request=request,
            token_type="refresh",
            username=username,
        )
        logger.info("JWT refresh validate: успех username=%s user_id=%s", username, user_id or username)
        return _user_dict_from_payload(payload)
    except HTTPException:
        raise
    except ExpiredSignatureError:
        logger.warning("JWT refresh validate: токен просрочен (exp)")
        raise _jwt_auth_error(
            "Не удалось валидировать refresh токен",
            reason="token expired (exp)",
            token_type="refresh",
            token=token,
            request=request,
        )
    except JWTError as exc:
        logger.warning("JWT refresh validate: ошибка JWT (%s)", type(exc).__name__)
        raise _jwt_auth_error(
            "Не удалось валидировать refresh токен",
            reason=f"JWT error ({type(exc).__name__})",
            token_type="refresh",
            token=token,
            request=request,
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Получить текущего пользователя из токена (обязательная авторизация)"""
    token = credentials.credentials
    logger.info("JWT auth: проверка access токена для обязательной авторизации")
    user_data = decode_token(token, request=request)

    return {
        "username": user_data["username"],
        "user_id": user_data["user_id"],
        "session_id": user_data.get("session_id"),
        "email": user_data.get("email"),
        "full_name": user_data.get("full_name"),
        "is_active": True,
        "is_admin": bool(user_data.get("is_admin")),
        "groups": list(user_data.get("groups") or []),
        "ldap_groups": list(user_data.get("ldap_groups") or []),
    }


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[dict]:
    """Получить текущего пользователя из токена (опциональная авторизация)"""
    if not credentials:
        logger.debug("JWT auth: опциональная авторизация без токена")
        return None

    try:
        token = credentials.credentials
        logger.info("JWT auth: проверка access токена для опциональной авторизации")
        user_data = decode_token(token, request=request)

        return {
            "username": user_data["username"],
            "user_id": user_data["user_id"],
            "session_id": user_data.get("session_id"),
            "email": user_data.get("email"),
            "full_name": user_data.get("full_name"),
            "is_active": True,
            "is_admin": bool(user_data.get("is_admin")),
            "groups": list(user_data.get("groups") or []),
            "ldap_groups": list(user_data.get("ldap_groups") or []),
        }
    except HTTPException:
        # Если токен невалидный, возвращаем None вместо ошибки
        logger.info("JWT auth: опциональная авторизация отклонена из-за невалидного токена")
        return None