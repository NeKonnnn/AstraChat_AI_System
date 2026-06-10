/**
 * Счётчик и мигание на вкладке браузера при завершении генерации / транскрибации.
 */

export const TAB_NOTIFICATIONS_ENABLED_KEY = 'tab_notifications_enabled';

const DEFAULT_TITLE = 'AstraChat';
const BLINK_INTERVAL_MS = 1000;

let unreadCount = 0;
let blinkTimer: ReturnType<typeof setInterval> | null = null;
let blinkVisible = true;
let baseTitle = DEFAULT_TITLE;
let faviconLink: HTMLLinkElement | null = null;
let storedFaviconHref: string | null = null;
let badgeObjectUrl: string | null = null;

const getFaviconLink = (): HTMLLinkElement | null => {
  if (faviconLink) return faviconLink;
  faviconLink =
    document.querySelector<HTMLLinkElement>('link[rel="icon"]') ||
    document.querySelector<HTMLLinkElement>('link[rel="shortcut icon"]');
  return faviconLink;
};

const revokeBadgeUrl = () => {
  if (badgeObjectUrl) {
    URL.revokeObjectURL(badgeObjectUrl);
    badgeObjectUrl = null;
  }
};

const restoreFavicon = () => {
  const link = getFaviconLink();
  if (!link || !storedFaviconHref) return;
  link.href = storedFaviconHref;
  revokeBadgeUrl();
};

const drawFaviconWithBadge = async (count: number, dimmed: boolean): Promise<void> => {
  const link = getFaviconLink();
  if (!link) return;

  if (!storedFaviconHref) {
    storedFaviconHref = link.href;
  }

  const size = 32;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const img = new Image();
  img.crossOrigin = 'anonymous';

  await new Promise<void>((resolve) => {
    img.onload = () => resolve();
    img.onerror = () => resolve();
    img.src = storedFaviconHref || '/astra.ico';
  });

  ctx.globalAlpha = dimmed ? 0.35 : 1;
  try {
    ctx.drawImage(img, 0, 0, size, size);
  } catch {
    ctx.fillStyle = '#2196f3';
    ctx.fillRect(0, 0, size, size);
  }
  ctx.globalAlpha = 1;

  const label = count > 99 ? '99+' : String(count);
  const badgeRadius = 10;
  const badgeX = size - badgeRadius;
  const badgeY = badgeRadius;

  ctx.beginPath();
  ctx.arc(badgeX, badgeY, badgeRadius, 0, Math.PI * 2);
  ctx.fillStyle = '#e53935';
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.fillStyle = '#ffffff';
  ctx.font = label.length > 2 ? 'bold 7px sans-serif' : 'bold 11px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, badgeX, badgeY + 0.5);

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((b) => resolve(b), 'image/png');
  });
  if (!blob) return;

  revokeBadgeUrl();
  badgeObjectUrl = URL.createObjectURL(blob);
  link.href = badgeObjectUrl;
};

const applyTabIndicator = () => {
  const prefix = unreadCount > 0 ? `(${unreadCount}) ` : '';
  document.title = blinkVisible && unreadCount > 0 ? `${prefix}${baseTitle}` : baseTitle;
  if (unreadCount > 0) {
    void drawFaviconWithBadge(unreadCount, !blinkVisible);
  } else {
    restoreFavicon();
  }
};

const stopBlink = () => {
  if (blinkTimer) {
    clearInterval(blinkTimer);
    blinkTimer = null;
  }
  blinkVisible = true;
};

const startBlink = () => {
  if (blinkTimer || unreadCount <= 0) return;
  blinkTimer = setInterval(() => {
    blinkVisible = !blinkVisible;
    applyTabIndicator();
  }, BLINK_INTERVAL_MS);
};

export function areTabNotificationsEnabled(): boolean {
  const enabled = localStorage.getItem(TAB_NOTIFICATIONS_ENABLED_KEY);
  return enabled === 'true';
}

export function setTabNotificationsEnabled(enabled: boolean): void {
  localStorage.setItem(TAB_NOTIFICATIONS_ENABLED_KEY, String(enabled));
  if (!enabled) {
    clearTabNotifications();
  }
}

export function initTabNotifications(): void {
  const title = document.title?.trim();
  if (title && !/^\(\d+\)\s/.test(title)) {
    baseTitle = title;
  }
  getFaviconLink();
}

export function incrementTabNotification(): void {
  if (!areTabNotificationsEnabled()) return;
  if (!document.hidden && document.hasFocus()) return;

  unreadCount += 1;
  blinkVisible = true;
  applyTabIndicator();
  startBlink();
}

export function clearTabNotifications(): void {
  unreadCount = 0;
  stopBlink();
  document.title = baseTitle;
  restoreFavicon();
}
