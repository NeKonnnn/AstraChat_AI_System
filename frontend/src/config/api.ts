// Конфигурация API для astrachat Frontend
// Использует новый модуль settings
import { getSettings } from '../settings';

// API эндпоинты
export const API_ENDPOINTS = {
  // Чат
  CHAT: '/api/chat',
  
  // Голос
  VOICE_RECOGNIZE: '/api/voice/recognize',
  VOICE_SYNTHESIZE: '/api/voice/synthesize',
  VOICE_SETTINGS: '/api/voice/settings',
  VOICE_WS: '/ws/voice',
  
  // Транскрибация
  TRANSCRIBE_UPLOAD: '/api/transcribe/upload',
  TRANSCRIBE_YOUTUBE: '/api/transcribe/youtube',
  TRANSCRIPTION_SETTINGS: '/api/transcription/settings',
  
  // Документы
  DOCUMENTS_UPLOAD: '/api/documents/upload',
  DOCUMENTS_QUERY: '/api/documents/query',
  DOCUMENTS_LIST: '/api/documents',
  DOCUMENTS_DELETE: '/api/documents',
  
  // Модели
  MODELS: '/api/models',
  MODELS_CURRENT: '/api/models/current',
  MODELS_SETTINGS: '/api/models/settings',
  MODELS_LOAD: '/api/models/load',
  
  // История
  HISTORY: '/api/history',
  
  // Сообщения
  UPDATE_MESSAGE: '/api/messages',
};

// Для обратной совместимости (deprecated - используйте getSettings())
export const API_CONFIG = {
  get BASE_URL(): string {
    const settings = getSettings();
    return settings.api.baseUrl;
  },
  
  get WS_URL(): string {
    const settings = getSettings();
    return settings.websocket.baseUrl;
  },
  
  ENDPOINTS: API_ENDPOINTS,
};

// Функция для получения полного URL API
export const getApiUrl = (endpoint: string): string => {
  const settings = getSettings();
  return settings.api.getApiUrl(endpoint);
};

// Функция для получения WebSocket URL
export const getWsUrl = (endpoint: string): string => {
  const settings = getSettings();
  return settings.websocket.getWsUrl(endpoint);
};
