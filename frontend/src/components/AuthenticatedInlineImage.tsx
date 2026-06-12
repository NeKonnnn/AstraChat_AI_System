import React, { useEffect, useState } from 'react';
import { Box, CircularProgress, SxProps, Theme, Typography } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

/** Превью из MinIO с Bearer-токеном (обычный img src не передаёт Authorization). */
export default function AuthenticatedInlineImage({
  src,
  alt,
  onExpand,
  sx,
}: {
  src: string;
  alt: string;
  onExpand?: (resolvedSrc: string) => void;
  sx?: SxProps<Theme>;
}): React.ReactElement | null {
  const { token } = useAuth();
  const [displaySrc, setDisplaySrc] = useState<string | null>(
    src.startsWith('data:') || src.startsWith('blob:') ? src : null,
  );
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    if (src.startsWith('data:') || src.startsWith('blob:')) {
      setDisplaySrc(src);
      return;
    }
    if (!token) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setDisplaySrc(null);
    (async () => {
      try {
        const res = await fetch(src, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok || cancelled) {
          if (!cancelled) setFailed(true);
          return;
        }
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setDisplaySrc(objectUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src, token]);

  if (failed) {
    return (
      <Box
        sx={{
          ...(sx as object),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 1,
        }}
      >
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)', textAlign: 'center' }}>
          Не удалось загрузить
        </Typography>
      </Box>
    );
  }

  if (!displaySrc) {
    return (
      <Box
        sx={{
          ...(sx as object),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: 72,
          minHeight: 72,
        }}
      >
        <CircularProgress size={22} />
      </Box>
    );
  }

  return (
    <Box
      component="img"
      src={displaySrc}
      alt={alt}
      onClick={() => onExpand?.(displaySrc)}
      sx={sx}
    />
  );
}
