import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class PromptEnhancementAgent(BaseAgent):
    """Агент для улучшения и создания промптов"""
    
    def __init__(self):
        super().__init__(
            name="prompt_enhancement",
            description="Агент для создания и улучшения промптов для LLM"
        )
        
        self.capabilities = [
            "prompt_enhancement",
            "prompt_analysis",
            "prompt_optimization",
            "prompt_generation"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов на улучшение промптов"""
        try:
            logger.info(f"[PromptEnhancementAgent] Обработка запроса: {message[:100]}...")
            
            # Получаем ask_agent из контекста или импортируем
            try:
                from backend.agent_llm_svc import ask_agent
            except ModuleNotFoundError:
                from agent_llm_svc import ask_agent
            
            # Определяем тип запроса
            message_lower = message.lower()
            
            # Если это запрос на улучшение существующего промпта
            if any(keyword in message_lower for keyword in ["улучши", "оптимизируй", "сделай лучше", "enhance", "improve", "optimize"]):
                return await self._enhance_existing_prompt(message, context, ask_agent)
            
            # Если это запрос на анализ промпта
            elif any(keyword in message_lower for keyword in ["проанализируй", "оцени", "analyze", "evaluate", "review"]):
                return await self._analyze_prompt(message, context, ask_agent)
            
            # Иначе - создание нового промпта из описания
            else:
                return await self._create_prompt_from_description(message, context, ask_agent)
                
        except Exception as e:
            logger.error(f"Ошибка в PromptEnhancementAgent: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Произошла ошибка при обработке запроса: {str(e)}"
    
    async def _create_prompt_from_description(
        self, 
        description: str, 
        context: Dict[str, Any], 
        ask_agent
    ) -> str:
        """Создание качественного промпта из простого описания"""
        
        system_prompt = """Ты - эксперт по созданию эффективных промптов для языковых моделей.
Твоя задача - преобразовать простое описание пользователя в качественный, структурированный промпт.

ПРИНЦИПЫ СОЗДАНИЯ ХОРОШИХ ПРОМПТОВ:
1. Четкая роль и контекст: Определи роль AI и контекст задачи
2. Конкретные инструкции: Используй четкие, конкретные инструкции
3. Структурированный формат: Организуй промпт логически (роль, задача, формат ответа, примеры)
4. Ограничения и требования: Укажи формат ответа, длину, стиль
5. Примеры: Добавь примеры желаемого вывода, если уместно
6. Избегай двусмысленности: Будь максимально конкретным

ФОРМАТ ОТВЕТА:
Создай промпт в следующем формате:

=== УЛУЧШЕННЫЙ ПРОМПТ ===

[Здесь полный улучшенный промпт]

=== ОБЪЯСНЕНИЕ УЛУЧШЕНИЙ ===

1. Роль и контекст: [объяснение]
2. Ключевые улучшения: [список улучшений]
3. Рекомендации по использованию: [советы]

=== АЛЬТЕРНАТИВНЫЕ ВАРИАНТЫ ===

[Краткие варианты для разных сценариев, если применимо]

ВАЖНО: НЕ ПОВТОРЯЙ запрос пользователя в ответе. Сразу начинай с секции "=== УЛУЧШЕННЫЙ ПРОМПТ ===".
Создай промпт на русском языке, если описание на русском, и на английском, если описание на английском."""

        user_prompt = f"""Создай качественный промпт для LLM на основе следующего описания:

{description}

Создай структурированный, эффективный промпт. ВАЖНО: Не дублируй запрос пользователя, сразу начинай с улучшенного промпта."""

        logger.info("[PromptEnhancementAgent] Генерация улучшенного промпта...")
        
        # Получаем историю из контекста
        history = context.get("history", []) if context else []
        
        # Получаем параметры стриминга из tool_context (приоритет) или из context (fallback)
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        tool_context = get_tool_context()
        streaming = tool_context.get('streaming', context.get("streaming", False)) if tool_context else (context.get("streaming", False) if context else False)
        stream_callback = tool_context.get('stream_callback', context.get("stream_callback")) if tool_context else (context.get("stream_callback") if context else None)
        selected_model = tool_context.get('selected_model', context.get("selected_model")) if tool_context else (context.get("selected_model") if context else None)
        
        logger.info(f"[PromptEnhancementAgent] Стриминг: {'включен' if streaming else 'выключен'}")
        if streaming and stream_callback:
            logger.info(f"[PromptEnhancementAgent] Stream callback доступен: {type(stream_callback)}")
        
        # Включаем системный промпт в основной промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if selected_model:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        logger.info(f"[PromptEnhancementAgent] Получен ответ, длина: {len(response)} символов")
        return response
    
    async def _enhance_existing_prompt(
        self, 
        message: str, 
        context: Dict[str, Any], 
        ask_agent
    ) -> str:
        """Улучшение существующего промпта"""
        
        system_prompt = """Ты - эксперт по оптимизации промптов для языковых моделей.
Твоя задача - улучшить существующий промпт, сделав его более эффективным и структурированным.

ПРИНЦИПЫ УЛУЧШЕНИЯ:
1. Добавь четкую роль и контекст, если их нет
2. Сделай инструкции более конкретными и структурированными
3. Добавь формат ответа и ограничения
4. Улучши логическую структуру
5. Добавь примеры, если это поможет
6. Убери двусмысленности

ФОРМАТ ОТВЕТА:

=== УЛУЧШЕННЫЙ ПРОМПТ ===

[Улучшенная версия промпта]

=== ЧТО БЫЛО УЛУЧШЕНО ===

1. [Конкретное улучшение 1]
2. [Конкретное улучшение 2]
3. [И т.д.]

=== ОЖИДАЕМЫЙ РЕЗУЛЬТАТ ===

[Опиши, как улучшенный промпт повлияет на качество ответа]

ВАЖНО: НЕ ПОВТОРЯЙ исходный промпт пользователя в ответе. Сразу начинай с секции "=== УЛУЧШЕННЫЙ ПРОМПТ ==="."""

        user_prompt = f"""Улучши следующий промпт:

{message}

Проанализируй и создай улучшенную версию. ВАЖНО: Не дублируй исходный текст, сразу начинай с улучшенной версии."""

        logger.info("[PromptEnhancementAgent] Улучшение существующего промпта...")
        
        history = context.get("history", []) if context else []
        selected_model = context.get("selected_model") if context else None
        
        # Получаем параметры стриминга из контекста
        streaming = context.get("streaming", False) if context else False
        stream_callback = context.get("stream_callback") if context else None
        
        logger.info(f"[PromptEnhancementAgent] Стриминг: {'включен' if streaming else 'выключен'}")
        
        # Включаем системный промпт в основной промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if selected_model:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return response
    
    async def _analyze_prompt(
        self, 
        message: str, 
        context: Dict[str, Any], 
        ask_agent
    ) -> str:
        """Анализ качества промпта"""
        
        system_prompt = """Ты - эксперт по анализу промптов для языковых моделей.
Твоя задача - проанализировать промпт и дать конструктивную обратную связь.

КРИТЕРИИ ОЦЕНКИ:
1. Четкость роли и контекста (0-10)
2. Конкретность инструкций (0-10)
3. Структурированность (0-10)
4. Наличие формата ответа (0-10)
5. Отсутствие двусмысленностей (0-10)

ФОРМАТ ОТВЕТА:

=== АНАЛИЗ ПРОМПТА ===

ОБЩАЯ ОЦЕНКА: [X/10]

=== ДЕТАЛЬНАЯ ОЦЕНКА ===

1. Четкость роли и контекста: [X/10]
   - Сильные стороны: [список]
   - Слабые стороны: [список]

2. Конкретность инструкций: [X/10]
   - Сильные стороны: [список]
   - Слабые стороны: [список]

3. Структурированность: [X/10]
   - Сильные стороны: [список]
   - Слабые стороны: [список]

4. Формат ответа: [X/10]
   - Сильные стороны: [список]
   - Слабые стороны: [список]

5. Отсутствие двусмысленностей: [X/10]
   - Сильные стороны: [список]
   - Слабые стороны: [список]

=== РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ ===

1. [Конкретная рекомендация 1]
2. [Конкретная рекомендация 2]
3. [И т.д.]

ВАЖНО: НЕ ПОВТОРЯЙ анализируемый промпт в ответе. Сразу начинай с секции "=== АНАЛИЗ ПРОМПТА ==="."""

        user_prompt = f"""Проанализируй следующий промпт:

{message}

Оцени по критериям и дай рекомендации. ВАЖНО: Не дублируй текст промпта, сразу начинай с анализа."""

        logger.info("[PromptEnhancementAgent] Анализ промпта...")
        
        history = context.get("history", []) if context else []
        selected_model = context.get("selected_model") if context else None
        
        # Получаем параметры стриминга из контекста
        streaming = context.get("streaming", False) if context else False
        stream_callback = context.get("stream_callback") if context else None
        
        logger.info(f"[PromptEnhancementAgent] Стриминг: {'включен' if streaming else 'выключен'}")
        
        # Включаем системный промпт в основной промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if selected_model:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None,
                model_path=selected_model
            )
        else:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback if streaming else None
            )
        
        return response
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        
        prompt_keywords = [
            "промпт", "prompt", "создай промпт", "улучши промпт", 
            "оптимизируй промпт", "проанализируй промпт", "оцени промпт",
            "сделай промпт", "напиши промпт", "помоги с промптом",
            "как написать промпт", "как улучшить промпт", "создать промпт для",
            "enhance prompt", "improve prompt", "create prompt", "analyze prompt"
        ]
        
        return any(keyword in message_lower for keyword in prompt_keywords)

