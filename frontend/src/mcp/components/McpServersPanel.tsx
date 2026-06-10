import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import { useMcpPlatform } from '../hooks/useMcpPlatform';
import type { McpServerStatus } from '../types';
import McpServerCard from './McpServerCard';
import { McpToolsSection } from './McpToolsTable';
import { useAuth } from '../../contexts/AuthContext';

interface McpServersPanelProps {
  isDarkMode: boolean;
}

export default function McpServersPanel({ isDarkMode }: McpServersPanelProps) {
  const { user } = useAuth();
  const { servers, status, tools, loading, error, refresh, loadTools, verifyServer } = useMcpPlatform();
  const [filterServerId, setFilterServerId] = useState<string>('');

  const statusById = useMemo(() => {
    const map = new Map<string, McpServerStatus>();
    for (const s of status?.servers || []) {
      map.set(s.id, s);
    }
    return map;
  }, [status]);

  useEffect(() => {
    void loadTools(filterServerId || undefined);
  }, [filterServerId, loadTools]);

  if (loading && servers.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      {status ? (
        <Typography variant="body1" sx={{ mb: 2 }}>
          MCP: {status.servers_connected ?? 0} / {status.servers_total ?? status.total_servers ?? 0} серверов
          подключено · {status.tools_total ?? status.tools ?? 0} инструментов
        </Typography>
      ) : null}

      {!status?.enabled ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          MCP-платформа отключена (MCP_ENABLED=false). Серверы из config не активны.
        </Alert>
      ) : null}

      {servers.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          Нет доступных MCP-серверов. Добавьте запись в mcp.servers[] на backend.
        </Typography>
      ) : (
        servers.map((srv) => (
          <McpServerCard
            key={srv.id}
            server={srv}
            runtimeStatus={statusById.get(srv.id) || null}
            isDarkMode={isDarkMode}
            isAdmin={Boolean(user?.is_admin)}
            onVerify={verifyServer}
            accessDenied={false}
          />
        ))
      )}

      <Box sx={{ mt: 3 }}>
        <FormControl size="small" fullWidth sx={{ mb: 2, maxWidth: 320 }}>
          <InputLabel id="mcp-tools-filter">Фильтр tools по server</InputLabel>
          <Select
            labelId="mcp-tools-filter"
            label="Фильтр tools по server"
            value={filterServerId}
            onChange={(e) => setFilterServerId(e.target.value)}
          >
            <MenuItem value="">Все серверы</MenuItem>
            {servers.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.display_name || s.id}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <McpToolsSection tools={tools} filterServerId={filterServerId || null} isDarkMode={isDarkMode} />
      </Box>

      <Typography
        component="button"
        type="button"
        onClick={() => void refresh()}
        sx={{ mt: 2, border: 'none', bgcolor: 'transparent', color: 'primary.main', cursor: 'pointer' }}
      >
        Обновить статус
      </Typography>
    </Box>
  );
}
