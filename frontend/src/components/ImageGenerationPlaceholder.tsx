import React from 'react';
import { Box, keyframes } from '@mui/material';
import { ImageOutlined as ImageOutlinedIcon, AutoAwesome as SparkleIcon } from '@mui/icons-material';

const shimmer = keyframes`
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
`;

const pulse = keyframes`
  0%, 100% { opacity: 0.85; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.04); }
`;

const drift = keyframes`
  0% { transform: translate(-8%, -6%) scale(1.1); }
  50% { transform: translate(6%, 4%) scale(1.15); }
  100% { transform: translate(-8%, -6%) scale(1.1); }
`;

const twinkle = keyframes`
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
`;

type Props = {
  /** Ширина карточки; по умолчанию адаптивная */
  maxWidth?: number | string;
};

const SPARKLE_POSITIONS = [
  { top: -6, right: -12, size: 18, delay: '0s', duration: '1.6s' },
  { top: -14, right: 4, size: 12, delay: '0.45s', duration: '2.1s' },
  { top: 2, right: -18, size: 10, delay: '0.9s', duration: '1.9s' },
] as const;

/**
 * Плейсхолдер генерации изображения (анимация в духе Qwen Studio).
 */
export default function ImageGenerationPlaceholder({ maxWidth = 420 }: Props) {
  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        maxWidth,
        aspectRatio: '16 / 10',
        minHeight: 200,
        borderRadius: '20px',
        overflow: 'hidden',
        background: 'linear-gradient(125deg, #6a3fb8 0%, #4f5bd5 28%, #2b6cb0 52%, #1a8a9e 78%, #5b3a9e 100%)',
        backgroundSize: '220% 220%',
        animation: `${shimmer} 5s ease-in-out infinite`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: 'inset 0 0 80px rgba(0,0,0,0.12)',
      }}
      aria-label="Генерация изображения"
      role="status"
    >
      <Box
        sx={{
          position: 'absolute',
          inset: '-20%',
          background:
            'radial-gradient(circle at 30% 40%, rgba(186, 104, 255, 0.55) 0%, transparent 45%), radial-gradient(circle at 70% 60%, rgba(64, 196, 255, 0.45) 0%, transparent 42%)',
          animation: `${drift} 8s ease-in-out infinite`,
          pointerEvents: 'none',
        }}
      />
      <Box
        sx={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(255,255,255,0.92)',
          animation: `${pulse} 2.4s ease-in-out infinite`,
        }}
      >
        <ImageOutlinedIcon sx={{ fontSize: 40, opacity: 0.95 }} />
        {SPARKLE_POSITIONS.map((sparkle, index) => (
          <SparkleIcon
            key={index}
            sx={{
              fontSize: sparkle.size,
              position: 'absolute',
              top: sparkle.top,
              right: sparkle.right,
              color: 'rgba(255,255,255,0.95)',
              animation: `${twinkle} ${sparkle.duration} ease-in-out infinite`,
              animationDelay: sparkle.delay,
            }}
          />
        ))}
      </Box>
    </Box>
  );
}
