"""
Сервис для работы с памятью диалогов через MongoDB
Файловый режим отключен - используется только MongoDB
"""

import logging
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Флаг доступности MongoDB
mongodb_available = False
conversation_repo = None
get_conversation_repository = None
Conversation = None
Message = None

try:
    from backend.database.init_db import get_conversation_repository
    from backend.database.mongodb.models import Conversation, Message
    # Устанавливаем флаг только если модули импортированы
    # Реальная доступность будет проверяться при использовании
    logger.info("MongoDB модуль импортирован для работы с памятью")
    logger.debug(f"get_conversation_repository импортирован: {get_conversation_repository is not None}")
except ImportError as e:
    logger.error(f"MongoDB недоступен: {e}")
    logger.error("Приложение не сможет сохранять диалоги без MongoDB!")
    get_conversation_repository = None
    Conversation = None
    Message = None


def _check_mongodb_available() -> bool:
    """Проверка реальной доступности MongoDB (не только импорт модулей)"""
    global conversation_repo, mongodb_available
    
    if get_conversation_repository is None:
        logger.warning("get_conversation_repository is None - MongoDB модули не импортированы")
        logger.warning("  Убедитесь, что motor и pymongo установлены в виртуальном окружении")
        mongodb_available = False
        return False
    
    try:
        # Пытаемся получить репозиторий - это проверит реальную инициализацию
        conversation_repo = get_conversation_repository()
        mongodb_available = True
        logger.debug("MongoDB доступен - репозиторий получен успешно")
        return True
    except RuntimeError as e:
        # MongoDB не инициализирован
        mongodb_available = False
        logger.warning(f"MongoDB не инициализирован: {e}")
        logger.warning("  Убедитесь, что init_mongodb() был вызван при старте приложения")
        return False
    except Exception as e:
        mongodb_available = False
        logger.error(f"Ошибка при проверке доступности MongoDB: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


# Глобальная переменная для текущего ID диалога
current_conversation_id = None


def get_or_create_conversation_id() -> str:
    """Получение или создание ID текущего диалога"""
    global current_conversation_id
    if current_conversation_id is None:
        current_conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    return current_conversation_id


def reset_conversation():
    """Сброс текущего диалога (начало нового)"""
    global current_conversation_id
    current_conversation_id = None


async def save_dialog_entry_mongodb(role: str, content: str, metadata: Optional[Dict[str, Any]] = None, message_id: Optional[str] = None, conversation_id: Optional[str] = None) -> bool:
    """
    Сохранение сообщения в MongoDB
    
    Args:
        role: Роль отправителя (user, assistant, system)
        content: Содержание сообщения
        metadata: Дополнительные метаданные
        message_id: ID сообщения (если не указан, генерируется автоматически)
        conversation_id: ID диалога (если не указан, используется текущий или создается новый)
        
    Returns:
        True если успешно, False в случае ошибки
    """
    try:
        global conversation_repo
        
        # Проверяем доступность MongoDB
        if not _check_mongodb_available():
            logger.error("MongoDB не инициализирован. Не удалось сохранить сообщение.")
            return False
        
        if conversation_repo is None:
            conversation_repo = get_conversation_repository()
        
        # Используем переданный conversation_id или получаем/создаем новый
        if conversation_id is None:
            conversation_id = get_or_create_conversation_id()
        
        # Используем переданный message_id или генерируем новый
        if message_id is None:
            message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        # Создаем сообщение
        message = Message(
            message_id=message_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Проверяем, существует ли диалог
        existing_conversation = await conversation_repo.get_conversation(conversation_id)
        
        if existing_conversation is None:
            # Создаем новый диалог
            conversation = Conversation(
                conversation_id=conversation_id,
                user_id="default_user",  # TODO: добавить поддержку пользователей
                title=f"Диалог {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                messages=[message],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await conversation_repo.create_conversation(conversation)
            logger.debug(f"Создан новый диалог: {conversation_id}")
        else:
            # Добавляем сообщение в существующий диалог
            await conversation_repo.add_message(conversation_id, message)
            logger.debug(f"Добавлено сообщение в диалог: {conversation_id}")
        
        return True
        
    except RuntimeError as e:
        # MongoDB не инициализирован
        logger.error(f"MongoDB не инициализирован: {e}")
        mongodb_available = False
        return False
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения в MongoDB: {e}")
        return False


async def save_dialog_entry(role: str, content: str, metadata: Optional[Dict[str, Any]] = None, message_id: Optional[str] = None, conversation_id: Optional[str] = None):
    """
    Сохранение сообщения в MongoDB (файловый режим отключен)
    
    Args:
        role: Роль отправителя
        content: Содержание сообщения
        metadata: Дополнительные метаданные
        message_id: ID сообщения (опционально)
        conversation_id: ID диалога (опционально)
    """
    # Проверяем реальную доступность MongoDB
    if not _check_mongodb_available():
        logger.error("MongoDB недоступен! Сообщение не будет сохранено.")
        raise RuntimeError("MongoDB недоступен. Невозможно сохранить сообщение.")
    
    try:
        success = await save_dialog_entry_mongodb(role, content, metadata, message_id, conversation_id)
        if not success:
            raise RuntimeError("Не удалось сохранить сообщение в MongoDB")
    except RuntimeError:
        # Пробрасываем RuntimeError как есть
        raise
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения: {e}")
        raise RuntimeError(f"Ошибка при сохранении сообщения: {e}")


async def load_dialog_history_mongodb(conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Загрузка истории диалога из MongoDB
    
    Args:
        conversation_id: ID диалога (если None, используется текущий)
        
    Returns:
        Список сообщений в формате словарей
    """
    try:
        global conversation_repo
        
        # Проверяем доступность MongoDB
        if not _check_mongodb_available():
            logger.warning("MongoDB не инициализирован. Не удалось загрузить историю.")
            return []
        
        if conversation_repo is None:
            conversation_repo = get_conversation_repository()
        
        if conversation_id is None:
            conversation_id = get_or_create_conversation_id()
        
        conversation = await conversation_repo.get_conversation(conversation_id)
        
        if conversation is None:
            return []
        
        # Конвертируем в формат словарей
        history = []
        for message in conversation.messages:
            history.append({
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat() if message.timestamp else None
            })
        
        return history
        
    except RuntimeError as e:
        logger.warning(f"MongoDB не инициализирован: {e}")
        mongodb_available = False
        return []
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории из MongoDB: {e}")
        return []


async def load_dialog_history() -> List[Dict[str, Any]]:
    """
    Загрузка истории диалога из MongoDB (файловый режим отключен)
    """
    # Проверяем реальную доступность MongoDB
    if not _check_mongodb_available():
        logger.warning("MongoDB недоступен! Возвращаем пустую историю.")
        return []
    
    try:
        return await load_dialog_history_mongodb()
    except Exception as e:
        logger.error(f"Ошибка при загрузке истории: {e}")
        return []


async def get_recent_dialog_history_mongodb(max_entries: Optional[int] = None, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Получение последних N сообщений из MongoDB
    
    Args:
        max_entries: Максимальное количество сообщений
        conversation_id: ID диалога (если None, используется текущий)
        
    Returns:
        Список последних сообщений
    """
    try:
        history = await load_dialog_history_mongodb(conversation_id)
        
        if max_entries is None:
            max_entries = int(os.getenv("MEMORY_MAX_HISTORY_LENGTH", "20"))
        
        return history[-max_entries:] if len(history) > max_entries else history
        
    except Exception as e:
        logger.error(f"Ошибка при получении последних сообщений из MongoDB: {e}")
        return []


async def get_recent_dialog_history(max_entries: Optional[int] = None, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Получение последних сообщений из MongoDB (файловый режим отключен)
    
    Args:
        max_entries: Максимальное количество сообщений
        conversation_id: ID диалога (если None, используется текущий)
    """
    # Проверяем реальную доступность MongoDB
    if not _check_mongodb_available():
        logger.warning("MongoDB недоступен! Возвращаем пустую историю.")
        return []
    
    try:
        # Если conversation_id не передан, используем текущий
        if conversation_id is None:
            conversation_id = get_or_create_conversation_id()
        
        return await get_recent_dialog_history_mongodb(max_entries, conversation_id)
    except Exception as e:
        logger.error(f"Ошибка при получении последних сообщений: {e}")
        return []


async def clear_dialog_history_mongodb() -> str:
    """Очистка истории диалога в MongoDB"""
    try:
        global conversation_repo
        
        # Проверяем доступность MongoDB
        if not _check_mongodb_available():
            logger.error("MongoDB не инициализирован. Не удалось очистить историю.")
            return "Ошибка: MongoDB не инициализирован"
        
        if conversation_repo is None:
            conversation_repo = get_conversation_repository()
        
        conversation_id = get_or_create_conversation_id()
        
        # Удаляем текущий диалог
        await conversation_repo.delete_conversation(conversation_id)
        
        # Сбрасываем ID диалога
        reset_conversation()
        
        logger.info(f"История диалога {conversation_id} очищена")
        return "История диалога очищена"
        
    except RuntimeError as e:
        logger.error(f"MongoDB не инициализирован: {e}")
        mongodb_available = False
        return f"Ошибка: MongoDB не инициализирован"
    except Exception as e:
        logger.error(f"Ошибка при очистке истории в MongoDB: {e}")
        return f"Ошибка при очистке истории: {str(e)}"


async def clear_dialog_history() -> str:
    """
    Очистка истории диалога в MongoDB (файловый режим отключен)
    """
    # Проверяем реальную доступность MongoDB
    if not _check_mongodb_available():
        logger.error("MongoDB недоступен! Невозможно очистить историю.")
        return "Ошибка: MongoDB недоступен"
    
    try:
        return await clear_dialog_history_mongodb()
    except Exception as e:
        logger.error(f"Ошибка при очистке истории: {e}")
        return f"Ошибка при очистке: {str(e)}"


async def search_conversations(query: str, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Поиск диалогов по тексту (только MongoDB)
    
    Args:
        query: Поисковый запрос
        user_id: Опциональный фильтр по пользователю
        limit: Максимальное количество результатов
        
    Returns:
        Список найденных диалогов
    """
    # Проверяем реальную доступность MongoDB
    if not _check_mongodb_available():
        logger.warning("Поиск доступен только с MongoDB")
        return []
    
    try:
        global conversation_repo
        if conversation_repo is None:
            conversation_repo = get_conversation_repository()
        
        conversations = await conversation_repo.search_conversations(query, user_id, limit)
        
        # Конвертируем в формат словарей
        results = []
        for conv in conversations:
            results.append({
                "conversation_id": conv.conversation_id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "message_count": len(conv.messages)
            })
        
        return results
        
    except RuntimeError as e:
        logger.warning(f"MongoDB не инициализирован: {e}")
        mongodb_available = False
        return []
    except Exception as e:
        logger.error(f"Ошибка при поиске диалогов: {e}")
        return []

