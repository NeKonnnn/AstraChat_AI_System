"""
Агент для работы с документами
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

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
            hits = await rag_client.search(message, k=3, strategy=current_rag_strategy)

            if not hits:
                return "В загруженных документах не найдено информации по вашему запросу."

            logger.info(f"[DocumentAgent] Найдено фрагментов: {len(hits)}")

            # Формируем контекст из найденных документов
            context_parts = []
            for i, (content, score, doc_id, chunk_idx) in enumerate(hits, 1):
                context_parts.append(
                    f"Фрагмент {i} (document_id={doc_id}, чанк {chunk_idx}, релевантность: {score:.2f}):\n{content}\n"
                )
            
            document_context = "\n".join(context_parts)
            
            # Используем LLM для формирования ответа на основе контекста
            from backend.agent_llm_svc import ask_agent

            prompt = f"""На основе предоставленного контекста из документов ответь на вопрос пользователя.
Если информации в контексте недостаточно, укажи это.
Отвечай только на основе информации из контекста. Не придумывай информацию.

Контекст из документов:

{document_context}

Вопрос пользователя: {message}

Ответ:"""

            # Проверяем, выбрана ли модель
            selected_model = context.get("selected_model") if context else None

            logger.info("Отправляем запрос к LLM с контекстом документов...")
            if selected_model:
                logger.info(f"DocumentAgent использует модель: {selected_model}")
                response = ask_agent(prompt, history=[], streaming=False, model_path=selected_model)
            else:
                logger.info("DocumentAgent использует модель по умолчанию")
                response = ask_agent(prompt, history=[], streaming=False)

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

