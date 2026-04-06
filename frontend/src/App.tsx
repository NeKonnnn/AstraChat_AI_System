import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box, IconButton, Tooltip } from '@mui/material';
import { ChevronRight as ChevronRightIcon } from '@mui/icons-material';
import Sidebar from './components/Sidebar';
import GlobalKeyboardShortcuts from './components/GlobalKeyboardShortcuts';
import SettingsModal from './components/SettingsModal';
import { ASTRA_FOCUS_CHAT_SEARCH, ASTRA_OPEN_SETTINGS } from './constants/hotkeys';
import UnifiedChatPage from './pages/UnifiedChatPage';
import VoicePage from './pages/VoicePage';
import DocumentsPage from './pages/DocumentsPage';
// import SettingsPage from './pages/SettingsPage'; // Удалено - теперь используется модальное окно
import HistoryPage from './pages/HistoryPage';
import PromptGalleryPage from './pages/PromptGalleryPage';
import ProjectPage from './pages/ProjectPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { SocketProvider } from './contexts/SocketContext';
import { AppProvider } from './contexts/AppContext';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import LoginPage from './pages/LoginPage';
import ProfilePage from './pages/ProfilePage';
import ShareViewPage from './pages/ShareViewPage';
import { initSettings } from './settings';
import LlmStatusBanner from './components/LlmStatusBanner';
import './App.css';
import { MENU_ITEM_HOVER_DARK, MENU_ITEM_HOVER_LIGHT, MENU_BORDER_RADIUS_PX, MENU_ITEM_HOVER_RADIUS_PX, MENU_ITEM_HOVER_MARGIN_PX, MENU_MIN_WIDTH_PX, MENU_ICON_MIN_WIDTH, MENU_ICON_TO_TEXT_GAP_PX, MENU_ICON_FONT_SIZE_PX } from './constants/menuStyles';

const MENU_ITEM_MARGIN = MENU_ITEM_HOVER_MARGIN_PX;
const MENU_ITEM_RADIUS = MENU_ITEM_HOVER_RADIUS_PX;

