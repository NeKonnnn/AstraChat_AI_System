"""
LLM Client для взаимодействия с микросервисами AI (LLM, STT, TTS, OCR, Diarization).

Начиная с рефакторинга на ``backend/llm_providers`` все LLM-методы
(``chat_completion``, ``stream_generation``, ``health_check``, ``get_models``,
``load_model``, ``load_model_if_needed``, ``unload_excess_llm_models``) — это
тонкие адаптеры над ``ProviderRegistry``. STT/TTS/OCR/Diarization остаются
как были, они не относятся к LLM.
"""

import httpx
import json
import asyncio
import logging
import re
import html as html_module
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator, Tuple
from datetime import datetime
import io
import os

from backend.llm_providers import (
    LLMProvider,
    ModelInfo,
    ProviderHealth,
    ProviderRegistry,
    get_registry,
    get_registry_sync_or_none,
    split_model_path,
)
from backend.llm_providers.llm_svc import LlmSvcProvider, pool_contains_model, same_llm_svc_model_id
from backend.llm_providers.openai_compat import clean_llm_response as _clean_llm_response_new


def resolve_llm_svc_model_id_for_request(model_path: Optional[str], fallback_model_name: str) -> str:
    """
    Legacy-API: получает model_id из произвольной ссылки на модель.

    Теперь это просто обёртка над ``split_model_path`` из ``llm_providers``:

    - ``llm-svc://host/model`` / ``llm-svc://model`` / ``provider_id/model`` → model_id;
    - плоский ``model`` → он же.

    Возвращает ``fallback_model_name``, если path пуст.
    """
    if not model_path or not str(model_path).strip():
        return fallback_model_name
    _, mid = split_model_path(str(model_path))
    return mid or fallback_model_name


def infer_llm_host_for_openai_model_id(
    model_id: str,
    llm_hosts: Dict[str, str],
    default_host_id: str,
) -> Tuple[str, str]:
    """Legacy: возвращает (default_host_id, model_id). Новый код напрямую использует registry."""
    mid = (model_id or "").strip()
    if not mid:
        return default_host_id, mid
    return default_host_id, mid


def resolve_llm_host_and_model_for_svc(
    model_ref: Optional[str],
    fallback_model: str,
    llm_hosts: Dict[str, str],
    default_host_id: Optional[str],
) -> Tuple[str, str]:
    """
    Legacy-API: разбирает ``<provider_id>/<model_id>`` или ``llm-svc://...`` и
    возвращает ``(provider_id, model_id)``.

    Новый код должен использовать ``registry.resolve(path)`` напрямую.
    Эта функция оставлена для обратной совместимости ``agent_llm_svc``.
    """
    fb = (fallback_model or "").strip() or "qwen-coder-30b"
    default_h = default_host_id if default_host_id and default_host_id in (llm_hosts or {}) else (
        next(iter(llm_hosts)) if llm_hosts else "default"
    )
    if not model_ref or not str(model_ref).strip():
        return default_h, fb

    head, tail = split_model_path(str(model_ref))
    if head and (not llm_hosts or head in llm_hosts):
        return head, (tail or fb)
    if head and llm_hosts and head not in llm_hosts:
        # Head существует, но не зарегистрирован в legacy-словаре → пусть регистратор
        # (если есть) сам решает. Для legacy-вызывающих возвращаем default + склейку.
        combined = f"{head}/{tail}" if tail else head
        return default_h, combined
    return default_h, (tail or fb)


# Алиас на новую реализацию — чтобы legacy-импорт "_clean_llm_response" сохранил работу.
_clean_llm_response = _clean_llm_response_new

# Импортируем настройки 
try:
    from settings import get_settings
