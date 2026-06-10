/**
 * Отображение политики блокировки входа на UI.
 * Параметры (лимит попыток, длительность, флаг) — только с backend:
 * GET /api/auth/login-lockout-policy и ответ POST /api/auth/login.
 */

export interface LoginLockoutConfig {
  enabled: boolean;
  maxFailedAttempts: number;
  lockoutDurationSeconds: number;
}

/** «15 мин. 30 сек.» — для отображения на странице входа */
export function formatDurationRu(totalSeconds: number): string {
  const sec = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(sec / 60);
  const seconds = sec % 60;
  if (minutes > 0 && seconds > 0) {
    return `${minutes} мин. ${seconds} сек.`;
  }
  if (minutes > 0) {
    return `${minutes} мин.`;
  }
  return `${seconds} сек.`;
}

/** Сообщение при исчерпании попыток входа (блокировка аккаунта). */
export const LOGIN_LOCKOUT_EXHAUSTED_MESSAGE =
  'Произведено слишком много попыток входа в аккаунт с некорректным паролем. Попробуйте повторно залогиниться через 15 минут';

export function formatLockoutPolicyHint(cfg: LoginLockoutConfig): string {
  if (!cfg.enabled) return '';
  return (
    `При ${cfg.maxFailedAttempts} неверных попытках подряд вход будет заблокирован на ` +
    `${formatDurationRu(cfg.lockoutDurationSeconds)}.`
  );
}

export function formatRemainingAttemptsHint(
  remaining: number,
  max: number,
  lockoutSeconds: number,
): string {
  const duration = formatDurationRu(lockoutSeconds);
  if (remaining <= 0) {
    return `Следующая неудачная попытка заблокирует вход на ${duration}.`;
  }
  return `Осталось попыток до блокировки: ${remaining} из ${max}.`;
}

/** Ответ API login / login-lockout-policy */
export interface LoginLockoutPolicyResponse {
  enabled: boolean;
  max_failed_attempts: number;
  lockout_duration_seconds?: number;
  /** @deprecated легаси API — переводится в секунды */
  lockout_duration_minutes?: number;
  remaining_attempts?: number | null;
  message?: string;
  retry_after_seconds?: number;
}

function resolveLockoutSecondsFromApi(
  data: Pick<LoginLockoutPolicyResponse, 'lockout_duration_seconds' | 'lockout_duration_minutes'>,
  fallback = 900,
): number {
  if (data.lockout_duration_seconds !== undefined) {
    return data.lockout_duration_seconds;
  }
  if (data.lockout_duration_minutes !== undefined) {
    return data.lockout_duration_minutes * 60;
  }
  return fallback;
}

export function mapApiPolicyToConfig(data: LoginLockoutPolicyResponse): LoginLockoutConfig {
  return {
    enabled: Boolean(data.enabled),
    maxFailedAttempts: data.max_failed_attempts,
    lockoutDurationSeconds: resolveLockoutSecondsFromApi(data),
  };
}

export function parseLoginErrorDetail(detail: unknown): {
  message: string;
  remainingAttempts?: number;
  maxFailedAttempts?: number;
  lockoutDurationSeconds?: number;
  retryAfterSeconds?: number;
} {
  if (typeof detail === 'string') {
    return { message: detail };
  }
  if (detail && typeof detail === 'object') {
    const d = detail as LoginLockoutPolicyResponse & { message?: string };
    const lockoutDurationSeconds =
      d.lockout_duration_seconds !== undefined
        ? d.lockout_duration_seconds
        : d.lockout_duration_minutes !== undefined
          ? d.lockout_duration_minutes * 60
          : undefined;
    return {
      message: d.message || 'Ошибка при входе в системе',
      remainingAttempts:
        d.remaining_attempts !== undefined && d.remaining_attempts !== null
          ? d.remaining_attempts
          : undefined,
      maxFailedAttempts: d.max_failed_attempts,
      lockoutDurationSeconds,
      retryAfterSeconds: d.retry_after_seconds,
    };
  }
  return { message: 'Ошибка при входе в систему' };
}
