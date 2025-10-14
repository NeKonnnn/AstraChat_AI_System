"""
Улучшенный main.py с поддержкой LangGraph и MCP
Демонстрирует интеграцию новой архитектуры агента
"""

# Настройка кодировки для Windows
import sys
import os

# Импортируем утилиту для исправления кодировки
try:
    from utils.encoding_fix import fix_windows_encoding, safe_print
    fix_windows_encoding()
except ImportError:
    # Если утилита недоступна, используем базовую настройку
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import asyncio
import json
import os
import sys
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from socketio import AsyncServer, ASGIApp
from starlette.applications import Starlette

# Добавляем корневую директорию в путь для импорта модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

# Настройка логирования с поддержкой UTF-8
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s [Enhanced Backend] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Настройка кодировки для обработчиков логирования
for handler in logging.root.handlers:
    if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
        handler.stream.reconfigure(encoding='utf-8')
logger = logging.getLogger(__name__)

# Импорты оригинального MemoAI
try:
    from backend.agent import ask_agent, model_settings, update_model_settings, reload_model_by_path, get_model_info, initialize_model
    logger.info("Оригинальный agent импортирован успешно")
except ImportError as e:
    logger.error(f"Ошибка импорта оригинального agent: {e}")
    ask_agent = None

# Импорты новой архитектуры
try:
    from backend.langgraph_agent import initialize_langgraph_agent, get_langgraph_agent
    from backend.mcp_client import initialize_mcp_client, get_mcp_client
    from backend.advanced_tools import get_all_advanced_tools
    logger.info("Новая архитектура импортирована успешно")
except ImportError as e:
    logger.error(f"Ошибка импорта новой архитектуры: {e}")
    initialize_langgraph_agent = None
    initialize_mcp_client = None

# Импорты памяти и других модулей
try:
    from backend.memory import save_dialog_entry, load_dialog_history, clear_dialog_history, get_recent_dialog_history
    from backend.voice import speak_text, recognize_speech, recognize_speech_from_file, check_vosk_model
    from backend.document_processor import DocumentProcessor
    logger.info("Вспомогательные модули импортированы успешно")
except ImportError as e:
    logger.error(f"Ошибка импорта вспомогательных модулей: {e}")

# Создание FastAPI приложения
app = FastAPI(
    title="MemoAI Enhanced",
    description="Улучшенный ИИ агент с поддержкой LangGraph и MCP",
    version="2.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO сервер
sio = AsyncServer(cors_allowed_origins="*")
socket_app = ASGIApp(sio, app)

# Глобальные переменные
langgraph_agent = None
mcp_client = None
doc_processor = None
memory_max_messages = 10

# Инициализация при запуске
@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения"""
    global langgraph_agent, mcp_client, doc_processor
    
    logger.info("Запуск MemoAI Enhanced...")
    
    # Инициализация оригинального агента
    if ask_agent:
        logger.info("Оригинальный агент доступен")
    
    # Инициализация LangGraph агента
    if initialize_langgraph_agent:
        try:
            success = initialize_langgraph_agent()
            if success:
                langgraph_agent = get_langgraph_agent()
                logger.info("LangGraph агент инициализирован")
            else:
                logger.warning("Не удалось инициализировать LangGraph агент")
        except Exception as e:
            logger.error(f"Ошибка инициализации LangGraph агента: {e}")
    
    # Инициализация MCP клиента
    if initialize_mcp_client:
        try:
            success = await initialize_mcp_client()
            if success:
                mcp_client = get_mcp_client()
                logger.info("MCP клиент инициализирован")
            else:
                logger.warning("Не удалось инициализировать MCP клиент")
        except Exception as e:
            logger.error(f"Ошибка инициализации MCP клиента: {e}")
    
    # Инициализация обработчика документов
    try:
        doc_processor = DocumentProcessor()
        logger.info("Обработчик документов инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации обработчика документов: {e}")
    
    logger.info("MemoAI Enhanced готов к работе!")

@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении работы"""
    global mcp_client
    
    if mcp_client:
        await mcp_client.cleanup()
        logger.info("MCP клиент очищен")

# ================================
# API ЭНДПОИНТЫ
# ================================

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "MemoAI Enhanced API",
        "version": "2.0.0",
        "features": [
            "LangGraph Agent",
            "MCP Protocol Support", 
            "Advanced Tools",
            "Document Processing",
            "Voice Interface"
        ],
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "original_agent": ask_agent is not None,
            "langgraph_agent": langgraph_agent is not None,
            "mcp_client": mcp_client is not None,
            "document_processor": doc_processor is not None
        }
    }

