import React, { useState, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Container,
  Card,
  CardContent,
  Button,
  TextField,
  IconButton,
  Chip,
  LinearProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  Upload as UploadIcon,
  Description as DocumentIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
  Send as SendIcon,
  Delete as DeleteIcon,
  GetApp as DownloadIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { useAppActions } from '../contexts/AppContext';

export default function DocumentsPage() {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryResponse, setQueryResponse] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<Array<{
    name: string;
    size: number;
    type: string;
    uploadDate: string;
  }>>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  
  const { showNotification } = useAppActions();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file: File) => {
    // Проверка типа файла
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'image/jpeg',
      'image/jpg',
      'image/png',
      'image/webp',
    ];

    if (!allowedTypes.includes(file.type)) {
      showNotification('error', 'Поддерживаются только файлы PDF, Word (.docx), Excel (.xlsx) и изображения (JPG, PNG, WebP)');
      return;
    }

    // Проверка размера файла (макс 50MB)
    if (file.size > 50 * 1024 * 1024) {
      showNotification('error', 'Размер файла не должен превышать 50MB');
      return;
    }

    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        showNotification('success', 'Документ успешно загружен и обработан');
        
        // Добавляем файл в список
        setUploadedFiles(prev => [...prev, {
          name: file.name,
          size: file.size,
          type: file.type,
          uploadDate: new Date().toISOString(),
        }]);
        
        setShowUploadDialog(false);
      } else {
        const error = await response.json().catch(() => ({ detail: 'Ошибка загрузки' }));
        showNotification('error', error.detail || 'Ошибка при загрузке документа');
      }
    } catch (error) {
      console.error('Ошибка загрузки:', error);
      showNotification('error', 'Ошибка при загрузке документа');
    } finally {
      setIsUploading(false);
    }
  };

  const handleQuery = async () => {
    if (!query.trim()) {
      showNotification('warning', 'Введите вопрос по документу');
      return;
    }

    if (uploadedFiles.length === 0) {
      showNotification('warning', 'Сначала загрузите документ');
      return;
    }

    setIsQuerying(true);
    
    try {
      const response = await fetch('http://localhost:8000/api/documents/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });

      if (response.ok) {
        const result = await response.json();
        setQueryResponse(result.response);
        showNotification('success', 'Ответ получен');
      } else {
        const error = await response.json().catch(() => ({ detail: 'Ошибка обработки' }));
        showNotification('error', error.detail || 'Ошибка при обработке запроса');
      }
    } catch (error) {
      console.error('Ошибка запроса:', error);
      showNotification('error', 'Ошибка при отправке запроса');
    } finally {
      setIsQuerying(false);
    }
  };

  const getFileIcon = (type: string) => {
    if (type.includes('pdf')) return <PdfIcon color="error" />;
    if (type.includes('word')) return <DocumentIcon color="primary" />;
    if (type.includes('sheet') || type.includes('excel')) return <ExcelIcon color="success" />;
    return <DocumentIcon />;
  };

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Byte';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)).toString());
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Заголовок */}
      <Paper elevation={2} sx={{ p: 2, borderRadius: 0 }}>
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="h5" fontWeight="600">
                Работа с документами
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Загрузите документы и задавайте вопросы по их содержимому
              </Typography>
            </Box>
            
            <Button
              variant="contained"
              startIcon={<UploadIcon />}
              onClick={() => setShowUploadDialog(true)}
              disabled={isUploading}
            >
              Загрузить документ
            </Button>
          </Box>
        </Container>
      </Paper>

      <Container maxWidth="lg" sx={{ flexGrow: 1, py: 3 }}>
        <Box sx={{ display: 'flex', gap: 3, height: '100%' }}>
          {/* Левая панель - список документов */}
          <Card sx={{ width: 350, display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1 }}>
              <Typography variant="h6" gutterBottom>
                Загруженные документы
              </Typography>
              
              {uploadedFiles.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <DocumentIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                  <Typography color="text.secondary">
                    Документы не загружены
                  </Typography>
                  <Button
                    variant="outlined"
                    startIcon={<UploadIcon />}
                    sx={{ mt: 2 }}
                    onClick={() => setShowUploadDialog(true)}
                  >
                    Загрузить первый документ
                  </Button>
                </Box>
              ) : (
                <List>
                  {uploadedFiles.map((file, index) => (
                    <React.Fragment key={index}>
                      <ListItem>
                        <ListItemIcon>
                          {getFileIcon(file.type)}
                        </ListItemIcon>
                        <ListItemText
                          primary={file.name}
                          secondary={
                            <React.Fragment>
                              <Typography variant="caption" display="block" component="span">
                                {formatFileSize(file.size)}
                              </Typography>
                              <Typography variant="caption" color="text.secondary" component="span">
                                {new Date(file.uploadDate).toLocaleDateString('ru-RU')}
                              </Typography>
                            </React.Fragment>
                          }
                        />
                        <IconButton size="small" color="error">
                          <DeleteIcon />
                        </IconButton>
                      </ListItem>
                      {index < uploadedFiles.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>

          {/* Правая панель - запросы и ответы */}
          <Card sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1 }}>
              <Typography variant="h6" gutterBottom>
                Задать вопрос по документу
              </Typography>

              {/* Поле для вопроса */}
              <Box sx={{ mb: 3 }}>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  placeholder="Например: Сделай краткий пересказ документа, или Найди информацию о..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={isQuerying || uploadedFiles.length === 0}
                  variant="outlined"
                />
                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="caption" color="text.secondary">
                    {uploadedFiles.length === 0 && 'Сначала загрузите документ'}
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<SendIcon />}
                    onClick={handleQuery}
                    disabled={!query.trim() || isQuerying || uploadedFiles.length === 0}
                  >
                    Задать вопрос
                  </Button>
                </Box>
              </Box>

              {/* Индикатор загрузки */}
              {isQuerying && (
                <Box sx={{ mb: 3 }}>
                  <LinearProgress />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Анализирую документ и формирую ответ...
                  </Typography>
                </Box>
              )}

              {/* Ответ */}
              {queryResponse && (
                <Card sx={{ backgroundColor: 'background.default', p: 2 }}>
                  <Typography variant="subtitle2" color="primary" gutterBottom>
                    Ответ:
                  </Typography>
                  <Box
                    sx={{
                      maxHeight: '400px', // Максимальная высота 400px
                      overflowY: 'auto', // Вертикальная прокрутка
                      overflowX: 'hidden', // Скрываем горизонтальную прокрутку
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                      p: 2,
                      mb: 2,
                      backgroundColor: 'background.paper',
                      // Кастомные стили для скроллбара
                      '&::-webkit-scrollbar': {
                        width: '8px',
                      },
                      '&::-webkit-scrollbar-track': {
                        backgroundColor: 'rgba(0,0,0,0.1)',
                        borderRadius: '4px',
                      },
                      '&::-webkit-scrollbar-thumb': {
                        backgroundColor: 'rgba(0,0,0,0.3)',
                        borderRadius: '4px',
                        '&:hover': {
                          backgroundColor: 'rgba(0,0,0,0.5)',
                        },
                      },
                    }}
                  >
                    <Typography 
                      variant="body1" 
                      sx={{ 
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word', // Перенос длинных слов
                        lineHeight: 1.6, // Улучшенная читаемость
                      }}
                    >
                      {queryResponse}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      size="small"
                      startIcon={<CopyIcon />}
                      onClick={() => {
                        navigator.clipboard.writeText(queryResponse).then(() => {
                          showNotification('success', 'Ответ скопирован в буфер обмена');
                        }).catch(() => {
                          showNotification('error', 'Не удалось скопировать ответ');
                        });
                      }}
                    >
                      Копировать
                    </Button>
                    <Button
                      size="small"
                      startIcon={<DownloadIcon />}
                      onClick={() => {
                        const blob = new Blob([queryResponse], { type: 'text/plain' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'answer.txt';
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                    >
                      Скачать ответ
                    </Button>
                  </Box>
                </Card>
              )}

              {/* Примеры вопросов */}
              {uploadedFiles.length > 0 && !queryResponse && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Примеры вопросов:
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {[
                      'Сделай краткий пересказ',
                      'Какие основные выводы?',
                      'Найди упоминания о...',
                      'Есть ли в документе информация о...?',
                      'Перечисли основные пункты',
                    ].map((example) => (
                      <Chip
                        key={example}
                        label={example}
                        variant="outlined"
                        size="small"
                        onClick={() => setQuery(example)}
                        sx={{ cursor: 'pointer' }}
                      />
                    ))}
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>
      </Container>

      {/* Диалог загрузки */}
      <Dialog
        open={showUploadDialog}
        onClose={() => setShowUploadDialog(false)}
        maxWidth="sm"
        fullWidth
        TransitionComponent={undefined}
        transitionDuration={0}
      >
        <DialogTitle>Загрузить документ</DialogTitle>
        <DialogContent>
          <Box
            sx={{
              border: '2px dashed',
              borderColor: isDragging ? 'primary.main' : 'grey.300',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              backgroundColor: isDragging ? 'primary.50' : 'background.default',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              '&:hover': {
                borderColor: 'primary.main',
                backgroundColor: 'primary.50',
              },
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Перетащите файл сюда или нажмите для выбора
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Поддерживаются: PDF, Word (.docx), Excel (.xlsx), изображения (JPG, PNG, WebP)
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Максимальный размер: 50MB
            </Typography>
          </Box>
          
          <input
            ref={fileInputRef}
            type="file"
            hidden
            accept=".pdf,.docx,.xlsx,.xls,.jpg,.jpeg,.png,.webp"
            onChange={handleFileSelect}
          />
          
          {isUploading && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Загружаю и обрабатываю документ...
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowUploadDialog(false)} disabled={isUploading}>
            Отмена
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
