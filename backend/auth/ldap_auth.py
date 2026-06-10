"""
LDAP аутентификация (Active Directory) через ldap3.
"""
from __future__ import annotations

import os
import ssl
import logging
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status

try:
    from ldap3 import Server, Connection, SIMPLE, SUBTREE, Tls
    from ldap3.core.exceptions import LDAPException, LDAPBindError
    from ldap3.utils.conv import escape_filter_chars
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False

logger = logging.getLogger(__name__)

# AD userAccountControl: ACCOUNTDISABLE
_AD_ACCOUNT_DISABLED = 0x0002


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _split_groups(raw: str) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _extract_group_cn(group_dn: str) -> str:
    """CN=Group Name,OU=... → Group Name (для ACL access_grants)."""
    raw = str(group_dn or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper.startswith("CN="):
        return raw[3:].split(",", 1)[0].strip()
    return raw


def _domain_from_base_dn(base_dn: str) -> str:
    parts = []
    for chunk in (base_dn or "").split(","):
        piece = chunk.strip()
        if piece.lower().startswith("dc="):
            parts.append(piece[3:])
    return ".".join(parts)


def _build_filter(filter_template: str, username: str) -> str:
    escaped = escape_filter_chars(username)
    # Поддержка форматов шаблона: {{username}} и {username}
    return (
        str(filter_template)
        .replace("{{username}}", escaped)
        .replace("{username}", escaped)
    )


def _get_ldap_settings() -> Dict[str, Any]:
    return {
        "enabled": _env_bool("LDAP_ENABLED", False),
        "url": os.getenv("LDAP_URL"),
        "base_dn": os.getenv("LDAP_USER_SEARCH_BASE"),
        "search_filter": os.getenv("LDAP_SEARCH_FILTER"),
        "ca_cert_path": os.getenv("LDAP_CA_CERT_PATH"),
        "bind_dn": os.getenv("LDAP_BIND_DN"),
        "bind_credentials": os.getenv("LDAP_BIND_CREDENTIALS"),
        "id_attr": os.getenv("LDAP_ID"),
        "email_attr": os.getenv("LDAP_EMAIL"),
        "full_name_attr": os.getenv("LDAP_FULL_NAME"),
        "username_attr": os.getenv("LDAP_USERNAME"),
        "login_uses_username": _env_bool("LDAP_LOGIN_USES_USERNAME", True),
        "admin_groups": _split_groups(os.getenv("LDAP_ADMIN_GROUPS", "")),
    }


def _build_server(ldap_url: str, timeout: int, ca_cert_path: Optional[str]):
    parsed = urlparse(ldap_url)
    scheme = parsed.scheme.lower() if parsed.scheme else "ldap"
    host = parsed.hostname or ldap_url
    port = parsed.port or (636 if scheme == "ldaps" else 389)
    use_ssl = scheme == "ldaps"

    tls = None
    if use_ssl:
        if ca_cert_path and os.path.exists(ca_cert_path):
            tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ca_cert_path)
        else:
            tls = Tls(validate=ssl.CERT_NONE)

    logger.info(
        "LDAP сервер инициализирован: host=%s port=%s use_ssl=%s ca_cert_configured=%s",
        host,
        port,
        use_ssl,
        bool(ca_cert_path),
    )
    return Server(
        host=host,
        port=port,
        use_ssl=use_ssl,
        connect_timeout=timeout,
        tls=tls,
        get_info=None,
    )


