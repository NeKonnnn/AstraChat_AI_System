import os
from typing import Dict, List
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class SileroConfig(BaseModel):
    enabled: bool = True
    models_dir: str = "silero_models"
    max_text_length: int = 5000  # Максимальная длина текста
    
    # Списки поддерживаемых языков и голосов (взяты из документации Silero)
    supported_languages: List[str] = ["ru", "en"]
    supported_speakers: Dict[str, List[str]] = {
        "ru": ["baya", "kseniya", "xenia", "eugene", "aidar"],
        "en": ["v3_en"] # Стандартный голос для английского v3
    }

class Settings(BaseSettings):
    silero: SileroConfig = SileroConfig()

settings = Settings()