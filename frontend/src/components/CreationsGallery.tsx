import React, { useMemo, useState } from 'react';
import { Box, Typography, Chip, CircularProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import AuthenticatedInlineImage from './AuthenticatedInlineImage';
import InlineImageLightbox from './InlineImageLightbox';
import { useImageCreations } from '../hooks/useImageCreations';
import { resolveCreationPreviewSrc, type ImageCreationItem } from '../utils/imageCreations';

type FilterKind = 'all' | 'image';

interface CreationsGalleryProps {
  isDarkMode?: boolean;
}

export default function CreationsGallery({ isDarkMode = true }: CreationsGalleryProps) {
  const navigate = useNavigate();
  const { items, loading } = useImageCreations(500);
  const [filter, setFilter] = useState<FilterKind>('all');
  const [preview, setPreview] = useState<ImageCreationItem | null>(null);

  const filtered = useMemo(() => items, [items, filter]);

  const textColor = isDarkMode ? '#fff' : '#111';
  const muted = isDarkMode ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)';
  const cardBg = isDarkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';

  const handleEdit = () => {
    if (!preview) return;
    const base = preview.prompt?.trim();
    const text = base ? `Отредактируй изображение: ${base}` : 'Отредактируй изображение: ';
    if (preview.conversation_id) {
      navigate(`/?chat=${preview.conversation_id}`);
    }
    window.dispatchEvent(new CustomEvent('astrachatPrefillChatInput', { detail: { text } }));
    setPreview(null);
  };

  return (
    <>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2, color: textColor }}>
        Моё творение
      </Typography>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 3 }}>
        <Chip
          label="Все"
          onClick={() => setFilter('all')}
          color={filter === 'all' ? 'primary' : 'default'}
          variant={filter === 'all' ? 'filled' : 'outlined'}
        />
        <Chip
          label="Изображение"
          onClick={() => setFilter('image')}
          color={filter === 'image' ? 'primary' : 'default'}
          variant={filter === 'image' ? 'filled' : 'outlined'}
        />
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : filtered.length === 0 ? (
        <Typography sx={{ color: muted }}>
          Пока нет сгенерированных изображений. Напишите в чате «нарисуй …».
        </Typography>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 1.5,
            pb: 2,
          }}
        >
          {filtered.map((item) => {
            const src = resolveCreationPreviewSrc(item.preview_url);
            return (
              <Box
                key={item.id}
                onClick={() => {
                  if (src) setPreview(item);
                  else if (item.conversation_id) navigate(`/?chat=${item.conversation_id}`);
                }}
                sx={{
                  aspectRatio: '1',
                  borderRadius: 2,
                  overflow: 'hidden',
                  bgcolor: cardBg,
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
                  transition: 'transform 0.15s ease',
                  '&:hover': { transform: 'scale(1.02)' },
                }}
              >
                {src ? (
                  <AuthenticatedInlineImage
                    src={src}
                    alt={item.prompt || item.name || 'generated'}
                    sx={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                  />
                ) : (
                  <Box
                    sx={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      p: 1,
                    }}
                  >
                    <Typography variant="caption" sx={{ color: muted, textAlign: 'center' }}>
                      {item.prompt || 'Изображение'}
                    </Typography>
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
      )}

      <InlineImageLightbox
        open={Boolean(preview)}
        src={preview ? resolveCreationPreviewSrc(preview.preview_url) || '' : ''}
        name={preview?.name || 'generated.png'}
        onClose={() => setPreview(null)}
        onEdit={handleEdit}
      />
    </>
  );
}
