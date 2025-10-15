# Dockerfile для MemoAI Backend
FROM ubuntu:22.04

# Установка Python и системных зависимостей
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    libsndfile1 \
    portaudio19-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Создание символической ссылки для python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Установка рабочей директории
WORKDIR /app

# Копирование requirements.txt
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание только необходимых директорий для backend
RUN mkdir -p /app/memory /app/logs /app/uploads /tmp/memoai

# Установка переменных окружения
ENV PYTHONPATH=/app
ENV MODEL_PATH=/app/models/model.gguf

# Открытие порта
EXPOSE 8000

# Команда запуска
CMD ["python", "main.py"]
