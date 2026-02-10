"""
Классы конфигурации подключений для различных сервисов
Все значения загружаются из YAML или ENV, без дефолтных значений
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
import os


def _get_env_value(key: str) -> Optional[str]:
    """Получает значение из переменной окружения или None"""
    return os.getenv(key)


def _get_env_value_int(key: str) -> Optional[int]:
    """Получает int значение из переменной окружения или None"""
    value = os.getenv(key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


class MongoDBConnectionConfig(BaseModel):
    """Конфигурация подключения к MongoDB
    Все значения должны быть заданы в YAML или ENV
    """
    
    host: str
    port: int
    database: str
    user: Optional[str] = None
    password: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def load_from_yaml_or_env(cls, data: dict) -> dict:
        """Загружает значения из YAML или ENV (приоритет: YAML > ENV)"""
        if not isinstance(data, dict):
            data = {}
        
        result = {}
        
        # Приоритет: YAML > ENV
        # Host
        if "host" in data:
            result["host"] = data["host"]
        else:
            host = _get_env_value("MONGODB_HOST")
            if host is None:
                raise ValueError("MONGODB_HOST не задан в YAML или ENV")
            result["host"] = host
        
        # Port
        if "port" in data:
            result["port"] = data["port"]
        else:
            port = _get_env_value_int("MONGODB_PORT")
            if port is None:
                raise ValueError("MONGODB_PORT не задан в YAML или ENV")
            result["port"] = port
        
        # Database
        if "database" in data:
            result["database"] = data["database"]
        else:
            database = _get_env_value("MONGODB_DATABASE")
            if database is None:
                raise ValueError("MONGODB_DATABASE не задан в YAML или ENV")
            result["database"] = database
        
        # User (опционально)
        if "user" in data:
            user = data["user"]
        else:
            user = _get_env_value("MONGODB_USER")
            if user:
                user = user.strip()
                # Игнорируем значения, которые начинаются с '#' (комментарии)
                if user.startswith('#'):
                    user = None
        
        if user:
            result["user"] = user
        
        # Password (опционально)
        if "password" in data:
            password = data["password"]
        else:
            password = _get_env_value("MONGODB_PASSWORD")
            if password:
                password = password.strip()
                # Игнорируем значения, которые начинаются с '#' (комментарии)
                if password.startswith('#'):
                    password = None
        
        if password:
            result["password"] = password
        
        return result
    
    @property
    def connection_string(self) -> str:
        """Формирует строку подключения к MongoDB"""
        if self.user and self.password:
            return f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/"
        return f"mongodb://{self.host}:{self.port}/"
    
    class Config:
        """Настройки Pydantic"""
        extra = "allow"  # Разрешаем дополнительные поля из YAML


class PostgreSQLConnectionConfig(BaseModel):
    """Конфигурация подключения к PostgreSQL
    Все значения должны быть заданы в YAML или ENV
    """
    
    host: str
    port: int
    database: str
    user: str
    password: str
    embedding_dim: int
    
    @model_validator(mode='before')
    @classmethod
    def load_from_yaml_or_env(cls, data: dict) -> dict:
        """Загружает значения из YAML или ENV (приоритет: YAML > ENV)"""
        if not isinstance(data, dict):
            data = {}
        
        result = {}
        
        # Приоритет: YAML > ENV
        # Host
        if "host" in data:
            result["host"] = data["host"]
        else:
            host = _get_env_value("POSTGRES_HOST")
            if host is None:
                raise ValueError("POSTGRES_HOST не задан в YAML или ENV")
            result["host"] = host
        
        # Port
        if "port" in data:
            result["port"] = data["port"]
        else:
            port = _get_env_value_int("POSTGRES_PORT")
            if port is None:
                raise ValueError("POSTGRES_PORT не задан в YAML или ENV")
            result["port"] = port
        
        # Database
        if "database" in data:
            result["database"] = data["database"]
        else:
            database = _get_env_value("POSTGRES_DB")
            if database is None:
                raise ValueError("POSTGRES_DB не задан в YAML или ENV")
            result["database"] = database
        
        # User
        if "user" in data:
            result["user"] = data["user"]
        else:
            user = _get_env_value("POSTGRES_USER")
            if user is None:
                raise ValueError("POSTGRES_USER не задан в YAML или ENV")
            result["user"] = user
        
        # Password
        if "password" in data:
            result["password"] = data["password"]
        else:
            password = _get_env_value("POSTGRES_PASSWORD")
            if password is None:
                raise ValueError("POSTGRES_PASSWORD не задан в YAML или ENV")
            result["password"] = password
        
        # Embedding dim
        if "embedding_dim" in data:
            result["embedding_dim"] = data["embedding_dim"]
        else:
            embedding_dim = _get_env_value_int("EMBEDDING_DIM")
            if embedding_dim is None:
                raise ValueError("EMBEDDING_DIM не задан в YAML или ENV")
            result["embedding_dim"] = embedding_dim
        
        return result
    
    @property
    def connection_string(self) -> str:
        """Формирует строку подключения к PostgreSQL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    class Config:
        """Настройки Pydantic"""
        extra = "allow"


