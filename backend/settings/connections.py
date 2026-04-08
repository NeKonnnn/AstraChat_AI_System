"""
Модуль конфигурации подключений для astrachat Backend
Содержит классы конфигурации для баз данных и микросервисов.
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator

class MongoDBConnectionConfig(BaseModel):
    host: str = "localhost"
    port: int = 27017
    database: str = "astrachat"
    username: Optional[str] = None
    password: Optional[str] = None
    
    @property
    def connection_string(self) -> str:
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"mongodb://{self.host}:{self.port}"
    
    @model_validator(mode='before')
    @classmethod
    def load_from_env(cls, data: dict) -> dict:
        if not data:
            data = {}
        if not data.get("host"):
            data["host"] = os.getenv("MONGODB_HOST", "localhost")
        if not data.get("port"):
            try:
                data["port"] = int(os.getenv("MONGODB_PORT", 27017))
            except (ValueError, TypeError):
                data["port"] = 27017
        if not data.get("database"):
            data["database"] = os.getenv("MONGODB_DATABASE", "astrachat")
        if not data.get("username"):
            data["username"] = os.getenv("MONGODB_USER")
        if not data.get("password"):
            data["password"] = os.getenv("MONGODB_PASSWORD")
        return data

class PostgreSQLConnectionConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str = "astrachat"
    username: str = "postgres"
    password: str = "postgres"
    embedding_dim: int = 384  # Размерность векторов (по умолчанию для paraphrase-multilingual-MiniLM-L12-v2)
    
    @property
    def user(self) -> str:
        return self.username
        
    @model_validator(mode='before')
    @classmethod
    def load_from_env(cls, data: dict) -> dict:
        if not data:
            data = {}
        if not data.get("host"):
            data["host"] = os.getenv("POSTGRES_HOST", "localhost")
        if not data.get("port"):
            try:
                data["port"] = int(os.getenv("POSTGRES_PORT", 5432))
            except (ValueError, TypeError):
                data["port"] = 5432
        if not data.get("database"):
            data["database"] = os.getenv("POSTGRES_DB", "astrachat")
        if not data.get("username"):
            data["username"] = os.getenv("POSTGRES_USER", "postgres")
        if not data.get("password"):
            data["password"] = os.getenv("POSTGRES_PASSWORD", "postgres")
        return data

class MinIOConnectionConfig(BaseModel):
    endpoint: str = "localhost"
    port: int = 9000
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    use_ssl: bool = False
    bucket_name: str = "astrachat-temp"
    documents_bucket_name: str = "astrachat-documents"
    memory_rag_bucket_name: str = "astrachat-memory-rag"
    project_rag_bucket_name: str = "astrachat-project-rag"
    
    @model_validator(mode='before')
    @classmethod
    def load_from_env(cls, data: dict) -> dict:
        if not data:
            data = {}
        if not data.get("endpoint"):
            data["endpoint"] = os.getenv("MINIO_ENDPOINT", "localhost")
        if not data.get("port"):
            try:
                data["port"] = int(os.getenv("MINIO_PORT", 9000))
            except (ValueError, TypeError):
                data["port"] = 9000
        if not data.get("access_key"):
            data["access_key"] = os.getenv("MINIO_ROOT_USER", os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
        if not data.get("secret_key"):
            data["secret_key"] = os.getenv("MINIO_ROOT_PASSWORD", os.getenv("MINIO_SECRET_KEY", "minioadmin"))
        if not data.get("use_ssl"):
            data["use_ssl"] = os.getenv("MINIO_USE_SSL", "false").lower() == "true"
        if not data.get("documents_bucket_name"):
            data["documents_bucket_name"] = os.getenv(
                "MINIO_DOCUMENTS_BUCKET_NAME", "astrachat-documents"
            )
        if not data.get("memory_rag_bucket_name"):
            data["memory_rag_bucket_name"] = os.getenv(
                "MINIO_MEMORY_RAG_BUCKET_NAME", "astrachat-memory-rag"
            )
        if not data.get("project_rag_bucket_name"):
            data["project_rag_bucket_name"] = os.getenv(
                "MINIO_PROJECT_RAG_BUCKET_NAME", "astrachat-project-rag"
            )
        return data

class ServiceConnectionConfig(BaseModel):
    url: str = ""
    timeout: float = 120.0
    
    @model_validator(mode='before')
    @classmethod
    def load_from_env(cls, data: dict) -> dict:
        return data

class LLMHostEntry(BaseModel):
    """Один инстанс llm-svc (или совместимого OpenAI API) с собственным base_url."""
    id: str = Field(..., description="Короткий идентификатор для путей llm-svc://id/model")
    base_url: str


class LLMServiceConnectionConfig(ServiceConnectionConfig):
    default_model: str = "qwen-coder-30b"
    fallback_model: Optional[str] = None
    auto_select: bool = False
    base_url: str = ""
    external_url: str = ""
    # Несколько хостов: если задано, маршрутизация llm-svc://host_id/model; иначе один base_url как host "default"
    hosts: Optional[List[LLMHostEntry]] = None
    default_host_id: Optional[str] = None

class STTConnectionConfig(ServiceConnectionConfig):
    pass

class TTSConnectionConfig(ServiceConnectionConfig):
    pass

class OCRConnectionConfig(ServiceConnectionConfig):
    pass

class DiarizationConnectionConfig(ServiceConnectionConfig):
    pass

# Алиасы для совместимости с кодом, который импортирует LLMConnectionConfig
LLMConnectionConfig = LLMServiceConnectionConfig