except ImportError:
    from backend.settings import get_settings

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для взаимодействия с распределенными API сервисов"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        # Получаем настройки из синглтона 
        settings = get_settings()
        
        # Определяем URL-адреса для каждого сервиса
        # Если передан base_url (в старом коде), считаем его LLM-адресом
        if base_url:
            self.llm_url = base_url.rstrip('/')
        else:
            self.llm_url = settings.get_llm_service_url().rstrip('/')

        self.stt_url = settings.microservice_http_base("stt_service_docker", "stt_service_port")
        self.tts_url = settings.microservice_http_base("tts_service_docker", "tts_service_port")
        self.ocr_url = settings.microservice_http_base("ocr_service_docker", "ocr_service_port")
        self.diarization_url = settings.microservice_http_base(
            "diarization_service_docker", "diarization_service_port"
        )
        
        # Проверка на опечатки в LLM URL
        if "1lm-svc" in self.llm_url or "11m-svc" in self.llm_url:
            logger.error(f"ОБНАРУЖЕНА ОПЕЧАТКА В URL: {self.llm_url}. Исправляем.")
            self.llm_url = self.llm_url.replace("1lm-svc", "llm-svc").replace("11m-svc", "llm-svc")

        # Несколько инстансов LLM: id -> base_url (из settings.llm_service.hosts)
        self.llm_hosts: Dict[str, str] = {}
        try:
            cfg_hosts = getattr(settings.llm_service, "hosts", None) or []
            for entry in cfg_hosts:
                if entry is None:
                    continue
                if hasattr(entry, "id") and hasattr(entry, "base_url"):
                    hid, bu = entry.id, entry.base_url
                elif isinstance(entry, dict):
                    hid, bu = entry.get("id"), entry.get("base_url")
                else:
                    continue
                if hid and bu:
                    self.llm_hosts[str(hid)] = str(bu).rstrip("/")
        except Exception as e:
            logger.warning(f"LLM hosts из конфига не разобраны: {e}")
        if not self.llm_hosts:
            self.llm_hosts = {"default": self.llm_url}
        dh = getattr(settings.llm_service, "default_host_id", None)
        self.default_llm_host: str = dh if dh and dh in self.llm_hosts else next(iter(self.llm_hosts))
        self.llm_url = self.llm_hosts[self.default_llm_host]
        
        logger.info(f"LLMClient инициализирован. Маршруты:")
        logger.info(
            f"  LLM: {self.llm_url} (hosts={list(self.llm_hosts.keys())}, default_host={self.default_llm_host}) | "
            f"STT: {self.stt_url} | TTS: {self.tts_url}"
        )
            
        self.api_key = api_key
        # Берем таймаут из конфига LLM сервиса для совместимости
        try:
            self.timeout = settings.llm_service.timeout
        except:
            self.timeout = 120.0
        
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _url_for_llm_host(self, host_id: Optional[str] = None) -> str:
        """Legacy: base_url по host_id. Если registry готов — берём оттуда."""
        r = get_registry_sync_or_none()
        if r is not None:
            try:
                return r.get(host_id).base_url
            except Exception:
                pass
        hid = host_id if host_id and host_id in self.llm_hosts else self.default_llm_host
        return self.llm_hosts.get(hid) or self.llm_url

    async def _get_provider(self, host_id: Optional[str] = None) -> LLMProvider:
        """Единая точка получения провайдера с учётом legacy host_id."""
        r = await get_registry()
        return r.get(host_id)

    # --- МЕТОДЫ LLM (делегируют в ProviderRegistry) ---

    async def health_check(self, host_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Проверка состояния LLM-провайдера. Возвращает dict с ключами
        ``status``, ``loaded_models``, ``model_loaded``, ``model_name`` —
        совместимый с legacy-вызывающими.
        """
        try:
            provider = await self._get_provider(host_id)
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
        h: ProviderHealth = await provider.health()
        result: Dict[str, Any] = {
            "status": "healthy" if h.healthy else "unhealthy",
            "loaded_models": list(h.loaded_models),
            "model_loaded": bool(h.loaded_models),
            "model_name": h.loaded_models[0] if h.loaded_models else None,
        }
        if h.error:
            result["error"] = h.error
        if h.raw:
            result.setdefault("raw", h.raw)
        return result

    async def get_models(self, host_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Список моделей одного провайдера (legacy: только один host)."""
        try:
            provider = await self._get_provider(host_id)
        except Exception as e:
            logger.error("get_models(%s) registry error: %s", host_id, e)
            return []
        models: List[ModelInfo] = await provider.list_models()
        # Формат, совместимый с legacy-вызывающими: список dict c "id" и "name".
        return [
            {
                "id": m.model_id,
                "name": m.display_name or m.model_id,
                "provider_id": m.provider_id,
                **(m.extra or {}),
            }
            for m in models
        ]

    async def load_model(self, model_name: str, host_id: Optional[str] = None) -> bool:
        """Загрузить/переключить модель — делегирует в ``provider.ensure_model_loaded``."""
        if not model_name or not model_name.strip():
            logger.warning("load_model: пустое имя модели")
            return False
        provider = await self._get_provider(host_id)
        return await provider.ensure_model_loaded(model_name.strip())

    async def load_model_if_needed(self, model_name: str, host_id: Optional[str] = None) -> bool:
        """Синоним ``load_model`` — ``ensure_model_loaded`` уже no-op если модель в пуле."""
        return await self.load_model(model_name, host_id=host_id)

    async def unload_excess_llm_models(self, host_id: Optional[str] = None) -> bool:
        """
        Очистка пула llm-svc. Для провайдеров, где пула нет (vLLM/Ollama/OpenAI)
        возвращает True (нечего выгружать).
        """
        try:
            registry = await get_registry()
        except Exception as e:
            logger.error("unload_excess_llm_models: registry error: %s", e)
            return False
        targets: List[LLMProvider] = (
            [registry.get(host_id)] if host_id else [p for p in registry.all() if isinstance(p, LlmSvcProvider)]
        )
        ok_all = True
        for p in targets:
            if isinstance(p, LlmSvcProvider):
                if not await p.unload_excess():
                    ok_all = False
        return ok_all

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-coder-30b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        host_id: Optional[str] = None,
    ) -> Any:
        """
        Non-streaming chat. Возвращает OpenAI-style dict ``{"choices": [...]}``
        для совместимости с legacy-вызывающими.
        """
        provider = await self._get_provider(host_id)
        content = await provider.chat(
            messages=messages, model=model, temperature=temperature, max_tokens=max_tokens,
        )
        return {
            "choices": [{"message": {"role": "assistant", "content": content}, "index": 0, "finish_reason": "stop"}],
            "model": model,
        }
    async def get_transcription_health(self) -> Dict[str, Any]:
        """Проверка состояния STT (WhisperX)"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.stt_url}/v1/whisperx/health")
                if response.status_code == 200:
                    return response.json()
                return {"status": "unhealthy", "code": response.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_tts_health(self) -> Dict[str, Any]:
        """Проверка состояния TTS сервиса"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.tts_url}/v1/health")
                if response.status_code == 200:
                    return response.json()
                return {"status": "unhealthy", "code": response.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # ==========================================
    # STT МЕТОДЫ (ИСПОЛЬЗУЮТ self.stt_url)
    # ==========================================

    async def transcribe_audio_whisperx(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "auto",
        compute_type: str = "float16",
        batch_size: int = 16,
        word_timestamps: bool = True,
    ) -> Dict[str, Any]:
        """Транскрибация аудио файла через WhisperX.
        word_timestamps=True запрашивает временны́е метки на уровне слов —
        они нужны для точного сопоставления со спикерами (аналог assign_word_speakers).
        """
        try:
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                ".wav": "audio/wav", ".webm": "audio/webm", ".ogg": "audio/ogg",
                ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".flac": "audio/flac",
            }
            content_type = content_type_map.get(ext, "audio/wav")
            files = {"file": (filename, io.BytesIO(audio_file), content_type)}
            data = {
                "language": language,
                "compute_type": compute_type,
                "batch_size": batch_size,
                "word_timestamps": str(word_timestamps).lower(),
            }
            
            # Таймаут 5 часов
            whisperx_timeout = httpx.Timeout(18000.0, connect=10.0, read=18000.0, write=60.0)
            async with httpx.AsyncClient(timeout=whisperx_timeout) as client:
                response = await client.post(
                    f"{self.stt_url}/v1/whisperx/transcribe",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка транскрибации WhisperX: {e}")
            raise

    async def reload_whisperx_models(self) -> Dict[str, Any]:
        """Принудительная перезагрузка моделей WhisperX"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.stt_url}/v1/whisperx/reload",
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка перезагрузки WhisperX: {e}")
            raise

    # ==========================================
    # TTS МЕТОДЫ (ИСПОЛЬЗУЮТ self.tts_url)
    # ==========================================

    async def synthesize_speech(
        self,
        text: str,
        language: str = "auto",
        speaker: str = "baya",
        sample_rate: int = 48000,
        speech_rate: float = 1.0
    ) -> bytes:
        """Синтез речи Silero"""
        try:
            data = {
                "text": text,
                "language": language,
                "speaker": speaker,
                "sample_rate": sample_rate,
                "speech_rate": speech_rate
            }
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.tts_url}/v1/synthesize",
                    data=data,
                    headers={"Accept": "audio/wav"}
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Ошибка синтеза речи: {e}")
            raise

    # ==========================================
    # DIARIZATION МЕТОДЫ (ИСПОЛЬЗУЮТ self.diarization_url)
    # ==========================================

    async def diarize_audio(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        min_speakers: int = 1,
        max_speakers: int = 10,
        min_duration: float = 0.5
    ) -> Dict[str, Any]:
        """Диаризация Pyannote"""
        try:
            files = {"file": (filename, io.BytesIO(audio_file), "audio/wav")}
            data = {"min_speakers": min_speakers, "max_speakers": max_speakers, "min_duration": min_duration}
            
            # Таймаут 5 часов
            diarize_timeout = httpx.Timeout(18000.0, connect=10.0, read=18000.0, write=60.0)
            async with httpx.AsyncClient(timeout=diarize_timeout) as client:
                response = await client.post(
                    f"{self.diarization_url}/v1/diarize",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка диаризации: {e}")
            raise

    async def transcribe_with_diarization(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "auto",
        min_speakers: int = 1,
        max_speakers: int = 10,
        min_duration: float = 0.5,
        engine: str = "whisperx",
    ) -> Dict[str, Any]:
        """
        Комбинированная транскрибация с диаризацией.
        Шаг 1: диаризация (diarization-service) → сегменты по спикерам.
        Шаг 2: транскрипция (stt-service) → текст с временными метками.
        Шаг 3: сопоставление по времени → segments[{speaker, text, start, end}].
        Возвращает {success, text, segments, speakers_count}.
        """
        try:
            long_timeout = httpx.Timeout(18000.0, connect=10.0, read=18000.0, write=60.0)
            
            # Шаг 1: Диаризация
            # min_duration=0.5 — позволяет детектировать короткие реплики (< 1 сек),
            # например "Да, всем добрый день." в начале разговора.
            logger.info(f"[transcribe_with_diarization] Шаг 1: диаризация... engine={engine}")
            diarization_result = await self.diarize_audio(
                audio_file, filename=filename,
                min_speakers=min_speakers, max_speakers=max_speakers,
                min_duration=min_duration
            )
            
            diar_segments = diarization_result.get("segments", [])
            if not diar_segments:
                logger.warning("[transcribe_with_diarization] Диаризация не нашла сегментов")
                return {"success": True, "text": "", "segments": [], "speakers_count": 0}
            
            # Шаг 2: Транскрипция
            logger.info(f"[transcribe_with_diarization] Шаг 2: транскрипция (WhisperX, запрошенный engine={engine})...")
            transcription_result = await self.transcribe_audio_whisperx(
                audio_file, filename=filename, language=language
            )

            full_text = (
                transcription_result.get("text", "")
                if isinstance(transcription_result, dict)
                else str(transcription_result)
            )
            
            # Шаг 3: Сопоставление сегментов STT и диаризации по времени
            stt_segments = transcription_result.get("segments", []) if isinstance(transcription_result, dict) else []
            has_timestamps = (
                len(stt_segments) > 0
                and all(
                    isinstance(s.get("start"), (int, float)) and isinstance(s.get("end"), (int, float))
                    for s in stt_segments
                )
            )
            
            if has_timestamps:
                diar_sorted = sorted(diar_segments, key=lambda s: s.get("start", 0))

                # Проверяем, есть ли word-level timestamps (приходят от WhisperX как
                # segment["words"] = [{word, start, end}, ...]).
                # Если есть — сопоставляем каждое слово со спикером, затем собираем
                # сегменты (аналог whisperx.assign_word_speakers).
                # Если нет — fallback: max-overlap на уровне сегментов.
                all_words = []
                for stt in stt_segments:
                    words = stt.get("words") or []
                    for w in words:
                        if isinstance(w, dict) and "start" in w and "end" in w and w.get("word"):
                            all_words.append(w)

                if all_words:
                    # --- Word-level сопоставление (точный аналог assign_word_speakers) ---
                    raw_parts = []  # (start, end, speaker, word)
                    for w in all_words:
                        w_start = float(w.get("start", 0))
                        w_end = float(w.get("end", 0))
                        word_text = (w.get("word") or "").strip()
                        if not word_text:
                            continue
                        best_speaker = "SPEAKER_0"
                        best_overlap = 0.0
                        for d in diar_sorted:
                            d_start = float(d.get("start", 0))
                            d_end = float(d.get("end", 0))
                            overlap = max(0.0, min(w_end, d_end) - max(w_start, d_start))
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_speaker = d.get("speaker", "SPEAKER_0")
                        raw_parts.append((w_start, w_end, best_speaker, word_text))

                    # Собираем слова в сегменты: слова одного спикера подряд → один сегмент
                    result_segments = []
                    for w_start, w_end, speaker, word_text in raw_parts:
                        if result_segments and result_segments[-1]["speaker"] == speaker:
                            result_segments[-1]["text"] += " " + word_text
                            result_segments[-1]["end"] = w_end
                        else:
                            result_segments.append({
                                "start": w_start,
                                "end": w_end,
                                "speaker": speaker,
                                "text": word_text,
                            })
                    logger.info(f"[transcribe_with_diarization] Word-level сопоставление: {len(result_segments)} сегментов")
                else:
                    # --- Segment-level: разбиваем каждый STT-сегмент по границам диаризации,
                    # затем объединяем смежные части одного спикера в один блок. ---
                    raw_parts = []  # (start, end, speaker, text_fragment)
                    for stt in stt_segments:
                        t_start = float(stt.get("start", 0))
                        t_end = float(stt.get("end", 0))
                        text = (stt.get("text") or "").strip()
                        if not text:
                            continue

                        overlapping = sorted([
                            (float(d.get("start", 0)), float(d.get("end", 0)),
                             d.get("speaker", "SPEAKER_0"),
                             max(0.0, min(t_end, float(d.get("end", 0))) - max(t_start, float(d.get("start", 0)))))
                            for d in diar_sorted
                            if max(0.0, min(t_end, float(d.get("end", 0))) - max(t_start, float(d.get("start", 0)))) > 0
                        ], key=lambda x: x[0])

                        if not overlapping:
                            nearest = min(diar_sorted, key=lambda d: abs(float(d.get("start", 0)) - t_start))
                            raw_parts.append((t_start, t_end, nearest.get("speaker", "SPEAKER_0"), text))
                            continue

                        if len(overlapping) == 1:
                            raw_parts.append((t_start, t_end, overlapping[0][2], text))
                        else:
                            # Делим текст пропорционально времени каждого спикера
                            total_overlap = sum(o for _, _, _, o in overlapping)
                            words_list = text.split()
                            word_idx = 0
                            for i, (d_start, d_end, speaker, overlap) in enumerate(overlapping):
                                if i == len(overlapping) - 1:
                                    chunk = words_list[word_idx:]
                                else:
                                    count = max(1, round(len(words_list) * overlap / total_overlap))
                                    chunk = words_list[word_idx:word_idx + count]
                                    word_idx += len(chunk)
                                chunk_text = " ".join(chunk).strip()
                                if chunk_text:
                                    raw_parts.append((d_start, d_end, speaker, chunk_text))

                    # Объединяем смежные части одного спикера в один блок
                    result_segments = []
                    for p_start, p_end, speaker, text in sorted(raw_parts, key=lambda x: x[0]):
                        if result_segments and result_segments[-1]["speaker"] == speaker:
                            result_segments[-1]["text"] += " " + text
                            result_segments[-1]["end"] = p_end
                        else:
                            result_segments.append({"start": p_start, "end": p_end, "speaker": speaker, "text": text})
                    logger.info(f"[transcribe_with_diarization] Segment+split+merge: {len(result_segments)} сегментов")
            else:
                # Fallback: распределяем текст по сегментам диаризации пропорционально длительности
                total_duration = sum(s.get("duration", s.get("end", 0) - s.get("start", 0)) for s in diar_segments)
                words = full_text.split() if full_text else []
                total_words = len(words)
                result_segments = []
                word_idx = 0
                for seg in diar_segments:
                    seg_duration = seg.get("duration", seg.get("end", 0) - seg.get("start", 0))
                    word_count = max(1, round(total_words * seg_duration / total_duration)) if total_duration > 0 else total_words
                    seg_words = words[word_idx:word_idx + word_count]
                    word_idx += word_count
                    result_segments.append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "speaker": seg.get("speaker", "SPEAKER_0"),
                        "text": " ".join(seg_words),
                    })
                if word_idx < total_words and result_segments:
                    result_segments[-1]["text"] += " " + " ".join(words[word_idx:])
                logger.info(f"[transcribe_with_diarization] Fallback по длительности: {len(diar_segments)} сегментов")
            
            return {
                "success": True,
                "text": full_text,
                "segments": result_segments,
                "speakers_count": diarization_result.get("speakers_count", 0)
            }
            
        except Exception as e:
            logger.error(f"[transcribe_with_diarization] Ошибка: {e}")
            raise

    # ==========================================
    # OCR - запросы идут в ocr-service (Surya), не в LLM (self.ocr_url)
    # ==========================================

    async def recognize_text_from_image(
        self,
        image_file: bytes,
        filename: str = "image.jpg",
        languages: str = "ru,en"
    ) -> Dict[str, Any]:
        """Распознавание текста с изображения: POST в ocr-service (Surya), не в LLM."""
        try:
            mime = "image/jpeg"
            if filename.lower().endswith(".png"): mime = "image/png"
            
            files = {"file": (filename, io.BytesIO(image_file), mime)}
            data = {"languages": languages}
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.ocr_url}/v1/ocr",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка OCR: {e}")
            raise

class LLMService:
    """Сервис высокого уровня для работы с AI"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.client = LLMClient(base_url, api_key)
        # Сериализуем переключение моделей в llm-svc, чтобы параллельные чаты не ломали друг другу состояние
        self._model_switch_lock = asyncio.Lock()
        
        # Получаем настройки модели из конфигурации 
        settings = get_settings()
        if settings and hasattr(settings, 'llm_service'):
            llm_svc_config = settings.llm_service
            self.model_name = llm_svc_config.default_model
            self.fallback_model = llm_svc_config.fallback_model
            self.auto_select = llm_svc_config.auto_select
        else:
            self.model_name = "qwen-coder-30b"
            self.fallback_model = None
            self.auto_select = False
        
    async def initialize(self) -> bool:
        """Инициализация связи с сервисом LLM (первый доступный хост из конфига)."""
        try:
            for hid in self.client.llm_hosts:
                health = await self.client.health_check(host_id=hid)
                if health.get("status") != "healthy":
                    continue
                logger.info(f"Связь с микросервисом LLM установлена (host={hid!r})")
                if health.get("model_loaded") and health.get("model_name"):
                    self.model_name = health["model_name"]
                    logger.info(f"Текущая загруженная модель в llm-svc: {self.model_name}")
                else:
                    models = await self.client.get_models(host_id=hid)
                    if models:
                        self.model_name = models[0]["id"]
                        logger.info(f"Модель не загружена в llm-svc, первая из списка: {self.model_name}")
                return True
            logger.error("Микросервис LLM недоступен ни на одном из настроенных хостов")
            return False
        except Exception as e:
            logger.error(f"Ошибка инициализации LLMService: {e}")
            return False

    async def _sync_loaded_model_name_from_health(self, host_id: Optional[str] = None):
        """
        Подтягивает self.model_name из GET /v1/health выбранного хоста (по умолчанию default_llm_host).
        Возвращает (model_loaded_ok, health_json) для проверки пула loaded_models
        """
        try:
            hid = host_id or self.client.default_llm_host
            health = await self.client.health_check(host_id=hid)
            if health.get("status") != "healthy":
                return False, health
            if health.get("model_loaded") and health.get("model_name"):
                actual = health["model_name"]
                if self.model_name != actual:
                    logger.info(
                        f"[LLMService] Синхронизация model_name с llm-svc: {self.model_name!r} → {actual!r}"
                    )
                self.model_name = actual
                return True, health
            return False, health
        except Exception as e:
            logger.debug(f"[LLMService] Пропуск синхронизации model_name по health: {e}")
            return False, {}
    
    def prepare_messages(self, prompt: str, history: Optional[List[Dict[str, str]]] = None, 
                        system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """Подготовка сообщений для OpenAI API формата """
        messages = []
        
        # Добавляем системный промпт 
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        elif history and len(history) > 0:
            system_prompt_with_history = """Ты - полезный AI ассистент. У тебя есть доступ к полной истории диалога с пользователем.       
            Важные возможности:
            - Ты МОЖЕШЬ обращаться к предыдущим сообщениям в диалоге
            - Ты МОЖЕШЬ подсчитать количество токенов и сообщений в истории
            - Ты ВИДИШЬ все предыдущие сообщения в этом диалоге
            - Ты МОЖЕШЬ ссылаться на информацию из предыдущих сообщений

            Когда пользователь спрашивает о предыдущих сообщениях или токенах - используй доступную историю для ответа."""
            messages.append({"role": "system", "content": system_prompt_with_history})
        
        # Наполнение историей с ограничением по токенам
        # Приблизительная оценка: 1 токен ~ 4 символа для латиницы, ~2 для кириллицы
        # Оставляем запас для системного промпта (~200 токенов), текущего запроса и ответа (max_tokens)
        MAX_CONTEXT_TOKENS = 28000  # Для моделей с большим контекстом (qwen2.5 32k), чтобы помещалась история при большом RAG
        
        if history:
            # Считаем токены текущего промпта и системного сообщения
            system_tokens = sum(len(m.get("content", "")) // 3 for m in messages)
            prompt_tokens = len(prompt) // 3
            used_tokens = system_tokens + prompt_tokens + 1024  # запас на ответ
            
            # Добавляем историю с конца (новые сообщения важнее)
            trimmed_history = []
            for entry in reversed(history):
                role = entry.get("role", "user")
                content = entry.get("content", "")
                if role not in ["user", "assistant", "system"]:
                    continue
                # Обрезаем слишком длинные сообщения из истории (ошибки, документы)
                if len(content) > 2000:
                    content = content[:2000] + "... [обрезано]"
                entry_tokens = len(content) // 3
                if used_tokens + entry_tokens > MAX_CONTEXT_TOKENS:
                    logger.warning(f"История обрезана: {len(trimmed_history)} из {len(history)} сообщений вместилось")
                    break
                trimmed_history.append({"role": role, "content": content})
                used_tokens += entry_tokens
            
            # Восстанавливаем хронологический порядок
            for entry in reversed(trimmed_history):
                messages.append(entry)
        
        # Текущий запрос
        messages.append({"role": "user", "content": prompt})
        return messages
    
    async def generate_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        streaming: bool = False,
        stream_callback: Optional[Callable[[str, str], bool]] = None,
        images: Optional[List[str]] = None,
        model_path: Optional[str] = None
    ) -> str:
        """Генерация ответа через распределенную систему"""
        try:
            if history:
                logger.info(f"История диалога: {len(history)} сообщений передается в LLM")
            
            messages = self.prepare_messages(prompt, history, system_prompt)
            
            # Обработка изображений для мультимодальных моделей
            # LLM-сервис в другом контейнере - передаём изображения как data URL (base64), а не file://
            if images:
                logger.info(f"Добавление {len(images)} изображений к запросу")
                import base64
                image_urls = []
                for image_path in images:
                    if not image_path or not os.path.exists(image_path):
                        continue
                    try:
                        with open(image_path, "rb") as f:
                            data = f.read()
                        b64 = base64.b64encode(data).decode("ascii")
                        ext = os.path.splitext(image_path)[1].lower()
                        mime = "image/png" if ext == ".png" else "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
                        image_urls.append(f"data:{mime};base64,{b64}")
                    except Exception as e:
                        logger.warning(f"Не удалось прочитать изображение {image_path}: {e}")
                if image_urls:
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            content = msg.get("content", "")
                            msg["content"] = [{"type": "text", "text": content}]
                            for url in image_urls:
                                msg["content"].append({
                                    "type": "image_url",
                                    "image_url": {"url": url}
                                })
                            break
            
            # Разрешаем путь модели через Registry (поддерживает новый формат
            # <provider_id>/<model_id> и legacy llm-svc://host/model).
            registry = await get_registry()
            provider, resolved_model = registry.resolve(model_path)
            # Если model_id в path не задан — используем закэшированный self.model_name
            # (имя default-модели провайдера, подтягивается из health при initialize()).
            model_to_use = resolved_model or self.model_name
            if not model_to_use:
                # Попытка: синхронизируем имя загруженной модели.
                await self._sync_loaded_model_name_from_health()
                model_to_use = self.model_name

            if str(model_path or "").strip():
                logger.info(
                    "[generate_response] model_path=%r → provider=%r model=%r",
                    model_path, provider.id, model_to_use,
                )

            # ensure_model_loaded сам делает всю работу:
            # - llm-svc: POST /v1/models/load при необходимости (с внутренним _switch_lock);
            # - vLLM/Ollama/OpenAI: проверка, что модель доступна (без сетевых побочных эффектов).
            if model_to_use:
                ok = await provider.ensure_model_loaded(model_to_use)
                if ok:
                    self.model_name = model_to_use
                else:
                    logger.warning(
                        "[generate_response] provider=%s не готов выдать модель %r; "
                        "используем текущее имя модели %r",
                        provider.id, model_to_use, self.model_name,
                    )
                    model_to_use = self.model_name

            if streaming and stream_callback:
                logger.info(
                    "[generate_response] stream → provider=%s model=%r",
                    provider.id, model_to_use,
                )
                return await provider.stream_chat(
                    messages=messages,
                    model=model_to_use,
                    callback=stream_callback,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                logger.info(
                    "[generate_response] chat → provider=%s model=%r",
                    provider.id, model_to_use,
                )
                content = await provider.chat(
                    messages=messages,
                    model=model_to_use,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
        except Exception as e:
            logger.error(f"Ошибка generate_response: {e}")
            return f"Извините, произошла ошибка: {str(e)}"

    async def _stream_generation(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream_callback: Callable[[str, str], bool],
        model_name: Optional[str] = None,
        host_id: Optional[str] = None,
    ) -> str:
        """
        Legacy-совместимая обёртка: делегирует в ``provider.stream_chat``.
        Новый код должен использовать ``provider.stream_chat`` напрямую.
        """
        try:
            provider = await self.client._get_provider(host_id)
            return await provider.stream_chat(
                messages=messages,
                model=model_name or self.model_name,
                callback=stream_callback,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f"Ошибка _stream_generation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Ошибка потока: {str(e)}"

    # Прокси-методы (для поддержки старых вызовов через LLMService)
    async def synthesize_speech(self, *args, **kwargs): return await self.client.synthesize_speech(*args, **kwargs)
    async def transcribe_audio_whisperx(self, *args, **kwargs): return await self.client.transcribe_audio_whisperx(*args, **kwargs)
    async def diarize_audio(self, *args, **kwargs): return await self.client.diarize_audio(*args, **kwargs)
    async def transcribe_with_diarization(self, *args, **kwargs): return await self.client.transcribe_with_diarization(*args, **kwargs)
    async def recognize_text_from_image(self, *args, **kwargs): return await self.client.recognize_text_from_image(*args, **kwargs)

    async def get_audio_services_health(self) -> Dict[str, Any]:
        """Сборное здоровье аудио-сервисов """
        try:
            v_h = await self.client.get_transcription_health()
            t_h = await self.client.get_tts_health()
            return {
                "transcription": v_h, "tts": t_h,
                "overall": "healthy" if (v_h.get("status")=="healthy" and t_h.get("status")=="healthy") else "unhealthy"
            }
        except: return {"overall": "unhealthy"}

# ==============================================================================
# ГЛОБАЛЬНЫЙ ДОСТУП И СИНХРОННЫЕ ОБЕРТКИ 
# ==============================================================================

llm_service = None

async def get_llm_service() -> LLMService:
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
        await llm_service.initialize()
    return llm_service

def ask_agent_llm_svc(prompt: str, history: Optional[List[Dict[str, str]]] = None, 
                     max_tokens: Optional[int] = None, streaming: bool = False,
                     stream_callback: Optional[Callable[[str, str], bool]] = None,
                     model_path: Optional[str] = None, custom_prompt_id: Optional[str] = None,
                     images: Optional[List[str]] = None,
                     system_prompt: Optional[str] = None,
                     temperature: Optional[float] = None) -> str:
    """Синхронная обертка с защитой event loop """
    logger.info(f"[ask_agent_llm_svc] Called with prompt len: {len(prompt)}, streaming: {streaming}")
    
    async def _async_generate():
        logger.info("[ask_agent_llm_svc] _async_generate started")
        try:
            service = await get_llm_service()
            logger.info("[ask_agent_llm_svc] Service obtained")
            result = await service.generate_response(
                prompt=prompt, history=history, max_tokens=max_tokens or 1024,
                streaming=streaming, stream_callback=stream_callback,
                images=images, model_path=model_path,
                system_prompt=system_prompt,
                temperature=temperature if temperature is not None else 0.7,
            )
            logger.info("[ask_agent_llm_svc] generate_response completed")
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                logger.warning("[ask_agent_llm_svc] LLM service busy or reinitializing (503)")
                return "Сервис модели занят или перезагружается. Повторите запрос через несколько секунд."
            logger.error(f"[ask_agent_llm_svc] HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"[ask_agent_llm_svc] Error in _async_generate: {e}")
            raise

    def _run_async_generate_sync() -> str:
        """Отдельный sync-вход для asyncio.run (в т.ч. из пула потоков)."""
        return asyncio.run(_async_generate())

    # Не используем try/except вокруг get_running_loop так, чтобы вложенные ошибки не цеплялись к RuntimeError в логах.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_async_generate_sync()

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_async_generate_sync)
        try:
            return future.result(timeout=120)
        except Exception as e:
            logger.error(f"[ask_agent_llm_svc] Error in executor: {e}")
            return "Ошибка при обращении к модели."

# --- Обертки для аудио и OCR ---

def _wrap_sync(coro):
    """Универсальный синхронный запуск"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as ex:
                return ex.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # Только RuntimeError (нет event loop) - пробуем asyncio.run
        return asyncio.run(coro)

def synthesize_speech_llm_svc(text: str, **kwargs) -> bytes:
    async def _call():
        s = await get_llm_service(); return await s.synthesize_speech(text, **kwargs)
    return _wrap_sync(_call())

def transcribe_audio_whisperx_llm_svc(audio_file: bytes, **kwargs) -> str:
    async def _call():
        s = await get_llm_service(); r = await s.transcribe_audio_whisperx(audio_file, **kwargs)
        return r.get("text", "") if isinstance(r, dict) else ""
    return _wrap_sync(_call())

def diarize_audio_llm_svc(audio_file: bytes, **kwargs) -> Dict[str, Any]:
    async def _call():
        s = await get_llm_service(); return await s.diarize_audio(audio_file, **kwargs)
    return _wrap_sync(_call())

def transcribe_with_diarization_llm_svc(audio_file: bytes, **kwargs) -> Dict[str, Any]:
    async def _call():
        s = await get_llm_service(); return await s.transcribe_with_diarization(audio_file, **kwargs)
    return _wrap_sync(_call())

def recognize_text_from_image_llm_svc(image_file: bytes, **kwargs) -> Dict[str, Any]:
    async def _call():
        s = await get_llm_service(); return await s.recognize_text_from_image(image_file, **kwargs)
    return _wrap_sync(_call())