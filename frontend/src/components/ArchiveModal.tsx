import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  TextField,
  InputAdornment,
  List,
  ListItem,
  ListItemText,
  Typography,
  IconButton,
  useTheme,
  useMediaQuery,
  Button,
  Divider,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  Close as CloseIcon,
  Search as SearchIcon,
  Archive as ArchiveIcon,
  Delete as DeleteIcon,
  Unarchive as UnarchiveIcon,
  FileDownload as FileDownloadIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';

interface ArchiveModalProps {
  open: boolean;
  onClose: () => void;
  isDarkMode: boolean;
}

export default function ArchiveModal({ open, onClose, isDarkMode }: ArchiveModalProps) {
  const { state } = useAppContext();
  const { unarchiveChat, deleteChat, exportChats, unarchiveAllChats, setCurrentChat } = useAppActions();
  const [searchQuery, setSearchQuery] = useState('');
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();

  // Получаем архивированные чаты
  const archivedChats = useMemo(() => {
    return state.chats.filter(chat => chat.isArchived === true);
  }, [state.chats]);

  // Фильтруем архивированные чаты по поисковому запросу
  const filteredArchivedChats = useMemo(() => {
    if (!searchQuery.trim()) {
      return archivedChats;
    }
    const query = searchQuery.toLowerCase();
    return archivedChats.filter(chat =>
      chat.title.toLowerCase().includes(query) ||
      chat.messages.some(msg =>
        msg.content.toLowerCase().includes(query)
      )
    );
  }, [archivedChats, searchQuery]);

  const handleUnarchiveChat = (chatId: string) => {
    unarchiveChat(chatId);
  };

  const handleDeleteChat = (chatId: string) => {
    if (window.confirm('Вы уверены, что хотите удалить этот чат?')) {
      deleteChat(chatId);
    }
  };

  const handleOpenChat = (chatId: string, event?: React.MouseEvent) => {
    // Предотвращаем открытие чата при клике на кнопки
    if (event) {
      const target = event.target as HTMLElement;
      if (target.closest('button') || target.closest('.MuiIconButton-root')) {
        return;
      }
    }
    setCurrentChat(chatId);
    onClose(); // Закрываем модальное окно архива
    navigate('/'); // Переходим на главную страницу с чатом
  };

  const handleUnarchiveAll = () => {
    if (window.confirm('Вы уверены, что хотите разархивировать все чаты?')) {
      unarchiveAllChats();
    }
  };

  const handleExportAll = () => {
    // Экспортируем только архивированные чаты
    const exportData = {
      chats: archivedChats,
      folders: [],
      exportDate: new Date().toISOString(),
      version: '1.0',
    };
    const dataStr = JSON.stringify(exportData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `archived_chats_export_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: {
          height: isMobile ? '100vh' : '80vh',
          maxHeight: isMobile ? '100vh' : '80vh',
          borderRadius: isMobile ? 0 : 2,
          backgroundColor: theme.palette.mode === 'dark' ? '#1a1a1a' : '#ffffff',
        }
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          borderBottom: `1px solid ${theme.palette.divider}`,
          backgroundColor: theme.palette.mode === 'dark' ? '#2a2a2a' : '#f5f5f5',
        }}
      >
        <Typography component="span" variant="h6" fontWeight="600">
          Архив чатов
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          sx={{
            color: theme.palette.text.secondary,
            '&:hover': {
              backgroundColor: theme.palette.action.hover,
            }
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0, display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Поиск */}
        <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
          <TextField
            fullWidth
            placeholder="Поиск в чатах"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: theme.palette.text.secondary }} />
                </InputAdornment>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: theme.palette.mode === 'dark' ? '#2a2a2a' : '#f5f5f5',
              }
            }}
          />
        </Box>

        {/* Список архивированных чатов */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          {filteredArchivedChats.length === 0 ? (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: theme.palette.text.secondary,
              }}
            >
              <ArchiveIcon sx={{ fontSize: 64, mb: 2, opacity: 0.5 }} />
              <Typography variant="h6" gutterBottom>
                {archivedChats.length === 0 ? 'Архив пуст' : 'Ничего не найдено'}
              </Typography>
              <Typography variant="body2">
                {archivedChats.length === 0
                  ? 'Здесь будут отображаться архивированные чаты'
                  : 'Попробуйте изменить поисковый запрос'}
              </Typography>
            </Box>
          ) : (
            <List sx={{ p: 0 }}>
              {filteredArchivedChats.map((chat, index) => (
                <ListItem 
                  key={chat.id} 
                  disablePadding 
                  sx={{ mb: 0.5 }}
                >
                  <Paper
                    elevation={0}
                    onClick={(e) => handleOpenChat(chat.id, e)}
                    sx={{
                      width: '100%',
                      borderRadius: 2,
                      px: 2,
                      py: 1.5,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      backgroundColor: 'transparent',
                      border: '1px solid transparent',
                      cursor: 'pointer',
                      '&:hover': {
                        backgroundColor: theme.palette.mode === 'dark' 
                          ? 'rgba(255,255,255,0.05)' 
                          : 'rgba(0,0,0,0.02)',
                        border: theme.palette.mode === 'dark'
                          ? '1px solid rgba(255,255,255,0.1)'
                          : '1px solid rgba(0,0,0,0.1)',
                      },
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <ListItemText
                      primary={chat.title}
                      primaryTypographyProps={{
                        sx: {
                          fontWeight: 500,
                          color: theme.palette.text.primary,
                        }
                      }}
                    />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Tooltip title="Разархивировать" placement="top">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleUnarchiveChat(chat.id);
                          }}
                          sx={{
                            borderRadius: 1,
                            minWidth: 40,
                            width: 40,
                            height: 40,
                            py: 1,
                            color: theme.palette.text.primary,
                            backgroundColor: 'transparent',
                            opacity: 0.7,
                            '&:hover': {
                              backgroundColor: theme.palette.mode === 'dark' 
                                ? 'rgba(255, 255, 255, 0.1)' 
                                : 'rgba(0, 0, 0, 0.1)',
                              opacity: 1,
                              '& .MuiSvgIcon-root': {
                                color: theme.palette.primary.main,
                              },
                            },
                            transition: 'all 0.2s ease',
                          }}
                        >
                          <UnarchiveIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить" placement="top">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteChat(chat.id);
                          }}
                          sx={{
                            borderRadius: 1,
                            minWidth: 40,
                            width: 40,
                            height: 40,
                            py: 1,
                            color: theme.palette.text.primary,
                            backgroundColor: 'transparent',
                            opacity: 0.7,
                            '&:hover': {
                              backgroundColor: theme.palette.mode === 'dark' 
                                ? 'rgba(255, 255, 255, 0.1)' 
                                : 'rgba(0, 0, 0, 0.1)',
                              opacity: 1,
                              '& .MuiSvgIcon-root': {
                                color: theme.palette.error.main,
                              },
                            },
                            transition: 'all 0.2s ease',
                          }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Paper>
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {/* Кнопки действий */}
        {archivedChats.length > 0 && (
          <Box
            sx={{
              p: 2,
              borderTop: `1px solid ${theme.palette.divider}`,
              display: 'flex',
              gap: 2,
            }}
          >
            <Button
              fullWidth
              variant="outlined"
              startIcon={<UnarchiveIcon />}
              onClick={handleUnarchiveAll}
              sx={{
                textTransform: 'none',
                backgroundColor: theme.palette.mode === 'dark' ? '#2a2a2a' : '#ffffff',
                color: theme.palette.text.primary,
                borderColor: theme.palette.divider,
                '&:hover': {
                  backgroundColor: theme.palette.action.hover,
                  borderColor: theme.palette.divider,
                },
              }}
            >
              Разархивировать все архивированные чаты
            </Button>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<FileDownloadIcon />}
              onClick={handleExportAll}
              sx={{
                textTransform: 'none',
                backgroundColor: theme.palette.mode === 'dark' ? '#2a2a2a' : '#ffffff',
                color: theme.palette.text.primary,
                borderColor: theme.palette.divider,
                '&:hover': {
                  backgroundColor: theme.palette.action.hover,
                  borderColor: theme.palette.divider,
                },
              }}
            >
              Экспортировать все архивированные чаты
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}

