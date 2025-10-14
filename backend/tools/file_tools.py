"""
Инструменты для работы с файлами
"""

import os
import json
from typing import Dict, List, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

class FileTools:
    """Класс с инструментами для работы с файлами"""
    
    @staticmethod
    @tool
    def read_file(file_path: str) -> str:
        """Чтение содержимого файла"""
        try:
            if not os.path.exists(file_path):
                return f"Файл {file_path} не найден"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return f"Содержимое файла {file_path}:\n{content}"
        except Exception as e:
            return f"Ошибка чтения файла: {str(e)}"
    
    @staticmethod
    @tool
    def write_file(file_path: str, content: str) -> str:
        """Запись содержимого в файл"""
        try:
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return f"Файл {file_path} успешно создан/обновлен"
        except Exception as e:
            return f"Ошибка записи файла: {str(e)}"
    
    @staticmethod
    @tool
    def list_directory(directory_path: str) -> str:
        """Получение списка файлов и папок в директории"""
        try:
            if not os.path.exists(directory_path):
                return f"Директория {directory_path} не найдена"
            
            items = []
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                if os.path.isdir(item_path):
                    items.append(f"{item}/")
                else:
                    size = os.path.getsize(item_path)
                    items.append(f"{item} ({size} байт)")
            
            return f"Содержимое директории {directory_path}:\n" + "\n".join(items)
        except Exception as e:
            return f"Ошибка чтения директории: {str(e)}"
    
    @staticmethod
    @tool
    def get_file_info(file_path: str) -> str:
        """Получение информации о файле"""
        try:
            if not os.path.exists(file_path):
                return f"Файл {file_path} не найден"
            
            stat = os.stat(file_path)
            info = {
                "Размер": f"{stat.st_size} байт",
                "Создан": stat.st_ctime,
                "Изменен": stat.st_mtime,
                "Тип": "Папка" if os.path.isdir(file_path) else "Файл"
            }
            
            result = f"Информация о файле {file_path}:\n"
            for key, value in info.items():
                result += f"{key}: {value}\n"
            
            return result
        except Exception as e:
            return f"Ошибка получения информации о файле: {str(e)}"
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов класса"""
        return [
            FileTools.read_file,
            FileTools.write_file,
            FileTools.list_directory,
            FileTools.get_file_info
        ]

