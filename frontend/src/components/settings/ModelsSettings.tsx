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
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Upload as UploadIcon,
  Computer as ComputerIcon,
  Memory as MemoryIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';

const API_BASE_URL = 'http://localhost:8000';

export default function ModelsSettings() {
  const [modelSettings, setModelSettings] = useState({
    context_size: 2048,
    output_tokens: 512,
    temperature: 0.7,
    top_p: 0.95,
    repeat_penalty: 1.05,
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
    repeat_penalty: 2.0
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
      // Загружаем глобальный промпт
      const globalResponse = await fetch(`${API_BASE_URL}/api/context-prompts/global`);
      if (globalResponse.ok) {
        const globalData = await globalResponse.json();
        setContextPrompts(prev => ({ ...prev, globalPrompt: globalData.prompt }));
      }

      // Загружаем модели с промптами
      const modelsResponse = await fetch(`${API_BASE_URL}/api/context-prompts/models`);
      if (modelsResponse.ok) {
        const modelsData = await modelsResponse.json();
        setModelsWithPrompts(modelsData.models || []);
        
        // Обновляем промпты моделей
        const modelPrompts: Record<string, string> = {};
        modelsData.models?.forEach((model: any) => {
          if (model.has_custom_prompt) {
            modelPrompts[model.path] = model.context_prompt;
          }
        });
        setContextPrompts(prev => ({ ...prev, modelPrompts }));
      }

      // Загружаем пользовательские промпты
      const customResponse = await fetch(`${API_BASE_URL}/api/context-prompts/custom`);
      if (customResponse.ok) {
        const customData = await customResponse.json();
        setContextPrompts(prev => ({ ...prev, customPrompts: customData.prompts || {} }));
      }
    } catch (error) {
      console.error('Ошибка загрузки контекстных промптов:', error);
      showNotification('error', 'Ошибка загрузки контекстных промптов');
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
        showNotification('success', 'Глобальный промпт сохранен');
        return true;
      } else {
        throw new Error('Ошибка сохранения глобального промпта');
      }
    } catch (error) {
      console.error('Ошибка сохранения глобального промпта:', error);
      showNotification('error', 'Ошибка сохранения глобального промпта');
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
        showNotification('success', 'Промпт модели сохранен');
        return true;
      } else {
        throw new Error('Ошибка сохранения промпта модели');
      }
    } catch (error) {
      console.error('Ошибка сохранения промпта модели:', error);
      showNotification('error', 'Ошибка сохранения промпта модели');
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

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <SettingsIcon color="primary" />
        Настройки моделей
      </Typography>

      {/* Настройки модели Газик ИИ */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SettingsIcon color="primary" />
            Настройки модели Газик ИИ
          </Typography>
          
          <Alert severity="info" sx={{ mb: 2 }}>
            Настройки автоматически сохраняются при изменении
          </Alert>
          
          <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(250px, 1fr))" gap={2}>
            <TextField
              label="Размер контекста"
              type="number"
              value={modelSettings.context_size}
              onChange={(e) => setModelSettings(prev => ({ 
                ...prev, 
                context_size: parseInt(e.target.value) || 2048 
              }))}
              inputProps={{ min: 512, max: maxValues.context_size, step: 512 }}
              fullWidth
            />
            
            <TextField
              label="Максимум токенов ответа"
              type="number"
              value={modelSettings.output_tokens}
              onChange={(e) => setModelSettings(prev => ({ 
                ...prev, 
                output_tokens: parseInt(e.target.value) || 512 
              }))}
              inputProps={{ min: 64, max: maxValues.output_tokens, step: 64 }}
              fullWidth
            />
            
            <TextField
              label="Температура"
              type="number"
              value={modelSettings.temperature}
              onChange={(e) => setModelSettings(prev => ({ 
                ...prev, 
                temperature: parseFloat(e.target.value) || 0.7 
              }))}
              inputProps={{ min: 0.1, max: maxValues.temperature, step: 0.1 }}
              fullWidth
            />
            
            <TextField
              label="Top-p"
              type="number"
              value={modelSettings.top_p}
              onChange={(e) => setModelSettings(prev => ({ 
                ...prev, 
                top_p: parseFloat(e.target.value) || 0.95 
              }))}
              inputProps={{ min: 0.1, max: maxValues.top_p, step: 0.05 }}
              fullWidth
            />
            
            <TextField
              label="Штраф за повторения"
              type="number"
              value={modelSettings.repeat_penalty}
              onChange={(e) => setModelSettings(prev => ({ 
                ...prev, 
                repeat_penalty: parseFloat(e.target.value) || 1.05 
              }))}
              inputProps={{ min: 1.0, max: maxValues.repeat_penalty, step: 0.05 }}
              fullWidth
            />
          </Box>
          
          <Box mt={2}>
            <FormControlLabel
              control={
                <Switch
                  checked={modelSettings.use_gpu}
                  onChange={(e) => setModelSettings(prev => ({ 
                    ...prev, 
                    use_gpu: e.target.checked 
                  }))}
                />
              }
              label="Использовать GPU"
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={modelSettings.streaming}
                  onChange={(e) => setModelSettings(prev => ({ 
                    ...prev, 
                    streaming: e.target.checked 
                  }))}
                />
              }
              label="Потоковая генерация"
            />
            
            {modelSettings.streaming && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Скорость потоковой генерации: {modelSettings.streaming_speed}ms
                </Typography>
                <input
                  type="range"
                  min="10"
                  max="200"
                  step="10"
                  value={modelSettings.streaming_speed}
                  onChange={(e) => setModelSettings(prev => ({ 
                    ...prev, 
                    streaming_speed: parseInt(e.target.value) 
                  }))}
                  style={{
                    width: '100%',
                    height: '6px',
                    borderRadius: '3px',
                    background: 'linear-gradient(to right, #1976d2 0%, #1976d2 50%, #e0e0e0 50%, #e0e0e0 100%)',
                    outline: 'none',
                    WebkitAppearance: 'none',
                  }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    Быстро (10ms)
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Медленно (200ms)
                  </Typography>
                </Box>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Управление моделями */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ComputerIcon color="primary" />
            Управление моделями
          </Typography>
          
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

      {/* Контекстные промпты */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MemoryIcon color="primary" />
            Контекстные промпты
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Настройте системные промпты для моделей. Глобальный промпт применяется ко всем моделям по умолчанию, 
            но вы можете создать индивидуальные промпты для конкретных моделей.
          </Typography>

          {/* Глобальный промпт */}
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="subtitle1" fontWeight="600">
                Глобальный промпт
              </Typography>
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
                {contextPrompts.globalPrompt || 'Глобальный промпт не установлен'}
              </Typography>
            </Box>
          </Box>

          {/* Промпты для моделей */}
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="subtitle1" fontWeight="600">
                Промпты для моделей
              </Typography>
              <Button
                variant="contained"
                size="small"
                startIcon={<span>+</span>}
                onClick={() => setShowModelPromptDialog(true)}
              >
                Добавить промпт
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
                Индивидуальные промпты для моделей не созданы
              </Typography>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Диалог редактирования промптов */}
      <Dialog
        open={promptDialogOpen}
        onClose={() => setPromptDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {promptDialogType === 'global' && 'Редактирование глобального промпта'}
          {promptDialogType === 'model' && 'Редактирование промпта модели'}
        </DialogTitle>
        <DialogContent>
          <TextField
            label="Промпт"
            value={promptDialogData.prompt}
            onChange={(e) => setPromptDialogData(prev => ({ ...prev, prompt: e.target.value }))}
            fullWidth
            multiline
            rows={8}
            placeholder="Введите системный промпт для модели..."
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

      {/* Диалог выбора модели для промпта */}
      <Dialog
        open={showModelPromptDialog}
        onClose={() => setShowModelPromptDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Выберите модель для создания промпта</DialogTitle>
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
                          <Chip label="Есть промпт" size="small" color="primary" />
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







