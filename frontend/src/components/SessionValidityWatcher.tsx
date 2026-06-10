import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { useSocket } from '../contexts/SocketContext';
import { getApiUrl } from '../config/api';
import { initSettings } from '../settings';
import { clearSessionTimeoutState } from '../settings/sessionTimeout';
import {
  cacheServerInstanceId,
  getCachedServerInstanceId,
  isServerInstanceMismatch,
  resolveLoginSessionNoticeReason,
  setLoginSessionNotice,
  type LoginSessionNoticeReason,
} from '../settings/sessionValidity';

const POLL_INTERVAL_MS = 30_000;

const authApiUrl = (path: string): string => {
  if (process.env.REACT_APP_API_URL) {
    const base = process.env.REACT_APP_API_URL.replace(/\/$/, '');
    const p = path.startsWith('/') ? path : `/${path}`;
    return `${base}${p}`;
  }
  return getApiUrl(path);
};

/**
 * Периодически проверяет, что backend не перезапускался и сессия ещё активна.
 * При рестарте backend instance_id меняется — пользователь перенаправляется на login.
 */
export default function SessionValidityWatcher() {
  const { isAuthenticated, isLoading, logout, token } = useAuth();
  const { isConnected } = useSocket();
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const checkingRef = useRef(false);
  const tokenRef = useRef<string | null>(null);
  const wasConnectedRef = useRef(false);

  tokenRef.current = token;

  const clearPoll = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const invalidateSession = useCallback(async (reason: LoginSessionNoticeReason) => {
    clearPoll();
    clearSessionTimeoutState();
    setLoginSessionNotice(reason);
    await logout();
    navigate('/login', { replace: true });
  }, [clearPoll, logout, navigate]);

  const checkSessionValidity = useCallback(async () => {
    if (checkingRef.current || !tokenRef.current) return;

    checkingRef.current = true;
    try {
      await initSettings();

      const { data: instanceData } = await axios.get<{ instance_id?: string }>(
        authApiUrl('/api/auth/server-instance'),
      );
      const currentInstanceId = String(instanceData?.instance_id || '').trim();
      if (currentInstanceId) {
        const cachedInstanceId = getCachedServerInstanceId();
        if (!cachedInstanceId) {
          cacheServerInstanceId(currentInstanceId);
        } else if (isServerInstanceMismatch(currentInstanceId)) {
          await invalidateSession('server_restart');
          return;
        }
      }

      try {
        await axios.get(authApiUrl('/api/auth/verify'), {
          headers: {
            Authorization: `Bearer ${tokenRef.current}`,
          },
        });
      } catch (error: any) {
        if (error?.response?.status === 401) {
          const reason = resolveLoginSessionNoticeReason(error?.response?.data?.detail);
          await invalidateSession(reason);
        }
      }
    } catch (error) {
      console.warn('Не удалось проверить валидность сессии (сетевая ошибка):', error);
    } finally {
      checkingRef.current = false;
    }
  }, [invalidateSession]);

  useEffect(() => {
    if (isLoading || !isAuthenticated) {
      clearPoll();
      return;
    }

    void checkSessionValidity();

    intervalRef.current = setInterval(() => {
      void checkSessionValidity();
    }, POLL_INTERVAL_MS);

    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      void checkSessionValidity();
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      clearPoll();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [isAuthenticated, isLoading, checkSessionValidity, clearPoll]);

  useEffect(() => {
    if (isLoading || !isAuthenticated) {
      wasConnectedRef.current = false;
      return;
    }
    if (isConnected && !wasConnectedRef.current) {
      void checkSessionValidity();
    }
    wasConnectedRef.current = isConnected;
  }, [isAuthenticated, isLoading, isConnected, checkSessionValidity]);

  return null;
}
