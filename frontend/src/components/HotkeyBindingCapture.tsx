import React, { useEffect, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import {
  DEFAULT_HOTKEY_BINDINGS,
  HOTKEY_ACTIONS,
  type HotkeyActionId,
  type HotkeyBinding,
  bindingFromKeyboardEvent,
  findHotkeyConflict,
  formatHotkeyBinding,
} from '../constants/hotkeys';

interface HotkeyBindingCaptureProps {
  actionId: HotkeyActionId;
  binding: HotkeyBinding;
  allBindings: Record<HotkeyActionId, HotkeyBinding>;
  onChange: (binding: HotkeyBinding) => void;
  onReset: () => void;
  isDarkMode: boolean;
  isActive: boolean;
  enabled: boolean;
  onActivate: () => void;
  onDeactivate: () => void;
}

export default function HotkeyBindingCapture({
  actionId,
  binding,
  allBindings,
  onChange,
  onReset,
  isDarkMode,
  isActive,
  enabled,
  onActivate,
  onDeactivate,
}: HotkeyBindingCaptureProps) {
  const [conflictLabel, setConflictLabel] = useState<string | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isActive) return;

    const onKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (e.key === 'Escape') {
        onDeactivate();
        return;
      }

      if (e.key === 'Backspace' || e.key === 'Delete') {
        onReset();
        onDeactivate();
        return;
      }

      const next = bindingFromKeyboardEvent(e);
      if (!next) return;

      const conflictId = findHotkeyConflict(actionId, next, allBindings);
      if (conflictId) {
        const conflictAction = HOTKEY_ACTIONS.find((a) => a.id === conflictId);
        setConflictLabel(conflictAction?.label ?? 'другое действие');
        window.setTimeout(() => setConflictLabel(null), 2000);
        return;
      }

      onChange(next);
      onDeactivate();
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [isActive, actionId, allBindings, onChange, onReset, onDeactivate]);

  useEffect(() => {
    if (isActive) {
      buttonRef.current?.focus();
    }
  }, [isActive]);

  const displayText = isActive
    ? 'Нажмите клавиши…'
    : conflictLabel
      ? `Занято: ${conflictLabel}`
      : formatHotkeyBinding(binding);

  return (
    <Box
      component="button"
      type="button"
      ref={buttonRef}
      disabled={!enabled && !isActive}
      onClick={() => {
        if (!isActive && enabled) onActivate();
      }}
      title={
        isActive
          ? 'Esc — отмена, Backspace — сброс к умолчанию'
          : enabled
            ? 'Нажмите, чтобы задать сочетание клавиш'
            : 'Включите переключатель слева'
      }
      sx={{
        border: 'none',
        p: 0,
        m: 0,
        minWidth: 0,
        cursor: enabled || isActive ? 'pointer' : 'default',
        background: 'transparent',
        textAlign: 'right',
        flexShrink: 0,
        maxWidth: '46%',
        '&:disabled': { cursor: 'default' },
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: isDarkMode ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.25)',
          outlineOffset: 2,
          borderRadius: 0.5,
        },
      }}
    >
      <Typography
        component="span"
        sx={{
          color: conflictLabel
            ? isDarkMode
              ? '#f0ad4e'
              : '#b45309'
            : isActive
              ? isDarkMode
                ? '#ffffff'
                : '#1a1a1a'
              : isDarkMode
                ? 'rgba(255,255,255,0.55)'
                : 'rgba(0,0,0,0.55)',
          fontSize: '0.875rem',
          fontWeight: 400,
          fontStyle: isActive ? 'italic' : 'normal',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: 'block',
          opacity: enabled ? 1 : 0.45,
        }}
      >
        {displayText}
      </Typography>
    </Box>
  );
}

export function getDefaultHotkeyBinding(actionId: HotkeyActionId): HotkeyBinding {
  return DEFAULT_HOTKEY_BINDINGS[actionId];
}
