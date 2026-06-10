"""HTTP middleware: request + пользователь в CEF audit context для исходящих INT005/INT006 и т.д."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.settings.cef_logger.cef_audit_context import cef_audit_reset, cef_audit_set


class CefAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        user = None
        try:
            from backend.auth.jwt_handler import try_user_from_request

            user = try_user_from_request(request)
        except Exception:
            pass

        tokens = cef_audit_set(request=request, user=user, socket_remote=None)
        try:
            return await call_next(request)
        finally:
            cef_audit_reset(tokens)