class MinIOConnectionConfig(BaseModel):
    """Конфигурация подключения к MinIO
    Все значения должны быть заданы в YAML или ENV
    """
    
    endpoint: str
    port: int
    access_key: str
    secret_key: str
    use_ssl: bool
    bucket_name: str
    documents_bucket_name: str
    
    @model_validator(mode='before')
    @classmethod
    def load_from_yaml_or_env(cls, data: dict) -> dict:
        """Загружает значения из YAML или ENV (приоритет: YAML > ENV)"""
        if not isinstance(data, dict):
            data = {}
        
        result = {}
        
        # Приоритет: YAML > ENV
        # Endpoint
        if "endpoint" in data:
            result["endpoint"] = data["endpoint"]
        else:
            endpoint = _get_env_value("MINIO_ENDPOINT")
            if endpoint is None:
                raise ValueError("MINIO_ENDPOINT не задан в YAML или ENV")
            result["endpoint"] = endpoint
        
        # Port
        if "port" in data:
            result["port"] = data["port"]
        else:
            port = _get_env_value_int("MINIO_PORT")
            if port is None:
                raise ValueError("MINIO_PORT не задан в YAML или ENV")
            result["port"] = port
        
        # Access key
        if "access_key" in data:
            result["access_key"] = data["access_key"]
        else:
            access_key = _get_env_value("MINIO_ACCESS_KEY") or _get_env_value("MINIO_ROOT_USER")
            if access_key is None:
                raise ValueError("MINIO_ACCESS_KEY или MINIO_ROOT_USER не задан в YAML или ENV")
            result["access_key"] = access_key
        
        # Secret key
        if "secret_key" in data:
            result["secret_key"] = data["secret_key"]
        else:
            secret_key = _get_env_value("MINIO_SECRET_KEY") or _get_env_value("MINIO_ROOT_PASSWORD")
            if secret_key is None:
                raise ValueError("MINIO_SECRET_KEY или MINIO_ROOT_PASSWORD не задан в YAML или ENV")
            result["secret_key"] = secret_key
        
        # Use SSL
        if "use_ssl" in data:
            use_ssl = data["use_ssl"]
        else:
            use_ssl_str = _get_env_value("MINIO_USE_SSL")
            if use_ssl_str is None:
                raise ValueError("MINIO_USE_SSL не задан в YAML или ENV")
            use_ssl = use_ssl_str.lower() == "true"
        result["use_ssl"] = use_ssl if isinstance(use_ssl, bool) else use_ssl
        
        # Bucket name
        if "bucket_name" in data:
            result["bucket_name"] = data["bucket_name"]
        else:
            bucket_name = _get_env_value("MINIO_BUCKET_NAME")
            if bucket_name is None:
                raise ValueError("MINIO_BUCKET_NAME не задан в YAML или ENV")
            result["bucket_name"] = bucket_name
        
        # Documents bucket name (может быть не задан, используем значение по умолчанию из bucket_name)
        if "documents_bucket_name" in data:
            result["documents_bucket_name"] = data["documents_bucket_name"]
        else:
            documents_bucket_name = _get_env_value("MINIO_DOCUMENTS_BUCKET_NAME")
            if documents_bucket_name is None:
                # Если не задан, используем bucket_name с суффиксом -documents
                result["documents_bucket_name"] = result.get("bucket_name", "astrachat-temp").replace("-temp", "-documents")
            else:
                result["documents_bucket_name"] = documents_bucket_name
        
        return result
    
    @property
    def full_endpoint(self) -> str:
        """Возвращает полный endpoint с портом"""
        if ':' not in self.endpoint:
            return f"{self.endpoint}:{self.port}"
        return self.endpoint
    
    class Config:
        """Настройки Pydantic"""
        extra = "allow"


