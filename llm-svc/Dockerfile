FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gcc \
    g++ \
    curl \
    libopenblas-dev \
    git \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

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
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]