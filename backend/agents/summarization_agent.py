"""
Агент для суммаризации текстов и документов

Умеет:
1. Создавать краткое резюме текста из чата
2. Суммаризировать документы
3. Извлекать ключевую информацию
4. Создавать различные виды саммари (executive summary, bullets, highlights)
"""

import logging
from typing import Dict, Any, Optional, List
from .base_agent import get_ask_agent

logger = logging.getLogger("Backend")

class SummarizationAgent:
    """Агент для суммаризации текстов и документов"""
    
    def __init__(self):
        self.name = "SummarizationAgent"
        self.description = "Агент для создания саммари текстов, документов и извлечения ключевой информации"
        
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """
        Обрабатывает запрос на суммаризацию
        
        Args:
            message: Запрос пользователя
            context: Контекст с историей, документами и настройками
            
        Returns:
            Результат суммаризации
        """
        if context is None:
            context = {}
            
        logger.info(f"[{self.name}] Обработка запроса: {message[:100]}...")
        
        # Получаем параметры стриминга из контекста
        streaming = context.get('streaming', False)
        stream_callback = context.get('stream_callback')
        
        logger.info(f"[{self.name}] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[{self.name}] Stream callback доступен: {type(stream_callback)}")
        
        # Определяем тип суммаризации на основе запроса
        summarization_type = self._determine_summarization_type(message)
        logger.info(f"[{self.name}] Тип суммаризации: {summarization_type}")
        
        # Выполняем суммаризацию в зависимости от типа
        if summarization_type == "document":
            result = await self._summarize_document(message, context)
        elif summarization_type == "chat_history":
            result = await self._summarize_chat_history(message, context)
        elif summarization_type == "key_info":
            result = await self._extract_key_information(message, context)
        elif summarization_type == "bullets":
            result = await self._create_bullet_summary(message, context)
        else:
            # По умолчанию - общая суммаризация
            result = await self._create_general_summary(message, context)
            
        logger.info(f"[{self.name}] Суммаризация завершена, длина результата: {len(result)} символов")
        return result
    
    def _determine_summarization_type(self, message: str) -> str:
        """Определяет тип суммаризации на основе запроса"""
        message_lower = message.lower()
        
        # Проверяем упоминание документов
        if any(word in message_lower for word in ['документ', 'файл', 'doc', 'pdf', 'прикрепленный']):
            return "document"
        
        # Проверяем запросы на извлечение ключевой информации
        if any(word in message_lower for word in ['ключев', 'важн', 'главн', 'основн', 'highlights', 'key']):
            return "key_info"
        
        # Проверяем запросы на список пунктов
        if any(word in message_lower for word in ['список', 'пункт', 'bullets', 'тезис']):
            return "bullets"
        
        # Проверяем запросы на саммари истории чата
        if any(word in message_lower for word in ['чат', 'разговор', 'диалог', 'беседа', 'история']):
            return "chat_history"
        
        # По умолчанию - общая суммаризация
        return "general"
    
    async def _summarize_document(self, message: str, context: Dict[str, Any]) -> str:
        """Создает саммари документа"""
        logger.info(f"[{self.name}] Создание саммари документа...")
        
        # Получаем doc_processor из контекста
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        doc_processor = tool_context.get("doc_processor")
        
        if not doc_processor or not doc_processor.doc_names:
            return "Ошибка: Нет прикрепленных документов для суммаризации. Пожалуйста, загрузите документ."
        
        # Получаем содержимое документа
        doc_content = doc_processor.get_all_text()
        if not doc_content:
            return "Ошибка: Не удалось прочитать содержимое документа."
        
        # Определяем уровень детализации
        detail_level = "medium"
        if any(word in message.lower() for word in ['кратк', 'короткий', 'brief']):
            detail_level = "short"
        elif any(word in message.lower() for word in ['подробн', 'детальн', 'detailed']):
            detail_level = "detailed"
        
        # Формируем промпт для LLM
        system_prompt = f"""Ты - эксперт по суммаризации текстов. Твоя задача - создать качественное саммари документа.

ВАЖНО:
- Начинай СРАЗУ с саммари, без повторения запроса пользователя
- Сохраняй ключевую информацию и важные детали
- Структурируй текст для удобного восприятия
- Уровень детализации: {detail_level}

Документ: {doc_processor.doc_names[0]}
Длина документа: {len(doc_content)} символов"""

        user_prompt = f"""Создай саммари следующего документа:

{doc_content[:15000]}  # Ограничиваем длину для контекста

Требования пользователя: {message}"""

        # Вызываем LLM со стримингом
        # Получаем параметры стриминга из tool_context (приоритет) или из context (fallback)
        streaming = tool_context.get('streaming', context.get('streaming', False)) if tool_context else context.get('streaming', False)
        stream_callback = tool_context.get('stream_callback', context.get('stream_callback')) if tool_context else context.get('stream_callback')
        selected_model = tool_context.get('selected_model', context.get('selected_model')) if tool_context else context.get('selected_model')
        
        logger.info(f"[{self.name}] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[{self.name}] Stream callback доступен: {type(stream_callback)}")
        
        # Объединяем system_prompt и user_prompt в один prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        ask_agent = get_ask_agent()
        
        if selected_model:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return result
    
    async def _summarize_chat_history(self, message: str, context: Dict[str, Any]) -> str:
        """Создает саммари истории чата"""
        logger.info(f"[{self.name}] Создание саммари истории чата...")
        
        # Получаем историю из контекста
        history = context.get('history', [])
        
        if not history or len(history) < 2:
            return "История чата пуста или слишком короткая для суммаризации."
        
        # Формируем текст истории
        chat_text = "\n\n".join([
            f"{'Пользователь' if msg.get('role') == 'user' else 'Ассистент'}: {msg.get('content', '')}"
            for msg in history[-20:]  # Последние 20 сообщений
        ])
        
        # Формируем промпт для LLM
        system_prompt = """Ты - эксперт по суммаризации диалогов. Твоя задача - создать краткое резюме беседы.

ВАЖНО:
- Начинай СРАЗУ с резюме, без повторения запроса
- Выдели основные темы и вопросы
- Укажи ключевые выводы и решения
- Сохрани важные детали и договоренности"""

        user_prompt = f"""Создай саммари следующего диалога:

{chat_text}

Требования: {message}"""

        # Вызываем LLM со стримингом
        # Получаем параметры стриминга из tool_context (приоритет) или из context (fallback)
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        streaming = tool_context.get('streaming', context.get('streaming', False)) if tool_context else context.get('streaming', False)
        stream_callback = tool_context.get('stream_callback', context.get('stream_callback')) if tool_context else context.get('stream_callback')
        selected_model = tool_context.get('selected_model', context.get('selected_model')) if tool_context else context.get('selected_model')
        
        logger.info(f"[{self.name}] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[{self.name}] Stream callback доступен: {type(stream_callback)}")
        
        # Объединяем system_prompt и user_prompt в один prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        ask_agent = get_ask_agent()
        
        if selected_model:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return result
    
    async def _extract_key_information(self, message: str, context: Dict[str, Any]) -> str:
        """Извлекает ключевую информацию"""
        logger.info(f"[{self.name}] Извлечение ключевой информации...")
        
        # Определяем источник: документ или история чата
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        doc_processor = tool_context.get("doc_processor")
        
        # Приоритет документу, если есть
        if doc_processor and doc_processor.doc_names:
            source_text = doc_processor.get_all_text()[:15000]
            source_type = "документа"
        else:
            # Используем историю чата
            history = context.get('history', [])
            source_text = "\n".join([msg.get('content', '') for msg in history[-10:]])
            source_type = "диалога"
        
        if not source_text:
            return "Нет текста для анализа."
        
        # Формируем промпт для LLM
        system_prompt = f"""Ты - эксперт по извлечению ключевой информации. Твоя задача - найти и выделить самое важное.

ВАЖНО:
- Начинай СРАЗУ с ключевой информации, без повторения запроса
- Выдели основные факты, цифры, даты, имена
- Структурируй информацию по категориям
- Используй маркированные списки для удобства"""

        user_prompt = f"""Извлеки ключевую информацию из следующего {source_type}:

{source_text}

Дополнительные требования: {message}"""

        # Вызываем LLM со стримингом
        # Получаем параметры стриминга из tool_context (приоритет) или из context (fallback)
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        streaming = tool_context.get('streaming', context.get('streaming', False)) if tool_context else context.get('streaming', False)
        stream_callback = tool_context.get('stream_callback', context.get('stream_callback')) if tool_context else context.get('stream_callback')
        selected_model = tool_context.get('selected_model', context.get('selected_model')) if tool_context else context.get('selected_model')
        
        logger.info(f"[{self.name}] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[{self.name}] Stream callback доступен: {type(stream_callback)}")
        
        # Объединяем system_prompt и user_prompt в один prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        ask_agent = get_ask_agent()
        
        if selected_model:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return result
    
    async def _create_bullet_summary(self, message: str, context: Dict[str, Any]) -> str:
        """Создает саммари в виде списка пунктов"""
        logger.info(f"[{self.name}] Создание саммари в виде списка...")
        
        # Определяем источник: документ или история чата
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        doc_processor = tool_context.get("doc_processor")
        
        if doc_processor and doc_processor.doc_names:
            source_text = doc_processor.get_all_text()[:15000]
            source_type = "документа"
        else:
            history = context.get('history', [])
            source_text = "\n".join([msg.get('content', '') for msg in history[-10:]])
            source_type = "диалога"
        
        if not source_text:
            return "Нет текста для создания саммари."
        
        # Формируем промпт для LLM
        system_prompt = f"""Ты - эксперт по структурированию информации. Твоя задача - создать краткое саммари в виде списка.

ВАЖНО:
- Начинай СРАЗУ со списка, без повторения запроса
- Используй маркированный список (•) или нумерованный (1. 2. 3.)
- Каждый пункт должен быть кратким и информативным
- Группируй связанную информацию"""

        user_prompt = f"""Создай краткое саммари в виде списка основных пунктов из следующего {source_type}:

{source_text}

Требования: {message}"""

        # Вызываем LLM со стримингом
        # Получаем параметры стриминга из tool_context (приоритет) или из context (fallback)
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        streaming = tool_context.get('streaming', context.get('streaming', False)) if tool_context else context.get('streaming', False)
        stream_callback = tool_context.get('stream_callback', context.get('stream_callback')) if tool_context else context.get('stream_callback')
        selected_model = tool_context.get('selected_model', context.get('selected_model')) if tool_context else context.get('selected_model')
        
        logger.info(f"[{self.name}] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[{self.name}] Stream callback доступен: {type(stream_callback)}")
        
        # Объединяем system_prompt и user_prompt в один prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        ask_agent = get_ask_agent()
        
        if selected_model:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return result
    
    async def _create_general_summary(self, message: str, context: Dict[str, Any]) -> str:
        """Создает общее саммари"""
        logger.info(f"[{self.name}] Создание общего саммари...")
        
        # Определяем источник: документ или история чата
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        doc_processor = tool_context.get("doc_processor")
        
        if doc_processor and doc_processor.doc_names:
            source_text = doc_processor.get_all_text()[:15000]
            source_type = "документа"
            source_name = doc_processor.doc_names[0]
        else:
            history = context.get('history', [])
            source_text = "\n".join([msg.get('content', '') for msg in history[-15:]])
            source_type = "диалога"
            source_name = "чат"
        
        if not source_text:
            return "Нет текста для суммаризации."
        
        # Формируем промпт для LLM
        system_prompt = f"""Ты - эксперт по суммаризации текстов. Твоя задача - создать качественное общее саммари.

ВАЖНО:
- Начинай СРАЗУ с саммари, без повторения запроса пользователя
- Сохрани ключевую информацию и контекст
- Структурируй текст для удобного чтения
- Используй абзацы и подзаголовки при необходимости"""

        user_prompt = f"""Создай саммари следующего {source_type} ({source_name}):

{source_text}

Запрос пользователя: {message}"""

        # Вызываем LLM со стримингом
        # Получаем параметры стриминга из tool_context (приоритет) или из context (fallback)
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        streaming = tool_context.get('streaming', context.get('streaming', False)) if tool_context else context.get('streaming', False)
        stream_callback = tool_context.get('stream_callback', context.get('stream_callback')) if tool_context else context.get('stream_callback')
        selected_model = tool_context.get('selected_model', context.get('selected_model')) if tool_context else context.get('selected_model')
        
        logger.info(f"[{self.name}] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[{self.name}] Stream callback доступен: {type(stream_callback)}")
        
        # Объединяем system_prompt и user_prompt в один prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        ask_agent = get_ask_agent()
        
        if selected_model:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            result = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return result

