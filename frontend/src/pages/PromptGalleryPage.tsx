import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  CardActions,
  Chip,
  Rating,
  IconButton,
  Menu,
  MenuItem,
  FormControl,
  InputLabel,
  Select,
  Pagination,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  Alert,
  Snackbar,
  Stack,
  InputAdornment,
  CircularProgress,
  Popover,
  Checkbox,
  Drawer,
  Divider,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  MoreVert as MoreVertIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  ContentCopy as CopyIcon,
  TrendingUp as TrendingUpIcon,
  Person as PersonIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  Visibility as ViewIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
  FilterList as FilterListIcon,
  Menu as MenuIcon,
  VisibilityOff as VisibilityOffIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';
import { getApiUrl, API_CONFIG } from '../config/api';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '@mui/material/styles';

interface Tag {
  id: number;
  name: string;
  description?: string;
  color?: string;
}

interface Prompt {
  id: number;
  title: string;
  content: string;
  description?: string;
  author_id: string;
  author_name: string;
  created_at: string;
  updated_at: string;
  is_public: boolean;
  usage_count: number;
  views_count: number;
  tags: Tag[];
  average_rating: number;
  total_votes: number;
  user_rating?: number;
  is_bookmarked?: boolean;
}

export default function PromptGalleryPage() {
  // Получаем токен из контекста аутентификации
  const { token } = useAuth();
  const theme = useTheme();
  const isDarkMode = theme.palette.mode === 'dark';
  
  // Состояние для промптов
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Состояние для фильтров
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [sortBy, setSortBy] = useState('rating');
  const [sortOrder] = useState('desc');
  const [showBookmarks, setShowBookmarks] = useState(false);

  // Состояние для тегов
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [popularTags, setPopularTags] = useState<Array<{ tag: Tag; count: number }>>([]);

  // Состояние для диалогов
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deletingPromptId, setDeletingPromptId] = useState<number | null>(null);
  const [filtersAnchorEl, setFiltersAnchorEl] = useState<null | HTMLElement>(null);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);
  const [rightSidebarHidden, setRightSidebarHidden] = useState(false);

  // Состояние для создания/редактирования
  const [promptForm, setPromptForm] = useState({
    title: '',
    content: '',
    description: '',
    is_public: true,
    tag_ids: [] as number[],
    new_tags: [] as string[],
  });
  
  // Состояние для ввода нового тега
  const [newTagInput, setNewTagInput] = useState('');

  // Уведомления
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  // Флаг для предотвращения одновременных загрузок
  const isLoadingRef = useRef(false);
  // Флаг для отслеживания первого рендера
  const hasLoadedRef = useRef(false);

  // Загрузка промптов
  const loadPrompts = useCallback(async () => {
    // Предотвращаем одновременные загрузки
    if (isLoadingRef.current) {
      return;
    }
    
    isLoadingRef.current = true;
    setLoading(true);
    try {
      let url = `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/`;
      
      // Если показываем закладки, используем другой endpoint
      if (showBookmarks) {
        if (!token) {
          showNotification('Для просмотра закладок необходимо войти в систему', 'error');
          setPrompts([]);
          setTotalPages(0);
          setLoading(false);
          return;
        }
        url = `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/my/bookmarks`;
      }
      
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '20',
      });
      
      // Для закладок не применяем сортировку и фильтры
      if (!showBookmarks) {
        params.append('sort_by', sortBy);
        params.append('sort_order', sortOrder);
        if (searchQuery) params.append('search', searchQuery);
        if (selectedTags.length > 0) params.append('tags', selectedTags.join(','));
      }

      const headers: HeadersInit = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const fullUrl = `${url}?${params}`;
      
      
      
      const response = await fetch(fullUrl, { headers });

      if (response.ok) {
        const data = await response.json();
        
        // Убеждаемся, что у каждого промпта есть поле tags
        const promptsWithTags = (data.prompts || []).map((p: any) => ({
          ...p,
          tags: p.tags || []
        }));
        
        setPrompts(promptsWithTags);
        setTotalPages(data.pages || 1);
      } else {
        // При ошибке очищаем список промптов
        setPrompts([]);
        setTotalPages(0);
        
        const errorText = await response.text();
        console.error('Ошибка загрузки промптов:', response.status, errorText);
        try {
          const errorData = JSON.parse(errorText);
          showNotification(errorData.detail || 'Ошибка загрузки промптов', 'error');
        } catch (e) {
          showNotification(`Ошибка загрузки промптов (${response.status})`, 'error');
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки промптов:', error);
      showNotification('Ошибка загрузки промптов', 'error');
    } finally {
      setLoading(false);
      isLoadingRef.current = false;
    }
  }, [page, sortBy, sortOrder, selectedTags, searchQuery, token, showBookmarks]);

  // Загрузка тегов
  const loadTags = async () => {
    try {
      const [allResponse, popularResponse] = await Promise.all([
        fetch(`${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/tags/all`),
        fetch(`${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/tags/popular?limit=20`),
      ]);

      if (allResponse.ok) {
        const tags = await allResponse.json();
        
        setAllTags(tags);
      } else {
        console.error('Ошибка загрузки всех тегов:', allResponse.status, await allResponse.text());
      }

      if (popularResponse.ok) {
        const popular = await popularResponse.json();
        setPopularTags(popular);
      } else {
        console.error('Ошибка загрузки популярных тегов:', popularResponse.status, await popularResponse.text());
      }
    } catch (error) {
      console.error('Ошибка загрузки тегов:', error);
    }
  };

  useEffect(() => {
    loadTags();
  }, []);

  // Сброс страницы при переключении закладок
  useEffect(() => {
    setPage(1);
  }, [showBookmarks]);

  // Основная загрузка промптов (без поиска)
  useEffect(() => {
    // Пропускаем если есть поисковый запрос - для него отдельный useEffect с дебаунсом
    if (searchQuery && searchQuery.trim()) {
      return;
    }
    
    loadPrompts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, sortBy, sortOrder, selectedTags, showBookmarks, token, searchQuery]);

  // Поиск с дебаунсом
  useEffect(() => {
    // Если поисковый запрос пустой, не делаем ничего (основной useEffect загрузит данные)
    if (!searchQuery || !searchQuery.trim()) {
      return;
    }

    const timer = setTimeout(() => {
      if (page === 1) {
        loadPrompts();
      } else {
        setPage(1);
      }
    }, 500);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery]);

  // Создание промпта
  const handleCreatePrompt = async () => {
    if (!token) {
      showNotification('Для создания промпта необходимо войти в систему', 'error');
      return;
    }
    
    // Валидация перед отправкой
    if (!promptForm.title || promptForm.title.trim().length < 3) {
      showNotification('Название промпта должно содержать минимум 3 символа', 'error');
      return;
    }
    
    if (!promptForm.content || promptForm.content.trim().length < 10) {
      showNotification('Текст промпта должен содержать минимум 10 символов', 'error');
      return;
    }
    
    try {
      // Подготавливаем данные для отправки
      const dataToSend = {
        title: promptForm.title.trim(),
        content: promptForm.content.trim(),
        description: promptForm.description?.trim() || null,
        is_public: promptForm.is_public,
        tag_ids: promptForm.tag_ids || [],
        new_tags: promptForm.new_tags || [],
      };
      
      const response = await fetch(
        `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(dataToSend),
        }
      );

      if (response.ok) {
        showNotification('Промпт успешно создан!', 'success');
        setShowCreateDialog(false);
        resetPromptForm();
        loadPrompts();
        loadTags(); // Перезагружаем теги, чтобы новые теги появились в списке
      } else {
        try {
          const errorData = await response.json();
          console.error('Ошибка создания промпта:', errorData);
          
          // Обработка ошибок валидации FastAPI (422)
          if (response.status === 422 && Array.isArray(errorData.detail)) {
            const validationErrors = errorData.detail.map((err: any) => {
              const field = err.loc ? err.loc.join('.') : 'поле';
              const msg = err.msg || 'Ошибка валидации';
              return `${field}: ${msg}`;
            }).join('; ');
            showNotification(`Ошибка валидации: ${validationErrors}`, 'error');
          } else {
            showNotification(errorData || 'Ошибка создания промпта', 'error');
          }
        } catch (e) {
          console.error('Ошибка парсинга ответа:', e);
          showNotification('Ошибка создания промпта', 'error');
        }
      }
    } catch (error) {
      console.error('Ошибка создания промпта:', error);
      showNotification('Ошибка создания промпта', 'error');
    }
  };

  // Обновление промпта
  const handleUpdatePrompt = async () => {
    if (!editingPrompt) return;
    if (!token) {
      showNotification('Для редактирования промпта необходимо войти в систему', 'error');
      return;
    }

    try {
      const response = await fetch(
        `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/${editingPrompt.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(promptForm),
        }
      );

      if (response.ok) {
        showNotification('Промпт успешно обновлён!', 'success');
        setShowEditDialog(false);
        setEditingPrompt(null);
        resetPromptForm();
        loadPrompts();
      } else {
        try {
          const error = await response.json();
          showNotification(error || 'Ошибка обновления промпта', 'error');
        } catch (e) {
          showNotification('Ошибка обновления промпта', 'error');
        }
      }
    } catch (error) {
      console.error('Ошибка обновления промпта:', error);
      showNotification('Ошибка обновления промпта', 'error');
    }
  };

  // Удаление промпта
  const handleDeletePrompt = async () => {
    if (!deletingPromptId) return;
    if (!token) {
      showNotification('Для удаления промпта необходимо войти в систему', 'error');
      return;
    }

    try {
      const response = await fetch(
        `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/${deletingPromptId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        showNotification('Промпт успешно удалён!', 'success');
        setShowDeleteDialog(false);
        setDeletingPromptId(null);
        loadPrompts();
      } else {
        try {
          const error = await response.json();
          showNotification(error || 'Ошибка удаления промпта', 'error');
        } catch (e) {
          showNotification('Ошибка удаления промпта', 'error');
        }
      }
    } catch (error) {
      console.error('Ошибка удаления промпта:', error);
      showNotification('Ошибка удаления промпта', 'error');
    }
  };

  // Оценка промпта
  const handleRatePrompt = async (promptId: number, rating: number) => {
    if (!token) {
      showNotification('Для оценки промпта необходимо войти в систему', 'error');
      return;
    }
    
    // Убеждаемся, что рейтинг - это число от 1 до 5
    const ratingValue = Number(rating);
    if (isNaN(ratingValue) || ratingValue < 1 || ratingValue > 5) {
      showNotification('Рейтинг должен быть от 1 до 5', 'error');
      return;
    }
    
    try {
      const response = await fetch(
        `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/${promptId}/rate`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ rating: ratingValue }),
        }
      );

      if (response.ok) {
        showNotification('Оценка сохранена!', 'success');
        loadPrompts();
      } else {
        try {
          const errorData = await response.json();
          console.error('Ошибка оценки промпта:', errorData);
          showNotification(errorData || 'Ошибка оценки промпта', 'error');
        } catch (e) {
          showNotification('Ошибка оценки промпта', 'error');
        }
      }
    } catch (error) {
      console.error('Ошибка оценки промпта:', error);
      showNotification('Ошибка оценки промпта', 'error');
    }
  };

  // Использование промпта
  const handleUsePrompt = async (prompt: Prompt) => {
    try {
      // Копируем промпт в буфер обмена
      await navigator.clipboard.writeText(prompt.content);
      showNotification('Промпт скопирован в буфер обмена!', 'success');

      // Отправляем статистику использования
      if (token) {
        await fetch(
          `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/${prompt.id}/use`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );
      }
      
      // Перезагружаем промпты, чтобы обновить счетчики
      loadPrompts();
    } catch (error) {
      console.error('Ошибка использования промпта:', error);
      showNotification('Ошибка копирования промпта', 'error');
    }
  };

  // Добавить/удалить закладку
  const handleToggleBookmark = async (prompt: Prompt) => {
    if (!token) {
      showNotification('Для работы с закладками необходимо войти в систему', 'error');
      return;
    }

    try {
      const method = prompt.is_bookmarked ? 'DELETE' : 'POST';
      const response = await fetch(
        `${getApiUrl(API_CONFIG.ENDPOINTS.CHAT)}/../prompts/${prompt.id}/bookmark`,
        {
          method,
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        showNotification(
          prompt.is_bookmarked ? 'Удалено из закладок' : 'Добавлено в закладки',
          'success'
        );
        loadPrompts(); // Обновляем список
      } else {
        showNotification('Ошибка при работе с закладками', 'error');
      }
    } catch (error) {
      console.error('Ошибка работы с закладками:', error);
      showNotification('Ошибка при работе с закладками', 'error');
    }
  };

  // Вспомогательные функции
  const showNotification = (message: string | any, severity: 'success' | 'error') => {
    // Убеждаемся, что message - это строка
    let messageStr = '';
    if (typeof message === 'string') {
      messageStr = message;
    } else if (Array.isArray(message)) {
      // Если это массив ошибок валидации
      messageStr = message.map((err: any) => {
        if (typeof err === 'string') return err;
        if (err.msg) return err.msg;
        if (err.message) return err.message;
        return JSON.stringify(err);
      }).join(', ');
    } else if (message && typeof message === 'object') {
      // Если это объект ошибки
      if (message.detail) {
        messageStr = typeof message.detail === 'string' ? message.detail : JSON.stringify(message.detail);
      } else if (message.message) {
        messageStr = message.message;
      } else if (message.msg) {
        messageStr = message.msg;
      } else {
        messageStr = JSON.stringify(message);
      }
    } else {
      messageStr = String(message || 'Произошла ошибка');
    }
    setSnackbar({ open: true, message: messageStr, severity });
  };

  const resetPromptForm = () => {
    setPromptForm({
      title: '',
      content: '',
      description: '',
      is_public: true,
      tag_ids: [],
      new_tags: [],
    });
    setNewTagInput('');
  };

  const openEditDialog = (prompt: Prompt) => {
    setEditingPrompt(prompt);
    setPromptForm({
      title: prompt.title,
      content: prompt.content,
      description: prompt.description || '',
      is_public: prompt.is_public,
      tag_ids: prompt.tags.map(t => t.id),
      new_tags: [],
    });
    setNewTagInput('');
    setShowEditDialog(true);
  };

  const openDeleteDialog = (promptId: number) => {
    setDeletingPromptId(promptId);
    setShowDeleteDialog(true);
  };

  const toggleTagFilter = (tagId: number) => {
    setSelectedTags(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
    setPage(1);
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex', bgcolor: 'background.default' }}>

      {/* Основной контент */}
      <Box 
        sx={{ 
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          marginRight: rightSidebarHidden ? 0 : (rightSidebarOpen ? 0 : '-64px'),
          transition: 'margin-right 0.3s ease',
          position: 'relative',
        }}
      >
        {/* Заголовок */}
        <Box sx={{ py: 2 }}>
          <Container maxWidth="xl">
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h4" fontWeight="bold" gutterBottom>
                Галерея Промптов
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Делитесь лучшими промптами и находите вдохновение
              </Typography>
            </Box>
          </Container>
        </Box>

        {/* Фильтры и поиск */}
        <Box sx={{ py: 2 }}>
          <Container maxWidth="xl">
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  placeholder="Поиск промптов..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon />
                      </InputAdornment>
                    ),
                  }}
                />
              </Box>
            </Box>
          </Container>
        </Box>

        {/* Список промптов */}
        <Container 
          maxWidth="xl" 
          sx={{ 
            flex: 1, 
            overflowY: 'auto', 
            py: 3,
          }}
        >
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : prompts.length === 0 ? (
          <Alert severity="info">
            Промпты не найдены. Попробуйте изменить фильтры или создайте первый промпт!
          </Alert>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }, gap: 3 }}>
            {prompts.map((prompt) => (
              <Box key={prompt.id}>
                <PromptCard
                  prompt={prompt}
                  onRate={(rating) => handleRatePrompt(prompt.id, rating)}
                  onUse={() => handleUsePrompt(prompt)}
                  onEdit={() => openEditDialog(prompt)}
                  onDelete={() => openDeleteDialog(prompt.id)}
                  onToggleBookmark={() => handleToggleBookmark(prompt)}
                  onView={loadPrompts}
                />
              </Box>
            ))}
          </Box>
        )}

        {/* Пагинация */}
        {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <Pagination
              count={totalPages}
              page={page}
              onChange={(_, value) => setPage(value)}
              color="primary"
              size="large"
            />
          </Box>
        )}
      </Container>
      </Box>

      {/* Диалог создания промпта */}
      <PromptDialog
        open={showCreateDialog}
        onClose={() => {
          setShowCreateDialog(false);
          resetPromptForm();
        }}
        onSave={handleCreatePrompt}
        promptForm={promptForm}
        setPromptForm={setPromptForm}
        allTags={allTags}
        title="Создать промпт"
        newTagInput={newTagInput}
        setNewTagInput={setNewTagInput}
      />

      {/* Диалог редактирования промпта */}
      <PromptDialog
        open={showEditDialog}
        onClose={() => {
          setShowEditDialog(false);
          setEditingPrompt(null);
          resetPromptForm();
        }}
        onSave={handleUpdatePrompt}
        promptForm={promptForm}
        setPromptForm={setPromptForm}
        allTags={allTags}
        title="Редактировать промпт"
        newTagInput={newTagInput}
        setNewTagInput={setNewTagInput}
      />

      {/* Диалог удаления */}
      <Dialog open={showDeleteDialog} onClose={() => setShowDeleteDialog(false)}>
        <DialogTitle>Удалить промпт?</DialogTitle>
        <DialogContent>
          Вы уверены, что хотите удалить этот промпт? Это действие нельзя отменить.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDeleteDialog(false)}>Отмена</Button>
          <Button onClick={handleDeletePrompt} color="error" variant="contained">
            Удалить
          </Button>
        </DialogActions>
      </Dialog>

      {/* Уведомления */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Правый сайдбар с кнопками */}
      {!rightSidebarHidden && (
      <Drawer
        variant="persistent"
        anchor="right"
        open={true}
        sx={{
          width: rightSidebarOpen ? 280 : 64,
          flexShrink: 0,
          transition: 'width 0.3s ease',
          '& .MuiDrawer-paper': {
            width: rightSidebarOpen ? 280 : 64,
            boxSizing: 'border-box',
            background: rightSidebarOpen 
              ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
              : 'background.default',
            color: rightSidebarOpen ? 'white' : 'text.primary',
            borderLeft: '1px solid',
            borderColor: 'divider',
            transition: 'width 0.3s ease, background 0.3s ease, color 0.3s ease',
            overflowX: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        {/* Заголовок */}
        <Box
          sx={{
            p: rightSidebarOpen ? 2 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: rightSidebarOpen ? 'space-between' : 'center',
            background: rightSidebarOpen ? 'rgba(0,0,0,0.1)' : 'transparent',
            minHeight: 64,
          }}
        >
          {rightSidebarOpen && (
            <Typography variant="h6" fontWeight="bold" sx={{ color: 'white' }}>
              Действия
            </Typography>
          )}
          <IconButton
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            sx={{
              color: rightSidebarOpen ? 'white' : 'text.primary',
              '&:hover': {
                backgroundColor: rightSidebarOpen 
                  ? 'rgba(255,255,255,0.1)' 
                  : 'action.hover',
              },
            }}
          >
            <MenuIcon />
          </IconButton>
        </Box>

        {rightSidebarOpen && <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />}

        {/* Кнопки */}
        <Box sx={{ 
          p: rightSidebarOpen ? 2 : 1, 
          display: 'flex', 
          flexDirection: 'column', 
          gap: rightSidebarOpen ? 2 : 1,
          flex: 1,
        }}>
          {/* Кнопка "Создать промпт" */}
          <Tooltip title={rightSidebarOpen ? '' : 'Создать промпт'} placement="left">
            <Button
              fullWidth={rightSidebarOpen}
              variant={rightSidebarOpen ? 'contained' : 'text'}
              startIcon={<AddIcon />}
              onClick={() => {
                setShowCreateDialog(true);
              }}
              sx={{
                bgcolor: rightSidebarOpen ? 'rgba(255,255,255,0.2)' : 'transparent',
                color: rightSidebarOpen ? 'white' : 'text.primary',
                opacity: !rightSidebarOpen ? 0.7 : 1,
                '&:hover': {
                  bgcolor: rightSidebarOpen 
                    ? 'rgba(255,255,255,0.3)' 
                    : (isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'),
                  opacity: 1,
                  '& .MuiSvgIcon-root': !rightSidebarOpen ? {
                    color: 'primary.main',
                  } : {},
                },
                textTransform: 'none',
                py: rightSidebarOpen ? 1.5 : 1,
                minWidth: rightSidebarOpen ? 'auto' : 40,
                width: rightSidebarOpen ? '100%' : 40,
                justifyContent: rightSidebarOpen ? 'flex-start' : 'center',
                '& .MuiButton-startIcon': {
                  margin: rightSidebarOpen ? '0 8px 0 0' : 0,
                },
              }}
            >
              {rightSidebarOpen && 'Создать промпт'}
            </Button>
          </Tooltip>

          {/* Кнопка "Мои закладки" */}
          {token && (
            <Tooltip title={rightSidebarOpen ? '' : (showBookmarks ? 'Все промпты' : 'Мои закладки')} placement="left">
              <Button
                fullWidth={rightSidebarOpen}
                variant={rightSidebarOpen ? (showBookmarks ? 'contained' : 'outlined') : 'text'}
                startIcon={<BookmarkIcon />}
                onClick={() => {
                  setShowBookmarks(!showBookmarks);
                }}
                sx={{
                  bgcolor: rightSidebarOpen 
                    ? (showBookmarks ? 'rgba(255,255,255,0.2)' : 'transparent')
                    : 'transparent',
                  color: rightSidebarOpen ? 'white' : 'text.primary',
                  borderColor: rightSidebarOpen ? 'rgba(255,255,255,0.3)' : 'transparent',
                  opacity: !rightSidebarOpen ? 0.7 : 1,
                  '&:hover': {
                    bgcolor: rightSidebarOpen 
                      ? 'rgba(255,255,255,0.2)' 
                      : (isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'),
                    borderColor: rightSidebarOpen ? 'rgba(255,255,255,0.5)' : 'transparent',
                    opacity: 1,
                    '& .MuiSvgIcon-root': !rightSidebarOpen ? {
                      color: 'primary.main',
                    } : {},
                  },
                  textTransform: 'none',
                  py: rightSidebarOpen ? 1.5 : 1,
                  minWidth: rightSidebarOpen ? 'auto' : 40,
                  width: rightSidebarOpen ? '100%' : 40,
                  justifyContent: rightSidebarOpen ? 'flex-start' : 'center',
                  '& .MuiButton-startIcon': {
                    margin: rightSidebarOpen ? '0 8px 0 0' : 0,
                  },
                }}
              >
                {rightSidebarOpen && (showBookmarks ? 'Все промпты' : 'Мои закладки')}
              </Button>
            </Tooltip>
          )}

          {/* Кнопка "Фильтры" */}
          <Tooltip title={rightSidebarOpen ? '' : 'Фильтры'} placement="left">
            <Button
              fullWidth={rightSidebarOpen}
              variant={rightSidebarOpen ? 'outlined' : 'text'}
              startIcon={<FilterListIcon />}
              onClick={(e) => {
                setFiltersAnchorEl(e.currentTarget);
              }}
              sx={{
                bgcolor: rightSidebarOpen && selectedTags.length > 0 
                  ? 'rgba(255,255,255,0.2)' 
                  : 'transparent',
                color: rightSidebarOpen ? 'white' : 'text.primary',
                borderColor: rightSidebarOpen ? 'rgba(255,255,255,0.3)' : 'transparent',
                opacity: !rightSidebarOpen ? 0.7 : 1,
                '&:hover': {
                  bgcolor: rightSidebarOpen 
                    ? 'rgba(255,255,255,0.2)' 
                    : (isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'),
                  borderColor: rightSidebarOpen ? 'rgba(255,255,255,0.5)' : 'transparent',
                  opacity: 1,
                  '& .MuiSvgIcon-root': !rightSidebarOpen ? {
                    color: 'primary.main',
                  } : {},
                },
                textTransform: 'none',
                py: rightSidebarOpen ? 1.5 : 1,
                minWidth: rightSidebarOpen ? 'auto' : 40,
                width: rightSidebarOpen ? '100%' : 40,
                justifyContent: rightSidebarOpen ? 'flex-start' : 'center',
                position: 'relative',
                '& .MuiButton-startIcon': {
                  margin: rightSidebarOpen ? '0 8px 0 0' : 0,
                },
              }}
            >
              {rightSidebarOpen && 'Фильтры'}
              {selectedTags.length > 0 && rightSidebarOpen && (
                <Chip
                  label={selectedTags.length}
                  size="small"
                  sx={{
                    ml: 1,
                    height: 20,
                    minWidth: 20,
                    bgcolor: 'rgba(255,255,255,0.3)',
                    color: 'white',
                    fontSize: '0.75rem',
                    '& .MuiChip-label': {
                      px: 0.5,
                    },
                  }}
                />
              )}
              {selectedTags.length > 0 && !rightSidebarOpen && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: 4,
                    right: 4,
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: 'primary.main',
                  }}
                />
              )}
            </Button>
          </Tooltip>
        </Box>

        {/* Кнопка "Скрыть панель" внизу узкой панели */}
        {!rightSidebarOpen && (
          <Box sx={{ 
            p: 1, 
            display: 'flex', 
            justifyContent: 'center',
            mt: 'auto',
          }}>
            <Tooltip title="Скрыть панель" placement="left">
              <IconButton
                onClick={() => setRightSidebarHidden(true)}
                sx={{
                  color: 'text.primary',
                  opacity: 0.7,
                  '&:hover': {
                    backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    opacity: 1,
                    '& .MuiSvgIcon-root': {
                      color: 'primary.main',
                    },
                  },
                }}
              >
                <ChevronRightIcon />
              </IconButton>
            </Tooltip>
          </Box>
        )}
      </Drawer>
      )}

      {/* Кнопка для показа скрытой панели */}
      {rightSidebarHidden && (
        <Box
          sx={{
            position: 'fixed',
            right: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 1200,
          }}
        >
          <Tooltip title="Показать панель" placement="left">
            <IconButton
              onClick={() => {
                setRightSidebarHidden(false);
                setRightSidebarOpen(false);
              }}
              sx={{
                bgcolor: 'background.paper',
                color: 'text.primary',
                borderRadius: '8px 0 0 8px',
                boxShadow: 2,
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              <ChevronRightIcon sx={{ transform: 'rotate(180deg)' }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Выпадающее меню с фильтрами */}
      <Popover
        open={Boolean(filtersAnchorEl)}
        anchorEl={filtersAnchorEl}
        onClose={() => setFiltersAnchorEl(null)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            width: { xs: '90vw', sm: 400 },
            maxWidth: 400,
            maxHeight: '80vh',
            mt: 1,
            p: 2,
          },
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Заголовок */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="h6" fontWeight="bold">
              Фильтры
            </Typography>
            <IconButton 
              size="small" 
              onClick={() => setFiltersAnchorEl(null)}
            >
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Сортировка */}
          <Box>
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
              Сортировка
            </Typography>
            <FormControl fullWidth size="small">
              <InputLabel>Сортировать по</InputLabel>
              <Select
                value={sortBy}
                label="Сортировать по"
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
                disabled={showBookmarks}
              >
                <MenuItem value="rating">По рейтингу</MenuItem>
                <MenuItem value="date">По дате</MenuItem>
                <MenuItem value="usage">По использованию</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {/* Теги */}
          <Box>
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
              Теги
            </Typography>
            <FormControl fullWidth size="small">
              <InputLabel>Теги</InputLabel>
              <Select
                multiple
                value={selectedTags}
                label="Теги"
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedTags(typeof value === 'string' ? [] : value);
                  setPage(1);
                }}
                disabled={showBookmarks}
                renderValue={(selected) => {
                  if (selected.length === 0) {
                    return <Typography variant="body2" color="text.secondary">Выберите теги</Typography>;
                  }
                  if (selected.length === 1) {
                    const tag = allTags.find(t => t.id === selected[0]);
                    return tag ? tag.name : '';
                  }
                  return `${selected.length} тегов выбрано`;
                }}
                MenuProps={{
                  PaperProps: {
                    style: {
                      maxHeight: 400,
                      width: 350,
                    },
                  },
                }}
              >
                {allTags.length === 0 ? (
                  <MenuItem disabled>
                    <Typography variant="body2" color="text.secondary">
                      Загрузка тегов...
                    </Typography>
                  </MenuItem>
                ) : (
                  allTags.map((tag) => (
                    <MenuItem key={tag.id} value={tag.id}>
                      <Checkbox checked={selectedTags.includes(tag.id)} />
                      <Box sx={{ ml: 1, flex: 1 }}>
                        <Typography variant="body2">
                          {tag.name}
                        </Typography>
                        {tag.description && (
                          <Typography 
                            variant="caption" 
                            color="text.secondary" 
                            display="block"
                            sx={{ mt: 0.25, lineHeight: 1.4 }}
                          >
                            {tag.description}
                          </Typography>
                        )}
                      </Box>
                    </MenuItem>
                  ))
                )}
              </Select>
            </FormControl>
            {selectedTags.length > 0 && (
              <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  onClick={() => {
                    setSelectedTags([]);
                    setPage(1);
                  }}
                >
                  Очистить
                </Button>
              </Box>
            )}
          </Box>
        </Box>
      </Popover>
    </Box>
  );
}

// Компонент карточки промпта
interface PromptCardProps {
  prompt: Prompt;
  onRate: (rating: number) => void;
  onUse: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggleBookmark: () => void;
  onView?: () => void;
}

function PromptCard({ prompt, onRate, onUse, onEdit, onDelete, onToggleBookmark, onView }: PromptCardProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const { user, token } = useAuth();
  const theme = useTheme();
  const isDarkMode = theme.palette.mode === 'dark';
  
  // Проверяем авторство: сравниваем author_id с user_id или username (если user_id нет)
  // Нормализуем для сравнения (lowercase, trim)
  const normalizeId = (id: string | undefined) => id ? id.trim().toLowerCase() : '';
  const isAuthor = user && (
    normalizeId(prompt.author_id) === normalizeId(user.user_id) || 
    normalizeId(prompt.author_id) === normalizeId(user.username)
  );
  
  // Проверяем, нужно ли показывать кнопку "Показать больше"
  const lines = prompt.content.split('\n');
  const hasMoreThan2Lines = lines.length > 2 || prompt.content.length > 150;
  
  // Обработчик открытия модального окна
  const handleViewPrompt = () => {
    // Сначала открываем модальное окно синхронно
    setShowViewDialog(true);
    
    // Увеличиваем счетчик просмотров при открытии (асинхронно, в фоне)
    // Не вызываем onView здесь, чтобы не перезагружать список и не закрывать модальное окно
    (async () => {
      try {
        const headers: HeadersInit = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        
        await fetch(
          `${API_CONFIG.BASE_URL}/api/prompts/${prompt.id}/view`,
          {
            method: 'POST',
            headers,
          }
        );
        // Счетчик обновится при следующей загрузке промптов (например, при закрытии модального окна)
      } catch (error) {
        console.error('Ошибка увеличения просмотров:', error);
      }
    })();
  };
  
  // Обработчик закрытия модального окна
  const handleCloseViewDialog = () => {
    setShowViewDialog(false);
    // Обновляем список промптов после закрытия, чтобы обновить счетчик просмотров
    if (onView) {
      onView();
    }
  };

  return (
    <Card sx={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column',
      backgroundColor: isDarkMode ? undefined : '#ffffff',
      boxShadow: isDarkMode ? undefined : '0 2px 8px rgba(0,0,0,0.1)',
      border: isDarkMode ? undefined : '1px solid rgba(0,0,0,0.08)',
    }}>
      <CardContent sx={{ flex: 1 }}>
        {/* Заголовок, закладка и меню */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="h6" component="div" sx={{ flex: 1, fontWeight: 'bold' }}>
            {prompt.title}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {/* Кнопка закладки */}
            <Tooltip title={prompt.is_bookmarked ? 'Удалить из закладок' : 'Добавить в закладки'}>
              <IconButton size="small" onClick={onToggleBookmark}>
                {prompt.is_bookmarked ? (
                  <BookmarkIcon fontSize="small" color="primary" />
                ) : (
                  <BookmarkBorderIcon fontSize="small" />
                )}
              </IconButton>
            </Tooltip>
            
            {/* Меню опций */}
            <IconButton size="small" onClick={(e) => setAnchorEl(e.currentTarget)}>
              <MoreVertIcon />
            </IconButton>
          </Box>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
          >
            {isAuthor && <MenuItem onClick={() => { onEdit(); setAnchorEl(null); }}><EditIcon sx={{ mr: 1 }} fontSize="small" />Редактировать</MenuItem>}
            {isAuthor && <MenuItem onClick={() => { onDelete(); setAnchorEl(null); }}><DeleteIcon sx={{ mr: 1 }} fontSize="small" />Удалить</MenuItem>}
          </Menu>
        </Box>

        {/* Автор */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
          <PersonIcon fontSize="small" color="action" />
          <Typography variant="caption" color="text.secondary">
            {prompt.author_name}
          </Typography>
        </Box>

        {/* Описание */}
        {prompt.description && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {prompt.description}
          </Typography>
        )}
        
        {/* Сам промпт (контент) */}
        <Box sx={{ 
          mb: 2, 
          p: 1.5, 
          bgcolor: isDarkMode ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.04)', 
          borderRadius: 1, 
          border: '1px solid', 
          borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)'
        }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
              Промпт:
            </Typography>
            {hasMoreThan2Lines && (
              <Button
                size="small"
                endIcon={<ExpandMoreIcon />}
                onClick={handleViewPrompt}
                sx={{ minWidth: 'auto', p: 0.5 }}
              >
                Показать больше
              </Button>
            )}
          </Box>
          <Typography 
            variant="body2" 
            sx={{ 
              whiteSpace: 'pre-wrap', 
              wordBreak: 'break-word',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              lineHeight: 1.6,
              color: isDarkMode ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.87)',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {prompt.content}
          </Typography>
        </Box>

        {/* Теги */}
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
          {prompt.tags.map((tag) => (
            <Chip
              key={tag.id}
              label={tag.name}
              size="small"
              sx={{ 
                bgcolor: tag.color || (isDarkMode ? 'primary.light' : 'primary.main'), 
                color: 'white', 
                fontWeight: 500 
              }}
            />
          ))}
        </Stack>

        {/* Рейтинг */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Rating
            value={prompt.average_rating}
            onChange={(_, value) => {
              if (value !== null) {
                // Округляем до целого числа, так как API ожидает целое число от 1 до 5
                onRate(Math.round(value));
              }
            }}
            precision={0.1}
            readOnly={!!prompt.user_rating} // Делаем readOnly, если пользователь уже голосовал
          />
          <Typography variant="caption" color="text.secondary">
            {prompt.average_rating.toFixed(1)} ({prompt.total_votes})
            {prompt.user_rating && ` • Ваша оценка: ${prompt.user_rating}`}
          </Typography>
        </Box>

        {/* Статистика */}
        <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
          <Tooltip title="Просмотров">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ViewIcon fontSize="small" color="action" />
              <Typography variant="caption">{prompt.views_count}</Typography>
            </Box>
          </Tooltip>
          <Tooltip title="Использований">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <TrendingUpIcon fontSize="small" color="action" />
              <Typography variant="caption">{prompt.usage_count}</Typography>
            </Box>
          </Tooltip>
        </Box>
      </CardContent>

      <CardActions>
        <Button
          size="small"
          startIcon={<CopyIcon />}
          onClick={onUse}
          fullWidth
          variant="contained"
        >
          Использовать
        </Button>
      </CardActions>
      
      {/* Модальное окно для просмотра промпта */}
      <Dialog 
        open={showViewDialog} 
        onClose={handleCloseViewDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h5" component="div" sx={{ fontWeight: 'bold' }}>
              {prompt.title}
            </Typography>
            <IconButton
              edge="end"
              color="inherit"
              onClick={handleCloseViewDialog}
              aria-label="close"
            >
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Stack spacing={3}>
            {/* Автор */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <PersonIcon fontSize="small" color="action" />
              <Typography variant="body2" color="text.secondary">
                Автор: {prompt.author_name}
              </Typography>
            </Box>
            
            {/* Описание */}
            {prompt.description && (
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Описание:
                </Typography>
                <Typography variant="body1">
                  {prompt.description}
                </Typography>
              </Box>
            )}
            
            {/* Содержание промпта */}
            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Промпт:
              </Typography>
              <Box sx={{ 
                p: 2, 
                bgcolor: isDarkMode ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.04)', 
                borderRadius: 1, 
                border: '1px solid', 
                borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)'
              }}>
                <Typography 
                  variant="body1" 
                  sx={{ 
                    whiteSpace: 'pre-wrap', 
                    wordBreak: 'break-word',
                    fontFamily: 'monospace',
                    fontSize: '0.9rem',
                    lineHeight: 1.8,
                    color: isDarkMode ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.87)'
                  }}
                >
                  {prompt.content}
                </Typography>
              </Box>
            </Box>
            
            {/* Теги */}
            {prompt.tags.length > 0 && (
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Теги:
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {prompt.tags.map((tag) => (
                    <Chip
                      key={tag.id}
                      label={tag.name}
                      size="medium"
                      sx={{ 
                        bgcolor: tag.color || (isDarkMode ? 'primary.light' : 'primary.main'), 
                        color: 'white', 
                        fontWeight: 500 
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            )}
            
            {/* Рейтинг */}
            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Рейтинг:
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Rating
                  value={prompt.average_rating}
                  onChange={(_, value) => {
                    if (value !== null) {
                      onRate(Math.round(value));
                    }
                  }}
                  precision={0.1}
                  readOnly={!!prompt.user_rating}
                  size="large"
                />
                <Typography variant="body1" color="text.secondary">
                  {prompt.average_rating.toFixed(1)} ({prompt.total_votes} {prompt.total_votes === 1 ? 'оценка' : 'оценок'})
                  {prompt.user_rating && ` • Ваша оценка: ${prompt.user_rating}`}
                </Typography>
              </Box>
            </Box>
            
            {/* Статистика */}
            <Box sx={{ display: 'flex', gap: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ViewIcon fontSize="small" color="action" />
                <Typography variant="body2" color="text.secondary">
                  Просмотров: {prompt.views_count}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUpIcon fontSize="small" color="action" />
                <Typography variant="body2" color="text.secondary">
                  Использований: {prompt.usage_count}
                </Typography>
              </Box>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseViewDialog}>
            Закрыть
          </Button>
          <Button 
            onClick={() => {
              onUse();
              handleCloseViewDialog();
            }} 
            variant="contained"
            startIcon={<CopyIcon />}
          >
            Использовать
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

// Компонент диалога создания/редактирования
interface PromptDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  promptForm: any;
  setPromptForm: React.Dispatch<React.SetStateAction<any>>;
  allTags: Tag[];
  title: string;
  newTagInput: string;
  setNewTagInput: React.Dispatch<React.SetStateAction<string>>;
}

function PromptDialog({ open, onClose, onSave, promptForm, setPromptForm, allTags, title, newTagInput, setNewTagInput }: PromptDialogProps) {
  const handleAddNewTag = () => {
    const tagName = newTagInput.trim();
    if (tagName && !promptForm.new_tags.includes(tagName)) {
      setPromptForm({ 
        ...promptForm, 
        new_tags: [...promptForm.new_tags, tagName] 
      });
      setNewTagInput('');
    }
  };

  const handleRemoveNewTag = (tagToRemove: string) => {
    setPromptForm({
      ...promptForm,
      new_tags: promptForm.new_tags.filter((tag: string) => tag !== tagToRemove)
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddNewTag();
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Название"
            fullWidth
            required
            value={promptForm.title}
            onChange={(e) => setPromptForm({ ...promptForm, title: e.target.value })}
          />
          
          <TextField
            label="Описание"
            fullWidth
            multiline
            rows={2}
            value={promptForm.description}
            onChange={(e) => setPromptForm({ ...promptForm, description: e.target.value })}
          />

          <TextField
            label="Промпт"
            fullWidth
            required
            multiline
            rows={10}
            value={promptForm.content}
            onChange={(e) => setPromptForm({ ...promptForm, content: e.target.value })}
          />

          <FormControl fullWidth>
            <InputLabel>Существующие теги</InputLabel>
            <Select
              multiple
              value={promptForm.tag_ids}
              label="Существующие теги"
              onChange={(e) => setPromptForm({ ...promptForm, tag_ids: e.target.value as number[] })}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {(selected as number[]).map((tagId) => {
                    const tag = allTags.find(t => t.id === tagId);
                    return tag ? <Chip key={tagId} label={tag.name} size="small" /> : null;
                  })}
                </Box>
              )}
            >
              {allTags.map((tag) => (
                <MenuItem key={tag.id} value={tag.id}>
                  {tag.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Поле для создания новых тегов */}
          <Box>
            <TextField
              label="Создать новый тег"
              fullWidth
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Введите название тега и нажмите Enter"
              InputProps={{
                endAdornment: (
                  <Button
                    size="small"
                    onClick={handleAddNewTag}
                    disabled={!newTagInput.trim()}
                  >
                    Добавить
                  </Button>
                ),
              }}
              helperText="Можно добавить несколько тегов, каждый новый тег - новая запись"
            />

            {/* Показываем добавленные новые теги */}
            {promptForm.new_tags.length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Новые теги:
                </Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                  {promptForm.new_tags.map((tag: string, index: number) => (
                    <Chip
                      key={index}
                      label={tag}
                      size="small"
                      onDelete={() => handleRemoveNewTag(tag)}
                      color="primary"
                      variant="outlined"
                    />
                  ))}
                </Stack>
              </Box>
            )}
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button onClick={onSave} variant="contained">
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
}

