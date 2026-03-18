import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  FormControlLabel,
  Switch,
} from '@mui/material';
import { LibraryBooks as LibraryBooksIcon } from '@mui/icons-material';
import MemoryRagLibraryModal from '../MemoryRagLibraryModal';
import {
  isKnowledgeRagEnabled,
  setKnowledgeRagEnabled,
  KNOWLEDGE_RAG_STORAGE_EVENT,
} from '../../utils/knowledgeRagStorage';

type Variant = 'prominent' | 'inline';

interface Props {
  /** prominent — отдельная заметная карточка сверху; inline — внутри другой карточки */
  variant?: Variant;
}

export default function MemoryRagLibrarySection({ variant = 'prominent' }: Props) {
  const [memoryRagModalOpen, setMemoryRagModalOpen] = useState(false);
  const [useMemoryLibraryRag, setUseMemoryLibraryRag] = useState(() => isKnowledgeRagEnabled());

  useEffect(() => {
    const onRag = () => setUseMemoryLibraryRag(isKnowledgeRagEnabled());
    window.addEventListener(KNOWLEDGE_RAG_STORAGE_EVENT, onRag);
    return () => window.removeEventListener(KNOWLEDGE_RAG_STORAGE_EVENT, onRag);
  }, []);

  const inner = (
    <>
      <Typography
        variant={variant === 'prominent' ? 'h6' : 'subtitle2'}
        gutterBottom
        sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: variant === 'prominent' ? 600 : 500 }}
      >
        <LibraryBooksIcon color="primary" fontSize={variant === 'prominent' ? 'medium' : 'small'} />
        Документы для RAG (библиотека памяти)
      </Typography>
      {variant === 'prominent' && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Загрузите PDF, Word, Excel, TXT — файлы в MinIO, поиск по векторам в PostgreSQL. Включите переключатель, чтобы
          модель использовала их в чате.
        </Typography>
      )}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
        <Button
          variant="contained"
          color="primary"
          size={variant === 'prominent' ? 'large' : 'medium'}
          startIcon={<LibraryBooksIcon />}
          onClick={() => setMemoryRagModalOpen(true)}
          sx={variant === 'prominent' ? { minWidth: 280 } : undefined}
        >
          Открыть библиотеку документов
        </Button>
        <FormControlLabel
          control={
            <Switch
              checked={useMemoryLibraryRag}
              onChange={(_, c) => {
                setUseMemoryLibraryRag(c);
                setKnowledgeRagEnabled(c);
              }}
            />
          }
          label="Учитывать в ответах чата"
        />
      </Box>
      {variant === 'inline' && (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          MinIO + pgvector. Переключатель включает контекст из библиотеки в сообщениях.
        </Typography>
      )}
      <MemoryRagLibraryModal open={memoryRagModalOpen} onClose={() => setMemoryRagModalOpen(false)} />
    </>
  );

  if (variant === 'inline') {
    return (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: 1,
          bgcolor: 'action.hover',
          border: 1,
          borderColor: 'divider',
        }}
      >
        {inner}
      </Box>
    );
  }

  return (
    <Card
      sx={{
        mb: 3,
        border: 2,
        borderColor: 'primary.main',
        background: (t) =>
          t.palette.mode === 'dark' ? 'rgba(25, 118, 210, 0.08)' : 'rgba(25, 118, 210, 0.06)',
      }}
    >
      <CardContent>{inner}</CardContent>
    </Card>
  );
}
