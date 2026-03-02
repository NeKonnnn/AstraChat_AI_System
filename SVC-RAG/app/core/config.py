# Настройки сервиса: URL RAG-MODELS, PostgreSQL, размерность эмбеддингов
import os
import yaml
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

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
    title: str = "RAG Service"
    description: str = "Логика RAG: индексация документов, поиск по pgvector и BM25"
    version: str = "1.0.0"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class RagModelsClientConfig(BaseModel):
    # URL сервиса SVC-RAG-MODELS (эмбеддинги и реранкер)
    base_url: str = os.environ.get("RAG_MODELS_URL", "http://rag-models:8000")
    timeout: float = 60.0


class PostgreSQLConfig(BaseModel):
    host: str = os.environ.get("POSTGRES_HOST", "localhost")
    port: int = int(os.environ.get("POSTGRES_PORT", "5432"))
    database: str = os.environ.get("POSTGRES_DB", "astrachat")
    user: str = os.environ.get("POSTGRES_USER", "postgres")
    password: str = os.environ.get("POSTGRES_PASSWORD", "postgres")
    embedding_dim: int = int(os.environ.get("RAG_EMBEDDING_DIM", "384"))


class OcrConfig(BaseModel):
    # URL сервиса OCR (Surya). Такой же, как в backend: SVC_OCR_URL / http://ocr-service:8000
    url: str = os.environ.get("SVC_OCR_URL", "http://ocr-service:8000")
    timeout: float = float(os.environ.get("RAG_OCR_TIMEOUT", "300.0"))


class RagServiceConfig(BaseModel):
    enabled: bool = True
    # Гибридный поиск: вектор + BM25
    use_hybrid_search: bool = os.environ.get("RAG_USE_HYBRID_SEARCH", "true").lower() == "true"
    hybrid_bm25_weight: float = float(os.environ.get("RAG_HYBRID_BM25_WEIGHT", "0.3"))
    # Реранкинг через SVC-RAG-MODELS
    use_reranking: bool = os.environ.get("RAG_USE_RERANKING", "false").lower() == "true"
    rerank_top_k: int = int(os.environ.get("RAG_RERANK_TOP_K", "20"))
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Иерархическое индексирование (как в backend DocumentProcessor)
    use_hierarchical_indexing: bool = os.environ.get("RAG_USE_HIERARCHICAL", "true").lower() == "true"
    hierarchical_threshold: int = int(os.environ.get("RAG_HIERARCHICAL_THRESHOLD", "10000"))
    hierarchical_chunk_size: int = int(os.environ.get("RAG_HIERARCHICAL_CHUNK_SIZE", "1500"))
    hierarchical_chunk_overlap: int = int(os.environ.get("RAG_HIERARCHICAL_CHUNK_OVERLAP", "200"))
    intermediate_summary_chunks: int = int(os.environ.get("RAG_INTERMEDIATE_SUMMARY_CHUNKS", "8"))
    create_full_summary_via_llm: bool = os.environ.get("RAG_CREATE_FULL_SUMMARY_VIA_LLM", "false").lower() == "true"


class LLMServiceConfig(BaseModel):
    base_url: str = os.environ.get("SVC_LLM_URL", "http://llm-service:8000")
    timeout: float = float(os.environ.get("RAG_LLM_TIMEOUT", "120.0"))
    default_model: str = os.environ.get("RAG_LLM_MODEL", "default")


class Settings(BaseModel):
    server: ServerConfig = ServerConfig()
    cors: CorsConfig = CorsConfig()
    app: AppConfig = AppConfig()
    logging: LoggingConfig = LoggingConfig()
    rag_models_client: RagModelsClientConfig = RagModelsClientConfig()
    postgresql: PostgreSQLConfig = PostgreSQLConfig()
    ocr: OcrConfig = OcrConfig()
    rag: RagServiceConfig = RagServiceConfig()
    llm_service: LLMServiceConfig = LLMServiceConfig()

    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None):
        if not config_path or config_path == "":
            for path in [
                "config/config.yml",
                "../config/config.yml",
                Path(__file__).resolve().parent.parent.parent / "config" / "config.yml",
            ]:
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
            raise ValueError(f"Ошибка загрузки конфига {config_path}: {e}")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml(os.environ.get("CONFIG_PATH", ""))
    return _settings


settings = get_settings()
