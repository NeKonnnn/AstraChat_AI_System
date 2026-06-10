/**
 * Абсолютный таймаут сессии с момента входа (без учёта активности).
 * Источник: AUTH_SESSION_TIMEOUT_SECONDS на backend (login + GET /api/auth/session-policy).
 */

export interface SessionTimeoutConfig {
  enabled: boolean;
  timeoutSeconds: number;
}

export interface SessionPolicyResponse {
  enabled: boolean;
  timeout_seconds: number;
}

export const AUTH_SESSION_STARTED_KEY = 'auth_session_started_ms';
export const AUTH_SESSION_POLICY_KEY = 'auth_session_policy';

export function mapApiSessionPolicyToConfig(data: SessionPolicyResponse): SessionTimeoutConfig {
  const timeoutSeconds = Math.max(0, Number(data.timeout_seconds) || 0);
  return {
    enabled: Boolean(data.enabled) && timeoutSeconds > 0,
    timeoutSeconds,
  };
}

export function cacheSessionPolicy(policy: SessionTimeoutConfig): void {
  sessionStorage.setItem(AUTH_SESSION_POLICY_KEY, JSON.stringify(policy));
}

export function getCachedSessionPolicy(): SessionTimeoutConfig | null {
  const raw = sessionStorage.getItem(AUTH_SESSION_POLICY_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as SessionTimeoutConfig;
    if (
      typeof parsed.enabled === 'boolean' &&
      typeof parsed.timeoutSeconds === 'number' &&
      Number.isFinite(parsed.timeoutSeconds)
    ) {
      return parsed;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function clearSessionPolicy(): void {
  sessionStorage.removeItem(AUTH_SESSION_POLICY_KEY);
}

/** Фиксирует момент входа (вызывать только при успешном login). */
export function markSessionStarted(): void {
  sessionStorage.setItem(AUTH_SESSION_STARTED_KEY, String(Date.now()));
}

export function clearSessionStarted(): void {
  sessionStorage.removeItem(AUTH_SESSION_STARTED_KEY);
}

export function clearSessionTimeoutState(): void {
  clearSessionStarted();
  clearSessionPolicy();
}

export function getJwtIssuedAtMs(jwtToken: string): number | null {
  try {
    const payloadPart = jwtToken.split('.')[1];
    if (!payloadPart) return null;
    const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded));
    if (typeof payload.iat !== 'number') return null;
    return payload.iat * 1000;
  } catch {
    return null;
  }
}

/** Время начала сессии (не сбрасывается при refresh токена). */
export function getSessionStartedMs(accessToken?: string | null): number {
  const raw = sessionStorage.getItem(AUTH_SESSION_STARTED_KEY);
  const parsed = raw ? Number(raw) : NaN;
  if (Number.isFinite(parsed)) {
    return parsed;
  }
  const iatMs = accessToken ? getJwtIssuedAtMs(accessToken) : null;
  if (iatMs !== null) {
    sessionStorage.setItem(AUTH_SESSION_STARTED_KEY, String(iatMs));
    return iatMs;
  }
  return Date.now();
}

export function isSessionExpired(timeoutSeconds: number, accessToken?: string | null): boolean {
  if (timeoutSeconds <= 0) return false;
  const started = getSessionStartedMs(accessToken);
  return Date.now() - started >= timeoutSeconds * 1000;
}

export function getSessionRemainingMs(timeoutSeconds: number, accessToken?: string | null): number {
  if (timeoutSeconds <= 0) return Infinity;
  const started = getSessionStartedMs(accessToken);
  return Math.max(0, timeoutSeconds * 1000 - (Date.now() - started));
}
