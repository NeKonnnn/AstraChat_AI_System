import os
from typing import List
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class SuryaConfig(BaseModel):
    enabled: bool = True
    # Путь внутри контейнера
    models_dir: str = "/app/models/surya" 
    device: str = "auto"
    max_file_size: int = 50 * 1024 * 1024
    supported_languages: List[str] = ["ru", "en"]

class Settings(BaseSettings):
    surya: SuryaConfig = SuryaConfig()

settings = Settings()