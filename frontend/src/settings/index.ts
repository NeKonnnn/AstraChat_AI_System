/**
 * Модуль настроек для astrachat Frontend
 * Централизованное управление конфигурацией и подключениями
 */

export {
  getSettings,
  initSettings,
  initConfig,
  resetSettings,
  getUrl,
  type SettingsConfig,
  type AppConfig,
  type UrlsConfig,
} from './config';

export {
  formatDurationRu,
  formatLockoutPolicyHint,
  LOGIN_LOCKOUT_EXHAUSTED_MESSAGE,
  formatRemainingAttemptsHint,
  mapApiPolicyToConfig,
  parseLoginErrorDetail,
  type LoginLockoutConfig,
  type LoginLockoutPolicyResponse,
} from './loginLockout';

export {
  mapApiSessionPolicyToConfig,
  markSessionStarted,
  clearSessionStarted,
  clearSessionTimeoutState,
  cacheSessionPolicy,
  getCachedSessionPolicy,
  AUTH_SESSION_STARTED_KEY,
  AUTH_SESSION_POLICY_KEY,
  type SessionTimeoutConfig,
  type SessionPolicyResponse,
} from './sessionTimeout';

export {
  APIConnectionConfigImpl,
  WebSocketConnectionConfigImpl,
  type APIConnectionConfig,
  type WebSocketConnectionConfig,
} from './connections';























