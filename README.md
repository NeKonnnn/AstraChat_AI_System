![Astra Chat Logo](assets/Astra_logo.png)

# MemoAI - Интеллектуальная AI-ассистент система

## Описание проекта

MemoAI - это современная интеллектуальная система с агентной архитектурой, объединяющая возможности больших языковых моделей (LLM), речевого распознавания, синтеза речи и анализа аудио. Система построена на микросервисной архитектуре с использованием Docker и поддерживает как локальные, так и облачные AI модели.

### Ключевые возможности

- **Агентная архитектура** - интеллектуальные агенты для разных задач
- **LLM интеграция** - поддержка Qwen, Llama, DeepSeek и других моделей
- **Речевое распознавание** - Vosk и WhisperX для транскрипции
- **Синтез речи** - Silero TTS для генерации голоса
- **Диаризация** - разделение аудио по спикерам
- **Облачная поддержка** - модели могут быть в S3, HTTP или локально
- **Docker** - полная контейнеризация для простого развертывания
- **WebSocket** - сетевой протокол для взаимодействия в режиме реального времени
- **React UI** - современный веб-интерфейс

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ПОЛЬЗОВАТЕЛЬ (ЧЕЛОВЕК)                                │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                                      │
│  • Современный UI с Material-UI                                                 │
│  • WebSocket для реального времени                                              │
│  • Загрузка аудио файлов                                                        │
│  • Отображение результатов                                                      │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ HTTP/WebSocket
                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                                     │
│  • Агентная архитектура (LangGraph)                                             │
│  • Обработка запросов пользователя                                              │
│  • Управление памятью и контекстом                                              │
│  • Выбор и оркестрация агентов                                                  │
│  • Интеграция с внешними сервисами                                              │
└─────────────────────┬───────────────────────────────────────────────────────────┘
                      │ HTTP REST API
                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LLM-SVC (AI Models Service)                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │     LLM     │ │    VOSK     │ │   SILERO    │ │  WHISPERX   │ │ DIARIZATION ││
│  │   модели    │ │ транскрипция│ │   синтез    │ │ транскрипция│ │  спикеры    ││
│  │             │ │             │ │    речи     │ │             │ │             ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           МОДЕЛИ (Локальные/Облачные)                           │
│  • LLM: Qwen, Llama, DeepSeek (локально или S3)                                 │
│  • Vosk: vosk-model-small-ru-0.22 (локально или HTTP)                           │
│  • Silero: baya, kseniya, xenia, eugene, aidar (локально или S3)                │
│  • WhisperX: faster-whisper models (локально или HuggingFace)                   │
│  • Diarization: pyannote.audio models (локально или S3)                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Стэк используемых технологий

### Backend
- **FastAPI** - современный веб-фреймворк
- **LangGraph** - агентная оркестрация
- **Pydantic** - валидация данных
- **httpx** - асинхронный HTTP клиент
- **WebSocket** - сетевой протокол для взаимодействия в режиме реального времени

### Frontend
- **React 19** - UI библиотека
- **TypeScript** - типизированный JavaScript
- **Material-UI (MUI)** - компоненты интерфейса
- **Axios** - HTTP клиент
- **Socket.io** - веб-сокеты
- **React Router** - маршрутизация
- **Webpack** - сборщик модулей
- **Babel** - транспилятор JavaScript
- **ESLint** - линтер кода
- **Prettier** - форматирование кода

### AI Models Service (llm-svc)
- **llama-cpp-python** - LLM модели
- **Vosk** - речевое распознавание
- **Silero TTS** - синтез речи
- **WhisperX** - продвинутая транскрипция
- **pyannote.audio** - диаризация спикеров

### Инфраструктура
- **Docker & Docker Compose** - контейнеризация
- **Nginx** - веб-сервер (опционально)
- **S3/HTTP** - облачное хранилище моделей

## Быстрый старт

### Предварительные требования

- **Docker** и Docker Compose
- **Git**
- **Минимум 8GB RAM** (для работы с AI моделями)
- **Минимум 20GB свободного места** на диске
- **Интернет** (для загрузки моделей)

### 1. Клонирование репозитория

```bash
git clone <your-repository-url>
cd memoai
```

### 2. Настройка окружения

```bash
# Создайте .env файл из примера
cp env.main.example .env

# Отредактируйте конфигурацию
nano .env
```

