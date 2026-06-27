"""
API routes для аутентификации
"""
import os
import uuid
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from typing import Optional
from .jwt_handler import (
    create_session_id,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    get_server_instance_id,
    jwt_token_byte_length,
    register_user_session,
    revoke_user_session,
)
from .ldap_auth import authenticate_ldap, is_ldap_enabled, validate_ldap_user_account
from .mock_users import authenticate_mock, is_mock_user
from .login_lockout import (
    assert_login_not_locked,
    build_cef_sec003_extra,
    build_login_failed_detail,
    get_lockout_policy,
    record_failed_login,
    record_successful_login,
)
from .session_timeout import get_session_policy
from backend.settings.cef_logger.cef_logger import (
    domain_from_ldap_base_dn,
    ldap_audit_cs_fields,
    ldap_reason_suffix,
    log_cef_event,
)
from backend.settings.logging import get_logger

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionPolicyPayload(BaseModel):
    timeout_seconds: int
    enabled: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
    session_policy: Optional[SessionPolicyPayload] = None
    server_instance_id: str


class ServerInstanceResponse(BaseModel):
    instance_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    username: str
    email: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_admin: bool


def _ensure_ldap_user_active(current_user: dict) -> None:
    """Проверить учётную запись в LDAP; при 401 отозвать текущую сессию."""
    username = current_user.get("username") or ""
    user_id = current_user.get("user_id") or ""
    if is_mock_user(username) or is_mock_user(user_id):
        return
    try:
        validate_ldap_user_account(username, user_id)
    except HTTPException as he:
        if he.status_code == status.HTTP_401_UNAUTHORIZED:
            revoke_user_session(
                current_user.get("user_id") or current_user.get("username") or "",
                current_user.get("session_id"),
            )
        raise


@router.get("/login-lockout-policy")
async def login_lockout_policy():
    """Публичные параметры блокировки входа (для страницы авторизации)."""
    return get_lockout_policy()


@router.get("/session-policy")
async def session_policy():
    """Параметры абсолютного таймаута сессии с момента входа (для frontend)."""
    return get_session_policy()


