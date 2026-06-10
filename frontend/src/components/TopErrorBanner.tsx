import React, { useEffect, useRef } from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';

export const TOP_ERROR_BANNER_AUTO_DISMISS_MS = 10_000;

interface TopErrorBannerProps {
  message: string;
  onClose: () => void;
  ariaLabel?: string;
}

/** Красная плашка сверху по центру (как LlmStatusBanner / Qwen UI). */
export default function TopErrorBanner({
  message,
  onClose,
  ariaLabel = 'Закрыть уведомление об ошибке',
}: TopErrorBannerProps) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!message.trim()) return undefined;
    const timer = window.setTimeout(() => onCloseRef.current(), TOP_ERROR_BANNER_AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [message]);

  if (!message.trim()) return null;

  return (
    <Box
      role="alert"
      sx={{
        position: 'fixed',
        top: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: (theme) => theme.zIndex.snackbar + 3,
        maxWidth: 'min(760px, calc(100vw - 24px))',
        px: 2,
        py: 1.25,
        borderRadius: 1,
        border: '2px solid',
        borderColor: 'error.main',
        bgcolor: (theme) =>
          theme.palette.mode === 'dark' ? 'rgba(183, 28, 28, 0.25)' : 'rgba(211, 47, 47, 0.08)',
        boxShadow: '0 4px 24px rgba(0,0,0,0.18)',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        <Typography variant="body2" color="error" sx={{ fontWeight: 600, textAlign: 'center', flex: 1 }}>
          {message}
        </Typography>
        <IconButton
          size="small"
          aria-label={ariaLabel}
          onClick={onClose}
          sx={{
            color: 'error.main',
            mt: -0.5,
            mr: -0.5,
            flexShrink: 0,
            '&:hover': { bgcolor: 'rgba(211, 47, 47, 0.12)' },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  );
}
