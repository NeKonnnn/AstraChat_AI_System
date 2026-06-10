import React from 'react';
import { Alert, Typography } from '@mui/material';
import AtlassianCredentialsForm from '../plugins/AtlassianCredentialsForm';

interface McpCredentialsSectionProps {
  serverId: string;
  authMode?: string;
  isDarkMode: boolean;
  compact?: boolean;
}

/** Generic credentials UI (F-M5): plugin per server_id. */
export default function McpCredentialsSection({
  serverId,
  authMode,
  isDarkMode,
  compact,
}: McpCredentialsSectionProps) {
  const mode = (authMode || 'service_account').toLowerCase();

  if (mode !== 'per_user') {
    return (
      <Alert severity="info" sx={{ fontSize: compact ? '0.75rem' : undefined }}>
        Режим <strong>{mode}</strong>: учётные данные задаются в Pod/Secret сервера (service account).
        Per-user PAT — при <code>auth_mode: per_user</code> в config.
      </Alert>
    );
  }

  if (serverId === 'atlassian') {
    return <AtlassianCredentialsForm isDarkMode={isDarkMode} compact={compact} />;
  }

  return (
    <Typography variant="body2" color="text.secondary">
      Per-user credentials для «{serverId}»: используйте{' '}
      <code>PUT /api/mcp/servers/{serverId}/credentials</code> (UI plugin не зарегистрирован).
    </Typography>
  );
}
