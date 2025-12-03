"""
Конфигурация для astrachat Backend
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Глобальная переменная для хранения конфигурации
_config: Optional[Dict[str, Any]] = None

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Загрузка конфигурации из YAML файла"""
    global _config
    
    if _config is not None:
        return _config
    
    if config_path is None:
        # Поиск config.yml в различных возможных местах
        possible_paths = [
            "config/config.yml",
            "../config/config.yml", 
            "./config.yml",
            Path(__file__).parent / "config.yml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        else:
            # Если файл не найден, используем значения по умолчанию
            _config = get_default_config()
            return _config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            _config = yaml.safe_load(f) or {}
            
        # Заполняем значения по умолчанию для отсутствующих ключей
        default_config = get_default_config()
        _config = merge_configs(default_config, _config)
        
        # Проверяем и исправляем опечатки в URL llm-svc
        if "microservices" in _config and "llm_svc" in _config["microservices"]:
            llm_svc = _config["microservices"]["llm_svc"]
            if "base_url" in llm_svc:
                original_url = llm_svc["base_url"]
                if "1lm-svc" in original_url or "11m-svc" in original_url:
                    print(f"ВНИМАНИЕ: Обнаружена опечатка в base_url: {original_url}")
                    llm_svc["base_url"] = original_url.replace("1lm-svc", "llm-svc").replace("11m-svc", "llm-svc")
                    print(f"Исправлено на: {llm_svc['base_url']}")
            if "external_url" in llm_svc:
                original_url = llm_svc["external_url"]
                if "1lm-svc" in original_url or "11m-svc" in original_url:
                    print(f"ВНИМАНИЕ: Обнаружена опечатка в external_url: {original_url}")
                    llm_svc["external_url"] = original_url.replace("1lm-svc", "llm-svc").replace("11m-svc", "llm-svc")
                    print(f"Исправлено на: {llm_svc['external_url']}")
        
        return _config
    except Exception as e:
        print(f"Ошибка загрузки конфигурации из {config_path}: {str(e)}")
        _config = get_default_config()
        return _config

def get_default_config() -> Dict[str, Any]:
    """Получение конфигурации по умолчанию"""
    return {
        "app": {
            "name": "astrachat Backend",
            "version": "1.0.0",
            "description": "Backend service for astrachat",
            "debug": False
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "log_level": "INFO",
            "workers": 1
        },
        "cors": {
            "allowed_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"]
        },
        "microservices": {
            "llm_svc": {
                "enabled": True,
                "base_url": "http://llm-svc:8000",  # ВАЖНО: llm-svc (две буквы 'l'), не 1lm-svc
                "external_url": "http://localhost:8001",
                "timeout": 300,
                "retry_attempts": 3,
                "retry_delay": 1
            }
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "console": True
        }
    }

def merge_configs(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Рекурсивное слияние конфигураций"""
    result = default.copy()
    
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result

def get_config() -> Dict[str, Any]:
    """Получение текущей конфигурации"""
    global _config
    if _config is None:
        config_path = os.environ.get("CONFIG_PATH")
        _config = load_config(config_path)
    return _config

def reset_config() -> Dict[str, Any]:
    """Сброс и перезагрузка конфигурации"""
    global _config
    config_path = os.environ.get("CONFIG_PATH")
    _config = None
    return load_config(config_path)

# Инициализация конфигурации при импорте модуля
config = get_config()