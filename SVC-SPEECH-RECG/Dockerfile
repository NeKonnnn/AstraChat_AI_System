FROM ubuntu:22.04

WORKDIR /app

# Установка переменных окружения 
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Установка timezone 
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Установка Python 3.11 и системных зависимостей 
# Здесь есть ffmpeg, sox, libsndfile - всё нужное для STT
RUN apt-get update && apt-get install -y \
    software-properties-common \
    tzdata \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    python3-pip \
    build-essential \
    cmake \
    gcc \
    g++ \
    curl \
    libopenblas-dev \
    git \
    pkg-config \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    wget \
    unzip \
    libsndfile1 \
    libsndfile1-dev \
    libsox-dev \
    sox \
    && rm -rf /var/lib/apt/lists/*

# Создание символической ссылки для python 
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Флаги для сборки 
ENV CMAKE_ARGS="-DGGML_METAL=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" \
    CFLAGS="-pthread" \
    CXXFLAGS="-pthread -mcpu=native"

# Установка Python зависимостей 
COPY requirements.txt .
RUN python3.11 -m pip install --upgrade pip && \
    python3.11 -m pip install --no-cache-dir --prefer-binary --timeout 120 --retries 5 -r requirements.txt

# Переменные окружения 
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Настройка многопоточности 
ENV OMP_NUM_THREADS=8
ENV OPENBLAS_NUM_THREADS=8
ENV MKL_NUM_THREADS=8

# Копирование исходного кода и конфигурации 
COPY app/ ./app/
COPY config/ ./config/

# Создание директории для моделей (модели монтируются томами, копирование не требуется)
RUN mkdir -p /app/models/vosk /app/models/whisperx_models

# Создание непривилегированного пользователя 
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Установка прав доступа к папке моделей
RUN chmod -R 755 /app/models

USER appuser

EXPOSE 8000

# Запуск
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]