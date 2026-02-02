"""
Основной модуль конфигурации для astrachat Backend
Загружает настройки из YAML и переменных окружения
"""

import yaml
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, model_validator

# Попытка загрузить переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    # Ищем .env файл в корне проекта
    root_dir = Path(__file__).parent.parent.parent
    env_paths = [
        root_dir / ".env",  # Корень проекта
        Path(__file__).parent.parent / ".env",  # backend/.env
    ]
    # Пробуем загрузить из стандартных путей
    loaded = False
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)  # override=False - env переменные имеют приоритет
            loaded = True
            break
    # Если .env не найден, пробуем найти любой файл, начинающийся с .env в корне
    if not loaded:
        for env_file in root_dir.glob(".env*"):
            if env_file.is_file() and not env_file.name.endswith('.example'):
                load_dotenv(env_file, override=False)
                break
except ImportError:
    # python-dotenv не установлен, используем только системные переменные окружения
    pass

from .connections import (
    MongoDBConnectionConfig,
    PostgreSQLConnectionConfig,
    MinIOConnectionConfig,
    LLMServiceConnectionConfig,
)


# Глобальный экземпляр настроек
_settings: Optional['Settings'] = None


class ServerConfig(BaseModel):
    """Конфигурация сервера"""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    workers: int = 1


class CorsConfig(BaseModel):
    """Конфигурация CORS"""
    allowed_origins: List[str] = []
    allow_credentials: bool = True
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]


class AppConfig(BaseModel):
    """Конфигурация приложения"""
    name: str = "astrachat Backend"
    version: str = "1.0.0"
    description: str = "Backend service for astrachat with microservice architecture"
    debug: bool = False


class MemoryConfig(BaseModel):
    """Конфигурация памяти"""
    enabled: bool = True
    storage_type: str = "file"  # file, redis, database
    file_path: str = "/app/memory"
    max_history_length: int = 100
    auto_save: bool = True
    save_interval: int = 30  # секунды


