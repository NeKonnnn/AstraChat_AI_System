"""
Агент для веб-поиска
"""

import logging
import requests
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class WebSearchAgent(BaseAgent):
    """Агент для поиска информации в интернете"""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Агент для поиска актуальной информации в интернете"
        )
        
        self.capabilities = [
            "web_search", "news_search", "weather_info", "currency_rates"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов веб-поиска"""
        try:
            # Извлекаем поисковый запрос
            search_query = self._extract_search_query(message)
            
            if not search_query:
                return "Не удалось определить поисковый запрос. Пожалуйста, уточните, что именно вы хотите найти в интернете."
            
            # Выполняем поиск
            search_results = await self._perform_search(search_query)
            
            if not search_results:
                return f"По запросу '{search_query}' ничего не найдено в интернете."
            
            # Формируем ответ
            response = f"**Результаты поиска по запросу '{search_query}':**\n\n"
            
            for i, result in enumerate(search_results[:5], 1):
                response += f"{i}. **{result.get('title', 'Без заголовка')}**\n"
                response += f"   {result.get('snippet', 'Описание недоступно')}\n"
                if result.get('url'):
                    response += f"   🔗 {result['url']}\n"
                response += "\n"
            
            # Добавляем рекомендации
            response += "**Рекомендации:**\n"
            response += "- Для получения более актуальной информации уточните запрос\n"
            response += "- Используйте 'сохрани эту информацию' для записи важных данных\n"
            response += "- Для погоды укажите город: 'погода в Москве'"
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка в WebSearchAgent: {e}")
            return f"Произошла ошибка при поиске в интернете: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение"""
        message_lower = message.lower()
        
        web_keywords = [
            "интернет", "веб", "поиск в интернете", "актуальная информация",
            "новости", "погода", "курс валют", "найди в интернете",
            "что происходит", "последние новости", "текущие события"
        ]
        
        return any(keyword in message_lower for keyword in web_keywords)
    
    def _extract_search_query(self, message: str) -> str:
        """Извлечение поискового запроса из сообщения"""
        # Убираем служебные слова
        stop_words = [
            "найди в интернете", "поиск в интернете", "что в интернете",
            "актуальная информация", "последние новости", "текущие события"
        ]
        
        query = message
        for stop_word in stop_words:
            query = query.replace(stop_word, "").strip()
        
        return query if query else message
    
    async def _perform_search(self, query: str) -> List[Dict[str, Any]]:
        """Выполнение поиска в интернете"""
        try:
            # Используем DuckDuckGo API (бесплатно)
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            results = []
            
            # Обрабатываем основные результаты
            for result in data.get("Results", []):
                results.append({
                    "title": result.get("Text", ""),
                    "url": result.get("FirstURL", ""),
                    "snippet": result.get("Text", "")
                })
            
            # Обрабатываем связанные темы
            for topic in data.get("RelatedTopics", []):
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            
            return results[:10]  # Ограничиваем количество результатов
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении поиска: {e}")
            return []