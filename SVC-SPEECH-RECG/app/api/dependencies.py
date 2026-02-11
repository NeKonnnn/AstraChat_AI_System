from fastapi import Depends, HTTPException, status
from app.core.security import verify_api_key

async def require_api_key(api_key_verified: bool = Depends(verify_api_key)):
    """Зависимость для проверки API ключа."""
    return api_key_verified