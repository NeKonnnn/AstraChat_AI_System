"""
Агент для работы с памятью
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MemoryAgent(BaseAgent):
    """Агент для работы с памятью системы"""
    
    def __init__(self):
        super().__init__(
            name="memory",
            description="Агент для сохранения и извлечения информации из памяти"
        )
        
        self.capabilities = [
            "save_memory", "retrieve_memory", "organize_memory", "search_memory"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов по работе с памятью"""
        try:
            message_lower = message.lower()
            
            # Определяем тип операции
            if any(word in message_lower for word in ["запомни", "сохрани", "запиши"]):
                return await self._save_to_memory(message, context)
            elif any(word in message_lower for word in ["найди в памяти", "что я помню", "покажи память"]):
                return await self._retrieve_from_memory(message, context)
            elif any(word in message_lower for word in ["очисти память", "удали память"]):
                return await self._clear_memory(message, context)
            else:
                return await self._save_to_memory(message, context)  # По умолчанию сохраняем
            
        except Exception as e:
            logger.error(f"Ошибка в MemoryAgent: {e}")
            return f"Произошла ошибка при работе с памятью: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        
        memory_keywords = [
            "запомни", "сохрани", "запиши", "память", "заметка",
            "найди в памяти", "что я помню", "покажи память",
            "очисти память", "удали память"
        ]
        
        return any(keyword in message_lower for keyword in memory_keywords)
    
    async def _save_to_memory(self, message: str, context: Dict[str, Any] = None) -> str:
        """Сохранение информации в память"""
        try:
            from backend.database.memory_service import save_dialog_entry
            
            # Извлекаем содержимое для сохранения
            content = self._extract_content_to_save(message)
            category = self._extract_category(message)
            
            if not content:
                return "Не удалось определить, что именно нужно сохранить в память."
            
            # Сохраняем в память
            await save_dialog_entry("system", f"[{category}] {content}")
            
            response = f"**Информация сохранена в память**\n\n"
            response += f"**Категория:** {category}\n"
            response += f"**Содержимое:** {content}\n\n"
            response += "**Рекомендации:**\n"
            response += "- Используйте 'что я помню о [теме]' для поиска информации\n"
            response += "- Используйте 'покажи всю память' для просмотра всех записей\n"
            response += "- Используйте 'очисти память' для удаления всех записей"
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в память: {e}")
            return f"Ошибка при сохранении в память: {str(e)}"
    
    async def _retrieve_from_memory(self, message: str, context: Dict[str, Any] = None) -> str:
        """Извлечение информации из памяти"""
        try:
            from backend.database.memory_service import load_dialog_history
            
            # Загружаем историю диалогов
            history = await load_dialog_history()
            
            if not history:
                return "Память пуста. Используйте 'запомни [информация]' для сохранения данных."
            
            # Фильтруем системные сообщения (записи памяти)
            memory_entries = []
            for entry in history:
                if entry.get("role") == "system" and entry.get("content", "").startswith("["):
                    memory_entries.append(entry)
            
            if not memory_entries:
                return "В памяти нет сохраненных записей."
            
            # Формируем ответ
            response = f"**Сохраненные записи в памяти ({len(memory_entries)}):**\n\n"
            
            for i, entry in enumerate(memory_entries[-10:], 1):  # Показываем последние 10
                content = entry.get("content", "")
                timestamp = entry.get("timestamp", "Неизвестно")
                
                response += f"{i}. **{timestamp}**\n"
                response += f"   {content}\n\n"
            
            if len(memory_entries) > 10:
                response += f"... и еще {len(memory_entries) - 10} записей\n\n"
            
            response += "**Рекомендации:**\n"
            response += "- Используйте 'найди в памяти [ключевое слово]' для поиска\n"
            response += "- Используйте 'очисти память' для удаления всех записей"
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка извлечения из памяти: {e}")
            return f"Ошибка при извлечении из памяти: {str(e)}"
    
    async def _clear_memory(self, message: str, context: Dict[str, Any] = None) -> str:
        """Очистка памяти"""
        try:
            from backend.database.memory_service import clear_dialog_history
            
            await clear_dialog_history()
            
            return "**Память очищена**\n\nВсе сохраненные записи удалены."
            
        except Exception as e:
            logger.error(f"Ошибка очистки памяти: {e}")
            return f"Ошибка при очистке памяти: {str(e)}"
    
    def _extract_content_to_save(self, message: str) -> str:
        """Извлечение содержимого для сохранения"""
        # Убираем служебные слова
        stop_words = ["запомни", "сохрани", "запиши", "в память"]
        
        content = message
        for stop_word in stop_words:
            content = content.replace(stop_word, "").strip()
        
        return content if content else message
    
    def _extract_category(self, message: str) -> str:
        """Извлечение категории для сохранения"""
        # Простая категоризация по ключевым словам
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["важно", "важная", "критично"]):
            return "важное"
        elif any(word in message_lower for word in ["идея", "мысль", "предложение"]):
            return "идеи"
        elif any(word in message_lower for word in ["факт", "информация", "данные"]):
            return "факты"
        elif any(word in message_lower for word in ["задача", "дело", "план"]):
            return "задачи"
        else:
            return "общее"

