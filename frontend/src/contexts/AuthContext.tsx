import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';
import { initSettings, parseLoginErrorDetail } from '../settings';
import {
  markSessionStarted,
  clearSessionTimeoutState,
  cacheSessionPolicy,
  mapApiSessionPolicyToConfig,
  type SessionPolicyResponse,
} from '../settings/sessionTimeout';
import { cacheServerInstanceId, clearServerInstanceId, resolveLoginSessionNoticeReason, setLoginSessionNotice } from '../settings/sessionValidity';
import { getApiUrl, fetchSessionPolicy } from '../config/api';

export type LoginErrorMeta = {
  remainingAttempts?: number;
  maxFailedAttempts?: number;
  lockoutDurationSeconds?: number;
  retryAfterSeconds?: number;
};

export class AuthLoginError extends Error {
  readonly meta: LoginErrorMeta;

  constructor(message: string, meta: LoginErrorMeta = {}) {
    super(message);
    this.name = 'AuthLoginError';
    this.meta = meta;
  }
}

interface User {
  username: string;
  user_id?: string;  // ID пользователя (может быть равен username)
  email: string | null;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  updateUser: (userData: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);
const REFRESH_TOKEN_STORAGE_KEY = 'auth_refresh_token';
const TOKEN_REFRESH_SKEW_MS = 2 * 60 * 1000;
const TOKEN_REFRESH_FALLBACK_MS = 25 * 60 * 1000;

/** URL API для auth: после initSettings() — из public/config/config.yml (или REACT_APP_API_URL при сборке). */
const authApiUrl = (path: string): string => {
  if (process.env.REACT_APP_API_URL) {
    const base = process.env.REACT_APP_API_URL.replace(/\/$/, '');
    const p = path.startsWith('/') ? path : `/${path}`;
    return `${base}${p}`;
  }
  return getApiUrl(path);
};

const getJwtExpiryMs = (jwtToken: string): number | null => {
  try {
    const payloadPart = jwtToken.split('.')[1];
    if (!payloadPart) return null;
    const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const payloadJson = atob(padded);
    const payload = JSON.parse(payloadJson);
    if (typeof payload.exp !== 'number') return null;
    return payload.exp * 1000;
  } catch {
    return null;
  }
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshInFlightRef = React.useRef<Promise<string | null> | null>(null);

  // Инициализация: проверяем наличие токена в localStorage
  useEffect(() => {
    const initializeAuth = async () => {
      // Сначала убеждаемся, что настройки загружены
      try {
        await initSettings();
      } catch (error) {
        console.warn('Не удалось загрузить настройки, используем дефолтные значения:', error);
      }
      
      const savedToken = localStorage.getItem('auth_token');
      const savedRefreshToken = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
      const savedUser = localStorage.getItem('auth_user');
      
      if (savedToken && savedUser) {
        try {
          setToken(savedToken);
          setUser(JSON.parse(savedUser));
          
          // Проверяем валидность токена асинхронно (не блокируем загрузку).
          // Если access-токен устарел, пробуем обновить по refresh-токену.
          verifyToken(savedToken).catch(async (error: any) => {
            if (error.response?.status !== 401) {
              console.warn('Не удалось проверить токен, но продолжаем работу:', error.message);
              return;
            }
            if (!savedRefreshToken) {
              console.warn('Access-токен невалиден и отсутствует refresh-токен, очищаем авторизацию');
              setLoginSessionNotice(resolveLoginSessionNoticeReason(error?.response?.data?.detail));
              localStorage.removeItem('auth_token');
              localStorage.removeItem('auth_user');
              clearSessionTimeoutState();
              clearServerInstanceId();
              setToken(null);
              setUser(null);
              return;
            }
            try {
              const refreshedToken = await refreshAccessToken(savedRefreshToken);
              if (!refreshedToken) {
                throw new Error('refresh token rejected');
              }
            } catch (refreshError: any) {
              console.warn('Не удалось обновить токен, очищаем авторизацию:', refreshError);
              setLoginSessionNotice(
                resolveLoginSessionNoticeReason(refreshError?.response?.data?.detail),
              );
              localStorage.removeItem('auth_token');
              localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
              localStorage.removeItem('auth_user');
              clearSessionTimeoutState();
              clearServerInstanceId();
              setToken(null);
              setUser(null);
            }
          });
        } catch (error) {
          console.error('Ошибка при инициализации авторизации:', error);
          // Очищаем поврежденные данные
          localStorage.removeItem('auth_token');
          localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
          localStorage.removeItem('auth_user');
          clearSessionTimeoutState();
          clearServerInstanceId();
          setToken(null);
          setUser(null);
        }
      }
      
      setIsLoading(false);
    };
    
    initializeAuth();
  }, []);

  useEffect(() => {
    if (!token) return;

    const refreshToken = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
    if (!refreshToken) return;

    const expiresAtMs = getJwtExpiryMs(token);
    const nowMs = Date.now();
    const targetTimeMs = expiresAtMs
      ? Math.max(0, expiresAtMs - TOKEN_REFRESH_SKEW_MS - nowMs)
      : TOKEN_REFRESH_FALLBACK_MS;

    const timerId = window.setTimeout(async () => {
      if (!refreshInFlightRef.current) {
        refreshInFlightRef.current = refreshAccessToken(refreshToken)
          .finally(() => {
            refreshInFlightRef.current = null;
          });
      }
      const newAccessToken = await refreshInFlightRef.current;
      if (!newAccessToken) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
        localStorage.removeItem('auth_user');
        clearSessionTimeoutState();
        clearServerInstanceId();
        setToken(null);
        setUser(null);
      }
    }, targetTimeMs);

    return () => {
      window.clearTimeout(timerId);
    };
  }, [token]);

