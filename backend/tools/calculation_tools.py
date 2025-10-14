"""
Инструменты для математических вычислений
"""

import math
import re
from typing import Dict, List, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

class CalculationTools:
    """Класс с инструментами для вычислений"""
    
    @staticmethod
    @tool
    def calculate_expression(expression: str) -> str:
        """Безопасное вычисление математических выражений"""
        try:
            # Разрешенные функции и операции
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
                    return f"Ошибка: недопустимая функция '{name}'"
            
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return f"Результат: {result}"
            
        except Exception as e:
            return f"Ошибка вычисления: {str(e)}"
    
    @staticmethod
    @tool
    def convert_units(value: float, from_unit: str, to_unit: str) -> str:
        """Конвертация единиц измерения"""
        try:
            # Простые конвертации
            conversions = {
                # Длина
                ("m", "cm"): lambda x: x * 100,
                ("cm", "m"): lambda x: x / 100,
                ("km", "m"): lambda x: x * 1000,
                ("m", "km"): lambda x: x / 1000,
                
                # Вес
                ("kg", "g"): lambda x: x * 1000,
                ("g", "kg"): lambda x: x / 1000,
                ("lb", "kg"): lambda x: x * 0.453592,
                ("kg", "lb"): lambda x: x / 0.453592,
                
                # Температура
                ("c", "f"): lambda x: x * 9/5 + 32,
                ("f", "c"): lambda x: (x - 32) * 5/9,
                ("c", "k"): lambda x: x + 273.15,
                ("k", "c"): lambda x: x - 273.15,
            }
            
            key = (from_unit.lower(), to_unit.lower())
            if key in conversions:
                result = conversions[key](value)
                return f"{value} {from_unit} = {result} {to_unit}"
            else:
                return f"Конвертация из {from_unit} в {to_unit} не поддерживается"
                
        except Exception as e:
            return f"Ошибка конвертации: {str(e)}"
    
    @staticmethod
    @tool
    def calculate_percentage(part: float, whole: float) -> str:
        """Вычисление процента"""
        try:
            if whole == 0:
                return "Ошибка: деление на ноль"
            
            percentage = (part / whole) * 100
            return f"{part} от {whole} составляет {percentage:.2f}%"
        except Exception as e:
            return f"Ошибка вычисления процента: {str(e)}"
    
    @staticmethod
    @tool
    def calculate_area(shape: str, **kwargs) -> str:
        """Вычисление площади геометрических фигур"""
        try:
            shape = shape.lower()
            
            if shape == "rectangle" and "length" in kwargs and "width" in kwargs:
                area = kwargs["length"] * kwargs["width"]
                return f"Площадь прямоугольника: {area}"
            
            elif shape == "circle" and "radius" in kwargs:
                area = math.pi * kwargs["radius"] ** 2
                return f"Площадь круга: {area:.2f}"
            
            elif shape == "triangle" and "base" in kwargs and "height" in kwargs:
                area = 0.5 * kwargs["base"] * kwargs["height"]
                return f"Площадь треугольника: {area}"
            
            else:
                return "Недостаточно параметров для вычисления площади"
                
        except Exception as e:
            return f"Ошибка вычисления площади: {str(e)}"
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов класса"""
        return [
            CalculationTools.calculate_expression,
            CalculationTools.convert_units,
            CalculationTools.calculate_percentage,
            CalculationTools.calculate_area
        ]

