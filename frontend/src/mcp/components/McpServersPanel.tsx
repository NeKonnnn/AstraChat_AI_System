import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  FormControl,
  InputAdornment,
  InputLabel,
  OutlinedInput,
  Popover,
  Typography,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import type { SxProps, Theme } from '@mui/material/styles';
import { useMcpPlatform } from '../hooks/useMcpPlatform';
import type { McpServerStatus } from '../types';
import McpServerCard from './McpServerCard';
import { McpToolsSection } from './McpToolsTable';
import { useAuth } from '../../contexts/AuthContext';
import {
  DROPDOWN_CHEVRON_SX,
  DROPDOWN_ITEM_HOVER_BG_DARK,
  DROPDOWN_ITEM_HOVER_BG_LIGHT,
  getDropdownItemSx,
  getDropdownPopoverPaperSx,
  getFormFieldInputSx,
} from '../../constants/menuStyles';

interface McpServersPanelProps {
  isDarkMode: boolean;
}

export default function McpServersPanel({ isDarkMode }: McpServersPanelProps) {
  const { user } = useAuth();
  const { servers, status, tools, loading, error, refresh, loadTools, verifyServer } = useMcpPlatform();
  const [filterServerId, setFilterServerId] = useState<string>('');
  const [filterPopoverAnchor, setFilterPopoverAnchor] = useState<HTMLElement | null>(null);
  const filterOutlinedRef = useRef<HTMLDivElement>(null);

  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const formFieldInputSx = useMemo(() => getFormFieldInputSx(isDarkMode), [isDarkMode]);
  const filterFieldSx = useMemo(
    () =>
      [
        formFieldInputSx,
        {
          '& .MuiOutlinedInput-root': { cursor: 'pointer' },
          '& .MuiOutlinedInput-root.Mui-focused fieldset': {
            borderColor: isDarkMode ? 'rgba(255,255,255,0.23)' : 'rgba(0,0,0,0.23)',
            borderWidth: '1px',
          },
          '& .MuiOutlinedInput-root:hover fieldset': {
            borderColor: isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
          },
          '& .MuiOutlinedInput-root.Mui-focused:hover fieldset': {
            borderColor: isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
          },
          '& .MuiInputLabel-root.Mui-focused': {
            color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
          },
        },
      ] as SxProps<Theme>,
    [formFieldInputSx, isDarkMode],
  );

  const filterOptions = useMemo(
    () => [
      { id: '', label: 'Все серверы' },
      ...servers.map((s) => ({
        id: s.id,
        label: s.display_name || s.id,
      })),
    ],
    [servers],
  );

  const filterDisplayValue = useMemo(() => {
    if (!filterServerId) return '';
    return filterOptions.find((o) => o.id === filterServerId)?.label || filterServerId;
  }, [filterServerId, filterOptions]);

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
        <FormControl
          variant="outlined"
          fullWidth
          size="small"
          sx={[filterFieldSx, { mb: 2, maxWidth: 320 }] as SxProps<Theme>}
        >
          <InputLabel htmlFor="mcp-tools-filter">Фильтр tools по server</InputLabel>
          <OutlinedInput
            ref={filterOutlinedRef}
            id="mcp-tools-filter"
            label="Фильтр tools по server"
            value={filterDisplayValue}
            readOnly
            placeholder="Все серверы"
            onClick={() => setFilterPopoverAnchor(filterOutlinedRef.current)}
            endAdornment={
              <InputAdornment position="end">
                <ExpandMoreIcon
                  sx={{
                    ...DROPDOWN_CHEVRON_SX,
                    color: isDarkMode ? DROPDOWN_CHEVRON_SX.color : 'rgba(0,0,0,0.45)',
                    transform: filterPopoverAnchor ? 'rotate(180deg)' : 'none',
                  }}
                />
              </InputAdornment>
            }
          />
        </FormControl>
        <Popover
          open={Boolean(filterPopoverAnchor)}
          anchorEl={filterPopoverAnchor}
          onClose={() => setFilterPopoverAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          slotProps={{
            paper: { sx: getDropdownPopoverPaperSx(filterPopoverAnchor, isDarkMode) },
          }}
        >
          <Box sx={{ py: 0.5 }}>
            {filterOptions.map((option) => {
              const selected = filterServerId === option.id;
              return (
                <Box
                  key={option.id || '__all__'}
                  onClick={() => {
                    setFilterServerId(option.id);
                    setFilterPopoverAnchor(null);
                  }}
                  sx={{
                    ...dropdownItemSx,
                    color: selected
                      ? isDarkMode
                        ? 'white'
                        : 'rgba(0,0,0,0.87)'
                      : isDarkMode
                        ? 'rgba(255,255,255,0.9)'
                        : 'rgba(0,0,0,0.7)',
                    fontWeight: selected ? 600 : 400,
                    bgcolor: selected
                      ? isDarkMode
                        ? DROPDOWN_ITEM_HOVER_BG_DARK
                        : DROPDOWN_ITEM_HOVER_BG_LIGHT
                      : 'transparent',
                  }}
                >
                  {option.label}
                </Box>
              );
            })}
          </Box>
        </Popover>
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
