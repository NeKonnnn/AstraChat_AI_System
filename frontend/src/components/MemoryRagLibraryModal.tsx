import React, { useState, useRef, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  IconButton,
  LinearProgress,
  Alert,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  Description as DocumentIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
  TextSnippet as TxtIcon,
  Article as ArticleIcon,
  Close as CloseIcon,
  LibraryBooks as LibraryIcon,
} from '@mui/icons-material';
import { getApiUrl, API_ENDPOINTS } from '../config/api';
import { useAppActions } from '../contexts/AppContext';

export interface MemoryRagDoc {
  id: number;
  filename: string;
  created_at: string | null;
  size?: number | null;
  file_type?: string | null;
}

function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null || !bytes) return '—';
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return <PdfIcon sx={{ color: '#e53935' }} />;
  if (['xlsx', 'xls', 'csv'].includes(ext)) return <ExcelIcon sx={{ color: '#43a047' }} />;
  if (ext === 'txt') return <TxtIcon sx={{ color: '#1e88e5' }} />;
  if (['docx', 'doc'].includes(ext)) return <ArticleIcon sx={{ color: '#1565c0' }} />;
  return <DocumentIcon sx={{ color: '#7b1fa2' }} />;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

async function fetchDocumentList(): Promise<MemoryRagDoc[]> {
  const resp = await fetch(getApiUrl(API_ENDPOINTS.MEMORY_RAG_LIST));
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  return data.documents || [];
}

export default function MemoryRagLibraryModal({ open, onClose }: Props) {
  const [documents, setDocuments] = useState<MemoryRagDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [banner, setBanner] = useState<{
    message: string;
    severity: 'success' | 'error' | 'info';
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showNotification } = useAppActions();
  const notifyRef = useRef(showNotification);
  notifyRef.current = showNotification;

  useEffect(() => {
    if (!open) {
      setBanner(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const docs = await fetchDocumentList();
        if (!cancelled) setDocuments(docs);
      } catch (e) {
        if (!cancelled) notifyRef.current('error', `Не удалось загрузить список: ${e}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      setDocuments(await fetchDocumentList());
    } catch (e) {
      notifyRef.current('error', `Не удалось загрузить список: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const allowed = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.csv'];

  const uploadFiles = async (files: FileList) => {
    if (!files.length) return;
    const valid = Array.from(files).filter((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      return allowed.includes(ext);
    });
    if (!valid.length) {
      setBanner({
        message: 'Допустимы: PDF, DOC/DOCX, XLS/XLSX, TXT, CSV',
        severity: 'error',
      });
      return;
    }
    setUploading(true);
    setBanner(null);
    for (const file of valid) {
      try {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch(getApiUrl(API_ENDPOINTS.MEMORY_RAG_UPLOAD), {
          method: 'POST',
          body: fd,
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({ detail: resp.statusText }));
          throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setBanner({ message: `${file.name}: ${msg}`, severity: 'error' });
        setUploading(false);
        try {
          setDocuments(await fetchDocumentList());
        } catch {
          /* ignore */
        }
        return;
      }
    }
    setUploading(false);
    setBanner({
      message: `Загружено файлов: ${valid.length}. Файлы в MinIO, текст проиндексирован в PostgreSQL (pgvector).`,
      severity: 'success',
    });
    try {
      setDocuments(await fetchDocumentList());
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (doc: MemoryRagDoc) => {
    try {
      const url = `${getApiUrl(API_ENDPOINTS.MEMORY_RAG_DELETE)}/${doc.id}`;
      const resp = await fetch(url, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setBanner({ message: `«${doc.filename}» удалён`, severity: 'success' });
      setDocuments(await fetchDocumentList());
    } catch (e) {
      setBanner({ message: `Ошибка удаления: ${e}`, severity: 'error' });
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      scroll="paper"
      disableScrollLock
      disableRestoreFocus
      slotProps={{
        root: {
          sx: { zIndex: 2000 },
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pr: 6 }}>
        <LibraryIcon color="primary" />
        <Box flex={1}>
          <Typography variant="h6" component="span">
            Документы для RAG (библиотека памяти)
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            Оригиналы в MinIO (bucket astrachat-memory-rag), чанки и векторы — в PostgreSQL
          </Typography>
        </Box>
        <IconButton aria-label="закрыть" onClick={onClose} sx={{ position: 'absolute', right: 8, top: 8 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {banner && (
          <Alert severity={banner.severity} onClose={() => setBanner(null)} sx={{ mb: 2 }}>
            {banner.message}
          </Alert>
        )}
        <Box
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
          }}
          sx={{
            border: '2px dashed',
            borderColor: 'divider',
            borderRadius: 2,
            p: 3,
            textAlign: 'center',
            mb: 2,
            bgcolor: 'action.hover',
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
            onChange={(e) => {
              if (e.target.files?.length) uploadFiles(e.target.files);
              e.target.value = '';
            }}
          />
          <UploadIcon sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
          <Typography variant="body2" gutterBottom>
            Перетащите файлы сюда или нажмите кнопку
          </Typography>
          <Button
            variant="contained"
            startIcon={<UploadIcon />}
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            Выбрать файлы
          </Button>
          {uploading && <LinearProgress sx={{ mt: 2 }} />}
        </Box>

        <Typography variant="subtitle2" gutterBottom>
          Проиндексированные документы ({documents.length})
        </Typography>
        {loading ? (
          <LinearProgress />
        ) : documents.length === 0 ? (
          <Typography color="text.secondary" variant="body2">
            Пока нет документов. Включите «Учитывать в ответах чата» в настройках памяти, чтобы модель использовала
            загруженные материалы.
          </Typography>
        ) : (
          <List dense disablePadding>
            {documents.map((doc) => (
              <ListItem
                key={doc.id}
                secondaryAction={
                  <Tooltip title="Удалить из БД и MinIO">
                    <IconButton edge="end" onClick={() => handleDelete(doc)} color="error" size="small">
                      <DeleteIcon />
                    </IconButton>
                  </Tooltip>
                }
                sx={{ borderBottom: 1, borderColor: 'divider' }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>{getFileIcon(doc.filename)}</ListItemIcon>
                <ListItemText
                  primary={doc.filename}
                  secondary={
                    <>
                      {formatFileSize(doc.size ?? null)}
                      {doc.created_at && (
                        <>
                          {' · '}
                          {new Date(doc.created_at).toLocaleString('ru-RU')}
                        </>
                      )}
                    </>
                  }
                />
                <Chip size="small" label={`#${doc.id}`} sx={{ mr: 4 }} />
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={loadDocuments} disabled={loading}>
          Обновить список
        </Button>
        <Button onClick={onClose} variant="contained">
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );
}
