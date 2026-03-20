"""
schemas.py - Pydantic-модели запросов/ответов
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    streaming: bool = True


class ModelSettings(BaseModel):
    context_size: int = 2048
    output_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.95
    repeat_penalty: float = 1.05
    top_k: int = 40
    min_p: float = 0.05
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    use_gpu: bool = False
    streaming: bool = True


class VoiceSettings(BaseModel):
    voice_id: str = "ru"
    speech_rate: float = 1.0
    voice_speaker: str = "baya"


class MemorySettings(BaseModel):
    max_messages: int = 20
    include_system_prompts: bool = True
    clear_on_restart: bool = False


class ModelLoadRequest(BaseModel):
    model_path: str


class ModelLoadResponse(BaseModel):
    message: str
    success: bool


class VoiceSynthesizeRequest(BaseModel):
    text: str
    voice_id: str = "ru"
    voice_speaker: str = "baya"
    speech_rate: float = 1.0


class TranscriptionSettings(BaseModel):
    engine: str = "whisperx"
    language: str = "ru"
    auto_detect: bool = True


class YouTubeTranscribeRequest(BaseModel):
    url: str


class DocumentQueryRequest(BaseModel):
    query: str


class RAGSettings(BaseModel):
    strategy: str = "auto"  # auto | reranking | hierarchical | hybrid | standard


class AgentModeRequest(BaseModel):
    mode: str  # "agent" | "direct" | "multi-llm"


class MultiLLMModelsRequest(BaseModel):
    models: List[str]


class AgentStatusResponse(BaseModel):
    is_initialized: bool
    mode: str
    available_agents: int
    orchestrator_active: bool
