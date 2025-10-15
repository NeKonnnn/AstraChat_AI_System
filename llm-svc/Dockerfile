FROM ubuntu:22.04

WORKDIR /app

# Установка Python и системных зависимостей
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    gcc \
    g++ \
    curl \
    libopenblas-dev \
    git \
    pkg-config \
    ffmpeg \
    wget \
    unzip \
    libsndfile1 \
    libsndfile1-dev \
    libsox-dev \
    sox \
    && rm -rf /var/lib/apt/lists/*

# Создание символической ссылки для python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Флаги для сборки llama.cpp (без Metal!)
ENV CMAKE_ARGS="-DGGML_METAL=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" \
    CFLAGS="-pthread -mcpu=native" \
    CXXFLAGS="-pthread -mcpu=native"

# Установка Python зависимостей
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Настройка переменных окружения для многопоточности

ENV OMP_NUM_THREADS=8
ENV OPENBLAS_NUM_THREADS=8
ENV MKL_NUM_THREADS=8
ENV VECLIB_MAXIMUM_THREADS=8
ENV NUMEXPR_NUM_THREADS=8

# Копирование исходного кода и конфигурации
COPY app/ ./app/
COPY config/ ./config/

# Создание только базовой директории для моделей (если нужно)
# RUN mkdir -p /app/models

# Скачивание модели Vosk (русская, маленькая)
RUN wget -O /tmp/vosk-model.zip https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip && \
    unzip /tmp/vosk-model.zip -d /app/models/ && \
    rm /tmp/vosk-model.zip

# Копирование конфигурации диаризации
COPY diarize_models/pyannote_diarization_config.yaml /app/models/diarization/

# Создание непривилегированного пользователя
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Установка прав доступа к папке моделей
RUN chmod -R 755 /app/models

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]