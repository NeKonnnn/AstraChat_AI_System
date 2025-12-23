# Используем легкий образ Python 3.12
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Устанавливаем системные библиотеки, необходимые для работы со звуком (ffmpeg, libsndfile)
# Без них torchaudio или scipy могут выдавать ошибки
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем библиотеки Python
# --no-cache-dir делает образ легче
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY app/ ./app/

# Копируем папку с моделями внутрь контейнера
# ВАЖНО: папка silero_models должна лежать рядом с Dockerfile при сборке
COPY silero_models/ ./silero_models/

# Сообщаем, что контейнер будет слушать порт 8000
EXPOSE 8000

# Команда для запуска сервера
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]