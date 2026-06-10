import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import { Image as ImageIcon } from '@mui/icons-material';
import { getApiUrl } from '../../config/api';
import { useAppActions } from '../../contexts/AppContext';
import { MODEL_SETTINGS_CARD_SX, MODEL_SETTINGS_SECTION_TITLE_SX } from '../../constants/modelSettingsStyles';

type StatusPayload = {
  enabled: boolean;
  configured: boolean;
  comfyui_reachable?: boolean | null;
  comfyui_error?: string | null;
  workflow_resolved?: string | null;
  has_node_map: boolean;
  available_checkpoints?: string[];
};

export default function ImageGenerationSettingsSection() {
  const { showNotification } = useAppActions();
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [prompt, setPrompt] = useState('');
  const [width, setWidth] = useState('');
  const [height, setHeight] = useState('');
  const [steps, setSteps] = useState('');
  const [busy, setBusy] = useState(false);
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const r = await fetch(getApiUrl('/api/image-generation/status'));
      if (!r.ok) throw new Error(String(r.status));
      const data = (await r.json()) as StatusPayload;
      setStatus(data);
    } catch {
      setStatus(null);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const handleGenerate = async () => {
    const p = prompt.trim();
    if (!p) {
      showNotification('warning', 'Введите промпт');
      return;
    }
    setBusy(true);
    setPreviewSrc(null);
    try {
      const body: Record<string, unknown> = { prompt: p };
      const w = parseInt(width, 10);
      const h = parseInt(height, 10);
      const s = parseInt(steps, 10);
      if (!Number.isNaN(w)) body.width = w;
      if (!Number.isNaN(h)) body.height = h;
      if (!Number.isNaN(s)) body.steps = s;

      const r = await fetch(getApiUrl('/api/image-generation/generate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detail = typeof data?.detail === 'string' ? data.detail : JSON.stringify(data?.detail || data);
        throw new Error(detail || `HTTP ${r.status}`);
      }
      const imgs = Array.isArray(data?.images) ? data.images : [];
      const uri = imgs[0]?.data_uri as string | undefined;
      if (uri) {
        setPreviewSrc(uri);
        showNotification('success', 'Изображение готово');
      } else {
        showNotification('warning', 'Ответ без изображений');
      }
    } catch (e) {
      showNotification('error', e instanceof Error ? e.message : 'Ошибка генерации');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card sx={MODEL_SETTINGS_CARD_SX}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={MODEL_SETTINGS_SECTION_TITLE_SX}>
          <ImageIcon color="primary" sx={{ mr: 0.75, verticalAlign: 'middle' }} />
          Генерация изображений (ComfyUI)
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Движок — отдельный ComfyUI: бэкенд шлёт workflow на <code>/prompt</code>.
          В чате напишите, например: <strong>нарисуй кота</strong> или <code>/image закат над морем</code>.
          Положите checkpoint SD1.5 в <code>models/comfyui/checkpoints/</code> (имя файла — в workflow JSON).
        </Typography>

        {loadingStatus ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={20} />
            <Typography variant="body2">Проверка конфигурации…</Typography>
          </Box>
        ) : !status ? (
          <Alert severity="error">Не удалось загрузить статус</Alert>
        ) : (
          <>
            {!status.enabled && (
              <Alert severity="info" sx={{ mb: 1 }}>
                Выключено: в <code>config.yml</code> задайте <code>image_generation.enabled: true</code> или{' '}
                <code>IMAGE_GEN_ENABLED=1</code>.
              </Alert>
            )}
            {status.enabled && (!status.configured || !status.has_node_map) && (
              <Alert severity="warning" sx={{ mb: 1 }}>
                Заполните <code>image_generation.comfyui_base_url</code>, сохраните workflow API JSON в файл из{' '}
                <code>workflow_path</code> и опишите <code>node_map</code> (см. комментарии в config.yml).
              </Alert>
            )}
            {status.comfyui_reachable === false && (
              <Alert severity="error" sx={{ mb: 1 }}>
                ComfyUI недоступен по URL: {status.comfyui_error || 'нет ответа'}. Запустите ComfyUI с{' '}
                <code>--listen</code>.
              </Alert>
            )}
            {status.comfyui_reachable === true && (
              <Alert severity="success" sx={{ mb: 1 }}>
                ComfyUI отвечает по сети
                {Array.isArray(status.available_checkpoints) && status.available_checkpoints.length > 0
                  ? ` — checkpoint: ${status.available_checkpoints.join(', ')}`
                  : ' — checkpoint-модели не найдены (положите .safetensors в models/comfyui/checkpoints/)'}
              </Alert>
            )}
            {status.workflow_resolved && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                Workflow: {status.workflow_resolved}
              </Typography>
            )}
          </>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 560 }}>
          <TextField
            label="Промпт"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={busy}
            multiline
            minRows={2}
          />
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <TextField
              label="Ширина (опц.)"
              value={width}
              onChange={(e) => setWidth(e.target.value)}
              disabled={busy}
              type="number"
              sx={{ width: 140 }}
            />
            <TextField
              label="Высота (опц.)"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              disabled={busy}
              type="number"
              sx={{ width: 140 }}
            />
            <TextField
              label="Шаги (опц.)"
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
              disabled={busy}
              type="number"
              sx={{ width: 140 }}
            />
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button variant="contained" onClick={() => void handleGenerate()} disabled={busy}>
              {busy ? (
                <>
                  <CircularProgress size={18} sx={{ mr: 1 }} color="inherit" />
                  Генерация…
                </>
              ) : (
                'Сгенерировать'
              )}
            </Button>
            <Button variant="outlined" onClick={() => void loadStatus()} disabled={busy}>
              Обновить статус
            </Button>
          </Box>
        </Box>

        {previewSrc && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="subtitle2" gutterBottom>
              Результат
            </Typography>
            <Box
              component="img"
              src={previewSrc}
              alt="Сгенерированное изображение"
              sx={{ maxWidth: '100%', borderRadius: 1, border: 1, borderColor: 'divider' }}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
