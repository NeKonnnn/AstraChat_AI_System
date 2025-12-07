"""
Инструменты для работы с промптами
Помогают создавать, улучшать и анализировать промпты для LLM
"""

import logging
import asyncio
import re
from contextvars import ContextVar
from typing import Dict, Any, Optional
from langchain_core.tools import tool
import threading

logger = logging.getLogger(__name__)

# ContextVar для контекста инструментов (работает через потоки и async/await)
_tool_context: ContextVar[Dict[str, Any]] = ContextVar('tool_context', default={})

# Глобальная переменная с блокировкой для контекста (запасной вариант)
_global_tool_context: Dict[str, Any] = {}
_global_context_lock = threading.Lock()


def _run_async_agent(agent_class, message: str, context: Dict[str, Any] = None):
    """
    Вспомогательная функция для запуска асинхронных агентов в синхронном контексте
    """
    try:
        # Получаем контекст из ContextVar если не передан
        if context is None:
            context = get_tool_context()
            logger.info(f"[_run_async_agent] Получен контекст из ContextVar: streaming={context.get('streaming', False)}")
        
        # Если все еще пусто, пробуем глобальный контекст
        if not context:
            context = _get_global_context()
            logger.info(f"[_run_async_agent] Получен глобальный контекст")
        
        logger.info(f"[_run_async_agent] Финальный контекст для агента: streaming={context.get('streaming', False)}, has_callback={context.get('stream_callback') is not None}")
        
        # Применяем nest_asyncio для поддержки вложенных event loops
        try:
            import nest_asyncio
            nest_asyncio.apply()
            logger.info(f"[_run_async_agent] nest_asyncio применен глобально")
        except ImportError:
            logger.warning(f"[_run_async_agent] nest_asyncio не установлен, могут быть проблемы")
        
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            logger.info(f"[_run_async_agent] Обнаружен запущенный event loop, сохраняем ссылку")
            
            # Сохраняем ссылку на основной event loop в контексте
            if context:
                context = context.copy()
                context['_main_event_loop'] = loop
            
            # Благодаря nest_asyncio можем вызывать asyncio.run напрямую в текущем потоке
            logger.info(f"[_run_async_agent] Запускаем агента напрямую через _run_in_new_loop (с nest_asyncio)")
            return _run_in_new_loop(agent_class, message, context)
            
        except RuntimeError:
            logger.info(f"[_run_async_agent] Нет запущенного event loop, запускаем напрямую")
            # Нет запущенного loop, можем использовать asyncio.run напрямую
            return _run_in_new_loop(agent_class, message, context)
    except Exception as e:
        logger.error(f"Ошибка в _run_async_agent: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Ошибка выполнения агента: {str(e)}"


def _run_in_new_loop(agent_class, message: str, context: Dict[str, Any] = None):
    """Запуск агента в новом event loop с поддержкой вложенных loops"""
    
    # Применяем nest_asyncio в САМОМ НАЧАЛЕ
    try:
        import nest_asyncio
        nest_asyncio.apply()
        logger.info(f"[_run_in_new_loop] nest_asyncio применен в начале функции")
    except ImportError:
        logger.warning(f"[_run_in_new_loop] nest_asyncio не установлен")
    
    # ВАЖНО: Для stream_callback нужно использовать основной event loop
    # Создаем синхронную версию callback для использования в новом потоке
    original_callback = context.get('stream_callback') if context else None
    main_loop = context.get('_main_event_loop') if context else None
    
    logger.info(f"[_run_in_new_loop] Контекст: streaming={context.get('streaming') if context else False}, has_sio={context.get('sio') is not None if context else False}, has_socket_id={context.get('socket_id') is not None if context else False}, has_callback={original_callback is not None}")
    logger.info(f"[_run_in_new_loop] Main loop: {'доступен' if main_loop and not main_loop.is_closed() else 'НЕДОСТУПЕН'}")
    
    # Получаем sio и socket_id для прямого emit (нужны всегда, даже без callback)
    sio = context.get('sio') if context else None
    socket_id = context.get('socket_id') if context else None
    
    logger.info(f"[_run_in_new_loop] sio={'есть' if sio else 'НЕТ'}, socket_id={socket_id if socket_id else 'НЕТ'}")
    
    if original_callback:
        logger.info(f"[_run_in_new_loop] Обнаружен stream_callback, создаем wrapper")
        
        if sio and socket_id:
            logger.info(f"[_run_in_new_loop] Используем прямой синхронный emit через Socket.IO (thread-safe)")
            
            # Создаем синхронный wrapper для async emit через Socket.IO
            def sync_callback_wrapper(chunk: str, accumulated: str):
                try:
                    # logger.info(f"[sync_callback_wrapper] Вызван! chunk_len={len(chunk)}, накоплено={len(accumulated)}")
                    
                    if sio and socket_id and main_loop and not main_loop.is_closed():
                        # ИСПРАВЛЕНИЕ: sio.emit() - это АСИНХРОННЫЙ метод в AsyncServer!
                        # Используем run_coroutine_threadsafe для отправки в основной event loop
                        try:
                            import asyncio
                            future = asyncio.run_coroutine_threadsafe(
                                sio.emit('chat_chunk', {
                                    'chunk': chunk,
                                    'accumulated': accumulated
                                }, room=socket_id),
                                main_loop
                            )
                            # Не ждем результат - просто запускаем в фоне
                            # logger.info(f"[sync_callback_wrapper] ✓ Chunk ОТПРАВЛЕН через Socket.IO!")
                        except Exception as e:
                            logger.error(f"[sync_callback_wrapper] Ошибка при отправке через Socket.IO: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    else:
                        # logger.warning(f"[sync_callback_wrapper] sio, socket_id или main_loop отсутствуют")
                        pass
                    
                    return True
                        
                except Exception as e:
                    logger.error(f"[sync_callback_wrapper] Критическая ошибка: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return True
            
            # Заменяем async callback на sync wrapper
            if context:
                context = context.copy()
                context['stream_callback'] = sync_callback_wrapper
                logger.info(f"[_run_in_new_loop] Stream callback заменен на sync wrapper с прямым emit")
        else:
            logger.warning(f"[_run_in_new_loop] sio, socket_id или main_loop отсутствуют, callback не будет работать")
    
    async def _async_wrapper():
        agent = agent_class()
        # ВАЖНО: Используем context с обновленным stream_callback (sync wrapper)
        agent_context = context if context is not None else {"history": []}
        logger.info(f"[_run_in_new_loop] Запуск агента с контекстом: streaming={agent_context.get('streaming', False)}, has_callback={agent_context.get('stream_callback') is not None}")
        # Обновляем tool_context с обновленным stream_callback, чтобы агенты могли его получить
        if context and 'stream_callback' in context:
            set_tool_context(context)
            logger.info(f"[_run_in_new_loop] Обновлен tool_context с stream_callback для агента")
        return await agent.process_message(message, agent_context)
    
    # nest_asyncio уже применен в начале функции, повторно не нужно
    
    return asyncio.run(_async_wrapper())


def set_tool_context(context: Dict[str, Any]):
    """Установка контекста для инструментов (вызывается из orchestrator)"""
    # Устанавливаем в ContextVar
    _tool_context.set(context)
    
    # Также устанавливаем в глобальную переменную (запасной вариант)
    global _global_tool_context
    with _global_context_lock:
        _global_tool_context = context.copy()
    
    logger.info(f"[set_tool_context] Установлен контекст (двойной): streaming={context.get('streaming', False)}, has_callback={context.get('stream_callback') is not None}")


def get_tool_context() -> Dict[str, Any]:
    """Получение контекста для инструментов"""
    # Сначала пытаемся получить из ContextVar
    result = _tool_context.get()
    
    # Если пусто, пробуем глобальную переменную
    if not result:
        with _global_context_lock:
            result = _global_tool_context.copy() if _global_tool_context else {}
        logger.info(f"[get_tool_context] Получен из глобальной переменной: streaming={result.get('streaming', False)}")
    else:
        logger.info(f"[get_tool_context] Получен из ContextVar: streaming={result.get('streaming', False)}")
    
    return result


def _get_global_context():
    """Получение глобального контекста из main.py"""
    try:
        # Сначала пытаемся получить контекст из thread-local хранилища
        tool_context = get_tool_context()
        if tool_context:
            logger.info(f"[TOOL_CONTEXT] Получен контекст из thread-local: streaming={tool_context.get('streaming', False)}")
            return tool_context
        
        # Если нет, получаем из main.py
        import backend.main as main_module
        context = {}
        
        # Получаем doc_processor
        if hasattr(main_module, 'doc_processor'):
            context['doc_processor'] = main_module.doc_processor
        
        # Получаем выбранную модель
        if hasattr(main_module, 'selected_model'):
            context['selected_model'] = main_module.selected_model
        
        # Получаем историю диалога, если доступна
        # Примечание: get_recent_dialog_history может быть async, поэтому пропускаем
        # История будет передана через контекст при вызове агента
            
        return context
    except Exception as e:
        logger.warning(f"Не удалось получить глобальный контекст: {e}")
        return {}


@tool
def enhance_prompt(user_description: str) -> str:
    """
    Создание качественного промпта для LLM на основе простого описания пользователя.
    Преобразует простое описание в структурированный, эффективный промпт с четкими инструкциями.
    
    Используй этот инструмент, когда пользователь просит:
    - Создать промпт для какой-либо задачи
    - Помочь написать промпт
    - Улучшить простое описание в качественный промпт
    
    Args:
        user_description: Простое описание задачи или желаемого результата от LLM
        
    Returns:
        Улучшенный, структурированный промпт с объяснением улучшений
    """
    try:
        logger.info(f"[TOOL] enhance_prompt вызван: {user_description[:100]}...")
        
        # Проверяем контекст сразу при входе в инструмент
        ctx = get_tool_context()
        logger.info(f"[TOOL] enhance_prompt контекст: streaming={ctx.get('streaming', False)}, has_callback={ctx.get('stream_callback') is not None}")
        
        try:
            from backend.agents.prompt_enhancement_agent import PromptEnhancementAgent
        except ModuleNotFoundError:
            from agents.prompt_enhancement_agent import PromptEnhancementAgent
        
        result = _run_async_agent(PromptEnhancementAgent, user_description)
        logger.info(f"[TOOL] enhance_prompt результат: {len(result)} символов")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в enhance_prompt: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Ошибка при создании промпта: {str(e)}"


@tool
def improve_existing_prompt(prompt_text: str) -> str:
    """
    Улучшение существующего промпта.
    Анализирует текущий промпт и создает оптимизированную версию с улучшениями.
    
    Используй этот инструмент, когда пользователь просит:
    - Улучшить существующий промпт
    - Оптимизировать промпт
    - Сделать промпт более эффективным
    
    Args:
        prompt_text: Текст существующего промпта для улучшения
        
    Returns:
        Улучшенная версия промпта с объяснением изменений
    """
    try:
        logger.info(f"[TOOL] improve_existing_prompt: {prompt_text[:100]}...")
        
        try:
            from backend.agents.prompt_enhancement_agent import PromptEnhancementAgent
        except ModuleNotFoundError:
            from agents.prompt_enhancement_agent import PromptEnhancementAgent
        
        message = f"Улучши следующий промпт: {prompt_text}"
        result = _run_async_agent(PromptEnhancementAgent, message)
        logger.info(f"[TOOL] improve_existing_prompt результат: {len(result)} символов")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в improve_existing_prompt: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Ошибка при улучшении промпта: {str(e)}"


@tool
def analyze_prompt_quality(prompt_text: str) -> str:
    """
    Анализ качества промпта.
    Оценивает промпт по различным критериям и дает рекомендации по улучшению.
    
    Используй этот инструмент, когда пользователь просит:
    - Проанализировать промпт
    - Оценить качество промпта
    - Получить обратную связь по промпту
    
    Args:
        prompt_text: Текст промпта для анализа
        
    Returns:
        Детальный анализ промпта с оценками и рекомендациями
    """
    try:
        logger.info(f"[TOOL] analyze_prompt_quality: {prompt_text[:100]}...")
        
        try:
            from backend.agents.prompt_enhancement_agent import PromptEnhancementAgent
        except ModuleNotFoundError:
            from agents.prompt_enhancement_agent import PromptEnhancementAgent
        
        message = f"Проанализируй следующий промпт: {prompt_text}"
        result = _run_async_agent(PromptEnhancementAgent, message)
        logger.info(f"[TOOL] analyze_prompt_quality результат: {len(result)} символов")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в analyze_prompt_quality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Ошибка при анализе промпта: {str(e)}"


@tool
def save_prompt_to_gallery(
    title: str,
    prompt_content: str,
    description: Optional[str] = None,
    is_public: bool = True,
    tag_names: Optional[str] = None
) -> str:
    """
    Сохранение промпта в галерею промптов.
    Сохраняет созданный или улучшенный промпт в базу данных для дальнейшего использования.
    
    Используй этот инструмент, когда пользователь просит:
    - Сохранить промпт
    - Добавить промпт в галерею
    - Сохранить промпт для будущего использования
    
    Args:
        title: Название промпта (минимум 3 символа)
        prompt_content: Текст промпта (минимум 10 символов)
        description: Описание промпта (опционально)
        is_public: Публичный или приватный промпт (по умолчанию True)
        tag_names: Теги через запятую (опционально)
        
    Returns:
        Сообщение об успешном сохранении или ошибке
    """
    try:
        logger.info(f"[TOOL] save_prompt_to_gallery: title={title}, content_length={len(prompt_content)}")
        
        # Валидация
        if len(title) < 3:
            return "Ошибка: Название промпта должно содержать минимум 3 символа"
        
        if len(prompt_content) < 10:
            return "Ошибка: Текст промпта должен содержать минимум 10 символов"
        
        # ВАЖНО: Для сохранения нужен авторизованный пользователь
        # В контексте инструмента мы не имеем прямого доступа к текущему пользователю
        # Поэтому возвращаем структурированную информацию для пользователя
        
        return f"""Промпт готов к сохранению!

Название: {title}
Описание: {description or 'Не указано'}
Теги: {tag_names or 'Не указаны'}
Публичный: {'Да' if is_public else 'Нет'}

ВАЖНО: Для сохранения промпта в галерею необходимо:
1. Войти в систему (если еще не вошли)
2. Перейти в раздел "Галерея промптов"
3. Нажать "Создать промпт"
4. Вставить следующее содержимое:

=== НАЗВАНИЕ ===
{title}

=== ОПИСАНИЕ ===
{description or 'Не указано'}

=== СОДЕРЖИМОЕ ПРОМПТА ===
{prompt_content}

=== ТЕГИ ===
{tag_names or 'Не указаны'}

Или используй API напрямую через веб-интерфейс."""
        
    except Exception as e:
        logger.error(f"Ошибка в save_prompt_to_gallery: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Ошибка при сохранении промпта: {str(e)}"


class PromptTools:
    """Класс для группировки инструментов работы с промптами"""
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов для работы с промптами"""
        return [
            enhance_prompt,
            improve_existing_prompt,
            analyze_prompt_quality,
            save_prompt_to_gallery
        ]

