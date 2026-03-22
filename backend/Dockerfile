FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# portaudio/espeak/libasound убраны — в Docker-контейнере нет аудиоустройств.
# llama-cpp-python тоже убран из requirements.txt — inference через llm-svc.
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
    libsndfile1-dev \
    ffmpeg \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN python3 -m pip install --upgrade pip setuptools wheel

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --prefer-binary --upgrade-strategy only-if-needed \
    --timeout 300 --retries 10 -r requirements.txt

COPY --chown=root:root . /app/

RUN mkdir -p /app/memory /app/logs /app/uploads /tmp/astrachat

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Симлинк нужен: volume-маунт ./backend:/app делает /app/ == ./backend/,
# и без него "from backend.xxx import" не работает (нет /app/backend/).
# Пакеты внутри backend/ НЕЛЬЗЯ называть именами stdlib или установленных пакетов
# (socket, socketio, asyncio и т.д.) — они будут видны Python как /app/<name>/.
RUN ln -sf /app /app/backend

EXPOSE 8000

CMD ["python", "main.py"]
