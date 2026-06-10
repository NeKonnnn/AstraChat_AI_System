import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  Collapse,
  IconButton,
  Typography,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  HubOutlined as HubIcon,
  LockOutlined as LockIcon,
} from '@mui/icons-material';
import type { McpServerConfigPublic, McpServerStatus } from '../types';
import { getMcpServerSettingsPlugin } from '../plugins/registry';
import McpVerifyButton from './McpVerifyButton';
import type { McpVerifyResult } from '../types';

interface McpServerCardProps {
  server: McpServerConfigPublic;
  runtimeStatus?: McpServerStatus | null;
  isDarkMode: boolean;
  isAdmin?: boolean;
  onVerify: (serverId: string) => Promise<McpVerifyResult>;
  accessDenied?: boolean;
}

export default function McpServerCard({
  server,
  runtimeStatus,
  isDarkMode,
  isAdmin,
  onVerify,
  accessDenied,
}: McpServerCardProps) {
  const [expanded, setExpanded] = useState(false);
  const Plugin = getMcpServerSettingsPlugin(server.id);
  const connected = runtimeStatus?.connected;
  const muted = isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)';

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
          <HubIcon sx={{ color: connected ? 'success.main' : muted, mt: 0.25 }} />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="h6" sx={{ fontSize: '1rem' }}>
                {server.display_name || server.id}
              </Typography>
              <Chip label={server.id} size="small" variant="outlined" />
              {!server.enabled ? <Chip label="disabled" size="small" color="default" /> : null}
              {accessDenied ? (
                <Chip icon={<LockIcon />} label="Нет доступа" size="small" color="warning" />
              ) : connected ? (
                <Chip label="connected" size="small" color="success" />
              ) : (
                <Chip label="offline" size="small" color="error" variant="outlined" />
              )}
            </Box>
            <Typography variant="body2" sx={{ color: muted, mt: 0.5 }}>
              Transport: {server.transport}
              {runtimeStatus?.tools != null ? ` · tools: ${runtimeStatus.tools}` : ''}
              {runtimeStatus?.latency_ms != null ? ` · ${runtimeStatus.latency_ms} ms` : ''}
            </Typography>
            {runtimeStatus?.error ? (
              <Typography variant="caption" color="error.main" sx={{ display: 'block', mt: 0.5 }}>
                {runtimeStatus.error}
              </Typography>
            ) : null}
          </Box>
          <IconButton onClick={() => setExpanded((v) => !v)} size="small">
            <ExpandMoreIcon sx={{ transform: expanded ? 'rotate(180deg)' : 'none' }} />
          </IconButton>
        </Box>

        <Collapse in={expanded}>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {Plugin ? (
              <Plugin serverId={server.id} isDarkMode={isDarkMode} authMode={server.auth_mode} />
            ) : null}
            {isAdmin && server.enabled ? (
              <McpVerifyButton serverId={server.id} onVerify={onVerify} />
            ) : null}
            <Typography variant="caption" sx={{ color: muted }}>
              Runtime toggle — в чате: Инструменты → MCP. Здесь только admin: verify и metadata.
            </Typography>
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}
