"""
Расширенная система инструментов для astrachat
Включает специализированные инструменты для различных задач
"""

import os
import json
import requests
import subprocess
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime
from langchain_core.tools import tool
from backend.settings.logging import get_logger

logger = get_logger(__name__)

# ================================
# ИНСТРУМЕНТЫ ДЛЯ РАБОТЫ С ФАЙЛАМИ
# ================================

@tool
def read_file_content(file_path: str) -> str:
    """Чтение содержимого файла"""
    try:
        if not os.path.exists(file_path):
            return f"Файл {file_path} не найден"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return f"Содержимое файла {file_path}:\n{content}"
    except Exception as e:
        return f"Ошибка чтения файла: {str(e)}"

@tool
def write_file_content(file_path: str, content: str) -> str:
    """Запись содержимого в файл"""
    try:
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"Файл {file_path} успешно создан/обновлен"
    except Exception as e:
        return f"Ошибка записи файла: {str(e)}"

@tool
def list_directory_contents(directory_path: str) -> str:
    """Получение списка файлов и папок в директории"""
    try:
        if not os.path.exists(directory_path):
            return f"Директория {directory_path} не найдена"
        
        items = []
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                items.append(f"📁 {item}/")
            else:
                size = os.path.getsize(item_path)
                items.append(f"📄 {item} ({size} байт)")
        
        return f"Содержимое директории {directory_path}:\n" + "\n".join(items)
    except Exception as e:
        return f"Ошибка чтения директории: {str(e)}"

# ================================
# ИНСТРУМЕНТЫ ДЛЯ ВЕБ-ПОИСКА
# ================================

@tool
def search_web(query: str, num_results: int = 5) -> str:
    """Поиск информации в интернете"""
    try:
        # Используем DuckDuckGo для поиска (бесплатно, без API ключей)
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        
        # Добавляем основные результаты
        for result in data.get("Results", [])[:num_results]:
            results.append(f"• {result.get('Text', '')} - {result.get('FirstURL', '')}")
        
        # Добавляем связанные темы
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append(f"• {topic['Text']}")
        
        if results:
            return f"Результаты поиска по запросу '{query}':\n" + "\n".join(results)
        else:
            return f"По запросу '{query}' ничего не найдено"
            
    except Exception as e:
        logger.error(f"Ошибка веб-поиска: {e}")
        return f"Ошибка при поиске в интернете: {str(e)}"

@tool
def get_weather(city: str) -> str:
    """Получение информации о погоде"""
    try:
        # Используем OpenWeatherMap API (требует API ключ)
        # Для демонстрации возвращаем заглушку
        return f"Погода в городе {city}: [Интеграция с погодным API в разработке]"
    except Exception as e:
        return f"Ошибка получения погоды: {str(e)}"

# ================================
# ИНСТРУМЕНТЫ ДЛЯ ВЫЧИСЛЕНИЙ
# ================================

@tool
def calculate_expression(expression: str) -> str:
    """Безопасное вычисление математических выражений"""
    try:
        # Разрешенные функции и операции
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "sqrt": lambda x: x ** 0.5,
            "sin": lambda x: __import__("math").sin(x),
            "cos": lambda x: __import__("math").cos(x),
            "tan": lambda x: __import__("math").tan(x),
            "log": lambda x: __import__("math").log(x),
            "pi": 3.14159265359,
            "e": 2.71828182846
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

# ================================
# ИНСТРУМЕНТЫ ДЛЯ РАБОТЫ С ДАТАМИ
# ================================

@tool
def get_current_datetime() -> str:
    """Получение текущей даты и времени"""
    now = datetime.now()
    return f"Текущая дата и время: {now.strftime('%Y-%m-%d %H:%M:%S')}"

@tool
def calculate_date_difference(date1: str, date2: str) -> str:
    """Вычисление разности между двумя датами"""
    try:
        from datetime import datetime
        
        d1 = datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.strptime(date2, "%Y-%m-%d")
        
        diff = abs((d2 - d1).days)
        return f"Разность между {date1} и {date2}: {diff} дней"
        
    except Exception as e:
        return f"Ошибка вычисления разности дат: {str(e)}"

