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
} from '../../constants/modelSettingsStyles';

type RAGStrategy = 'auto' | 'hierarchical' | 'hybrid' | 'standard' | 'graph';
const RAG_STRATEGY_STORAGE_KEY = 'rag_strategy';

function normalizeStoredStrategy(raw: string | null): RAGStrategy {
  const s = (raw || 'auto').trim().toLowerCase();
  if (s === 'reranking') return 'hybrid';
  if (s === 'auto' || s === 'hierarchical' || s === 'hybrid' || s === 'standard' || s === 'graph') {
    return s;
  }
  return 'auto';
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
  const [memoryRagModalOpen, setMemoryRagModalOpen] = useState(false);
  const [agenticRagEnabled, setAgenticRagEnabled] = useState(true);
  const [ragQueryFixTypos, setRagQueryFixTypos] = useState(false);
  const [ragMultiQueryEnabled, setRagMultiQueryEnabled] = useState(false);
  const [ragHydeEnabled, setRagHydeEnabled] = useState(false);
  const [ragChatTopK, setRagChatTopK] = useState(5);
  const [strategyInfoExpanded, setStrategyInfoExpanded] = useState(true);
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
      case 'hierarchical':
        return 'Иерархический поиск';
      case 'hybrid':
        return 'Гибридный поиск';
      case 'standard':
        return 'Стандартный поиск';
      case 'graph':
        return 'Graph RAG (графовый поиск)';
      default:
        return 'Автоматический выбор';
    }
  };

  const getStrategyDescription = (strategy: RAGStrategy): string => {
    switch (strategy) {
      case 'auto':
        return 'Сервер сам выбирает режим среди доступных: гибрид (BM25+вектор), граф, иерархия (только глобальная библиотека, если построен индекс) или стандартный вектор — по тексту запроса и флагу RAG_AUTO_MODE (heuristic по умолчанию или priority). Переранжирование (cross-encoder) включается настройками SVC-RAG для выбранного режима.';
      case 'hierarchical':
        return 'Умный поиск по иерархической структуре документов. Автоматически выбирает между быстрой стратегией (summary) для общих вопросов и детальной (detailed) для конкретных. Идеально для больших документов.';
      case 'hybrid':
        return 'Комбинирует векторный поиск (семантический) и BM25 (ключевые слова), объединяет кандидатов; при RAG_USE_RERANKING в SVC-RAG — cross-encoder переупорядочивает фрагменты под запрос. Так легче попасть в нужный абзац (например, место работы в резюме).';
      case 'standard':
        return 'Базовый векторный поиск через pgvector с использованием cosine similarity. Самый быстрый вариант, но менее точный. Используется как fallback, если другие стратегии недоступны.';
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
      case 'hierarchical':
        return 'Используйте для работы с большими документами (отчеты, книги, длинные тексты).';
      case 'hybrid':
        return 'Используйте когда нужен баланс между точностью и скоростью, особенно для поиска по ключевым словам и датам.';
      case 'standard':
        return 'Используйте только если другие стратегии недоступны или нужна максимальная скорость.';
      case 'graph':
        return 'Используйте для сложных запросов, где ответ требует объединять факты из нескольких связанных фрагментов.';
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
                    {(['auto', 'hierarchical', 'hybrid', 'standard', 'graph'] as const).map((strategy) => (
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

            <ListItem sx={{ px: 0, py: 1.5, display: 'block' }}>
              <Box sx={{ maxWidth: { xs: '100%', sm: 236 }, minWidth: 0 }}>
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
                        'LLM генерирует 3–5 коротких альтернативных формулировок того же смысла. По каждой выполняется поиск в RAG, затем результаты объединяются. ' +
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
                        'Не подставляет реальные факты из файлов — только улучшает retrieval. Один вызов LLM для гипотетического текста, затем обогащённый запрос уходит в эмбеддинг. Можно включать вместе с multi-query.'
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

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', ...MODEL_SETTINGS_RESET_BUTTON_SX }}>
            <Button variant="outlined" startIcon={<RestoreIcon />} onClick={resetRAGSettings} disabled={isLoading}>
              Восстановить настройки
            </Button>
          </Box>
        </CardContent>
      </Card>

      <MemoryRagLibraryModal open={memoryRagModalOpen} onClose={() => setMemoryRagModalOpen(false)} />
    </Box>
  );
}

