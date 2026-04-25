"""
API routes для аутентификации
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from .jwt_handler import (
    create_session_id,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_user,
    register_user_session,
    revoke_user_session,
)
from .mock_users import authenticate_mock
from .ldap_auth import authenticate_ldap, is_ldap_enabled

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    username: str
    email: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_admin: bool


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """
    Логин пользователя через LDAP или Mock-режим

    Если LDAP включен (LDAP_ENABLED=true):
    - Использует Active Directory аутентификацию

    Если LDAP отключен (LDAP_ENABLED=false):
    - Использует тестовых пользователей:
      * admin / admin123
      * user / user123
      * test / test123
    """
    user = None

    # Сначала пробуем LDAP (если включен)
    if is_ldap_enabled():
        user = authenticate_ldap(credentials.username, credentials.password)

    # Если LDAP отключен или аутентификация не прошла, пробуем Mock
    if not user:
        user = authenticate_mock(credentials.username, credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль"
        )

    uid = user.get("user_id", credentials.username)
    session_id = create_session_id()
    register_user_session(uid, session_id)
    logger.info("auth login: выдача токенов user_id=%s", uid)

    access_token = create_access_token(
        username=credentials.username,
        user_id=uid,
        session_id=session_id,
    )
    refresh_token = create_refresh_token(
        username=credentials.username,
        user_id=uid,
        session_id=session_id,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(payload: RefreshRequest):
    """Обновить access токен по refresh токену."""
    token_data = decode_refresh_token(payload.refresh_token)
    username = token_data["username"]
    user_id = token_data["user_id"]
    session_id = token_data.get("session_id")
    logger.info("auth refresh: user_id=%s", user_id)

    new_access_token = create_access_token(username=username, user_id=user_id, session_id=session_id)
    new_refresh_token = create_refresh_token(username=username, user_id=user_id, session_id=session_id)

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
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Выход из системы"""
    revoke_user_session(current_user["user_id"], current_user.get("session_id"))
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


@router.get("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Проверить валидность токена"""
    return {
        "valid": True,
        "username": current_user["username"]
    }