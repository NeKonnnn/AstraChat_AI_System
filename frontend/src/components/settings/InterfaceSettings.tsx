import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Switch,
  Divider,
} from '@mui/material';
import {
  Computer as ComputerIcon,
} from '@mui/icons-material';
import { useAppActions } from '../../contexts/AppContext';

export default function InterfaceSettings() {
  const [interfaceSettings, setInterfaceSettings] = useState(() => {
    const savedAutoTitle = localStorage.getItem('auto_generate_titles');
    const savedLargeTextAsFile = localStorage.getItem('large_text_as_file');
    const savedUserNoBorder = localStorage.getItem('user_no_border');
    const savedAssistantNoBorder = localStorage.getItem('assistant_no_border');
    const savedLeftAlignMessages = localStorage.getItem('left_align_messages');
    const savedWidescreenMode = localStorage.getItem('widescreen_mode');
    const savedShowUserName = localStorage.getItem('show_user_name');
    const savedEnableNotification = localStorage.getItem('enable_notification');
    const savedShowModelSelectorInSettings = localStorage.getItem('show_model_selector_in_settings');
    const savedUseFoldersMode = localStorage.getItem('use_folders_mode');
    return {
      autoGenerateTitles: savedAutoTitle !== null ? savedAutoTitle === 'true' : true,
      largeTextAsFile: savedLargeTextAsFile !== null ? savedLargeTextAsFile === 'true' : false,
      userNoBorder: savedUserNoBorder !== null ? savedUserNoBorder === 'true' : false,
      assistantNoBorder: savedAssistantNoBorder !== null ? savedAssistantNoBorder === 'true' : false,
      leftAlignMessages: savedLeftAlignMessages !== null ? savedLeftAlignMessages === 'true' : false,
      widescreenMode: savedWidescreenMode !== null ? savedWidescreenMode === 'true' : false,
      showUserName: savedShowUserName !== null ? savedShowUserName === 'true' : false,
      enableNotification: savedEnableNotification !== null ? savedEnableNotification === 'true' : false,
      showModelSelectorInSettings: savedShowModelSelectorInSettings !== null ? savedShowModelSelectorInSettings === 'true' : false,
      useFoldersMode: savedUseFoldersMode !== null ? savedUseFoldersMode === 'true' : true, // По умолчанию папки
    };
  });
  
  const { showNotification } = useAppActions();

  const handleInterfaceSettingChange = (key: keyof typeof interfaceSettings, value: boolean) => {
    const newSettings = { ...interfaceSettings, [key]: value };
    setInterfaceSettings(newSettings);
    localStorage.setItem('auto_generate_titles', String(newSettings.autoGenerateTitles));
    localStorage.setItem('large_text_as_file', String(newSettings.largeTextAsFile));
    localStorage.setItem('user_no_border', String(newSettings.userNoBorder));
    localStorage.setItem('assistant_no_border', String(newSettings.assistantNoBorder));
    localStorage.setItem('left_align_messages', String(newSettings.leftAlignMessages));
    localStorage.setItem('widescreen_mode', String(newSettings.widescreenMode));
    localStorage.setItem('show_user_name', String(newSettings.showUserName));
    localStorage.setItem('enable_notification', String(newSettings.enableNotification));
    localStorage.setItem('show_model_selector_in_settings', String(newSettings.showModelSelectorInSettings));
    localStorage.setItem('use_folders_mode', String(newSettings.useFoldersMode));
    // Отправляем кастомное событие для обновления настроек в том же окне
    window.dispatchEvent(new Event('interfaceSettingsChanged'));
    showNotification('success', 'Настройки интерфейса сохранены');
  };

  return (
    <Box sx={{ p: 3 }}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ComputerIcon color="primary" />
            Настройки интерфейса
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

            <Divider />

            {/* Отображение имени пользователя */}
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
                primary="Отображать имя пользователя вместо 'Вы' в чате"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.showUserName}
                onChange={(e) => handleInterfaceSettingChange('showUserName', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Режим отображения сообщений пользователя */}
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
                primary="Сообщения пользователя без рамки"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.userNoBorder}
                onChange={(e) => handleInterfaceSettingChange('userNoBorder', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Режим отображения сообщений ассистента */}
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
                primary="Сообщения ассистента без рамки"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.assistantNoBorder}
                onChange={(e) => handleInterfaceSettingChange('assistantNoBorder', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Включить оповещение */}
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
                primary="Включить оповещение"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.enableNotification}
                onChange={(e) => handleInterfaceSettingChange('enableNotification', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Выравнивание сообщений */}
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
                primary="Выравнивание по левому краю"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.leftAlignMessages}
                onChange={(e) => handleInterfaceSettingChange('leftAlignMessages', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Режим широкоформатного экрана */}
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
                primary="Режим широкоформатного экрана"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
              />
              <Switch
                checked={interfaceSettings.widescreenMode}
                onChange={(e) => handleInterfaceSettingChange('widescreenMode', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Отображать выбор модели в настройках */}
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
                primary="Отображать выбор модели в настройках"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
                secondary="Если включено, выбор модели будет в настройках, иначе в рабочей зоне"
                secondaryTypographyProps={{
                  variant: 'body2',
                  sx: { mt: 0.5 }
                }}
              />
              <Switch
                checked={interfaceSettings.showModelSelectorInSettings}
                onChange={(e) => handleInterfaceSettingChange('showModelSelectorInSettings', e.target.checked)}
              />
            </ListItem>

            <Divider />

            {/* Использовать папки вместо проектов */}
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
                primary="Использовать папки"
                primaryTypographyProps={{
                  variant: 'body1',
                  fontWeight: 500,
                }}
                secondary={interfaceSettings.useFoldersMode 
                  ? "Включен функционал папок. Проекты недоступны." 
                  : "Включен функционал проектов. Папки недоступны."}
                secondaryTypographyProps={{
                  variant: 'body2',
                  sx: { mt: 0.5 }
                }}
              />
              <Switch
                checked={interfaceSettings.useFoldersMode}
                onChange={(e) => handleInterfaceSettingChange('useFoldersMode', e.target.checked)}
              />
            </ListItem>
          </List>
        </CardContent>
      </Card>
    </Box>
  );
}

