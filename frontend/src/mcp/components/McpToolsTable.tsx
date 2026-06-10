import React, { useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Collapse,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import type { McpToolInfo } from '../types';

interface McpToolsTableProps {
  tools: McpToolInfo[];
  filterServerId?: string | null;
  isDarkMode?: boolean;
}

export default function McpToolsTable({ tools, filterServerId, isDarkMode }: McpToolsTableProps) {
  const muted = isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)';

  const filtered = useMemo(() => {
    if (!filterServerId) return tools;
    return tools.filter((t) => t.server_id === filterServerId);
  }, [tools, filterServerId]);

  if (filtered.length === 0) {
    return (
      <Typography variant="body2" sx={{ color: muted }}>
        Инструменты не найдены или сервер недоступен.
      </Typography>
    );
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Qualified name</TableCell>
          <TableCell>Tool</TableCell>
          <TableCell>Server</TableCell>
          <TableCell>Описание</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {filtered.map((t) => (
          <TableRow key={t.qualified_name}>
            <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{t.qualified_name}</TableCell>
            <TableCell>{t.name}</TableCell>
            <TableCell>{t.server_id}</TableCell>
            <TableCell sx={{ maxWidth: 280, color: muted }}>{t.description || '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

interface McpToolsSectionProps extends McpToolsTableProps {
  title?: string;
}

export function McpToolsSection({ title = 'Инструменты MCP', ...props }: McpToolsSectionProps) {
  const [open, setOpen] = useState(false);
  return (
    <Box>
      <Box
        role="button"
        tabIndex={0}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setOpen((v) => !v);
          }
        }}
        sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', mb: 1 }}
      >
        <Typography variant="subtitle2">{title}</Typography>
        <Chip label={props.tools.length} size="small" />
        <IconButton size="small" sx={{ transform: open ? 'rotate(180deg)' : 'none' }}>
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={open}>
        <McpToolsTable {...props} />
      </Collapse>
    </Box>
  );
}
