import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  RadioGroup,
  Radio,
  TextField,
  Switch,
  Button,
  Alert,
  IconButton,
  Tooltip,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  Palette as PaletteIcon,
  Memory as MemoryIcon,
  HelpOutline as HelpOutlineIcon,
  Restore as RestoreIcon,
  Computer as ComputerIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../../contexts/AppContext';

interface GeneralSettingsProps {
  isDarkMode: boolean;
  onToggleTheme: () => void;
}

const API_BASE_URL = 'http://localhost:8000';

export default function GeneralSettings({ isDarkMode, onToggleTheme }: GeneralSettingsProps) {
  
  const [memorySettings, setMemorySettings] = useState({
    max_messages: 20,
    include_system_prompts: true,
    clear_on_restart: false,
  });
  
  const [interfaceSettings, setInterfaceSettings] = useState(() => {
    const savedAutoTitle = localStorage.getItem('auto_generate_titles');
    const savedLargeTextAsFile = localStorage.getItem('large_text_as_file');
    return {
      autoGenerateTitles: savedAutoTitle !== null ? savedAutoTitle === 'true' : true,
      largeTextAsFile: savedLargeTextAsFile !== null ? savedLargeTextAsFile === 'true' : false,
    };
  });
  
  const { showNotification } = useAppActions();

  useEffect(() => {
    loadMemorySettings();
  }, []);

  const loadMemorySettings = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/memory/settings`);
      if (response.ok) {
        const data = await response.json();
        setMemorySettings(prev => ({ ...prev, ...data }));
      }
    } catch (error) {
      console.warn('Не удалось загрузить настройки памяти:', error);
    }
  };

  const saveMemorySettings = async (newSettings: typeof memorySettings) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/memory/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      });
      
      if (response.ok) {
        showNotification('success', 'Настройки памяти сохранены');
        return true;
      } else {
        throw new Error('Ошибка сохранения настроек памяти');
      }
    } catch (error) {
      console.error('Ошибка сохранения настроек памяти:', error);
      showNotification('error', 'Ошибка сохранения настроек памяти');
      return false;
    }
  };

  const handleMemorySettingChange = async (key: keyof typeof memorySettings, value: any) => {
    const newSettings = { ...memorySettings, [key]: value };
    setMemorySettings(newSettings);
    await saveMemorySettings(newSettings);
  };

  const clearMemory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/memory/clear`, {
        method: 'POST',
      });
      if (response.ok) {
        showNotification('success', 'Память ассистента очищена');
      } else {
        showNotification('error', 'Не удалось очистить память');
      }
    } catch (error) {
      showNotification('error', 'Ошибка при очистке памяти');
    }
  };

  const getMemoryStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/memory/status`);
      if (response.ok) {
        const data = await response.json();
        showNotification('info', `В памяти: ${data.message_count || 0} сообщений`);
      }
    } catch (error) {
      showNotification('error', 'Не удалось получить статус памяти');
    }
  };

  const resetMemorySettings = () => {
    const defaultSettings = {
      max_messages: 20,
      include_system_prompts: true,
      clear_on_restart: false,
    };
    setMemorySettings(defaultSettings);
    saveMemorySettings(defaultSettings);
    showNotification('info', 'Настройки памяти сброшены к значениям по умолчанию');
  };

  const handleInterfaceSettingChange = (key: keyof typeof interfaceSettings, value: boolean) => {
    const newSettings = { ...interfaceSettings, [key]: value };
    setInterfaceSettings(newSettings);
    localStorage.setItem('auto_generate_titles', String(newSettings.autoGenerateTitles));
    localStorage.setItem('large_text_as_file', String(newSettings.largeTextAsFile));
    // Отправляем кастомное событие для обновления настроек в том же окне
    window.dispatchEvent(new Event('interfaceSettingsChanged'));
    showNotification('success', 'Настройки интерфейса сохранены');
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Настройки темы */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PaletteIcon color="primary" />
            Тема приложения
          </Typography>
          
          <FormControl component="fieldset">
            <RadioGroup
              value={isDarkMode ? 'dark' : 'light'}
              onChange={(e) => {
                if (e.target.value === 'dark' && !isDarkMode) {
                  onToggleTheme();
                } else if (e.target.value === 'light' && isDarkMode) {
                  onToggleTheme();
                }
              }}
            >
              <FormControlLabel
                value="dark"
                control={<Radio />}
                label="Темная"
              />
              <FormControlLabel
                value="light"
                control={<Radio />}
                label="Светлая"
              />
            </RadioGroup>
          </FormControl>
        </CardContent>
      </Card>

      {/* Настройки памяти */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MemoryIcon color="primary" />
            Настройки памяти
            <Tooltip 
              title="Как это работает: Ассистент использует последние сообщения из диалога для понимания контекста. Больше сообщений = лучше понимание, но больше потребление памяти. Рекомендуется: 20-40 сообщений для обычного общения." 
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
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Управление контекстом и памятью ассистента для более эффективного общения
          </Typography>

          <Box display="grid" gridTemplateColumns="repeat(auto-fit, minmax(250px, 1fr))" gap={2} sx={{ mb: 2 }}>
            <TextField
              label="Максимум сообщений в контексте"
              type="number"
              value={memorySettings.max_messages}
              onChange={(e) => {
                const value = parseInt(e.target.value);
                if (value >= 5 && value <= 100) {
                  handleMemorySettingChange('max_messages', value);
                }
              }}
              inputProps={{ min: 5, max: 100, step: 5 }}
              fullWidth
              helperText="Количество последних сообщений, которые ассистент запоминает (5-100)"
              error={memorySettings.max_messages < 5 || memorySettings.max_messages > 100}
            />
            
            <TextField
              label="Размер контекста (токены)"
              type="number"
              value={Math.round(memorySettings.max_messages * 150)}
              disabled
              fullWidth
              helperText="Примерный размер контекста в токенах (только для чтения)"
            />
          </Box>

          <Box sx={{ mb: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={memorySettings.include_system_prompts}
                  onChange={(e) => handleMemorySettingChange('include_system_prompts', e.target.checked)}
                />
              }
              label="Включать системные промпты в контекст"
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={memorySettings.clear_on_restart}
                  onChange={(e) => handleMemorySettingChange('clear_on_restart', e.target.checked)}
                />
              }
              label="Очищать память при перезапуске"
            />
          </Box>

          {memorySettings.max_messages > 50 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="body2">
                <strong>Внимание:</strong> Установлено большое количество сообщений ({memorySettings.max_messages}). 
                Это может замедлить работу ассистента и увеличить потребление памяти.
              </Typography>
            </Alert>
          )}

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 3 }}>
            <Button
              variant="outlined"
              startIcon={<RestoreIcon />}
              onClick={resetMemorySettings}
            >
              Восстановить настройки
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Настройки интерфейса */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ComputerIcon color="primary" />
            Интерфейс
          </Typography>

          <List>
            {/* Автогенерация заголовков */}
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
                primary="Автогенерация заголовков"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.autoGenerateTitles}
                onChange={(e) => handleInterfaceSettingChange('autoGenerateTitles', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Вставить большой текст как файл */}
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
                primary="Вставить большой текст как файл"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.largeTextAsFile}
                onChange={(e) => handleInterfaceSettingChange('largeTextAsFile', e.target.checked)}
              />
            </ListItem>
          </List>
        </CardContent>
      </Card>
    </Box>
  );
}

