import { logChatAttach, logChatAttachError } from './chatAttachDebug';

/** Макс. сторона изображения для inline-вложения (достаточно для мультимодалки). */
const MAX_DIMENSION_PX = 2048;
/** Целевой размер data URL (~4 МБ raw ≈ лимит многих ingress). */
const TARGET_DATA_URL_CHARS = 5_500_000;
const MIN_JPEG_QUALITY = 0.55;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('invalid-image'));
    img.src = src;
  });
}

function estimateBytesFromDataUrl(dataUrl: string): number {
  const base64 = dataUrl.split(',')[1] || '';
  return Math.round((base64.length * 3) / 4);
}

/**
 * Сжимает изображение в браузере до data URL без запроса на сервер.
 * Обходит лимит ingress (413) на POST /api/documents/extract.
 */
export async function prepareInlineImageFile(file: File): Promise<{
  dataUrl: string;
  filename: string;
  originalSize: number;
  compressedSize: number;
  wasCompressed: boolean;
}> {
  logChatAttach('image-compress-start', {
    name: file.name,
    type: file.type,
    size: file.size,
    sizeHuman: formatFileSize(file.size),
  });

  const objectUrl = URL.createObjectURL(file);
  try {
    const img = await loadImage(objectUrl);
    let width = img.naturalWidth;
    let height = img.naturalHeight;

    logChatAttach('image-loaded', {
      name: file.name,
      naturalWidth: width,
      naturalHeight: height,
    });

    const maxSide = Math.max(width, height);
    if (maxSide > MAX_DIMENSION_PX) {
      const scale = MAX_DIMENSION_PX / maxSide;
      width = Math.round(width * scale);
      height = Math.round(height * scale);
      logChatAttach('image-resize', { name: file.name, newWidth: width, newHeight: height, maxSide });
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('canvas-unavailable');
    }
    ctx.drawImage(img, 0, 0, width, height);

    const usePng = file.type === 'image/png' || file.type === 'image/gif';
    let dataUrl = usePng
      ? canvas.toDataURL('image/png')
      : canvas.toDataURL('image/jpeg', 0.88);

    if (dataUrl.length > TARGET_DATA_URL_CHARS && usePng) {
      logChatAttach('image-png-to-jpeg', { name: file.name, dataUrlChars: dataUrl.length });
      dataUrl = canvas.toDataURL('image/jpeg', 0.88);
    }

    let quality = 0.88;
    while (dataUrl.length > TARGET_DATA_URL_CHARS && quality >= MIN_JPEG_QUALITY) {
      quality = Math.round((quality - 0.08) * 100) / 100;
      dataUrl = canvas.toDataURL('image/jpeg', quality);
    }

    const compressedSize = estimateBytesFromDataUrl(dataUrl);
    const baseName = (file.name || 'image').replace(/\.[^.]+$/, '');
    const ext = dataUrl.startsWith('data:image/png') ? '.png' : '.jpg';

    const result = {
      dataUrl,
      filename: `${baseName}${ext}`,
      originalSize: file.size,
      compressedSize,
      wasCompressed: file.size > compressedSize || maxSide > MAX_DIMENSION_PX,
    };

    logChatAttach('image-compress-done', {
      name: file.name,
      outputFilename: result.filename,
      originalSize: result.originalSize,
      compressedSize: result.compressedSize,
      dataUrlChars: dataUrl.length,
      targetDataUrlChars: TARGET_DATA_URL_CHARS,
      overTarget: dataUrl.length > TARGET_DATA_URL_CHARS,
      finalQuality: quality,
      wasCompressed: result.wasCompressed,
    });

    return result;
  } catch (error) {
    logChatAttachError('image-compress-failed', error, { name: file.name, size: file.size });
    throw error;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

/** Data URL → File для загрузки сжатого изображения на /api/documents/attach */
export function dataUrlToFile(dataUrl: string, filename: string): File {
  const [header, base64] = dataUrl.split(',');
  const mime = header.match(/:(.*?);/)?.[1] ?? 'image/jpeg';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new File([bytes], filename, { type: mime });
}

/** Изображение из буфера (Win+Shift+S, Print Screen, копирование картинки). */
export function getClipboardImageFile(clipboardData: DataTransfer): File | null {
  const fromItems = (): File | null => {
    const items = clipboardData.items;
    if (!items) return null;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind !== 'file' || !item.type.startsWith('image/')) continue;
      const blob = item.getAsFile();
      if (!blob) continue;
      const ext = blob.type.split('/')[1] || 'png';
      const name = blob.name?.trim() ? blob.name : `screenshot_${Date.now()}.${ext}`;
      return blob.name?.trim() ? blob : new File([blob], name, { type: blob.type || 'image/png' });
    }
    return null;
  };

  const fromFiles = (): File | null => {
    const files = clipboardData.files;
    if (!files?.length) return null;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) continue;
      const ext = file.type.split('/')[1] || 'png';
      const name = file.name?.trim() ? file.name : `screenshot_${Date.now()}.${ext}`;
      return file.name?.trim() ? file : new File([file], name, { type: file.type });
    }
    return null;
  };

  return fromItems() ?? fromFiles();
}