def _try_user_bind(server, username: str, password: str, settings: Dict[str, Any]) -> Optional[Connection]:
    candidates: List[str] = []
    if settings["login_uses_username"]:
        candidates.append(username)

    domain = _domain_from_base_dn(settings["base_dn"])
    if domain and "@" not in username:
        candidates.append(f"{username}@{domain}")

    seen = set()
    logger.info("LDAP bind: подготовлены кандидаты count=%s user=%s", len(candidates), username)
    for bind_user in candidates:
        if bind_user in seen:
            continue
        seen.add(bind_user)
        logger.info("LDAP bind: попытка user=%s bind_identity=%s", username, bind_user)
        try:
            conn = Connection(
                server,
                user=bind_user,
                password=password,
                authentication=SIMPLE,
                receive_timeout=10,
                auto_bind=True,
            )
            logger.info("LDAP bind: успех user=%s bind_identity=%s", username, bind_user)
            return conn
        except LDAPBindError as exc:
            logger.warning(
                "LDAP bind: отклонено user=%s bind_identity=%s reason=%s",
                username,
                bind_user,
                str(exc),
            )
            continue
        except LDAPException as exc:
            logger.warning(
                "LDAP bind: LDAP-исключение user=%s bind_identity=%s reason=%s",
                username,
                bind_user,
                str(exc),
            )
            continue
    logger.info("LDAP bind: все кандидаты исчерпаны user=%s", username)
    return None


def _service_bind_and_search(
    server,
    settings: Dict[str, Any],
    username: str,
    search_filter: str,
    attributes: List[str],
):
    conn = Connection(
        server,
        user=settings["bind_dn"],
        password=settings["bind_credentials"],
        authentication=SIMPLE,
        receive_timeout=10,
        auto_bind=True,
    )
    logger.info("LDAP service bind: успех bind_dn=%s", settings["bind_dn"])

    found = conn.search(
        search_base=settings["base_dn"],
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=attributes,
    )
    if not found or not conn.entries:
        logger.info("LDAP search: записи не найдены user=%s", username)
        conn.unbind()
        return None, None

    entry = conn.entries[0]
    attrs = entry.entry_attributes_as_dict
    entry_dn = str(entry.entry_dn)
    conn.unbind()
    logger.info(
        "LDAP search: успех user=%s attrs_present=%s",
        username,
        ",".join(sorted(attrs.keys())),
    )
    return attrs, entry_dn


def _verify_user_password_by_dn(server, username: str, user_dn: str, password: str) -> bool:
    logger.info("LDAP bind: проверка пароля пользователя через DN user=%s user_dn=%s", username, user_dn)
    try:
        conn = Connection(
            server,
            user=user_dn,
            password=password,
            authentication=SIMPLE,
            receive_timeout=10,
            auto_bind=True,
        )
        conn.unbind()
        logger.info("LDAP bind: пароль пользователя подтвержден user=%s", username)
        return True
    except LDAPBindError as exc:
        logger.warning("LDAP bind: неверный пароль пользователя user=%s reason=%s", username, str(exc))
        return False
    except LDAPException as exc:
        logger.warning("LDAP bind: ошибка при проверке пароля user=%s reason=%s", username, str(exc))
        return False


def _extract_first(attrs: Dict[str, Any], attr_name: str) -> Optional[str]:
    if not attr_name or attr_name not in attrs:
        return None
    value = attrs.get(attr_name)
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    if value is None:
        return None
    return str(value)


def _ldap_lookup_attributes(settings: Dict[str, Any]) -> List[str]:
    return list(
        {
            settings["id_attr"],
            settings["email_attr"],
            settings["full_name_attr"],
            settings["username_attr"],
            "mail",
            "displayName",
            "cn",
            "memberOf",
            "userPrincipalName",
            "sAMAccountName",
            "userAccountControl",
            "lockoutTime",
        }
    )


def _parse_int_attr(attrs: Dict[str, Any], attr_name: str) -> Optional[int]:
    raw = _extract_first(attrs, attr_name)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return None


def _is_account_disabled(attrs: Dict[str, Any]) -> bool:
    uac = _parse_int_attr(attrs, "userAccountControl")
    if uac is None:
        return False
    return bool(uac & _AD_ACCOUNT_DISABLED)


def _is_account_locked(attrs: Dict[str, Any]) -> bool:
    lockout = _parse_int_attr(attrs, "lockoutTime")
    return lockout is not None and lockout > 0