@router.get("/server-instance", response_model=ServerInstanceResponse)
async def server_instance():
    """Идентификатор текущего процесса backend (меняется при рестарте)."""
    return {"instance_id": get_server_instance_id()}


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, request: Request):
    """
    Логин через LDAP (Active Directory) или локальные mock-учётки (admin/user/test).
    Сначала LDAP (если включён), затем mock — для локальной разработки без AD.
    """
    username = credentials.username
    logger.info("auth login start user=%s", username)
    try:
        assert_login_not_locked(username)
    except HTTPException as he:
        if he.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            log_cef_event(
                "SEC003",
                request=request,
                current_user={"username": username},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                extra=build_cef_sec003_extra(username, account_locked=True),
            )
        raise
    ldap_on = is_ldap_enabled()
    logger.info("auth login ldap_enabled=%s", ldap_on)

    user = None
    if ldap_on:
        user = authenticate_ldap(username, credentials.password)
        logger.info("auth login after LDAP user_resolved=%s", bool(user))
    if not user:
        user = authenticate_mock(username, credentials.password)
        if user:
            logger.info("auth login mock user=%s", username)

    if not user:
        record_failed_login(username)
        logger.info("auth login rejecting invalid credentials user=%s", username)
        log_cef_event(
            "SEC003",
            request=request,
            current_user={"username": username},
            status_code=status.HTTP_401_UNAUTHORIZED,
            extra=build_cef_sec003_extra(username, account_locked=False),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_login_failed_detail(username),
        )

    record_successful_login(username)

    # Создаем JWT токен с user_id
    uid = user.get("user_id", username)
    session_id = create_session_id()
    session_info = register_user_session(uid, session_id, username=username, request=request)
    logger.info("auth login issuing token user_id=%s", uid)
    try:
        access_token = create_access_token(
            username=username, user_id=uid, session_id=session_id, user_profile=user
        )
        refresh_token = create_refresh_token(
            username=username, user_id=uid, session_id=session_id, user_profile=user
        )
    except Exception:
        logger.exception("auth login JWT token create failed user=%s", username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка выдачи токена",
        )

    logger.info(
        "JWT: login user_id=%s access=%s байт refresh=%s байт",
        uid,
        jwt_token_byte_length(access_token),
        jwt_token_byte_length(refresh_token),
    )
    logger.info("auth login success user_id=%s", uid)
    _ldap_cs = ldap_audit_cs_fields(user)
    log_cef_event(
        "SEC001",
        request=request,
        current_user=user,
        status_code=status.HTTP_200_OK,
        extra=_ldap_cs,
    )
    if session_info.get("first_seen"):
        _dntdom = domain_from_ldap_base_dn(os.getenv("LDAP_USER_SEARCH_BASE", "")) or (
            user.get("email", "").split("@", 1)[-1] if user.get("email") else None
        )
        log_cef_event(
            "USR001",
            request=request,
            current_user=user,
            status_code=status.HTTP_200_OK,
            extra={
                "duser": user.get("username"),
                "dntdom": _dntdom,
                **_ldap_cs,
            },
        )
    policy = get_session_policy()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
        "session_policy": SessionPolicyPayload(
            timeout_seconds=policy["timeout_seconds"],
            enabled=policy["enabled"],
        ),
        "server_instance_id": get_server_instance_id(),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: Request, payload: RefreshRequest):
    """Обновить access токен по refresh токену."""
    try:
        token_data = decode_refresh_token(payload.refresh_token, request=request)
    except HTTPException as he:
        log_cef_event(
            "INT006",
            request=request,
            current_user={"username": "anonymous"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            extra={
                "methodName": "POST /api/auth/refresh",
                "serviceName": "AstraChat-Auth",
                "requestUuid": uuid.uuid4().hex,
                "codeStatus": str(he.status_code),
                "textStatus": str(he.detail or "Invalid refresh token")[:512],
            },
        )
        raise
    username = token_data["username"]
    user_id = token_data["user_id"]
    session_id = token_data.get("session_id")
    logger.info("auth refresh start user_id=%s", user_id)

    _ensure_ldap_user_active(
        {
            "username": username,
            "user_id": user_id,
            "session_id": session_id,
        }
    )

    new_access_token = create_access_token(
        username=username, user_id=user_id, session_id=session_id, user_profile=token_data
    )
    new_refresh_token = create_refresh_token(
        username=username, user_id=user_id, session_id=session_id, user_profile=token_data
    )
    logger.info(
        "JWT: refresh user_id=%s access=%s байт refresh=%s байт",
        user_id,
        jwt_token_byte_length(new_access_token),
        jwt_token_byte_length(new_refresh_token),
    )
    logger.info("auth refresh success user_id=%s", user_id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "username": username,
            "email": None,
            "full_name": None,
            "is_active": True,
            "is_admin": False,
        },
        "server_instance_id": get_server_instance_id(),
    }

@router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """Выход из системы"""
    revoke_user_session(current_user["user_id"], current_user.get("session_id"))
    log_cef_event("SEC002", request=request, current_user=current_user, status_code=status.HTTP_200_OK)
    return {
        "message": "Успешный выход из системы",
        "username": current_user["username"]
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_info(
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Обновить информацию пользователя"""
    if email:
        current_user["email"] = email
    if full_name:
        current_user["full_name"] = full_name
    return current_user


@router.delete("/me")
async def delete_user_account(request: Request, current_user: dict = Depends(get_current_user)):
    """Удаление учетной записи пользователя (аудит-событие, без физического удаления профиля в LDAP)."""
    revoke_user_session(current_user["user_id"], current_user.get("session_id"))
    log_cef_event(
        "USR002",
        request=request,
        current_user=current_user,
        status_code=status.HTTP_200_OK,
        extra={
            "duser": current_user.get("username"),
            "dntdom": domain_from_ldap_base_dn(os.getenv("LDAP_USER_SEARCH_BASE", ""))
            or (current_user.get("email", "").split("@", 1)[-1] if current_user.get("email") else None),
            "dmail": current_user.get("email") or "-",
        },
    )
    return {"message": "Учетная запись помечена как удаленная", "username": current_user["username"]}

@router.get("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Проверить валидность токена и статус учётной записи в LDAP."""
    _ensure_ldap_user_active(current_user)
    return {
        "valid": True,
        "username": current_user["username"],
        "server_instance_id": get_server_instance_id(),
    }