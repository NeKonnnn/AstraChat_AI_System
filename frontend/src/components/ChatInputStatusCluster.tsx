import React, { useMemo } from 'react';
import { Box, Tooltip, Typography } from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';
import {
  MenuBook as MenuBookIcon,
  SmartToyOutlined as AgentStatusIcon,
  HubOutlined as HubIcon,
} from '@mui/icons-material';
import type { ActiveMcpServerIndicator } from '../mcp/hooks/useChatInputMcpIndicators';

export interface ChatInputStatusClusterProps {
  isDarkMode: boolean;
  libraryActive: boolean;
  onLibraryToggle?: () => void;
  /** Хотя один тумблер стандартного агента в «Инструменты → Агенты» включён */
  standardAgentsActive: boolean;
  /** Выбран пользовательский агент (Мои агенты) */
  myAgentName: string | null;
  /** Включённые MCP-серверы для текущего чата */
  activeMcpServers?: ActiveMcpServerIndicator[];
  onMcpClick?: () => void;
}

/**
 * Индикаторы у поля ввода: библиотека, агент, MCP.
 * Несколько активных — одна «пилюля» с вертикальными разделителями.
 */
export default function ChatInputStatusCluster({
  isDarkMode,
  libraryActive,
  onLibraryToggle,
  standardAgentsActive,
  myAgentName,
  activeMcpServers = [],
  onMcpClick,
}: ChatInputStatusClusterProps) {
  const theme = useTheme();
  const agentActive = standardAgentsActive || Boolean(myAgentName);
  const mcpActive = activeMcpServers.length > 0;

  const mcpLabel = useMemo(() => {
    if (activeMcpServers.length === 0) return '';
    if (activeMcpServers.length === 1) return activeMcpServers[0].display_name;
    return `${activeMcpServers.length} MCP`;
  }, [activeMcpServers]);

  const tooltipTitle = useMemo(() => {
    const parts: string[] = [];
    if (libraryActive) {
      parts.push('Библиотека в ответах включена. Нажмите на книгу, чтобы отключить.');
    }
    if (standardAgentsActive && myAgentName) {
      parts.push(`Стандартные агенты активны; выбран агент «${myAgentName}» (Мои агенты).`);
    } else if (standardAgentsActive) {
      parts.push('Включены стандартные агенты (Инструменты → Агенты).');
    } else if (myAgentName) {
      parts.push(`Активен агент «${myAgentName}» (Мои агенты).`);
    }
    if (mcpActive) {
      parts.push(
        `MCP: ${activeMcpServers.map((s) => s.display_name).join(', ')}. Инструменты → MCP.`,
      );
    }
    return parts.join(' ');
  }, [libraryActive, standardAgentsActive, myAgentName, mcpActive, activeMcpServers]);

  if (!libraryActive && !agentActive && !mcpActive) return null;

  const borderC = alpha(theme.palette.primary.main, 0.4);
  const bg = alpha(theme.palette.primary.main, 0.12);
  const dividerColor = isDarkMode ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)';

  const segments: Array<'library' | 'agent' | 'mcp'> = [];
  if (libraryActive) segments.push('library');
  if (agentActive) segments.push('agent');
  if (mcpActive) segments.push('mcp');

  return (
    <Tooltip title={tooltipTitle}>
      <Box
        sx={{
          display: 'inline-flex',
          flexDirection: 'row',
          alignItems: 'stretch',
          flexShrink: 0,
          height: 36,
          borderRadius: '18px',
          border: `1px solid ${borderC}`,
          bgcolor: bg,
          overflow: 'hidden',
        }}
      >
        {segments.map((seg, idx) => (
          <React.Fragment key={seg}>
            {idx > 0 ? (
              <Box
                aria-hidden
                sx={{
                  width: '1px',
                  flexShrink: 0,
                  alignSelf: 'stretch',
                  minHeight: 22,
                  my: '7px',
                  bgcolor: dividerColor,
                }}
              />
            ) : null}
            {seg === 'library' ? (
              <Box
                component="button"
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onLibraryToggle?.();
                }}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 36,
                  minWidth: 36,
                  height: 36,
                  p: 0,
                  border: 'none',
                  bgcolor: 'transparent',
                  cursor: onLibraryToggle ? 'pointer' : 'default',
                  color: 'primary.main',
                  '&:hover': onLibraryToggle ? { bgcolor: alpha(theme.palette.primary.main, 0.12) } : {},
                }}
              >
                <MenuBookIcon sx={{ fontSize: '1.15rem' }} />
              </Box>
            ) : null}
            {seg === 'agent' ? (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minWidth: 36,
                  height: 36,
                  px: libraryActive ? 0.5 : 0.75,
                  color: 'primary.main',
                }}
              >
                <AgentStatusIcon sx={{ fontSize: '1.15rem' }} />
              </Box>
            ) : null}
            {seg === 'mcp' ? (
              <Box
                component={onMcpClick ? 'button' : 'div'}
                type={onMcpClick ? 'button' : undefined}
                onClick={
                  onMcpClick
                    ? (e: React.MouseEvent) => {
                        e.stopPropagation();
                        e.preventDefault();
                        onMcpClick();
                      }
                    : undefined
                }
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 0.35,
                  minWidth: 36,
                  height: 36,
                  px: 0.75,
                  border: 'none',
                  bgcolor: 'transparent',
                  color: 'primary.main',
                  cursor: onMcpClick ? 'pointer' : 'default',
                  maxWidth: 140,
                }}
              >
                <HubIcon sx={{ fontSize: '1.15rem', flexShrink: 0 }} />
                {mcpLabel ? (
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 600,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      lineHeight: 1,
                    }}
                  >
                    {mcpLabel}
                  </Typography>
                ) : null}
              </Box>
            ) : null}
          </React.Fragment>
        ))}
      </Box>
    </Tooltip>
  );
}
