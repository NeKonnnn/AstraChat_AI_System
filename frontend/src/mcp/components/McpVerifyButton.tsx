import React, { useState } from 'react';
import { Button, CircularProgress, Typography, Box } from '@mui/material';
import { CheckCircleOutline, ErrorOutline, VerifiedUserOutlined } from '@mui/icons-material';
import type { McpVerifyResult } from '../types';

interface McpVerifyButtonProps {
  serverId: string;
  onVerify: (serverId: string) => Promise<McpVerifyResult>;
  disabled?: boolean;
  size?: 'small' | 'medium';
}

export default function McpVerifyButton({
  serverId,
  onVerify,
  disabled,
  size = 'small',
}: McpVerifyButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<McpVerifyResult | null>(null);

  const handleClick = async () => {
    setLoading(true);
    setResult(null);
    try {
      const vr = await onVerify(serverId);
      setResult(vr);
    } catch (e) {
      setResult({
        server_id: serverId,
        success: false,
        error: e instanceof Error ? e.message : 'Verify failed',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, alignItems: 'flex-start' }}>
      <Button
        size={size}
        variant="outlined"
        disabled={disabled || loading}
        onClick={() => void handleClick()}
        startIcon={loading ? <CircularProgress size={14} /> : <VerifiedUserOutlined />}
      >
        Проверить подключение
      </Button>
      {result ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {result.success ? (
            <CheckCircleOutline color="success" fontSize="small" />
          ) : (
            <ErrorOutline color="error" fontSize="small" />
          )}
          <Typography variant="caption" color={result.success ? 'success.main' : 'error.main'}>
            {result.success
              ? `OK · ${result.tools_count ?? 0} tools · ${result.latency_ms ?? '—'} ms`
              : result.error || 'Ошибка verify'}
          </Typography>
        </Box>
      ) : null}
    </Box>
  );
}
