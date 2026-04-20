# Настройки сервиса: URL RAG-MODELS, PostgreSQL, размерность эмбеддингов
import os
import yaml
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import BaseModel

_settings = None


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
    "frontend_port_1",
    "frontend_port_1_ipv4",
    "frontend_port_2",
    "frontend_port_2_ipv4",
    "frontend_port_3",
    "frontend_port_3_ipv4",
    "backend_port_1",
    "backend_port_1_ipv4",
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

    cors = dict(out.get("cors") or {})
    ao = cors.get("allowed_origins")
    if not ao or ao == ["*"]:
        merged = [str(urls[k]).strip() for k in _URLS_CORS_KEYS if urls.get(k) and str(urls[k]).strip()]
        if merged:
            cors["allowed_origins"] = merged
    out["cors"] = cors
    out.pop("urls", None)
    return out


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"


class CorsConfig(BaseModel):
    allowed_origins: List[str] = []
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
    base_url: str = ""
    timeout: float = 60.0


class PostgreSQLConfig(BaseModel):
    host: str = os.environ.get("POSTGRES_HOST", "localhost")
    port: int = int(os.environ.get("POSTGRES_PORT", "5432"))
    database: str = os.environ.get("POSTGRES_DB", "astrachat")
    user: str = os.environ.get("POSTGRES_USER", "postgres")
    password: str = os.environ.get("POSTGRES_PASSWORD", "postgres")
    embedding_dim: int = int(os.environ.get("RAG_EMBEDDING_DIM", "384"))


class OcrConfig(BaseModel):
    url: str = ""
    timeout: float = 300.0


class RagServiceConfig(BaseModel):
    enabled: bool = True
    # Гибридный поиск: вектор + BM25
    use_hybrid_search: bool = os.environ.get("RAG_USE_HYBRID_SEARCH", "true").lower() == "true"
    hybrid_bm25_weight: float = float(os.environ.get("RAG_HYBRID_BM25_WEIGHT", "0.3"))
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
    base_url: str = ""
    timeout: float = 120.0
    default_model: str = "default"


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
            data = _apply_urls_section(data)
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Ошибка загрузки конфига {config_path}: {e}")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml(os.environ.get("CONFIG_PATH", ""))
    return _settings


settings = get_settings()