### 2.1. Настройка фронтенда (опционально для разработки)

```bash
# Установка Node.js (если еще не установлен)
# См. подробную инструкцию в разделе "Разработка Frontend"

# Переход в директорию фронтенда
cd frontend

# Установка зависимостей
npm install

# Создание .env файла для фронтенда
cat > .env << EOF
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_LLM_SVC_URL=http://localhost:8001
NODE_ENV=development
EOF

# Запуск в режиме разработки
npm start
```

### 3. Запуск системы

```bash
# Запуск всех сервисов
docker-compose up

# Или в фоновом режиме
docker-compose up -d
```

### 4. Проверка работы

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **LLM Service**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

## Разработка Frontend

### Предварительные требования для фронтенда

- **Node.js 18+** (рекомендуется LTS версия)
- **npm 9+** или **yarn 1.22+**
- **Git** для версионирования

### Установка Node.js

#### Windows
```bash
# Скачайте с официального сайта
# https://nodejs.org/en/download/

# Или через Chocolatey
choco install nodejs

# Или через winget
winget install OpenJS.NodeJS
```

#### Linux (Ubuntu/Debian)
```bash
# Установка через NodeSource
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Проверка версии
node --version
npm --version
```

#### Linux (CentOS/RHEL)
```bash
# Установка через NodeSource
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo yum install -y nodejs

# Проверка версии
node --version
npm --version
```

#### macOS
```bash
# Через Homebrew
brew install node

# Или скачайте с официального сайта
# https://nodejs.org/en/download/
```

### Установка зависимостей фронтенда

```bash
# Переход в директорию фронтенда
cd frontend

# Установка зависимостей
npm install

# Или через yarn
yarn install
```

### Структура фронтенда

```
frontend/
├── public/                 # Статические файлы
│   ├── index.html         # Главная HTML страница
│   ├── favicon.ico        # Иконка сайта
│   └── manifest.json      # Манифест PWA
├── src/                   # Исходный код
│   ├── components/        # React компоненты
│   │   ├── Chat/         # Компоненты чата
│   │   ├── Audio/        # Аудио компоненты
│   │   ├── UI/           # UI компоненты
│   │   └── Layout/       # Компоненты макета
│   ├── pages/            # Страницы приложения
│   │   ├── Home.tsx      # Главная страница
│   │   ├── Chat.tsx      # Страница чата
│   │   └── Settings.tsx  # Настройки
│   ├── services/         # API сервисы
│   │   ├── api.ts        # HTTP клиент
│   │   ├── websocket.ts  # WebSocket клиент
│   │   └── auth.ts       # Аутентификация
│   ├── hooks/            # React хуки
│   ├── utils/            # Утилиты
│   ├── types/            # TypeScript типы
│   ├── styles/           # Стили
│   ├── App.tsx           # Главный компонент
│   └── index.tsx         # Точка входа
├── package.json          # Зависимости и скрипты
├── tsconfig.json         # Конфигурация TypeScript
├── webpack.config.js     # Конфигурация Webpack
├── .eslintrc.js          # Конфигурация ESLint
├── .prettierrc           # Конфигурация Prettier
└── Dockerfile            # Docker конфигурация
```

### Основные зависимости фронтенда

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@mui/material": "^5.15.0",
    "@mui/icons-material": "^5.15.0",
    "@emotion/react": "^11.11.0",
    "@emotion/styled": "^11.11.0",
    "axios": "^1.6.0",
    "socket.io-client": "^4.7.0",
    "react-router-dom": "^6.20.0",
    "react-query": "^3.39.0",
    "react-hook-form": "^7.48.0",
    "react-dropzone": "^14.2.0",
    "react-audio-player": "^0.17.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@types/node": "^20.10.0",
    "typescript": "^5.3.0",
    "webpack": "^5.89.0",
    "webpack-cli": "^5.1.0",
    "webpack-dev-server": "^4.15.0",
    "babel-loader": "^9.1.0",
    "@babel/core": "^7.23.0",
    "@babel/preset-env": "^7.23.0",
    "@babel/preset-react": "^7.22.0",
    "@babel/preset-typescript": "^7.23.0",
    "eslint": "^8.55.0",
    "prettier": "^3.1.0",
    "css-loader": "^6.8.0",
    "style-loader": "^3.3.0",
    "file-loader": "^6.2.0"
  }
}
```

### Запуск фронтенда в режиме разработки

```bash
# Переход в директорию фронтенда
cd frontend