@app.get("/api/agent/info")
async def get_agent_info():
    """Получение информации об агентах"""
    info = {
        "original_agent": {
            "available": ask_agent is not None,
            "model_info": get_model_info() if ask_agent else None
        },
        "langgraph_agent": {
            "available": langgraph_agent is not None,
            "tools_count": len(get_all_advanced_tools()) if langgraph_agent else 0
        },
        "mcp_client": {
            "available": mcp_client is not None,
            "servers": list(mcp_client.servers.keys()) if mcp_client else [],
            "tools": list(mcp_client.tools.keys()) if mcp_client else []
        }
    }
    return info

# ================================
# ЧАТ API С ПОДДЕРЖКОЙ НОВОЙ АРХИТЕКТУРЫ
# ================================

from pydantic import BaseModel

class ChatMessage(BaseModel):
    message: str
    use_langgraph: bool = True
    use_mcp: bool = True

class ChatResponse(BaseModel):
    response: str
    agent_type: str
    tools_used: List[str] = []
    processing_time: float

@app.post("/api/chat/enhanced", response_model=ChatResponse)
async def enhanced_chat(message: ChatMessage):
    """Улучшенный чат с поддержкой LangGraph и MCP"""
    start_time = datetime.now()
    
    try:
        response_text = ""
        agent_type = "original"
        tools_used = []
        
        # Выбираем агента для обработки
        if message.use_langgraph and langgraph_agent:
            # Используем LangGraph агента
            response_text = langgraph_agent.process_message_sync(message.message)
            agent_type = "langgraph"
            
            # TODO: Добавить отслеживание использованных инструментов
            
        elif ask_agent:
            # Используем оригинального агента
            history = get_recent_dialog_history(max_entries=memory_max_messages) if get_recent_dialog_history else []
            response_text = ask_agent(message.message, history=history, streaming=False)
            agent_type = "original"
        
        else:
            response_text = "Агенты недоступны. Проверьте инициализацию системы."
        
        # Сохраняем в память
        if save_dialog_entry:
            save_dialog_entry("user", message.message)
            save_dialog_entry("assistant", response_text)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ChatResponse(
            response=response_text,
            agent_type=agent_type,
            tools_used=tools_used,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Ошибка в enhanced_chat: {e}")
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ChatResponse(
            response=f"Ошибка обработки сообщения: {str(e)}",
            agent_type="error",
            tools_used=[],
            processing_time=processing_time
        )

# ================================
# MCP API
# ================================

@app.get("/api/mcp/servers")
async def get_mcp_servers():
    """Получение списка MCP серверов"""
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP клиент недоступен")
    
    servers_info = {}
    for name, server in mcp_client.servers.items():
        servers_info[name] = {
            "type": server.type,
            "enabled": server.enabled,
            "running": name in mcp_client.processes
        }
    
    return {"servers": servers_info}

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """Получение списка MCP инструментов"""
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP клиент недоступен")
    
    tools_info = {}
    for name, tool in mcp_client.tools.items():
        tools_info[name] = {
            "description": tool.description,
            "server": tool.server,
            "parameters": tool.parameters
        }
    
    return {"tools": tools_info}

@app.post("/api/mcp/call")
async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]):
    """Вызов MCP инструмента"""
    if not mcp_client:
        raise HTTPException(status_code=503, detail="MCP клиент недоступен")
    
    try:
        result = await mcp_client.call_tool(tool_name, arguments)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка вызова инструмента: {str(e)}")

# ================================
# WEBSOCKET ПОДДЕРЖКА
# ================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/enhanced")
async def websocket_enhanced_chat(websocket: WebSocket):
    """WebSocket для улучшенного чата"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_message = message_data.get("message", "")
            use_langgraph = message_data.get("use_langgraph", True)
            
            logger.info(f"WebSocket enhanced chat: {user_message[:50]}...")
            
            # Обрабатываем сообщение
            if use_langgraph and langgraph_agent:
                response = langgraph_agent.process_message_sync(user_message)
                agent_type = "langgraph"
            elif ask_agent:
                history = get_recent_dialog_history(max_entries=memory_max_messages) if get_recent_dialog_history else []
                response = ask_agent(user_message, history=history, streaming=False)
                agent_type = "original"
            else:
                response = "Агенты недоступны"
                agent_type = "error"
            
            # Отправляем ответ
            await websocket.send_text(json.dumps({
                "type": "response",
                "content": response,
                "agent_type": agent_type,
                "timestamp": datetime.now().isoformat()
            }))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ================================

if __name__ == "__main__":
    uvicorn.run(
        "enhanced_main:socket_app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

