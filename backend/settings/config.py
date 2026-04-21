"""
Основной модуль конфигурации для astrachat Backend.
Сетевые URL микросервисов задаются в backend/config/config.yml (секция urls).
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
    LLMHostEntry,
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


def _docker_runtime() -> bool:
    de = os.getenv("DOCKER_ENV")
    if de is not None:
        return str(de).lower() == "true"
    return os.path.exists("/.dockerenv")


def _preprocess_urls_and_microservices(config_data: Dict[str, Any]) -> None:
    """Легаси-ключ diarization_docker; base_url для llm host local из urls; убрать дублирующие microservices.url."""
    urls = config_data.get("urls")
    if isinstance(urls, dict):
        if urls.get("diarization_docker") and not urls.get("diarization_service_docker"):
            urls["diarization_service_docker"] = urls["diarization_docker"]
    ms = config_data.get("microservices")
    if not isinstance(ms, dict):
        return
    if not isinstance(urls, dict):
        urls = {}
    docker = _docker_runtime()
    llm_u = (
        (urls.get("llm_service_docker") or "").strip()
        if docker
        else (urls.get("llm_service_port") or urls.get("llm_service_docker") or "").strip()
    ).rstrip("/")
    llm = ms.get("llm")
    if isinstance(llm, dict):
        llm.pop("url", None)
        for h in llm.get("hosts") or []:
            if isinstance(h, dict) and not (str(h.get("base_url") or "").strip()) and llm_u:
                h["base_url"] = llm_u
    for key in ("stt", "tts", "ocr", "diarization"):
        svc = ms.get(key)
        if isinstance(svc, dict):
            svc.pop("url", None)


class UrlsConfig(BaseModel):
    """URL из backend/config/config.yml (секция urls)."""

    frontend_port_1: Optional[str] = None
    frontend_port_1_ipv4: Optional[str] = None
    frontend_port_2: Optional[str] = None
    frontend_port_2_ipv4: Optional[str] = None
    frontend_port_3: Optional[str] = None
    frontend_port_3_ipv4: Optional[str] = None

    backend_port_1: Optional[str] = None
    backend_port_1_ipv4: Optional[str] = None
    backend_port_2: Optional[str] = None
    backend_port_2_ipv4: Optional[str] = None

    llm_service_port: Optional[str] = None

    frontend_docker: Optional[str] = None
    backend_docker: Optional[str] = None
    llm_service_docker: Optional[str] = None
    stt_service_docker: Optional[str] = None
    stt_service_port: Optional[str] = None
    tts_service_docker: Optional[str] = None
    tts_service_port: Optional[str] = None
    ocr_service_docker: Optional[str] = None
    ocr_service_port: Optional[str] = None
    diarization_service_docker: Optional[str] = None
    diarization_service_port: Optional[str] = None
    rag_service_docker: Optional[str] = None
    rag_service_port: Optional[str] = None
    rag_models_service_docker: Optional[str] = None
    rag_models_service_port: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_urls_yaml(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            data = {}
        out = {**data}
        if out.get("diarization_docker") and not out.get("diarization_service_docker"):
            out["diarization_service_docker"] = out["diarization_docker"]
        return out


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

    # Мультипровайдерная конфигурация LLM (llm-svc, vLLM, Ollama, OpenAI, ...).
    # Если пуст — auto-migration из llm_service.hosts в registry.
    llm_providers: List[Dict[str, Any]] = Field(default_factory=list)
    default_llm_provider: Optional[str] = None

    class Config:
        """Настройки Pydantic"""
        extra = "allow"  # Разрешаем дополнительные поля из YAML

    def microservice_http_base(self, docker_field: str, port_field: str) -> str:
        """Базовый URL микросервиса: в Docker — *_docker, с хоста — *_port (или fallback *_docker)."""
        u = self.urls
        if _docker_runtime():
            v = getattr(u, docker_field, None)
        else:
            v = getattr(u, port_field, None) or getattr(u, docker_field, None)
        if not v or not str(v).strip():
            raise ValueError(
                f"Задайте urls.{docker_field} и urls.{port_field} в backend/config/config.yml"
            )
        return str(v).strip().rstrip("/")
    
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

            _preprocess_urls_and_microservices(config_data)

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
                elif key == "llm_providers":
                    # Список провайдеров — принимаем как список dict'ов
                    if isinstance(value, list):
                        settings_data[key] = value
                    elif value is None:
                        settings_data[key] = []
                    else:
                        settings_data[key] = value
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

            # microservices.llm (config.yml) — алиас к llm_service
            if "microservices" in config_data and "llm" in config_data.get("microservices", {}):
                llm_ms = config_data["microservices"]["llm"]
                if isinstance(llm_ms, dict):
                    if "timeout" in llm_ms and "timeout" not in settings_data["llm_service"]:
                        settings_data["llm_service"]["timeout"] = llm_ms["timeout"]
                    models_block = llm_ms.get("models")
                    if isinstance(models_block, dict):
                        if models_block.get("default") and "default_model" not in settings_data["llm_service"]:
                            settings_data["llm_service"]["default_model"] = models_block["default"]
                        if models_block.get("fallback") is not None and "fallback_model" not in settings_data["llm_service"]:
                            settings_data["llm_service"]["fallback_model"] = models_block["fallback"]
                    hosts_raw = llm_ms.get("hosts")
                    if isinstance(hosts_raw, list) and hosts_raw and "hosts" not in settings_data["llm_service"]:
                        parsed = []
                        for h in hosts_raw:
                            if isinstance(h, dict) and h.get("id") and h.get("base_url"):
                                parsed.append(LLMHostEntry(id=str(h["id"]), base_url=str(h["base_url"]).rstrip("/")))
                        if parsed:
                            settings_data["llm_service"]["hosts"] = [e.model_dump() for e in parsed]
                    if llm_ms.get("default_host_id") and "default_host_id" not in settings_data["llm_service"]:
                        settings_data["llm_service"]["default_host_id"] = str(llm_ms["default_host_id"])
            
            # Создаем экземпляр Settings
            settings = cls(**settings_data)

            if config_data.get("urls"):
                try:
                    bu = settings.microservice_http_base("llm_service_docker", "llm_service_port")
                    settings.llm_service.base_url = bu
                    ep = (settings.urls.llm_service_port or "").strip().rstrip("/")
                    if ep:
                        settings.llm_service.external_url = ep
                except ValueError:
                    pass

            # CORS из urls, если в YAML не задан список origins
            if config_data.get("urls") and not config_data.get("cors", {}).get("allowed_origins"):
                urls = config_data["urls"]
                cors_origins = [
                    urls.get("frontend_port_1", ""),
                    urls.get("frontend_port_1_ipv4", ""),
                    urls.get("frontend_port_2", ""),
                    urls.get("frontend_port_2_ipv4", ""),
                    urls.get("frontend_port_3", ""),
                    urls.get("frontend_port_3_ipv4", ""),
                    urls.get("backend_port_1", ""),
                    urls.get("backend_port_1_ipv4", ""),
                ]
                cors_origins = [origin for origin in cors_origins if origin]
                if cors_origins:
                    settings.cors.allowed_origins = cors_origins

            return settings
            
        except Exception as e:
            raise ValueError(f"Ошибка загрузки конфигурации из {config_path}: {str(e)}")
    
    def get_llm_service_url(self) -> str:
        """URL LLM для текущего окружения (см. urls.llm_service_* в config.yml)."""
        return self.microservice_http_base("llm_service_docker", "llm_service_port")


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