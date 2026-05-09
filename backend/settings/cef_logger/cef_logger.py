import logging
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


logger = logging.getLogger("cef")


@dataclass(frozen=True)
class CEFEventSpec:
    event_id: str
    name: str
    severity: int
    cat: str
    act: str
    outcome: str
    msg_template: str
    device_direction: int = 0


EVENTS: Dict[str, CEFEventSpec] = {
    "SYS001": CEFEventSpec(
        "SYS001",
        "Application Started",
        3,
        "/System/Startup",
        "start",
        "success",
        "Приложение AstraChat запущено, API доступен по адресу https://{dhost} [{cat}]",
    ),
    "SYS002": CEFEventSpec(
        "SYS002",
        "Application Stopped",
        3,
        "/System/Shutdown",
        "stop",
        "success",
        "Приложение AstraChat остановлено (завершение работы экземпляра) [{cat}]",
    ),
    "OBJ001": CEFEventSpec(
        "OBJ001",
        "API Call Success",
        1,
        "/Object/API/Request",
        "request",
        "success",
        "Обработка запроса '{methodName}' сервиса {serviceName} выполнена успешно ({requestUuid})",
    ),
    "OBJ002": CEFEventSpec(
        "OBJ002",
        "API Call Failed",
        4,
        "/Object/API/Request",
        "request",
        "failure",
        "Ошибка '{codeStatus} {textStatus}' обработки запроса '{methodName}' сервиса {serviceName} ({requestUuid})",
    ),
    "FS001": CEFEventSpec(
        "FS001",
        "MinIO File Read",
        1,
        "/Storage/MinIO/Read",
        "read",
        "success",
        "Чтение файла '{file}' из бакета '{bucket}'",
    ),
    "FS002": CEFEventSpec(
        "FS002",
        "MinIO File Read Failed",
        4,
        "/Storage/MinIO/Read",
        "read",
        "failure",
        "Ошибка чтения файла '{file}' из бакета '{bucket}'",
    ),
    "FS003": CEFEventSpec(
        "FS003",
        "MinIO File Write",
        1,
        "/Storage/MinIO/Write",
        "write",
        "success",
        "Сохранение файла '{file}' в бакет '{bucket}'",
    ),
    "FS004": CEFEventSpec(
        "FS004",
        "MinIO File Write Failed",
        4,
        "/Storage/MinIO/Write",
        "write",
        "failure",
        "Ошибка сохранения файла '{file}' в бакет '{bucket}'",
    ),
    "SEC001": CEFEventSpec(
        "SEC001",
        "User Login Success",
        3,
        "/Authentication/Login",
        "login",
        "success",
        "Пользователь {suser} аутентифицирован с адреса {src} через LDAP-сервер {cs1}, ТУЗ {cs2}. "
        "Ролевая модель: {cs4} ({cs3}) [{cat}]",
    ),
    "SEC002": CEFEventSpec(
        "SEC002",
        "User Logout",
        3,
        "/Authentication/Logout",
        "logout",
        "success",
        "Пользователь {suser} завершил сеанс [{cat}]",
    ),
    "SEC003": CEFEventSpec(
        "SEC003",
        "User Login Failed",
        5,
        "/Authentication/Login",
        "login",
        "failure",
        "Неудачная попытка аутентификации УЗ {suser} с адреса {src}. Причина: {reason} [{cat}]",
    ),
    "SEC004": CEFEventSpec(
        "SEC004",
        "Agent Access Changed",
        5,
        "/Authorization/Agent/AccessChange",
        "modify",
        "success",
        "Пользователь {suser} изменил права доступа к агенту {cs1} (ID: {cs2}): пользователю {duser} назначена роль «{cs3}» [{cat}]",
    ),
    "SEC005": CEFEventSpec(
        "SEC005",
        "Admin Settings Changed",
        5,
        "/Authorization/AdminSettings/Modify",
        "modify",
        "success",
        "Администратор {suser} изменил глобальные разрешения раздела «{cs1}» для роли {cs2}: {cs3} [{cat}]",
    ),
    "SEC006": CEFEventSpec(
        "SEC006",
        "Session Invalidated",
        5,
        "/Authentication/SessionInvalidated",
        "invalidate",
        "success",
        "Принудительная инвалидация {cn1} предыдущих сессий пользователя {suser}. "
        "Причина: вход из другого браузера/устройства (single-session enforcement) [{cat}]",
    ),
    "USR001": CEFEventSpec(
        "USR001",
        "User Account Created",
        4,
        "/UserManagement/Create",
        "create",
        "success",
        "УЗ пользователя {duser} создана при первом входе через LDAP-сервер {cs1}. Ролевая модель: {cs4} ({cs3}) [{cat}]",
    ),
    "USR002": CEFEventSpec(
        "USR002",
        "User Account Deleted",
        7,
        "/UserManagement/Delete",
        "delete",
        "success",
        "УЗ пользователя {duser} ({dmail}) удалена пользователем {suser} [{cat}]",
    ),
    "AGT001": CEFEventSpec(
        "AGT001",
        "Agent Created",
        3,
        "/Object/Agent/Create",
        "create",
        "success",
        "Агент {cs1} (ID: {cs2}) создан пользователем {suser} [{cat}]",
    ),
    "AGT002": CEFEventSpec(
        "AGT002",
        "Agent Config Changed",
        4,
        "/Object/Agent/Modify",
        "modify",
        "success",
        "Конфигурация агента {cs1} (ID: {cs2}) изменена пользователем {suser} [{cat}]",
    ),
    "AGT003": CEFEventSpec(
        "AGT003",
        "Agent Duplicated",
        3,
        "/Object/Agent/Copy",
        "copy",
        "success",
        "Агент {cs1} скопирован в {agt_copy_target} пользователем {suser} [{cat}]",
    ),
    "AGT004": CEFEventSpec(
        "AGT004",
        "Agent Version Rollback",
        5,
        "/Object/Agent/Rollback",
        "rollback",
        "success",
        "Агент {cs1} (ID: {cs2}) откачен к версии {cn1} пользователем {suser} [{cat}]",
    ),
    "AGT005": CEFEventSpec(
        "AGT005",
        "Agent Deleted",
        5,
        "/Object/Agent/Delete",
        "delete",
        "success",
        "Агент {cs1} (ID: {cs2}) удалён пользователем {suser} [{cat}]",
    ),
    "CNV001": CEFEventSpec(
        "CNV001",
        "Conversation Renamed",
        1,
        "/Object/Conversation/Rename",
        "rename",
        "success",
        "Диалог {cs2} переименован пользователем {suser} [{cat}]",
    ),
    "CNV002": CEFEventSpec(
        "CNV002",
        "Conversation Archived",
        1,
        "/Object/Conversation/Archive",
        "archive",
        "success",
        "Диалог {cs2} архивирован пользователем {suser} [{cat}]",
    ),
    "CNV003": CEFEventSpec(
        "CNV003",
        "Conversation Duplicated",
        1,
        "/Object/Conversation/Copy",
        "copy",
        "success",
        "Диалог {cs2} скопирован пользователем {suser} [{cat}]",
    ),
    "CNV004": CEFEventSpec(
        "CNV004",
        "Conversation Deleted",
        3,
        "/Object/Conversation/Delete",
        "delete",
        "success",
        "Диалог {cs2} удалён пользователем {suser} [{cat}]",
    ),
    "CNV005": CEFEventSpec(
        "CNV005",
        "All Conversations Deleted",
        7,
        "/Object/Conversation/Purge",
        "purge",
        "success",
        "Все диалоги пользователя {suser} удалены [{cat}]",
    ),
    "FIL001": CEFEventSpec(
        "FIL001",
        "File Uploaded",
        3,
        "/Object/File/Upload",
        "upload",
        "success",
        "Файл {fname} ({fsize} байт) загружен пользователем {suser} [{cat}]",
    ),
    "FIL002": CEFEventSpec(
        "FIL002",
        "File Deleted",
        4,
        "/Object/File/Delete",
        "delete",
        "success",
        "Файл {fname} ({fsize} байт) удалён пользователем {suser} [{cat}]",
    ),
    "INT001": CEFEventSpec(
        "INT001",
        "MCP Tool Invoked",
        3,
        "/Integration/MCP/Invoke",
        "execute",
        "success",
        "Пользователь {suser} вызвал MCP-сервер {cs3}, инструмент {cs1}, диалог {cs2}{cef_tail} [{cat}]",
        1,
    ),
    "INT002": CEFEventSpec(
        "INT002",
        "MCP Tool Completed",
        3,
        "/Integration/MCP/Complete",
        "complete",
        "success",
        "MCP-сервер {cs3}, инструмент {cs1} завершил работу. Длительность: {cn1} мс. Статус: {outcome}{cef_tail} [{cat}]",
        1,
    ),
    "INT003": CEFEventSpec(
        "INT003",
        "LLM Model Called",
        3,
        "/Integration/LLM/Request",
        "request",
        "success",
        "Пользователь {suser} инициировал запрос к модели {cs1} с помощью провайдера {cs3} [{cat}]",
        1,
    ),
    "INT004": CEFEventSpec(
        "INT004",
        "Agent REST API Call",
        3,
        "/Integration/Agent/Request",
        "request",
        "success",
        "Пользователь {suser} обратился к агенту {cs1} (ID: {cs2}) с адреса {src} [{cat}]",
    ),
}