def _ldap_account_status_error(attrs: Dict[str, Any]) -> Optional[str]:
    if _is_account_disabled(attrs):
        return "Учётная запись отключена в LDAP"
    if _is_account_locked(attrs):
        return "Учётная запись заблокирована в LDAP"
    return None


def _service_bind_lookup_user(
    username: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Найти пользователя в LDAP через service bind (без пароля пользователя)."""
    settings = settings or _get_ldap_settings()
    if not settings.get("bind_dn") or not settings.get("bind_credentials"):
        return None

    required_keys = ("url", "base_dn", "search_filter")
    missing = [key for key in required_keys if not settings.get(key)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LDAP конфигурация неполная. Отсутствуют: {', '.join(missing)}",
        )

    server = _build_server(settings["url"], 10, settings["ca_cert_path"])
    search_filter = _build_filter(settings["search_filter"], username)
    attributes = _ldap_lookup_attributes(settings)
    attrs, _user_dn = _service_bind_and_search(
        server,
        settings,
        username,
        search_filter,
        attributes,
    )
    return attrs


def validate_ldap_user_account(username: str, user_id: Optional[str] = None) -> None:
    """Проверить, что учётная запись существует и активна в LDAP/AD.

    Raises:
        HTTPException 401 — учётная запись не найдена, отключена или заблокирована.
        HTTPException 503 — LDAP временно недоступен (сессию не завершаем).
    """
    if not is_ldap_enabled():
        return

    settings = _get_ldap_settings()
    if not settings.get("bind_dn") or not settings.get("bind_credentials"):
        logger.debug(
            "LDAP validate: пропуск, service bind не настроен user=%s user_id=%s",
            username,
            user_id,
        )
        return

    lookup_names: List[str] = []
    for name in (username, user_id):
        normalized = (name or "").strip()
        if normalized and normalized not in lookup_names:
            lookup_names.append(normalized)

    for lookup_name in lookup_names:
        try:
            attrs = _service_bind_lookup_user(lookup_name, settings)
        except HTTPException:
            raise
        except LDAPBindError as exc:
            logger.warning(
                "LDAP validate: service bind отклонён user=%s reason=%s",
                lookup_name,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LDAP сервер недоступен",
            )
        except LDAPException as exc:
            logger.warning(
                "LDAP validate: LDAP-исключение user=%s reason=%s",
                lookup_name,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LDAP сервер недоступен",
            )

        if not attrs:
            continue

        status_error = _ldap_account_status_error(attrs)
        if status_error:
            logger.info(
                "LDAP validate: отклонено user=%s lookup=%s reason=%s",
                username,
                lookup_name,
                status_error,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=status_error,
            )
        return

    logger.info(
        "LDAP validate: учётная запись не найдена user=%s user_id=%s",
        username,
        user_id,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Учётная запись не найдена в LDAP",
    )


def authenticate_ldap(username: str, password: str) -> Optional[Dict]:
    """Аутентификация пользователя через LDAP/AD."""
    settings = _get_ldap_settings()
    if not settings["enabled"]:
        logger.info("LDAP auth: пропуск, LDAP отключен user=%s", username)
        return None
    if not password:
        logger.info("LDAP auth: пустой пароль user=%s", username)
        return None

    if not LDAP_AVAILABLE:
        logger.error("LDAP auth: недоступно, модуль ldap3 не установлен user=%s", username)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP аутентификация недоступна: модуль ldap3 не установлен",
        )

    try:
        required_keys = (
            "url",
            "base_dn",
            "search_filter",
            "id_attr",
            "email_attr",
            "full_name_attr",
            "username_attr",
        )
        missing = [key for key in required_keys if not settings.get(key)]
        if missing:
            logger.error("LDAP config: неполная конфигурация missing=%s", ",".join(missing))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LDAP конфигурация неполная. Отсутствуют: {', '.join(missing)}",
            )

        if bool(settings.get("bind_dn")) != bool(settings.get("bind_credentials")):
            logger.error("LDAP config: bind_dn и bind_credentials должны быть заданы вместе")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LDAP конфигурация неполная. Укажите одновременно LDAP_BIND_DN и LDAP_BIND_CREDENTIALS",
            )

        logger.info("LDAP auth: старт user=%s base_dn=%s", username, settings["base_dn"])
        server = _build_server(settings["url"], 10, settings["ca_cert_path"])

        search_filter = _build_filter(settings["search_filter"], username)
        attributes = _ldap_lookup_attributes(settings)
        logger.info(
            "LDAP search: старт user=%s base_dn=%s attrs_count=%s",
            username,
            settings["base_dn"],
            len(attributes),
        )
        logger.debug("LDAP search: фильтр user=%s filter=%s", username, search_filter)

        if settings.get("bind_dn") and settings.get("bind_credentials"):
            logger.info("LDAP auth: используется service bind для поиска user=%s", username)
            attrs, user_dn = _service_bind_and_search(server, settings, username, search_filter, attributes)
            if not attrs or not user_dn:
                return None
            if not _verify_user_password_by_dn(server, username, user_dn, password):
                logger.info("LDAP auth: неуспешно на этапе проверки пароля user=%s", username)
                return None
        else:
            conn = _try_user_bind(server, username, password, settings)
            if conn is None:
                logger.info("LDAP auth: неуспешно на этапе bind user=%s", username)
                return None
            found = conn.search(
                search_base=settings["base_dn"],
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
            )
            if not found or not conn.entries:
                logger.info("LDAP search: записи не найдены user=%s", username)
                conn.unbind()
                return None
            entry = conn.entries[0]
            attrs = entry.entry_attributes_as_dict
            conn.unbind()
            logger.info(
                "LDAP search: успех user=%s attrs_present=%s",
                username,
                ",".join(sorted(attrs.keys())),
            )

        status_error = _ldap_account_status_error(attrs)
        if status_error:
            logger.info("LDAP auth: отклонено user=%s reason=%s", username, status_error)
            return None

        ldap_username = _extract_first(attrs, settings["id_attr"]) or username
        full_name = (
            _extract_first(attrs, settings["full_name_attr"])
            or _extract_first(attrs, "displayName")
            or _extract_first(attrs, "cn")
        )
        email = (
            _extract_first(attrs, settings["email_attr"])
            or _extract_first(attrs, "mail")
            or _extract_first(attrs, "userPrincipalName")
        )

        group_values = attrs.get("memberOf") or []
        groups = [str(group) for group in group_values]
        group_names = [_extract_group_cn(g) for g in groups if _extract_group_cn(g)]
        admin_groups = [g.lower() for g in settings["admin_groups"]]
        is_admin = any(
            any(
                f"cn={admin_group}," in group.lower() or group.lower() == admin_group
                for admin_group in admin_groups
            )
            for group in groups
        )
        logger.info(
            "LDAP auth: пользователь определен user=%s ldap_username=%s groups_count=%s is_admin=%s",
            username,
            ldap_username,
            len(groups),
            is_admin,
        )

        return {
            "user_id": ldap_username,
            "username": ldap_username,
            "email": email,
            "full_name": full_name,
            "is_active": True,
            "is_admin": is_admin,
            "groups": group_names,
            "ldap_groups": groups,
        }
    except LDAPBindError as exc:
        logger.warning("LDAP auth: ошибка bind user=%s reason=%s", username, str(exc))
        return None
    except LDAPException as exc:
        logger.exception("LDAP auth: LDAP-исключение user=%s", username)
        if os.getenv("DEBUG", "false").lower() == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LDAP ошибка: {str(exc)}",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LDAP сервер недоступен или вернул ошибку",
        )
    except Exception as exc:
        logger.exception("LDAP auth: непредвиденная ошибка user=%s", username)
        if os.getenv("DEBUG", "false").lower() == "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка LDAP аутентификации: {str(exc)}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка аутентификации",
        )


def is_ldap_enabled() -> bool:
    """Проверить, включена ли LDAP аутентификация."""
    settings = _get_ldap_settings()
    return settings["enabled"] and LDAP_AVAILABLE