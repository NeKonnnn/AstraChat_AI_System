import os
from typing import List
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class VoskConfig(BaseModel):
    enabled: bool = True
    model_path: str = "model_small" 
    sample_rate: int = 16000
    # 50 MB по умолчанию
    max_file_size: int = 50 * 1024 * 1024
    supported_languages: List[str] = ["ru", "en"]

class WhisperXConfig(BaseModel):
    enabled: bool = True
    models_dir: str = "whisperx_models"
    device: str = "auto" 
    compute_type: str = "auto"
    supported_languages: List[str] = ["ru", "en"]
    # 100 MB для Whisper
    max_file_size: int = 100 * 1024 * 1024
    batch_size: int = 16

class Settings(BaseSettings):
    vosk: VoskConfig = VoskConfig()
    whisperx: WhisperXConfig = WhisperXConfig()

settings = Settings()