# Установка зависимостей (если еще не установлены)
npm install

# Запуск в режиме разработки
npm start

# Или через yarn
yarn start
```

### Сборка для продакшена

```bash
# Сборка production версии
npm run build

# Или через yarn
yarn build
```

### Настройка переменных окружения фронтенда

Создайте файл `frontend/.env`:

```bash
# API URL для backend
REACT_APP_API_URL=http://localhost:8000

# WebSocket URL
REACT_APP_WS_URL=ws://localhost:8000

# URL для LLM Service (если нужен прямой доступ)
REACT_APP_LLM_SVC_URL=http://localhost:8001

# Режим разработки
NODE_ENV=development

# Публичный URL (для продакшена)
PUBLIC_URL=https://yourdomain.com
```

### Настройка Nginx для фронтенда

#### Установка Nginx

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx

# macOS
brew install nginx

# Windows
# Скачайте с официального сайта
# https://nginx.org/en/download.html
```

#### Конфигурация Nginx для фронтенда

Создайте файл `/etc/nginx/sites-available/memoai-frontend`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Корневая директория фронтенда
    root /var/www/memoai/frontend/build;
    index index.html index.htm;
    
    # Gzip сжатие
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # Кэширование статических файлов
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Обработка React Router
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API проксирование на backend
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket проксирование
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Безопасность
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

#### Активация конфигурации

```bash
# Создание символической ссылки
sudo ln -s /etc/nginx/sites-available/memoai-frontend /etc/nginx/sites-enabled/

# Удаление дефолтной конфигурации
sudo rm /etc/nginx/sites-enabled/default

# Проверка конфигурации
sudo nginx -t

# Перезапуск Nginx
sudo systemctl restart nginx
```

### Развертывание фронтенда

#### 1. Сборка приложения

```bash
# В директории frontend
npm run build

# Копирование в веб-директорию
sudo cp -r build/* /var/www/memoai/frontend/
```

#### 2. Настройка прав доступа

```bash
# Создание директории
sudo mkdir -p /var/www/memoai/frontend

# Установка прав
sudo chown -R www-data:www-data /var/www/memoai/frontend
sudo chmod -R 755 /var/www/memoai/frontend
```

#### 3. SSL сертификаты

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение SSL сертификата
sudo certbot --nginx -d yourdomain.com

# Автоматическое обновление
sudo crontab -e
# Добавьте строку:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

### Отладка фронтенда

#### Просмотр логов

```bash
# Логи Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Логи systemd (если используете)
sudo journalctl -u nginx -f
```

#### Проверка конфигурации

```bash
# Проверка синтаксиса Nginx
sudo nginx -t

# Проверка статуса
sudo systemctl status nginx

# Перезапуск
sudo systemctl restart nginx
```

#### Отладка в браузере

1. Откройте Developer Tools (F12)
2. Перейдите на вкладку Console
3. Проверьте ошибки JavaScript
4. Перейдите на вкладку Network
5. Проверьте HTTP запросы

### Оптимизация фронтенда

#### 1. Сжатие файлов

```bash
# Установка gzip
sudo apt install gzip

# Сжатие статических файлов
gzip -k -9 /var/www/memoai/frontend/static/css/*.css
gzip -k -9 /var/www/memoai/frontend/static/js/*.js
```

#### 2. CDN настройка

```bash
# В .env файле добавьте CDN URL
REACT_APP_CDN_URL=https://cdn.yourdomain.com
```

#### 3. Кэширование

```nginx
# В конфигурации Nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Конфигурация

### Переменные окружения (.env файл)

Основные настройки системы:

```bash
# ===========================================
# ОСНОВНЫЕ НАСТРОЙКИ
# ===========================================
NODE_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# ===========================================
# ПУТИ К МОДЕЛЯМ (настраиваемые)
# ===========================================

# LLM модели
LLM_MODEL_PATH=/app/models/Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf
LLM_MODEL_NAME=qwen-coder-30b

# Vosk модели (речевое распознавание)
VOSK_MODEL_PATH=/app/models/vosk-model-small-ru-0.22

# Silero модели (синтез речи)
SILERO_MODELS_DIR=/app/models/silero

