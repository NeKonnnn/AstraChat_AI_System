import React, { useEffect, useState } from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { fetchAtlassianConfig } from '../api';
import type { ServerPluginProps } from '../types';

export default function AtlassianServerDetails({ serverId, isDarkMode, compact }: ServerPluginProps) {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const muted = isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)';

  useEffect(() => {
    if (serverId !== 'atlassian') return;
    let cancelled = false;
    void (async () => {
      const cfg = await fetchAtlassianConfig();
      if (!cancelled) setConfig(cfg);
    })();
    return () => {
      cancelled = true;
    };
  }, [serverId]);

  if (serverId !== 'atlassian') return null;

  const toolsets = (config?.toolsets as Record<string, boolean> | undefined) || {};

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: compact ? 0.5 : 1 }}>
      <Typography variant="body2" sx={{ color: muted, fontSize: compact ? '0.72rem' : '0.82rem' }}>
        Jira / Confluence через MCP Pod (service account или per-user PAT — фаза 2).
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
        {toolsets.jira !== false ? <Chip label="Jira" size="small" color="primary" variant="outlined" /> : null}
        {toolsets.confluence !== false ? (
          <Chip label="Confluence" size="small" color="primary" variant="outlined" />
        ) : null}
        {config?.read_only ? <Chip label="Read-only" size="small" /> : null}
      </Box>
    </Box>
  );
}
