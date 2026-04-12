import React, { useMemo } from 'react';
import { Box, Tooltip } from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';
import { MenuBook as MenuBookIcon, SmartToyOutlined as AgentStatusIcon } from '@mui/icons-material';

export interface ChatInputStatusClusterProps {
  isDarkMode: boolean;
  libraryActive: boolean;
  onLibraryToggle?: () => void;
  /** Хотя один тумблер стандартного агента в «Инструменты → Агенты» включён */
  standardAgentsActive: boolean;
  /** Выбран пользовательский агент (Мои агенты) */
  myAgentName: string | null;
}

/**
 * Индикаторы у поля ввода: библиотека (клик — выкл), агент (стандартный и/или «мой»).
 * Оба активны — одна «пилюля» с вертикальным разделителем.
 */
export default function ChatInputStatusCluster({
  isDarkMode,
  libraryActive,
  onLibraryToggle,
  standardAgentsActive,
  myAgentName,
}: ChatInputStatusClusterProps) {
  const theme = useTheme();
  const agentActive = standardAgentsActive || Boolean(myAgentName);

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
    return parts.join(' ');
  }, [libraryActive, standardAgentsActive, myAgentName]);

  if (!libraryActive && !agentActive) return null;

  const borderC = alpha(theme.palette.primary.main, 0.4);
  const bg = alpha(theme.palette.primary.main, 0.12);
  const dividerColor = isDarkMode ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.18)';

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
        {libraryActive ? (
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
              m: 0,
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

        {libraryActive && agentActive ? (
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

        {agentActive ? (
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
      </Box>
    </Tooltip>
  );
}
