# Модуль настроек для astrachat Frontend

Централизованное управление конфигурацией и подключениями к API и WebSocket.

## Структура

```
frontend/src/settings/
├── index.ts            # Экспорт всех классов
├── connections.ts      # Классы конфигурации подключений
├── config.ts          # Основной класс Settings
└── README.md          # Документация
```

## Использование

### Инициализация при старте приложения

```typescript
// В index.tsx или App.tsx
import { initSettings } from './settings';

// При загрузке приложения
await initSettings();
```

### Базовое использование

```typescript
import { getSettings, getUrl } from './settings';

// Получение настроек
const settings = getSettings();

// Доступ к конфигурации подключений
const apiConfig = settings.api;
const websocketConfig = settings.websocket;

// Получение URL
const backendUrl = getUrl('backend_port_1');
```

### Использование API подключения

```typescript
import { getSettings } from './settings';

const settings = getSettings();

// Получение полного URL для API endpoint
const chatUrl = settings.api.getApiUrl('/api/chat');
// Результат: http://localhost:8000/api/chat
```

### Использование WebSocket подключения

```typescript
import { getSettings } from './settings';

const settings = getSettings();

// Получение полного URL для WebSocket endpoint
const voiceWsUrl = settings.websocket.getWsUrl('/ws/voice');
// Результат: ws://localhost:8000/ws/voice
```

## Классы подключений

### APIConnectionConfigImpl

- `baseUrl`: Базовый URL для API
- `timeout`: Таймаут запросов в миллисекундах
- `retryEnabled`: Включены ли retry попытки
- `retryAttempts`: Количество попыток retry
- `retryDelay`: Задержка между попытками в миллисекундах
- `getApiUrl(endpoint)`: Метод для получения полного URL

### WebSocketConnectionConfigImpl

- `baseUrl`: Базовый URL для WebSocket
- `timeout`: Таймаут подключения в миллисекундах
- `pingInterval`: Интервал ping в миллисекундах
- `pingTimeout`: Таймаут ping в миллисекундах
- `reconnectionAttempts`: Максимальное количество попыток переподключения
- `reconnectionDelay`: Задержка между попытками переподключения
- `reconnectionDelayMax`: Максимальная задержка переподключения
- `getWsUrl(endpoint)`: Метод для получения полного URL

## Миграция существующего кода

### До миграции

```typescript
// config/api.ts
export const API_CONFIG = {
  get BASE_URL(): string {
    return process.env.REACT_APP_API_URL || getUrl('backend_port_1');
  },
  get WS_URL(): string {
    const baseUrl = process.env.REACT_APP_WS_URL || getUrl('backend_port_1');
    return baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  },
};

export const getApiUrl = (endpoint: string): string => {
  return `${API_CONFIG.BASE_URL}${endpoint}`;
};

export const getWsUrl = (endpoint: string): string => {
  return `${API_CONFIG.WS_URL}${endpoint}`;
};
```

### После миграции

```typescript
import { getSettings } from './settings';

const settings = getSettings();

// Вместо API_CONFIG.BASE_URL
const baseUrl = settings.api.baseUrl;

// Вместо getApiUrl(endpoint)
const apiUrl = settings.api.getApiUrl('/api/chat');

// Вместо getWsUrl(endpoint)
const wsUrl = settings.websocket.getWsUrl('/ws/voice');
```

## Примеры использования

### Инициализация в App.tsx

```typescript
import React, { useEffect, useState } from 'react';
import { initSettings, getSettings } from './settings';

function App() {
  const [configLoaded, setConfigLoaded] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        await initSettings();
        setConfigLoaded(true);
      } catch (error) {
        console.error('Ошибка загрузки конфигурации:', error);
      }
    };

    loadConfig();
  }, []);

  if (!configLoaded) {
    return <div>Загрузка конфигурации...</div>;
  }

  // Остальной код приложения
  return <div>...</div>;
}
```

### Использование в компонентах

```typescript
import { getSettings } from '../settings';

function ChatComponent() {
  const settings = getSettings();

  const sendMessage = async (message: string) => {
    const url = settings.api.getApiUrl('/api/chat');
    const response = await fetch(url, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
    // ...
  };

  return <div>...</div>;
}
```

### Использование WebSocket

```typescript
import { getSettings } from '../settings';

function VoiceComponent() {
  const settings = getSettings();

  useEffect(() => {
    const wsUrl = settings.websocket.getWsUrl('/ws/voice');
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket подключен');
    };

    return () => {
      ws.close();
    };
  }, []);

  return <div>...</div>;
}
```

## Приоритет источников конфигурации

1. **Переменные окружения** (process.env.REACT_APP_*) - высший приоритет
2. **YAML файл** (public/config/config.yml) - средний приоритет
3. **Значения по умолчанию** - низший приоритет

## Перезагрузка конфигурации

```typescript
import { resetSettings } from './settings';

// Принудительная перезагрузка (например, после изменения config.yml)
await resetSettings();
```
