# Порядок полей расширения как в разделе 7 CEF.md (примеры полных сообщений)
_EXTENSION_KEY_ORDER: List[str] = [
    "externalId",
    "deviceProcessName",
    "cat",
    "shost",
    "src",
    "sntdom",
    "spt",
    "dhost",
    "dst",
    "dpt",
    "duser",
    "dntdom",
    "app",
    "act",
    "outcome",
    "suser",
    "suid",
    "start",
    "end",
    "rt",
    "msg",
    "deviceDirection",
    "cs1",
    "cs1Label",
    "cs2",
    "cs2Label",
    "cs3",
    "cs3Label",
    "cs4",
    "cs4Label",
    "cn1",
    "cn1Label",
    "fname",
    "fsize",
    "request",
    "reason",
    "methodName",
    "serviceName",
    "requestUuid",
    "codeStatus",
    "textStatus",
    "file",
    "bucket",
]


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "-"


def _esc(val: Any) -> str:
    text = str(val if val is not None else "-")
    return text.replace("\\", "\\\\").replace("=", r"\=").replace("\n", r"\n")


def _outcome_from_status(status_code: Optional[int]) -> str:
    if status_code is None:
        return "success"
    if 200 <= status_code < 300:
        return "success"
    if 400 <= status_code < 500:
        return "failure"
    if status_code >= 500:
        return "error"
    return "success"


