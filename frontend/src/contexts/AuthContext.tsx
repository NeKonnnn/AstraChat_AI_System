import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';
import { getSettings, initSettings } from '../settings';

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

// Получаем базовый URL из конфига
const getApiBaseUrl = () => {
  // Сначала пробуем из env переменных (самый быстрый способ)
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  
  // Затем пробуем из настроек (может быть еще не загружены)
  try {
    const settings = getSettings();
    return settings.api.baseUrl;
  } catch (error) {
    // Если настройки еще не загружены, используем дефолтное значение
    // Это значение должно совпадать с тем, что в config.yml
    console.warn('Настройки еще не загружены, используем дефолтный URL:', error);
    return 'http://localhost:8000';
  }
};
// Используем getApiBaseUrl() напрямую в функциях

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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
      const savedUser = localStorage.getItem('auth_user');
      
      if (savedToken && savedUser) {
        try {
          setToken(savedToken);
          setUser(JSON.parse(savedUser));
          
          // Проверяем валидность токена асинхронно (не блокируем загрузку)
          // Проверка выполняется после установки токена, чтобы пользователь мог видеть контент
          verifyToken(savedToken).catch((error: any) => {
            // Удаляем токен только если сервер явно вернул 401 (неавторизован)
            // Для других ошибок (сеть, сервер недоступен) оставляем токен
            if (error.response?.status === 401) {
              console.warn('Токен невалиден (401), очищаем данные авторизации');
              localStorage.removeItem('auth_token');
              localStorage.removeItem('auth_user');
              setToken(null);
              setUser(null);
            } else {
              console.warn('Не удалось проверить токен, но продолжаем работу:', error.message);
            }
          });
        } catch (error) {
          console.error('Ошибка при инициализации авторизации:', error);
          // Очищаем поврежденные данные
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_user');
          setToken(null);
          setUser(null);
        }
      }
      
      setIsLoading(false);
    };
    
    initializeAuth();
  }, []);

  // Проверка валидности токена
  const verifyToken = async (token: string) => {
    try {
      const response = await axios.get(`${getApiBaseUrl()}/api/auth/verify`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
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

  // Настройка axios для автоматического добавления токена
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  const login = async (username: string, password: string) => {
    try {
      const response = await axios.post(`${getApiBaseUrl()}/api/auth/login`, {
        username,
        password,
      });

      const { access_token, user: userData } = response.data;
      
      setToken(access_token);
      setUser(userData);
      
      // Сохраняем в localStorage
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('auth_user', JSON.stringify(userData));
    } catch (error: any) {
      if (error.response?.status === 401) {
        throw new Error('Неверное имя пользователя или пароль');
      } else if (error.response?.status === 503) {
        throw new Error('Сервис аутентификации временно недоступен');
      } else {
        throw new Error('Ошибка при входе в систему');
      }
    }
  };

  const logout = async () => {
    try {
      if (token) {
        await axios.post(`${getApiBaseUrl()}/api/auth/logout`, {}, {
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
      localStorage.removeItem('auth_user');
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



