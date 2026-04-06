import React, { useEffect, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { getApiUrl } from '../config/api';
import { getSettings } from '../settings';

/**
 * Плашка сверху (как в Qwen UI), если бэкенд сообщает, что до LLM (llm-svc) достучаться нельзя.
 * URL сервиса моделей фронт не знает — только GET /api/llm/status.
 */
export default function LlmStatusBanner() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;

    const poll = async () => {
      try {
        getSettings();
      } catch {
        return;
      }
      try {
        const res = await fetch(getApiUrl('/api/llm/status'));
        if (!res.ok) return;
        const data = await res.json();
        if (data.use_llm_svc === true && data.connected === false) {
          setOpen(true);
          setMessage(
            typeof data.message === 'string' && data.message.trim()
              ? data.message
              : 'Подключиться к LLM не удалось. Проверьте сервис моделей и конфигурацию на сервере.'
          );
        } else {
          setOpen(false);
          setMessage('');
        }
      } catch {
        setOpen(false);
      }
    };

    poll();
    interval = setInterval(poll, 30000);
    return () => {
      if (interval) clearInterval(interval);
    };
  }, []);

  if (!open) return null;

  return (
    <Box
      role="alert"
      sx={{
        position: 'fixed',
        top: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: (theme) => theme.zIndex.snackbar + 2,
        maxWidth: 'min(720px, calc(100vw - 24px))',
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
      <Typography variant="body2" color="error" sx={{ fontWeight: 600, textAlign: 'center' }}>
        {message}
      </Typography>
    </Box>
  );
}