  // Проверка валидности токена
  const verifyToken = async (token: string) => {
    try {
      const response = await axios.get(authApiUrl('/api/auth/verify'), {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (typeof response.data?.server_instance_id === 'string') {
        cacheServerInstanceId(response.data.server_instance_id);
      }
      return response.data.valid;
    } catch (error: any) {
      // Если это ошибка авторизации (401), токен точно невалиден
      if (error.response?.status === 401) {
        throw error;
      }
      // Для других ошибок (сеть, сервер недоступен и т.д.) не считаем токен невалидным
      // Просто логируем и продолжаем работу
      console.warn('Не удалось проверить токен (возможна сетевая ошибка):', error.message);
      return true; // Предполагаем, что токен валиден, если это не ошибка авторизации
    }
  };

  const refreshAccessToken = async (refreshToken: string): Promise<string | null> => {
    try {
      const response = await axios.post(authApiUrl('/api/auth/refresh'), {
        refresh_token: refreshToken,
      });
      const { access_token, refresh_token, user: userData } = response.data;
      if (!access_token || !refresh_token) {
        return null;
      }
      setToken(access_token);
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refresh_token);
      if (userData) {
        setUser(userData);
        localStorage.setItem('auth_user', JSON.stringify(userData));
      }
      if (typeof response.data.server_instance_id === 'string') {
        cacheServerInstanceId(response.data.server_instance_id);
      }
      return access_token;
    } catch (error: any) {
      if (error?.response?.status === 401) {
        setLoginSessionNotice(resolveLoginSessionNoticeReason(error?.response?.data?.detail));
      }
      return null;
    }
  };

  // Настройка axios для автоматического добавления токена
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(
      (response: any) => response,
      async (error: any) => {
        const originalRequest = error?.config as any;
        const statusCode = error?.response?.status;
        const isAuthEndpoint = typeof originalRequest?.url === 'string' && originalRequest.url.includes('/api/auth/');
        if (statusCode !== 401 || !originalRequest || originalRequest._retry || isAuthEndpoint) {
          return Promise.reject(error);
        }

        const refreshToken = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
        if (!refreshToken) {
          return Promise.reject(error);
        }

        originalRequest._retry = true;
        if (!refreshInFlightRef.current) {
          refreshInFlightRef.current = refreshAccessToken(refreshToken)
            .finally(() => {
              refreshInFlightRef.current = null;
            });
        }

        const newAccessToken = await refreshInFlightRef.current;
        if (!newAccessToken) {
          localStorage.removeItem('auth_token');
          localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
          localStorage.removeItem('auth_user');
          clearSessionTimeoutState();
          clearServerInstanceId();
          setToken(null);
          setUser(null);
          return Promise.reject(error);
        }

        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return axios(originalRequest);
      },
    );

    return () => {
      axios.interceptors.response.eject(interceptorId);
    };
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const response = await axios.post(authApiUrl('/api/auth/login'), {
        username,
        password,
      });

      const { access_token, refresh_token, user: userData, session_policy } = response.data;
      if (!refresh_token) {
        throw new Error('Сервер не вернул refresh-токен');
      }

      markSessionStarted();
      if (typeof response.data.server_instance_id === 'string') {
        cacheServerInstanceId(response.data.server_instance_id);
      }
      if (session_policy) {
        cacheSessionPolicy(
          mapApiSessionPolicyToConfig(session_policy as SessionPolicyResponse),
        );
      } else {
        try {
          await initSettings();
          cacheSessionPolicy(await fetchSessionPolicy());
        } catch (policyError) {
          console.warn('Не удалось загрузить session_policy после login:', policyError);
        }
      }

      setToken(access_token);
      setUser(userData);

      localStorage.setItem('auth_token', access_token);
      localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refresh_token);
      localStorage.setItem('auth_user', JSON.stringify(userData));
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      if (error.response?.status === 401) {
        const parsed = parseLoginErrorDetail(detail);
        throw new AuthLoginError(parsed.message, {
          remainingAttempts: parsed.remainingAttempts,
          maxFailedAttempts: parsed.maxFailedAttempts,
          lockoutDurationSeconds: parsed.lockoutDurationSeconds,
        });
      }
      if (error.response?.status === 429) {
        const parsed = parseLoginErrorDetail(detail);
        throw new AuthLoginError(
          parsed.message || 'Слишком много неудачных попыток входа. Попробуйте позже.',
          {
            remainingAttempts: 0,
            maxFailedAttempts: parsed.maxFailedAttempts,
            lockoutDurationSeconds: parsed.lockoutDurationSeconds,
            retryAfterSeconds: parsed.retryAfterSeconds,
          },
        );
      }
      if (error.response?.status === 503) {
        throw new AuthLoginError('Сервис аутентификации временно недоступен');
      }
      throw new AuthLoginError('Ошибка при входе в систему');
    }
  };

  const logout = async () => {
    try {
      if (token) {
        await axios.post(authApiUrl('/api/auth/logout'), {}, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
      }
    } catch (error) {
      console.error('Ошибка при выходе:', error);
    } finally {
      // Очищаем данные независимо от результата запроса
      setToken(null);
      setUser(null);
      localStorage.removeItem('auth_token');
      localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
      localStorage.removeItem('auth_user');
      clearSessionTimeoutState();
      clearServerInstanceId();
    }
  };

  const updateUser = (userData: Partial<User>) => {
    if (user) {
      const updatedUser = { ...user, ...userData };
      setUser(updatedUser);
      localStorage.setItem('auth_user', JSON.stringify(updatedUser));
    }
  };

  const value = {
    user,
    token,
    login,
    logout,
    isAuthenticated: !!token && !!user,
    isLoading,
    updateUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}