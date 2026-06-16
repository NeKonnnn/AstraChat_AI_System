import { useCallback, useEffect, useState } from 'react';
import {
  ASTRA_HOTKEYS_CHANGED,
  DEFAULT_HOTKEY_BINDINGS,
  type HotkeyActionId,
  type HotkeyBinding,
  formatHotkeyBinding,
  getDisabledHotkeys,
  getHotkeyBindings,
  isHotkeyEnabled,
  resetAllHotkeyBindings,
  resetHotkeyBinding,
  saveHotkeyBinding,
  setHotkeyEnabled,
} from '../constants/hotkeys';

export function useHotkeyBindings() {
  const [bindings, setBindings] = useState(() => getHotkeyBindings());
  const [disabled, setDisabled] = useState(() => getDisabledHotkeys());

  useEffect(() => {
    const onChange = () => {
      setBindings(getHotkeyBindings());
      setDisabled(getDisabledHotkeys());
    };
    window.addEventListener(ASTRA_HOTKEYS_CHANGED, onChange);
    return () => window.removeEventListener(ASTRA_HOTKEYS_CHANGED, onChange);
  }, []);

  const setBinding = useCallback((actionId: HotkeyActionId, binding: HotkeyBinding) => {
    saveHotkeyBinding(actionId, binding);
  }, []);

  const resetBinding = useCallback((actionId: HotkeyActionId) => {
    resetHotkeyBinding(actionId);
  }, []);

  const resetAll = useCallback(() => {
    resetAllHotkeyBindings();
  }, []);

  const setEnabled = useCallback((actionId: HotkeyActionId, enabled: boolean) => {
    setHotkeyEnabled(actionId, enabled);
  }, []);

  const isEnabled = useCallback((actionId: HotkeyActionId) => isHotkeyEnabled(actionId), [disabled]);

  const format = useCallback((binding: HotkeyBinding) => formatHotkeyBinding(binding), []);

  const isDefault = useCallback(
    (actionId: HotkeyActionId) =>
      bindings[actionId] &&
      bindings[actionId].code === DEFAULT_HOTKEY_BINDINGS[actionId].code &&
      !!bindings[actionId].mod === !!DEFAULT_HOTKEY_BINDINGS[actionId].mod &&
      !!bindings[actionId].shift === !!DEFAULT_HOTKEY_BINDINGS[actionId].shift &&
      !!bindings[actionId].alt === !!DEFAULT_HOTKEY_BINDINGS[actionId].alt,
    [bindings],
  );

  return { bindings, disabled, setBinding, resetBinding, resetAll, setEnabled, isEnabled, format, isDefault };
}
