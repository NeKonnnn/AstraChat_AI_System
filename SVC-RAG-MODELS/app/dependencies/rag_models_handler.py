# Загрузка моделей для RAG: эмбеддинги и реранкер.
# Можно использовать свои скачанные веса из models_dir, в офлайне — через HF_HUB_OFFLINE.
import os
import logging
from typing import List, Optional, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_rag_models: Optional[dict] = None
_last_rag_models_error: Optional[str] = None


def _resolve_model_path(models_dir: str, name_or_path: Optional[str], default_hf: str) -> str:
    # Если есть локальная папка — возвращаем полный путь, иначе имя модели с HF.
    if not name_or_path:
        return default_hf
    if os.path.isabs(name_or_path) and os.path.isdir(name_or_path):
        return name_or_path
    full = os.path.join(models_dir, name_or_path)
    if os.path.isdir(full):
        return full
    # Поиск по началу имени: ms-marco... или paraphrase-multilingual...
    try:
        for entry in os.listdir(models_dir):
            if not os.path.isdir(os.path.join(models_dir, entry)):
                continue
            if name_or_path.startswith("ms-marco") and entry.startswith("ms-marco"):
                return os.path.join(models_dir, entry)
            if name_or_path.startswith("paraphrase-multilingual") and entry.startswith("paraphrase-multilingual"):
                return os.path.join(models_dir, entry)
    except OSError:
        pass
    # Вариант кэша HuggingFace: cross-encoder/ms-marco-... → cross-encoder--ms-marco-...
    if "marco" in name_or_path.lower() or "cross-encoder" in default_hf.lower():
        alt_name = default_hf.replace("/", "--")
        alt_full = os.path.join(models_dir, alt_name)
        if os.path.isdir(alt_full):
            # Кэш HF: внутри есть snapshots/<hash>/ — нужен путь к snapshot
            snap_dir = os.path.join(alt_full, "snapshots")
            if os.path.isdir(snap_dir):
                for h in os.listdir(snap_dir):
                    snap_path = os.path.join(snap_dir, h)
                    if os.path.isdir(snap_path) and os.path.isfile(os.path.join(snap_path, "config.json")):
                        return snap_path
            return alt_full
        for entry in os.listdir(models_dir):
            if "ms-marco" in entry.lower() or "minilm-l-6" in entry.lower():
                candidate = os.path.join(models_dir, entry)
                if os.path.isdir(candidate):
                    snap_dir = os.path.join(candidate, "snapshots")
                    if os.path.isdir(snap_dir):
                        for h in os.listdir(snap_dir):
                            snap_path = os.path.join(snap_dir, h)
                            if os.path.isdir(snap_path) and os.path.isfile(os.path.join(snap_path, "config.json")):
                                return snap_path
                    return candidate
    return name_or_path  # пусть библиотека сама разберётся (HF или путь)


async def get_rag_models_handler() -> Optional[dict]:
    # Поднимаем эмбеддинг-модель и реранкер. Кэш/локальные пути — в models_dir.
    # offline=True чтобы вообще не лезть в интернет.
    global _rag_models, _last_rag_models_error
    _last_rag_models_error = None

    if not settings.rag_models.enabled:
        logger.info("RAG-модели выключены в конфиге")
        return None

    if _rag_models is not None:
        return _rag_models

    try:
        models_dir = os.path.abspath(settings.rag_models.models_dir)
        os.makedirs(models_dir, exist_ok=True)

        # Весь кэш HF и sentence-transformers складываем в одну папку
        os.environ["HF_HOME"] = models_dir
        os.environ["HF_HUB_CACHE"] = models_dir
        os.environ["TRANSFORMERS_CACHE"] = models_dir

        if settings.rag_models.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            logger.info("RAG models: офлайн, в сеть не ходим")

        device = settings.rag_models.device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        logger.info(f"RAG models устройство: {device}")

        # Путь к модели: либо папка внутри models_dir, либо имя с HuggingFace
        embedding_model = _resolve_model_path(
            models_dir,
            settings.rag_models.embedding_model,
            settings.rag_models.embedding_model_default,
        )
        reranker_model = _resolve_model_path(
            models_dir,
            settings.rag_models.reranker_model,
            settings.rag_models.reranker_model_default,
        )

        # В офлайне реранкер обязан грузиться с диска
        if settings.rag_models.offline and not os.path.isdir(reranker_model):
            raise FileNotFoundError(
                f"Реранкер в офлайне не найден по пути: {reranker_model}. "
                f"Проверьте, что в {models_dir} есть папка ms-marco-MiniLM-L-6-v2 (или начинается с ms-marco)."
            )

        # Грузим эмбеддинги (sentence-transformers)
        from sentence_transformers import SentenceTransformer

        logger.info(f"Гружу эмбеддинг-модель: {embedding_model}")
        embedding_model_obj = SentenceTransformer(embedding_model, device=device)
        logger.info("Эмбеддинг-модель загружена")

        # Грузим реранкер (CrossEncoder)
        from sentence_transformers import CrossEncoder

        logger.info(f"Гружу реранкер: {reranker_model}")
        reranker_model_obj = CrossEncoder(reranker_model, device=device)
        logger.info("Реранкер загружен")

        _rag_models = {
            "embedding_model": embedding_model_obj,
            "reranker_model": reranker_model_obj,
            "device": device,
            "embedding_dim": settings.rag_models.embedding_dim,
        }
        return _rag_models
    except Exception as e:
        _last_rag_models_error = str(e)
        logger.error(f"Не удалось загрузить RAG-модели: {e}", exc_info=True)
        return None


def get_last_rag_models_error() -> Optional[str]:
    """Текст последней ошибки загрузки RAG-моделей (для логов при старте)."""
    return _last_rag_models_error


async def cleanup_rag_models_handler() -> None:
    global _rag_models
    if _rag_models is not None:
        logger.info("Выгружаю RAG-модели")
        _rag_models = None
