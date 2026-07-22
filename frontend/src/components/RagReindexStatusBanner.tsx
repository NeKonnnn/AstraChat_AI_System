import React, { useEffect, useState } from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import { useRagReindexStatus } from '../hooks/useRagReindexStatus';
import { TOP_ERROR_BANNER_AUTO_DISMISS_MS } from './TopErrorBanner';

/**
 * Оранжевая плашка сверху при перечанковке RAG (poll GET /api/rag/reindex-status).
 */
export default function RagReindexStatusBanner() {
  const { anyReindexing, blockMessage } = useRagReindexStatus();
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (anyReindexing) {
      setOpen(!dismissed);
    } else {
      setOpen(false);
      setDismissed(false);
    }
  }, [anyReindexing, dismissed]);

  useEffect(() => {
    if (!open) return undefined;
    const timer = window.setTimeout(() => {
      setOpen(false);
      setDismissed(true);
    }, TOP_ERROR_BANNER_AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [open, blockMessage]);

  if (!open || !blockMessage) return null;

  return (
    <Box
      role="alert"
      sx={{
        position: 'fixed',
        top: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: (theme) => theme.zIndex.snackbar + 1,
        maxWidth: 'min(720px, calc(100vw - 24px))',
        px: 2,
        py: 1.25,
        borderRadius: 1,
        border: '2px solid',
        borderColor: 'warning.main',
        bgcolor: 'rgba(237, 108, 2, 0.12)',
        boxShadow: '0 4px 24px rgba(0,0,0,0.18)',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
        <Typography
          variant="body2"
          color="warning.main"
          sx={{ fontWeight: 600, textAlign: 'center', flex: 1 }}
        >
          {blockMessage}
        </Typography>
        <IconButton
          size="small"
          aria-label="Закрыть уведомление о перечанковке RAG"
          onClick={() => {
            setOpen(false);
            setDismissed(true);
          }}
          sx={{
            color: 'warning.main',
            mt: -0.5,
            mr: -0.5,
            '&:hover': { bgcolor: 'rgba(237, 108, 2, 0.12)' },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  );
}
