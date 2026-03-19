import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
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
  Button,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  Description as DocumentIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
  TextSnippet as TxtIcon,
  Article as ArticleIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { getApiUrl, API_ENDPOINTS } from '../config/api';

export interface ProjectRagDoc {
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
  if (ext === 'txt' || ext === 'md') return <TxtIcon sx={{ color: '#1e88e5' }} />;
  if (['docx', 'doc'].includes(ext)) return <ArticleIcon sx={{ color: '#1565c0' }} />;
  return <DocumentIcon sx={{ color: '#7b1fa2' }} />;
}

const ALLOWED = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.csv', '.md'];

export interface ProjectRagLibraryInlineProps {
  /** null — до первого resolve (новый проект) */
  projectId: string | null;
  /** Вызывается перед первой загрузкой, если projectId ещё null; должен вернуть id проекта */
  onResolveProjectId?: () => string | Promise<string>;
  /** Загружать список при монтировании / смене id */
  autoLoad?: boolean;
  /** Подпись под заголовком */
  subtitle?: string;
  dense?: boolean;
}

export default function ProjectRagLibraryInline({
  projectId,
  onResolveProjectId,
  autoLoad = true,
  subtitle = 'Оригиналы в MinIO, чанки и векторы — в PostgreSQL (только этот проект)',
  dense = false,
}: ProjectRagLibraryInlineProps) {
  const [documents, setDocuments] = useState<ProjectRagDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [banner, setBanner] = useState<{ message: string; severity: 'success' | 'error' | 'info' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resolvedId, setResolvedId] = useState<string | null>(projectId);

  useEffect(() => {
    setResolvedId(projectId);
  }, [projectId]);

  const effectiveId = resolvedId ?? projectId;

  const fetchList = useCallback(async (pid: string): Promise<ProjectRagDoc[]> => {
    const url = getApiUrl((API_ENDPOINTS.PROJECT_RAG_LIST as (id: string) => string)(pid));
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    return data.documents || [];
  }, []);

  const loadDocuments = useCallback(async () => {
    if (!effectiveId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setBanner(null);
    try {
      setDocuments(await fetchList(effectiveId));
    } catch (e) {
      setBanner({
        message: `Не удалось загрузить список файлов: ${e instanceof Error ? e.message : String(e)}`,
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [effectiveId, fetchList]);

  useEffect(() => {
    if (!autoLoad) return;
    if (!effectiveId) {
      setDocuments([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchList(effectiveId)
      .then((docs) => {
        if (!cancelled) setDocuments(docs);
      })
      .catch(() => {
        if (!cancelled) setDocuments([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveId, autoLoad, fetchList]);

  const ensureProjectId = async (): Promise<string | null> => {
    if (effectiveId) return effectiveId;
    if (!onResolveProjectId) {
      setBanner({
        message: 'Загрузка файлов для этого экрана недоступна (не передан обработчик создания проекта).',
        severity: 'error',
      });
      return null;
    }
    try {
      const id = await Promise.resolve(onResolveProjectId());
      setResolvedId(id);
      return id;
    } catch (e) {
      setBanner({
        message: `Не удалось подготовить проект: ${e instanceof Error ? e.message : String(e)}`,
        severity: 'error',
      });
      return null;
    }
  };

  const uploadFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;

    const pid = await ensureProjectId();
    if (!pid) return;

    const valid = list.filter((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      return ALLOWED.includes(ext);
    });
    if (!valid.length) {
      setBanner({
        message: 'Допустимы: PDF, DOC/DOCX, XLS/XLSX, TXT, CSV, MD',
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
        const url = getApiUrl((API_ENDPOINTS.PROJECT_RAG_UPLOAD as (id: string) => string)(pid));
        const resp = await fetch(url, { method: 'POST', body: fd });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({ detail: resp.statusText }));
          throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setBanner({ message: `${file.name}: ${msg}`, severity: 'error' });
        setUploading(false);
        try {
          setDocuments(await fetchList(pid));
        } catch {
          /* ignore */
        }
        return;
      }
    }
    setUploading(false);
    setBanner({
      message: `Загружено файлов: ${valid.length}. Документы проиндексированы для RAG.`,
      severity: 'success',
    });
    try {
      setDocuments(await fetchList(pid));
    } catch {
      /* ignore */
    }
  };

  const handleDelete = async (doc: ProjectRagDoc) => {
    if (!effectiveId) return;
    try {
      const url = getApiUrl(
        (API_ENDPOINTS.PROJECT_RAG_DELETE_DOC as (pid: string, did: number) => string)(effectiveId, doc.id)
      );
      const resp = await fetch(url, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setBanner({ message: `«${doc.filename}» удалён`, severity: 'success' });
      setDocuments(await fetchList(effectiveId));
    } catch (e) {
      setBanner({ message: `Ошибка удаления: ${e}`, severity: 'error' });
    }
  };

  const dropZone = (
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
        p: dense ? 2 : 3,
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
        accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.md"
        onChange={(e) => {
          if (e.target.files?.length) uploadFiles(e.target.files);
          e.target.value = '';
        }}
      />
      <UploadIcon sx={{ fontSize: dense ? 32 : 40, color: 'text.secondary', mb: 1 }} />
      <Typography variant="body2" gutterBottom>
        Перетащите файлы сюда или нажмите кнопку — загрузка сразу на сервер
      </Typography>
      <Button
        variant="contained"
        size={dense ? 'small' : 'medium'}
        startIcon={<UploadIcon />}
        disabled={uploading}
        onClick={() => fileInputRef.current?.click()}
      >
        Выбрать файлы
      </Button>
      {uploading && <LinearProgress sx={{ mt: 2 }} />}
    </Box>
  );

  return (
    <Box>
      <Typography variant="subtitle2" fontWeight={600} gutterBottom>
        Файлы проекта (RAG)
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
        {subtitle}
      </Typography>

      {banner && (
        <Alert severity={banner.severity} onClose={() => setBanner(null)} sx={{ mb: 2 }}>
          {banner.message}
        </Alert>
      )}

      {dropZone}

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2">
          Проиндексированные документы ({documents.length})
        </Typography>
        <Button
          size="small"
          startIcon={<RefreshIcon />}
          onClick={() => loadDocuments()}
          disabled={loading || !effectiveId}
        >
          Обновить
        </Button>
      </Box>

      {!effectiveId ? (
        <Typography color="text.secondary" variant="body2">
          После выбора файлов будет создан черновик проекта (если его ещё нет), и документы сразу попадут в хранилище.
        </Typography>
      ) : loading ? (
        <LinearProgress />
      ) : documents.length === 0 ? (
        <Typography color="text.secondary" variant="body2">
          Пока нет документов. Загрузите файлы выше — они станут доступны для поиска в рамках этого проекта.
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
    </Box>
  );
}
