"""
Модели данных для MongoDB
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Модель сообщения в диалоге"""
    
    message_id: str = Field(..., description="Уникальный ID сообщения")
    role: str = Field(..., description="Роль: user, assistant, system")
    content: str = Field(..., description="Содержание сообщения")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Временная метка")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные метаданные")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_123",
                "role": "user",
                "content": "Привет!",
                "timestamp": "2024-01-01T10:00:00Z",
                "metadata": {
                    "model": "qwen3-coder",
                    "tokens": 5
                }
            }
        }


class Conversation(BaseModel):
    """Модель диалога"""
    
    conversation_id: str = Field(..., description="Уникальный ID диалога")
    user_id: Optional[str] = Field(None, description="ID пользователя")
    title: Optional[str] = Field(None, description="Название диалога")
    messages: List[Message] = Field(default_factory=list, description="Список сообщений")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные метаданные")
    expires_at: Optional[datetime] = Field(None, description="Дата истечения для TTL")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_123",
                "user_id": "user_456",
                "title": "Разговор о Python",
                "messages": [
                    {
                        "message_id": "msg_1",
                        "role": "user",
                        "content": "Привет!",
                        "timestamp": "2024-01-01T10:00:00Z"
                    }
                ],
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z",
                "metadata": {}
            }
        }








