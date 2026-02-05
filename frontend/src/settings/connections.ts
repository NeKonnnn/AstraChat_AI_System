/**
 * Классы конфигурации подключений для различных сервисов
 */

export interface APIConnectionConfig {
  /** Базовый URL для API */
  baseUrl: string;
  /** Таймаут запросов в миллисекундах */
  timeout: number;
  /** Включены ли retry попытки */
  retryEnabled: boolean;
  /** Количество попыток retry */
  retryAttempts: number;
  /** Задержка между попытками в миллисекундах */
  retryDelay: number;
}

export interface WebSocketConnectionConfig {
  /** Базовый URL для WebSocket */
  baseUrl: string;
  /** Таймаут подключения в миллисекундах */
  timeout: number;
  /** Интервал ping в миллисекундах */
  pingInterval: number;
  /** Таймаут ping в миллисекундах */
  pingTimeout: number;
  /** Максимальное количество попыток переподключения */
  reconnectionAttempts: number;
  /** Задержка между попытками переподключения в миллисекундах */
  reconnectionDelay: number;
  /** Максимальная задержка переподключения в миллисекундах */
  reconnectionDelayMax: number;
}

export class APIConnectionConfigImpl implements APIConnectionConfig {
  baseUrl: string;
  timeout: number;
  retryEnabled: boolean;
  retryAttempts: number;
  retryDelay: number;

  constructor(config: APIConnectionConfig) {
    // Все значения должны быть переданы из конфигурации (YAML или ENV)
    if (!config.baseUrl) {
      throw new Error('baseUrl не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.timeout === undefined || config.timeout === null) {
      throw new Error('timeout не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.retryAttempts === undefined || config.retryAttempts === null) {
      throw new Error('retryAttempts не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.retryDelay === undefined || config.retryDelay === null) {
      throw new Error('retryDelay не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    
    this.baseUrl = config.baseUrl;
    this.timeout = config.timeout;
    this.retryEnabled = config.retryEnabled ?? true;
    this.retryAttempts = config.retryAttempts;
    this.retryDelay = config.retryDelay;
  }

  /**
   * Получает полный URL для API endpoint
   */
  getApiUrl(endpoint: string): string {
    const base = this.baseUrl.endsWith('/') ? this.baseUrl.slice(0, -1) : this.baseUrl;
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${base}${path}`;
  }
}

export class WebSocketConnectionConfigImpl implements WebSocketConnectionConfig {
  baseUrl: string;
  timeout: number;
  pingInterval: number;
  pingTimeout: number;
  reconnectionAttempts: number;
  reconnectionDelay: number;
  reconnectionDelayMax: number;

  constructor(config: WebSocketConnectionConfig) {
    // Все значения должны быть переданы из конфигурации (YAML или ENV)
    if (!config.baseUrl) {
      throw new Error('baseUrl не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.timeout === undefined || config.timeout === null) {
      throw new Error('timeout не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.pingInterval === undefined || config.pingInterval === null) {
      throw new Error('pingInterval не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.pingTimeout === undefined || config.pingTimeout === null) {
      throw new Error('pingTimeout не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.reconnectionAttempts === undefined || config.reconnectionAttempts === null) {
      throw new Error('reconnectionAttempts не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.reconnectionDelay === undefined || config.reconnectionDelay === null) {
      throw new Error('reconnectionDelay не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    if (config.reconnectionDelayMax === undefined || config.reconnectionDelayMax === null) {
      throw new Error('reconnectionDelayMax не задан в конфигурации. Проверьте YAML или ENV переменные.');
    }
    
    // Преобразуем http/https в ws/wss
    let wsBaseUrl = config.baseUrl;
    if (!wsBaseUrl.startsWith('ws://') && !wsBaseUrl.startsWith('wss://')) {
      wsBaseUrl = wsBaseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    }
    
    this.baseUrl = wsBaseUrl;
    this.timeout = config.timeout;
    this.pingInterval = config.pingInterval;
    this.pingTimeout = config.pingTimeout;
    this.reconnectionAttempts = config.reconnectionAttempts;
    this.reconnectionDelay = config.reconnectionDelay;
    this.reconnectionDelayMax = config.reconnectionDelayMax;
  }

  /**
   * Получает полный URL для WebSocket endpoint
   */
  getWsUrl(endpoint: string): string {
    const base = this.baseUrl.endsWith('/') ? this.baseUrl.slice(0, -1) : this.baseUrl;
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${base}${path}`;
  }
}

