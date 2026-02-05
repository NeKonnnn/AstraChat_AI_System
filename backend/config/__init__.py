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
                # base_url и external_url теперь читаются из секции urls
                "base_url": "",
                "external_url": "",
                "timeout": 300,
                "retry_attempts": 3,
                "retry_delay": 1
            }
        },
        # Секция urls не включена в дефолтный конфиг
        # Все URL должны быть указаны в config.yml
        # Это единственный источник истины для URL-адресов
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

def get_project_root() -> Path:
    """Получение корневой директории проекта"""
    current_file = Path(__file__).resolve()
    
    # В Docker контейнере: /app/backend/config/__init__.py -> /app
    # В локальной разработке: F:/memo_new_api/backend/config/__init__.py -> F:/memo_new_api
    # Проверяем, находимся ли мы в /app (Docker)
    if str(current_file).startswith('/app'):
        # Если файл в /app/backend/config/__init__.py, то корень - /app
        if 'backend' in str(current_file):
            return Path('/app')
        # Если файл в /app/config/__init__.py, то корень тоже /app
        return Path('/app')
    
    # Для локальной разработки: идем на 3 уровня вверх от config/__init__.py
    # backend/config/__init__.py -> backend -> корень проекта
    return current_file.parent.parent.parent.absolute()

def get_path(path_key: str) -> str:
    """Получение абсолютного пути из конфигурации"""
    config = get_config()
    paths_config = config.get("paths", {})
    relative_path = paths_config.get(path_key, "")
    
    if not relative_path:
        # Логируем предупреждение, если путь не найден
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Путь '{path_key}' не найден в config.yml секции paths")
        return ""
    
    project_root = get_project_root()
    full_path = project_root / relative_path
    result = str(full_path.absolute())
    
    # Логируем для отладки
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"get_path('{path_key}'): project_root={project_root}, relative={relative_path}, full={result}")
    
    return result

# Инициализация конфигурации при импорте модуля
config = get_config()

# Константы для обратной совместимости (вычисляются при импорте)
MODEL_PATH = get_path("model_path")
MEMORY_PATH = get_path("memory_path")