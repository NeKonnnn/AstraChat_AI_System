/**
 * Основной модуль конфигурации для astrachat Frontend
 * Загружает настройки из YAML и переменных окружения
 */

import yaml from 'js-yaml';
import { APIConnectionConfigImpl, WebSocketConnectionConfigImpl } from './connections';

export interface UrlsConfig {
  // Frontend адреса
  frontend_port_1: string;
  frontend_port_1_ipv4: string;
  frontend_port_2: string;
  frontend_port_2_ipv4: string;
  frontend_port_3: string;
  frontend_port_3_ipv4: string;
  
  // Backend адреса
  backend_port_1: string;
  backend_port_1_ipv4: string;
  backend_port_2: string;
  backend_port_2_ipv4: string;
  
  // LLM Service адреса
  llm_service_port: string;
  
  // Docker внутренние адреса
  frontend_docker: string;
  backend_docker: string;
  llm_service_docker: string;
}

export interface AppConfig {
  name: string;
  version: string;
  description: string;
  debug: boolean;
}

export interface SettingsConfig {
  app: AppConfig;
  urls: UrlsConfig;
  api: APIConnectionConfigImpl;
  websocket: WebSocketConnectionConfigImpl;
}

// Глобальный экземпляр настроек
let _settings: SettingsConfig | null = null;
let _loadPromise: Promise<SettingsConfig> | null = null;

/**
 * Загрузка конфигурации из YAML файла
 */
