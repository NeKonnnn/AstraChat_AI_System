import os
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class DiarizationConfig(BaseModel):
    enabled: bool = True
    # Важно: путь должен вести к файлу config.yaml внутри контейнера
    config_path: str = "diarize_models/config.yaml" 
    # Важно: папка, где лежат модели
    models_dir: str = "diarize_models"
    device: str = "auto"
    max_file_size: int = 200 * 1024 * 1024
    
class Settings(BaseSettings):
    diarization: DiarizationConfig = DiarizationConfig()

settings = Settings()