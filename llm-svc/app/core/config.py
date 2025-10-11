import yaml
from pydantic import BaseModel
from typing import List, Optional
import os
from pathlib import Path

# Глобальный экземпляр настроек
_settings = None

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"


class CorsConfig(BaseModel):
    allowed_origins: List[str] = ["http://localhost:3080", "http://localhost:8000"]
    allow_credentials: bool = True
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]


class ModelConfig(BaseModel):
    path: str = "/app/models/llama-2-7b-chat.Q4_K_M.gguf"
    name: str = "llama-2-7b-chat"
    ctx_size: int = 4096
    gpu_layers: int = 0
    verbose: bool = False


class GenerationConfig(BaseModel):
    default_temperature: float = 0.7
    default_max_tokens: int = 256
    stream: bool = False


class AppConfig(BaseModel):
    title: str = "Llama CPP API Service"
    description: str = "API service for Llama-based models compatible with OpenAI API"
    version: str = "1.0.0"


class MonitoringConfig(BaseModel):
    enabled: bool = False
    prometheus_port: int = 9090
    metrics_path: str = "/metrics"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_size: int = 10485760
    backup_count: int = 5


class CachingConfig(BaseModel):
    enabled: bool = True
    ttl: int = 300
    max_size: int = 1000


class SecurityConfig(BaseModel):
    enabled: bool = True
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"


class NexusConfig(BaseModel):
    enabled: bool = False
    url: str = ""
    repo: str = ""
    name: str = ""
    id: str = ""
    version: str = ""
    file_name: str = ""
    login: Optional[str] = None
    password: Optional[str] = None
    cert_path: Optional[str] = None

    def __init__(self, **data):
        # Инициализация параметров аутентификации из переменных окружения, если они не заданы в конфиге
        if 'login' not in data or data['login'] is None:
            data['login'] = os.environ.get('NEXUS_LOGIN')
        if 'password' not in data or data['password'] is None:
            data['password'] = os.environ.get('NEXUS_PASSWORD')
        if 'cert_path' not in data or data['cert_path'] is None:
            data['cert_path'] = os.environ.get('NEXUS_CERT_PATH')
        super().__init__(**data)


class Settings(BaseModel):
    server: ServerConfig = ServerConfig()
    cors: CorsConfig = CorsConfig()
    model: ModelConfig = ModelConfig()
    generation: GenerationConfig = GenerationConfig()
    app: AppConfig = AppConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    logging: LoggingConfig = LoggingConfig()
    caching: CachingConfig = CachingConfig()
    security: SecurityConfig = SecurityConfig()
    nexus: NexusConfig = NexusConfig()

    @classmethod
    def from_yaml(cls, config_path: str = None):
        """Загрузка конфигурации из YAML файла"""
        if config_path is None:
            # Поиск config.yml в различных возможных местах
            possible_paths = [
                "config/config.yml",
                "../config/config.yml",
                "./config.yml",
                Path(__file__).parent.parent.parent / "config" / "config.yml"
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            else:
                # Если файл не найден, используем значения по умолчанию
                # Просто возвращаем класс, поля инициализируются автоматически
                return cls()

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                if config_data is None:
                    config_data = {}
                return cls(**config_data)
        except Exception as e:
            raise ValueError(f"Error loading config from {config_path}: {str(e)}")


def get_settings() -> Settings:
    """Получение экземпляра настроек."""
    global _settings
    if _settings is None:
        config_path = os.environ.get("CONFIG_PATH")
        _settings = Settings.from_yaml(config_path)
    return _settings

def reset_settings() -> Settings:
    """Сброс и принудительная перезагрузка настроек."""
    global _settings, settings
    config_path = os.environ.get("CONFIG_PATH")
    _settings = Settings.from_yaml(config_path)
    settings = _settings  # Обновляем глобальную переменную
    return _settings

# Инициализация настроек
settings = get_settings()