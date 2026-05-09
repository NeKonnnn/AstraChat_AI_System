"""CEF-аудит: события и контекст запроса для LLM/памяти."""

from backend.settings.cef_logger.cef_audit_context import cef_audit_peek, cef_audit_reset, cef_audit_set
from backend.settings.cef_logger.cef_logger import (
    CEFEventSpec,
    EVENTS,
    cef_llm_int003_extra,
    domain_from_ldap_base_dn,
    ldap_audit_cs_fields,
    ldap_reason_suffix,
    log_cef_event,
    log_cef_int003_llm_request,
    log_cef_obj002_llm_api_failure,
    request_context,
)

__all__ = [
    "CEFEventSpec",
    "EVENTS",
    "cef_audit_peek",
    "cef_audit_reset",
    "cef_audit_set",
    "cef_llm_int003_extra",
    "domain_from_ldap_base_dn",
    "ldap_audit_cs_fields",
    "ldap_reason_suffix",
    "log_cef_event",
    "log_cef_int003_llm_request",
    "log_cef_obj002_llm_api_failure",
    "request_context",
]
