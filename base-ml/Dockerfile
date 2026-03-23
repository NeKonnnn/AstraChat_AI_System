# =============================================================================
# astrachat-base-ml — общий базовый образ для всех ML-сервисов
#
# Содержит:
#   - Ubuntu 22.04 + Python 3.11
#   - Все системные зависимости (superset всех сервисов)
#   - torch==2.1.2 + torchaudio==2.1.2 + numpy + scipy
#
# Собирается ОДИН раз, потом все сервисы наследуют готовый torch:
#   docker build -t astrachat-base-ml:latest ./base-ml
#
# (или через скрипт: ./build.sh)
# =============================================================================

FROM ubuntu:22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Системные зависимости — superset для всех ML-сервисов:
#   ffmpeg + libav* (STT/WhisperX), libsndfile/sox (аудио), libopenblas (torch BLAS),
#   libgl1/libglib2.0 (OpenCV/Surya OCR), libldap/libsasl (python-ldap)
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
    libldap2-dev \
    libsasl2-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Общие ENV для всех сервисов
ENV CMAKE_ARGS="-DGGML_METAL=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" \
    CFLAGS="-pthread" \
    CXXFLAGS="-pthread" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=8 \
    OPENBLAS_NUM_THREADS=8 \
    MKL_NUM_THREADS=8 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

RUN python3.11 -m pip install --upgrade pip

# torch==2.1.2 + torchaudio==2.1.2 — самый тяжёлый пакет (~1.5 ГБ).
# Устанавливается ОДИН раз здесь, все сервисы наследуют через FROM.
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.11 -m pip install --timeout 300 --retries 10 \
    "torch>=2.4.0,<2.6.0" \
    --index-url https://download.pytorch.org/whl/cpu

# Базовые научные библиотеки — нужны практически всем сервисам
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.11 -m pip install --prefer-binary --timeout 300 --retries 10 \
    "numpy>=1.24.3,<2.0.0" \
    "scipy>=1.10.0"

# Непривилегированный пользователь — создаётся здесь, сервисы просто делают chown
RUN useradd -m -u 1000 appuser
