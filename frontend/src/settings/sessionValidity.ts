/**
 * Идентификатор процесса backend на момент login.
 * После рестарта backend выдаёт новый instance_id — frontend завершает сессию.
 */

export const AUTH_SERVER_INSTANCE_KEY = 'auth_server_instance_id';

export function cacheServerInstanceId(instanceId: string): void {
  const normalized = instanceId.trim();
  if (!normalized) return;
  sessionStorage.setItem(AUTH_SERVER_INSTANCE_KEY, normalized);
}

export function getCachedServerInstanceId(): string | null {
  const raw = sessionStorage.getItem(AUTH_SERVER_INSTANCE_KEY);
  if (!raw) return null;
  const normalized = raw.trim();
  return normalized || null;
}

export function clearServerInstanceId(): void {
  sessionStorage.removeItem(AUTH_SERVER_INSTANCE_KEY);
}

export function isServerInstanceMismatch(currentInstanceId: string): boolean {
  const cached = getCachedServerInstanceId();
  if (!cached) return false;
  return cached !== currentInstanceId.trim();
}

export const LOGIN_SESSION_NOTICE_KEY = 'login_session_notice';

export type LoginSessionNoticeReason = 'server_restart' | 'session_expired' | 'ldap_blocked';

export const LOGIN_SESSION_NOTICE_MESSAGES: Record<LoginSessionNoticeReason, string> = {
  server_restart: 'Сессия завершена: сервер перезапущен. Войдите снова.',
  session_expired: 'Сессия завершена. Войдите снова.',
  ldap_blocked: 'Доступ запрещён: учётная запись заблокирована или недоступна в LDAP.',
};

export function setLoginSessionNotice(reason: LoginSessionNoticeReason): void {
  sessionStorage.setItem(LOGIN_SESSION_NOTICE_KEY, reason);
}

export function consumeLoginSessionNotice(): string | null {
  const raw = sessionStorage.getItem(LOGIN_SESSION_NOTICE_KEY);
  sessionStorage.removeItem(LOGIN_SESSION_NOTICE_KEY);
  if (raw === 'server_restart' || raw === 'session_expired' || raw === 'ldap_blocked') {
    return LOGIN_SESSION_NOTICE_MESSAGES[raw];
  }
  return null;
}

export function isServerRestartAuthDetail(detail: unknown): boolean {
  return typeof detail === 'string' && detail.toLowerCase().includes('перезапущен');
}

export function isLdapBlockedAuthDetail(detail: unknown): boolean {
  if (typeof detail !== 'string') return false;
  const lower = detail.toLowerCase();
  return (
    lower.includes('ldap')
    || lower.includes('заблокирован')
    || lower.includes('отключен')
    || lower.includes('не найден')
  );
}

export function resolveLoginSessionNoticeReason(detail: unknown): LoginSessionNoticeReason {
  if (isServerRestartAuthDetail(detail)) return 'server_restart';
  if (isLdapBlockedAuthDetail(detail)) return 'ldap_blocked';
  return 'session_expired';
}
