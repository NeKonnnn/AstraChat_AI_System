import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Menu,
  MenuItem,
  CircularProgress,
} from '@mui/material';
import {
  Computer as ComputerIcon,
  KeyboardArrowDown as KeyboardArrowDownIcon,
} from '@mui/icons-material';
import { useAppActions } from '../contexts/AppContext';
import { API_CONFIG } from '../config/api';

const API_BASE_URL = API_CONFIG.BASE_URL;

interface Model {
  name: string;
  path: string;
  size?: number;
  size_mb?: number;
}

interface ModelSelectorProps {
  isDarkMode: boolean;
  onModelSelect?: (modelPath: string) => void;
}

// Описания моделей на основе их имен
const getModelDescription = (modelName: string): string => {
  const name = modelName.toLowerCase();
  
  if (name.includes('qwen3-max')) {
    return 'Самая мощная языковая модель в серии Qwen.';
  }
  if (name.includes('qwen3-vl') && name.includes('235b')) {
    return 'Мощная модель взаимодействия изображений и языка на основе Qwen3';
  }
  if (name.includes('qwen3-coder')) {
    return 'Сильный агент программирования, способный выполнять задачи на длительном временном горизонте';
  }
  if (name.includes('qwen3-vl') && name.includes('32b')) {
    return 'Мощная плотная модель визуально-речевого взаимодействия из серии Qwen3-VL.';
  }
  if (name.includes('qwen')) {
    return 'Мощная языковая модель серии Qwen';
  }
  if (name.includes('coder') || name.includes('code')) {
    return 'Специализированная модель для программирования и работы с кодом';
  }
  if (name.includes('mistral')) {
    return 'Эффективная языковая модель Mistral';
  }
  if (name.includes('deepseek')) {
    return 'Продвинутая модель для рассуждений и программирования';
  }
  if (name.includes('llama') || name.includes('codellama')) {
    return 'Мощная модель для программирования и общих задач';
  }
  
  return 'Языковая модель для различных задач';
};

