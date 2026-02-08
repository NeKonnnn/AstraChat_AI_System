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
  FormControlLabel,
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
  Tabs,
  Tab,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Slider,
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
  ChevronRight as ChevronRightIcon,
  SmartToy as AgentIcon,
  AutoAwesome as PromptIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { getApiUrl, API_ENDPOINTS } from '../config/api';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';

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

interface Agent {
  id: number;
  name: string;
  description?: string;
  system_prompt: string;
  config?: Record<string, any>;
  tools?: string[];
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
  const navigate = useNavigate();
  
  // Состояние для вкладок
  const [activeTab, setActiveTab] = useState(0); // 0 = промпты, 1 = агенты
  
  // Состояние для промптов
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Состояние для агентов
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsPage, setAgentsPage] = useState(1);
  const [agentsTotalPages, setAgentsTotalPages] = useState(1);

  // Состояние для фильтров
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [sortBy, setSortBy] = useState('rating');
  const [sortOrder] = useState('desc');
  const [showBookmarks, setShowBookmarks] = useState(false);

  // Состояние для тегов
  const [allTags, setAllTags] = useState<Tag[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [popularTags, setPopularTags] = useState<Array<{ tag: Tag; count: number }>>([]);

  // Состояние для диалогов
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deletingPromptId, setDeletingPromptId] = useState<number | null>(null);
  
  // Состояние для диалогов агентов
  const [showCreateAgentDialog, setShowCreateAgentDialog] = useState(false);
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
  
  // Состояние для создания агента
  const [agentForm, setAgentForm] = useState({
    name: '',
    description: '',
    system_prompt: '',
    config: {
      model_path: '',
      model_settings: {
        context_size: 2048,
        output_tokens: 512,
        temperature: 0.7,
        top_p: 0.95,
        repeat_penalty: 1.05,
        use_gpu: false,
        streaming: true,
        streaming_speed: 50,
      },
    } as Record<string, any>,
    tools: [] as string[],
    is_public: true,
    tag_ids: [] as number[],
    new_tags: [] as string[],
  });
  
  // Состояние для доступных моделей
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [availableModels, setAvailableModels] = useState<Array<{
    name: string;
    path: string;
    size?: number;
    size_mb?: number;
  }>>([]);
  
  // Состояние для ввода нового тега
  const [newTagInput, setNewTagInput] = useState('');
  const [newAgentTagInput, setNewAgentTagInput] = useState('');

  // Уведомления
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });

  // Флаг для предотвращения одновременных загрузок
  const isLoadingRef = useRef(false);
  const isAgentsLoadingRef = useRef(false);
  // Флаг для отслеживания первого рендера
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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
      let url = `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/`;
      
      // Если показываем закладки, используем другой endpoint
      if (showBookmarks) {
        if (!token) {
          showNotification('Для просмотра закладок необходимо войти в систему', 'error');
          setPrompts([]);
          setTotalPages(0);
          setLoading(false);
          return;
        }
        url = `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/my/bookmarks`;
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
        fetch(`${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/tags/all`),
        fetch(`${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/tags/popular?limit=20`),
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
    loadAvailableModels();
  }, []);

  // Загрузка доступных моделей
  const loadAvailableModels = async () => {
    try {
      const response = await fetch(`${getApiUrl(API_ENDPOINTS.CHAT)}/../models/available`);
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки моделей:', error);
    }
  };

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
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/`,
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
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/${editingPrompt.id}`,
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
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/${deletingPromptId}`,
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
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/${promptId}/rate`,
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
          `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/${prompt.id}/use`,
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
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../prompts/${prompt.id}/bookmark`,
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

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const toggleTagFilter = (tagId: number) => {
    setSelectedTags(prev =>
      prev.includes(tagId) ? prev.filter(id => id !== tagId) : [...prev, tagId]
    );
    setPage(1);
  };

  // ===================================
  // ФУНКЦИИ ДЛЯ РАБОТЫ С АГЕНТАМИ
  // ===================================

  // Загрузка агентов
  const loadAgents = useCallback(async () => {
    if (isAgentsLoadingRef.current) {
      return;
    }
    
    isAgentsLoadingRef.current = true;
    setAgentsLoading(true);
    try {
      let url = `${getApiUrl(API_ENDPOINTS.CHAT)}/../agents/`;
      
      const params = new URLSearchParams({
        page: agentsPage.toString(),
        limit: '20',
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      
      if (searchQuery) params.append('search', searchQuery);
      if (selectedTags.length > 0) params.append('tags', selectedTags.join(','));

      const headers: HeadersInit = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(`${url}?${params}`, { headers });

      if (response.ok) {
        const data = await response.json();
        const agentsWithTags = (data.agents || []).map((a: any) => ({
          ...a,
          tags: a.tags || []
        }));
        
        setAgents(agentsWithTags);
        setAgentsTotalPages(data.pages || 1);
      } else {
        setAgents([]);
        setAgentsTotalPages(0);
      }
    } catch (error) {
      console.error('Ошибка загрузки агентов:', error);
      setAgents([]);
      setAgentsTotalPages(0);
    } finally {
      setAgentsLoading(false);
      isAgentsLoadingRef.current = false;
    }
  }, [agentsPage, sortBy, sortOrder, searchQuery, selectedTags, token]);

  // Загрузка агентов при изменении параметров
  useEffect(() => {
    if (activeTab === 1) { // Вкладка агентов
      if (!searchQuery || !searchQuery.trim()) {
        loadAgents();
      }
    }
  }, [agentsPage, sortBy, sortOrder, selectedTags, activeTab, loadAgents]);

  // Поиск агентов с дебаунсом
  useEffect(() => {
    if (activeTab !== 1 || !searchQuery || !searchQuery.trim()) {
      return;
    }

    const timer = setTimeout(() => {
      if (agentsPage === 1) {
        loadAgents();
      } else {
        setAgentsPage(1);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [searchQuery, activeTab, agentsPage, loadAgents]);

  // Обработка переключения вкладок
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
    setPage(1);
    setAgentsPage(1);
    if (newValue === 0) {
      loadPrompts();
    } else {
      loadAgents();
    }
  };

  // Создание агента
  const handleCreateAgent = async () => {
    if (!token) {
      showNotification('Для создания агента необходимо войти в систему', 'error');
      return;
    }
    
    // Валидация
    if (!agentForm.name || agentForm.name.trim().length < 3) {
      showNotification('Название агента должно содержать минимум 3 символа', 'error');
      return;
    }
    
    if (!agentForm.system_prompt || agentForm.system_prompt.trim().length < 10) {
      showNotification('Системный промпт должен содержать минимум 10 символов', 'error');
      return;
    }
    
    try {
      const dataToSend = {
        name: agentForm.name.trim(),
        description: agentForm.description?.trim() || null,
        system_prompt: agentForm.system_prompt.trim(),
        config: agentForm.config || {},
        tools: agentForm.tools || [],
        is_public: agentForm.is_public,
        tag_ids: agentForm.tag_ids || [],
        new_tags: agentForm.new_tags || [],
      };
      
      const response = await fetch(
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../agents/`,
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
        showNotification('Агент успешно создан!', 'success');
        setShowCreateAgentDialog(false);
        resetAgentForm();
        loadAgents();
        loadTags(); // Перезагружаем теги, чтобы новые теги появились в списке
      } else {
        try {
          const errorData = await response.json();
          showNotification(errorData.detail || 'Ошибка создания агента', 'error');
        } catch (e) {
          showNotification('Ошибка создания агента', 'error');
        }
      }
    } catch (error) {
      console.error('Ошибка создания агента:', error);
      showNotification('Ошибка создания агента', 'error');
    }
  };

  const resetAgentForm = () => {
    setAgentForm({
      name: '',
      description: '',
      system_prompt: '',
      config: {
        model_path: '',
        model_settings: {
          context_size: 2048,
          output_tokens: 512,
          temperature: 0.7,
          top_p: 0.95,
          repeat_penalty: 1.05,
          use_gpu: false,
          streaming: true,
          streaming_speed: 50,
        },
      },
      tools: [],
      is_public: true,
      tag_ids: [],
      new_tags: [],
    });
    setNewAgentTagInput('');
  };

  // Использование агента
  const handleUseAgent = async (agent: Agent) => {
    try {
      // Сохраняем агента в localStorage для применения в чате
      localStorage.setItem('selectedAgent', JSON.stringify({
        id: agent.id,
        name: agent.name,
        system_prompt: agent.system_prompt,
        config: agent.config,
        tools: agent.tools,
      }));

      // Применяем системный промпт и настройки агента через API
      if (token) {
        try {
          // Применяем системный промпт
          const promptResponse = await fetch(
            `${getApiUrl(API_ENDPOINTS.CHAT)}/../context-prompts/global`,
            {
              method: 'PUT',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
              },
              body: JSON.stringify({ prompt: agent.system_prompt }),
            }
          );

          // Применяем настройки модели, если они указаны
          if (agent.config?.model_settings) {
            try {
              await fetch(
                `${getApiUrl(API_ENDPOINTS.CHAT)}/../models/settings`,
                {
                  method: 'PUT',
                  headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                  },
                  body: JSON.stringify(agent.config.model_settings),
                }
              );
            } catch (error) {
              console.warn('Не удалось применить настройки модели:', error);
            }
          }

          // Загружаем указанную модель, если она указана
          if (agent.config?.model_path) {
            try {
              await fetch(
                `${getApiUrl(API_ENDPOINTS.CHAT)}/../models/load`,
                {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                  },
                  body: JSON.stringify({ model_path: agent.config.model_path }),
                }
              );
            } catch (error) {
              console.warn('Не удалось загрузить модель:', error);
            }
          }

          if (promptResponse.ok) {
            showNotification(`Агент "${agent.name}" применён! Переходим в чат...`, 'success');
            
            // Увеличиваем счетчик использований
            await fetch(
              `${getApiUrl(API_ENDPOINTS.CHAT)}/../agents/${agent.id}/use`,
              {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`,
                },
              }
            );
            
            // Переходим в чат через небольшую задержку, чтобы пользователь увидел уведомление
            setTimeout(() => {
              navigate('/');
              loadAgents(); // Обновляем список для обновления счетчиков
            }, 1000);
          } else {
            // Если не удалось применить через API, просто сохраняем в localStorage
            showNotification(`Агент "${agent.name}" сохранён! Переходим в чат...`, 'success');
            setTimeout(() => {
              navigate('/');
              loadAgents();
            }, 1000);
          }
        } catch (error) {
          console.error('Ошибка применения агента:', error);
          // В случае ошибки все равно переходим в чат
          showNotification(`Агент "${agent.name}" сохранён! Переходим в чат...`, 'success');
          setTimeout(() => {
            navigate('/');
            loadAgents();
          }, 1000);
        }
      } else {
        // Если пользователь не авторизован, просто переходим в чат
        showNotification(`Агент "${agent.name}" сохранён! Переходим в чат...`, 'success');
        setTimeout(() => {
          navigate('/');
          loadAgents();
        }, 1000);
      }
    } catch (error) {
      console.error('Ошибка использования агента:', error);
      showNotification('Ошибка использования агента', 'error');
    }
  };

  // Добавить/удалить закладку агента
  const handleToggleAgentBookmark = async (agent: Agent) => {
    if (!token) {
      showNotification('Для работы с закладками необходимо войти в систему', 'error');
      return;
    }

    try {
      const method = agent.is_bookmarked ? 'DELETE' : 'POST';
      const response = await fetch(
        `${getApiUrl(API_ENDPOINTS.CHAT)}/../agents/${agent.id}/bookmark`,
        {
          method,
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        showNotification(
          agent.is_bookmarked ? 'Удалено из закладок' : 'Добавлено в закладки',
          'success'
        );
        loadAgents(); // Обновляем список
      } else {
        showNotification('Ошибка при работе с закладками', 'error');
      }
    } catch (error) {
      console.error('Ошибка работы с закладками:', error);
      showNotification('Ошибка при работе с закладками', 'error');
    }
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
                Галерея Промптов и Агентов
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Делитесь лучшими промптами и создавайте собственных ИИ агентов
              </Typography>
            </Box>
          </Container>
        </Box>

        {/* Вкладки */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Container maxWidth="xl">
            <Tabs 
              value={activeTab} 
              onChange={handleTabChange}
              variant="fullWidth"
              textColor="primary"
              indicatorColor="primary"
            >
              <Tab icon={<PromptIcon />} label="Промпты" iconPosition="start" />
              <Tab icon={<AgentIcon />} label="Агенты" iconPosition="start" />
            </Tabs>
          </Container>
        </Box>

        {/* Фильтры и поиск */}
        <Box sx={{ py: 2 }}>
          <Container maxWidth="xl">
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
              <Box sx={{ flex: '1 1 300px', minWidth: '250px' }}>
                <TextField
                  fullWidth
                  placeholder={activeTab === 0 ? "Поиск промптов..." : "Поиск агентов..."}
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

        {/* Контент в зависимости от вкладки */}
        <Container 
          maxWidth="xl" 
          sx={{ 
            flex: 1, 
            overflowY: 'auto', 
            py: 3,
          }}
        >
        {activeTab === 0 ? (
          // Вкладка промптов
          <>
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

            {/* Пагинация для промптов */}
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
          </>
        ) : (
          // Вкладка агентов
          <>
            {agentsLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                <CircularProgress />
              </Box>
            ) : agents.length === 0 ? (
              <Alert severity="info">
                Агенты не найдены. Попробуйте изменить фильтры или создайте первого агента!
              </Alert>
            ) : (
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }, gap: 3 }}>
                {agents.map((agent) => (
                  <Card key={agent.id} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                    <CardContent sx={{ flexGrow: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                        <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
                          {agent.name}
                        </Typography>
                        <IconButton size="small">
                          <MoreVertIcon />
                        </IconButton>
                      </Box>
                      
                      {agent.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                          {agent.description}
                        </Typography>
                      )}
                      
                      {agent.tags && agent.tags.length > 0 && (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
                          {agent.tags.map((tag: Tag) => (
                            <Chip key={tag.id} label={tag.name} size="small" />
                          ))}
                        </Box>
                      )}
                      
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Rating 
                          value={agent.average_rating} 
                          readOnly 
                          size="small"
                          precision={0.1}
                        />
                        <Typography variant="caption" color="text.secondary">
                          ({agent.total_votes})
                        </Typography>
                      </Box>
                      
                      <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                        <Chip 
                          icon={<PersonIcon />} 
                          label={agent.author_name} 
                          size="small" 
                          variant="outlined"
                        />
                        <Chip 
                          icon={<ViewIcon />} 
                          label={agent.views_count} 
                          size="small" 
                          variant="outlined"
                        />
                      </Box>
                    </CardContent>
                    <CardActions>
                      <Button 
                        size="small" 
                        startIcon={<CopyIcon />}
                        onClick={() => handleUseAgent(agent)}
                        fullWidth
                        variant="contained"
                      >
                        Использовать
                      </Button>
                      <Button 
                        size="small" 
                        startIcon={agent.is_bookmarked ? <BookmarkIcon /> : <BookmarkBorderIcon />}
                        onClick={() => handleToggleAgentBookmark(agent)}
                      >
                        {agent.is_bookmarked ? 'В закладках' : 'В закладки'}
                      </Button>
                    </CardActions>
                  </Card>
                ))}
              </Box>
            )}

            {/* Пагинация для агентов */}
            {agentsTotalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <Pagination
                  count={agentsTotalPages}
                  page={agentsPage}
                  onChange={(_, value) => setAgentsPage(value)}
                  color="primary"
                  size="large"
                />
              </Box>
            )}
          </>
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

      {/* Диалог создания агента */}
      <AgentDialog
        open={showCreateAgentDialog}
        onClose={() => {
          setShowCreateAgentDialog(false);
          resetAgentForm();
        }}
        onSave={handleCreateAgent}
        agentForm={agentForm}
        setAgentForm={setAgentForm}
        allTags={allTags}
        title="Создать агента"
        newTagInput={newAgentTagInput}
        setNewTagInput={setNewAgentTagInput}
      />

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
          {/* Кнопка "Создать промпт" или "Создать агента" */}
          <Tooltip title={rightSidebarOpen ? '' : (activeTab === 0 ? 'Создать промпт' : 'Создать агента')} placement="left">
            <Button
              fullWidth={rightSidebarOpen}
              variant={rightSidebarOpen ? 'contained' : 'text'}
              startIcon={<AddIcon />}
              onClick={() => {
                if (activeTab === 0) {
                  setShowCreateDialog(true);
                } else {
                  setShowCreateAgentDialog(true);
                }
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
              {rightSidebarOpen && (activeTab === 0 ? 'Создать промпт' : 'Создать агента')}
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
          `${getApiUrl('/api/prompts')}/${prompt.id}/view`,
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

// Компонент диалога создания/редактирования агента
interface AgentDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  agentForm: any;
  setAgentForm: React.Dispatch<React.SetStateAction<any>>;
  allTags: Tag[];
  title: string;
  newTagInput: string;
  setNewTagInput: React.Dispatch<React.SetStateAction<string>>;
}

function AgentDialog({ open, onClose, onSave, agentForm, setAgentForm, allTags, title, newTagInput, setNewTagInput }: AgentDialogProps) {
  const [availableModels, setAvailableModels] = useState<Array<{
    name: string;
    path: string;
    size?: number;
    size_mb?: number;
  }>>([]);

  // Загружаем модели при открытии диалога
  useEffect(() => {
    if (open) {
      const loadModels = async () => {
        try {
          const response = await fetch(`${getApiUrl(API_ENDPOINTS.CHAT)}/../models/available`);
          if (response.ok) {
            const data = await response.json();
            setAvailableModels(data.models || []);
          }
        } catch (error) {
          console.error('Ошибка загрузки моделей:', error);
        }
      };
      loadModels();
    }
  }, [open]);

  const handleAddNewTag = () => {
    const tagName = newTagInput.trim();
    if (tagName && !agentForm.new_tags.includes(tagName)) {
      setAgentForm({ 
        ...agentForm, 
        new_tags: [...agentForm.new_tags, tagName] 
      });
      setNewTagInput('');
    }
  };

  const handleRemoveNewTag = (tagToRemove: string) => {
    setAgentForm({
      ...agentForm,
      new_tags: agentForm.new_tags.filter((tag: string) => tag !== tagToRemove)
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddNewTag();
    }
  };

  const handleAddTool = () => {
    const toolInput = (document.getElementById('tool-input') as HTMLInputElement)?.value?.trim();
    if (toolInput && !agentForm.tools.includes(toolInput)) {
      setAgentForm({
        ...agentForm,
        tools: [...agentForm.tools, toolInput]
      });
      if (document.getElementById('tool-input')) {
        (document.getElementById('tool-input') as HTMLInputElement).value = '';
      }
    }
  };

  const handleRemoveTool = (toolToRemove: string) => {
    setAgentForm({
      ...agentForm,
      tools: agentForm.tools.filter((tool: string) => tool !== toolToRemove)
    });
  };

  const updateModelSetting = (key: string, value: any) => {
    setAgentForm({
      ...agentForm,
      config: {
        ...agentForm.config,
        model_settings: {
          ...(agentForm.config?.model_settings || {}),
          [key]: value,
        },
      },
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Название агента"
            fullWidth
            required
            value={agentForm.name}
            onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })}
            helperText="Минимум 3 символа"
          />
          
          <TextField
            label="Описание"
            fullWidth
            multiline
            rows={2}
            value={agentForm.description}
            onChange={(e) => setAgentForm({ ...agentForm, description: e.target.value })}
            helperText="Краткое описание назначения агента"
          />

          <TextField
            label="Системный промпт"
            fullWidth
            required
            multiline
            rows={10}
            value={agentForm.system_prompt}
            onChange={(e) => setAgentForm({ ...agentForm, system_prompt: e.target.value })}
            helperText="Определяет поведение и возможности агента. Минимум 10 символов."
          />

          {/* Настройки модели */}
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SettingsIcon />
                <Typography variant="subtitle1">Настройки модели (опционально)</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                {/* Выбор модели */}
                <FormControl fullWidth>
                  <InputLabel>Модель</InputLabel>
                  <Select
                    value={agentForm.config?.model_path || ''}
                    label="Модель"
                    onChange={(e) => setAgentForm({
                      ...agentForm,
                      config: {
                        ...agentForm.config,
                        model_path: e.target.value,
                      },
                    })}
                  >
                    <MenuItem value="">
                      <em>Использовать текущую модель</em>
                    </MenuItem>
                    {availableModels.map((model) => (
                      <MenuItem key={model.path} value={model.path}>
                        {model.name} {model.size_mb ? `(${model.size_mb} MB)` : ''}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {/* Гиперпараметры */}
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, gap: 2 }}>
                  <TextField
                    label="Размер контекста"
                    type="number"
                    value={agentForm.config?.model_settings?.context_size || 2048}
                    onChange={(e) => updateModelSetting('context_size', parseInt(e.target.value) || 2048)}
                    inputProps={{ min: 512, max: 32768, step: 512 }}
                    helperText="Максимальное количество токенов контекста"
                  />
                  
                  <TextField
                    label="Макс. токенов ответа"
                    type="number"
                    value={agentForm.config?.model_settings?.output_tokens || 512}
                    onChange={(e) => updateModelSetting('output_tokens', parseInt(e.target.value) || 512)}
                    inputProps={{ min: 128, max: 8192, step: 128 }}
                    helperText="Максимальная длина ответа"
                  />
                  
                  <Box>
                    <Typography variant="body2" gutterBottom>
                      Температура: {agentForm.config?.model_settings?.temperature || 0.7}
                    </Typography>
                    <Slider
                      value={agentForm.config?.model_settings?.temperature || 0.7}
                      onChange={(_, value) => updateModelSetting('temperature', value)}
                      min={0}
                      max={2}
                      step={0.1}
                      marks={[
                        { value: 0, label: '0' },
                        { value: 1, label: '1' },
                        { value: 2, label: '2' },
                      ]}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Контролирует случайность ответов (0 = детерминированный, 2 = очень случайный)
                    </Typography>
                  </Box>
                  
                  <Box>
                    <Typography variant="body2" gutterBottom>
                      Top-p: {agentForm.config?.model_settings?.top_p || 0.95}
                    </Typography>
                    <Slider
                      value={agentForm.config?.model_settings?.top_p || 0.95}
                      onChange={(_, value) => updateModelSetting('top_p', value)}
                      min={0}
                      max={1}
                      step={0.05}
                      marks={[
                        { value: 0, label: '0' },
                        { value: 0.5, label: '0.5' },
                        { value: 1, label: '1' },
                      ]}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Ядерная выборка: учитывает только топ токены с вероятностью p
                    </Typography>
                  </Box>
                  
                  <Box>
                    <Typography variant="body2" gutterBottom>
                      Штраф за повторения: {agentForm.config?.model_settings?.repeat_penalty || 1.05}
                    </Typography>
                    <Slider
                      value={agentForm.config?.model_settings?.repeat_penalty || 1.05}
                      onChange={(_, value) => updateModelSetting('repeat_penalty', value)}
                      min={1}
                      max={2}
                      step={0.05}
                      marks={[
                        { value: 1, label: '1' },
                        { value: 1.5, label: '1.5' },
                        { value: 2, label: '2' },
                      ]}
                    />
                    <Typography variant="caption" color="text.secondary">
                      Штраф за повторение токенов (1 = нет штрафа, &gt;1 = штраф)
                    </Typography>
                  </Box>
                  
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={agentForm.config?.model_settings?.use_gpu || false}
                        onChange={(e) => updateModelSetting('use_gpu', e.target.checked)}
                      />
                    }
                    label="Использовать GPU"
                  />
                  
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={agentForm.config?.model_settings?.streaming !== false}
                        onChange={(e) => updateModelSetting('streaming', e.target.checked)}
                      />
                    }
                    label="Потоковая генерация"
                  />
                </Box>
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Инструменты */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Инструменты (опционально)
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField
                id="tool-input"
                label="Название инструмента"
                fullWidth
                size="small"
                placeholder="Например: calculator, web_search"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddTool();
                  }
                }}
              />
              <Button
                variant="outlined"
                onClick={handleAddTool}
                sx={{ minWidth: 100 }}
              >
                Добавить
              </Button>
            </Box>
            {agentForm.tools.length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                  {agentForm.tools.map((tool: string, index: number) => (
                    <Chip
                      key={index}
                      label={tool}
                      size="small"
                      onDelete={() => handleRemoveTool(tool)}
                      color="secondary"
                      variant="outlined"
                    />
                  ))}
                </Stack>
              </Box>
            )}
          </Box>

          <FormControl fullWidth>
            <InputLabel>Существующие теги</InputLabel>
            <Select
              multiple
              value={agentForm.tag_ids}
              label="Существующие теги"
              onChange={(e) => setAgentForm({ ...agentForm, tag_ids: e.target.value as number[] })}
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
            {agentForm.new_tags.length > 0 && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Новые теги:
                </Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                  {agentForm.new_tags.map((tag: string, index: number) => (
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

          {/* Публичность */}
          <FormControl fullWidth>
            <FormControlLabel
              control={
                <Checkbox
                  checked={agentForm.is_public}
                  onChange={(e) => setAgentForm({ ...agentForm, is_public: e.target.checked })}
                />
              }
              label="Публичный агент (виден всем пользователям)"
            />
          </FormControl>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button onClick={onSave} variant="contained">
          Создать
        </Button>
      </DialogActions>
    </Dialog>
  );
}

