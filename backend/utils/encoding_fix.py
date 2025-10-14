"""
Утилита для исправления проблем с кодировкой в Windows
"""

import sys
import os
import logging

def fix_windows_encoding():
    """Исправляет проблемы с кодировкой в Windows"""
    if sys.platform == "win32":
        try:
            # Устанавливаем UTF-8 кодировку для консоли Windows
            os.system("chcp 65001 >nul 2>&1")
            
            # Настраиваем stdout и stderr для корректного отображения русских символов
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')
            
            # Настраиваем кодировку для всех обработчиков логирования
            for handler in logging.root.handlers:
                if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
                    handler.stream.reconfigure(encoding='utf-8')
            
            print("Кодировка Windows настроена на UTF-8")
            return True
            
        except Exception as e:
            print(f"Ошибка настройки кодировки: {e}")
            return False
    
    return True

def safe_print(text: str):
    """Безопасный вывод текста с правильной кодировкой"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Если не удается вывести с UTF-8, пробуем ASCII
        print(text.encode('ascii', 'ignore').decode('ascii'))

def safe_log(logger, level: str, message: str):
    """Безопасное логирование с правильной кодировкой"""
    try:
        if level.upper() == 'INFO':
            logger.info(message)
        elif level.upper() == 'DEBUG':
            logger.debug(message)
        elif level.upper() == 'WARNING':
            logger.warning(message)
        elif level.upper() == 'ERROR':
            logger.error(message)
        else:
            logger.info(message)
    except UnicodeEncodeError:
        # Если не удается залогировать с UTF-8, пробуем ASCII
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        logger.info(safe_message)


