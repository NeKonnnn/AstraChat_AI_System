"""
LLM Client для взаимодействия с llm-svc сервисом
Обеспечивает совместимость с OpenAI API через llm-svc
"""

import httpx
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для взаимодействия с llm-svc API"""
    
    def __init__(self, base_url: str = "http://localhost:8001", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = 300.0  # 5 минут таймаут для больших моделей
        
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для запросов"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния llm-svc"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/health",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка проверки здоровья llm-svc: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """Получение списка доступных моделей"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-coder-30b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Отправка запроса на генерацию ответа"""
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if stream:
                    # Потоковый запрос
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/v1/chat/completions",
                        headers={**self._get_headers(), "Accept": "text/event-stream"},
                        json=payload
                    ) as response:
                        response.raise_for_status()
                        return response
                else:
                    # Обычный запрос
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=self._get_headers(),
                        json=payload
                    )
                    response.raise_for_status()
                    return response.json()
        except Exception as e:
            logger.error(f"Ошибка запроса к llm-svc: {e}")
            raise

class LLMService:
    """Сервис для работы с LLM через llm-svc"""
    
    def __init__(self, base_url: str = "http://localhost:8001", api_key: Optional[str] = None):
        self.client = LLMClient(base_url, api_key)
        self.model_name = "qwen-coder-30b"  # Модель по умолчанию
        
    async def initialize(self) -> bool:
        """Инициализация сервиса"""
        try:
            health = await self.client.health_check()
            if health.get("status") == "healthy":
                logger.info("llm-svc сервис доступен")
                
                # Получаем список моделей
                models = await self.client.get_models()
                if models:
                    self.model_name = models[0]["id"]
                    logger.info(f"Используется модель: {self.model_name}")
                
                return True
            else:
                logger.error(f"llm-svc недоступен: {health}")
                return False
        except Exception as e:
            logger.error(f"Ошибка инициализации llm-svc: {e}")
            return False
    
    def prepare_messages(self, prompt: str, history: Optional[List[Dict[str, str]]] = None, 
                        system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """Подготовка сообщений в формате OpenAI API"""
        messages = []
        
        # Добавляем системный промпт
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Добавляем историю диалога
        if history:
            for entry in history:
                role = entry.get("role", "user")
                content = entry.get("content", "")
                if role in ["user", "assistant", "system"]:
                    messages.append({"role": role, "content": content})
        
        # Добавляем текущий запрос
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
        stream_callback: Optional[Callable[[str, str], bool]] = None
    ) -> str:
        """Генерация ответа через llm-svc"""
        
        try:
            # Подготавливаем сообщения
            messages = self.prepare_messages(prompt, history, system_prompt)
            
            if streaming and stream_callback:
                # Потоковая генерация
                return await self._stream_generation(
                    messages, temperature, max_tokens, stream_callback
                )
            else:
                # Обычная генерация
                response = await self.client.chat_completion(
                    messages=messages,
                    model=self.model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                
                if "choices" in response and len(response["choices"]) > 0:
                    return response["choices"][0]["message"]["content"]
                else:
                    logger.error("Неожиданный формат ответа от llm-svc")
                    return "Ошибка генерации ответа"
                    
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return f"Извините, произошла ошибка при генерации ответа: {str(e)}"
    
    async def _stream_generation(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream_callback: Callable[[str, str], bool]
    ) -> str:
        """Потоковая генерация с колбэком"""
        
        accumulated_text = ""
        
        try:
            async with self.client.client.stream(
                "POST",
                f"{self.client.base_url}/v1/chat/completions",
                headers={**self.client._get_headers(), "Accept": "text/event-stream"},
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Убираем "data: "
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    chunk = delta["content"]
                                    accumulated_text += chunk
                                    
                                    # Вызываем колбэк
                                    should_continue = stream_callback(chunk, accumulated_text)
                                    if not should_continue:
                                        logger.info("Генерация остановлена по сигналу колбэка")
                                        return None
                        except json.JSONDecodeError:
                            continue
                
                return accumulated_text
                
        except Exception as e:
            logger.error(f"Ошибка потоковой генерации: {e}")
            return f"Ошибка потоковой генерации: {str(e)}"

# Глобальный экземпляр сервиса
llm_service = None

async def get_llm_service() -> LLMService:
    """Получение глобального экземпляра LLM сервиса"""
    global llm_service
    if llm_service is None:
        # Настройки из переменных окружения или конфига
        base_url = "http://localhost:8001"  # Можно вынести в конфиг
        api_key = None  # Можно добавить в конфиг
        
        llm_service = LLMService(base_url, api_key)
        await llm_service.initialize()
    
    return llm_service

# Синхронные обертки для совместимости с существующим кодом
def ask_agent_llm_svc(prompt: str, history: Optional[List[Dict[str, str]]] = None, 
                     max_tokens: Optional[int] = None, streaming: bool = False,
                     stream_callback: Optional[Callable[[str, str], bool]] = None,
                     model_path: Optional[str] = None, custom_prompt_id: Optional[str] = None) -> str:
    """Синхронная обертка для ask_agent через llm-svc"""
    
    async def _async_generate():
        service = await get_llm_service()
        return await service.generate_response(
            prompt=prompt,
            history=history,
            system_prompt=None,  # Можно добавить поддержку custom_prompt_id
            temperature=0.7,
            max_tokens=max_tokens or 1024,
            streaming=streaming,
            stream_callback=stream_callback
        )
    
    # Запускаем асинхронную функцию в новом event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если loop уже запущен, создаем новый в отдельном потоке
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_generate())
                return future.result()
        else:
            return loop.run_until_complete(_async_generate())
    except RuntimeError:
        # Если нет event loop, создаем новый
        return asyncio.run(_async_generate())