# WhisperX модели (продвинутое распознавание)
WHISPERX_MODELS_DIR=/app/models/whisperx

# Модели диаризации (разделение по спикерам)
DIARIZATION_MODELS_DIR=/app/models/diarization
DIARIZATION_CONFIG_PATH=/app/models/diarization/pyannote_diarization_config.yaml
```

### Поддерживаемые форматы путей к моделям

#### 1. Локальные модели
```bash
LLM_MODEL_PATH=/app/models/Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf
VOSK_MODEL_PATH=/app/models/vosk-model-small-ru-0.22
```

#### 2. Облачное хранилище (S3)
```bash
LLM_MODEL_PATH=s3://my-bucket/models/Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf
VOSK_MODEL_PATH=s3://my-bucket/models/vosk-model-small-ru-0.22
SILERO_MODELS_DIR=s3://my-bucket/models/silero
```

#### 3. HTTP/HTTPS URL
```bash
LLM_MODEL_PATH=https://huggingface.co/microsoft/DialoGPT-medium/resolve/main/pytorch_model.bin
VOSK_MODEL_PATH=https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22
SILERO_MODELS_DIR=https://models.silero.ai/models/tts/ru
```

#### 4. Google Cloud Storage
```bash
LLM_MODEL_PATH=gs://my-bucket/models/Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf
VOSK_MODEL_PATH=gs://my-bucket/models/vosk-model-small-ru-0.22
```

## Агентная архитектура

### Доступные агенты

1. **General Agent** - общие задачи и диалог
2. **Calculation Agent** - математические вычисления
3. **Document Agent** - работа с документами
4. **Web Search Agent** - поиск в интернете
5. **Memory Agent** - управление памятью
6. **MCP Agent** - интеграция с внешними сервисами

### Оркестрация агентов

Система использует LangGraph для интеллектуального выбора и координации агентов:

```python
# Пример использования агентов
from backend.agents.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
result = await orchestrator.process_request(
    user_input="Сколько будет 2+2?",
    context={"user_id": "123", "session_id": "abc"}
)
```

## API Endpoints

### Backend API (порт 8000)

#### Чат с AI
```http
POST /chat
Content-Type: application/json

{
  "message": "Привет, как дела?",
  "context": {
    "user_id": "123",
    "session_id": "abc"
  }
}
```

#### Загрузка аудио
```http
POST /upload-audio
Content-Type: multipart/form-data

file: audio.wav
language: ru
```

#### WebSocket для реального времени
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.send(JSON.stringify({
  type: 'message',
  data: { message: 'Привет!' }
}));
```

### LLM Service API (порт 8001)

#### LLM генерация
```http
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "qwen-coder-30b",
  "messages": [
    {"role": "user", "content": "Привет!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

#### Транскрипция (Vosk)
```http
POST /v1/transcribe
Content-Type: multipart/form-data

file: audio.wav
language: ru
```

#### Транскрипция (WhisperX)
```http
POST /v1/whisperx/transcribe
Content-Type: multipart/form-data

file: audio.wav
language: auto
compute_type: float16
```

#### Синтез речи (Silero)
```http
POST /v1/tts/synthesize
Content-Type: application/json

{
  "text": "Привет, как дела?",
  "language": "ru",
  "speaker": "baya",
  "sample_rate": 48000
}
```

#### Диаризация
```http
POST /v1/diarize
Content-Type: multipart/form-data

file: audio.wav
min_speakers: 1
max_speakers: 5
```

## Docker развертывание

### Структура сервисов

```yaml
services:
  llm-svc:          # AI Models Service (порт 8001)
  memoai-backend:   # Backend API (порт 8000)
  memoai-frontend:  # React UI (порт 3000)
  nginx:            # Веб-сервер (порт 80/443) - опционально
```

### Dockerfile для фронтенда

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine as build

# Установка рабочей директории
WORKDIR /app

# Копирование package.json и package-lock.json
COPY package*.json ./

# Установка зависимостей
RUN npm ci --only=production

# Копирование исходного кода
COPY . .

# Сборка приложения
RUN npm run build

# Production stage
FROM nginx:alpine

# Копирование собранного приложения
COPY --from=build /app/build /usr/share/nginx/html

# Копирование конфигурации Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открытие порта
EXPOSE 80

# Запуск Nginx
CMD ["nginx", "-g", "daemon off;"]
```

