import React from 'react';
import { Box, IconButton, Modal, Typography } from '@mui/material';
import { Close as CloseIcon, FileDownload as DownloadIcon } from '@mui/icons-material';
import { getInlineAttachmentExtension } from '../utils/inlineAttachmentRules';

interface InlineImageLightboxProps {
  open: boolean;
  src: string;
  name: string;
  onClose: () => void;
}

export default function InlineImageLightbox({ open, src, name, onClose }: InlineImageLightboxProps) {
  const ext = getInlineAttachmentExtension(name);
  const formatLabel = ext ? ext.slice(1).toUpperCase() : 'IMG';

  const handleDownload = () => {
    const anchor = document.createElement('a');
    anchor.href = src;
    anchor.download = name || `image${ext || '.png'}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: (theme) => theme.zIndex.modal + 2,
      }}
      slotProps={{
        backdrop: { sx: { bgcolor: 'rgba(0, 0, 0, 0.92)' } },
      }}
    >
      <Box
        sx={{
          position: 'relative',
          width: '100vw',
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          outline: 'none',
          p: { xs: 1, sm: 2 },
        }}
        onClick={onClose}
      >
        <IconButton
          aria-label="Закрыть просмотр изображения"
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          sx={{
            position: 'fixed',
            top: { xs: 12, sm: 20 },
            right: { xs: 12, sm: 24 },
            color: 'rgba(255,255,255,0.9)',
            bgcolor: 'rgba(0,0,0,0.35)',
            '&:hover': { bgcolor: 'rgba(0,0,0,0.55)' },
            zIndex: 1,
          }}
        >
          <CloseIcon />
        </IconButton>

        <Box
          sx={{
            position: 'relative',
            maxWidth: 'min(98vw, 1800px)',
            maxHeight: '96vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Box
            component="img"
            src={src}
            alt={name}
            sx={{
              display: 'block',
              maxWidth: 'min(98vw, 1800px)',
              maxHeight: '96vh',
              width: 'auto',
              height: 'auto',
              objectFit: 'contain',
              borderRadius: '4px',
              boxShadow: '0 12px 48px rgba(0,0,0,0.55)',
            }}
          />

          <Box
            sx={{
              position: 'absolute',
              left: '50%',
              bottom: 20,
              transform: 'translateX(-50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 0.75,
            }}
          >
            <Typography
              variant="caption"
              sx={{
                color: 'rgba(255,255,255,0.75)',
                fontSize: '0.75rem',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              {formatLabel}
              {ext ? ` · ${ext}` : ''}
            </Typography>
            <Box
              component="button"
              type="button"
              onClick={handleDownload}
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.75,
                px: 2,
                py: 0.85,
                border: 'none',
                borderRadius: '999px',
                bgcolor: 'rgba(30, 30, 30, 0.82)',
                color: 'rgba(255,255,255,0.92)',
                cursor: 'pointer',
                fontSize: '0.875rem',
                fontWeight: 500,
                backdropFilter: 'blur(8px)',
                transition: 'background-color 0.15s',
                '&:hover': { bgcolor: 'rgba(50, 50, 50, 0.92)' },
              }}
            >
              <DownloadIcon sx={{ fontSize: '1.1rem' }} />
              Скачать
            </Box>
          </Box>
        </Box>
      </Box>
    </Modal>
  );
}
