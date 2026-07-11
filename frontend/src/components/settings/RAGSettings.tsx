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
  getDropdownPopoverPaperSx,
  getDropdownItemSx,
  getDropdownTriggerButtonSx,
  getDropdownTriggerTextSx,
  getDropdownChevronSx,
  getDropdownItemStateSx,
} from '../../constants/menuStyles';
import MemoryRagLibraryModal from '../MemoryRagLibraryModal';
import RagModelSelector from '../RagModelSelector';
import {
  MODEL_SETTINGS_RESET_BUTTON_SX,
  MODEL_SETTINGS_LABEL_WRAPPER_SX,
  MODEL_SETTINGS_HELP_ICON_BUTTON_SX,
  MODEL_SETTINGS_INPUT_SX,
} from '../../constants/modelSettingsStyles';

const RAG_NUM_FIELDS_ROW_SX = {
  display: 'flex',
  flexDirection: { xs: 'column', sm: 'row' },
  gap: 2,
  alignItems: { sm: 'flex-start' },
  flexWrap: 'wrap',
} as const;

const RAG_MODEL_SELECTOR_ROW_SX = {
  display: 'flex',
  flexDirection: { xs: 'column', sm: 'row' },
  justifyContent: 'space-between',
  alignItems: { xs: 'flex-start', sm: 'center' },
  gap: 1.5,
  py: 1,
} as const;

