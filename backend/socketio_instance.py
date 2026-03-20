"""
socketio_instance.py - создание AsyncServer (Socket.IO)

Выделено в отдельный модуль, чтобы избежать circular imports:
    main.py          → импортирует sio и socket_app
    socket_handlers  → импортирует sio отсюда же
"""

from socketio import AsyncServer, ASGIApp
from starlette.applications import Starlette
from backend.app_state import settings

# -- собираем список разрешенных origins из конфига
urls = settings.urls
_origins_raw = [
    getattr(urls, "frontend_port_1", None),
    getattr(urls, "frontend_port_1_ipv4", None),
    getattr(urls, "backend_port_1", None),
    getattr(urls, "backend_port_1_ipv4", None),
    getattr(urls, "frontend_docker", None),
    getattr(urls, "backend_docker", None),
]
socketio_origins = [o for o in _origins_raw if o]

sio = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=socketio_origins,
    ping_timeout=300,
    ping_interval=15,
    logger=False,
    engineio_logger=False,
)

_starlette_app = Starlette()
socket_app = ASGIApp(sio, _starlette_app)
