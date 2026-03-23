"""
backend/ws/ - Socket.IO подсистема

Структура:
    instance.py   - создание AsyncServer (sio) и socket_app
    handlers.py   - @sio.event обработчики, register_handlers()
    helpers.py    - утилиты, общие для handlers и роутеров
"""

from backend.realtime.instance import sio, socket_app
from backend.realtime.handlers import register_handlers

__all__ = ["sio", "socket_app", "register_handlers"]
