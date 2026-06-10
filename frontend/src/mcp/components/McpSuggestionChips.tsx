import React from 'react';
import { Box, Chip } from '@mui/material';

interface McpSuggestionChipsProps {
  suggestions: string[];
  onSelect: (text: string) => void;
  disabled?: boolean;
}

/** Быстрые подсказки над полем ввода (F-7, plugin-driven). */
export default function McpSuggestionChips({ suggestions, onSelect, disabled }: McpSuggestionChipsProps) {
  if (!suggestions.length || disabled) return null;

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 1, px: 0.5 }}>
      {suggestions.map((label) => (
        <Chip
          key={label}
          label={label}
          size="small"
          variant="outlined"
          clickable={!disabled}
          onClick={() => onSelect(label)}
          sx={{ maxWidth: '100%' }}
        />
      ))}
    </Box>
  );
}
