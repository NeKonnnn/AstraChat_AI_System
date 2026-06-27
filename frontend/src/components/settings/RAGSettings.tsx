import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useTheme } from '@mui/material/styles';
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
  Switch,
  TextField,
  Collapse,
} from '@mui/material';
import {
  Search as SearchIcon,
  HelpOutline as HelpOutlineIcon,
  ExpandMore as ExpandMoreIcon,
  LibraryBooks as LibraryBooksIcon,
  Restore as RestoreIcon,
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';
import { getApiUrl } from '../../config/api';
import {
  DROPDOWN_TRIGGER_BUTTON_SX,
  DROPDOWN_CHEVRON_SX,
  getDropdownPopoverPaperSx,
  getDropdownItemSx,
  DROPDOWN_ITEM_HOVER_BG,
} from '../../constants/menuStyles';
import MemoryRagLibraryModal from '../MemoryRagLibraryModal';
import {
  MODEL_SETTINGS_RESET_BUTTON_SX,
  MODEL_SETTINGS_LABEL_WRAPPER_SX,
  MODEL_SETTINGS_HELP_ICON_BUTTON_SX,
  MODEL_SETTINGS_INPUT_SX,
} from '../../constants/modelSettingsStyles';

type RAGStrategy = 'auto' | 'hybrid' | 'standard' | 'graph' | 'lexical';
type ChunkingStrategy = 'hierarchical' | 'fixed' | 'markdown' | 'separators' | 'semantic';
const RAG_STRATEGY_STORAGE_KEY = 'rag_strategy';
const RAG_CHUNKING_STORAGE_KEY = 'rag_chunking_strategy';
const DEFAULT_RAG_SYSTEM_PROMPT =
  'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.';

function normalizeStoredStrategy(raw: string | null): RAGStrategy {
  const s = (raw || 'auto').trim().toLowerCase();
  if (s === 'reranking') return 'hybrid';
  if (s === 'auto' || s === 'hybrid' || s === 'standard' || s === 'graph' || s === 'lexical') {
    return s;
  }
  return 'auto';
}

function normalizeChunkingStrategy(raw: string | null): ChunkingStrategy {
  const s = (raw || 'hierarchical').trim().toLowerCase();
  if (s === 'hierarchical' || s === 'fixed' || s === 'markdown' || s === 'separators' || s === 'semantic') {
    return s;
  }
  return 'hierarchical';
}

interface RAGSettingsProps {}

export default function RAGSettings({}: RAGSettingsProps) {
  const theme = useTheme();
  const dropdownItemSx = useMemo(() => getDropdownItemSx(theme.palette.mode === 'dark'), [theme.palette.mode]);
  const [selectedStrategy, setSelectedStrategy] = useState<RAGStrategy>(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(RAG_STRATEGY_STORAGE_KEY) : null;
    return normalizeStoredStrategy(saved);
  });
  const [isLoading, setIsLoading] = useState(false);
  const [strategyPopoverAnchor, setStrategyPopoverAnchor] = useState<HTMLElement | null>(null);
  const [chunkingPopoverAnchor, setChunkingPopoverAnchor] = useState<HTMLElement | null>(null);
  const [memoryRagModalOpen, setMemoryRagModalOpen] = useState(false);
  const [agenticRagEnabled, setAgenticRagEnabled] = useState(true);
  const [ragQueryFixTypos, setRagQueryFixTypos] = useState(false);
  const [ragMultiQueryEnabled, setRagMultiQueryEnabled] = useState(false);
  const [ragHydeEnabled, setRagHydeEnabled] = useState(false);
  const [ragChatTopK, setRagChatTopK] = useState(5);
  const [ragChunkingStrategy, setRagChunkingStrategy] = useState<ChunkingStrategy>(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(RAG_CHUNKING_STORAGE_KEY) : null;
    return normalizeChunkingStrategy(saved);
  });
  const [ragChunkOverlap, setRagChunkOverlap] = useState(200);
  const [ragSimilarityThreshold, setRagSimilarityThreshold] = useState(0);
  const [ragRerankingEnabled, setRagRerankingEnabled] = useState(false);
  const [ragRerankTopN, setRagRerankTopN] = useState(5);
  const [ragSystemPrompt, setRagSystemPrompt] = useState(DEFAULT_RAG_SYSTEM_PROMPT);
  const [strategyInfoExpanded, setStrategyInfoExpanded] = useState(true);
  const [chunkingInfoExpanded, setChunkingInfoExpanded] = useState(true);
  const isInitializedRef = useRef(false);
  const skipNextRagSaveToastRef = useRef(false);
  const { showNotification } = useAppActions();

  useEffect(() => {
    loadRAGSettings();
  }, []);

  // Автосохранение настроек RAG после первичной загрузки.
  useEffect(() => {
    if (!isInitializedRef.current) return;

    // Обновляем localStorage сразу, чтобы следующий отправленный запрос
    // (SocketContext) использовал выбранную стратегию без ожидания таймера.
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(RAG_STRATEGY_STORAGE_KEY, selectedStrategy);
    }

    const timeoutId = setTimeout(() => {
      saveRAGSettings().then(() => {
        // После сохранения обновляем информацию о применяемом методе
        loadRAGSettings();
      });
    }, 300); // Небольшая задержка для "дребезга" изменений

    return () => clearTimeout(timeoutId);
  }, [
    selectedStrategy,
    agenticRagEnabled,
    ragQueryFixTypos,
    ragMultiQueryEnabled,
    ragHydeEnabled,
    ragChatTopK,
    ragChunkingStrategy,
    ragChunkOverlap,
    ragSimilarityThreshold,
    ragRerankingEnabled,
    ragRerankTopN,
    ragSystemPrompt,
  ]);

  const loadRAGSettings = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(getApiUrl('/api/rag/settings'));
      if (response.ok) {
        const data = await response.json();
        if (data.strategy) {
          const next = normalizeStoredStrategy(String(data.strategy));
          setSelectedStrategy(next);
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(RAG_STRATEGY_STORAGE_KEY, next);
          }
        }
        if (typeof data.agentic_rag_enabled === 'boolean') {
          setAgenticRagEnabled(data.agentic_rag_enabled);
        }
        if (typeof data.rag_query_fix_typos === 'boolean') {
          setRagQueryFixTypos(data.rag_query_fix_typos);
        }
        if (typeof data.rag_multi_query_enabled === 'boolean') {
          setRagMultiQueryEnabled(data.rag_multi_query_enabled);
        }
        if (typeof data.rag_hyde_enabled === 'boolean') {
          setRagHydeEnabled(data.rag_hyde_enabled);
        }
        if (typeof data.rag_chat_top_k === 'number' && Number.isFinite(data.rag_chat_top_k)) {
          const k = Math.max(1, Math.min(64, Math.round(data.rag_chat_top_k)));
          setRagChatTopK(k);
        }
        if (typeof data.rag_chunking_strategy === 'string') {
          const strategy = normalizeChunkingStrategy(data.rag_chunking_strategy);
          setRagChunkingStrategy(strategy);
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(RAG_CHUNKING_STORAGE_KEY, strategy);
          }
        }
        if (typeof data.rag_chunk_overlap === 'number' && Number.isFinite(data.rag_chunk_overlap)) {
          setRagChunkOverlap(Math.max(0, Math.min(2000, Math.round(data.rag_chunk_overlap))));
        }
        if (typeof data.rag_similarity_threshold === 'number' && Number.isFinite(data.rag_similarity_threshold)) {
          setRagSimilarityThreshold(Math.max(0, Math.min(1, data.rag_similarity_threshold)));
        }
        if (typeof data.rag_reranking_enabled === 'boolean') {
          setRagRerankingEnabled(data.rag_reranking_enabled);
        }
        if (typeof data.rag_rerank_top_n === 'number' && Number.isFinite(data.rag_rerank_top_n)) {
          setRagRerankTopN(Math.max(1, Math.min(64, Math.round(data.rag_rerank_top_n))));
        }
        if (typeof data.rag_system_prompt === 'string' && data.rag_system_prompt.trim()) {
          setRagSystemPrompt(data.rag_system_prompt);
        }
      } else if (response.status === 404) {
        // Оставляем текущее значение (локальное), если endpoint не найден
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек RAG:', error);
      // Оставляем текщее значение (локальное), если сервер недоступен
    } finally {
      setIsLoading(false);
      isInitializedRef.current = true;
    }
  };

  const saveRAGSettings = async (): Promise<void> => {
    try {
      const response = await fetch(getApiUrl('/api/rag/settings'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy: selectedStrategy,
          agentic_rag_enabled: agenticRagEnabled,
          rag_query_fix_typos: ragQueryFixTypos,
          rag_multi_query_enabled: ragMultiQueryEnabled,
          rag_hyde_enabled: ragHydeEnabled,
          rag_chat_top_k: ragChatTopK,
          rag_chunking_strategy: ragChunkingStrategy,
          rag_chunk_overlap: ragChunkOverlap,
          rag_similarity_threshold: ragSimilarityThreshold,
          rag_reranking_enabled: ragRerankingEnabled,
          rag_rerank_top_n: ragRerankTopN,
          rag_system_prompt: ragSystemPrompt.trim() || DEFAULT_RAG_SYSTEM_PROMPT,
        }),
      });
      
      if (response.ok) {
        if (skipNextRagSaveToastRef.current) {
          skipNextRagSaveToastRef.current = false;
        } else {
          showNotification('success', 'Настройки RAG сохранены');
        }
      } else {
        throw new Error(`Ошибка сохранения настроек RAG: ${response.status}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек RAG:', error);
      showNotification('error', 'Ошибка сохранения настроек RAG');
    }
  };

  const resetRAGSettings = async () => {
    try {
      const response = await fetch(getApiUrl('/api/rag/settings/reset'), { method: 'POST' });
      if (!response.ok) {
        throw new Error(`reset ${response.status}`);
      }
      skipNextRagSaveToastRef.current = true;
      await loadRAGSettings();
      showNotification('success', 'Настройки RAG восстановлены по умолчанию');
    } catch (error) {
      console.error('Ошибка сброса настроек RAG:', error);
      showNotification('error', 'Не удалось сбросить настройки RAG');
    }
  };

  const getStrategyLabel = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Автоматический выбор';
      case 'hybrid':
        return 'Гибридный поиск';
      case 'standard':
        return 'Векторный';
      case 'lexical':
        return 'Ключевой/Лексический (BM25)';
      case 'graph':
        return 'Graph RAG (графовый поиск)';
      default:
        return 'Автоматический выбор';
    }
  };

  const getStrategyDescription = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Сервер автоматически подбирает оптимальный режим среди доступных стратегий (гибрид, векторный, графовый) по типу запроса.';
      case 'hybrid':
        return 'Комбинирует векторный поиск (семантический) и BM25 (ключевые слова), объединяет кандидатов; при RAG_USE_RERANKING в SVC-RAG — cross-encoder переупорядочивает фрагменты под запрос. Так легче попасть в нужный абзац (например, место работы в резюме).';
      case 'standard':
        return 'Чистый векторный поиск через pgvector (cosine similarity). Хорошо работает на смысловых запросах и перефразах.';
      case 'lexical':
        return 'Ключевой/лексический поиск работает по BM25. Полезен для точных совпадений терминов, кодов, артикулов, ФИО и формулировок без смыслового расширения.';
      case 'graph':
        return 'Графовый RAG: сначала находит релевантные seed-чанки, затем расширяет контекст по связям между фрагментами (соседние чанки, семантические связи, общие сущности) и ранжирует итоговый набор. Полезно для многошаговых вопросов и длинных документов.';
      default:
        return '';
    }
  };

  const getStrategyUseCase = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Используйте для большинства случаев - система сама выберет оптимальную стратегию.';
      case 'hybrid':
        return 'Используйте когда нужен баланс между точностью и скоростью, особенно для поиска по ключевым словам и датам.';
      case 'standard':
        return 'Используйте как основной семантический режим: хороший баланс точности и скорости.';
      case 'lexical':
        return 'Используйте для строгих запросов по словам: коды, номера, имена, артикулы, точные термины.';
      case 'graph':
        return 'Используйте для сложных запросов, где ответ требует объединять факты из нескольких связанных фрагментов.';
      default:
        return '';
    }
  };

  const getChunkingLabel = (strategy: ChunkingStrategy): string => {
    switch (strategy) {
      case 'hierarchical':
        return 'Иерархическое';
      case 'fixed':
        return 'Фиксированное';
      case 'markdown':
        return 'По разметке';
      case 'separators':
        return 'По разделителям';
      case 'semantic':
        return 'Семантическое';
      default:
        return 'Иерархическое';
    }
  };

  const getChunkingDescription = (strategy: ChunkingStrategy): string => {
    switch (strategy) {
      case 'hierarchical':
        return 'Документ сначала делится на крупные смысловые блоки, затем на более мелкие фрагменты. Это обычно дает лучший баланс между полнотой контекста и точностью поиска.';
      case 'fixed':
        return 'Текст режется на чанки фиксированной длины. Предсказуемо по размеру и скорости, но может разрывать мысль на границах.';
      case 'markdown':
        return 'Чанкование ориентируется на структуру разметки (заголовки, списки, секции). Хорошо подходит для технической документации и markdown-файлов.';
      case 'separators':
        return 'Разделение по естественным разделителям (абзацы, переносы, знаки, служебные маркеры). Менее жесткое, чем fixed, и обычно более читабельное.';
      case 'semantic':
        return 'Смысловое чанкование пытается сохранять цельные идеи внутри чанка. Обычно дает лучшее качество retrieval, но требует больше вычислений.';
      default:
        return '';
    }
  };

  const getChunkingUseCase = (strategy: ChunkingStrategy): string => {
    switch (strategy) {
      case 'hierarchical':
        return 'Рекомендуется как универсальный режим для смешанных корпусов документов.';
      case 'fixed':
        return 'Подходит для простых однотипных документов, где важна стабильная производительность.';
      case 'markdown':
        return 'Используйте для wiki/документации с выраженной структурой разделов.';
      case 'separators':
        return 'Подходит для текстов с понятной абзацной структурой без сложной разметки.';
      case 'semantic':
        return 'Используйте, когда приоритет - максимальная релевантность и смысловая целостность чанков.';
      default:
        return '';
    }
  };

  const ragPillsRowSx = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 1.5,
    alignItems: 'flex-start',
  };

  const ragPillFieldWrapperSx = {
    width: { xs: '100%', sm: 148 },
    maxWidth: { xs: '100%', sm: 148 },
    flex: '0 0 auto',
    minWidth: 0,
  };

  return (
    <Box sx={{ p: 3 }}>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SearchIcon color="primary" />
            Настройки для RAG
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
                    {(['auto', 'hybrid', 'standard', 'lexical', 'graph'] as const).map((strategy) => (
                      <Box
                        key={strategy}
                        onClick={() => {
                          // Обновляем сразу, чтобы следующий запрос (SocketContext) не успел
                          // прочитать "старое" значение.
                          if (typeof localStorage !== 'undefined') {
                            localStorage.setItem(RAG_STRATEGY_STORAGE_KEY, strategy);
                          }
                          setSelectedStrategy(strategy);
                          setStrategyPopoverAnchor(null);
                        }}
                        sx={{
                          ...dropdownItemSx,
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

            <ListItem sx={{ px: 0, py: 1.5, display: 'block' }}>
              <Alert
                severity="info"
                sx={{
                  '& .MuiAlert-message': { width: '100%', pt: 0.25 },
                  py: 1,
                }}
                action={
                  <Tooltip title={strategyInfoExpanded ? 'Свернуть' : 'Развернуть'} arrow>
                    <IconButton
                      size="small"
                      color="inherit"
                      aria-expanded={strategyInfoExpanded}
                      aria-label={strategyInfoExpanded ? 'Свернуть описание стратегии' : 'Развернуть описание стратегии'}
                      onClick={() => setStrategyInfoExpanded((v) => !v)}
                      edge="end"
                    >
                      <ExpandMoreIcon
                        sx={{
                          transform: strategyInfoExpanded ? 'rotate(180deg)' : 'none',
                          transition: theme.transitions.create('transform', {
                            duration: theme.transitions.duration.shorter,
                          }),
                        }}
                      />
                    </IconButton>
                  </Tooltip>
                }
              >
                <Typography variant="subtitle2" fontWeight="600" gutterBottom>
                  {getStrategyLabel(selectedStrategy)}
                </Typography>
                <Collapse in={strategyInfoExpanded} timeout="auto" unmountOnExit={false}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {getStrategyDescription(selectedStrategy)}
                    </Typography>
                    <Typography variant="body2" fontWeight="500" sx={{ mt: 1 }}>
                      {getStrategyUseCase(selectedStrategy)}
                    </Typography>
                  </Box>
                </Collapse>
              </Alert>
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
                    Стратегия чанкования
                    <Tooltip title="Выберите способ нарезки документов на чанки перед индексацией." arrow>
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
                  onClick={(e) => !isLoading && setChunkingPopoverAnchor(e.currentTarget)}
                  sx={{
                    ...DROPDOWN_TRIGGER_BUTTON_SX,
                    opacity: isLoading ? 0.7 : 1,
                    pointerEvents: isLoading ? 'none' : 'auto',
                  }}
                >
                  <Typography sx={{ color: 'white', fontWeight: 500, fontSize: '0.875rem' }}>
                    {getChunkingLabel(ragChunkingStrategy)}
                  </Typography>
                  <ExpandMoreIcon sx={{ ...DROPDOWN_CHEVRON_SX, transform: chunkingPopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                </Box>
                <Popover
                  open={Boolean(chunkingPopoverAnchor)}
                  anchorEl={chunkingPopoverAnchor}
                  onClose={() => setChunkingPopoverAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  slotProps={{ paper: { sx: getDropdownPopoverPaperSx(chunkingPopoverAnchor) } }}
                >
                  <Box sx={{ py: 0.5 }}>
                    {(['hierarchical', 'fixed', 'markdown', 'separators', 'semantic'] as const).map((strategy) => (
                      <Box
                        key={strategy}
                        onClick={() => {
                          if (typeof localStorage !== 'undefined') {
                            localStorage.setItem(RAG_CHUNKING_STORAGE_KEY, strategy);
                          }
                          setRagChunkingStrategy(strategy);
                          setChunkingPopoverAnchor(null);
                        }}
                        sx={{
                          ...dropdownItemSx,
                          color: ragChunkingStrategy === strategy ? 'white' : 'rgba(255,255,255,0.9)',
                          fontWeight: ragChunkingStrategy === strategy ? 600 : 400,
                          bgcolor: ragChunkingStrategy === strategy ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                        }}
                      >
                        {getChunkingLabel(strategy)}
                      </Box>
                    ))}
                  </Box>
                </Popover>
              </Box>
            </ListItem>

            <ListItem sx={{ px: 0, py: 1.5, display: 'block' }}>
              <Alert
                severity="info"
                sx={{
                  '& .MuiAlert-message': { width: '100%', pt: 0.25 },
                  py: 1,
                }}
                action={
                  <Tooltip title={chunkingInfoExpanded ? 'Свернуть' : 'Развернуть'} arrow>
                    <IconButton
                      size="small"
                      color="inherit"
                      aria-expanded={chunkingInfoExpanded}
                      aria-label={chunkingInfoExpanded ? 'Свернуть описание чанкования' : 'Развернуть описание чанкования'}
                      onClick={() => setChunkingInfoExpanded((v) => !v)}
                      edge="end"
                    >
                      <ExpandMoreIcon
                        sx={{
                          transform: chunkingInfoExpanded ? 'rotate(180deg)' : 'none',
                          transition: theme.transitions.create('transform', {
                            duration: theme.transitions.duration.shorter,
                          }),
                        }}
                      />
                    </IconButton>
                  </Tooltip>
                }
              >
                <Typography variant="subtitle2" fontWeight="600" gutterBottom>
                  {getChunkingLabel(ragChunkingStrategy)}
                </Typography>
                <Collapse in={chunkingInfoExpanded} timeout="auto" unmountOnExit={false}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {getChunkingDescription(ragChunkingStrategy)}
                    </Typography>
                    <Typography variant="body2" fontWeight="500" sx={{ mt: 1 }}>
                      {getChunkingUseCase(ragChunkingStrategy)}
                    </Typography>
                  </Box>
                </Collapse>
              </Alert>
            </ListItem>

            <Divider />

            <ListItem sx={{ px: 0, py: 1.5, display: 'block' }}>
              <Box sx={ragPillsRowSx}>
                <Box sx={ragPillFieldWrapperSx}>
                <TextField
                  fullWidth
                  size="small"
                  disabled={isLoading}
                  type="number"
                  label={
                    <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX} component="span">
                      Количество чанков (K)
                      <Tooltip
                        title={
                          'Сколько наиболее релевантных фрагментов запрашивать у SVC-RAG и подмешивать в промпт (чат, /api/chat с RAG, агент с документами; в retrieve_rag_context — если k в JSON не указан). ' +
                          'Диапазон 1–64, по умолчанию 5. Больше K — длиннее контекст и медленнее ответ LLM. ' +
                          'Нарезка файла при загрузке в базу не меняется: при индексации используется RecursiveCharacterTextSplitter в SVC-RAG (размер чанка и перекрытие из конфига сервиса, обычно ~1000 символов и ~200 перекрытия).'
                        }
                        arrow
                      >
                        <IconButton
                          size="small"
                          sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <HelpOutlineIcon fontSize="small" color="action" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  }
                  value={ragChatTopK}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') return;
                    const v = parseInt(raw, 10);
                    if (!Number.isNaN(v)) setRagChatTopK(Math.max(1, Math.min(64, v)));
                  }}
                  onBlur={(e) => {
                    const raw = e.target.value.trim();
                    if (raw === '') {
                      setRagChatTopK(5);
                      return;
                    }
                    const n = parseInt(raw, 10);
                    if (Number.isNaN(n)) setRagChatTopK(5);
                    else setRagChatTopK(Math.max(1, Math.min(64, n)));
                  }}
                  inputProps={{ min: 1, max: 64, step: 1 }}
                  sx={MODEL_SETTINGS_INPUT_SX}
                />
                </Box>
                <Box sx={ragPillFieldWrapperSx}>
                <TextField
                  fullWidth
                  size="small"
                  disabled={isLoading}
                  type="number"
                  label="Размер перекрытия"
                  value={ragChunkOverlap}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') return;
                    const v = parseInt(raw, 10);
                    if (!Number.isNaN(v)) setRagChunkOverlap(Math.max(0, Math.min(2000, v)));
                  }}
                  onBlur={(e) => {
                    const raw = e.target.value.trim();
                    if (raw === '') {
                      setRagChunkOverlap(200);
                      return;
                    }
                    const n = parseInt(raw, 10);
                    if (Number.isNaN(n)) setRagChunkOverlap(200);
                    else setRagChunkOverlap(Math.max(0, Math.min(2000, n)));
                  }}
                  inputProps={{ min: 0, max: 2000, step: 10 }}
                  sx={MODEL_SETTINGS_INPUT_SX}
                />
                </Box>
                <Box sx={ragPillFieldWrapperSx}>
                <TextField
                  fullWidth
                  size="small"
                  disabled={isLoading}
                  type="number"
                  label="Порог схожести"
                  value={ragSimilarityThreshold}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') return;
                    const v = Number(raw);
                    if (!Number.isNaN(v)) {
                      setRagSimilarityThreshold(Math.max(0, Math.min(1, Number(v.toFixed(4)))));
                    }
                  }}
                  onBlur={(e) => {
                    const raw = e.target.value.trim();
                    if (raw === '') {
                      setRagSimilarityThreshold(0);
                      return;
                    }
                    const n = Number(raw);
                    if (Number.isNaN(n)) setRagSimilarityThreshold(0);
                    else setRagSimilarityThreshold(Math.max(0, Math.min(1, Number(n.toFixed(4)))));
                  }}
                  inputProps={{ min: 0, max: 1, step: 0.01 }}
                  sx={MODEL_SETTINGS_INPUT_SX}
                />
                </Box>
              </Box>
            </ListItem>

            <Divider />

            <ListItem sx={{ px: 0, py: 1.5, display: 'block' }}>
              <TextField
                fullWidth
                size="small"
                disabled={isLoading}
                multiline
                minRows={4}
                maxRows={12}
                label="Системный промпт для RAG"
                value={ragSystemPrompt}
                onChange={(e) => setRagSystemPrompt(e.target.value)}
                InputLabelProps={{ shrink: true }}
                sx={MODEL_SETTINGS_INPUT_SX}
              />
            </ListItem>
          </List>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', ...MODEL_SETTINGS_RESET_BUTTON_SX }}>
            <Button variant="outlined" startIcon={<RestoreIcon />} onClick={resetRAGSettings} disabled={isLoading}>
              Восстановить настройки
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SearchIcon color="primary" />
            Методы улучшения запросов
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
                    Agentic RAG
                    <Tooltip
                      title={
                        'В режиме чата «Агент»: модель сама запрашивает документы инструментом retrieve_rag_context. ' +
                        'Выключите, чтобы фрагменты из проекта/KB/памяти заранее подмешивались в запрос (классический pre-retrieval). ' +
                        'Нужен режим «Агент» в чате. Стратегия из списка выше применяется к вызовам SVC-RAG из инструментов.'
                      }
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
                            '& .MuiSvgIcon-root': { color: 'primary.main' },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{ variant: 'body1', fontWeight: 500 }}
              />
              <Switch
                checked={agenticRagEnabled}
                onChange={(e) => setAgenticRagEnabled(e.target.checked)}
                disabled={isLoading}
                color="primary"
              />
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
                    Переранжирование
                    <Tooltip title="Cross-encoder переупорядочивает найденные чанки после первичного retrieval." arrow>
                      <IconButton
                        size="small"
                        sx={{
                          p: 0,
                          ml: 0.5,
                          opacity: 0.7,
                          '&:hover': {
                            opacity: 1,
                            '& .MuiSvgIcon-root': { color: 'primary.main' },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{ variant: 'body1', fontWeight: 500 }}
              />
              <Switch
                checked={ragRerankingEnabled}
                onChange={(e) => setRagRerankingEnabled(e.target.checked)}
                disabled={isLoading}
                color="primary"
              />
            </ListItem>

            <Divider />

            <ListItem sx={{ px: 0, py: 1.5, display: 'block' }}>
              <Box sx={ragPillFieldWrapperSx}>
                <TextField
                  fullWidth
                  size="small"
                  disabled={isLoading || !ragRerankingEnabled}
                  type="number"
                  label="Top-N после реранкинга"
                  value={ragRerankTopN}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') return;
                    const v = parseInt(raw, 10);
                    if (!Number.isNaN(v)) setRagRerankTopN(Math.max(1, Math.min(64, v)));
                  }}
                  onBlur={(e) => {
                    const raw = e.target.value.trim();
                    if (raw === '') {
                      setRagRerankTopN(5);
                      return;
                    }
                    const n = parseInt(raw, 10);
                    if (Number.isNaN(n)) setRagRerankTopN(5);
                    else setRagRerankTopN(Math.max(1, Math.min(64, n)));
                  }}
                  inputProps={{ min: 1, max: 64, step: 1 }}
                  sx={MODEL_SETTINGS_INPUT_SX}
                />
              </Box>
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
                    Исправление опечаток в запросе
                    <Tooltip
                      title={
                        'Один короткий запрос к LLM: исправить опечатки в вашей фразе, не меняя смысл. Удобно для ключевых слов и имён; снижает риск промаха лексического поиска (BM25). ' +
                        'До поиска по базе — отдельный вызов LLM. Выключено: фраза уходит в RAG как есть (после нормализации пробелов).'
                      }
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
                            '& .MuiSvgIcon-root': { color: 'primary.main' },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{ variant: 'body1', fontWeight: 500 }}
              />
              <Switch
                checked={ragQueryFixTypos}
                onChange={(e) => setRagQueryFixTypos(e.target.checked)}
                disabled={isLoading}
                color="primary"
              />
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
                    Несколько формулировок (multi-query)
                    <Tooltip
                      title={
                        'LLM генерирует 3-5 коротких альтернативных формулировок того же смысла. По каждой выполняется поиск в RAG, затем результаты объединяются. ' +
                        'Помогает, когда в документе другие слова (например «soft skills» и «софт скилы», «автомобиль» и «машина»), если модель попала в удачные синонимы. ' +
                        'Вызывает LLM и несколько запросов к RAG за один вопрос — ответ в чате медленнее, но выше шанс найти нужные формулировки в документах.'
                      }
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
                            '& .MuiSvgIcon-root': { color: 'primary.main' },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{ variant: 'body1', fontWeight: 500 }}
              />
              <Switch
                checked={ragMultiQueryEnabled}
                onChange={(e) => setRagMultiQueryEnabled(e.target.checked)}
                disabled={isLoading}
                color="primary"
              />
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
                    HyDE (гипотетический ответ для поиска)
                    <Tooltip
                      title={
                        'HyDE: LLM пишет короткий гипотетический ответ на ваш вопрос. Текст добавляется при построении вектора запроса, чтобы ближе по смыслу совпасть с абзацами в документах. ' +
                        'Не подставляет реальные факты из файлов — только улучшает retrieval. Один вызов LLM для гипотетического текста, затем обогащенный запрос уходит в эмбеддинг. Можно включать вместе с multi-query.'
                      }
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
                            '& .MuiSvgIcon-root': { color: 'primary.main' },
                          },
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <HelpOutlineIcon fontSize="small" color="action" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                }
                primaryTypographyProps={{ variant: 'body1', fontWeight: 500 }}
              />
              <Switch
                checked={ragHydeEnabled}
                onChange={(e) => setRagHydeEnabled(e.target.checked)}
                disabled={isLoading}
                color="primary"
              />
            </ListItem>
          </List>
        </CardContent>
      </Card>

      <MemoryRagLibraryModal open={memoryRagModalOpen} onClose={() => setMemoryRagModalOpen(false)} />
    </Box>
  );
}

