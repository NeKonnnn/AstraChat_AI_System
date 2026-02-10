import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  Button,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Mic as MicIcon,
  Refresh as RefreshIcon,
  HelpOutline as HelpOutlineIcon,
  Restore as RestoreIcon,
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';
import { getApiUrl } from '../../config/api';


export default function TranscriptionSettings() {
  const [transcriptionSettings, setTranscriptionSettings] = useState({
    engine: "whisperx" as "whisperx" | "vosk",
    language: "ru",
    auto_detect: true,
  });
  const [isLoading, setIsLoading] = useState(false);
  
  const { showNotification } = useAppActions();

  useEffect(() => {
    loadTranscriptionSettings();
  }, []);

  // Автосохранение настроек транскрибации
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveTranscriptionSettings();
    }, 1000); // Сохраняем через 1 секунду после изменения

    return () => clearTimeout(timeoutId);
  }, [transcriptionSettings]);

  const loadTranscriptionSettings = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(getApiUrl('/api/transcription/settings'));
      if (response.ok) {
        const data = await response.json();
        setTranscriptionSettings(prev => ({ ...prev, ...data }));
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек транскрибации:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const saveTranscriptionSettings = async () => {
    try {
      const response = await fetch(getApiUrl('/api/transcription/settings'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(transcriptionSettings),
      });
      
      if (response.ok) {
        showNotification('success', 'Настройки транскрибации сохранены');
      } else {
        throw new Error(`Ошибка сохранения настроек транскрибации: ${response.status}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек транскрибации:', error);
      showNotification('error', 'Ошибка сохранения настроек транскрибации');
    }
  };

  const handleSettingChange = (key: keyof typeof transcriptionSettings, value: any) => {
    setTranscriptionSettings(prev => ({ ...prev, [key]: value }));
  };

  const resetToDefaults = () => {
    const defaultSettings = {
      engine: "whisperx" as "whisperx" | "vosk",
      language: "ru",
      auto_detect: true,
    };
    setTranscriptionSettings(defaultSettings);
    showNotification('info', 'Настройки транскрибации сброшены к значениям по умолчанию');
  };

  return (
    <Box sx={{ p: 3 }}>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MicIcon color="primary" />
            Основные настройки
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
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Настройте параметры распознавания речи для голосового ввода
          </Typography>

          <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(250px, 1fr))" gap={3}>
            <FormControl fullWidth>
              <InputLabel>Движок транскрибации</InputLabel>
              <Select
                value={transcriptionSettings.engine}
                label="Движок транскрибации"
                onChange={(e) => handleSettingChange('engine', e.target.value)}
              >
                <MenuItem value="whisperx">
                  <Box>
                    <Typography variant="body2" fontWeight="500">
                      WhisperX
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Точный, медленный
                    </Typography>
                  </Box>
                </MenuItem>
                <MenuItem value="vosk">
                  <Box>
                    <Typography variant="body2" fontWeight="500">
                      Vosk
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Быстрый, менее точный
                    </Typography>
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
            
            <FormControl fullWidth>
              <InputLabel>Язык транскрибации</InputLabel>
              <Select
                value={transcriptionSettings.language}
                label="Язык транскрибации"
                onChange={(e) => handleSettingChange('language', e.target.value)}
              >
                <MenuItem value="ru">
                  <Box>
                    <Typography variant="body2" fontWeight="500">
                      Русский
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Рекомендуется для русской речи
                    </Typography>
                  </Box>
                </MenuItem>
                <MenuItem value="en">
                  <Box>
                    <Typography variant="body2" fontWeight="500">
                      English
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Рекомендуется для английской речи
                    </Typography>
                  </Box>
                </MenuItem>
                <MenuItem value="auto">
                  <Box>
                    <Typography variant="body2" fontWeight="500">
                      Автоопределение
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Автоматическое определение языка
                    </Typography>
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
          </Box>
          
          <Box mt={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={transcriptionSettings.auto_detect}
                  onChange={(e) => handleSettingChange('auto_detect', e.target.checked)}
                />
              }
              label="Автоматическое определение языка"
            />
          </Box>
        </CardContent>
      </Card>

      {/* Информация о движках */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Информация о движках
          </Typography>
          
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 2 }}>
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'grey.300', borderRadius: 1 }}>
              <Typography variant="subtitle1" fontWeight="600" gutterBottom>
                WhisperX
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                <strong>Преимущества:</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                • Высокая точность распознавания
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                • Поддержка множества языков
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                • Хорошо работает с шумом
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Недостатки:</strong> Медленная работа, требует больше ресурсов
              </Typography>
            </Box>

            <Box sx={{ p: 2, border: '1px solid', borderColor: 'grey.300', borderRadius: 1 }}>
              <Typography variant="subtitle1" fontWeight="600" gutterBottom>
                Vosk
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                <strong>Преимущества:</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                • Быстрая работа
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                • Низкое потребление ресурсов
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                • Работает в реальном времени
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Недостатки:</strong> Меньшая точность, хуже работает с шумом
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Текущие настройки */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Текущие настройки
          </Typography>
          
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              <strong>Движок:</strong> {transcriptionSettings.engine === 'whisperx' ? 'WhisperX' : 'Vosk'}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              <strong>Язык:</strong> {
                transcriptionSettings.language === 'ru' ? 'Русский' :
                transcriptionSettings.language === 'en' ? 'English' :
                'Автоопределение'
              }
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Автоопределение языка:</strong> {transcriptionSettings.auto_detect ? 'Включено' : 'Отключено'}
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Кнопки управления */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={loadTranscriptionSettings}
          disabled={isLoading}
        >
          Обновить настройки
        </Button>
        
        <Button
          variant="outlined"
          startIcon={<RestoreIcon />}
          onClick={resetToDefaults}
        >
          Восстановить настройки
        </Button>
      </Box>
    </Box>
  );
}