### Конфигурация Nginx для Docker

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name localhost;
    
    root /usr/share/nginx/html;
    index index.html index.htm;
    
    # Gzip сжатие
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # Кэширование статических файлов
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Обработка React Router
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API проксирование на backend
    location /api/ {
        proxy_pass http://memoai-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket проксирование
    location /ws/ {
        proxy_pass http://memoai-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Переменные окружения для фронтенда в Docker

```yaml
# В docker-compose.yml
memoai-frontend:
  environment:
    - REACT_APP_API_URL=${REACT_APP_API_URL:-http://localhost:8000}
    - REACT_APP_WS_URL=${REACT_APP_WS_URL:-ws://localhost:8000}
    - NODE_ENV=${NODE_ENV:-development}
    - PUBLIC_URL=${PUBLIC_URL:-/}
```

### Запуск

```bash
# Разработка
docker-compose up

# Продакшн
docker-compose -f docker-compose.prod.yml up -d

# Только определенные сервисы
docker-compose up llm-svc memoai-backend
```

### Управление

```bash
# Просмотр статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f llm-svc
docker-compose logs -f memoai-backend

# Перезапуск сервиса
docker-compose restart llm-svc

# Остановка всех сервисов
docker-compose down

# Очистка (ОСТОРОЖНО!)
docker-compose down -v --rmi all
```

## Структура проекта

```
memoai/
├── backend/                    # Backend сервис
│   ├── agents/                # Агентная архитектура
│   ├── config/                # Конфигурация backend
│   ├── tools/                 # Инструменты агентов
│   ├── orchestrator/          # LangGraph оркестратор
│   ├── llm_client.py          # Клиент для llm-svc
│   └── main.py                # Точка входа
├── llm-svc/                   # AI Models Service
│   ├── app/
│   │   ├── api/endpoints/     # API эндпоинты
│   │   ├── dependencies/      # Обработчики моделей
│   │   └── core/              # Конфигурация
│   ├── config/                # Конфигурация llm-svc
│   └── requirements.txt       # Python зависимости
├── frontend/                  # React приложение
│   ├── src/
│   │   ├── components/        # React компоненты
│   │   ├── pages/             # Страницы
│   │   └── services/          # API сервисы
│   └── package.json           # Node.js зависимости
├── docker-compose.yml         # Docker конфигурация
├── env.example               # Пример переменных окружения
└── README.md                 # Документация
```

## Миграция на облачные модели

### 1. Подготовка облачного хранилища

```bash
# AWS S3
aws s3 mb s3://my-memoai-models
aws s3 cp models/ s3://my-memoai-models/models/ --recursive
aws s3 cp silero_models/ s3://my-memoai-models/silero/ --recursive
aws s3 cp model_small/ s3://my-memoai-models/vosk-model-small-ru-0.22/ --recursive
aws s3 cp whisperx_models/ s3://my-memoai-models/whisperx/ --recursive
aws s3 cp diarize_models/ s3://my-memoai-models/diarization/ --recursive
```

### 2. Обновление .env файла

```bash
# .env
LLM_MODEL_PATH=s3://my-memoai-models/models/Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf
VOSK_MODEL_PATH=s3://my-memoai-models/vosk-model-small-ru-0.22
SILERO_MODELS_DIR=s3://my-memoai-models/silero
WHISPERX_MODELS_DIR=s3://my-memoai-models/whisperx
DIARIZATION_MODELS_DIR=s3://my-memoai-models/diarization
DIARIZATION_CONFIG_PATH=s3://my-memoai-models/diarization/pyannote_diarization_config.yaml

# AWS настройки
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
```

### 3. Удаление локальных моделей

```bash
# Безопасно удалите локальные папки
rm -rf models/
rm -rf silero_models/
rm -rf model_small/
rm -rf whisperx_models/
rm -rf diarize_models/
```

### 4. Перезапуск системы

```bash
docker-compose down
docker-compose up
```

## Продакшн развертывание

### 1. Настройка .env для продакшена

```bash
# .env
NODE_ENV=production
DEBUG=false
LOG_LEVEL=WARNING
ENABLE_SECURITY=true
API_KEY=your-very-secure-api-key-here

# CORS настройки
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Облачные модели
LLM_MODEL_PATH=s3://your-production-bucket/models/Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf
VOSK_MODEL_PATH=s3://your-production-bucket/models/vosk-model-small-ru-0.22
SILERO_MODELS_DIR=s3://your-production-bucket/models/silero
WHISPERX_MODELS_DIR=s3://your-production-bucket/models/whisperx
DIARIZATION_MODELS_DIR=s3://your-production-bucket/models/diarization
```

### 2. Настройка Nginx

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Frontend
    location / {
        proxy_pass http://memoai-frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://memoai-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # LLM Service API
    location /llm/ {
        proxy_pass http://llm-svc:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://memoai-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. SSL сертификаты

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение SSL сертификата
sudo certbot --nginx -d yourdomain.com
```

## Мониторинг и отладка

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f llm-svc
docker-compose logs -f memoai-backend
docker-compose logs -f memoai-frontend

# Последние 100 строк
docker-compose logs --tail=100 llm-svc
```

### Проверка здоровья сервисов

```bash
# Backend
curl http://localhost:8000/health

# LLM Service
curl http://localhost:8001/v1/health

# Frontend
curl http://localhost:3000
```

### Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Использование диска
docker system df

# Очистка неиспользуемых ресурсов
docker system prune -a
```

## Устранение неполадок

### Частые проблемы

#### 1. Модели не загружаются

```bash
# Проверьте переменные окружения
docker exec -it llm-svc env | grep MODEL

# Проверьте доступность облачного хранилища
docker exec -it llm-svc aws s3 ls s3://your-bucket/

# Проверьте логи
docker-compose logs llm-svc | grep -i "model\|error"
```

#### 2. CORS ошибки

```bash
# Проверьте настройки CORS в .env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Или добавьте ваш домен
CORS_ALLOWED_ORIGINS=https://yourdomain.com,http://localhost:3000
```

#### 3. Проблемы с памятью

```bash
# Увеличьте лимиты Docker
# В docker-compose.yml добавьте:
deploy:
  resources:
    limits:
      memory: 8G
    reservations:
      memory: 4G
```

#### 4. Медленная работа

```bash
# Используйте GPU (если доступен)
# В .env добавьте:
DEVICE=cuda
CUDA_VISIBLE_DEVICES=0

# Или оптимизируйте модели
LLM_MODEL_GPU_LAYERS=-1  # Использовать все слои на GPU
```

## Производительность

### Рекомендуемые настройки

#### Для CPU
```bash
# .env
DEVICE=cpu
LLM_MODEL_GPU_LAYERS=0
WHISPERX_DEVICE=cpu
DIARIZATION_DEVICE=cpu
```

#### Для GPU
```bash
# .env
DEVICE=cuda
CUDA_VISIBLE_DEVICES=0
LLM_MODEL_GPU_LAYERS=-1
WHISPERX_DEVICE=cuda
DIARIZATION_DEVICE=cuda
```

### Оптимизация

1. **Используйте GPU** для ускорения
2. **Кэшируйте модели** в Docker volumes
3. **Настройте batch_size** для WhisperX
4. **Используйте облачные модели** для масштабирования

## Безопасность

### Настройка API ключей

```bash
# .env
ENABLE_SECURITY=true
API_KEY=your-very-secure-api-key-here
RATE_LIMITING_ENABLED=true
RATE_LIMITING_REQUESTS_PER_MINUTE=100
```

### Настройка файрвола

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Масштабирование

### Горизонтальное масштабирование

```yaml
# docker-compose.scale.yml
services:
  llm-svc:
    deploy:
      replicas: 3
  memoai-backend:
    deploy:
      replicas: 2
```

### Вертикальное масштабирование

```yaml
# docker-compose.yml
services:
  llm-svc:
    deploy:
      resources:
        limits:
          memory: 16G
          cpus: '8'
```

## Обновление системы

### Обновление зависимостей

```bash
# Python зависимости
docker-compose exec llm-svc pip install --upgrade -r requirements.txt
docker-compose exec memoai-backend pip install --upgrade -r requirements.txt

# Node.js зависимости
docker-compose exec memoai-frontend npm update
```

### Обновление моделей

```bash
# Обновление через API
curl -X POST http://localhost:8001/v1/models/reload

# Или перезапуск сервиса
docker-compose restart llm-svc
```


## Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Создайте Pull Request

## Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

---

**MemoAI** - Ваш интеллектуальный AI-ассистент! 