function ragModelRowLabel(label: string, tooltip: string) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0, flexShrink: 0 }}>
      <Typography variant="body1" fontWeight={500}>
        {label}
      </Typography>
      <Tooltip title={tooltip} arrow>
        <IconButton
          size="small"
          sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Справка: ${label}`}
        >
          <HelpOutlineIcon fontSize="small" color="action" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

type RAGStrategy = 'auto' | 'hybrid' | 'vector' | 'graph' | 'lexical';
type ChunkingStrategy = 'hierarchical' | 'fixed' | 'markdown' | 'separators' | 'semantic';
const RAG_STRATEGY_STORAGE_KEY = 'rag_strategy';
const RAG_CHUNKING_STORAGE_KEY = 'rag_chunking_strategy';
const DEFAULT_RAG_SYSTEM_PROMPT =
  'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.';

function normalizeStoredStrategy(raw: string | null): RAGStrategy {
  const s = (raw || 'auto').trim().toLowerCase();
  if (s === 'reranking') return 'hybrid';
  // Однократная миграция старого внутреннего имени; новые запросы его не используют.
  if (s === 'standard') return 'vector';
  if (s === 'auto' || s === 'hybrid' || s === 'vector' || s === 'graph' || s === 'lexical') {
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
  const isDarkMode = theme.palette.mode === 'dark';
  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const dropdownTriggerSx = useMemo(() => getDropdownTriggerButtonSx(isDarkMode), [isDarkMode]);
  const dropdownTriggerTextSx = useMemo(() => getDropdownTriggerTextSx(isDarkMode), [isDarkMode]);
  const dropdownChevronSx = useMemo(() => getDropdownChevronSx(isDarkMode), [isDarkMode]);
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
  const [ragChunkSize, setRagChunkSize] = useState(1000);
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
      // Не перечитываем настройки сразу после PUT: при ошибке/старой версии
      // backend это возвращало прежнее ``auto`` и визуально отменяло выбор.
      void saveRAGSettings();
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
    ragChunkSize,
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
          // Для чата стратегия является пользовательским выбором этого браузера:
          // SocketContext тоже читает её из localStorage. Не затираем её старым
          // серверным ``auto`` при открытии настроек или временной ошибке сохранения.
          const localStrategy =
            typeof localStorage !== 'undefined'
              ? localStorage.getItem(RAG_STRATEGY_STORAGE_KEY)
              : null;
          const next = normalizeStoredStrategy(localStrategy ?? String(data.strategy));
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
        if (typeof data.rag_chunk_size === 'number' && Number.isFinite(data.rag_chunk_size)) {
          setRagChunkSize(Math.max(200, Math.min(8000, Math.round(data.rag_chunk_size))));
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

  const saveRAGSettings = async (): Promise<boolean> => {
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
          rag_chunk_size: ragChunkSize,
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
        return true;
      } else {
        const details = await response.text().catch(() => '');
        throw new Error(`Ошибка сохранения настроек RAG: ${response.status}${details ? ` — ${details}` : ''}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек RAG:', error);
      showNotification('error', 'Не удалось сохранить настройки на сервере. Локальный выбор сохранён.');
      return false;
    }
  };

  const resetRAGSettings = async () => {
    try {
      const response = await fetch(getApiUrl('/api/rag/settings/reset'), { method: 'POST' });
      if (!response.ok) {
        throw new Error(`reset ${response.status}`);
      }
      skipNextRagSaveToastRef.current = true;
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(RAG_STRATEGY_STORAGE_KEY, 'auto');
      }
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
        return 'Гибридный';
      case 'vector':
        return 'Векторный';
      case 'lexical':
        return 'Лексический';
      case 'graph':
        return 'Графовый';
      default:
        return 'Автоматический выбор';
    }
  };

  const getStrategyDescription = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Анализирует формулировку вопроса и сам выбирает одну из четырёх стратегий. Точные фразы и коды направляет в лексический поиск, вопросы по смыслу — в векторный, связи между фактами — в графовый, а для остальных запросов использует гибридный.';
      case 'hybrid':
        return 'Одновременно ищет и по смыслу, и по точным словам. Хорошо подходит для большинства обычных вопросов, когда заранее неизвестно, какой способ поиска даст лучший результат.';
      case 'vector':
        return 'Ищет фрагменты, близкие к вопросу по смыслу, даже если в документе использованы другие слова. Лучше выбирать для пересказов, объяснений и вопросов со свободной формулировкой.';
      case 'lexical':
        return 'Ищет точные слова и формулировки из вопроса. Лучше выбирать для кодов, номеров, артикулов, имён, цитат и терминов, которые должны совпасть с текстом документа.';
      case 'graph':
        return 'Находит подходящие фрагменты и добавляет связанный с ними контекст из документа. Лучше выбирать для сравнений, причин и последствий, цепочек событий и вопросов, ответ на которые расположен в нескольких связанных фрагментах.';
      default:
        return '';
    }
  };

  const getStrategyUseCase = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Выбирайте, если не уверены, какая стратегия лучше подходит к вопросу.';
      case 'hybrid':
        return 'Выбирайте как универсальный режим для повседневной работы с документами.';
      case 'vector':
        return 'Выбирайте, когда смысл важнее совпадения конкретных слов.';
      case 'lexical':
        return 'Выбирайте, когда в документе нужно найти конкретное слово, имя, номер или выражение.';
      case 'graph':
        return 'Выбирайте для сложных вопросов, требующих собрать несколько связанных фактов.';
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
    const scope =
      ' Применяется к RAG проектов и документов агента. Библиотека (кнопка в чате / KB / memory) всегда режется универсальным структурным чанкером.';
    switch (strategy) {
      case 'hierarchical':
        return (
          'Документ сначала делится на крупные смысловые блоки, затем на более мелкие фрагменты. Это обычно дает лучший баланс между полнотой контекста и точностью поиска.' +
          scope
        );
      case 'fixed':
        return (
          'Текст режется на чанки фиксированной длины. Предсказуемо по размеру и скорости, но может разрывать мысль на границах.' +
          scope
        );
      case 'markdown':
        return (
          'Чанкование ориентируется на структуру разметки (заголовки, списки, секции). Хорошо подходит для технической документации и markdown-файлов.' +
          scope
        );
      case 'separators':
        return (
          'Разделение по естественным разделителям (абзацы, переносы, знаки, служебные маркеры). Менее жесткое, чем fixed, и обычно более читабельное.' +
          scope
        );
      case 'semantic':
        return (
          'Смысловое чанкование пытается сохранять цельные идеи внутри чанка (абзацный режим). Обычно дает лучшее качество retrieval.' +
          scope
        );
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

            <ListItem sx={{ px: 0, py: 0.5, display: 'block' }}>
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                <Box sx={RAG_MODEL_SELECTOR_ROW_SX}>
                  {ragModelRowLabel(
                    'Модель эмбеддингов',
                    'Преобразует текст документов и запросов в векторы для семантического поиска в RAG.'
                  )}
                  <Box sx={{ flexShrink: 0, width: { xs: '100%', sm: 'auto' } }}>
                    <RagModelSelector
                      kind="embedding"
                      isDarkMode={theme.palette.mode === 'dark'}
                      disabled={isLoading}
                      triggerMaxWidth={280}
                    />
                  </Box>
                </Box>
                <Box sx={RAG_MODEL_SELECTOR_ROW_SX}>
                  {ragModelRowLabel(
                    'Cross-encoder (реранкер)',
                    'Переупорядочивает найденные чанки после первичного поиска для более точной выдачи.'
                  )}
                  <Box sx={{ flexShrink: 0, width: { xs: '100%', sm: 'auto' } }}>
                    <RagModelSelector
                      kind="reranker"
                      isDarkMode={theme.palette.mode === 'dark'}
                      disabled={isLoading}
                      triggerMaxWidth={280}
                    />
                  </Box>
                </Box>
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
                    ...dropdownTriggerSx,
                    opacity: isLoading ? 0.7 : 1,
                    pointerEvents: isLoading ? 'none' : 'auto',
                  }}
                >
                  <Typography sx={dropdownTriggerTextSx}>
                    {getStrategyLabel(selectedStrategy)}
                  </Typography>
                  <ExpandMoreIcon sx={{ ...dropdownChevronSx, transform: strategyPopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                </Box>
                <Popover
                  open={Boolean(strategyPopoverAnchor)}
                  anchorEl={strategyPopoverAnchor}
                  onClose={() => setStrategyPopoverAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  slotProps={{ paper: { sx: getDropdownPopoverPaperSx(strategyPopoverAnchor, isDarkMode) } }}
                >
                  <Box sx={{ py: 0.5 }}>
                    {(['auto', 'vector', 'lexical', 'hybrid', 'graph'] as const).map((strategy) => (
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
                          ...getDropdownItemStateSx(isDarkMode, selectedStrategy === strategy),
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
                    ...dropdownTriggerSx,
                    opacity: isLoading ? 0.7 : 1,
                    pointerEvents: isLoading ? 'none' : 'auto',
                  }}
                >
                  <Typography sx={dropdownTriggerTextSx}>
                    {getChunkingLabel(ragChunkingStrategy)}
                  </Typography>
                  <ExpandMoreIcon sx={{ ...dropdownChevronSx, transform: chunkingPopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                </Box>
                <Popover
                  open={Boolean(chunkingPopoverAnchor)}
                  anchorEl={chunkingPopoverAnchor}
                  onClose={() => setChunkingPopoverAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  slotProps={{ paper: { sx: getDropdownPopoverPaperSx(chunkingPopoverAnchor, isDarkMode) } }}
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
                          ...getDropdownItemStateSx(isDarkMode, ragChunkingStrategy === strategy),
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
              <Box sx={RAG_NUM_FIELDS_ROW_SX}>
                <Box sx={{ maxWidth: { xs: '100%', sm: 300 }, minWidth: { sm: 260 }, flex: { sm: '0 0 auto' } }}>
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
                            'Сколько наиболее релевантных фрагментов запрашивать у SVC-RAG и подмешивать в промпт. Диапазон 1–64, по умолчанию 5. Больше K — длиннее контекст и медленнее ответ LLM.'
                          }
                          arrow
                        >
                          <IconButton
                            size="small"
                            sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
                            onClick={(e) => e.stopPropagation()}
                            aria-label="Справка: количество чанков"
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
                    InputLabelProps={{ shrink: true }}
                  />
                </Box>
                <Box sx={{ maxWidth: { xs: '100%', sm: 236 }, minWidth: { sm: 200 }, flex: { sm: '0 0 auto' } }}>
                  <TextField
                    fullWidth
                    size="small"
                    disabled={isLoading}
                    type="number"
                    label={
                      <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX} component="span">
                        Размер чанка
                        <Tooltip
                          title="Целевой размер одного чанка в символах при нарезке документа. Диапазон 200–8000, по умолчанию 1000. Меньше — точнее, но больше чанков; больше — шире контекст в каждом фрагменте."
                          arrow
                        >
                          <IconButton
                            size="small"
                            sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
                            onClick={(e) => e.stopPropagation()}
                            aria-label="Справка: размер чанка"
                          >
                            <HelpOutlineIcon fontSize="small" color="action" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    }
                    value={ragChunkSize}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (raw === '') return;
                      const v = parseInt(raw, 10);
                      if (!Number.isNaN(v)) setRagChunkSize(Math.max(200, Math.min(8000, v)));
                    }}
                    onBlur={(e) => {
                      const raw = e.target.value.trim();
                      if (raw === '') {
                        setRagChunkSize(1000);
                        return;
                      }
                      const n = parseInt(raw, 10);
                      if (Number.isNaN(n)) setRagChunkSize(1000);
                      else setRagChunkSize(Math.max(200, Math.min(8000, n)));
                    }}
                    inputProps={{ min: 200, max: 8000, step: 50 }}
                    InputLabelProps={{ shrink: true }}
                  />
                </Box>
                <Box sx={{ maxWidth: { xs: '100%', sm: 236 }, minWidth: { sm: 200 }, flex: { sm: '0 0 auto' } }}>
                  <TextField
                    fullWidth
                    size="small"
                    disabled={isLoading}
                    type="number"
                    label={
                      <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX} component="span">
                        Размер перекрытия
                        <Tooltip
                          title="Количество символов перекрытия между соседними чанками при нарезке документа. Диапазон 0–2000, по умолчанию 200."
                          arrow
                        >
                          <IconButton
                            size="small"
                            sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
                            onClick={(e) => e.stopPropagation()}
                            aria-label="Справка: размер перекрытия"
                          >
                            <HelpOutlineIcon fontSize="small" color="action" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    }
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
                    InputLabelProps={{ shrink: true }}
                  />
                </Box>
                <Box sx={{ maxWidth: { xs: '100%', sm: 236 }, minWidth: { sm: 200 }, flex: { sm: '0 0 auto' } }}>
                  <TextField
                    fullWidth
                    size="small"
                    disabled={isLoading}
                    type="number"
                    label={
                      <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX} component="span">
                        Порог схожести
                        <Tooltip
                          title="Минимальный порог схожести для включения чанка в результат поиска. 0 — без фильтрации, выше — строже отбор. Диапазон 0–1."
                          arrow
                        >
                          <IconButton
                            size="small"
                            sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
                            onClick={(e) => e.stopPropagation()}
                            aria-label="Справка: порог схожести"
                          >
                            <HelpOutlineIcon fontSize="small" color="action" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    }
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
                    InputLabelProps={{ shrink: true }}
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
              <Box sx={{ maxWidth: { xs: '100%', sm: 320 }, minWidth: { sm: 280 }, flex: { sm: '0 0 auto' } }}>
                <TextField
                  fullWidth
                  size="small"
                  disabled={isLoading || !ragRerankingEnabled}
                  type="number"
                  label={
                    <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX} component="span">
                      Количество чанков после реранкинга (Top-N)
                      <Tooltip
                        title="Сколько лучших чанков оставить после переранжирования cross-encoder. Диапазон 1–64, по умолчанию 5. Работает только при включённом переранжировании."
                        arrow
                      >
                        <IconButton
                          size="small"
                          sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX}
                          onClick={(e) => e.stopPropagation()}
                          aria-label="Справка: Top-N после реранкинга"
                        >
                          <HelpOutlineIcon fontSize="small" color="action" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  }
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
                  InputLabelProps={{ shrink: true }}
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

