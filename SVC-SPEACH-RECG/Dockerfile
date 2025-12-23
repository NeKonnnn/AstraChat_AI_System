# Используем Python 3.10 (WhisperX стабильнее на 3.10, чем на 3.12)
FROM python:3.10-slim

WORKDIR /app

# Устанавливаем системные зависимости (FFmpeg обязателен!)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .

# Устанавливаем Python библиотеки
# WhisperX иногда капризничает, поэтому флаг --no-cache-dir полезен
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY app/ ./app/

# Копируем модели (это самая долгая часть при сборке из-за размера)
COPY model_small/ ./model_small/
COPY whisperx_models/ ./whisperx_models/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]