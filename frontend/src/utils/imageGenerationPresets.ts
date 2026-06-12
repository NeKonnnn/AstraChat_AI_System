export const IMAGE_GEN_PRESET_STORAGE_KEY = 'image_gen_preset_id';

export type ImageGenPreset = {
  id: string;
  label: string;
  description?: string;
  workflow_path?: string;
  checkpoint_name?: string;
  default_width?: number;
  default_height?: number;
  default_steps?: number;
  available?: boolean;
};

export type ImageGenPresetsPayload = {
  default_preset_id?: string;
  presets?: ImageGenPreset[];
  available_checkpoints?: string[];
};

export function readSelectedImageGenPresetId(): string | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(IMAGE_GEN_PRESET_STORAGE_KEY);
  return raw && raw.trim() ? raw.trim() : null;
}

export function writeSelectedImageGenPresetId(presetId: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(IMAGE_GEN_PRESET_STORAGE_KEY, presetId);
  window.dispatchEvent(new CustomEvent('astrachatImageGenPresetChanged', { detail: { presetId } }));
}

export function resolveImageGenPresetLabel(
  presets: ImageGenPreset[],
  presetId: string | null | undefined,
): string {
  if (!presetId) return '';
  const hit = presets.find((p) => p.id === presetId);
  return hit?.label || presetId;
}
