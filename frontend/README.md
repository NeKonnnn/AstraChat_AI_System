# astrachat Frontend

Frontend приложение для astrachat - персонального AI ассистента.

## Системные требования

- **Node.js**: версия 18.0.0 или выше (рекомендуется 18.x или 20.x)
- **npm**: версия 8.0.0 или выше (обычно поставляется с Node.js)

## Установка зависимостей

### Автоматическая установка (рекомендуется)

```bash
# Перейти в корневую директорию проекта
cd F:\memo_new_api

# Установить все зависимости (включая фронтенд)
npm run install:all
```

### Ручная установка

```bash
# 1. Установить зависимости корневого проекта
npm install

# 2. Перейти в папку фронтенда
cd frontend

# 3. Установить зависимости фронтенда
npm install
```

## Запуск проекта

### Разработка
```bash
# Запустить и бэкенд, и фронтенд одновременно
npm run dev
```

### Только фронтенд
```bash
cd frontend
npm start
```

### Сборка для продакшена
```bash
npm run build
```

## Настройка API

Приложение использует централизованную конфигурацию API в файле `src/config/api.ts`.

### Переменные окружения

Создайте файл `.env` в корне frontend папки со следующими настройками:

```bash
# API Configuration
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000

# Development settings
REACT_APP_DEBUG=true
REACT_APP_LOG_LEVEL=info
```

### Структура API

Все API эндпоинты определены в `src/config/api.ts`:

- **Чат**: `/api/chat`
- **Голос**: `/api/voice/*`
- **Транскрибация**: `/api/transcribe/*`
- **Документы**: `/api/documents/*`
- **Модели**: `/api/models/*`
- **История**: `/api/history`

## Основные зависимости

- **React 19.1.1** - Основная библиотека React
- **Material-UI 7.3.1** - UI компоненты
- **TypeScript 4.9.5** - TypeScript компилятор
- **React Router 7.8.1** - Маршрутизация
- **Axios 1.11.0** - HTTP клиент
- **Socket.IO 4.8.1** - WebSocket клиент
- **React Markdown 10.1.0** - Рендеринг Markdown
- **Recharts 3.1.2** - Графики и визуализация

## Возможные проблемы и решения

### Ошибка версии Node.js
Если возникает ошибка с версией Node.js, обновите до версии 18.x или 20.x:
```bash
# Проверить текущую версию
node --version

# Обновить через nvm (если установлен)
nvm install 20
nvm use 20
```

### Ошибки с зависимостями
Если возникают проблемы с установкой зависимостей:
```bash
# Очистить кэш npm
npm cache clean --force

# Удалить node_modules и переустановить
rm -rf node_modules package-lock.json
npm install
```


