import React from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import { Close as CloseIcon, Description as DocumentIcon, PictureAsPdf as PdfIcon } from '@mui/icons-material';
import { formatFileSize } from '../utils/inlineImage';

export const INLINE_DOC_ICON_SIZE = 44;
export const INLINE_DOC_CHIP_MIN_HEIGHT = 56;

export type InlineDocKind = 'pdf' | 'word' | 'excel' | 'txt' | 'other';

export function getInlineDocKind(filename: string): InlineDocKind {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.pdf')) return 'pdf';
  if (/\.docx?$/.test(lower)) return 'word';
  if (/\.xlsx?$/.test(lower)) return 'excel';
  if (lower.endsWith('.txt')) return 'txt';
  return 'other';
}

function getInlineDocThumbColor(kind: InlineDocKind, isDarkMode: boolean): string {
  switch (kind) {
    case 'pdf': return '#d94a3a';
    case 'word': return '#2b579a';
    case 'excel': return '#217346';
    case 'txt': return '#00a4ef';
    default: return isDarkMode ? '#546e7a' : '#78909c';
  }
}

/** Имя с многоточием, но с сохранением расширения: «Длинное … .docx» */
export function formatInlineAttachmentFileName(name: string, maxLength = 30): string {
  if (name.length <= maxLength) return name;
  const dot = name.lastIndexOf('.');
  const ext = dot > 0 ? name.slice(dot) : '';
  const base = dot > 0 ? name.slice(0, dot) : name;
  const suffix = ext ? ` …${ext}` : '…';
  const available = maxLength - suffix.length;
  if (available <= 1) return `${name.slice(0, maxLength - 1)}…`;
  return `${base.slice(0, available)}${suffix}`;
}

const officeLetterSx = {
  fontWeight: 700,
  fontSize: '1.35rem',
  lineHeight: 1,
  fontFamily: '"Segoe UI", system-ui, -apple-system, sans-serif',
  userSelect: 'none',
} as const;

function PdfThumbIcon() {
  return <PdfIcon sx={{ fontSize: '1.65rem' }} />;
}

export function InlineDocThumb({
  filename,
  isDarkMode = false,
}: {
  filename: string;
  isDarkMode?: boolean;
}) {
  const kind = getInlineDocKind(filename);
  const color = getInlineDocThumbColor(kind, isDarkMode);

  const boxSx = {
    width: INLINE_DOC_ICON_SIZE,
    height: INLINE_DOC_ICON_SIZE,
    borderRadius: '8px',
    bgcolor: color,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'white',
    flexShrink: 0,
  };

  if (kind === 'pdf') {
    return (
      <Box sx={boxSx}>
        <PdfThumbIcon />
      </Box>
    );
  }
  if (kind === 'word') {
    return (
      <Box sx={boxSx}>
        <Typography sx={officeLetterSx}>W</Typography>
      </Box>
    );
  }
  if (kind === 'excel') {
    return (
      <Box sx={boxSx}>
        <Typography sx={officeLetterSx}>X</Typography>
      </Box>
    );
  }
  if (kind === 'txt') {
    return (
      <Box sx={boxSx}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.72rem', lineHeight: 1, letterSpacing: '0.03em' }}>
          TXT
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={boxSx}>
      <DocumentIcon sx={{ fontSize: '1.45rem' }} />
    </Box>
  );
}

export function getInlineDocChipCloseSx(isDarkMode: boolean, isMessage: boolean) {
  return {
    position: 'absolute' as const,
    top: 6,
    right: 6,
    width: 22,
    height: 22,
    minWidth: 22,
    p: 0,
    borderRadius: '50%',
    bgcolor: isMessage ? 'rgba(0, 0, 0, 0.28)' : isDarkMode ? 'rgba(0, 0, 0, 0.38)' : 'rgba(0, 0, 0, 0.12)',
    color: isMessage ? 'rgba(255, 255, 255, 0.82)' : isDarkMode ? 'rgba(255, 255, 255, 0.72)' : 'rgba(0, 0, 0, 0.55)',
    '&:hover': {
      bgcolor: isMessage ? 'rgba(0, 0, 0, 0.42)' : isDarkMode ? 'rgba(0, 0, 0, 0.52)' : 'rgba(0, 0, 0, 0.18)',
      color: isMessage ? 'white' : isDarkMode ? 'white' : '#333',
    },
  };
}

export function getInlineDocChipSx(isDarkMode: boolean, isMessage: boolean) {
  return {
    position: 'relative' as const,
    display: 'flex',
    alignItems: 'center',
    gap: 1.25,
    width: '100%',
    minWidth: 0,
    minHeight: INLINE_DOC_CHIP_MIN_HEIGHT,
    px: 1.25,
    py: 0.875,
    pr: 3.5,
    borderRadius: '10px',
    bgcolor: isMessage ? 'rgba(255, 255, 255, 0.14)' : isDarkMode ? 'rgba(255, 255, 255, 0.07)' : 'rgba(0, 0, 0, 0.05)',
    border: isMessage
      ? '1px solid rgba(255, 255, 255, 0.2)'
      : `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)'}`,
    boxSizing: 'border-box' as const,
  };
}

interface InlineDocAttachmentChipProps {
  name: string;
  size?: number;
  sizeLabel?: string;
  isDarkMode?: boolean;
  isMessage?: boolean;
  onRemove?: () => void;
  removeDisabled?: boolean;
  leading?: React.ReactNode;
}

export default function InlineDocAttachmentChip({
  name,
  size,
  sizeLabel,
  isDarkMode = false,
  isMessage = false,
  onRemove,
  removeDisabled = false,
  leading,
}: InlineDocAttachmentChipProps) {
  const displayName = formatInlineAttachmentFileName(name);
  const resolvedSizeLabel =
    sizeLabel ?? (typeof size === 'number' && size > 0 ? formatFileSize(size) : undefined);

  const nameSx = {
    fontWeight: 600,
    display: 'block',
    color: isMessage ? 'primary.contrastText' : isDarkMode ? 'rgba(255,255,255,0.92)' : '#1a1a1a',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    fontSize: '0.8125rem',
    lineHeight: 1.3,
  };

  const fileSizeSx = {
    display: 'block',
    mt: 0.125,
    fontSize: '0.6875rem',
    lineHeight: 1.25,
    color: isMessage ? 'rgba(255, 255, 255, 0.62)' : isDarkMode ? 'rgba(255, 255, 255, 0.48)' : 'rgba(0, 0, 0, 0.48)',
  };

  return (
    <Box className="file-attachment" sx={getInlineDocChipSx(isDarkMode, isMessage)}>
      {leading ?? <InlineDocThumb filename={name} isDarkMode={isDarkMode} />}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="caption" sx={nameSx} title={name}>
          {displayName}
        </Typography>
        {resolvedSizeLabel && (
          <Typography variant="caption" sx={fileSizeSx}>
            {resolvedSizeLabel}
          </Typography>
        )}
      </Box>
      {onRemove && (
        <IconButton
          size="small"
          onClick={onRemove}
          disabled={removeDisabled}
          aria-label={`Удалить вложение ${name}`}
          sx={{
            ...getInlineDocChipCloseSx(isDarkMode, isMessage),
            ...(removeDisabled ? { opacity: 0.45 } : {}),
          }}
        >
          <CloseIcon sx={{ fontSize: '0.9rem' }} />
        </IconButton>
      )}
    </Box>
  );
}
