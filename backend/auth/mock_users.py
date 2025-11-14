"""
Mock пользователи для разработки без LDAP
"""

MOCK_USERS = {
    "admin": {
        "username": "admin",
        "password": "admin123",
        "email": "admin@example.com",
        "full_name": "Администратор",
        "is_active": True,
        "is_admin": True,
    },
    "user": {
        "username": "user",
        "password": "user123",
        "email": "user@example.com",
        "full_name": "Тестовый Пользователь",
        "is_active": True,
        "is_admin": False,
    },
    "test": {
        "username": "test",
        "password": "test123",
        "email": "test@example.com",
        "full_name": "Test User",
        "is_active": True,
        "is_admin": False,
    },
}


def authenticate_mock(username: str, password: str):
    """Mock аутентификация"""
    user = MOCK_USERS.get(username)
    if not user or user["password"] != password:
        return None
    
    return {
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "is_active": user["is_active"],
        "is_admin": user["is_admin"],
    }



