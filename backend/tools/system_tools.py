"""
Инструменты для работы с системой
"""

import subprocess
import platform
import psutil
from datetime import datetime
from typing import Dict, List, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

class SystemTools:
    """Класс с инструментами для работы с системой"""
    
    @staticmethod
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
    
    @staticmethod
    @tool
    def get_system_info() -> str:
        """Получение информации о системе"""
        try:
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
    
    @staticmethod
    @tool
    def get_current_datetime() -> str:
        """Получение текущей даты и времени"""
        now = datetime.now()
        return f"Текущая дата и время: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @staticmethod
    @tool
    def get_memory_usage() -> str:
        """Получение информации об использовании памяти"""
        try:
            memory = psutil.virtual_memory()
            return f"""Использование памяти:
Всего: {memory.total // (1024**3)} GB
Использовано: {memory.used // (1024**3)} GB
Свободно: {memory.available // (1024**3)} GB
Процент использования: {memory.percent}%"""
        except Exception as e:
            return f"Ошибка получения информации о памяти: {str(e)}"
    
    @staticmethod
    @tool
    def get_disk_usage() -> str:
        """Получение информации об использовании диска"""
        try:
            disk = psutil.disk_usage('/')
            return f"""Использование диска:
Всего: {disk.total // (1024**3)} GB
Использовано: {disk.used // (1024**3)} GB
Свободно: {disk.free // (1024**3)} GB
Процент использования: {(disk.used / disk.total) * 100:.1f}%"""
        except Exception as e:
            return f"Ошибка получения информации о диске: {str(e)}"
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов класса"""
        return [
            SystemTools.execute_command,
            SystemTools.get_system_info,
            SystemTools.get_current_datetime,
            SystemTools.get_memory_usage,
            SystemTools.get_disk_usage
        ]

