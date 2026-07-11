# Настройки сервиса: URL RAG-MODELS, PostgreSQL, размерность эмбеддингов
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

_settings = None


def _env_str(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _env_int(name: str) -> Optional[int]:
    value = _env_str(name)
    if value is None:
        return None
    return int(value)


def _docker_runtime() -> bool:
    de = os.environ.get("DOCKER_ENV")
    if de is not None:
        return str(de).lower() == "true"
    return os.path.exists("/.dockerenv")


def _pick_service_url(urls: dict, docker_key: str, port_key: str) -> str:
    if not isinstance(urls, dict):
        return ""
    if _docker_runtime():
        return (urls.get(docker_key) or "").strip().rstrip("/")
    return ((urls.get(port_key) or urls.get(docker_key)) or "").strip().rstrip("/")


_URLS_CORS_KEYS: Tuple[str, ...] = (
    "frontend_port",
    "frontend_port_ipv4",
    "frontend_port_2",
    "frontend_port_2_ipv4",
    "frontend_port_3",
    "frontend_port_3_ipv4",
    "backend_port",
    "backend_port_ipv4",
    "backend_port_2",
    "backend_port_2_ipv4",
)


def _apply_urls_section(data: dict) -> dict:
    urls = data.get("urls")
    if not isinstance(urls, dict):
        return data
    out = dict(data)
    rmc = dict(out.get("rag_models_client") or {})
    if not str(rmc.get("base_url") or "").strip():
        bu = _pick_service_url(urls, "rag_models_service_docker", "rag_models_service_port")
        if bu:
            rmc["base_url"] = bu
    out["rag_models_client"] = rmc

    oc = dict(out.get("ocr") or {})
    if not str(oc.get("url") or "").strip():
        u = _pick_service_url(urls, "ocr_service_docker", "ocr_service_port")
        if u:
            oc["url"] = u
    out["ocr"] = oc

    llm = dict(out.get("llm_service") or {})
    if not str(llm.get("base_url") or "").strip():
        bu = _pick_service_url(urls, "llm_service_docker", "llm_service_port")
        if bu:
            llm["base_url"] = bu
    out["llm_service"] = llm

    be = dict(out.get("backend") or {})
    if not str(be.get("base_url") or "").strip():
        bu = _pick_service_url(urls, "backend_service_docker", "backend_service_port")
        if bu:
            be["base_url"] = bu
    out["backend"] = be

    cors = dict(out.get("cors") or {})
    ao = cors.get("allowed_origins")
    if not ao or ao == ["*"]:
        merged = [str(urls[k]).strip() for k in _URLS_CORS_KEYS if urls.get(k) and str(urls[k]).strip()]
        if merged:
            cors["allowed_origins"] = merged
    out["cors"] = cors
    out.pop("urls", None)
    return out


def _apply_postgres_env_overrides(data: dict) -> dict:
    """Приоритет подключения к PostgreSQL: env -> config.yml -> defaults."""
    out = dict(data)
    pg = dict(out.get("postgresql") or {})

    host = _env_str("POSTGRES_HOST")
    port = _env_int("POSTGRES_PORT")
    db = _env_str("POSTGRES_DB")
    user = _env_str("POSTGRES_USER")
    password = _env_str("POSTGRES_PASSWORD")
    embedding_dim = _env_int("RAG_EMBEDDING_DIM")

    if host is not None:
        pg["host"] = host
    if port is not None:
        pg["port"] = port
    if db is not None:
        pg["database"] = db
    if user is not None:
        pg["user"] = user
    if password is not None:
        pg["password"] = password
    if embedding_dim is not None:
        pg["embedding_dim"] = embedding_dim

    out["postgresql"] = pg
    return out


def _apply_backend_service_env(data: dict) -> dict:
    """env backend_service_port (или BACKEND_SERVICE_PORT) перекрывает urls.backend_service_port."""
    out = dict(data)
    url = (
        os.environ.get("backend_service_port")
        or os.environ.get("BACKEND_SERVICE_PORT")
        or ""
    ).strip()
    if url:
        be = dict(out.get("backend") or {})
        be["base_url"] = url.rstrip("/")
        out["backend"] = be
    return out


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"


class CorsConfig(BaseModel):
    allowed_origins: List[str] = Field(default_factory=list)
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
    base_url: str = Field(...)
    timeout: float = Field(...)
    # Сколько чанков отправлять за один POST /v1/embed (меньше → меньше пик RAM на svc-rag-models)
    embed_batch_size: int = int(os.environ.get("RAG_MODELS_CLIENT_EMBED_BATCH_SIZE", "24"))


class PostgreSQLConfig(BaseModel):
    host: str = Field(...)
    port: int = Field(...)
    database: str = Field(...)
    user: str = Field(...)
    password: str = Field(...)
    embedding_dim: int = Field(...)


class MinioConfig(BaseModel):
    endpoint: str = Field(...)
    port: int = Field(...)
    access_key: str = Field(...)
    secret_key: str = Field(...)
    use_ssl: bool = Field(...)
    bucket_name: str = Field(...)
    documents_bucket_name: str = Field(...)


class OcrConfig(BaseModel):
    url: str = Field(...)
    timeout: float = Field(...)


class RagServiceConfig(BaseModel):
    enabled: bool = True
    # Гибридный поиск: вектор + BM25
    use_hybrid_search: bool = os.environ.get("RAG_USE_HYBRID_SEARCH", "true").lower() == "true"
    hybrid_bm25_weight: float = float(os.environ.get("RAG_HYBRID_BM25_WEIGHT", "0.3"))
    # Диверсификация применяется только после weighted RRF и не использует
    # cosine-пороги (RRF и cosine имеют разные шкалы).
    hybrid_diversify_results: bool = (
        os.environ.get("RAG_HYBRID_DIVERSIFY_RESULTS", "true").lower() == "true"
    )
    hybrid_max_chunks_per_document: int = int(
        os.environ.get("RAG_HYBRID_MAX_CHUNKS_PER_DOCUMENT", "2")
    )
    # Реранкинг через SVC-RAG-MODELS
    use_reranking: bool = os.environ.get("RAG_USE_RERANKING", "false").lower() == "true"
    rerank_top_k: int = int(os.environ.get("RAG_RERANK_TOP_K", "20"))
    # Порог по финальному скору после реранка: 0.7*логит(CrossEncoder) + 0.3*cosine; не шкала 0..1.
    # 0 = не отсекать; положительные значения часто выкидывают все чанки — подбирайте с осторожностью.
    rerank_min_score: float = float(os.environ.get("RAG_RERANK_MIN_SCORE", "0"))
    sentence_window: int = int(os.environ.get("RAG_SENTENCE_WINDOW", "0"))
    chunk_size: int = 1000
    chunk_overlap: int = 200
    # Минимальный косинусный скор чанка после pgvector — отсекает явно нерелевантные результаты до реранка.
    # 0 = не фильтровать; типичные мультиязычные эмбеддинги дают релевантные чанки на 0.12–0.25,
    # поэтому порог выше 0.10 массово «съедает» правильные ответы. При всех чанках ниже порога
    # включится rescue top-N (см. filter_by_min_vector_similarity).
    min_vector_similarity: float = float(os.environ.get("RAG_MIN_VECTOR_SIMILARITY", "0.05"))
    # Минимальная длина чанка для low_signal-фильтра; 0 = не фильтровать.
    min_chunk_length: int = int(os.environ.get("RAG_MIN_CHUNK_LENGTH", "40"))

    # Иерархическое индексирование
    use_hierarchical_indexing: bool = os.environ.get("RAG_USE_HIERARCHICAL", "true").lower() == "true"
    hierarchical_threshold: int = int(os.environ.get("RAG_HIERARCHICAL_THRESHOLD", "10000"))
    hierarchical_chunk_size: int = int(os.environ.get("RAG_HIERARCHICAL_CHUNK_SIZE", "1500"))
    hierarchical_chunk_overlap: int = int(os.environ.get("RAG_HIERARCHICAL_CHUNK_OVERLAP", "200"))
    intermediate_summary_chunks: int = int(os.environ.get("RAG_INTERMEDIATE_SUMMARY_CHUNKS", "8"))
    create_full_summary_via_llm: bool = os.environ.get("RAG_CREATE_FULL_SUMMARY_VIA_LLM", "false").lower() == "true"
    enable_graph_rag: bool = os.environ.get("RAG_ENABLE_GRAPH", "true").lower() == "true"
    # Разрешить LLM-as-a-Judge в POST /search (доп. вызов llm-service; только при eval_llm_judge=true в теле)
    eval_llm_judge_allowed: bool = os.environ.get("RAG_EVAL_LLM_JUDGE_ALLOWED", "false").lower() == "true"


class LLMServiceConfig(BaseModel):
    base_url: str = Field(...)
    timeout: float = Field(...)
    default_model: str = Field(...)


class BackendServiceConfig(BaseModel):
    base_url: str = ""
    timeout: float = 120.0


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Эти секции содержат обязательные адреса/учётные данные. Не создаём их
    # пустыми при импорте модуля: значения сначала загружаются из config.yml/env,
    # затем Pydantic валидирует готовый словарь в ``from_yaml``.
    rag_models_client: RagModelsClientConfig
    postgresql: PostgreSQLConfig
    minio: MinioConfig
    ocr: OcrConfig
    llm_service: LLMServiceConfig

    rag: RagServiceConfig = Field(default_factory=RagServiceConfig)
    backend: BackendServiceConfig = Field(default_factory=BackendServiceConfig)

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
                raise ValueError(
                    "Файл config.yml не найден: настройки должны приходить из env Kubernetes или config.yml"
                )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data = _apply_urls_section(data)
            data = _apply_postgres_env_overrides(data)
            data = _apply_backend_service_env(data)
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Ошибка загрузки конфига {config_path}: {e}")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml(os.environ.get("CONFIG_PATH", ""))
    return _settings


def get_settings_diagnostics(settings_obj: Optional[Settings] = None) -> Dict[str, Any]:
    """Безопасная сводка фактически загруженной конфигурации для startup-логов.

    Функция намеренно не возвращает пароли, access/secret keys и другие секреты.
    Необязательный аргумент сохраняет совместимость с вызовами как
    ``get_settings_diagnostics()``, так и ``get_settings_diagnostics(settings)``.
    """
    cfg = settings_obj or get_settings()
    configured_path = (os.environ.get("CONFIG_PATH") or "").strip()
    return {
        "config_source": configured_path or "auto-discovered config.yml",
        "docker_runtime": _docker_runtime(),
        "server": {
            "host": cfg.server.host,
            "port": cfg.server.port,
        },
        "rag_models": {
            "base_url": cfg.rag_models_client.base_url,
            "timeout": cfg.rag_models_client.timeout,
            "embed_batch_size": cfg.rag_models_client.embed_batch_size,
        },
        "postgresql": {
            "host": cfg.postgresql.host,
            "port": cfg.postgresql.port,
            "database": cfg.postgresql.database,
            "user": cfg.postgresql.user,
            "embedding_dim": cfg.postgresql.embedding_dim,
        },
        "ocr": {
            "url": cfg.ocr.url,
            "timeout": cfg.ocr.timeout,
        },
        "llm_service": {
            "base_url": cfg.llm_service.base_url,
            "timeout": cfg.llm_service.timeout,
            "default_model": cfg.llm_service.default_model,
        },
        "backend": {
            "base_url": cfg.backend.base_url,
            "timeout": cfg.backend.timeout,
        },
        "rag": {
            "enabled": cfg.rag.enabled,
            "use_hybrid_search": cfg.rag.use_hybrid_search,
            "enable_graph_rag": cfg.rag.enable_graph_rag,
        },
    }


settings = get_settings()
