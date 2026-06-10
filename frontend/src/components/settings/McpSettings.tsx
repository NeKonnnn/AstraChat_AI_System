import React from 'react';
import { Box, Typography } from '@mui/material';
import McpServersPanel from '../../mcp/components/McpServersPanel';

interface McpSettingsProps {
  isDarkMode: boolean;
}

/** Admin/settings tab — composition layer над generic MCP platform (F-2). */
export default function McpSettings({ isDarkMode }: McpSettingsProps) {
  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h5" gutterBottom>
        MCP
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Универсальная платформа инструментов Model Context Protocol. Подключение серверов — через backend config;
        в чате включайте MCP в «Инструменты → MCP».
      </Typography>
      <McpServersPanel isDarkMode={isDarkMode} />
    </Box>
  );
}
