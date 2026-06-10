"""
socket/instance.py — создание AsyncServer (Socket.IO)

Выделено в отдельный модуль, чтобы избежать circular imports:
    main.py        -> импортирует sio и socket_app
    handlers.py    -> импортирует sio отсюда же
"""

from socketio import AsyncServer, ASGIApp
from starlette.applications import Starlette
from backend.app_state import settings
import os

# Лимит тела Socket.IO-сообщения (inline-картинки в base64 могут быть >1 МБ).
_DEFAULT_SOCKET_MAX_HTTP_BUFFER_BYTES = 52 * 1024 * 1024  # чуть выше INLINE_ATTACHMENT_MAX_BYTES (50 МБ)


def _socket_max_http_buffer_size() -> int:
    raw = os.getenv("SOCKET_MAX_HTTP_BUFFER_BYTES")
    if raw is None or not str(raw).strip():
        return _DEFAULT_SOCKET_MAX_HTTP_BUFFER_BYTES
    try:
        value = int(str(raw).strip())
    except ValueError:
        return _DEFAULT_SOCKET_MAX_HTTP_BUFFER_BYTES
    return max(value, 1_048_576)

# -- собираем список разрешённых origins из конфига
urls = settings.urls
_origins_raw = [
    getattr(urls, "frontend_port", None),
    getattr(urls, "frontend_port_ipv4", None),
    getattr(urls, "backend_port", None),
    getattr(urls, "backend_port_ipv4", None),
    getattr(urls, "frontend_docker", None),
    getattr(urls, "backend_docker", None),
    getattr(urls, "ingress_port", None),
]
socketio_origins = [o for o in _origins_raw if o]

sio = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=socketio_origins,
    ping_timeout=300,
    ping_interval=15,
    max_http_buffer_size=_socket_max_http_buffer_size(),
    logger=False,
    engineio_logger=False,
)

_starlette_app = Starlette()
socket_app = ASGIApp(sio, _starlette_app)
