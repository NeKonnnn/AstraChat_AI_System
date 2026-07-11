"""
Агент для работы с документами (KB + библиотека памяти).
Global documents store больше не используется.
"""

from typing import Any, Dict, List, Optional, Tuple

import backend.app_state as state
from backend.app_state import get_rag_chat_top_k
from backend.rag_query.post_generation import maybe_replace_ungrounded
from backend.rag_query.prompts import RAG_STRICT_NOT_FOUND_MESSAGE, merge_strict_rag_system_prompt
from backend.realtime.rag_evidence import (
    RAG_NO_RELEVANT_CONTEXT_MESSAGE,
    build_rag_id_to_filename,
    filter_rag_hits_by_score,
    rag_document_label,
    rag_guard_env,
)
from backend.settings.logging import get_logger

from .base_agent import BaseAgent

logger = get_logger(__name__)

Hit = Tuple[str, float, Optional[int], Optional[int]]


class DocumentAgent(BaseAgent):
    """Агент для поиска по KB и библиотеке памяти (не global store)."""

    def __init__(self):
        super().__init__(name="document", description="Агент для поиска и анализа документов")
        self.capabilities = ["document_search", "text_analysis", "content_extraction"]

    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов по документам"""
        try:
            request_strategy = str((context or {}).get("rag_strategy") or "").strip().lower()
            try:
                import backend.main as main_module

                rag_client = getattr(main_module, "rag_client", None)
                current_rag_strategy = request_strategy or getattr(main_module, "current_rag_strategy", "auto")
            except Exception:
                logger.exception("Ошибка операции")
                rag_client = None
                current_rag_strategy = request_strategy or "auto"
            if not rag_client:
                return "Сервис поиска по документам (SVC-RAG) недоступен. Пожалуйста, убедитесь, что система инициализирована."

            logger.info("[DocumentAgent] Поиск в KB + memory: %s", message)
            min_sim, _ = rag_guard_env()
            k = get_rag_chat_top_k()
            hits: List[Hit] = []
            id_map: Dict[Any, str] = {}

            try:
                kb_hits = await rag_client.kb_search(message, k=k, strategy=current_rag_strategy) or []
                hits.extend(kb_hits)
                id_map.update(build_rag_id_to_filename(list(await rag_client.kb_list_documents() or [])))
            except Exception:
                logger.exception("DocumentAgent kb_search")

            try:
                mem_hits = await rag_client.memory_rag_search(message, k=k, strategy=current_rag_strategy) or []
                hits.extend(mem_hits)
                id_map.update(build_rag_id_to_filename(list(await rag_client.memory_rag_list_documents() or [])))
            except Exception:
                logger.exception("DocumentAgent memory_rag_search")

            hits = filter_rag_hits_by_score(hits, min_sim)
            hits.sort(key=lambda h: float(h[1]) if h and len(h) > 1 else 0.0, reverse=True)
            hits = hits[:k]
            if not hits:
                return RAG_NO_RELEVANT_CONTEXT_MESSAGE

            logger.info("[DocumentAgent] Найдено фрагментов: %s", len(hits))
            context_parts = []
            for i, (content, score, doc_id, chunk_idx) in enumerate(hits, 1):
                title = rag_document_label(doc_id, id_map)
                context_parts.append(
                    f"Фрагмент {i} (документ «{title}», чанк {chunk_idx}, релевантность: {score:.2f}):\n{content}\n"
                )
            document_context = "\n".join(context_parts)
            from backend.agent_llm_svc import ask_agent

            prompt = f"CONTEXT:\n\n{document_context}\n\nВопрос пользователя: {message}\n\nОтвет:"
            selected_model = context.get("selected_model") if context else None
            logger.info("Отправляем запрос к LLM с контекстом документов...")
            system_prompt = merge_strict_rag_system_prompt(
                None, rag_override=getattr(state, "rag_system_prompt", None)
            )
            if selected_model:
                logger.info("DocumentAgent использует модель: %s", selected_model)
                response = ask_agent(
                    prompt,
                    history=[],
                    streaming=False,
                    model_path=selected_model,
                    system_prompt=system_prompt,
                )
            else:
                logger.info("DocumentAgent использует модель по умолчанию")
                response = ask_agent(
                    prompt,
                    history=[],
                    streaming=False,
                    system_prompt=system_prompt,
                )
            response = await maybe_replace_ungrounded(prompt[:20000], response, RAG_STRICT_NOT_FOUND_MESSAGE)
            logger.info("Получен ответ от LLM, длина: %s символов", len(response))
            return response
        except Exception as e:
            logger.exception("Ошибка в DocumentAgent")
            return f"Произошла ошибка при поиске в документах: {str(e)}"

    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        document_keywords = [
            "документ",
            "файл",
            "текст",
            "поиск в документах",
            "найди в файлах",
            "загруженные документы",
            "что в документах",
            "информация из файлов",
            "анализ документов",
        ]
        return any((keyword in message_lower for keyword in document_keywords))
