"""
JWT токены для аутентификации
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# Настройки JWT
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def create_access_token(username: str, user_id: Optional[str] = None) -> str:
    """Создать JWT токен"""
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": username,
        "user_id": user_id or username,  # Используем username как user_id, если не передан
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Декодировать JWT токен и вернуть данные пользователя"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный токен"
            )
        
        return {
            "username": username,
            "user_id": user_id or username  # Fallback на username если user_id нет
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось валидировать токен"
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
            "email": None,
            "full_name": None,
            "is_active": True,
            "is_admin": False
        }
    except HTTPException:
        # Если токен невалидный, возвращаем None вместо ошибки
        return None



