import React, { useState } from 'react';
import {
  Box,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
} from '@mui/material';
import {
  MoreHoriz as MoreHorizIcon,
  Edit as EditIcon,
  VolumeUp as VolumeUpIcon,
} from '@mui/icons-material';
import type { SxProps, Theme } from '@mui/material/styles';
import SplitArrowIcon from './SplitArrowIcon';
import { getDropdownPopoverPaperSx } from '../constants/menuStyles';

export interface MessageMoreActionsMenuProps {
  isDarkMode: boolean;
  compact?: boolean;
  disabled?: boolean;
  isSpeaking?: boolean;
  branchDisabled?: boolean;
  showBranch?: boolean;
  onEdit: () => void;
  onReadAloud: () => void;
  onBranch?: () => void;
  iconSx?: SxProps<Theme>;
}

export default function MessageMoreActionsMenu({
  isDarkMode,
  compact = false,
  disabled = false,
  isSpeaking = false,
  branchDisabled = false,
  showBranch = false,
  onEdit,
  onReadAloud,
  onBranch,
  iconSx,
}: MessageMoreActionsMenuProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const defaultIconSx: SxProps<Theme> = {
    opacity: 0.7,
    p: 0.5,
    borderRadius: '6px',
    minWidth: compact ? '26px' : '28px',
    width: compact ? '26px' : '28px',
    height: compact ? '26px' : '28px',
    '&:hover:not(:disabled)': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
    '&:disabled': { opacity: 0.4 },
    '& .MuiSvgIcon-root': {
      fontSize: compact ? '16px !important' : '18px !important',
      width: compact ? '16px !important' : '18px !important',
      height: compact ? '16px !important' : '18px !important',
    },
  };

  const close = () => setAnchorEl(null);

  const handleEdit = () => {
    close();
    onEdit();
  };

  const handleReadAloud = () => {
    close();
    onReadAloud();
  };

  const handleBranch = () => {
    close();
    onBranch?.();
  };

  const menuTextColor = isDarkMode ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.87)';
  const menuIconColor = isDarkMode ? 'rgba(255,255,255,0.75)' : 'rgba(0,0,0,0.6)';

  return (
    <>
      <Tooltip title="Больше действий">
        <span>
          <IconButton
            size="small"
            disabled={disabled}
            onClick={(e) => setAnchorEl(e.currentTarget)}
            className="message-more-actions-button"
            data-theme={isDarkMode ? 'dark' : 'light'}
            sx={iconSx ?? defaultIconSx}
            aria-label="Больше действий"
          >
            <MoreHorizIcon />
          </IconButton>
        </span>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{
          paper: {
            sx: {
              ...getDropdownPopoverPaperSx(null, isDarkMode),
              mt: 0.75,
              minWidth: 220,
            },
          },
        }}
      >
        <MenuItem onClick={handleReadAloud} disabled={isSpeaking}>
          <ListItemIcon sx={{ minWidth: 36, color: menuIconColor }}>
            <VolumeUpIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary="Прочесть вслух"
            primaryTypographyProps={{ fontSize: '0.875rem', color: menuTextColor }}
          />
        </MenuItem>
        <MenuItem onClick={handleEdit}>
          <ListItemIcon sx={{ minWidth: 36, color: menuIconColor }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary="Редактировать"
            primaryTypographyProps={{ fontSize: '0.875rem', color: menuTextColor }}
          />
        </MenuItem>
        {showBranch ? (
          <MenuItem onClick={handleBranch} disabled={branchDisabled}>
            <ListItemIcon sx={{ minWidth: 36, color: menuIconColor }}>
              <Box component="span" sx={{ display: 'inline-flex', color: 'inherit' }}>
                <SplitArrowIcon sx={{ fontSize: 18 }} />
              </Box>
            </ListItemIcon>
            <ListItemText
              primary="Ветка в новом чате"
              primaryTypographyProps={{ fontSize: '0.875rem', color: menuTextColor }}
            />
          </MenuItem>
        ) : null}
      </Menu>
    </>
  );
}
