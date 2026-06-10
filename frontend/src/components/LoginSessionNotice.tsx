import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Box } from '@mui/material';
import { consumeLoginSessionNotice } from '../settings/sessionValidity';

const AUTO_HIDE_MS = 10_000;

/**
 * Всплывающее уведомление на странице login после принудительного завершения сессии.
 */
export default function LoginSessionNotice() {
  const [message, setMessage] = useState<string | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
    setMessage(null);
  }, []);

  useEffect(() => {
    const notice = consumeLoginSessionNotice();
    if (notice) {
      setMessage(notice);
    }
  }, []);

  useEffect(() => {
    if (!message) return undefined;

    hideTimerRef.current = setTimeout(dismiss, AUTO_HIDE_MS);
    return () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
    };
  }, [message, dismiss]);

  if (!message) return null;

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 2000,
        width: 'min(480px, calc(100% - 32px))',
      }}
    >
      <Alert
        severity="error"
        variant="outlined"
        onClose={dismiss}
        sx={{
          borderWidth: 2,
          borderColor: 'error.main',
          boxShadow: '0 4px 20px rgba(211, 47, 47, 0.25)',
        }}
      >
        {message}
      </Alert>
    </Box>
  );
}