def domain_from_ldap_base_dn(base_dn: str) -> str:
    parts = []
    for chunk in (base_dn or "").split(","):
        piece = chunk.strip()
        if piece.lower().startswith("dc="):
            parts.append(piece[3:])
    return ".".join(parts)


def ldap_audit_cs_fields(user: Optional[dict]) -> Dict[str, Any]:
    """cs1–cs4 для SEC001/USR001 по CEF.md (LDAP-сервер, bind ТУЗ, группа AD, роль)."""
    if not user:
        return {}
    try:
        from urllib.parse import urlparse

        from backend.auth.ldap_auth import _get_ldap_settings

        settings = _get_ldap_settings()
        url = settings.get("url") or ""
        host = "-"
        if url:
            p = urlparse(url)
            host = p.hostname or p.netloc or "-"
        bind_dn = settings.get("bind_dn") or "-"
        admin_groups = settings.get("admin_groups") or []
        matched = admin_groups[0] if user.get("is_admin") and admin_groups else "-"
        role = "ADMIN" if user.get("is_admin") else "USER"
        return {
            "cs1": host,
            "cs1Label": "LDAPServer",
            "cs2": bind_dn,
            "cs2Label": "LDAPBindAccount",
            "cs3": matched,
            "cs3Label": "MatchedADGroup",
            "cs4": role,
            "cs4Label": "RoleModel",
        }
    except Exception:
        return {
            "cs1": "-",
            "cs1Label": "LDAPServer",
            "cs2": "-",
            "cs2Label": "LDAPBindAccount",
            "cs3": "-",
            "cs3Label": "MatchedADGroup",
            "cs4": "USER",
            "cs4Label": "RoleModel",
        }


def ldap_reason_suffix() -> str:
    """Суффикс к причине отказа SEC003, как в примере CEF.md."""
    try:
        from urllib.parse import urlparse

        from backend.auth.ldap_auth import _get_ldap_settings

        settings = _get_ldap_settings()
        url = settings.get("url") or ""
        host = "-"
        if url:
            p = urlparse(url)
            host = p.hostname or p.netloc or "-"
        bind_dn = settings.get("bind_dn") or "-"
        return f" (сервер {host}, ТУЗ {bind_dn})"
    except Exception:
        return ""