class LoggingConfig(BaseModel):
    """Конфигурация логирования"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = "/app/logs/backend.log"
    max_size: int = 10485760  # 10MB
    backup_count: int = 5
    console: bool = True


class SecurityConfig(BaseModel):
    """Конфигурация безопасности"""
    enabled: bool = False
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
    rate_limiting_enabled: bool = False
    rate_limiting_requests_per_minute: int = 60


class WebSocketConfig(BaseModel):
    """Конфигурация WebSocket"""
    enabled: bool = True
    ping_interval: int = 30  # секунды
    ping_timeout: int = 10  # секунды
    max_connections: int = 100


class FilesConfig(BaseModel):
    """Конфигурация файлов"""
    upload_dir: str = "/app/uploads"
    max_file_size: int = 104857600  # 100MB
    allowed_extensions: List[str] = [".txt", ".md", ".pdf", ".docx", ".wav", ".mp3", ".mp4", ".m4a", ".flac", ".ogg"]
    temp_dir: str = "/tmp/astrachat"


class UrlsConfig(BaseModel):
    """Конфигурация URL адресов
    Все значения должны быть заданы в YAML или ENV
    """
    # Frontend адреса
    frontend_port_1: str
    frontend_port_1_ipv4: str
    frontend_port_2: str
    frontend_port_2_ipv4: str
    frontend_port_3: str
    frontend_port_3_ipv4: str
    
    # Backend адреса
    backend_port_1: str
    backend_port_1_ipv4: str
    backend_port_2: str
    backend_port_2_ipv4: str
    
    # LLM Service адреса
    llm_service_port: str
    
    # Docker внутренние адреса
    frontend_docker: str
    backend_docker: str
    llm_service_docker: str
    
    @model_validator(mode='before')
    @classmethod
    def load_from_yaml_or_env(cls, data: dict) -> dict:
        """Загружает значения из YAML или ENV (приоритет: YAML > ENV)"""
        if not isinstance(data, dict):
            data = {}
        
        result = {}
        required_keys = [
            "frontend_port_1", "frontend_port_1_ipv4",
            "frontend_port_2", "frontend_port_2_ipv4",
            "frontend_port_3", "frontend_port_3_ipv4",
            "backend_port_1", "backend_port_1_ipv4",
            "backend_port_2", "backend_port_2_ipv4",
            "llm_service_port",
            "frontend_docker", "backend_docker", "llm_service_docker",
        ]
        
        for key in required_keys:
            if key in data:
                result[key] = data[key]
            else:
                # Пробуем получить из ENV (например, FRONTEND_PORT_1, BACKEND_PORT_1 и т.д.)
                env_key = key.upper()
                env_value = os.getenv(env_key)
                if env_value is None:
                    raise ValueError(f"{key} не задан в YAML (urls.{key}) или ENV ({env_key})")
                result[key] = env_value
        
        return result


class Settings(BaseModel):
    """Основной класс настроек приложения"""
    
    app: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    files: FilesConfig = Field(default_factory=FilesConfig)
    urls: UrlsConfig = Field(default_factory=UrlsConfig)
    
    # Подключения к внешним сервисам
    mongodb: MongoDBConnectionConfig = Field(default_factory=MongoDBConnectionConfig)
    postgresql: PostgreSQLConnectionConfig = Field(default_factory=PostgreSQLConnectionConfig)
    minio: MinIOConnectionConfig = Field(default_factory=MinIOConnectionConfig)
    llm_service: LLMServiceConnectionConfig = Field(default_factory=LLMServiceConnectionConfig)
    
    class Config:
        """Настройки Pydantic"""
        extra = "allow"  # Разрешаем дополнительные поля из YAML
    
    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None) -> 'Settings':
        """
        Загрузка конфигурации из YAML файла
        
        Args:
            config_path: Путь к файлу конфигурации. Если None, ищет в стандартных местах.
        
        Returns:
            Экземпляр Settings с загруженной конфигурацией
        """
        if config_path is None:
            # Поиск config.yml в различных возможных местах
            possible_paths = [
                Path(__file__).parent.parent / "config" / "config.yml",  # backend/config/config.yml
                Path(__file__).parent.parent.parent / "backend" / "config" / "config.yml",  # из корня проекта
                "config/config.yml",
                "../config/config.yml",
                "./config.yml",
            ]
            
            for path in possible_paths:
                path_obj = Path(path) if isinstance(path, str) else path
                if path_obj.exists():
                    config_path = str(path_obj.absolute())
                    break
            else:
                # Если файл не найден, используем значения по умолчанию
                return cls()
        else:
            # Если CONFIG_PATH задан, проверяем существование файла
            if not os.path.exists(config_path):
                # Если файл не найден по указанному пути, пробуем найти в стандартных местах
                possible_paths = [
                    Path(__file__).parent.parent / "config" / "config.yml",
                    Path(__file__).parent.parent.parent / "backend" / "config" / "config.yml",
                ]
                for path in possible_paths:
                    if path.exists():
                        config_path = str(path.absolute())
                        break
                else:
                    # Если файл не найден, используем значения по умолчанию
                    return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            
            # Подготавливаем данные для создания Settings
            # Классы подключений сами загрузят значения из env через model_validator,
            # если они не заданы в YAML
            settings_data = {}
            
            # Копируем все секции из YAML
            for key, value in config_data.items():
                if key in ["mongodb", "postgresql", "minio", "llm_service"]:
                    # Для секций подключений передаем данные как есть (может быть пустым dict)
                    # model_validator в классах подключений сам загрузит из env, если секция пустая
                    settings_data[key] = value if value is not None else {}
                else:
                    settings_data[key] = value
            
            # Если секций подключений нет в YAML, создаем пустые dict для загрузки из ENV
            if "mongodb" not in settings_data:
                settings_data["mongodb"] = {}
            if "postgresql" not in settings_data:
                settings_data["postgresql"] = {}
            if "minio" not in settings_data:
                settings_data["minio"] = {}
            if "llm_service" not in settings_data:
                settings_data["llm_service"] = {}
            
            # Обработка LLM Service - может быть в секции microservices.llm_svc
            if "microservices" in config_data and "llm_svc" in config_data["microservices"]:
                llm_svc_data = config_data["microservices"]["llm_svc"]
                # Объединяем данные из microservices.llm_svc с данными из llm_service
                if isinstance(llm_svc_data, dict):
                    # Копируем настройки из microservices.llm_svc в llm_service
                    for key, value in llm_svc_data.items():
                        if key not in settings_data["llm_service"]:
                            settings_data["llm_service"][key] = value
            
            # Создаем экземпляр Settings
            settings = cls(**settings_data)
            
            # Обновляем URL для LLM Service из секции urls
            if config_data.get("urls"):
                urls = config_data["urls"]
                # Определяем окружение: если есть переменная DOCKER_ENV в ENV, используем её
                # Иначе определяем автоматически по наличию docker адресов
                docker_env = os.getenv("DOCKER_ENV")
                if docker_env is None:
                    # Автоматическое определение: если мы в Docker, то используем docker адреса
                    # Проверяем, запущен ли код в контейнере (обычно есть файл /.dockerenv)
                    docker_env = str(os.path.exists("/.dockerenv")).lower()
                
                docker_env = docker_env.lower() == "true"
                
                if docker_env:
                    llm_url = urls.get("llm_service_docker", "")
                else:
                    llm_url = urls.get("llm_service_port", "")
                
                if llm_url:
                    settings.llm_service.base_url = llm_url.rstrip('/')
                    settings.llm_service.external_url = urls.get("llm_service_port", "").rstrip('/')
            
            # Обновляем CORS allowed_origins из urls
            if config_data.get("urls") and not config_data.get("cors", {}).get("allowed_origins"):
                urls = config_data["urls"]
                cors_origins = [
                    urls.get("frontend_port_1", ""),
                    urls.get("frontend_port_1_ipv4", ""),
                    urls.get("frontend_port_2", ""),
                    urls.get("frontend_port_2_ipv4", ""),
                    urls.get("frontend_port_3", ""),
                    urls.get("frontend_port_3_ipv4", ""),
                ]
                # Фильтруем пустые значения
                cors_origins = [origin for origin in cors_origins if origin]
                if cors_origins:
                    settings.cors.allowed_origins = cors_origins
            
            return settings
            
        except Exception as e:
            raise ValueError(f"Ошибка загрузки конфигурации из {config_path}: {str(e)}")
    
    def get_llm_service_url(self) -> str:
        """
        Получает URL для LLM Service в зависимости от окружения
        
        Returns:
            URL для подключения к LLM Service
        """
        # Определяем окружение: если есть переменная DOCKER_ENV в ENV, используем её
        # Иначе определяем автоматически по наличию docker адресов
        docker_env = os.getenv("DOCKER_ENV")
        if docker_env is None:
            # Автоматическое определение: если мы в Docker, то используем docker адреса
            # Проверяем, запущен ли код в контейнере (обычно есть файл /.dockerenv)
            docker_env = str(os.path.exists("/.dockerenv")).lower()
        
        docker_env = docker_env.lower() == "true"
        
        if docker_env:
            return self.urls.llm_service_docker
        return self.urls.llm_service_port


def get_settings() -> Settings:
    """
    Получение глобального экземпляра настроек (singleton)
    
    Returns:
        Экземпляр Settings
    """
    global _settings
    if _settings is None:
        config_path = os.environ.get("CONFIG_PATH")
        _settings = Settings.from_yaml(config_path)
    return _settings


def reset_settings() -> Settings:
    """
    Сброс и принудительная перезагрузка настроек
    
    Returns:
        Новый экземпляр Settings
    """
    global _settings
    config_path = os.environ.get("CONFIG_PATH")
    _settings = Settings.from_yaml(config_path)
    return _settings


# Инициализация настроек при импорте модуля (ленивая)
# Не инициализируем сразу, чтобы избежать ошибок при импорте
settings = None

def _init_settings():
    """Ленивая инициализация настроек"""
    global settings
    if settings is None:
        settings = get_settings()
    return settings