const loadConfig = async (): Promise<SettingsConfig> => {
  if (_settings) return _settings;
  if (_loadPromise) return _loadPromise;

  _loadPromise = (async () => {
    try {
      // Загружаем config.yml из public/config
      const response = await fetch('/config/config.yml');
      if (!response.ok) {
        throw new Error(
          `Не удалось загрузить config.yml: ${response.statusText}. ` +
          `Проверьте наличие файла public/config/config.yml`
        );
      }
      
      const yamlText = await response.text();
      const configData: any = yaml.load(yamlText) || {};
      
      if (!configData.urls) {
        throw new Error('В config.yml отсутствует секция urls. Проверьте формат файла.');
      }

      // Создаем конфигурацию приложения
      const appConfig: AppConfig = {
        name: configData.app?.name || 'astrachat Frontend',
        version: configData.app?.version || '1.0.0',
        description: configData.app?.description || 'Frontend for astrachat',
        debug: configData.app?.debug ?? false,
      };

      // Создаем конфигурацию URL (приоритет: YAML > ENV, без дефолтов)
      const getUrlValue = (yamlKey: string, envKey: string): string => {
        // Сначала пробуем из YAML
        if (configData.urls && configData.urls[yamlKey]) {
          return configData.urls[yamlKey];
        }
        // Затем из ENV
        const envValue = process.env[envKey];
        if (envValue) {
          return envValue;
        }
        // Если нет ни в YAML, ни в ENV - ошибка
        throw new Error(
          `${yamlKey} не задан в YAML (urls.${yamlKey}) или ENV (${envKey}). ` +
          `Проверьте файл public/config/config.yml или переменные окружения.`
        );
      };

      const urlsConfig: UrlsConfig = {
        frontend_port_1: getUrlValue('frontend_port_1', 'REACT_APP_FRONTEND_PORT_1'),
        frontend_port_1_ipv4: getUrlValue('frontend_port_1_ipv4', 'REACT_APP_FRONTEND_PORT_1_IPV4'),
        frontend_port_2: getUrlValue('frontend_port_2', 'REACT_APP_FRONTEND_PORT_2'),
        frontend_port_2_ipv4: getUrlValue('frontend_port_2_ipv4', 'REACT_APP_FRONTEND_PORT_2_IPV4'),
        frontend_port_3: getUrlValue('frontend_port_3', 'REACT_APP_FRONTEND_PORT_3'),
        frontend_port_3_ipv4: getUrlValue('frontend_port_3_ipv4', 'REACT_APP_FRONTEND_PORT_3_IPV4'),
        backend_port_1: getUrlValue('backend_port_1', 'REACT_APP_BACKEND_PORT_1'),
        backend_port_1_ipv4: getUrlValue('backend_port_1_ipv4', 'REACT_APP_BACKEND_PORT_1_IPV4'),
        backend_port_2: getUrlValue('backend_port_2', 'REACT_APP_BACKEND_PORT_2'),
        backend_port_2_ipv4: getUrlValue('backend_port_2_ipv4', 'REACT_APP_BACKEND_PORT_2_IPV4'),
        llm_service_port: getUrlValue('llm_service_port', 'REACT_APP_LLM_SERVICE_PORT'),
        frontend_docker: getUrlValue('frontend_docker', 'REACT_APP_FRONTEND_DOCKER'),
        backend_docker: getUrlValue('backend_docker', 'REACT_APP_BACKEND_DOCKER'),
        llm_service_docker: getUrlValue('llm_service_docker', 'REACT_APP_LLM_SERVICE_DOCKER'),
      };

      // Определяем базовый URL для API (приоритет: env > config.yml)
      // Если REACT_APP_API_URL задан в ENV, используем его, иначе берем из config.yml
      const apiBaseUrl = process.env.REACT_APP_API_URL || urlsConfig.backend_port_1;
      // Для WebSocket: если REACT_APP_WS_URL задан в ENV, используем его, иначе берем из config.yml и преобразуем
      const wsBaseUrlRaw = process.env.REACT_APP_WS_URL || urlsConfig.backend_port_1;
      // Преобразуем http/https в ws/wss, если нужно
      const wsBaseUrl = wsBaseUrlRaw.startsWith('ws://') || wsBaseUrlRaw.startsWith('wss://') 
        ? wsBaseUrlRaw 
        : wsBaseUrlRaw.replace('http://', 'ws://').replace('https://', 'wss://');

      // Создаем конфигурацию подключений (приоритет: YAML > ENV, без дефолтов)
      const getConfigValue = <T>(yamlPath: string[], envKey: string, defaultValue: T | null = null): T => {
        // Сначала пробуем из YAML
        let value: any = configData;
        for (const key of yamlPath) {
          value = value?.[key];
          if (value === undefined) break;
        }
        if (value !== undefined) {
          return value;
        }
        // Затем из ENV
        const envValue = process.env[envKey];
        if (envValue !== undefined) {
          // Преобразуем строку в нужный тип
          if (typeof defaultValue === 'number') {
            return parseInt(envValue, 10) as T;
          }
          if (typeof defaultValue === 'boolean') {
            return (envValue.toLowerCase() === 'true') as T;
          }
          return envValue as T;
        }
        // Если есть дефолт, используем его
        if (defaultValue !== null) {
          return defaultValue;
        }
        // Иначе ошибка
        throw new Error(
          `Значение не задано в YAML (${yamlPath.join('.')}) или ENV (${envKey}). ` +
          `Проверьте файл public/config/config.yml или переменные окружения.`
        );
      };

      const apiConfig = new APIConnectionConfigImpl({
        baseUrl: apiBaseUrl,
        timeout: getConfigValue(['api', 'timeout'], 'REACT_APP_API_TIMEOUT', 30000),
        retryEnabled: getConfigValue(['api', 'retryEnabled'], 'REACT_APP_API_RETRY_ENABLED', true),
        retryAttempts: getConfigValue(['api', 'retryAttempts'], 'REACT_APP_API_RETRY_ATTEMPTS', 3),
        retryDelay: getConfigValue(['api', 'retryDelay'], 'REACT_APP_API_RETRY_DELAY', 1000),
      });

      const websocketConfig = new WebSocketConnectionConfigImpl({
        baseUrl: wsBaseUrl,
        timeout: getConfigValue(['websocket', 'timeout'], 'REACT_APP_WS_TIMEOUT', 10000),
        pingInterval: getConfigValue(['websocket', 'pingInterval'], 'REACT_APP_WS_PING_INTERVAL', 30000),
        pingTimeout: getConfigValue(['websocket', 'pingTimeout'], 'REACT_APP_WS_PING_TIMEOUT', 10000),
        reconnectionAttempts: getConfigValue(['websocket', 'reconnectionAttempts'], 'REACT_APP_WS_RECONNECTION_ATTEMPTS', 10),
        reconnectionDelay: getConfigValue(['websocket', 'reconnectionDelay'], 'REACT_APP_WS_RECONNECTION_DELAY', 1000),
        reconnectionDelayMax: getConfigValue(['websocket', 'reconnectionDelayMax'], 'REACT_APP_WS_RECONNECTION_DELAY_MAX', 5000),
      });

      _settings = {
        app: appConfig,
        urls: urlsConfig,
        api: apiConfig,
        websocket: websocketConfig,
      };

      return _settings;
    } catch (error) {
      console.error('КРИТИЧЕСКАЯ ОШИБКА загрузки конфигурации:', error);
      throw error;
    } finally {
      _loadPromise = null;
    }
  })();

  return _loadPromise;
};

/**
 * Получение глобального экземпляра настроек (singleton)
 */
export const getSettings = (): SettingsConfig => {
  if (!_settings) {
    throw new Error(
      'Конфигурация не загружена! Убедитесь, что initSettings() вызван перед использованием getSettings().'
    );
  }
  return _settings;
};

/**
 * Инициализация настроек (загружает конфиг заранее при старте приложения)
 * ОБЯЗАТЕЛЬНО вызвать при старте приложения!
 */
export const initSettings = async (): Promise<SettingsConfig> => {
  return await loadConfig();
};

/**
 * Сброс и принудительная перезагрузка настроек
 */
export const resetSettings = async (): Promise<SettingsConfig> => {
  _settings = null;
  _loadPromise = null;
  return await loadConfig();
};

/**
 * Получение URL из конфигурации (синхронно, использует кэш)
 */
export const getUrl = (key: keyof UrlsConfig): string => {
  const settings = getSettings();
  const url = settings.urls[key];
  if (!url) {
    throw new Error(
      `Ключ '${key}' не найден в config.yml! Проверьте наличие этого ключа в секции urls файла public/config/config.yml`
    );
  }
  return url;
};

// Типы уже экспортированы выше через export interface

