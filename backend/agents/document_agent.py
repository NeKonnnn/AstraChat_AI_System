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
            # Получаем doc_processor из контекста или из main
            doc_processor = context.get("doc_processor") if context else None
            
            if not doc_processor:
                # Пытаемся получить из main.py
                try:
                    import backend.main as main_module
                    doc_processor = getattr(main_module, 'doc_processor', None)
                except:
                    pass
            
            if not doc_processor:
                return "DocumentProcessor недоступен. Пожалуйста, убедитесь, что система инициализирована."
            
            # Проверяем состояние документов
            doc_list = doc_processor.get_document_list()
            logger.info(f"[DocumentAgent] doc_processor ID: {id(doc_processor)}")
            logger.info(f"[DocumentAgent] doc_list: {doc_list}")
            logger.info(f"[DocumentAgent] doc_names: {doc_processor.doc_names}")
            logger.info(f"[DocumentAgent] documents count: {len(doc_processor.documents) if doc_processor.documents else 0}")
            logger.info(f"[DocumentAgent] vectorstore exists: {doc_processor.vectorstore is not None}")
            
            if not doc_list or len(doc_list) == 0:
                return "Документы не загружены. Пожалуйста, загрузите документы через веб-интерфейс (кнопка 'Загрузить документ')."
            
            if not doc_processor.vectorstore:
                return f"Векторное хранилище не инициализировано, хотя документы загружены ({len(doc_list)} документов). Попробуйте перезагрузить документы."
            
            # Поиск в векторном хранилище
            logger.info(f"Поиск в векторном хранилище: {message}")
            docs = doc_processor.vectorstore.similarity_search(message, k=3)
            
            if not docs:
                return "В загруженных документах не найдено информации по вашему запросу."
            
            logger.info(f"Найдено документов: {len(docs)}")
            
            # Формируем контекст из найденных документов
            context_parts = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get('source', 'Неизвестный источник')
                content = doc.page_content
                context_parts.append(f"Фрагмент {i} (из документа '{source}'):\n{content}\n")
            
            document_context = "\n".join(context_parts)
            
            # Используем LLM для формирования ответа на основе контекста
            from backend.agent import ask_agent
            
            prompt = f"""На основе предоставленного контекста из документов ответь на вопрос пользователя.
Если информации в контексте недостаточно, укажи это.
Отвечай только на основе информации из контекста. Не придумывай информацию.

Контекст из документов:

{document_context}

Вопрос пользователя: {message}

Ответ:"""
            
            # Получаем историю из контекста
            history = context.get("history", []) if context else []
            
            # Проверяем, выбрана ли модель
            selected_model = context.get("selected_model") if context else None
            
            logger.info("Отправляем запрос к LLM с контекстом документов...")
            if selected_model:
                logger.info(f"DocumentAgent использует модель: {selected_model}")
                response = ask_agent(prompt, history=[], streaming=False, model_path=selected_model)
            else:
                logger.info(f"DocumentAgent использует модель по умолчанию")
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

