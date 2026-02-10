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
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';
import { getApiUrl } from '../../config/api';

interface GeneralSettingsProps {
  isDarkMode: boolean;
  onToggleTheme: () => void;
}

export default function GeneralSettings({ isDarkMode, onToggleTheme }: GeneralSettingsProps) {
  
  const [memorySettings, setMemorySettings] = useState({
    max_messages: 20,
    include_system_prompts: true,
    clear_on_restart: false,
    unlimited_memory: false,
  });
  
  const { showNotification } = useAppActions();

  useEffect(() => {
    loadMemorySettings();
  }, []);

  const loadMemorySettings = async () => {
    try {
      const response = await fetch(getApiUrl('/api/memory/settings'));
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
      const response = await fetch(getApiUrl('/api/memory/settings'), {
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

  const resetMemorySettings = () => {
    const defaultSettings = {
      max_messages: 20,
      include_system_prompts: true,
      clear_on_restart: false,
      unlimited_memory: false,
    };
    setMemorySettings(defaultSettings);
    saveMemorySettings(defaultSettings);
    showNotification('info', 'Настройки памяти сброшены к значениям по умолчанию');
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
          
          <List>
            {/* Неограниченная память */}
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
                    Неограниченная память
                    <Tooltip 
                      title="Неограниченная память: Ассистент будет запоминать все сообщения в диалоге. Это может значительно увеличить потребление памяти при длинных диалогах." 
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
              <Switch
                checked={memorySettings.unlimited_memory}
                onChange={(e) => handleMemorySettingChange('unlimited_memory', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Максимум сообщений в контексте - показывается только если неограниченная память выключена */}
            {!memorySettings.unlimited_memory && (
              <>
                <ListItem
                  sx={{
                    px: 0,
                    py: 2,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'stretch',
                  }}
                >
                  <Box sx={{ mb: 2 }}>
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
                  </Box>
                  
                  <Box>
                    <TextField
                      label="Размер контекста (токены)"
                      type="number"
                      value={Math.round(memorySettings.max_messages * 150)}
                      disabled
                      fullWidth
                      helperText="Примерный размер контекста в токенах (только для чтения)"
                    />
                  </Box>
                </ListItem>

                <Divider />
              </>
            )}

            {/* Включать системные промпты в контекст */}
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
                primary="Включать системные промпты в контекст"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={memorySettings.include_system_prompts}
                onChange={(e) => handleMemorySettingChange('include_system_prompts', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Очищать память при перезапуске */}
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
                primary="Очищать память при перезапуске"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={memorySettings.clear_on_restart}
                onChange={(e) => handleMemorySettingChange('clear_on_restart', e.target.checked)}
              />
            </ListItem>
          </List>

          {!memorySettings.unlimited_memory && memorySettings.max_messages > 50 && (
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

    </Box>
  );
}

