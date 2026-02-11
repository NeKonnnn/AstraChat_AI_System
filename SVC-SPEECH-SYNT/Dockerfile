FROM ubuntu:22.04

WORKDIR /app

# Установка переменных окружения (ОРИГИНАЛ)
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Установка timezone без интерактивного промпта (ОРИГИНАЛ)
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Установка Python 3.11 и системных зависимостей (ОРИГИНАЛ)
# Для TTS критически важны: ffmpeg, libsndfile1, sox
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
    wget \
    unzip \
    libsndfile1 \
    libsndfile1-dev \
    libsox-dev \
    sox \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# Создание символической ссылки для python (ОРИГИНАЛ)
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Флаги для сборки (ОРИГИНАЛ)
ENV CMAKE_ARGS="-DGGML_METAL=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" \
    CFLAGS="-pthread -mcpu=native" \
    CXXFLAGS="-pthread -mcpu=native"

# Установка Python зависимостей (ОРИГИНАЛ)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

# Переменные окружения (ОРИГИНАЛ)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Настройка многопоточности (ОРИГИНАЛ)
ENV OMP_NUM_THREADS=8
ENV OPENBLAS_NUM_THREADS=8
ENV MKL_NUM_THREADS=8

# Копирование исходного кода и конфигурации (ТЕПЕРЬ ТОЛЬКО ДЛЯ ЭТОГО СЕРВИСА)
COPY app/ ./app/
COPY config/ ./config/

# Создание директории для моделей
RUN mkdir -p /app/models

# --- СПЕЦИФИКА TTS: Копируем локальную папку моделей в образ ---
# Мы кладем их по пути, который указали в .env и config.yml
COPY silero_models/ /app/models/silero/

# Создание непривилегированного пользователя (ОРИГИНАЛ)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Установка прав доступа к папке моделей
RUN chmod -R 755 /app/models

USER appuser

EXPOSE 8000

# Запуск (использует .env файл, переданный при старте docker run)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]