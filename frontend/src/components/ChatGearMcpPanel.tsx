import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  CircularProgress,
  FormControlLabel,
  Switch,
  Typography,
  Link,
  Chip,
} from '@mui/material';
import {
  HubOutlined as HubIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import {
  MENU_ACTION_TEXT_SIZE,
  CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX,
  CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX,
} from '../constants/menuStyles';
import { fetchMcpServers, fetchMcpStatus } from '../mcp/api';
import { getMcpServerPlugin } from '../mcp/plugins/registry';
import { getMcpToolIdsForChat, isMcpServerEnabledForChat } from '../mcp/selectionStorage';
import { useChatMcpSelection } from '../mcp/hooks/useChatMcpSelection';
import type { McpServerConfigPublic, McpServerStatus } from '../mcp/types';
import { ASTRA_OPEN_SETTINGS, ASTRA_OPEN_SETTINGS_SECTION } from '../constants/hotkeys';

interface ChatGearMcpPanelProps {
  isDarkMode: boolean;
  chatId: string | null | undefined;
}

export default function ChatGearMcpPanel({ isDarkMode, chatId }: ChatGearMcpPanelProps) {
  const { toggleServer } = useChatMcpSelection(chatId);
  const [servers, setServers] = useState<McpServerConfigPublic[]>([]);
  const [statusMap, setStatusMap] = useState<Map<string, McpServerStatus>>(new Map());
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const muted = isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)';
  const text = isDarkMode ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.9)';
  const border = isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  const placeholderColor = isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.35)';

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [srv, st] = await Promise.all([fetchMcpServers(), fetchMcpStatus()]);
      setServers(srv.filter((s) => s.enabled));
      const map = new Map<string, McpServerStatus>();
      for (const s of st.servers || []) {
        map.set(s.id, s);
      }
      setStatusMap(map);
    } catch {
      setServers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return servers;
    return servers.filter((s) => [s.id, s.display_name].join(' ').toLowerCase().includes(q));
  }, [servers, search]);

  const openMcpSettings = () => {
    window.dispatchEvent(new CustomEvent(ASTRA_OPEN_SETTINGS));
    window.dispatchEvent(new CustomEvent(ASTRA_OPEN_SETTINGS_SECTION, { detail: { section: 'mcp' } }));
  };

  if (!chatId) {
    return (
      <Box sx={{ p: 1.5, maxWidth: 320 }}>
        <Typography variant="body2" sx={{ color: muted, fontSize: MENU_ACTION_TEXT_SIZE }}>
          Выберите или создайте чат, чтобы включить MCP-серверы для этого диалога.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1, height: '100%', overflow: 'hidden' }}>
      <Box sx={{ flexShrink: 0, px: 1.5, py: 0.9, display: 'flex', alignItems: 'center', gap: 1, borderBottom: `1px solid ${border}` }}>
        <SearchIcon sx={{ color: muted, fontSize: 16 }} />
        <Box
          component="input"
          placeholder="Поиск MCP..."
          value={search}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
          sx={{
            flex: 1,
            bgcolor: 'transparent',
            border: 'none',
            outline: 'none',
            color: text,
            fontSize: MENU_ACTION_TEXT_SIZE,
            '&::placeholder': { color: placeholderColor },
          }}
        />
      </Box>

      <Box
        sx={{
          height: `${CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX}px`,
          maxHeight: `${CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX}px`,
          overflowY: 'auto',
          px: 0.75,
          py: 1,
          ...CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX,
        }}
      >
        {loading && servers.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={28} />
          </Box>
        ) : filtered.length === 0 ? (
          <Typography variant="body2" sx={{ color: muted, fontSize: MENU_ACTION_TEXT_SIZE, px: 0.5 }}>
            Нет доступных MCP-серверов.
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {filtered.map((srv) => {
              const st = statusMap.get(srv.id);
              const enabled = isMcpServerEnabledForChat(chatId, srv.id);
              const Plugin = getMcpServerPlugin(srv.id);
              const expanded = expandedId === srv.id;
              return (
                <Box
                  key={srv.id}
                  sx={{
                    border: `1px solid ${border}`,
                    borderRadius: 1,
                    overflow: 'hidden',
                    bgcolor: isDarkMode ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.02)',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, py: 0.65, px: 0.85 }}>
                    <HubIcon sx={{ fontSize: 20, color: enabled ? 'primary.main' : muted, flexShrink: 0 }} />
                    <Box
                      role="button"
                      tabIndex={0}
                      onClick={() => setExpandedId((p) => (p === srv.id ? null : srv.id))}
                      sx={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer' }}
                    >
                      <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, fontWeight: 600, color: text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {srv.display_name || srv.id}
                      </Typography>
                      {st?.connected === false ? (
                        <Chip label="offline" size="small" color="error" variant="outlined" sx={{ height: 20, fontSize: '0.65rem' }} />
                      ) : st?.connected ? (
                        <Chip label="ok" size="small" color="success" variant="outlined" sx={{ height: 20, fontSize: '0.65rem' }} />
                      ) : null}
                      <ExpandMoreIcon sx={{ fontSize: 20, color: muted, transform: expanded ? 'rotate(180deg)' : 'none' }} />
                    </Box>
                    <FormControlLabel
                      onClick={(e) => e.stopPropagation()}
                      control={
                        <Switch
                          size="small"
                          checked={enabled}
                          onChange={(_e, checked) => toggleServer(srv.id, checked)}
                          color="primary"
                        />
                      }
                      label=""
                      sx={{ m: 0 }}
                    />
                  </Box>
                  {expanded && Plugin ? (
                    <Box sx={{ px: 1, pb: 1, pt: 0, borderTop: `1px solid ${border}` }}>
                      <Plugin serverId={srv.id} isDarkMode={isDarkMode} compact />
                    </Box>
                  ) : null}
                </Box>
              );
            })}
          </Box>
        )}
      </Box>

      <Box sx={{ flexShrink: 0, px: 1.5, py: 1, borderTop: `1px solid ${border}` }}>
        <Typography variant="caption" sx={{ color: muted, display: 'block', mb: 0.5 }}>
          tool_ids:{' '}
          {(() => {
            const ids = getMcpToolIdsForChat(chatId);
            return ids.length ? ids.join(', ') : '—';
          })()}
        </Typography>
        <Link component="button" type="button" variant="caption" onClick={openMcpSettings}>
          Подробные настройки MCP →
        </Link>
      </Box>
    </Box>
  );
}
