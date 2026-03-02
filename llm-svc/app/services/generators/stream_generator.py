import json
import time
import uuid
import re
from typing import List, Optional, AsyncGenerator, Dict, Any, Callable
from app.models.schemas import Message, ToolDefinition
from .base_generator import BaseResponseGenerator
from app.services.generators.tool_call_processor import ToolCallProcessor
import logging

logger = logging.getLogger(__name__)

class StreamResponseGenerator(BaseResponseGenerator):
    """Генератор потоковых ответов с поддержкой tool calls для LibreChat"""
    
    def __init__(self, model_name: str, completion_caller: Callable):
        super().__init__(model_name, completion_caller)
        self.tool_processor = ToolCallProcessor()
        self.tool_call_pattern = re.compile(r'<tool_call>\s(.*?)\s*</tool_call>', re.DOTALL)

    async def generate(
        self,
        messages: List[Message],
        temperature: float,
        max_tokens: int,
        frequency_penalty: float,
        presence_penalty: float,
        tools: Optional[List[ToolDefinition]] = None,
        session_id: str = None,
    ) -> AsyncGenerator[str, None]:
        logger.info(f"Streaming generation started [Session: {session_id}]")
        response_id = f"chatcmpl-{uuid.uuid4().hex}"
        buffer = ""
        tool_call_detected = False
        try:
            params = self._prepare_generation_params(
                messages, temperature, max_tokens, frequency_penalty, presence_penalty, tools
            )
            async for chunk in self._completion_caller(session_id, params): # Убран ** так как в models_service передается словарь
                delta = chunk.get('choices', [{}])[0].get('delta', {})
                content = delta.get('content', '')
                if not content:
                    continue
                if not tool_call_detected and '<tool_call>' not in content:
                    # Обычный текст
                    yield self._create_chunk(response_id, content)
                else:
                    # Tool call detection
                    buffer += content
                    tool_call_detected = True
                    if '</tool_call>' in buffer:
                        tool_calls = self.parse_tool_calls_from_buffer(buffer) # Исправлен вызов self
                        if tool_calls:
                            # Генерируем последовательность как OpenAI
                            async for tool_chunk in self._stream_tool_calls(response_id, tool_calls[0]):
                                yield tool_chunk
                        buffer = ""
                        tool_call_detected = False
            if buffer and not tool_call_detected:
                yield self._create_chunk(response_id, buffer)
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}", exc_info=True)
            yield self._create_error_chunk(response_id, str(e))

    async def _stream_tool_calls(self, response_id: str, tool_call: dict) -> AsyncGenerator[str, None]:
        """Строгая имитация OpenAI streaming для LibreChat"""
        yield f"data: {json.dumps({
            'id': response_id,
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': self.model_name,
            'choices': [{
                'index': 0,
                'delta': {
                    'role': 'assistant',
                    'tool_calls': [{
                        'index': 0,
                        'id': tool_call['id'],
                        'type': 'function',
                        'function': {'name': tool_call['function']['name'], 'arguments': ''}
                    }]
                },
                'finish_reason': None
            }]
        }, ensure_ascii=False)}\n\n"
        
        args = tool_call['function']['arguments']
        mid = len(args) // 2
        if mid > 0:
            yield f"data: {json.dumps({
                'id': response_id,
                'object': 'chat.completion.chunk',
                'created': int(time.time()),
                'model': self.model_name,
                'choices': [{
                    'index': 0,
                    'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': args[:mid]}}]},
                    'finish_reason': None
                }]
            }, ensure_ascii=False)}\n\n"
        
        yield f"data: {json.dumps({
            'id': response_id,
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': self.model_name,
            'choices': [{
                'index': 0,
                'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': args[mid:]}}]},
                'finish_reason': 'tool_calls'
            }]
        }, ensure_ascii=False)}\n\n"

    def _create_chunk(self, response_id: str, content: str) -> str:
        return f"data: {json.dumps({
            'id': response_id,
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': self.model_name,
            'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]
        }, ensure_ascii=False)}\n\n"

    def _create_error_chunk(self, response_id: str, error_message: str) -> str:
        return f"data: {json.dumps({
            'id': response_id,
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': self.model_name,
            'choices': [{
                'index': 0,
                'delta': {'role': 'assistant', 'content': f'Error: {error_message}'},
                'finish_reason': 'stop'
            }]
        }, ensure_ascii=False)}\n\n"

    def parse_tool_calls_from_buffer(self, buffer: str) -> List[dict]:
        tool_calls = []
        for match in self.tool_call_pattern.findall(buffer):
            try:
                match_data = json.loads(match)
                tool_calls.append({
                    "id": f"call{int(time.time())}",
                    "type": "function",
                    "function": {
                        "name": match_data['name'],
                        "arguments": json.dumps(match_data['arguments'], ensure_ascii=False)
                    }
                })
            except Exception as e:
                logger.warning(f"Parse error: {e}")
        return tool_calls