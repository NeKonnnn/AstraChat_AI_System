import React from 'react';
import { Box, Typography, keyframes } from '@mui/material';
import type { ChatInputSuggestion } from '../chat/inputSuggestions';

const fadeIn = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`;

interface MessageFollowUpSuggestionsProps {
  suggestions?: ChatInputSuggestion[];
  disabled?: boolean;
  isDarkMode?: boolean;
  onSelect: (content: string) => void;
}

export default function MessageFollowUpSuggestions({
  suggestions = [],
  disabled = false,
  isDarkMode = false,
  onSelect,
}: MessageFollowUpSuggestionsProps) {
  if (!suggestions.length) return null;

  const titleColor = isDarkMode ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.87)';
  const subtitleColor = isDarkMode ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.5)';
  const labelColor = isDarkMode ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)';
  const dividerColor = isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';

  return (
    <Box
      sx={{
        mt: 2,
        animation: `${fadeIn} 180ms ease forwards`,
      }}
    >
      <Typography
        variant="body2"
        sx={{
          fontWeight: 500,
          fontSize: '0.875rem',
          color: labelColor,
          mb: 1,
        }}
      >
        Следующий шаг
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {suggestions.map((item, index) => (
          <React.Fragment key={item.id}>
            <Box
              component="button"
              type="button"
              disabled={disabled}
              onClick={() => onSelect(item.content)}
              sx={{
                display: 'block',
                width: '100%',
                p: '6px 0',
                m: 0,
                border: 'none',
                bgcolor: 'transparent',
                textAlign: 'left',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                transition: 'opacity 0.15s ease',
                '&:hover': disabled ? undefined : { opacity: 0.72 },
              }}
            >
              <Typography
                sx={{
                  display: 'block',
                  fontWeight: 600,
                  fontSize: '0.95rem',
                  lineHeight: 1.35,
                  color: titleColor,
                }}
              >
                {item.title}
              </Typography>
              {item.subtitle ? (
                <Typography
                  sx={{
                    display: 'block',
                    mt: 0.1,
                    fontWeight: 400,
                    fontSize: '0.875rem',
                    lineHeight: 1.4,
                    color: subtitleColor,
                  }}
                >
                  {item.subtitle}
                </Typography>
              ) : null}
            </Box>
            {index < suggestions.length - 1 ? (
              <Box sx={{ height: '1px', bgcolor: dividerColor, my: 0.25 }} />
            ) : null}
          </React.Fragment>
        ))}
      </Box>
    </Box>
  );
}