def request_context(request: Any, current_user: Optional[dict] = None) -> Dict[str, Any]:
    base_dn = os.getenv("LDAP_USER_SEARCH_BASE", "")
    sntdom = domain_from_ldap_base_dn(base_dn) or (base_dn or "-")
    if request is None:
        src = "127.0.0.1"
        shost = "localhost"
        spt = 0
        app = "HTTPS"
    else:
        src = (request.headers.get("x-real-ip") or request.client.host or "127.0.0.1").split(",")[0].strip()
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            src = fwd.split(",")[0].strip()
        shost = src
        spt = int(getattr(request.client, "port", 0) or 0)
        proto = request.headers.get("x-forwarded-proto") or getattr(request.url, "scheme", "http")
        app = "HTTPS" if str(proto).lower().startswith("https") else "HTTP"
    return {
        "src": src,
        "shost": shost,
        "spt": spt,
        "app": app,
        "suser": (current_user or {}).get("username", "anonymous"),
        "sntdom": sntdom,
    }


def cef_llm_int003_extra(
    *,
    base_url: str,
    provider_id: str,
    model: str,
    request_uuid: str,
) -> Dict[str, Any]:
    """Поля ``extra`` для INT003 (запрос к LLM по OpenAI-compatible ``/v1/chat/completions``)."""
    root = (base_url or "").rstrip("/")
    extra: Dict[str, Any] = {
        "cs1": model,
        "cs1Label": "LLMModel",
        "cs3": provider_id,
        "cs3Label": "LLMProvider",
        "request": f"{root}/v1/chat/completions",
        "duser": os.getenv("CEF_LLM_DUSER", "API-KEY"),
        "requestUuid": request_uuid,
    }
    try:
        pu = urlparse(base_url)
        if pu.hostname:
            extra["dhost"] = pu.hostname
        if pu.port:
            extra["dpt"] = int(pu.port)
        elif (pu.scheme or "").lower() == "https":
            extra["dpt"] = 443
    except Exception:
        pass
    dnt = os.getenv("CEF_LLM_DNTDOM")
    if dnt:
        extra["dntdom"] = dnt
    return extra


def log_cef_int003_llm_request(
    *,
    base_url: str,
    provider_id: str,
    model: str,
    request_uuid: str,
) -> None:
    """CEF INT003: исходящий вызов LLM (до HTTP-запроса)."""
    log_cef_event(
        "INT003",
        current_user=None,
        status_code=200,
        extra=cef_llm_int003_extra(
            base_url=base_url,
            provider_id=provider_id,
            model=model,
            request_uuid=request_uuid,
        ),
    )


def log_cef_obj002_llm_api_failure(
    *,
    request_uuid: str,
    code_status: Any,
    text_status: str,
    service_name: str,
    method_name: str = "POST /v1/chat/completions",
    status_code: Optional[int] = None,
) -> None:
    """CEF OBJ002: сбой вызова LLM API (HTTP, формат ответа, исключение)."""
    from backend.settings.cef_logger.cef_audit_context import cef_audit_peek

    req, user, _ = cef_audit_peek()
    log_cef_event(
        "OBJ002",
        request=req,
        current_user=user,
        status_code=status_code,
        extra={
            "methodName": method_name,
            "serviceName": service_name,
            "requestUuid": request_uuid,
            "codeStatus": str(code_status),
            "textStatus": (text_status or "")[:512],
        },
    )


def _extension_ordered_items(extension: Dict[str, Any]) -> List[Tuple[str, Any]]:
    seen: set[str] = set()
    out: List[Tuple[str, Any]] = []
    for key in _EXTENSION_KEY_ORDER:
        if key not in extension:
            continue
        val = extension[key]
        if val is None:
            continue
        out.append((key, val))
        seen.add(key)
    for key in sorted(extension.keys()):
        if key in seen or key.startswith("_"):
            continue
        val = extension[key]
        if val is None:
            continue
        out.append((key, val))
    return out


