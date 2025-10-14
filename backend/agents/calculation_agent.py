"""
Агент для математических вычислений
"""

import logging
import re
import math
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class CalculationAgent(BaseAgent):
    """Агент для выполнения математических вычислений"""
    
    def __init__(self):
        super().__init__(
            name="calculation",
            description="Агент для выполнения математических вычислений"
        )
        
        self.capabilities = [
            "arithmetic", "algebra", "geometry", "statistics", "unit_conversion"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка математических запросов"""
        try:
            # Извлекаем математическое выражение
            expression = self._extract_expression(message)
            
            if not expression:
                return "Не удалось найти математическое выражение для вычисления. Пожалуйста, укажите выражение, например: '2 + 2' или '15 * 3'."
            
            # Выполняем вычисление
            result = self._calculate(expression)
            
            if result is None:
                return f"Не удалось вычислить выражение: {expression}. Проверьте правильность записи."
            
            # Формируем ответ
            response = f"**Результат вычисления:**\n\n"
            response += f"**Выражение:** {expression}\n"
            response += f"**Результат:** {result}\n\n"
            
            # Добавляем дополнительную информацию
            if isinstance(result, (int, float)):
                if result > 1000000:
                    response += f"**В научной нотации:** {result:.2e}\n"
                if isinstance(result, float) and result.is_integer():
                    response += f"**Целое число:** {int(result)}\n"
            
            # Добавляем рекомендации
            response += "\n**Рекомендации:**\n"
            response += "- Для сложных вычислений используйте скобки: (2 + 3) * 4\n"
            response += "- Доступны функции: sin, cos, tan, log, sqrt, pow\n"
            response += "- Для конвертации единиц: '100 см в метры'"
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка в CalculationAgent: {e}")
            return f"Произошла ошибка при вычислении: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        
        calculation_keywords = [
            "вычисли", "посчитай", "математика", "формула", "расчет",
            "сложить", "умножить", "разделить", "вычесть", "сколько будет",
            "результат", "ответ", "конвертация", "единицы измерения"
        ]
        
        # Проверяем наличие математических символов
        math_symbols = ['+', '-', '*', '/', '=', '(', ')', '^', '**']
        has_math_symbols = any(symbol in message for symbol in math_symbols)
        
        # Проверяем наличие чисел
        has_numbers = bool(re.search(r'\d+', message))
        
        return (any(keyword in message_lower for keyword in calculation_keywords) or 
                (has_math_symbols and has_numbers))
    
    def _extract_expression(self, message: str) -> str:
        """Извлечение математического выражения из сообщения"""
        # Убираем служебные слова
        stop_words = [
            "вычисли", "посчитай", "сколько будет", "результат", "ответ",
            "математика", "формула", "расчет"
        ]
        
        expression = message
        for stop_word in stop_words:
            expression = expression.replace(stop_word, "").strip()
        
        # Ищем математические выражения
        math_pattern = r'[\d\+\-\*\/\(\)\.\s\^]+'
        matches = re.findall(math_pattern, expression)
        
        if matches:
            # Берем самое длинное совпадение
            return max(matches, key=len).strip()
        
        return expression if any(c in expression for c in '+-*/()^') else ""
    
    def _calculate(self, expression: str) -> Any:
        """Безопасное выполнение математических вычислений"""
        try:
            # Очищаем выражение
            expression = expression.strip()
            
            # Заменяем ^ на ** для возведения в степень
            expression = expression.replace('^', '**')
            
            # Разрешенные функции и константы
            allowed_names = {
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "pow": pow, "sqrt": lambda x: x ** 0.5,
                "sin": lambda x: math.sin(x), "cos": lambda x: math.cos(x),
                "tan": lambda x: math.tan(x), "log": lambda x: math.log(x),
                "pi": math.pi, "e": math.e
            }
            
            # Проверяем безопасность выражения
            code = compile(expression, "<string>", "eval")
            for name in code.co_names:
                if name not in allowed_names:
                    logger.warning(f"Недопустимая функция: {name}")
                    return None
            
            # Выполняем вычисление
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return result
            
        except Exception as e:
            logger.error(f"Ошибка вычисления: {e}")
            return None