// Создаем тему Material-UI
const createAppTheme = (isDark: boolean) => createTheme({
  palette: {
    mode: isDark ? 'dark' : 'light',
    primary: {
      main: '#2196f3',
      dark: '#1976d2',
      light: '#64b5f6',
    },
    secondary: {
      main: '#f50057',
      dark: '#c51162',
      light: '#ff5983',
    },
    background: {
      default: isDark ? '#121212' : '#fafafa',
      paper: isDark ? '#1e1e1e' : '#ffffff',
    },
    action: {
      hover: isDark ? MENU_ITEM_HOVER_DARK : MENU_ITEM_HOVER_LIGHT,
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        },
      },
    },
    // Единый цвет подсветки при наведении + округлая подушечка (не во всю ширину)
    MuiMenuItem: {
      styleOverrides: {
        root: ({ theme }) => ({
          marginLeft: MENU_ITEM_MARGIN,
          marginRight: MENU_ITEM_MARGIN,
          borderRadius: MENU_ITEM_RADIUS,
          '&:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        }),
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: ({ theme }) => ({
          marginLeft: MENU_ITEM_MARGIN,
          marginRight: MENU_ITEM_MARGIN,
          borderRadius: MENU_ITEM_RADIUS,
          '&:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        }),
      },
    },
    // Опции в Select и Autocomplete — тот же серый hover
    MuiAutocomplete: {
      styleOverrides: {
        listbox: ({ theme }) => ({
          '& .MuiMenuItem-root:hover': {
            backgroundColor: theme.palette.action.hover,
          },
        }),
      },
    },
  },
});

function App() {
  // Инициализация конфигурации при загрузке приложения
  useEffect(() => {
    initSettings().catch((error) => {
      console.error('Ошибка загрузки конфигурации:', error);
    });
  }, []);

  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('gazikii-dark-mode');
    return saved ? JSON.parse(saved) : false;
  });

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('sidebarOpen');
    return saved !== null ? saved === 'true' : true;
  });
  const [sidebarHidden, setSidebarHidden] = useState(() => {
    const saved = localStorage.getItem('sidebarHidden');
    return saved !== null ? saved === 'true' : false;
  });

  /** Счётчик для фокуса поля «Поиск в чатах» (в т.ч. после показа скрытого сайдбара). */
  const [searchFocusNonce, setSearchFocusNonce] = useState(0);
  /** Настройки по Alt+S — в App, чтобы работало даже при скрытой левой панели. */
  const [settingsFromHotkeyOpen, setSettingsFromHotkeyOpen] = useState(false);

  useEffect(() => {
    const onOpenSettings = () => setSettingsFromHotkeyOpen(true);
    window.addEventListener(ASTRA_OPEN_SETTINGS, onOpenSettings);
    return () => window.removeEventListener(ASTRA_OPEN_SETTINGS, onOpenSettings);
  }, []);

  useEffect(() => {
    const onFocusSearch = () => {
      setSidebarHidden(false);
      setSidebarOpen(true);
      setSearchFocusNonce((n) => n + 1);
    };
    window.addEventListener(ASTRA_FOCUS_CHAT_SEARCH, onFocusSearch);
    return () => window.removeEventListener(ASTRA_FOCUS_CHAT_SEARCH, onFocusSearch);
  }, []);

  useEffect(() => {
    localStorage.setItem('gazikii-dark-mode', JSON.stringify(isDarkMode));
  }, [isDarkMode]);

  useEffect(() => {
    localStorage.setItem('sidebarOpen', String(sidebarOpen));
  }, [sidebarOpen]);

  useEffect(() => {
    localStorage.setItem('sidebarHidden', String(sidebarHidden));
  }, [sidebarHidden]);

  // CSS-переменные для меню: единый серый hover, скругление, подушечка подсветки (перебивают глобальные стили в App.css)
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--menu-item-hover', isDarkMode ? MENU_ITEM_HOVER_DARK : MENU_ITEM_HOVER_LIGHT);
    root.style.setProperty('--menu-border-radius', `${MENU_BORDER_RADIUS_PX}px`);
    root.style.setProperty('--menu-item-hover-radius', `${MENU_ITEM_HOVER_RADIUS_PX}px`);
    root.style.setProperty('--menu-item-hover-margin', `${MENU_ITEM_HOVER_MARGIN_PX}px`);
    root.style.setProperty('--menu-min-width', `${MENU_MIN_WIDTH_PX}px`); /* дублируем из index.tsx при смене темы */
    root.style.setProperty('--menu-icon-min-width', `${MENU_ICON_MIN_WIDTH}px`);
    root.style.setProperty('--menu-icon-to-text-gap', `${MENU_ICON_TO_TEXT_GAP_PX}px`);
    root.style.setProperty('--menu-icon-font-size', `${MENU_ICON_FONT_SIZE_PX}px`);
  }, [isDarkMode]);

  const theme = createAppTheme(isDarkMode);

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  const toggleSidebar = () => {
    console.log('Переключение сайдбара:', sidebarOpen, '->', !sidebarOpen);
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <LlmStatusBanner />
      <AuthProvider>
        <AppProvider>
          <SocketProvider>
            <Router>
              <Routes>
                {/* Публичный маршрут для логина */}
                <Route path="/login" element={<LoginPage />} />
                
                {/* Публичный маршрут для просмотра публичных ссылок */}
                <Route path="/share/:shareId" element={<ShareViewPage />} />
                
                {/* Защищенные маршруты */}
                <Route
                  path="/*"
                  element={
                    <PrivateRoute>
                      <Box sx={{ display: 'flex', height: '100vh' }}>
                        {!sidebarHidden && (
                          <Sidebar 
                            open={sidebarOpen} 
                            onToggle={toggleSidebar}
                            isDarkMode={isDarkMode}
                            onToggleTheme={toggleTheme}
                            onHide={() => setSidebarHidden(true)}
                            searchFocusNonce={searchFocusNonce}
                          />
                        )}
                        <GlobalKeyboardShortcuts />
                        <SettingsModal
                          open={settingsFromHotkeyOpen}
                          onClose={() => setSettingsFromHotkeyOpen(false)}
                          isDarkMode={isDarkMode}
                          onToggleTheme={toggleTheme}
                        />
                        <Box 
                          component="main" 
                          sx={{ 
                            flexGrow: 1, 
                            display: 'flex',
                            flexDirection: 'column',
                            overflow: 'hidden',
                            marginLeft: sidebarHidden ? 0 : (sidebarOpen ? 0 : '-64px'),
                            transition: 'margin-left 0.3s ease',
                            position: 'relative',
                          }}
                        >
                          {/* Кнопка для показа скрытой панели */}
                          {sidebarHidden && (
                            <Box
                              sx={{
                                position: 'fixed',
                                left: 0,
                                top: '50%',
                                transform: 'translateY(-50%)',
                                zIndex: 1200,
                              }}
                            >
                              <Tooltip title="Показать панель" placement="right">
                                <IconButton
                                  onClick={() => {
                                    setSidebarHidden(false);
                                    setSidebarOpen(false);
                                  }}
                                  sx={{
                                    bgcolor: 'transparent',
                                    color: 'text.primary',
                                    opacity: 0.7,
                                    '&:hover': {
                                      bgcolor: 'transparent',
                                      opacity: 1,
                                      '& .MuiSvgIcon-root': {
                                        color: 'primary.main',
                                      },
                                    },
                                  }}
                                >
                                  <ChevronRightIcon />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          )}
                          
                          <Routes>
                            <Route path="/" element={<UnifiedChatPage isDarkMode={isDarkMode} sidebarOpen={sidebarOpen} />} />
                            <Route path="/project/:projectId" element={<ProjectPage />} />
                            <Route path="/voice" element={<VoicePage />} />
                            <Route path="/documents" element={<DocumentsPage />} />
                            <Route path="/knowledge-base" element={<KnowledgeBasePage isDarkMode={isDarkMode} />} />
                            <Route path="/prompts" element={<PromptGalleryPage />} />
                            <Route path="/profile" element={<ProfilePage />} />
                            <Route path="/history" element={<HistoryPage />} />
                          </Routes>
                        </Box>
                      </Box>
                    </PrivateRoute>
                  }
                />
              </Routes>
            </Router>
          </SocketProvider>
        </AppProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;