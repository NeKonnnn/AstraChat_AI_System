/**
 * Секция настроек «LLM-провайдеры» (read-only).
 *
 * Политика: API-ключи задаются **только** через ENV (см. backend/llm_providers/secrets.py).
 * UI показывает статус всех провайдеров, health, какая ENV-переменная ожидается,
 * выставлена ли она, и hint для PowerShell/bash. Редактировать провайдера из UI
 * нельзя — это сознательное решение из соображений безопасности.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Cloud as CloudIcon,
  CheckCircle as CheckCircleIcon,
  ErrorOutline as ErrorIcon,
  ContentCopy as CopyIcon,
  Refresh as RefreshIcon,
  Key as KeyIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { getApiUrl } from '../../config/api';
import { useAppActions } from '../../contexts/AppContext';

interface ProviderCapabilities {
  hot_swap: boolean;
  multi_loaded: boolean;
  streaming: boolean;
  vision: boolean;
}

interface ProviderHealth {
  healthy: boolean;
  error: string | null;
  loaded_models: string[];
}

interface ProviderSecretHint {
  env_name: string;
  required: boolean;
  powershell: string;
  bash: string;
}

interface ProviderDTO {
  id: string;
  kind: string;
  base_url: string;
  enabled: boolean;
  static_model?: string | null;
  capabilities: ProviderCapabilities;
  api_key_env: string | null;
  api_key_required: boolean;
  api_key_set: boolean;
  api_key_preview: string | null;
  secret_hint: ProviderSecretHint;
  health?: ProviderHealth;
}

interface ListResponse {
  default_provider_id: string | null;
  providers: ProviderDTO[];
}

const KIND_LABELS: Record<string, string> = {
  'llm-svc': 'llm-svc (dynamic load)',
  vllm: 'vLLM',
  ollama: 'Ollama',
  litellm: 'LiteLLM',
  'openai-compat': 'OpenAI-compatible',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
};

const KIND_COLORS: Record<string, string> = {
  'llm-svc': '#8e7cc3',
  vllm: '#3f6cd4',
  ollama: '#00a67e',
  litellm: '#1e88e5',
  'openai-compat': '#607d8b',
  openai: '#10a37f',
  openrouter: '#d97706',
  anthropic: '#c47a3d',
};


export default function LlmProvidersSection() {
  const { showNotification } = useAppActions();
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(getApiUrl('/api/llm-providers?include_health=true'));
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = (await resp.json()) as ListResponse;
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const copyToClipboard = useCallback(
    async (text: string, label: string) => {
      try {
        await navigator.clipboard.writeText(text);
        showNotification('success', `${label} скопировано в буфер обмена`);
      } catch {
        showNotification('warning', 'Не удалось скопировать в буфер обмена');
      }
    },
    [showNotification],
  );

  const providers = data?.providers ?? [];
  const defaultId = data?.default_provider_id ?? null;

  const summary = useMemo(() => {
    const total = providers.length;
    const healthy = providers.filter((p) => p.health?.healthy).length;
    const keysRequired = providers.filter((p) => p.api_key_required).length;
    const keysMissing = providers.filter((p) => p.api_key_required && !p.api_key_set).length;
    return { total, healthy, keysRequired, keysMissing };
  }, [providers]);

  return (
    <Card sx={{ mt: 3 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <CloudIcon color="primary" />
          <Typography variant="h6" sx={{ flex: 1 }}>
            LLM-провайдеры
          </Typography>
          <Tooltip title="Обновить список и health-статус">
            <span>
              <IconButton onClick={reload} disabled={loading} size="small">
                {loading ? <CircularProgress size={18} /> : <RefreshIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Список доступных LLM-бэкендов (read-only). Управление провайдерами и
          API-ключами производится на стороне сервера: конфигурация — в{' '}
          <code>backend/config/config.yml</code> (секция <code>llm_providers</code>),
          API-ключи — <strong>только</strong> через переменные окружения.
        </Typography>

        {/* Summary */}
        <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 2 }}>
          <Chip
            size="small"
            label={`Всего: ${summary.total}`}
            variant="outlined"
          />
          <Chip
            size="small"
            color={summary.healthy === summary.total && summary.total > 0 ? 'success' : 'default'}
            label={`Healthy: ${summary.healthy}/${summary.total}`}
            variant="outlined"
          />
          {summary.keysRequired > 0 ? (
            <Chip
              size="small"
              color={summary.keysMissing > 0 ? 'warning' : 'success'}
              label={
                summary.keysMissing > 0
                  ? `Ключи не заданы: ${summary.keysMissing}/${summary.keysRequired}`
                  : `API-ключи: OK (${summary.keysRequired})`
              }
              variant="outlined"
            />
          ) : null}
        </Stack>

        {error ? (
          <Box sx={{ color: 'error.main', display: 'flex', alignItems: 'center', gap: 1 }}>
            <ErrorIcon fontSize="small" />
            <Typography variant="body2">Ошибка загрузки: {error}</Typography>
          </Box>
        ) : null}

        {!loading && !error && providers.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Ни один провайдер не зарегистрирован.
          </Typography>
        ) : null}

        <Stack spacing={1.5}>
          {providers.map((p) => (
            <ProviderRow
              key={p.id}
              provider={p}
              isDefault={p.id === defaultId}
              onCopy={copyToClipboard}
            />
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}


interface ProviderRowProps {
  provider: ProviderDTO;
  isDefault: boolean;
  onCopy: (text: string, label: string) => void;
}

function ProviderRow({ provider, isDefault, onCopy }: ProviderRowProps) {
  const p = provider;
  const health = p.health;
  const kindLabel = KIND_LABELS[p.kind] ?? p.kind;
  const kindColor = KIND_COLORS[p.kind] ?? '#78909c';
  const keyMissing = p.api_key_required && !p.api_key_set;

  let statusIcon: React.ReactNode;
  let statusColor = 'text.secondary';
  if (health?.healthy) {
    statusIcon = <CheckCircleIcon fontSize="small" sx={{ color: 'success.main' }} />;
    statusColor = 'success.main';
  } else if (health) {
    statusIcon = <ErrorIcon fontSize="small" sx={{ color: 'error.main' }} />;
    statusColor = 'error.main';
  } else {
    statusIcon = <CircularProgress size={14} />;
  }

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1.5,
        p: 1.5,
        bgcolor: 'background.paper',
      }}
    >
      {/* header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        {statusIcon}
        <Typography variant="body1" sx={{ fontWeight: 600 }}>
          {p.id}
        </Typography>
        <Chip
          size="small"
          label={kindLabel}
          sx={{
            bgcolor: kindColor,
            color: '#fff',
            height: 22,
            '& .MuiChip-label': { px: 1, fontSize: '0.72rem', fontWeight: 600 },
          }}
        />
        {isDefault ? (
          <Chip size="small" label="default" variant="outlined" color="primary" sx={{ height: 22 }} />
        ) : null}
        {!p.enabled ? (
          <Chip size="small" label="disabled" variant="outlined" sx={{ height: 22 }} />
        ) : null}
        <Box sx={{ flex: 1 }} />
        {p.capabilities.hot_swap ? (
          <Chip size="small" label="hot-swap" variant="outlined" sx={{ height: 22 }} />
        ) : null}
        {p.capabilities.multi_loaded ? (
          <Chip size="small" label="multi" variant="outlined" sx={{ height: 22 }} />
        ) : null}
        {p.capabilities.vision ? (
          <Chip size="small" label="vision" variant="outlined" sx={{ height: 22 }} />
        ) : null}
      </Box>

      {/* base_url */}
      <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.75, gap: 1 }}>
        <Typography
          variant="body2"
          sx={{ fontFamily: 'monospace', fontSize: '0.82rem', color: 'text.secondary', wordBreak: 'break-all' }}
        >
          {p.base_url}
        </Typography>
      </Box>

      {/* health error */}
      {health && !health.healthy && health.error ? (
        <Typography variant="caption" sx={{ color: statusColor, display: 'block', mt: 0.5 }}>
          {health.error}
        </Typography>
      ) : null}
      {health?.loaded_models && health.loaded_models.length > 0 ? (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
          Загружены: {health.loaded_models.join(', ')}
        </Typography>
      ) : null}

      {/* API key section */}
      {p.api_key_env ? (
        <Box
          sx={{
            mt: 1,
            p: 1,
            borderRadius: 1,
            bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'),
            border: '1px dashed',
            borderColor: keyMissing ? 'warning.main' : 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            {keyMissing ? (
              <WarningIcon fontSize="small" sx={{ color: 'warning.main' }} />
            ) : (
              <KeyIcon fontSize="small" sx={{ color: p.api_key_set ? 'success.main' : 'text.secondary' }} />
            )}
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              API-ключ:
            </Typography>
            <Typography
              variant="body2"
              sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}
              color={p.api_key_set ? 'success.main' : keyMissing ? 'warning.main' : 'text.secondary'}
            >
              {p.api_key_set
                ? `задан (${p.api_key_preview ?? '***'})`
                : p.api_key_required
                  ? 'не задан (требуется)'
                  : 'не задан (опционально)'}
            </Typography>
            <Box sx={{ flex: 1 }} />
            <Chip
              size="small"
              variant="outlined"
              label={p.api_key_env}
              sx={{ fontFamily: 'monospace', height: 22 }}
            />
            <Tooltip title="Скопировать имя ENV-переменной">
              <IconButton size="small" onClick={() => onCopy(p.api_key_env!, 'Имя переменной')}>
                <CopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          {keyMissing && p.secret_hint ? (
            <Box sx={{ mt: 0.75, pl: 3 }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                Выставьте переменную окружения перед стартом бэкенда:
              </Typography>
              <HintRow
                label="PowerShell"
                command={p.secret_hint.powershell}
                onCopy={(t) => onCopy(t, 'Команда PowerShell')}
              />
              <HintRow
                label="bash"
                command={p.secret_hint.bash}
                onCopy={(t) => onCopy(t, 'Команда bash')}
              />
            </Box>
          ) : null}
        </Box>
      ) : null}
    </Box>
  );
}


interface HintRowProps {
  label: string;
  command: string;
  onCopy: (text: string) => void;
}

function HintRow({ label, command, onCopy }: HintRowProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        mt: 0.25,
        fontFamily: 'monospace',
        fontSize: '0.78rem',
      }}
    >
      <Typography variant="caption" sx={{ minWidth: 80, color: 'text.secondary' }}>
        {label}
      </Typography>
      <Box
        sx={{
          flex: 1,
          p: 0.5,
          px: 1,
          borderRadius: 0.75,
          bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(0,0,0,0.35)' : 'rgba(0,0,0,0.06)'),
          overflowX: 'auto',
          whiteSpace: 'nowrap',
        }}
      >
        {command}
      </Box>
      <Tooltip title="Скопировать команду">
        <IconButton size="small" onClick={() => onCopy(command)}>
          <CopyIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
