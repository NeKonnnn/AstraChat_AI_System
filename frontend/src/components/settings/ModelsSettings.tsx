import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Switch,
  FormControl,
  FormControlLabel,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Alert,
  List,
  ListItem,
  ListItemText,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Divider,
  IconButton,
  Tooltip,
  InputAdornment,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Upload as UploadIcon,
  Computer as ComputerIcon,
  Memory as MemoryIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
  HelpOutline as HelpOutlineIcon,
  Restore as RestoreIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';
import ModelSelector from '../ModelSelector';
import { useTheme } from '@mui/material';
import { API_CONFIG } from '../../config/api';

const API_BASE_URL = API_CONFIG.BASE_URL;

export default function ModelsSettings() {
  const [showModelSelectorInSettings, setShowModelSelectorInSettings] = useState(() => {
    const saved = localStorage.getItem('show_model_selector_in_settings');
    return saved !== null ? saved === 'true' : false;
  });
  
  const [modelSettings, setModelSettings] = useState({
    context_size: 2048,
    output_tokens: 512,
    temperature: 0.7,
    top_p: 0.95,
    repeat_penalty: 1.05,
    top_k: 40,
    min_p: 0.05,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    use_gpu: false,
    streaming: true,
    streaming_speed: 50,
  });

  const [maxValues, setMaxValues] = useState({
    context_size: 32768,
    output_tokens: 8192,
    batch_size: 2048,
    n_threads: 24,
    temperature: 2.0,
    top_p: 1.0,
    repeat_penalty: 2.0,
    top_k: 200,
    min_p: 1.0,
    frequency_penalty: 2.0,
    presence_penalty: 2.0
  });

  const [contextPrompts, setContextPrompts] = useState({
    globalPrompt: '',
    modelPrompts: {} as Record<string, string>,
    customPrompts: {} as Record<string, { prompt: string; description: string; created_at: string }>,
  });

  const [modelsWithPrompts, setModelsWithPrompts] = useState<Array<{
    name: string;
    path: string;
    size: number;
    size_mb: number;
    context_prompt: string;
    has_custom_prompt: boolean;
  }>>([]);

  const [availableModels, setAvailableModels] = useState<Array<{
    name: string;
    path: string;
    size: number;
    size_mb: number;
  }>>([]);

  const [currentModel, setCurrentModel] = useState<any>(null);
  const [selectedModelPath, setSelectedModelPath] = useState<string>("");
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [showModelDialog, setShowModelDialog] = useState(false);
  const [promptDialogOpen, setPromptDialogOpen] = useState(false);
  const [promptDialogType, setPromptDialogType] = useState<'global' | 'model'>('global');
  const [promptDialogData, setPromptDialogData] = useState({ prompt: '', description: '', id: '' });
  const [selectedModelForPrompt, setSelectedModelForPrompt] = useState<string>('');
  const [showModelPromptDialog, setShowModelPromptDialog] = useState(false);

  const { showNotification } = useAppActions();

  useEffect(() => {
    loadSettings();
    loadModels();
    loadCurrentModel();
    loadContextPrompts();
    
    // Слушаем изменения настроек
    const handleSettingsChange = () => {
      const saved = localStorage.getItem('show_model_selector_in_settings');
      setShowModelSelectorInSettings(saved !== null ? saved === 'true' : false);
    };
    
    window.addEventListener('interfaceSettingsChanged', handleSettingsChange);
    return () => window.removeEventListener('interfaceSettingsChanged', handleSettingsChange);
  }, []);

  // Автосохранение настроек модели
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveModelSettings();
    }, 1000); // Сохраняем через 1 секунду после изменения

    return () => clearTimeout(timeoutId);
  }, [modelSettings]);

  const loadSettings = async () => {
    try {
      // Загружаем настройки модели
      const modelResponse = await fetch(`${API_BASE_URL}/api/models/settings`);
      if (modelResponse.ok) {
        const modelData = await modelResponse.json();
        setModelSettings(prev => ({ ...prev, ...modelData }));
      }
      
      // Загружаем максимальные значения
      const maxResponse = await fetch(`${API_BASE_URL}/api/models/settings/recommended`);
      if (maxResponse.ok) {
        const maxData = await maxResponse.json();
        if (maxData.max_values) {
          setMaxValues(maxData.max_values);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек:', error);
    }
  };

  const saveModelSettings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(modelSettings),
      });
      
      if (response.ok) {
        showNotification('success', 'Настройки модели сохранены');
      } else {
        throw new Error(`Ошибка сохранения настроек модели: ${response.status}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек модели:', error);
      showNotification('error', 'Ошибка сохранения настроек модели');
    }
  };

  const resetModelSettings = () => {
    const defaultSettings = {
      context_size: 2048,
      output_tokens: 512,
      temperature: 0.7,
      top_p: 0.95,
      repeat_penalty: 1.05,
      top_k: 40,
      min_p: 0.05,
      frequency_penalty: 0.0,
      presence_penalty: 0.0,
      use_gpu: false,
      streaming: true,
      streaming_speed: 50,
    };
    setModelSettings(defaultSettings);
    showNotification('success', 'Настройки модели восстановлены до значений по умолчанию');
  };

  const loadModels = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models`);
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || []);
      }
    } catch (err) {
      console.error('Ошибка загрузки моделей:', err);
    }
  };

  const loadCurrentModel = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models/current`);
      if (response.ok) {
        const data = await response.json();
        setCurrentModel(data);
        setSelectedModelPath(data.path || "");
      }
    } catch (err) {
      console.warn('Не удалось загрузить текущую модель:', err);
    }
  };

  const loadContextPrompts = async () => {
    try {
      // Загружаем глобальную инструкцию
      const globalResponse = await fetch(`${API_BASE_URL}/api/context-prompts/global`);
      if (globalResponse.ok) {
        const globalData = await globalResponse.json();
        setContextPrompts(prev => ({ ...prev, globalPrompt: globalData.prompt }));
      }

      // Загружаем модели с инструкциями
      const modelsResponse = await fetch(`${API_BASE_URL}/api/context-prompts/models`);
      if (modelsResponse.ok) {
        const modelsData = await modelsResponse.json();
        setModelsWithPrompts(modelsData.models || []);
        
        // Обновляем инструкции моделей
        const modelPrompts: Record<string, string> = {};
        modelsData.models?.forEach((model: any) => {
          if (model.has_custom_prompt) {
            modelPrompts[model.path] = model.context_prompt;
          }
        });
        setContextPrompts(prev => ({ ...prev, modelPrompts }));
      }

      // Загружаем пользовательские инструкции
      const customResponse = await fetch(`${API_BASE_URL}/api/context-prompts/custom`);
      if (customResponse.ok) {
        const customData = await customResponse.json();
        setContextPrompts(prev => ({ ...prev, customPrompts: customData.prompts || {} }));
      }
    } catch (error) {
      console.error('Ошибка загрузки контекстных инструкций:', error);
      showNotification('error', 'Ошибка загрузки контекстных инструкций');
    }
  };

  const saveGlobalPrompt = async (prompt: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/context-prompts/global`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      
      if (response.ok) {
        setContextPrompts(prev => ({ ...prev, globalPrompt: prompt }));
        showNotification('success', 'Глобальная инструкция сохранена');
        return true;
      } else {
        throw new Error('Ошибка сохранения глобальной инструкции');
      }
    } catch (error) {
      console.error('Ошибка сохранения глобальной инструкции:', error);
      showNotification('error', 'Ошибка сохранения глобальной инструкции');
      return false;
    }
  };

  const saveModelPrompt = async (modelPath: string, prompt: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/context-prompts/model/${encodeURIComponent(modelPath)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      
      if (response.ok) {
        setContextPrompts(prev => ({
          ...prev,
          modelPrompts: { ...prev.modelPrompts, [modelPath]: prompt }
        }));
        showNotification('success', 'Инструкция модели сохранена');
        return true;
      } else {
        throw new Error('Ошибка сохранения инструкции модели');
      }
    } catch (error) {
      console.error('Ошибка сохранения инструкции модели:', error);
      showNotification('error', 'Ошибка сохранения инструкции модели');
      return false;
    }
  };

  const loadModel = async (modelPath: string) => {
    try {
      setIsLoadingModel(true);
      
      const response = await fetch(`${API_BASE_URL}/api/models/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_path: modelPath }),
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          showNotification('success', 'Модель успешно загружена!');
          setSelectedModelPath(modelPath);
          loadCurrentModel();
        } else {
          throw new Error(data.message || 'Не удалось загрузить модель');
        }
      } else {
        throw new Error('Ошибка загрузки модели');
      }
      
    } catch (err) {
      showNotification('error', `Ошибка загрузки модели: ${err}`);
    } finally {
      setIsLoadingModel(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const openPromptDialog = (type: 'global' | 'model', data?: any) => {
    setPromptDialogType(type);
    if (type === 'global') {
      setPromptDialogData({ prompt: contextPrompts.globalPrompt, description: '', id: '' });
    } else if (type === 'model' && data) {
      setPromptDialogData({ 
        prompt: contextPrompts.modelPrompts[data.path] || contextPrompts.globalPrompt, 
        description: '', 
        id: data.path 
      });
      setSelectedModelForPrompt(data.path);
    } else {
      setPromptDialogData({ prompt: '', description: '', id: '' });
    }
    setPromptDialogOpen(true);
  };

  const handlePromptDialogSave = async () => {
    let success = false;
    if (promptDialogType === 'global') {
      success = await saveGlobalPrompt(promptDialogData.prompt);
    } else if (promptDialogType === 'model') {
      success = await saveModelPrompt(selectedModelForPrompt, promptDialogData.prompt);
    }

    if (success) {
      setPromptDialogOpen(false);
      await loadContextPrompts();
    }
  };

  const theme = useTheme();
  const isDarkMode = theme.palette.mode === 'dark';

  return (
    <Box sx={{ p: 3 }}>
      {/* Выбор модели - показываем только если включено в настройках */}
      {showModelSelectorInSettings && (
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ComputerIcon color="primary" />
            Выбор модели
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <ModelSelector 
              isDarkMode={isDarkMode}
              onModelSelect={(modelPath) => {
                console.log('Модель выбрана:', modelPath);
                loadCurrentModel();
              }}
            />
          </Box>
          
          {/* Информация о текущей модели */}
          {currentModel?.loaded ? (
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <ComputerIcon color="primary" />
                <Chip label="Загружена" color="success" size="small" />
              </Box>
              <Typography variant="body1" fontWeight="500" gutterBottom>
                {currentModel.metadata?.['general.name'] || 'Неизвестная модель'}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Архитектура: {currentModel.metadata?.['general.architecture'] || 'Неизвестно'}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Контекст: {currentModel.n_ctx || 'Неизвестно'} токенов
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                Путь: {currentModel.path}
              </Typography>
            </Box>
          ) : (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Модель не загружена
            </Alert>
          )}
          
          <Button
            variant="outlined"
            startIcon={<UploadIcon />}
            onClick={() => setShowModelDialog(true)}
            disabled={isLoadingModel}
            fullWidth
          >
            {isLoadingModel ? 'Загрузка модели...' : 'Сменить модель'}
          </Button>
        </CardContent>
      </Card>
      )}

      {/* Настройки модели astrachat */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SettingsIcon color="primary" />
            Настройки выбранной модели
            <Tooltip title="Настройки автоматически сохраняются при изменении" arrow>
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
          
          {/* Тонкая настройка - аккордеон */}
          <Accordion sx={{ mt: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SettingsIcon />
                <Typography variant="subtitle1">Тонкая настройка</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(250px, 1fr))" gap={2}>
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Размер контекста
                      <Tooltip title="Максимальное количество токенов, которые модель может использовать для понимания контекста. Больше значение = больше контекста, но больше потребление памяти." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.context_size}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, context_size: 0 }));
                    } else {
                      const numValue = parseInt(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, context_size: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, context_size: 2048 }));
                    } else {
                      const value = parseInt(strValue);
                      if (isNaN(value) || value < 512) {
                        setModelSettings(prev => ({ ...prev, context_size: 2048 }));
                      }
                    }
                  }}
                  inputProps={{ min: 512, max: maxValues.context_size, step: 512 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      max_tokens
                      <Tooltip title="Этот параметр устанавливает максимальное количество токенов, которые модель может генерировать в своем ответе. Увеличение этого ограничения позволяет модели предоставлять более длинные ответы, но также может увеличить вероятность создания бесполезного или нерелевантного контента." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.output_tokens}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, output_tokens: 0 }));
                    } else {
                      const numValue = parseInt(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, output_tokens: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, output_tokens: 512 }));
                    } else {
                      const value = parseInt(strValue);
                      if (isNaN(value) || value < 64) {
                        setModelSettings(prev => ({ ...prev, output_tokens: 512 }));
                      }
                    }
                  }}
                  inputProps={{ min: 64, max: maxValues.output_tokens, step: 64 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Температура
                      <Tooltip title="Контролирует случайность генерации. Низкие значения (0.1-0.5) делают ответы более детерминированными и точными. Высокие значения (0.8-1.5) делают ответы более креативными и разнообразными." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.temperature}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, temperature: 0 }));
                    } else {
                      const numValue = parseFloat(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, temperature: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, temperature: 0.7 }));
                    } else {
                      const value = parseFloat(strValue);
                      if (isNaN(value) || value < 0.1) {
                        setModelSettings(prev => ({ ...prev, temperature: 0.7 }));
                      }
                    }
                  }}
                  inputProps={{ min: 0.1, max: maxValues.temperature, step: 0.1 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Top-p
                      <Tooltip title="Работает совместно с top-k. Более высокое значение (например, 0,95) приведет к более разнообразному тексту, в то время как более низкое значение, например 0,5) приведет к созданию более сфокусированного и консервативного текста." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.top_p}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, top_p: 0 }));
                    } else {
                      const numValue = parseFloat(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, top_p: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, top_p: 0.95 }));
                    } else {
                      const value = parseFloat(strValue);
                      if (isNaN(value) || value < 0.1) {
                        setModelSettings(prev => ({ ...prev, top_p: 0.95 }));
                      }
                    }
                  }}
                  inputProps={{ min: 0.1, max: maxValues.top_p, step: 0.05 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Repeat penalty
                      <Tooltip title="Применяет штраф к уже использованным токенам в текущем ответе, чтобы уменьшить вероятность их повторения. Работает ПОСЛЕ фильтрации top_p/top_k, модифицируя вероятности уже использованных слов. Значения выше 1.0 (например, 1.1-1.2) уменьшают повторения, значения ниже 1.0 могут их увеличить. Это НЕ то же самое, что top_p или top_k - они фильтруют кандидатов, а repeat_penalty наказывает уже использованные слова." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.repeat_penalty}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, repeat_penalty: 0 }));
                    } else {
                      const numValue = parseFloat(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, repeat_penalty: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, repeat_penalty: 1.05 }));
                    } else {
                      const value = parseFloat(strValue);
                      if (isNaN(value) || value < 1.0) {
                        setModelSettings(prev => ({ ...prev, repeat_penalty: 1.05 }));
                      }
                    }
                  }}
                  inputProps={{ min: 1.0, max: maxValues.repeat_penalty, step: 0.05 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Top-k
                      <Tooltip title="Ограничивает выборку только k наиболее вероятными токенами. Например, top_k=40 означает, что модель будет выбирать только из 40 наиболее вероятных вариантов. Это метод фильтрации кандидатов ДО выборки следующего токена. Большее значение (100+) даст более разнообразные ответы, меньшее (10-20) - более консервативные и предсказуемые." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.top_k}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, top_k: 0 }));
                    } else {
                      const numValue = parseInt(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, top_k: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, top_k: 40 }));
                    } else {
                      const value = parseInt(strValue);
                      if (isNaN(value) || value < 1) {
                        setModelSettings(prev => ({ ...prev, top_k: 40 }));
                      }
                    }
                  }}
                  inputProps={{ min: 1, max: maxValues.top_k, step: 1 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Min-p
                      <Tooltip title="Альтернатива top_p и направлена на обеспечение баланса качества и разнообразия. Параметр p представляет минимальную вероятность того, что токен будет рассмотрен по сравнению с вероятностью наиболее вероятного токена. Например при p=0,05 и наиболее вероятно значении токена, имеющем вероятность 0,9, логиты со значением менее 0,045 отфильтровываются." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.min_p}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, min_p: 0 }));
                    } else {
                      const numValue = parseFloat(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, min_p: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, min_p: 0.05 }));
                    } else {
                      const value = parseFloat(strValue);
                      if (isNaN(value)) {
                        setModelSettings(prev => ({ ...prev, min_p: 0.05 }));
                      }
                    }
                  }}
                  inputProps={{ min: 0.0, max: maxValues.min_p, step: 0.01 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Frequency penalty
                      <Tooltip title="Устанавливает смещение масштабирования для токенов, чтобы наказывать за повторения, в зависимости от того, сколько раз они появились. Более высокое значение (например, 1,5) будет наказывать за повторения более строго, в то время как более низкое значение (например 0,9) будет более мягким. При значении 0 оно отключается" arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.frequency_penalty}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, frequency_penalty: 0 }));
                    } else {
                      const numValue = parseFloat(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, frequency_penalty: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, frequency_penalty: 0.0 }));
                    } else {
                      const value = parseFloat(strValue);
                      if (isNaN(value)) {
                        setModelSettings(prev => ({ ...prev, frequency_penalty: 0.0 }));
                      }
                    }
                  }}
                  inputProps={{ min: 0.0, max: maxValues.frequency_penalty, step: 0.1 }}
                  fullWidth
                />
                
                <TextField
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Presence penalty
                      <Tooltip title="Устанавливает нулевое значение для символов, которые появились хотя бы один раз. Более высокое значение (например 1,5) будет более строгим наказанием за повторения, в то время как более низкое значение (например, 0,9) будет более мягким. При значении 0 он отключается." arrow>
                        <IconButton 
                          size="small" 
                          sx={{ 
                            p: 0,
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
                  type="number"
                  value={modelSettings.presence_penalty}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === '') {
                      setModelSettings(prev => ({ ...prev, presence_penalty: 0 }));
                    } else {
                      const numValue = parseFloat(value);
                      if (!isNaN(numValue)) {
                        setModelSettings(prev => ({ ...prev, presence_penalty: numValue }));
                      }
                    }
                  }}
                  onBlur={(e) => {
                    const strValue = e.target.value.trim();
                    if (strValue === '') {
                      setModelSettings(prev => ({ ...prev, presence_penalty: 0.0 }));
                    } else {
                      const value = parseFloat(strValue);
                      if (isNaN(value)) {
                        setModelSettings(prev => ({ ...prev, presence_penalty: 0.0 }));
                      }
                    }
                  }}
                  inputProps={{ min: 0.0, max: maxValues.presence_penalty, step: 0.1 }}
                  fullWidth
                />
              </Box>
            </AccordionDetails>
          </Accordion>
          
          {/* Слайдеры в стиле раздела "Интерфейс" */}
          <List sx={{ mt: 2 }}>
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
                    Использовать GPU
                    <Tooltip title="Использование графического процессора для ускорения работы модели. Требует наличие GPU с поддержкой CUDA." arrow>
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
              <Switch
                checked={modelSettings.use_gpu}
                onChange={(e) => setModelSettings(prev => ({ 
                  ...prev, 
                  use_gpu: e.target.checked 
                }))}
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
                    Потоковая генерация
                    <Tooltip title="Показывать ответ модели по мере генерации (токен за токеном) вместо ожидания полного ответа. Улучшает восприятие скорости работы." arrow>
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
              <Switch
                checked={modelSettings.streaming}
                onChange={(e) => setModelSettings(prev => ({ 
                  ...prev, 
                  streaming: e.target.checked 
                }))}
              />
            </ListItem>
          </List>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 3 }}>
            <Button
              variant="outlined"
              startIcon={<RestoreIcon />}
              onClick={resetModelSettings}
            >
              Восстановить настройки
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Контекстные инструкции */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MemoryIcon color="primary" />
            Контекстные инструкции
          </Typography>

          {/* Глобальная инструкция */}
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="subtitle1" fontWeight="600">
                  Глобальная инструкция
                </Typography>
                <Tooltip title="Инструкция применяется ко всем моделям" arrow>
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
              </Box>
              <Button
                variant="outlined"
                size="small"
                onClick={() => openPromptDialog('global')}
              >
                Редактировать
              </Button>
            </Box>
            <Box sx={{ 
              p: 2, 
              bgcolor: 'background.default', 
              borderRadius: 1, 
              maxHeight: 150,
              overflow: 'auto'
            }}>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: 'text.secondary' }}>
                {contextPrompts.globalPrompt || 'Глобальная инструкция не установлена'}
              </Typography>
            </Box>
          </Box>

          {/* Инструкции для моделей */}
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="subtitle1" fontWeight="600">
                  Инструкции для моделей
                </Typography>
                <Tooltip title="Инструкция применяется к конкретной модели" arrow>
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
              </Box>
              <Button
                variant="outlined"
                size="small"
                onClick={() => setShowModelPromptDialog(true)}
              >
                Добавить инструкцию
              </Button>
            </Box>
            {modelsWithPrompts.filter(model => model.has_custom_prompt).length > 0 ? (
              <List>
                {modelsWithPrompts.filter(model => model.has_custom_prompt).map((model) => (
                  <ListItem key={model.path} sx={{ 
                    border: '1px solid', 
                    borderColor: 'grey.400', 
                    borderRadius: 1, 
                    mb: 1,
                    bgcolor: 'background.default'
                  }}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="subtitle2" color="text.primary">
                            {model.name}
                          </Typography>
                          <Chip label="Кастомный" size="small" color="primary" />
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            {model.path}
                          </Typography>
                          <Box sx={{ 
                            p: 1, 
                            bgcolor: 'background.default', 
                            borderRadius: 1,
                            maxHeight: 60,
                            overflow: 'hidden'
                          }}>
                            <Typography variant="body2" sx={{ 
                              whiteSpace: 'pre-wrap',
                              color: 'text.secondary'
                            }}>
                              {model.context_prompt}
                            </Typography>
                          </Box>
                        </Box>
                      }
                    />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => openPromptDialog('model', model)}
                      >
                        Изменить
                      </Button>
                    </Box>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Индивидуальные инструкции для моделей не созданы
              </Typography>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Диалог редактирования инструкций */}
      <Dialog
        open={promptDialogOpen}
        onClose={() => setPromptDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {promptDialogType === 'global' && 'Редактирование глобальной инструкции'}
          {promptDialogType === 'model' && 'Редактирование инструкции модели'}
        </DialogTitle>
        <DialogContent>
          <TextField
            label="Инструкция"
            value={promptDialogData.prompt}
            onChange={(e) => setPromptDialogData(prev => ({ ...prev, prompt: e.target.value }))}
            fullWidth
            multiline
            rows={8}
            placeholder="Введите системную инструкцию для модели..."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPromptDialogOpen(false)}>
            Отмена
          </Button>
          <Button onClick={handlePromptDialogSave} variant="contained">
            Сохранить
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог выбора модели для инструкции */}
      <Dialog
        open={showModelPromptDialog}
        onClose={() => setShowModelPromptDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Выберите модель для создания инструкции</DialogTitle>
        <DialogContent>
          {modelsWithPrompts.length > 0 ? (
            <List>
              {modelsWithPrompts.map((model) => (
                <ListItem 
                  key={model.path} 
                  component="div"
                  onClick={() => {
                    setSelectedModelForPrompt(model.path);
                    openPromptDialog('model', model);
                    setShowModelPromptDialog(false);
                  }}
                  sx={{ 
                    border: '1px solid', 
                    borderColor: 'grey.300', 
                    borderRadius: 1, 
                    mb: 1,
                    bgcolor: model.has_custom_prompt ? 'primary.50' : 'background.default',
                    cursor: 'pointer',
                    '&:hover': {
                      bgcolor: model.has_custom_prompt ? 'primary.100' : 'action.hover'
                    }
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle2">
                          {model.name}
                        </Typography>
                        {model.has_custom_prompt && (
                          <Chip label="Есть инструкция" size="small" color="primary" />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {model.path}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Размер: {model.size_mb} MB
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Модели не найдены
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowModelPromptDialog(false)}>
            Отмена
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог выбора модели */}
      <Dialog
        open={showModelDialog}
        onClose={() => setShowModelDialog(false)}
        maxWidth="md"
        fullWidth
        TransitionComponent={undefined}
        transitionDuration={0}
      >
        <DialogTitle>Выбор модели</DialogTitle>
        <DialogContent>
          {availableModels.length === 0 ? (
            <Alert severity="info">
              Модели не найдены. Поместите GGUF файлы в директорию models/
            </Alert>
          ) : (
            <List>
              {availableModels.map((model, index) => (
                <ListItem
                  key={index}
                  component="div"
                  sx={{ 
                    cursor: 'pointer',
                    borderRadius: 1,
                    '&:hover': { backgroundColor: 'action.hover' },
                    backgroundColor: selectedModelPath === model.path ? 'action.selected' : 'transparent',
                    border: selectedModelPath === model.path ? '2px solid #1976d2' : '1px solid transparent',
                    mb: 1,
                  }}
                  onClick={() => setSelectedModelPath(model.path)}
                >
                  <ListItemText
                    primary={model.name}
                    secondary={
                      <Box>
                        <Typography variant="caption" display="block">
                          Размер: {formatFileSize(model.size)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {model.path}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
              ))}
            </List>
          )}
          
          {isLoadingModel && <LinearProgress sx={{ mt: 2 }} />}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setShowModelDialog(false)} 
            disabled={isLoadingModel}
          >
            Отмена
          </Button>
          <Button
            onClick={() => {
              if (selectedModelPath) {
                loadModel(selectedModelPath);
                setShowModelDialog(false);
              }
            }}
            disabled={!selectedModelPath || isLoadingModel}
            variant="contained"
          >
            {isLoadingModel ? 'Загрузка...' : 'Загрузить модель'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}







