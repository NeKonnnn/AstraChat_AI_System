"""
API routes для аутентификации
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from .jwt_handler import create_access_token, get_current_user
from .mock_users import authenticate_mock
from .ldap_auth import authenticate_ldap, is_ldap_enabled

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


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
    
    # Создаем JWT токен
    token = create_access_token(credentials.username)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Выход из системы"""
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