# ================================
# ИНСТРУМЕНТЫ ДЛЯ РАБОТЫ С СИСТЕМОЙ
# ================================

@tool
def execute_command(command: str) -> str:
    """Выполнение системной команды (с ограничениями безопасности)"""
    try:
        # Разрешенные команды
        allowed_commands = [
            "ls", "dir", "pwd", "whoami", "date", "uptime",
            "ps", "df", "free", "uname", "cat", "head", "tail"
        ]
        
        cmd_parts = command.split()
        if not cmd_parts or cmd_parts[0] not in allowed_commands:
            return f"Команда '{command}' не разрешена для выполнения"
        
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            return f"Результат выполнения '{command}':\n{result.stdout}"
        else:
            return f"Ошибка выполнения '{command}':\n{result.stderr}"
            
    except subprocess.TimeoutExpired:
        return f"Команда '{command}' превысила время выполнения"
    except Exception as e:
        return f"Ошибка выполнения команды: {str(e)}"

@tool
def get_system_info() -> str:
    """Получение информации о системе"""
    try:
        import platform
        import psutil
        
        info = {
            "Операционная система": platform.system(),
            "Версия": platform.version(),
            "Архитектура": platform.machine(),
            "Процессор": platform.processor(),
            "Память": f"{psutil.virtual_memory().total // (1024**3)} GB",
            "Диск": f"{psutil.disk_usage('/').total // (1024**3)} GB"
        }
        
        result = "Информация о системе:\n"
        for key, value in info.items():
            result += f"{key}: {value}\n"
        
        return result
        
    except Exception as e:
        return f"Ошибка получения информации о системе: {str(e)}"

# ================================
# ИНСТРУМЕНТЫ ДЛЯ РАБОТЫ С ДАННЫМИ
# ================================

@tool
def create_json_data(data: str) -> str:
    """Создание JSON структуры из текстового описания"""
    try:
        # Простой парсер для создания JSON
        # Это упрощенная версия, в реальности нужен более сложный парсер
        
        # Пример: "name: John, age: 30, city: Moscow"
        if ":" in data and "," in data:
            items = data.split(",")
            json_obj = {}
            for item in items:
                if ":" in item:
                    key, value = item.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Пытаемся определить тип значения
                    if value.isdigit():
                        json_obj[key] = int(value)
                    elif value.lower() in ["true", "false"]:
                        json_obj[key] = value.lower() == "true"
                    else:
                        json_obj[key] = value
            
            return f"JSON структура:\n{json.dumps(json_obj, indent=2, ensure_ascii=False)}"
        else:
            return "Не удалось распарсить данные в JSON формат"
            
    except Exception as e:
        return f"Ошибка создания JSON: {str(e)}"

@tool
def analyze_text(text: str) -> str:
    """Анализ текста (подсчет слов, символов, предложений)"""
    try:
        words = len(text.split())
        chars = len(text)
        chars_no_spaces = len(text.replace(" ", ""))
        sentences = len([s for s in text.split(".") if s.strip()])
        
        analysis = {
            "Количество слов": words,
            "Количество символов": chars,
            "Символов без пробелов": chars_no_spaces,
            "Количество предложений": sentences,
            "Средняя длина слова": round(chars_no_spaces / words, 2) if words > 0 else 0
        }
        
        result = "Анализ текста:\n"
        for key, value in analysis.items():
            result += f"{key}: {value}\n"
        
        return result
        
    except Exception as e:
        return f"Ошибка анализа текста: {str(e)}"

# ================================
# ЭКСПОРТ ВСЕХ ИНСТРУМЕНТОВ
# ================================

ADVANCED_TOOLS = [
    # Файловые операции
    read_file_content,
    write_file_content,
    list_directory_contents,
    
    # Веб-поиск
    search_web,
    get_weather,
    
    # Вычисления
    calculate_expression,
    convert_units,
    
    # Работа с датами
    get_current_datetime,
    calculate_date_difference,
    
    # Системные команды
    execute_command,
    get_system_info,
    
    # Работа с данными
    create_json_data,
    analyze_text,
]

def get_all_advanced_tools():
    """Получение всех расширенных инструментов"""
    return ADVANCED_TOOLS

