# Загрузка моделей для RAG: эмбеддинги и реранкер — только локальные веса из models_dir
import gc
import os
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_rag_models: Optional[dict] = None
_last_rag_models_error: Optional[str] = None


def _free_model_memory() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _is_giga_embed_path(model_path: str) -> bool:
    n = (model_path or "").replace("\\", "/").lower()
    if "giga" in n and "embed" in n:
        return True
    cfg_path = os.path.join(model_path, "config.json") if model_path else ""
    if not cfg_path or not os.path.isfile(cfg_path):
        return False
    try:
        import json

        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("model_type") or "").lower() == "gigarembed"
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _register_giga_remote_code(model_path: str) -> None:
    """Импорт modeling_gigarembed.py — регистрирует LatentAttentionConfig в AutoModel.

    Без этого GigarEmbedModel.__init__ падает:
    Unrecognized configuration class LatentAttentionConfig for AutoModel.
    """
    try:
        from transformers import AutoModel
        from transformers.dynamic_module_utils import get_class_from_dynamic_module

        latent_cfg = get_class_from_dynamic_module(
            "configuration_gigarembed.LatentAttentionConfig",
            model_path,
            trust_remote_code=True,
        )
        latent_model = get_class_from_dynamic_module(
            "modeling_gigarembed.LatentAttentionModel",
            model_path,
            trust_remote_code=True,
        )
        gigar_cfg = get_class_from_dynamic_module(
            "configuration_gigarembed.GigarEmbedConfig",
            model_path,
            trust_remote_code=True,
        )
        gigar_model = get_class_from_dynamic_module(
            "modeling_gigarembed.GigarEmbedModel",
            model_path,
            trust_remote_code=True,
        )
        # Явная регистрация (на случай если в локальной копии modeling нет register)
        for cfg, mdl in (
            (latent_cfg, latent_model),
            (gigar_cfg, gigar_model),
        ):
            try:
                AutoModel.register(cfg, mdl, exist_ok=True)
            except TypeError:
                try:
                    AutoModel.register(cfg, mdl)
                except ValueError:
                    pass  # уже зарегистрировано
        logger.info("Giga: LatentAttention/GigarEmbed зарегистрированы в AutoModel")
    except Exception as e:
        logger.warning("Giga: предрегистрация remote-code не удалась: %s", e)


def _load_sentence_transformer(model_path: str, device: str):
    """SentenceTransformer с корректным trust_remote_code для Giga и др."""
    import torch
    from sentence_transformers import SentenceTransformer

    if _is_giga_embed_path(model_path):
        _register_giga_remote_code(model_path)

    model_kwargs: dict = {"trust_remote_code": True}
    config_kwargs: dict = {"trust_remote_code": True}
    if device.startswith("cuda"):
        model_kwargs["torch_dtype"] = (
            torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        )
    else:
        model_kwargs["torch_dtype"] = torch.float32

    # Официальный способ для Giga-Embeddings-instruct (README):
    # trust_remote_code и в model_kwargs, и в config_kwargs.
    return SentenceTransformer(
        model_path,
        device=device,
        trust_remote_code=True,
        local_files_only=True,
        model_kwargs=model_kwargs,
        config_kwargs=config_kwargs,
    )


def _resolve_model_path(
    models_dir: str, name_or_path: Optional[str], default_local: str
) -> str:
    # Только локальные папки в models_dir (имя из ConfigMap / settings).
    if not name_or_path:
        name_or_path = default_local
    name_or_path = name_or_path.strip()
    # org/model → последняя компонента (на случай старых значений)
    if "/" in name_or_path and not os.path.isabs(name_or_path):
        name_or_path = name_or_path.split("/")[-1]
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
            if name_or_path.startswith("paraphrase-multilingual") and entry.startswith(
                "paraphrase-multilingual"
            ):
                return os.path.join(models_dir, entry)
            if name_or_path.startswith("bge-reranker") and entry.startswith(
                "bge-reranker"
            ):
                if (
                    name_or_path.lower() in entry.lower()
                    or entry.lower() in name_or_path.lower()
                ):
                    return os.path.join(models_dir, entry)
    except OSError:
        pass
    # Локальный snapshot-layout: models--org--name/snapshots/<hash>/
    folder = name_or_path
    try:
        for entry in os.listdir(models_dir):
            entry_l = entry.lower()
            if folder.lower() not in entry_l and entry_l not in folder.lower():
                continue
            candidate = os.path.join(models_dir, entry)
            if not os.path.isdir(candidate):
                continue
            snap_dir = os.path.join(candidate, "snapshots")
            if os.path.isdir(snap_dir):
                for h in os.listdir(snap_dir):
                    snap_path = os.path.join(snap_dir, h)
                    if os.path.isdir(snap_path) and os.path.isfile(
                        os.path.join(snap_path, "config.json")
                    ):
                        return snap_path
            if os.path.isfile(os.path.join(candidate, "config.json")):
                return candidate
    except OSError:
        pass
    return full


