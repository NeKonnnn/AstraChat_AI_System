import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchSessionPolicy } from '../config/api';
import { initSettings } from '../settings';
import {
  clearSessionTimeoutState,
  getCachedSessionPolicy,
  cacheSessionPolicy,
  getSessionRemainingMs,
  isSessionExpired,
  type SessionTimeoutConfig,
} from '../settings/sessionTimeout';

const POLL_INTERVAL_MS = 1000;

/**
 * Завершает сессию через N секунд с момента входа (AUTH_SESSION_TIMEOUT_SECONDS).
 */
export default function SessionTimeoutWatcher() {
  const { isAuthenticated, isLoading, logout, token } = useAuth();
  const navigate = useNavigate();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const expiringRef = useRef(false);
  const policyRef = useRef<SessionTimeoutConfig | null>(null);
  const tokenRef = useRef<string | null>(null);

  tokenRef.current = token;

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const expireSession = useCallback(async () => {
    if (expiringRef.current) return;
    const policy = policyRef.current;
    if (!policy?.enabled) return;

    expiringRef.current = true;
    clearTimers();
    clearSessionTimeoutState();
    await logout();
    navigate('/login', { replace: true });
    expiringRef.current = false;
  }, [clearTimers, logout, navigate]);

  const scheduleExpiry = useCallback(
    (policy: SessionTimeoutConfig) => {
      clearTimers();
      policyRef.current = policy;
      if (!policy.enabled) return;

      const accessToken = tokenRef.current;
      if (isSessionExpired(policy.timeoutSeconds, accessToken)) {
        void expireSession();
        return;
      }

      const remainingMs = getSessionRemainingMs(policy.timeoutSeconds, accessToken);
      timerRef.current = setTimeout(() => {
        void expireSession();
      }, remainingMs);

      intervalRef.current = setInterval(() => {
        if (isSessionExpired(policy.timeoutSeconds, tokenRef.current)) {
          void expireSession();
        }
      }, POLL_INTERVAL_MS);
    },
    [clearTimers, expireSession],
  );

  useEffect(() => {
    if (isLoading || !isAuthenticated) {
      policyRef.current = null;
      clearTimers();
      return;
    }

    let active = true;

    (async () => {
      try {
        let policy = getCachedSessionPolicy();
        if (!policy) {
          await initSettings();
          policy = await fetchSessionPolicy();
          cacheSessionPolicy(policy);
        }
        if (!active) return;

        if (!policy.enabled) {
          policyRef.current = policy;
          return;
        }

        scheduleExpiry(policy);
      } catch (error) {
        console.error(
          'Не удалось применить политику сессии (login/session-policy). Автовыход отключён:',
          error,
        );
      }
    })();

    const onVisibility = () => {
      const policy = policyRef.current;
      if (!policy?.enabled || document.visibilityState !== 'visible') return;
      if (isSessionExpired(policy.timeoutSeconds, tokenRef.current)) {
        void expireSession();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      active = false;
      clearTimers();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [isAuthenticated, isLoading, clearTimers, scheduleExpiry, expireSession]);

  return null;
}
