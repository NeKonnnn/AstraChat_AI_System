"""
LDAP аутентификация (Active Directory)
"""

import os
from typing import Optional, Dict
from fastapi import HTTPException, status

# Опциональный импорт python-ldap (может быть недоступен на Windows)
try:
    import ldap
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    ldap = None

# Настройки LDAP из переменных окружения
LDAP_ENABLED = os.getenv("LDAP_ENABLED", "false").lower() == "true"
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://localhost:389")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=example,dc=com")
LDAP_USER_DN_TEMPLATE = os.getenv(
    "LDAP_USER_DN_TEMPLATE", 
    "cn={username},ou=Users,dc=example,dc=com"
)
LDAP_SEARCH_FILTER = os.getenv("LDAP_SEARCH_FILTER", "(sAMAccountName={username})")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", None)
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", None)
LDAP_TIMEOUT = int(os.getenv("LDAP_TIMEOUT", "10"))


def authenticate_ldap(username: str, password: str) -> Optional[Dict]:
    """
    Аутентификация через LDAP/Active Directory
    
    Возвращает данные пользователя или None при ошибке
    """
    if not LDAP_ENABLED:
        return None
    
    if not LDAP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP аутентификация недоступна: модуль python-ldap не установлен"
        )
    
    try:
        # Инициализация LDAP соединения
        conn = ldap.initialize(LDAP_SERVER)
        conn.set_option(ldap.OPT_NETWORK_TIMEOUT, LDAP_TIMEOUT)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        
        # Формирование DN пользователя для Active Directory
        # Поддержка разных форматов:
        # 1. cn={username},ou=Users,dc=example,dc=com
        # 2. {username}@domain.com (userPrincipalName)
        # 3. DOMAIN\{username} (sAMAccountName)
        
        user_dn = LDAP_USER_DN_TEMPLATE.format(username=username)
        
        # Попытка привязки (bind) с учетными данными пользователя
        try:
            conn.simple_bind_s(user_dn, password)
        except ldap.INVALID_CREDENTIALS:
            # Если не получилось с CN, пробуем userPrincipalName
            if "@" not in user_dn and "." in LDAP_BASE_DN:
                domain = ".".join([dc.split("=")[1] for dc in LDAP_BASE_DN.split(",") if dc.startswith("dc=")])
                user_dn = f"{username}@{domain}"
                try:
                    conn.simple_bind_s(user_dn, password)
                except ldap.INVALID_CREDENTIALS:
                    conn.unbind_s()
                    return None
            else:
                conn.unbind_s()
                return None
        
        # Если bind успешен, получаем атрибуты пользователя
        search_filter = LDAP_SEARCH_FILTER.format(username=username)
        
        # Используем bind DN если настроен, иначе используем текущее соединение
        if LDAP_BIND_DN and LDAP_BIND_PASSWORD:
            conn.unbind_s()
            conn = ldap.initialize(LDAP_SERVER)
            conn.set_option(ldap.OPT_NETWORK_TIMEOUT, LDAP_TIMEOUT)
            conn.set_option(ldap.OPT_REFERRALS, 0)
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
            conn.simple_bind_s(LDAP_BIND_DN, LDAP_BIND_PASSWORD)
        
        # Атрибуты Active Directory
        attributes = [
            "sAMAccountName",       # Имя пользователя
            "cn",                   # Полное имя
            "displayName",          # Отображаемое имя
            "mail",                 # Email
            "userPrincipalName",    # UPN
            "givenName",            # Имя
            "sn",                   # Фамилия
            "memberOf",             # Группы
        ]
        
        result = conn.search_s(
            LDAP_BASE_DN,
            ldap.SCOPE_SUBTREE,
            search_filter,
            attributes
        )
        
        conn.unbind_s()
        
        if result:
            dn, attrs = result[0]
            
            # Извлекаем данные пользователя
            def get_attr(attr_name):
                """Безопасно извлечь атрибут из LDAP"""
                if attr_name in attrs and attrs[attr_name]:
                    value = attrs[attr_name][0]
                    if isinstance(value, bytes):
                        return value.decode("utf-8")
                    return value
                return None
            
            # Определяем полное имя
            full_name = (
                get_attr("displayName") or 
                get_attr("cn") or 
                f"{get_attr('givenName') or ''} {get_attr('sn') or ''}".strip() or
                None
            )
            
            # Определяем email
            email = get_attr("mail") or get_attr("userPrincipalName")
            
            # Проверяем, является ли пользователь администратором
            # По умолчанию проверяем членство в группе Domain Admins
            is_admin = False
            member_of = attrs.get("memberOf", [])
            for group in member_of:
                group_str = group.decode("utf-8") if isinstance(group, bytes) else group
                if "Domain Admins" in group_str or "Administrators" in group_str:
                    is_admin = True
                    break
            
            user_data = {
                "user_id": username,  # Используем username как user_id для LDAP
                "username": username,
                "email": email,
                "full_name": full_name,
                "is_active": True,
                "is_admin": is_admin,
            }
            
            return user_data
        
        return None
        
    except ldap.INVALID_CREDENTIALS:
        return None
    except ldap.SERVER_DOWN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP сервер недоступен"
        )
    except ldap.TIMEOUT:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Превышено время ожидания LDAP сервера"
        )
    except Exception as e:
        # В разработке возвращаем детальную ошибку
        if os.getenv("DEBUG", "false").lower() == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка LDAP аутентификации: {str(e)}"
            )
        # В продакшене - общая ошибка
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка аутентификации"
        )


def is_ldap_enabled() -> bool:
    """Проверить, включена ли LDAP аутентификация"""
    return LDAP_ENABLED and LDAP_AVAILABLE