class LLMServiceConnectionConfig(BaseModel):
    """Конфигурация подключения к LLM Service
    Все значения должны быть заданы в YAML или ENV
    """
    
    enabled: bool
    timeout: int
    retry_attempts: int
    retry_delay: int
    
    # URL будут определяться динамически из секции urls в config.yml
    # или из переменных окружения
    base_url: Optional[str] = None
    external_url: Optional[str] = None
    
    # Настройки моделей
    default_model: str
    fallback_model: str
    auto_select: bool
    
    @model_validator(mode='before')
    @classmethod
    def load_from_yaml_or_env(cls, data: dict) -> dict:
        """Загружает значения из YAML или ENV (приоритет: YAML > ENV)"""
        if not isinstance(data, dict):
            data = {}
        
        result = {}
        
        # Приоритет: YAML > ENV
        # Enabled
        if "enabled" in data:
            enabled = data["enabled"]
        else:
            enabled_str = _get_env_value("USE_LLM_SVC")
            if enabled_str is None:
                raise ValueError("USE_LLM_SVC не задан в YAML или ENV")
            enabled = enabled_str.lower() == "true"
        result["enabled"] = enabled if isinstance(enabled, bool) else enabled
        
        # Timeout
        if "timeout" in data:
            result["timeout"] = data["timeout"]
        else:
            timeout = _get_env_value_int("LLM_SVC_TIMEOUT")
            if timeout is None:
                raise ValueError("LLM_SVC_TIMEOUT не задан в YAML или ENV")
            result["timeout"] = timeout
        
        # Retry attempts
        if "retry_attempts" in data:
            result["retry_attempts"] = data["retry_attempts"]
        else:
            retry_attempts = _get_env_value_int("LLM_SVC_RETRY_ATTEMPTS")
            if retry_attempts is None:
                raise ValueError("LLM_SVC_RETRY_ATTEMPTS не задан в YAML или ENV")
            result["retry_attempts"] = retry_attempts
        
        # Retry delay
        if "retry_delay" in data:
            result["retry_delay"] = data["retry_delay"]
        else:
            retry_delay = _get_env_value_int("LLM_SVC_RETRY_DELAY")
            if retry_delay is None:
                raise ValueError("LLM_SVC_RETRY_DELAY не задан в YAML или ENV")
            result["retry_delay"] = retry_delay
        
        # Обработка вложенной структуры models из YAML
        models_data = data.get("models", {}) if isinstance(data.get("models"), dict) else {}
        
        # Default model (может быть в YAML в секции microservices.llm_svc.models.default)
        if "default_model" in data:
            result["default_model"] = data["default_model"]
        elif models_data.get("default"):
            result["default_model"] = models_data["default"]
        else:
            # Если не задан, пробуем получить из config.yml через внешний контекст
            # Это значение должно быть в config.yml в секции microservices.llm_svc.models.default
            raise ValueError("default_model не задан в YAML (llm_service.default_model или llm_service.models.default или microservices.llm_svc.models.default)")
        
        # Fallback model
        if "fallback_model" in data:
            result["fallback_model"] = data["fallback_model"]
        elif models_data.get("fallback"):
            result["fallback_model"] = models_data["fallback"]
        else:
            raise ValueError("fallback_model не задан в YAML (llm_service.fallback_model или llm_service.models.fallback или microservices.llm_svc.models.fallback)")
        
        # Auto select
        if "auto_select" in data:
            result["auto_select"] = data["auto_select"]
        elif "auto_select" in models_data:
            result["auto_select"] = models_data["auto_select"]
        else:
            # По умолчанию True, если не задано
            result["auto_select"] = True
        
        return result
    
    class Config:
        """Настройки Pydantic"""
        extra = "allow"