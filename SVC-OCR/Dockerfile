FROM python:3.10-slim

WORKDIR /app

# Библиотеки для работы с изображениями (OpenCV/Pillow)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем папку для моделей
RUN mkdir -p /app/models/surya

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]