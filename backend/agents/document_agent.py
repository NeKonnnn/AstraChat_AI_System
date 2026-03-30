"""
Агент для работы с документами
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

from backend.realtime.rag_evidence import (
    build_rag_id_to_filename,
    filter_rag_hits_by_score,
    rag_document_label,
    rag_guard_env,
    RAG_NO_RELEVANT_CONTEXT_MESSAGE,
)
from backend.app_state import get_rag_chat_top_k
from backend.rag_query.post_generation import maybe_replace_ungrounded
from backend.rag_query.prompts import RAG_STRICT_NOT_FOUND_MESSAGE, merge_strict_rag_system_prompt

logger = logging.getLogger(__name__)

class DocumentAgent(BaseAgent):
    """Агент для работы с загруженными документами"""
    
    def __init__(self):
        super().__init__(
            name="document",
            description="Агент для поиска и анализа документов"
        )
        
        self.capabilities = [
            "document_search", "text_analysis", "content_extraction"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов по документам"""
        try:
            # Получаем клиента SVC-RAG из backend.main
            try:
                import backend.main as main_module
                rag_client = getattr(main_module, "rag_client", None)
                current_rag_strategy = getattr(main_module, "current_rag_strategy", "auto")
            except Exception:
                rag_client = None
                current_rag_strategy = "auto"

            if not rag_client:
                return "Сервис поиска по документам (SVC-RAG) недоступен. Пожалуйста, убедитесь, что система инициализирована."

            # Выполняем поиск по документам через SVC-RAG
            logger.info(f"[DocumentAgent] Поиск в документах через SVC-RAG: {message}")
            min_sim, _ = rag_guard_env()
            hits = await rag_client.search(message, k=get_rag_chat_top_k(), strategy=current_rag_strategy)
            hits = filter_rag_hits_by_score(hits, min_sim)

            if not hits:
                return RAG_NO_RELEVANT_CONTEXT_MESSAGE

            logger.info(f"[DocumentAgent] Найдено фрагментов: {len(hits)}")

            id_map = build_rag_id_to_filename(list(await rag_client.list_documents() or []))
            context_parts = []
            for i, (content, score, doc_id, chunk_idx) in enumerate(hits, 1):
                title = rag_document_label(doc_id, id_map)
                context_parts.append(
                    f"Фрагмент {i} (документ «{title}», чанк {chunk_idx}, релевантность: {score:.2f}):\n{content}\n"
                )
            
            document_context = "\n".join(context_parts)
            
            # Используем LLM для формирования ответа на основе контекста
            from backend.agent_llm_svc import ask_agent

            prompt = f"""CONTEXT:

{document_context}

Вопрос пользователя: {message}

Ответ:"""

            # Проверяем, выбрана ли модель
            selected_model = context.get("selected_model") if context else None

            logger.info("Отправляем запрос к LLM с контекстом документов...")
            if selected_model:
                logger.info(f"DocumentAgent использует модель: {selected_model}")
                response = ask_agent(
                    prompt,
                    history=[],
                    streaming=False,
                    model_path=selected_model,
                    system_prompt=merge_strict_rag_system_prompt(None),
                )
            else:
                logger.info("DocumentAgent использует модель по умолчанию")
                response = ask_agent(
                    prompt,
                    history=[],
                    streaming=False,
                    system_prompt=merge_strict_rag_system_prompt(None),
                )

            response = await maybe_replace_ungrounded(
                prompt[:20000], response, RAG_STRICT_NOT_FOUND_MESSAGE
            )

            logger.info(f"Получен ответ от LLM, длина: {len(response)} символов")
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка в DocumentAgent: {e}")
            return f"Произошла ошибка при поиске в документах: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        
        document_keywords = [
            "документ", "файл", "текст", "поиск в документах", 
            "найди в файлах", "загруженные документы", "что в документах",
            "информация из файлов", "анализ документов"
        ]
        
        return any(keyword in message_lower for keyword in document_keywords)