def log_cef_event(
    event_id: str,
    *,
    request: Any = None,
    current_user: Optional[dict] = None,
    status_code: Optional[int] = None,
    outcome: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    spec = EVENTS.get(event_id)
    if not spec:
        logger.warning("CEF event id '%s' is not configured", event_id)
        return

    _cef_ac: Optional[str] = None
    try:
        from backend.settings.cef_logger.cef_audit_context import cef_audit_peek

        _ar, _au, _cef_ac = cef_audit_peek()
        if request is None and _ar is not None:
            request = _ar
        if current_user is None and _au is not None:
            current_user = _au
    except Exception:
        pass

    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    dhost_fqdn = os.getenv("DOMAIN_SERVER", socket.getfqdn())

    if event_id in ("SYS001", "SYS002"):
        ctx = {
            "src": "127.0.0.1",
            "shost": socket.getfqdn() or socket.gethostname() or "localhost",
            "spt": 0,
            "app": "HTTPS",
            "suser": "SYSTEM",
            "sntdom": domain_from_ldap_base_dn(os.getenv("LDAP_USER_SEARCH_BASE", "")) or "-",
        }
        current_user_effective = {"username": "SYSTEM", "user_id": None}
    else:
        ctx = request_context(request, current_user)
        current_user_effective = current_user

    extra = dict(extra) if extra else {}
    if event_id == "INT003" and _cef_ac and extra.get("cs2") in (None, "", "-"):
        extra["cs2"] = _cef_ac
        extra.setdefault("cs2Label", "ConversationId")
    cef_tail = extra.pop("cef_tail", "")
    if cef_tail is None:
        cef_tail = ""

    extension: Dict[str, Any] = {
        "externalId": uuid.uuid4().hex,
        "deviceProcessName": os.getenv("CEF_DEVICE_PROCESS", "astrachat"),
        "cat": spec.cat,
        "shost": ctx["shost"],
        "src": ctx["src"],
        "sntdom": ctx["sntdom"],
        "spt": ctx["spt"],
        "dhost": dhost_fqdn,
        "dpt": int(os.getenv("CEF_DPT", "443")),
        "app": ctx["app"],
        "act": spec.act,
        "outcome": outcome or _outcome_from_status(status_code) or spec.outcome,
        "suser": ctx["suser"],
        "start": now_ms,
        "end": now_ms,
        "rt": datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "deviceDirection": spec.device_direction,
    }

    uid = (current_user_effective or {}).get("user_id")
    if uid and event_id != "SYS001":
        extension["suid"] = str(uid)

    if spec.device_direction == 1:
        if extra.get("dst"):
            extension["dst"] = extra.get("dst")
        if extra.get("duser"):
            extension["duser"] = extra.get("duser")
        if extra.get("dntdom"):
            extension["dntdom"] = extra.get("dntdom")
        if extra.get("dhost"):
            extension["dhost"] = extra.get("dhost")
        if extra.get("dpt") is not None:
            extension["dpt"] = int(extra["dpt"])

    extension.update({k: v for k, v in extra.items() if v is not None and not str(k).startswith("_")})

    if event_id in ("INT001", "INT002"):
        extension.pop("src", None)
        extension["shost"] = os.getenv("CEF_INT_SHOST", "localhost")
        extension["spt"] = 0

    fmt_map = _SafeDict({**extension, "cat": spec.cat, "cef_tail": cef_tail or ""})
    if "dmail" not in fmt_map or fmt_map["dmail"] in ("", "-"):
        fmt_map["dmail"] = (current_user_effective or {}).get("email") or "-"
    if event_id == "AGT003" and (fmt_map.get("agt_copy_target") in (None, "", "-")):
        fmt_map["agt_copy_target"] = fmt_map.get("cs2") or "-"

    extension["msg"] = spec.msg_template.format_map(fmt_map)

    for _msg_only in ("agt_copy_target", "dmail"):
        extension.pop(_msg_only, None)

    # Заголовок CEF: поля через "|", далее расширение — пары key=value через пробел (как в CEF.md §7).
    prefix = "CEF:0|{vendor}|{product}|{version}|{event_id}|{name}|{severity}|".format(
        vendor=os.getenv("CEF_DEVICE_VENDOR", "CORSUR"),
        product=os.getenv("CEF_DEVICE_PRODUCT", "AstraChat"),
        version=os.getenv("CEF_DEVICE_VERSION", "0.0.0"),
        event_id=spec.event_id,
        name=spec.name,
        severity=spec.severity,
    )
    ext_str = " ".join(f"{k}={_esc(v)}" for k, v in _extension_ordered_items(extension))
    logger.info("%s%s", prefix, ext_str)
