import json
import hashlib
import asyncio
from typing import Dict, Any, List, Union
import logging

from app.models.schemas import Message, ChatCompletionRequestSystemMessage, ChatCompletionRequestUserMessage, \
    ChatCompletionRequestAssistantMessage, ChatCompletionRequestToolMessage, ChatCompletionRequestFunctionMessage

logger = logging.getLogger(__name__)


def convert_to_chat_completion_messages(messages: List[Message]) -> List[Union[
    ChatCompletionRequestSystemMessage,
    ChatCompletionRequestUserMessage,
    ChatCompletionRequestAssistantMessage,
    ChatCompletionRequestToolMessage,
    ChatCompletionRequestFunctionMessage
]]:
    """Преобразование сообщений в типы, совместимые с create_chat_completion."""
    result = []

    for msg in messages:
        if msg.role == "system":
            result.append(ChatCompletionRequestSystemMessage(
                content=msg.content,
            ))
        elif msg.role == "user":
            result.append(ChatCompletionRequestUserMessage(
                content=msg.content,
            ))
        elif msg.role == "assistant":
            result.append(ChatCompletionRequestAssistantMessage(
                content=msg.content,
            ))
        elif msg.role == "tool":
            result.append(ChatCompletionRequestToolMessage(
                content=msg.content,
                tool_call_id=msg.name if msg.name else ""
            ))
        elif msg.role == "function":
            result.append(ChatCompletionRequestFunctionMessage(
                content=msg.content,
            ))

    return result


def convert_to_dict_messages(messages: List[Message]) -> List[Dict[str, Any]]:
    """Преобразование сообщений в словари для обратной совместимости."""
    return [
        {
            "role": msg.role,
            "content": msg.content,
        }
        for msg in messages
    ]


def generate_response_id(messages: list) -> str:
    """Генерация уникального ID для ответа на основе сообщений."""
    messages_str = json.dumps(messages, sort_keys=True)
    return hashlib.md5(messages_str.encode()).hexdigest()


def estimate_tokens(text: str) -> int:
    """Примерная оценка количества токенов в тексте."""
    return len(text) // 4


def format_messages_for_llama(messages: list) -> str:
    """Форматирование сообщений для ввода в модель."""
    formatted = ""
    for msg in messages:
        role = msg.role
        content = msg.content
        formatted += f"{role}: {content}\n"

    return formatted + "assistant: "


async def run_in_thread(func, *args, **kwargs):
    """Запуск блокирующей функции в отдельном потоке."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
