FROM ubuntu:22.04

WORKDIR /app

# Установка переменных окружения для неинтерактивной установки
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Установка timezone без интерактивного промпта
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Установка Python 3.11 и системных зависимостей
# Примечание: Python 3.12 недоступен в deadsnakes для Ubuntu 22.04,
# используем Python 3.11 который поддерживается
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
    && rm -rf /var/lib/apt/lists/*

# Создание символической ссылки для python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

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

# Создание директории для моделей
RUN mkdir -p /app/models

# Создание непривилегированного пользователя
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Установка прав доступа к папке моделей
RUN chmod -R 755 /app/models

USER appuser

EXPOSE 8000

# Запускаем uvicorn с параметрами из конфига (app.main:app читает settings)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]