export default function ModelSelector({ isDarkMode, onModelSelect }: ModelSelectorProps) {
  const [availableModels, setAvailableModels] = useState<Model[]>([]);
  const [currentModel, setCurrentModel] = useState<any>(null);
  const [selectedModelPath, setSelectedModelPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const open = Boolean(anchorEl);
  
  const { showNotification } = useAppActions();

  useEffect(() => {
    loadModels();
    loadCurrentModel();
  }, []);

  const loadModels = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/models`);
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || []);
      }
    } catch (err) {
      
    } finally {
      setIsLoading(false);
    }
  };

  const loadCurrentModel = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/models/current`);
      if (response.ok) {
        const data = await response.json();
        
        setCurrentModel(data);
        setSelectedModelPath(data.path || '');
      }
    } catch (err) {
      
    }
  };

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleModelSelect = async (modelPath: string) => {
    if (modelPath === selectedModelPath) {
      handleClose();
      return;
    }
    
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
          setSelectedModelPath(modelPath);
          await loadCurrentModel();
          showNotification('success', 'Модель успешно загружена!');
          handleClose();
          if (onModelSelect) {
            onModelSelect(modelPath);
          }
        } else {
          throw new Error(data.message || 'Не удалось загрузить модель');
        }
      } else {
        throw new Error('Ошибка загрузки модели');
      }
    } catch (err: any) {
      showNotification('error', `Ошибка загрузки модели: ${err.message || err}`);
    } finally {
      setIsLoadingModel(false);
    }
  };

  const getCurrentModelName = () => {
    // Сначала проверяем, есть ли название модели напрямую в ответе API
    if (currentModel?.name && currentModel.name !== 'Неизвестно' && currentModel.name !== 'Unknown') {
      return currentModel.name;
    }
    
    // Проверяем метаданные, но игнорируем "Неизвестно"
    const metadataName = currentModel?.metadata?.['general.name'];
    if (metadataName && metadataName !== 'Неизвестно' && metadataName !== 'Unknown') {
      return metadataName;
    }
    
    // Если есть путь к модели, пытаемся найти её в списке доступных моделей
    const modelPath = currentModel?.path || selectedModelPath;
    if (modelPath) {
      const model = availableModels.find(m => m.path === modelPath);
      if (model) {
        return model.name.replace('.gguf', '');
      }
      // Если модель не найдена в списке, извлекаем название из пути
      const fileName = modelPath.split('/').pop() || modelPath.split('\\').pop();
      if (fileName) {
        return fileName.replace('.gguf', '');
      }
    }
    
    return 'Выберите модель';
  };

  if (isLoading) {
    return (
      <Button
        disabled
        sx={{
          color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
          textTransform: 'none',
        }}
      >
        <CircularProgress size={16} sx={{ mr: 1 }} />
        Загрузка моделей...
      </Button>
    );
  }

  if (availableModels.length === 0) {
    return null;
  }

  const currentModelName = getCurrentModelName();
  const hasSelectedModel = currentModelName !== 'Выберите модель';

  return (
    <Box>
      <Box
        ref={containerRef}
        onClick={isLoadingModel ? undefined : handleClick}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 0.5,
          userSelect: 'none',
          cursor: isLoadingModel ? 'default' : 'pointer',
          opacity: isLoadingModel ? 0.6 : 1,
          transition: 'opacity 0.2s',
          '&:hover': isLoadingModel ? {} : {
            opacity: 0.8,
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography
            variant="body1"
            sx={{
              color: isDarkMode ? 'white' : '#333',
              fontSize: '1rem',
              fontWeight: 400,
            }}
          >
            {isLoadingModel ? 'Загрузка...' : 'Выбрать модель'}
          </Typography>
          {!isLoadingModel && (
            <KeyboardArrowDownIcon 
              fontSize="small" 
              sx={{
                color: isDarkMode ? 'white' : '#333',
              }}
            />
          )}
          {isLoadingModel && <CircularProgress size={16} />}
        </Box>
        {hasSelectedModel && !isLoadingModel && (
          <Typography
            variant="body2"
            sx={{
              color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
              fontSize: '0.875rem',
              fontWeight: 400,
              ml: 0.5,
            }}
          >
            {currentModelName}
          </Typography>
        )}
      </Box>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        PaperProps={{
          sx: {
            bgcolor: isDarkMode ? '#1e1e1e' : '#ffffff',
            minWidth: 400,
            maxWidth: 600,
            maxHeight: 500,
            mt: 1,
            borderRadius: 2,
            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
            boxShadow: isDarkMode 
              ? '0 8px 32px rgba(0, 0, 0, 0.4)'
              : '0 8px 32px rgba(0, 0, 0, 0.15)',
            '& .MuiMenuItem-root': {
              py: 1.5,
              px: 2,
            },
          },
        }}
        MenuListProps={{
          sx: {
            py: 1,
          },
        }}
      >
        {availableModels.map((model) => {
          const isSelected = selectedModelPath === model.path;
          const description = getModelDescription(model.name);
          
          return (
            <MenuItem
              key={model.path}
              onClick={() => handleModelSelect(model.path)}
              selected={isSelected}
              disabled={isLoadingModel && !isSelected}
              sx={{
                flexDirection: 'column',
                alignItems: 'flex-start',
                bgcolor: isSelected
                  ? isDarkMode
                    ? 'rgba(156, 39, 176, 0.25)'
                    : 'rgba(156, 39, 176, 0.12)'
                  : 'transparent',
                '&:hover': {
                  bgcolor: isSelected
                    ? isDarkMode
                      ? 'rgba(156, 39, 176, 0.35)'
                      : 'rgba(156, 39, 176, 0.18)'
                    : isDarkMode
                      ? 'rgba(255, 255, 255, 0.05)'
                      : 'rgba(0, 0, 0, 0.05)',
                },
                '&.Mui-selected': {
                  bgcolor: isDarkMode
                    ? 'rgba(156, 39, 176, 0.25)'
                    : 'rgba(156, 39, 176, 0.12)',
                  '&:hover': {
                    bgcolor: isDarkMode
                      ? 'rgba(156, 39, 176, 0.35)'
                      : 'rgba(156, 39, 176, 0.18)',
                  },
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', mb: 0.5 }}>
                <Typography
                  variant="body1"
                  sx={{
                    fontWeight: 600,
                    color: isDarkMode ? 'white' : '#333',
                    fontSize: '0.9375rem',
                    flex: 1,
                  }}
                >
                  {model.name.replace('.gguf', '')}
                </Typography>
                {isSelected && (
                  <ComputerIcon 
                    fontSize="small" 
                    sx={{ 
                      color: isDarkMode ? '#9c27b0' : '#9c27b0',
                      ml: 1,
                    }}
                  />
                )}
              </Box>
              <Typography
                variant="body2"
                sx={{
                  color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                  fontSize: '0.8125rem',
                  mt: 0.25,
                }}
              >
                {description}
              </Typography>
            </MenuItem>
          );
        })}
      </Menu>
    </Box>
  );
}
