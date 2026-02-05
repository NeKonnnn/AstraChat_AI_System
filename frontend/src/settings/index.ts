/**
 * Модуль настроек для astrachat Frontend
 * Централизованное управление конфигурацией и подключениями
 */

export {
  getSettings,
  initSettings,
  resetSettings,
  getUrl,
  type SettingsConfig,
  type AppConfig,
  type UrlsConfig,
} from './config';

export {
  APIConnectionConfigImpl,
  WebSocketConnectionConfigImpl,
  type APIConnectionConfig,
  type WebSocketConnectionConfig,
} from './connections';




