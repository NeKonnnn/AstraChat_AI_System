import yaml
from pydantic import BaseModel
from typing import List, Optional
import os
from pathlib import Path

_settings = None


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"


class CorsConfig(BaseModel):
    allowed_origins: List[str] = ["*"]
    allow_credentials: bool = True
    allow_methods: List[str] = ["*"]
    allow_headers: List[str] = ["*"]


class AppConfig(BaseModel):
    title: str = "RAG Models Service"
    description: str = "Embedding and Reranker models for RAG (MiniLM-L12, MiniLM-L6)"
    version: str = "1.0.0"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class RagModelsConfig(BaseModel):
    """Настройки эмбеддингов и реранкера. Можно указать свои папки с моделями и работать офлайн."""
    enabled: bool = True
    # Папка, куда кладём кэш HF и свои модели
    models_dir: str = os.environ.get("RAG_MODELS_DIR", "/app/models/rag")
    # Эмбеддинг: имя с HF или подпапка в models_dir 
    embedding_model: Optional[str] = os.environ.get("RAG_EMBEDDING_MODEL")
    # Реранкер: то же самое 
    reranker_model: Optional[str] = os.environ.get("RAG_RERANKER_MODEL")
    # Только локальные веса, в интернет не качаем
    offline: bool = os.environ.get("RAG_MODELS_OFFLINE", "0").strip().lower() in ("1", "true", "yes")
    device: str = os.environ.get("RAG_MODELS_DEVICE", "cpu")  # cpu, cuda или auto
    # Дефолтные имена с HuggingFace, если свои не задали
    embedding_model_default: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    reranker_model_default: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    embedding_dim: int = 384  # у MiniLM-L12 вектор такой длины


class Settings(BaseModel):
    server: ServerConfig = ServerConfig()
    cors: CorsConfig = CorsConfig()
    app: AppConfig = AppConfig()
    logging: LoggingConfig = LoggingConfig()
    rag_models: RagModelsConfig = RagModelsConfig()

    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None):
        # Ищем config по типичным путям, если путь не передали
        if config_path is None or config_path == "":
            possible_paths = [
                "config/config.yml",
                "../config/config.yml",
                Path(__file__).resolve().parent.parent.parent / "config" / "config.yml",
            ]
            for path in possible_paths:
                p = str(path) if hasattr(path, "resolve") else path
                if os.path.exists(p):
                    config_path = p
                    break
            else:
                return cls()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Error loading config from {config_path}: {e}")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        config_path = os.environ.get("CONFIG_PATH", "")
        _settings = Settings.from_yaml(config_path or None)
    return _settings


settings = get_settings()
