"""
Агент PromptEngineer - специализированный агент для создания и улучшения промптов
Использует инструменты для работы с промптами и LLM для генерации качественных промптов
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class PromptEngineer(BaseAgent):
    """Специализированный агент для инженерии промптов"""
    
    def __init__(self):
        super().__init__(
            name="prompt_engineer",
            description="Специализированный агент для создания, улучшения и анализа промптов для LLM"
        )
        
        self.capabilities = [
            "prompt_creation",
            "prompt_enhancement",
            "prompt_optimization",
            "prompt_analysis",
            "prompt_engineering"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов на работу с промптами"""
        try:
            logger.info(f"[PromptEngineer] Обработка запроса: {message[:100]}...")
            
            # Получаем ask_agent из контекста или импортируем
            try:
                from backend.agent_llm_svc import ask_agent
            except ModuleNotFoundError:
                from agent_llm_svc import ask_agent
            
            # Определяем тип запроса и используем соответствующий подход
            message_lower = message.lower()
            
            # Если это запрос на улучшение существующего промпта
            if any(keyword in message_lower for keyword in ["улучши", "оптимизируй", "сделай лучше", "enhance", "improve", "optimize"]):
                return await self._enhance_prompt(message, context, ask_agent)
            
            # Если это запрос на анализ промпта
            elif any(keyword in message_lower for keyword in ["проанализируй", "оцени", "analyze", "evaluate", "review", "качество"]):
                return await self._analyze_prompt(message, context, ask_agent)
            
            # Если это запрос на сохранение
            elif any(keyword in message_lower for keyword in ["сохрани", "добавь в галерею", "save", "add to gallery"]):
                return await self._save_prompt(message, context, ask_agent)
            
            # Иначе - создание нового промпта из описания
            else:
                return await self._create_prompt(message, context, ask_agent)
                
        except Exception as e:
            logger.error(f"Ошибка в PromptEngineer: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Произошла ошибка при обработке запроса: {str(e)}"
    
    async def _create_prompt(
        self, 
        description: str, 
        context: Dict[str, Any], 
        ask_agent
    ) -> str:
        """Создание качественного промпта из простого описания"""
        
        system_prompt = """Ты - эксперт по инженерии промптов (Prompt Engineering) для языковых моделей.
Твоя задача - преобразовать простое описание пользователя в профессиональный, структурированный промпт.

ПРИНЦИПЫ СОЗДАНИЯ ЭФФЕКТИВНЫХ ПРОМПТОВ:

1. ЧЕТКАЯ РОЛЬ И КОНТЕКСТ
   - Определи роль AI (эксперт, ассистент, аналитик и т.д.)
   - Установи контекст задачи
   - Укажи область знаний

2. КОНКРЕТНЫЕ ИНСТРУКЦИИ
   - Используй четкие, однозначные команды
   - Избегай двусмысленностей
   - Разбей сложные задачи на шаги

3. СТРУКТУРИРОВАННЫЙ ФОРМАТ
   - Организуй промпт логически
   - Используй разделы и подразделы
   - Применяй форматирование для читаемости

4. ОГРАНИЧЕНИЯ И ТРЕБОВАНИЯ
   - Укажи формат ответа (JSON, список, таблица и т.д.)
   - Определи длину ответа
   - Задай стиль (формальный, неформальный, технический)

5. ПРИМЕРЫ И ШАБЛОНЫ
   - Добавь примеры желаемого вывода
   - Покажи паттерны, если уместно
   - Демонстрируй ожидаемый формат

6. ОБРАБОТКА ОШИБОК
   - Укажи, что делать при недостатке информации
   - Определи поведение при неоднозначности
   - Задай правила для edge cases

ФОРМАТ ОТВЕТА:

=== УЛУЧШЕННЫЙ ПРОМПТ ===

[Здесь полный улучшенный промпт, готовый к использованию]

=== ОБЪЯСНЕНИЕ УЛУЧШЕНИЙ ===

1. Роль и контекст: [объяснение выбранной роли и контекста]
2. Ключевые улучшения: [список конкретных улучшений]
3. Структура: [объяснение структуры промпта]
4. Рекомендации по использованию: [советы по применению]

=== АЛЬТЕРНАТИВНЫЕ ВАРИАНТЫ ===

[Краткие варианты для разных сценариев, если применимо]

=== МЕТРИКИ КАЧЕСТВА ===

- Четкость: [оценка]
- Конкретность: [оценка]
- Структурированность: [оценка]
- Полнота: [оценка]

Создай промпт на том же языке, что и описание пользователя."""

        user_prompt = f"""Создай профессиональный, эффективный промпт для LLM на основе следующего описания:

ОПИСАНИЕ ЗАДАЧИ:
{description}

Создай структурированный, оптимизированный промпт, который поможет получить наилучший результат от LLM. 
Примени все принципы инженерии промптов."""

        logger.info("[PromptEngineer] Генерация улучшенного промпта...")
        
        # Получаем историю из контекста
        history = context.get("history", []) if context else []
        
        # Получаем выбранную модель
        selected_model = context.get("selected_model") if context else None
        
        # Включаем системный промпт в основной промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if selected_model:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=False,
                model_path=selected_model
            )
        else:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=False
            )
        
        logger.info(f"[PromptEngineer] Получен ответ, длина: {len(response)} символов")
        return response
    
    async def _enhance_prompt(
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
7. Оптимизируй для лучших результатов

ФОРМАТ ОТВЕТА:

=== УЛУЧШЕННЫЙ ПРОМПТ ===

[Улучшенная версия промпта, готовая к использованию]

=== ЧТО БЫЛО УЛУЧШЕНО ===

1. [Конкретное улучшение 1 с объяснением]
2. [Конкретное улучшение 2 с объяснением]
3. [И т.д.]

=== СРАВНЕНИЕ ===

ДО:
[Ключевые проблемы оригинального промпта]

ПОСЛЕ:
[Ключевые преимущества улучшенного промпта]

=== ОЖИДАЕМЫЙ РЕЗУЛЬТАТ ===

[Опиши, как улучшенный промпт повлияет на качество ответа]"""

        # Извлекаем промпт из сообщения
        prompt_text = self._extract_prompt_from_message(message)
        
        user_prompt = f"""Улучши следующий промпт, сделав его более эффективным:

ОРИГИНАЛЬНЫЙ ПРОМПТ:
{prompt_text}

Проанализируй промпт и создай улучшенную версию с детальным объяснением всех изменений."""

        logger.info("[PromptEngineer] Улучшение существующего промпта...")
        
        history = context.get("history", []) if context else []
        selected_model = context.get("selected_model") if context else None
        
        # Включаем системный промпт в основной промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if selected_model:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=False,
                model_path=selected_model
            )
        else:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=False
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
Твоя задача - проанализировать промпт и дать детальную, конструктивную обратную связь.

КРИТЕРИИ ОЦЕНКИ (0-10):
1. Четкость роли и контекста
2. Конкретность инструкций
3. Структурированность
4. Наличие формата ответа
5. Отсутствие двусмысленностей
6. Полнота информации
7. Применимость примеров
8. Обработка edge cases

ФОРМАТ ОТВЕТА:

=== АНАЛИЗ ПРОМПТА ===

ОБЩАЯ ОЦЕНКА: [X/10]
УРОВЕНЬ: [Начинающий/Средний/Продвинутый/Экспертный]

=== ДЕТАЛЬНАЯ ОЦЕНКА ===

1. Четкость роли и контекста: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

2. Конкретность инструкций: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

3. Структурированность: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

4. Формат ответа: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

5. Отсутствие двусмысленностей: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

6. Полнота информации: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

7. Применимость примеров: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

8. Обработка edge cases: [X/10]
   Сильные стороны: [список]
   Слабые стороны: [список]

=== РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ ===

1. [Конкретная рекомендация 1 с примером]
2. [Конкретная рекомендация 2 с примером]
3. [И т.д.]

=== ПРИОРИТЕТЫ ===

Критично: [что нужно исправить в первую очередь]
Важно: [что стоит улучшить]
Желательно: [что можно добавить для совершенства]"""

        # Извлекаем промпт из сообщения
        prompt_text = self._extract_prompt_from_message(message)
        
        user_prompt = f"""Проанализируй следующий промпт и дай детальную оценку:

ПРОМПТ ДЛЯ АНАЛИЗА:
{prompt_text}

Оцени промпт по всем критериям и дай конструктивные рекомендации по улучшению."""

        logger.info("[PromptEngineer] Анализ промпта...")
        
        history = context.get("history", []) if context else []
        selected_model = context.get("selected_model") if context else None
        
        # Включаем системный промпт в основной промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        if selected_model:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=False,
                model_path=selected_model
            )
        else:
            response = ask_agent(
                full_prompt,
                history=[],
                streaming=False
            )
        
        return response
    
    async def _save_prompt(
        self, 
        message: str, 
        context: Dict[str, Any], 
        ask_agent
    ) -> str:
        """Помощь в сохранении промпта"""
        
        return """Для сохранения промпта в галерею:

1. Перейди в раздел "Галерея промптов"
2. Нажми кнопку "Создать промпт"
3. Заполни форму:
   - Название промпта
   - Описание
   - Содержимое промпта
   - Теги (опционально)
4. Выбери видимость (публичный/приватный)
5. Сохрани

Или используй инструмент save_prompt_to_gallery для автоматического сохранения."""
    
    def _extract_prompt_from_message(self, message: str) -> str:
        """Извлечение текста промпта из сообщения"""
        # Пытаемся найти промпт в кавычках
        import re
        
        # Ищем текст в кавычках
        quoted = re.findall(r'["""](.*?)["""]', message, re.DOTALL)
        if quoted:
            return quoted[0].strip()
        
        # Ищем текст после ключевых слов
        keywords = ["промпт:", "prompt:", "текст:", "содержимое:"]
        for keyword in keywords:
            if keyword.lower() in message.lower():
                parts = message.split(keyword, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        
        # Если ничего не найдено, возвращаем все сообщение
        return message.strip()
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        
        prompt_keywords = [
            "промпт", "prompt", "создай промпт", "улучши промпт", 
            "оптимизируй промпт", "проанализируй промпт", "оцени промпт",
            "сделай промпт", "напиши промпт", "помоги с промптом",
            "как написать промпт", "как улучшить промпт", "создать промпт для",
            "enhance prompt", "improve prompt", "create prompt", "analyze prompt",
            "prompt engineering", "инженерия промптов", "инженер промптов",
            "prompt engineer", "помощь с промптом", "help with prompt"
        ]
        
        return any(keyword in message_lower for keyword in prompt_keywords)