async def get_rag_models_handler() -> Optional[dict]:
    # Поднимаем эмбеддинг-модель и реранкер. Кэш/локальные пути - в models_dir.
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
        try:
            os.makedirs(models_dir, exist_ok=True)
        except OSError:
            # models_dir часто смонтирован :ro — веса уже на месте, кэш пишем отдельно
            pass

        # Веса читаем из models_dir (может быть read-only).
        # Рабочий кэш transformers (modules для trust_remote_code) — в writable path.
        # Имена HF_* — это переменные библиотеки transformers, не провайдер моделей.
        cache_root = (
            os.environ.get("TRANSFORMERS_CACHE")
            or os.environ.get("HF_HOME")
            or "/tmp/rag-models-cache"
        )
        cache_paths = {
            "HF_HOME": cache_root,
            "HF_HUB_CACHE": os.path.join(cache_root, "hub"),
            "TRANSFORMERS_CACHE": os.path.join(cache_root, "transformers"),
            "SENTENCE_TRANSFORMERS_HOME": os.path.join(
                cache_root, "sentence-transformers"
            ),
        }
        try:
            for cache_path in cache_paths.values():
                os.makedirs(cache_path, exist_ok=True)
        except OSError as cache_err:
            logger.warning(
                "Кэш transformers '%s' недоступен на запись (%s) - оставляю models_dir. "
                "Для MiniCPM/Giga (trust_remote_code) нужен writable /tmp.",
                cache_root,
                cache_err,
            )
            cache_paths = {
                "HF_HOME": models_dir,
                "HF_HUB_CACHE": models_dir,
                "TRANSFORMERS_CACHE": models_dir,
            }
        os.environ.update(cache_paths)
        # Всегда без сетевых загрузок — только локальные веса
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        logger.info("Кэш transformers: %s (offline)", os.environ["HF_HOME"])

        device = settings.rag_models.device
        if device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        logger.info(f"RAG models устройство: {device}")

        # Путь к модели: подпапка внутри models_dir
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
                f"Проверьте, что в {models_dir} есть папка {settings.rag_models.reranker_model} "
                "(например bge-reranker-v2-minicpm-layerwise или ms-marco-...)."
            )

        # Грузим эмбеддинги (sentence-transformers)
        logger.info(f"Гружу эмбеддинг-модель: {embedding_model}")
        embedding_model_obj = _load_sentence_transformer(embedding_model, device)
        logger.info("Эмбеддинг-модель загружена")
        # Реальная размерность модели (не конфиг по умолчанию 384)
        try:
            detected_dim = int(embedding_model_obj.get_sentence_embedding_dimension())
        except Exception:
            detected_dim = int(settings.rag_models.embedding_dim or 384)
        if detected_dim > 0:
            settings.rag_models.embedding_dim = detected_dim
        logger.info("Размерность эмбеддингов: %s", detected_dim)

        # LLM-реранкеры (MiniCPM layerwise / Gemma) ≠ CrossEncoder
        from app.services.llm_reranker import is_llm_reranker_path, load_llm_reranker

        logger.info(f"Гружу реранкер: {reranker_model}")
        if is_llm_reranker_path(reranker_model):
            reranker_model_obj = load_llm_reranker(reranker_model, device=device)
        else:
            from sentence_transformers import CrossEncoder

            # ST 5.x: local_files_only — top-level; в model_kwargs даёт
            # TypeError/KeyError («multiple values» / 'local_files_only').
            try:
                reranker_model_obj = CrossEncoder(
                    reranker_model,
                    device=device,
                    trust_remote_code=True,
                    local_files_only=True,
                )
            except TypeError:
                # Старые ST: automodel_args / tokenizer_args
                try:
                    reranker_model_obj = CrossEncoder(
                        reranker_model,
                        device=device,
                        trust_remote_code=True,
                        automodel_args={"local_files_only": True},
                        tokenizer_args={"local_files_only": True},
                    )
                except TypeError:
                    reranker_model_obj = CrossEncoder(
                        reranker_model,
                        device=device,
                        trust_remote_code=True,
                        model_kwargs={"trust_remote_code": True},
                        tokenizer_kwargs={"trust_remote_code": True},
                    )
        logger.info("Реранкер загружен")

        _rag_models = {
            "embedding_model": embedding_model_obj,
            "reranker_model": reranker_model_obj,
            "device": device,
            "embedding_dim": detected_dim,
        }
        return _rag_models
    except Exception as e:
        _last_rag_models_error = str(e)
        logger.error(f"Не удалось загрузить RAG-модели: {e}", exc_info=True)
        _free_model_memory()
        return None


def get_last_rag_models_error() -> Optional[str]:
    """Текст последней ошибки загрузки RAG-моделей (для логов при старте)."""
    return _last_rag_models_error


async def cleanup_rag_models_handler() -> None:
    global _rag_models
    if _rag_models is not None:
        logger.info("Выгружаю RAG-модели")
        _rag_models = None
    _free_model_memory()
