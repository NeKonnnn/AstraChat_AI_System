import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  Switch,
  Button,
  IconButton,
  Tooltip,
  Alert,
  Divider,
  Popover,
} from '@mui/material';
import {
  Mic as MicIcon,
  Refresh as RefreshIcon,
  HelpOutline as HelpOutlineIcon,
  Restore as RestoreIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import {
  DROPDOWN_TRIGGER_BUTTON_SX,
  DROPDOWN_CHEVRON_SX,
  getDropdownPopoverPaperSx,
  DROPDOWN_ITEM_SX,
  DROPDOWN_ITEM_HOVER_BG,
} from '../../constants/menuStyles';
import { useAppActions } from '../../contexts/AppContext';
import { getApiUrl } from '../../config/api';

type Engine = 'whisperx' | 'vosk';
type Language = 'ru' | 'en' | 'auto';

export default function TranscriptionSettings() {
  const [transcriptionSettings, setTranscriptionSettings] = useState({
    engine: 'whisperx' as Engine,
    language: 'ru' as Language,
    auto_detect: true,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [enginePopoverAnchor, setEnginePopoverAnchor] = useState<HTMLElement | null>(null);
  const [languagePopoverAnchor, setLanguagePopoverAnchor] = useState<HTMLElement | null>(null);

  const { showNotification } = useAppActions();

  useEffect(() => {
    loadTranscriptionSettings();
  }, []);

  // Автосохранение настроек транскрибации
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveTranscriptionSettings();
    }, 1000);

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
    setTranscriptionSettings({
      engine: 'whisperx',
      language: 'ru',
      auto_detect: true,
    });
    showNotification('info', 'Настройки транскрибации сброшены к значениям по умолчанию');
  };

  const getEngineLabel = (engine: Engine): string => {
    switch (engine) {
      case 'whisperx':
        return 'WhisperX';
      case 'vosk':
        return 'Vosk';
      default:
        return 'WhisperX';
    }
  };

  const getEngineDescription = (engine: Engine): string => {
    switch (engine) {
      case 'whisperx':
        return 'Высокая точность распознавания, поддержка множества языков, хорошо работает с шумом. Требует больше ресурсов и работает медленнее, чем Vosk.';
      case 'vosk':
        return 'Быстрая работа и низкое потребление ресурсов, подходит для работы в реальном времени. Меньшая точность по сравнению с WhisperX, хуже справляется с шумом.';
      default:
        return '';
    }
  };

  const getEngineUseCase = (engine: Engine): string => {
    switch (engine) {
      case 'whisperx':
        return 'Используйте для максимальной точности транскрипции, особенно при записях с шумом или на разных языках.';
      case 'vosk':
        return 'Используйте когда важна скорость или ограничены ресурсы; подходит для быстрой предобработки и онлайн-распознавания.';
      default:
        return '';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MicIcon color="primary" />
            Основные настройки
            <Tooltip
              title="Настройки распознавания речи для голосового ввода. Сохраняются автоматически при изменении."
              arrow
            >
              <IconButton
                size="small"
                sx={{
                  ml: 0.5,
                  opacity: 0.7,
                  '&:hover': {
                    opacity: 1,
                    '& .MuiSvgIcon-root': { color: 'primary.main' },
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
                    Движок транскрибации
                    <Tooltip
                      title="Выберите движок распознавания речи. WhisperX — точнее, Vosk — быстрее."
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
              <Box sx={{ minWidth: 280 }}>
                <Box
                  onClick={(e) => !isLoading && setEnginePopoverAnchor(e.currentTarget)}
                  sx={{
                    ...DROPDOWN_TRIGGER_BUTTON_SX,
                    opacity: isLoading ? 0.7 : 1,
                    pointerEvents: isLoading ? 'none' : 'auto',
                  }}
                >
                  <Typography sx={{ color: 'white', fontWeight: 500, fontSize: '0.875rem' }}>
                    {transcriptionSettings.engine === 'whisperx' ? 'WhisperX' : 'Vosk'}
                  </Typography>
                  <ExpandMoreIcon sx={{ ...DROPDOWN_CHEVRON_SX, transform: enginePopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                </Box>
                <Popover
                  open={Boolean(enginePopoverAnchor)}
                  anchorEl={enginePopoverAnchor}
                  onClose={() => setEnginePopoverAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  slotProps={{ paper: { sx: getDropdownPopoverPaperSx(enginePopoverAnchor) } }}
                >
                  <Box sx={{ py: 0.5 }}>
                    {(['whisperx', 'vosk'] as const).map((engine) => (
                      <Box
                        key={engine}
                        onClick={() => { handleSettingChange('engine', engine); setEnginePopoverAnchor(null); }}
                        sx={{
                          ...DROPDOWN_ITEM_SX,
                          color: transcriptionSettings.engine === engine ? 'white' : 'rgba(255,255,255,0.9)',
                          fontWeight: transcriptionSettings.engine === engine ? 600 : 400,
                          bgcolor: transcriptionSettings.engine === engine ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                        }}
                      >
                        {engine === 'whisperx' ? 'WhisperX' : 'Vosk'}
                      </Box>
                    ))}
                  </Box>
                </Popover>
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
                    Язык транскрибации
                    <Tooltip
                      title="Язык распознавания. Автоопределение доступно при включённой опции ниже."
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
              <Box sx={{ minWidth: 280 }}>
                <Box
                  onClick={(e) => !isLoading && setLanguagePopoverAnchor(e.currentTarget)}
                  sx={{
                    ...DROPDOWN_TRIGGER_BUTTON_SX,
                    opacity: isLoading ? 0.7 : 1,
                    pointerEvents: isLoading ? 'none' : 'auto',
                  }}
                >
                  <Typography sx={{ color: 'white', fontWeight: 500, fontSize: '0.875rem' }}>
                    {transcriptionSettings.language === 'ru' ? 'Русский' : transcriptionSettings.language === 'en' ? 'English' : 'Автоопределение'}
                  </Typography>
                  <ExpandMoreIcon sx={{ ...DROPDOWN_CHEVRON_SX, transform: languagePopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                </Box>
                <Popover
                  open={Boolean(languagePopoverAnchor)}
                  anchorEl={languagePopoverAnchor}
                  onClose={() => setLanguagePopoverAnchor(null)}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  slotProps={{ paper: { sx: getDropdownPopoverPaperSx(languagePopoverAnchor) } }}
                >
                  <Box sx={{ py: 0.5 }}>
                    {(['ru', 'en', 'auto'] as const).map((lang) => (
                      <Box
                        key={lang}
                        onClick={() => { handleSettingChange('language', lang); setLanguagePopoverAnchor(null); }}
                        sx={{
                          ...DROPDOWN_ITEM_SX,
                          color: transcriptionSettings.language === lang ? 'white' : 'rgba(255,255,255,0.9)',
                          fontWeight: transcriptionSettings.language === lang ? 600 : 400,
                          bgcolor: transcriptionSettings.language === lang ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                        }}
                      >
                        {lang === 'ru' ? 'Русский' : lang === 'en' ? 'English' : 'Автоопределение'}
                      </Box>
                    ))}
                  </Box>
                </Popover>
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
                    Автоматическое определение языка
                    <Tooltip
                      title="Если включено, язык может определяться автоматически по аудио."
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
                checked={transcriptionSettings.auto_detect}
                onChange={(e) => handleSettingChange('auto_detect', e.target.checked)}
                disabled={isLoading}
              />
            </ListItem>
          </List>

          {/* Информационный блок о выбранном движке — как в RAG */}
          <Alert
            severity="info"
            sx={{
              mt: 2,
              '& .MuiAlert-message': { width: '100%' },
            }}
          >
            <Box>
              <Typography variant="subtitle2" fontWeight="600" gutterBottom>
                {getEngineLabel(transcriptionSettings.engine)}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {getEngineDescription(transcriptionSettings.engine)}
              </Typography>
              <Typography variant="body2" fontWeight="500" sx={{ mt: 1 }}>
                {getEngineUseCase(transcriptionSettings.engine)}
              </Typography>
            </Box>
          </Alert>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 3 }}>
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
        </CardContent>
      </Card>
    </Box>
  );
}







