import React from 'react';
import { Box, useTheme } from '@mui/material';
import CreationsGallery from '../components/CreationsGallery';
import { getWorkZoneBackgroundColor } from '../constants/workZoneBackground';
import { useWorkZoneBgMode } from '../hooks/useWorkZoneBgMode';

export default function CreationsPage() {
  const theme = useTheme();
  const isDarkMode = theme.palette.mode === 'dark';
  const workZoneMode = useWorkZoneBgMode();
  const workZoneBgColor = getWorkZoneBackgroundColor(isDarkMode, workZoneMode);

  return (
    <Box
      sx={{
        flexGrow: 1,
        height: '100%',
        overflow: 'auto',
        pt: 4,
        px: { xs: 2, sm: 3 },
        pb: 3,
        backgroundColor: workZoneBgColor,
        color: isDarkMode ? 'white' : '#333',
      }}
    >
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <CreationsGallery isDarkMode={isDarkMode} />
      </Box>
    </Box>
  );
}
