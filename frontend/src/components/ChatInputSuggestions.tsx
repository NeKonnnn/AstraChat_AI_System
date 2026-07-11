import React, { useMemo } from 'react';
import { Box, Typography, keyframes } from '@mui/material';
import { AutoAwesome as SparkleIcon } from '@mui/icons-material';
import {
  type ChatInputSuggestion,
  pickVisibleSuggestions,
} from '../chat/inputSuggestions';

const fadeInUp = keyframes`
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

const MAX_VISIBLE = 3;
const MAX_INPUT_LENGTH = 500;

interface ChatInputSuggestionsProps {
  suggestions: ChatInputSuggestion[];
  inputValue: string;
  onSelect: (content: string) => void;
  disabled?: boolean;
  isDarkMode?: boolean;
  maxWidth?: string | number;
  showLabel?: boolean;
  /** Отступ слева (theme.spacing) — выравнивание под кнопкой «Инструменты». */
  contentInset?: number;
}

export default function ChatInputSuggestions({
  suggestions,
  inputValue,
  onSelect,
  disabled = false,
  isDarkMode = false,
  maxWidth = '100%',
  showLabel = true,
  contentInset = 6.25,
}: ChatInputSuggestionsProps) {
  const filtered = useMemo(() => {
    if (disabled || inputValue.length > MAX_INPUT_LENGTH) return [];
    return pickVisibleSuggestions(suggestions, inputValue, MAX_VISIBLE);
  }, [suggestions, inputValue, disabled]);

  if (!filtered.length) return null;

  const titleColor = isDarkMode ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.87)';
  const subtitleColor = isDarkMode ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.5)';
  const labelColor = isDarkMode ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)';

  return (
    <Box
      sx={{
        width: '100%',
        maxWidth,
        mx: 'auto',
        mt: 2,
        pr: 1,
        pl: contentInset,
        textAlign: 'left',
      }}
    >
      {showLabel ? (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            mb: 1.5,
            color: labelColor,
          }}
        >
          <SparkleIcon sx={{ fontSize: 16, opacity: 0.85, flexShrink: 0 }} />
          <Typography
            variant="body2"
            sx={{
              fontWeight: 500,
              fontSize: '0.875rem',
              color: 'inherit',
            }}
          >
            Предложено
          </Typography>
        </Box>
      ) : null}

      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 1.75,
          pl: showLabel
            ? (theme) => `calc(16px + ${theme.spacing(0.75)})`
            : 0,
        }}
      >
        {filtered.map((item, index) => (
          <Box
            key={item.id}
            component="button"
            type="button"
            disabled={disabled}
            onClick={() => onSelect(item.content)}
            sx={{
              display: 'block',
              p: 0,
              m: 0,
              border: 'none',
              bgcolor: 'transparent',
              textAlign: 'left',
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
              animation: `${fadeInUp} 220ms ease forwards`,
              animationDelay: `${index * 50}ms`,
              animationFillMode: 'both',
              transition: 'opacity 0.15s ease',
              '&:hover': disabled
                ? undefined
                : {
                    opacity: 0.72,
                  },
              '&:focus-visible': {
                outline: 'none',
                '& .suggestion-title': {
                  textDecoration: 'underline',
                  textUnderlineOffset: 3,
                },
              },
            }}
          >
            <Typography
              className="suggestion-title"
              sx={{
                display: 'block',
                fontWeight: 600,
                fontSize: '1.05rem',
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
                  mt: 0.15,
                  fontWeight: 400,
                  fontSize: '0.95rem',
                  lineHeight: 1.4,
                  color: subtitleColor,
                }}
              >
                {item.subtitle}
              </Typography>
            ) : null}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
