from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any, Union
from enum import Enum

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: str

class ChatCompletionRequestSystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: str

class ChatCompletionRequestUserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: Union[str, List[Dict[str, Any]]]

class ChatCompletionRequestAssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class ChatCompletionRequestToolMessage(BaseModel):
    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str

class ChatCompletionRequestFunctionMessage(BaseModel):
    role: Literal["function"] = "function"
    content: str

class ChatRequest(BaseModel):
    model: str = "abstract-model"
    messages: List[Message]
    temperature: Optional[float] = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(256, ge=1)
    stream: Optional[bool] = False

class ChatChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[str] = "stop"

class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: Optional[str] = None

class ModelsListResponse(BaseModel):
    data: List[Dict[str, Any]]
    object: str = "list"
