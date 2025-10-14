"""
Инструменты для веб-поиска и работы с интернетом
"""

import requests
import json
from typing import Dict, List, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

class WebTools:
    """Класс с инструментами для веб-поиска"""
    
    @staticmethod
    @tool
    def search_web(query: str, num_results: int = 5) -> str:
        """Поиск информации в интернете"""
        try:
            # Используем DuckDuckGo для поиска (бесплатно, без API ключей)
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
            
            # Добавляем основные результаты
            for result in data.get("Results", [])[:num_results]:
                results.append(f"• {result.get('Text', '')} - {result.get('FirstURL', '')}")
            
            # Добавляем связанные темы
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(f"• {topic['Text']}")
            
            if results:
                return f"Результаты поиска по запросу '{query}':\n" + "\n".join(results)
            else:
                return f"По запросу '{query}' ничего не найдено"
                
        except Exception as e:
            logger.error(f"Ошибка веб-поиска: {e}")
            return f"Ошибка при поиске в интернете: {str(e)}"
    
    @staticmethod
    @tool
    def get_weather(city: str) -> str:
        """Получение информации о погоде"""
        try:
            # Используем OpenWeatherMap API (требует API ключ)
            # Для демонстрации возвращаем заглушку
            return f"Погода в городе {city}: [Интеграция с погодным API в разработке]"
        except Exception as e:
            return f"Ошибка получения погоды: {str(e)}"
    
    @staticmethod
    @tool
    def get_currency_rate(from_currency: str, to_currency: str) -> str:
        """Получение курса валют"""
        try:
            # Простая заглушка для курса валют
            return f"Курс {from_currency.upper()} к {to_currency.upper()}: [Интеграция с валютным API в разработке]"
        except Exception as e:
            return f"Ошибка получения курса валют: {str(e)}"
    
    @staticmethod
    @tool
    def check_url_status(url: str) -> str:
        """Проверка доступности URL"""
        try:
            response = requests.head(url, timeout=5)
            return f"URL {url} доступен. Статус: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return f"URL {url} недоступен. Ошибка: {str(e)}"
        except Exception as e:
            return f"Ошибка проверки URL: {str(e)}"
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов класса"""
        return [
            WebTools.search_web,
            WebTools.get_weather,
            WebTools.get_currency_rate,
            WebTools.check_url_status
        ]

