import React, { useMemo, useState } from 'react';
import {
  Box,
  Dialog,
  IconButton,
  Switch,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import {
  HOTKEY_ACTIONS,
  HOTKEY_CATEGORY_LABELS,
  HOTKEY_CATEGORY_ORDER,
  type HotkeyActionId,
  type HotkeyCategoryId,
} from '../constants/hotkeys';
import { useHotkeyBindings } from '../hooks/useHotkeyBindings';
import HotkeyBindingCapture from './HotkeyBindingCapture';

interface HotkeysSettingsDialogProps {
  open: boolean;
  onClose: () => void;
  isDarkMode: boolean;
}

const shortcutSwitchSx = (isDarkMode: boolean) => ({
  width: 36,
  height: 20,
  p: 0,
  mr: 1.5,
  flexShrink: 0,
  '& .MuiSwitch-switchBase': {
    p: 0.25,
    '&.Mui-checked': {
      transform: 'translateX(16px)',
    },
  },
  '& .MuiSwitch-thumb': {
    width: 16,
    height: 16,
    boxShadow: 'none',
    backgroundColor: '#ffffff',
  },
  '& .MuiSwitch-track': {
    borderRadius: 10,
    opacity: 1,
    backgroundColor: isDarkMode ? '#1a1a1a' : '#c8c8c8',
  },
  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
    opacity: 1,
    backgroundColor: isDarkMode ? '#1a1a1a' : '#1a1a1a',
  },
});

export default function HotkeysSettingsDialog({ open, onClose, isDarkMode }: HotkeysSettingsDialogProps) {
  const { bindings, setBinding, resetBinding, resetAll, setEnabled, isEnabled } = useHotkeyBindings();
  const [recordingHotkeyId, setRecordingHotkeyId] = useState<HotkeyActionId | null>(null);

  const groupedActions = useMemo(() => {
    const groups: Record<HotkeyCategoryId, typeof HOTKEY_ACTIONS> = {
      editor: [],
      application: [],
    };
    for (const action of HOTKEY_ACTIONS) {
      groups[action.category].push(action);
    }
    return groups;
  }, []);

  const handleClose = () => {
    setRecordingHotkeyId(null);
    onClose();
  };

  const rowBg = isDarkMode ? '#2b2b2b' : '#f0f0f0';
  const modalBg = isDarkMode ? '#1a1a1a' : '#ffffff';
  const sectionColor = isDarkMode ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)';
  const labelColor = isDarkMode ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.9)';

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: modalBg,
          color: isDarkMode ? '#ffffff' : '#1a1a1a',
          borderRadius: '16px',
          overflow: 'hidden',
        },
      }}
    >
      <Box
        sx={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: 2,
          py: 2,
        }}
      >
        <Typography
          component="h2"
          sx={{
            fontSize: '1.125rem',
            fontWeight: 600,
            color: isDarkMode ? '#ffffff' : '#1a1a1a',
          }}
        >
          Сочетания клавиш
        </Typography>
        <IconButton
          onClick={handleClose}
          size="small"
          sx={{
            position: 'absolute',
            right: 12,
            top: '50%',
            transform: 'translateY(-50%)',
            color: isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)',
            '&:hover': {
              backgroundColor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
            },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <Box sx={{ px: 2, pb: 2.5, pt: 0 }}>
        {HOTKEY_CATEGORY_ORDER.map((categoryId) => {
          const actions = groupedActions[categoryId];
          if (actions.length === 0) return null;

          return (
            <Box key={categoryId} sx={{ mb: 2.5 }}>
              <Typography
                sx={{
                  fontSize: '0.8125rem',
                  fontWeight: 500,
                  color: sectionColor,
                  mb: 1,
                  px: 0.25,
                }}
              >
                {HOTKEY_CATEGORY_LABELS[categoryId]}
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                {actions.map((action) => {
                  const enabled = isEnabled(action.id);
                  const isRecording = recordingHotkeyId === action.id;

                  return (
                    <Box
                      key={action.id}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        minHeight: 44,
                        px: 1.25,
                        py: 0.75,
                        borderRadius: '10px',
                        backgroundColor: rowBg,
                        boxShadow: isRecording
                          ? isDarkMode
                            ? 'inset 0 0 0 1px rgba(255,255,255,0.22)'
                            : 'inset 0 0 0 1px rgba(0,0,0,0.18)'
                          : 'none',
                      }}
                    >
                      <Switch
                        checked={enabled}
                        onChange={(_, checked) => setEnabled(action.id, checked)}
                        sx={shortcutSwitchSx(isDarkMode)}
                        inputProps={{ 'aria-label': `Включить: ${action.label}` }}
                      />

                      <Typography
                        sx={{
                          flex: 1,
                          minWidth: 0,
                          fontSize: '0.9375rem',
                          fontWeight: 400,
                          color: labelColor,
                          opacity: enabled ? 1 : 0.55,
                          pr: 1.5,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {action.label}
                      </Typography>

                      <HotkeyBindingCapture
                        actionId={action.id}
                        binding={bindings[action.id]}
                        allBindings={bindings}
                        onChange={(binding) => setBinding(action.id, binding)}
                        onReset={() => resetBinding(action.id)}
                        isDarkMode={isDarkMode}
                        enabled={enabled}
                        isActive={isRecording}
                        onActivate={() => setRecordingHotkeyId(action.id)}
                        onDeactivate={() => setRecordingHotkeyId(null)}
                      />
                    </Box>
                  );
                })}
              </Box>
            </Box>
          );
        })}

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
          <Box
            component="button"
            type="button"
            onClick={() => {
              resetAll();
              setRecordingHotkeyId(null);
            }}
            sx={{
              border: isDarkMode ? 'none' : '1px solid rgba(0,0,0,0.1)',
              cursor: 'pointer',
              borderRadius: '999px',
              px: 2.25,
              py: 1,
              fontSize: '0.875rem',
              fontWeight: 500,
              fontFamily: 'inherit',
              color: '#1a1a1a',
              backgroundColor: '#ffffff',
              transition: 'background-color 0.15s ease, opacity 0.15s ease',
              '&:hover': {
                backgroundColor: isDarkMode ? 'rgba(255,255,255,0.9)' : '#f5f5f5',
              },
            }}
          >
            Восстановить значения по умолчанию
          </Box>
        </Box>
      </Box>
    </Dialog>
  );
}
