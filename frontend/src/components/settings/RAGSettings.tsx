import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
  Alert,
  Popover,
  Button,
  Divider,
} from '@mui/material';
import {
  Search as SearchIcon,
  HelpOutline as HelpOutlineIcon,
  ExpandMore as ExpandMoreIcon,
  LibraryBooks as LibraryBooksIcon,
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';
import { getApiUrl } from '../../config/api';
import {
  DROPDOWN_TRIGGER_BUTTON_SX,
  DROPDOWN_CHEVRON_SX,
  getDropdownPopoverPaperSx,
  DROPDOWN_ITEM_SX,
  DROPDOWN_ITEM_HOVER_BG,
} from '../../constants/menuStyles';
import MemoryRagLibraryModal from '../MemoryRagLibraryModal';

type RAGStrategy = 'auto' | 'reranking' | 'hierarchical' | 'hybrid' | 'standard';

interface RAGSettingsProps {}

export default function RAGSettings({}: RAGSettingsProps) {
  const [selectedStrategy, setSelectedStrategy] = useState<RAGStrategy>('auto');
  const [isLoading, setIsLoading] = useState(false);
  const [strategyPopoverAnchor, setStrategyPopoverAnchor] = useState<HTMLElement | null>(null);
  const [memoryRagModalOpen, setMemoryRagModalOpen] = useState(false);
  const { showNotification } = useAppActions();

  useEffect(() => {
    loadRAGSettings();
  }, []);

  // Автосохранение настроек RAG
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveRAGSettings().then(() => {
        // После сохранения обновляем информацию о применяемом методе
        loadRAGSettings();
      });
    }, 1000); // Сохраняем через 1 секунду после изменения

    return () => clearTimeout(timeoutId);
  }, [selectedStrategy]);

  const loadRAGSettings = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(getApiUrl('/api/rag/settings'));
      if (response.ok) {
        const data = await response.json();
        if (data.strategy) {
          setSelectedStrategy(data.strategy);
        }
      } else if (response.status === 404) {
        // Если endpoint не найден, используем значение по умолчанию
        setSelectedStrategy('auto');
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек RAG:', error);
      // Используем значение по умолчанию при ошибке
      setSelectedStrategy('auto');
    } finally {
      setIsLoading(false);
    }
  };

  const saveRAGSettings = async (): Promise<void> => {
    try {
      const response = await fetch(getApiUrl('/api/rag/settings'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy: selectedStrategy }),
      });
      
      if (response.ok) {
        showNotification('success', 'Настройки RAG сохранены');
      } else {
        throw new Error(`Ошибка сохранения настроек RAG: ${response.status}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек RAG:', error);
      showNotification('error', 'Ошибка сохранения настроек RAG');
    }
  };

  const handleStrategyChange = (event: any) => {
    const newStrategy = event.target.value as RAGStrategy;
    setSelectedStrategy(newStrategy);
  };

  const getStrategyLabel = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Автоматический выбор';
      case 'reranking':
        return 'Reranking (переранжирование)';
      case 'hierarchical':
        return 'Иерархический поиск';
      case 'hybrid':
        return 'Гибридный поиск';
      case 'standard':
        return 'Стандартный поиск';
      default:
        return 'Автоматический выбор';
    }
  };

  const getStrategyDescription = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Система автоматически выберет лучшую доступную стратегию поиска на основе текущих настроек. Рекомендуется для большинства случаев.';
      case 'reranking':
        return 'Использует CrossEncoder модель для переоценки релевантности результатов. Улучшает точность на 20-30%, но требует GPU и работает медленнее. Лучше всего для точных ответов на сложные вопросы.';
      case 'hierarchical':
        return 'Умный поиск по иерархической структуре документов. Автоматически выбирает между быстрой стратегией (summary) для общих вопросов и детальной (detailed) для конкретных. Идеально для больших документов.';
      case 'hybrid':
        return 'Комбинирует векторный поиск (семантический) и BM25 (ключевые слова). Параллельно выполняет оба поиска и объединяет результаты. Хорош для баланса между точностью и скоростью.';
      case 'standard':
        return 'Базовый векторный поиск через pgvector с использованием cosine similarity. Самый быстрый вариант, но менее точный. Используется как fallback, если другие стратегии недоступны.';
      default:
        return '';
    }
  };

  const getStrategyUseCase = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Используйте для большинства случаев - система сама выберет оптимальную стратегию.';
      case 'reranking':
        return 'Используйте когда нужна максимальная точность ответов на сложные вопросы. Требует GPU.';
      case 'hierarchical':
        return 'Используйте для работы с большими документами (отчеты, книги, длинные тексты).';
      case 'hybrid':
        return 'Используйте когда нужен баланс между точностью и скоростью, особенно для поиска по ключевым словам и датам.';
      case 'standard':
        return 'Используйте только если другие стратегии недоступны или нужна максимальная скорость.';
      default:
        return '';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SearchIcon color="primary" />
            Стратегия поиска RAG
            <Tooltip 
              title="RAG (Retrieval-Augmented Generation) - система поиска релевантных документов для улучшения ответов модели. Выберите стратегию поиска, которая лучше всего подходит для ваших задач." 
              arrow
            >
              <IconButton 
                size="small" 
                sx={{ 
                  ml: 0.5,
                  opacity: 0.7,
                  '&:hover': {
                    opacity: 1,
                    '& .MuiSvgIcon-root': {
                      color: 'primary.main',
                    },
                  },
                }}
              >
                <HelpOutlineIcon fontSize="small" color="action" />
              </IconButton>
            </Tooltip>
          </Typography>

          <List sx={{ p: 0 }}>
            <ListItem
              sx={{
                px: 0,
                py: 2,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    Управление документами
                    <Tooltip
                      title="Загрузка PDF, Word, Excel, TXT в библиотеку памяти (MinIO + pgvector). Подключение поиска к ответам — в зоне ввода сообщения кнопкой «Подключить базу знаний»."
                      arrow
                    >
                      <IconButton
                        size="small"
                        sx={{
                          p: 0,
                          ml: 0.5,
                          opacity: 0.7,
                          '&:hover': {
                            opacity: 1,
                            '& .MuiSvgIcon-root': {
                              color: 'primary.main',
                            },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                        aria-label="Справка по библиотеке документов"
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Button
                variant="outlined"
                color="primary"
                startIcon={<LibraryBooksIcon />}
                onClick={() => setMemoryRagModalOpen(true)}
                sx={{
                  textTransform: 'none',
                  minWidth: 180,
                }}
              >
                Открыть базу данных
              </Button>
            </ListItem>

            <Divider />

            <ListItem
              sx={{
                px: 0,
                py: 2,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    Стратегия поиска
                    <Tooltip 
                      title="Выберите стратегию поиска по документам. Каждая стратегия имеет свои преимущества и подходит для разных задач." 
                      arrow
                    >
                      <IconButton 
                        size="small" 
                        sx={{ 
                          p: 0,
                          ml: 0.5,
                          opacity: 0.7,
                          '&:hover': {
                            opacity: 1,
                            '& .MuiSvgIcon-root': {
                              color: 'primary.main',
                            },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Box sx={{ minWidth: 280 }}>
                <Box
                  onClick={(e) => !isLoading && setStrategyPopoverAnchor(e.currentTarget)}
                  sx={{
                    ...DROPDOWN_TRIGGER_BUTTON_SX,
                    opacity: isLoading ? 0.7 : 1,
                    pointerEvents: isLoading ? 'none' : 'auto',
                  }}
                >
                  <Typography sx={{ color: 'white', fontWeight: 500, fontSize: '0.875rem' }}>
                    {getStrategyLabel(selectedStrategy)}
                  </Typography>
                  <ExpandMoreIcon sx={{ ...DROPDOWN_CHEVRON_SX, transform: strategyPopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                </Box>
                <Popover
                  open={Boolean(strategyPopoverAnchor)}
                  anchorEl={strategyPopoverAnchor}
                  onClose={() => setStrategyPopoverAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  slotProps={{ paper: { sx: getDropdownPopoverPaperSx(strategyPopoverAnchor) } }}
                >
                  <Box sx={{ py: 0.5 }}>
                    {(['auto', 'reranking', 'hierarchical', 'hybrid', 'standard'] as const).map((strategy) => (
                      <Box
                        key={strategy}
                        onClick={() => { setSelectedStrategy(strategy); setStrategyPopoverAnchor(null); }}
                        sx={{
                          ...DROPDOWN_ITEM_SX,
                          color: selectedStrategy === strategy ? 'white' : 'rgba(255,255,255,0.9)',
                          fontWeight: selectedStrategy === strategy ? 600 : 400,
                          bgcolor: selectedStrategy === strategy ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                        }}
                      >
                        {getStrategyLabel(strategy)}
                      </Box>
                    ))}
                  </Box>
                </Popover>
              </Box>
            </ListItem>
          </List>

          {/* Информационный блок о выбранной стратегии */}
          <Alert 
            severity="info" 
            sx={{ 
              mt: 2,
              '& .MuiAlert-message': {
                width: '100%',
              },
            }}
          >
            <Box>
              <Typography variant="subtitle2" fontWeight="600" gutterBottom>
                {getStrategyLabel(selectedStrategy)}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {getStrategyDescription(selectedStrategy)}
              </Typography>
              <Typography variant="body2" fontWeight="500" sx={{ mt: 1 }}>
                {getStrategyUseCase(selectedStrategy)}
              </Typography>
            </Box>
          </Alert>
        </CardContent>
      </Card>

      <MemoryRagLibraryModal open={memoryRagModalOpen} onClose={() => setMemoryRagModalOpen(false)} />
    </Box>
  );
}

