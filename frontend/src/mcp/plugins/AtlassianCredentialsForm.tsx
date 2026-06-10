import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  TextField,
  Typography,
} from '@mui/material';
import { deleteMcpCredentials, fetchMcpCredentialsMeta, saveMcpCredentials } from '../api';

interface AtlassianCredentialsFormProps {
  isDarkMode: boolean;
  compact?: boolean;
}

const FIELDS = [
  { key: 'jira_url', label: 'Jira URL', secret: false },
  { key: 'jira_pat', label: 'Jira PAT', secret: true },
  { key: 'confluence_url', label: 'Confluence URL', secret: false },
  { key: 'confluence_pat', label: 'Confluence PAT', secret: true },
] as const;

export default function AtlassianCredentialsForm({ isDarkMode, compact }: AtlassianCredentialsFormProps) {
  const muted = isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)';
  const [meta, setMeta] = useState<Awaited<ReturnType<typeof fetchMcpCredentialsMeta>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({
    jira_url: '',
    jira_pat: '',
    confluence_url: '',
    confluence_pat: '',
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const m = await fetchMcpCredentialsMeta('atlassian');
      setMeta(m);
    } catch {
      setMeta({ configured: false, storage_available: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: Record<string, string> = {};
      for (const f of FIELDS) {
        const v = form[f.key]?.trim();
        if (v) payload[f.key] = v;
      }
      await saveMcpCredentials('atlassian', payload);
      setSuccess('Учётные данные сохранены');
      setForm({ jira_url: '', jira_pat: '', confluence_url: '', confluence_pat: '' });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteMcpCredentials('atlassian');
      setSuccess('Учётные данные удалены');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось удалить');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: compact ? 1 : 2 }}>
        <CircularProgress size={22} />
      </Box>
    );
  }

  if (meta?.storage_available === false) {
    return (
      <Alert severity="warning" sx={{ fontSize: compact ? '0.75rem' : undefined }}>
        Хранилище credentials недоступно (MongoDB / MCP_CREDENTIALS_ENCRYPTION_KEY).
      </Alert>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: compact ? 1 : 1.5 }}>
      <Typography variant="body2" sx={{ color: muted, fontSize: compact ? '0.72rem' : '0.82rem' }}>
        Per-user PAT (auth_mode=per_user). Секреты не возвращаются с сервера — только флаги «задано».
      </Typography>
      {meta?.configured ? (
        <Typography variant="caption" color="success.main">
          Настроено:{' '}
          {Object.entries(meta.fields || {})
            .filter(([, v]) => v)
            .map(([k]) => k)
            .join(', ') || 'да'}
        </Typography>
      ) : (
        <Typography variant="caption" color="text.secondary">
          PAT ещё не сохранён для вашего пользователя.
        </Typography>
      )}
      {FIELDS.map((f) => (
        <TextField
          key={f.key}
          size="small"
          fullWidth
          label={f.label}
          type={f.secret ? 'password' : 'text'}
          value={form[f.key]}
          onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
          placeholder={meta?.fields?.[f.key] ? '•••• (оставьте пустым, чтобы не менять)' : undefined}
        />
      ))}
      {error ? <Alert severity="error">{error}</Alert> : null}
      {success ? <Alert severity="success">{success}</Alert> : null}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Button size="small" variant="contained" disabled={saving} onClick={() => void onSave()}>
          Сохранить
        </Button>
        {meta?.configured ? (
          <Button size="small" color="error" disabled={saving} onClick={() => void onDelete()}>
            Удалить
          </Button>
        ) : null}
      </Box>
    </Box>
  );
}
