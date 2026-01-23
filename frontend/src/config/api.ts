// Конфигурация API для astrachat Frontend
import { getUrl } from './config';

// Конфигурация API для astrachat Frontend  
export const API_CONFIG = {
  // Базовый URL для API
  get BASE_URL(): string {
    return process.env.REACT_APP_API_URL || getUrl('backend_port_1');
  },
  
  // WebSocket URL
  get WS_URL(): string {
    const baseUrl = process.env.REACT_APP_WS_URL || getUrl('backend_port_1');
    return baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  },
  
  // API эндпоинты
  ENDPOINTS: {
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
  }
};

// Функция для получения полного URL API
export const getApiUrl = (endpoint: string): string => {
  return `${API_CONFIG.BASE_URL}${endpoint}`;
};

// Функция для получения WebSocket URL
export const getWsUrl = (endpoint: string): string => {
  return `${API_CONFIG.WS_URL}${endpoint}`;
};
