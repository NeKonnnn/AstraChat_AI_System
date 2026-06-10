import React, { useState } from 'react';
import { Box, Chip, Collapse, IconButton, Typography } from '@mui/material';
import { ExpandMore as ExpandMoreIcon, HubOutlined as HubIcon } from '@mui/icons-material';
import type { McpToolCallRecord } from '../types';

interface McpToolCallsPanelProps {
  toolCalls: McpToolCallRecord[];
  serverLabels?: Record<string, string>;
}

export default function McpToolCallsPanel({ toolCalls, serverLabels }: McpToolCallsPanelProps) {
  const [open, setOpen] = useState(false);
  if (!toolCalls.length) return null;

  const ends = toolCalls.filter((t) => t.type === 'mcp_tool_end');

  return (
    <Box sx={{ mt: 1 }}>
      <Box
        role="button"
        tabIndex={0}
        onClick={() => setOpen((v) => !v)}
        sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, cursor: 'pointer' }}
      >
        <HubIcon sx={{ fontSize: 16, color: 'primary.main' }} />
        <Typography variant="caption" color="primary">
          Использованные MCP-инструменты ({ends.length || toolCalls.length})
        </Typography>
        <IconButton size="small" sx={{ transform: open ? 'rotate(180deg)' : 'none' }}>
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 0.75, pl: 0.5 }}>
          {(ends.length ? ends : toolCalls).map((t, i) => (
            <Box
              key={`${t.qualified_name}-${i}`}
              sx={{
                borderLeft: '2px solid',
                borderColor: t.success === false ? 'error.light' : 'primary.light',
                pl: 1,
              }}
            >
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
                <Chip size="small" label={serverLabels?.[t.server_id] || t.server_id} variant="outlined" />
                {t.model ? <Chip size="small" label={t.model} color="info" variant="outlined" /> : null}
                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                  {t.qualified_name}
                </Typography>
                {t.duration_ms != null ? (
                  <Typography variant="caption" color="text.secondary">
                    {t.duration_ms} ms
                  </Typography>
                ) : null}
              </Box>
              {t.type === 'mcp_tool_end' && t.success === false ? (
                <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.25 }}>
                  {t.error || 'error'}
                </Typography>
              ) : null}
              {t.result_preview ? (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    display: 'block',
                    mt: 0.35,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontFamily: 'inherit',
                  }}
                >
                  {t.result_preview}
                </Typography>
              ) : null}
              {t.has_image ? (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  [вложение: изображение]
                </Typography>
              ) : null}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
