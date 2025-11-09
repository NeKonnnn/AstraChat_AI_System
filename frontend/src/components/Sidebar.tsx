import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  IconButton,
  Box,
  Typography,
  Avatar,
  Chip,
  Button,
  TextField,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Chat as ChatIcon,
  Transcribe as TranscribeIcon,
  Settings as SettingsIcon,
  Info as InfoIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  MoreVert as MoreVertIcon,
  BarChart as BarChartIcon,
  ExpandMore as ExpandMoreIcon,
  Search as SearchIcon,
  Folder as FolderIcon,
  CreateNewFolder as AddFolderIcon,
  Menu as MenuIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import SettingsModal from './SettingsModal';

// Функция для оценки количества токенов в тексте (дублируем из AppContext)
function estimateTokens(text: string): number {
  if (!text) return 0;
  const baseTokens = Math.ceil(text.length / 4);
  const specialChars = (text.match(/[^\w\sа-яё]/g) || []).length;
  const newlines = (text.match(/\n/g) || []).length;
  return baseTokens + Math.ceil(specialChars / 2) + Math.ceil(newlines / 2);
}

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
}

const menuItems: any[] = [];

export default function Sidebar({ open, onToggle, isDarkMode, onToggleTheme }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state } = useAppContext();
  const { 
    createChat, 
    setCurrentChat, 
    deleteChat, 
    updateChatTitle, 
    getCurrentChat,
    createFolder,
    updateFolder,
    deleteFolder,
    moveChatToFolder,
    toggleFolder,
    getFolders
  } = useAppActions();
  const { isConnected } = useSocket();
  
  // Получаем папки из состояния
  const folders = getFolders();
  
  const [editingChatId, setEditingChatId] = React.useState<string | null>(null);
  const [editingTitle, setEditingTitle] = React.useState('');
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [showStatsDialog, setShowStatsDialog] = React.useState(false);
  const [chatMenuAnchor, setChatMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [selectedChatId, setSelectedChatId] = React.useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [chatsExpanded, setChatsExpanded] = React.useState(true);
  const [showSettingsModal, setShowSettingsModal] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [showCreateFolderDialog, setShowCreateFolderDialog] = React.useState(false);
  const [newFolderName, setNewFolderName] = React.useState('');
  const [showMoveToFolderMenu, setShowMoveToFolderMenu] = React.useState(false);
  const [folderMenuAnchor, setFolderMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(null);
  const [showRenameFolderDialog, setShowRenameFolderDialog] = React.useState(false);
  const [renamingFolderName, setRenamingFolderName] = React.useState('');
  const [showDeleteFolderDialog, setShowDeleteFolderDialog] = React.useState(false);
  const [deleteWithContent, setDeleteWithContent] = React.useState(false);
  const menuOpen = Boolean(anchorEl);
  const chatMenuOpen = Boolean(chatMenuAnchor);
  const folderMenuOpen = Boolean(folderMenuAnchor);

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  const handleCreateChat = () => {
    const chatId = createChat();
    setCurrentChat(chatId);
    navigate('/');
  };

  const handleSelectChat = (chatId: string) => {
    setCurrentChat(chatId);
    navigate('/');
  };



  const handleSaveEdit = () => {
    if (editingChatId && editingTitle.trim()) {
      updateChatTitle(editingChatId, editingTitle.trim());
    }
    setEditingChatId(null);
    setEditingTitle('');
  };

  const handleCancelEdit = () => {
    setEditingChatId(null);
    setEditingTitle('');
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      handleSaveEdit();
    } else if (event.key === 'Escape') {
      handleCancelEdit();
    }
  };

  const currentChat = getCurrentChat();

  // Функция для определения папки, в которой находится чат
  const getChatFolder = (chatId: string) => {
    return folders.find(folder => folder.chatIds.includes(chatId));
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleMenuAction = (action: string) => {
    handleMenuClose();
    switch (action) {
      case 'settings':
        setShowSettingsModal(true);
        break;
      case 'transcription':
        navigate('/transcription');
        break;
      case 'statistics':
        // Показываем статистику в диалоге
        setShowStatsDialog(true);
        break;
    }
  };

  const handleChatMenuClick = (event: React.MouseEvent<HTMLElement>, chatId: string) => {
    event.stopPropagation();
    setChatMenuAnchor(event.currentTarget);
    setSelectedChatId(chatId);
  };

  const handleChatMenuClose = () => {
    setChatMenuAnchor(null);
    setSelectedChatId(null);
  };

  const handleChatMenuAction = (action: string) => {
    if (!selectedChatId) {
      return;
    }
    
    // Сохраняем selectedChatId перед закрытием меню
    const chatIdToAction = selectedChatId;
    
    switch (action) {
      case 'edit':
        const chatToEdit = state.chats.find(chat => chat.id === chatIdToAction);
        handleChatMenuClose();
        setEditingChatId(chatIdToAction);
        setEditingTitle(chatToEdit?.title || '');
        break;
      case 'delete':
        handleChatMenuClose();
        setSelectedChatId(chatIdToAction); // Восстанавливаем selectedChatId для диалога
        setShowDeleteDialog(true);
        break;
      default:
        handleChatMenuClose();
        break;
    }
  };

  const handleConfirmDelete = () => {
    if (selectedChatId) {
      deleteChat(selectedChatId);
      if (state.currentChatId === selectedChatId) {
        // Если удаляем текущий чат, переключаемся на первый доступный
        const remainingChats = state.chats.filter(chat => chat.id !== selectedChatId);
        if (remainingChats.length > 0) {
          setCurrentChat(remainingChats[0].id);
        } else {
          setCurrentChat(null);
        }
      }
      setShowDeleteDialog(false);
      setSelectedChatId(null);
    }
  };

  // Функция для группировки чатов по времени
  const groupChatsByTime = (chats: any[]) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    const groups = {
      today: [] as any[],
      yesterday: [] as any[],
      week: [] as any[],
      older: [] as any[]
    };

    chats.forEach(chat => {
      const chatDate = new Date(chat.updatedAt);
      if (chatDate >= today) {
        groups.today.push(chat);
      } else if (chatDate >= yesterday) {
        groups.yesterday.push(chat);
      } else if (chatDate >= weekAgo) {
        groups.week.push(chat);
      } else {
        groups.older.push(chat);
      }
    });

    return groups;
  };

  // Функция для фильтрации чатов по поисковому запросу
  const filteredChats = React.useMemo(() => {
    // Исключаем чаты, которые уже находятся в папках
    const chatsInFolders = new Set(folders.flatMap(folder => folder.chatIds));
    const availableChats = state.chats.filter(chat => !chatsInFolders.has(chat.id));
    
    if (!searchQuery.trim()) {
      return availableChats;
    }
    return availableChats.filter(chat => 
      chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.messages.some(msg => 
        msg.content.toLowerCase().includes(searchQuery.toLowerCase())
      )
    );
  }, [state.chats, searchQuery, folders]);


  // Функции для работы с папками
  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      createFolder(newFolderName.trim());
      setNewFolderName('');
      setShowCreateFolderDialog(false);
    }
  };

  const handleToggleFolder = (folderId: string) => {
    toggleFolder(folderId);
  };

  const handleMoveToFolder = (chatId: string, folderId: string) => {
    moveChatToFolder(chatId, folderId);
    setShowMoveToFolderMenu(false);
  };

  const handleRemoveFromFolder = (chatId: string) => {
    moveChatToFolder(chatId, null);
  };

  // Функции для управления папками
  const handleFolderMenuClick = (event: React.MouseEvent<HTMLElement>, folderId: string) => {
    event.stopPropagation();
    setFolderMenuAnchor(event.currentTarget);
    setSelectedFolderId(folderId);
  };

  const handleFolderMenuClose = () => {
    setFolderMenuAnchor(null);
    setSelectedFolderId(null);
  };

  const handleFolderMenuAction = (action: string) => {
    if (!selectedFolderId) {
      return;
    }
    
    // Сохраняем selectedFolderId перед закрытием меню
    const folderIdToAction = selectedFolderId;
    
    if (action === 'rename') {
      const folder = folders.find(f => f.id === folderIdToAction);
      if (folder) {
        setRenamingFolderName(folder.name);
        setShowRenameFolderDialog(true);
      }
    } else if (action === 'delete') {
      setShowDeleteFolderDialog(true);
    }
  };

  const handleRenameFolder = () => {
    if (selectedFolderId && renamingFolderName.trim()) {
      updateFolder(selectedFolderId, renamingFolderName.trim());
      setRenamingFolderName('');
      setShowRenameFolderDialog(false);
      handleFolderMenuClose(); // Закрываем меню после переименования
    }
  };

  const handleDeleteFolder = () => {
    if (!selectedFolderId) {
      return;
    }
    
    const folder = folders.find(f => f.id === selectedFolderId);
    if (!folder) {
      return;
    }
    
    if (deleteWithContent) {
      // Удаляем папку со всем содержимым
      folder.chatIds.forEach(chatId => {
        deleteChat(chatId);
      });
    } else {
      // Перемещаем чаты в "Все чаты" (убираем из папки)
      folder.chatIds.forEach(chatId => {
        moveChatToFolder(chatId, null);
      });
    }
    
    // Удаляем папку
    deleteFolder(selectedFolderId);
    setShowDeleteFolderDialog(false);
    setDeleteWithContent(false);
    setSelectedFolderId(null);
    handleFolderMenuClose(); // Закрываем меню после удаления
  };

  return (
    <Drawer
      variant="persistent"
      anchor="left"
      open={open}
      sx={{
        width: 280,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: 280,
          boxSizing: 'border-box',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          borderRight: 'none',
        },
      }}
    >
      {/* Заголовок */}
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(0,0,0,0.1)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Box
              component="img"
              src="/astra.png"
              alt="Astra"
              sx={{
                width: '150%',
                height: '150%',
                objectFit: 'cover',
                transform: 'scale(1.2)',
              }}
            />
          </Box>
          <Box>
            <Typography variant="h6" fontWeight="bold">
              AstraChat
            </Typography>
            
          </Box>
        </Box>
        <IconButton
          onClick={onToggle}
          sx={{
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(255,255,255,0.1)',
            },
          }}
        >
          <MenuIcon />
        </IconButton>
      </Box>

      {/* Статус соединения */}
      <Box sx={{ px: 2, pb: 1 }}>
        <Chip
          size="small"
          icon={<InfoIcon fontSize="small" />}
          label={isConnected ? 'Подключено' : 'Отключено'}
          color={isConnected ? 'success' : 'error'}
          variant="outlined"
          sx={{ 
            color: 'white',
            borderColor: isConnected ? 'rgba(76, 175, 80, 0.5)' : 'rgba(244, 67, 54, 0.5)',
          }}
        />
      </Box>

      {/* Кнопка создания нового чата */}
      <Box sx={{ p: 1.5 }}>
        <Button
          fullWidth
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleCreateChat}
          sx={{
            backgroundColor: 'rgba(255,255,255,0.1)',
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(255,255,255,0.2)',
            },
            textTransform: 'none',
            fontWeight: 500,
            py: 1,
            px: 2,
            borderRadius: 2,
            justifyContent: 'flex-start',
            fontSize: '0.875rem',
          }}
        >
          Новый чат
        </Button>
      </Box>

      {/* Поиск в чатах */}
      <Box sx={{ p: 1.5 }}>
        <TextField
          fullWidth
          placeholder="Поиск в чатах"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          size="small"
          InputProps={{
            startAdornment: <SearchIcon sx={{ color: 'rgba(255,255,255,0.7)', mr: 1, fontSize: '1rem' }} />,
            endAdornment: (
              <IconButton
                size="small"
                onClick={() => setShowCreateFolderDialog(true)}
                sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                title="Создать папку"
              >
                <AddFolderIcon fontSize="small" />
              </IconButton>
            ),
            sx: {
              backgroundColor: 'rgba(255,255,255,0.1)',
              borderRadius: 2,
              '& .MuiOutlinedInput-notchedOutline': {
                border: 'none',
              },
              '& .MuiInputBase-input': {
                color: 'white',
                fontSize: '0.875rem',
                py: 1,
                '&::placeholder': {
                  color: 'rgba(255,255,255,0.7)',
                  opacity: 1,
                },
              },
            },
          }}
        />
      </Box>

      {/* Список чатов */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        <Box sx={{ p: 1 }}>
          <Box
            onClick={() => setChatsExpanded(!chatsExpanded)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 2,
              py: 1,
              cursor: 'pointer',
              borderRadius: 1,
              '&:hover': {
                backgroundColor: 'rgba(255,255,255,0.05)',
              },
              transition: 'background-color 0.2s ease',
            }}
          >
            <Typography variant="subtitle2" sx={{ opacity: 0.8, fontSize: '0.75rem' }}>
              Все чаты
            </Typography>
            <ExpandMoreIcon
              sx={{
                fontSize: '1rem',
                opacity: 0.8,
                transform: chatsExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                transition: 'transform 0.2s ease',
              }}
            />
          </Box>
          {chatsExpanded && (
            <>
              {filteredChats.length === 0 ? (
                <Typography variant="body2" sx={{ px: 2, py: 2, opacity: 0.6, textAlign: 'center' }}>
                  {searchQuery ? 'Ничего не найдено' : 'Пока нет чатов'}
                </Typography>
              ) : (
                <List sx={{ py: 0 }}>
                  {filteredChats.map((chat) => (
                <ListItem key={chat.id} disablePadding sx={{ mb: 0.5 }}>
                  <ListItemButton
                    onClick={() => handleSelectChat(chat.id)}
                    sx={{
                      borderRadius: 2,
                      backgroundColor: state.currentChatId === chat.id ? 'rgba(255,255,255,0.15)' : 'transparent',
                      '&:hover': {
                        backgroundColor: state.currentChatId === chat.id ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                      },
                      transition: 'all 0.2s ease',
                      py: 1,
                      px: 2,
                    }}
                  >
                    <ListItemIcon sx={{ color: 'white', minWidth: 28 }}>
                      <ChatIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        editingChatId === chat.id ? (
                          <TextField
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onBlur={handleSaveEdit}
                            onKeyDown={handleKeyPress}
                            autoFocus
                            size="small"
                            sx={{
                              '& .MuiInputBase-input': {
                                color: 'white',
                                fontSize: '0.875rem',
                                py: 0.5,
                              },
                              '& .MuiOutlinedInput-notchedOutline': {
                                borderColor: 'rgba(255,255,255,0.3)',
                              },
                              '&:hover .MuiOutlinedInput-notchedOutline': {
                                borderColor: 'rgba(255,255,255,0.5)',
                              },
                            }}
                          />
                        ) : (
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight: state.currentChatId === chat.id ? 600 : 400,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              fontSize: '0.8rem',
                            }}
                          >
                            {chat.title}
                          </Typography>
                        )
                      }
                    />
                    {!editingChatId && (
                      <IconButton
                        size="small"
                        onClick={(e) => handleChatMenuClick(e, chat.id)}
                        sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                      >
                        <MoreVertIcon fontSize="small" />
                      </IconButton>
                    )}
                  </ListItemButton>
                </ListItem>
                  ))}
                </List>
              )}
            </>
          )}

          {/* Отображение папок как отдельных разделов */}
          {folders.map((folder) => (
            <Box key={folder.id} sx={{ mb: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  px: 2,
                  py: 1,
                  borderRadius: 1,
                  '&:hover': {
                    backgroundColor: 'rgba(255,255,255,0.05)',
                  },
                  transition: 'background-color 0.2s ease',
                }}
              >
                <Box
                  onClick={() => handleToggleFolder(folder.id)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    flex: 1,
                    cursor: 'pointer',
                  }}
                >
                  <Typography variant="subtitle2" sx={{ opacity: 0.8, fontSize: '0.75rem' }}>
                    {folder.name}
                  </Typography>
                  <ExpandMoreIcon
                    sx={{
                      fontSize: '1rem',
                      opacity: 0.8,
                      transform: folder.expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                      transition: 'transform 0.2s ease',
                      ml: 1,
                    }}
                  />
                </Box>
                <IconButton
                  size="small"
                  onClick={(e) => handleFolderMenuClick(e, folder.id)}
                  sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                >
                  <MoreVertIcon fontSize="small" />
                </IconButton>
              </Box>
              {folder.expanded && (
                <List sx={{ py: 0 }}>
                  {(() => {
                    const filteredFolderChats = folder.chatIds
                      .map(chatId => ({ chatId, chat: state.chats.find(c => c.id === chatId) }))
                      .filter(({ chat }) => {
                        if (!chat) return false;
                        if (!searchQuery.trim()) return true;
                        return chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                               chat.messages.some(msg => 
                                 msg.content.toLowerCase().includes(searchQuery.toLowerCase())
                               );
                      });
                    
                    if (filteredFolderChats.length === 0 && searchQuery.trim()) {
                      return (
                        <Typography variant="body2" sx={{ px: 2, py: 2, opacity: 0.6, textAlign: 'center', fontSize: '0.8rem' }}>
                          Ничего не найдено
                        </Typography>
                      );
                    }
                    
                    return filteredFolderChats.map(({ chatId, chat }) => {
                      if (!chat) return null;
                      return (
                      <ListItem key={chatId} disablePadding sx={{ mb: 0.5 }}>
                        <ListItemButton
                          onClick={() => handleSelectChat(chatId)}
                          sx={{
                            borderRadius: 2,
                            backgroundColor: state.currentChatId === chatId ? 'rgba(255,255,255,0.15)' : 'transparent',
                            '&:hover': {
                              backgroundColor: state.currentChatId === chatId ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                            },
                            transition: 'all 0.2s ease',
                            py: 1,
                            px: 2,
                          }}
                        >
                          <ListItemIcon sx={{ color: 'white', minWidth: 28 }}>
                            <ChatIcon fontSize="small" />
                          </ListItemIcon>
                          <ListItemText
                            primary={
                              editingChatId === chatId ? (
                                <TextField
                                  value={editingTitle}
                                  onChange={(e) => setEditingTitle(e.target.value)}
                                  onBlur={handleSaveEdit}
                                  onKeyDown={handleKeyPress}
                                  autoFocus
                                  size="small"
                                  sx={{
                                    '& .MuiInputBase-input': {
                                      color: 'white',
                                      fontSize: '0.8rem',
                                      py: 0.5,
                                    },
                                    '& .MuiOutlinedInput-notchedOutline': {
                                      borderColor: 'rgba(255,255,255,0.3)',
                                    },
                                    '&:hover .MuiOutlinedInput-notchedOutline': {
                                      borderColor: 'rgba(255,255,255,0.5)',
                                    },
                                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                      borderColor: 'white',
                                    },
                                  }}
                                />
                              ) : (
                                <Typography
                                  variant="body2"
                                  sx={{
                                    color: 'white',
                                    fontWeight: state.currentChatId === chatId ? 600 : 400,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    fontSize: '0.8rem',
                                  }}
                                >
                                  {chat.title}
                                </Typography>
                              )
                            }
                          />
                          {!editingChatId && (
                            <IconButton
                              size="small"
                              onClick={(e) => handleChatMenuClick(e, chatId)}
                              sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                            >
                              <MoreVertIcon fontSize="small" />
                            </IconButton>
                          )}
                        </ListItemButton>
                      </ListItem>
                      );
                    });
                  })()}
                </List>
              )}
            </Box>
          ))}
        </Box>
      </Box>

      {/* Навигационное меню */}
      <List sx={{ flexGrow: 1, px: 1 }}>
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <ListItem key={item.path} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                onClick={() => handleNavigation(item.path)}
                sx={{
                  borderRadius: 2,
                  backgroundColor: isActive ? 'rgba(255,255,255,0.15)' : 'transparent',
                  '&:hover': {
                    backgroundColor: isActive ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                  },
                  transition: 'all 0.2s ease',
                  py: 1,
                  px: 2,
                }}
              >
                <ListItemIcon sx={{ color: 'white', minWidth: 32 }}>
                  <Icon />
                </ListItemIcon>
                <ListItemText 
                  primary={item.label}
                  secondary={item.description}
                  primaryTypographyProps={{
                    fontWeight: isActive ? 600 : 400,
                  }}
                  secondaryTypographyProps={{
                    sx: { opacity: 0.8, fontSize: '0.75rem' }
                  }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>

      {/* Выпадающее меню с функциями */}
      <Box sx={{ p: 2, background: 'rgba(0,0,0,0.2)' }}>
        <Button
          fullWidth
          variant="contained"
          startIcon={<MoreVertIcon />}
          onClick={handleMenuClick}
          sx={{
            backgroundColor: 'rgba(255,255,255,0.1)',
            color: 'white',
            '&:hover': {
              backgroundColor: 'rgba(255,255,255,0.2)',
            },
            textTransform: 'none',
            fontWeight: 500,
            py: 1,
            px: 2,
            justifyContent: 'flex-start',
            borderRadius: 2,
            fontSize: '0.875rem',
          }}
        >
          Меню
        </Button>
        
        <Menu
          anchorEl={anchorEl}
          open={menuOpen}
          onClose={handleMenuClose}
          anchorOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          PaperProps={{
            sx: {
              backgroundColor: 'rgba(30, 30, 30, 0.95)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 2,
              minWidth: 200,
            },
          }}
        >
          <MenuItem 
            onClick={() => handleMenuAction('settings')}
            sx={{ 
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
            }}
          >
            <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
              <SettingsIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Настройки" />
          </MenuItem>
          
          
          <MenuItem 
            onClick={() => handleMenuAction('transcription')}
            sx={{ 
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
            }}
          >
            <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
              <TranscribeIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Транскрибация" />
          </MenuItem>
          
          <MenuItem 
            onClick={() => handleMenuAction('statistics')}
            sx={{ 
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
            }}
          >
            <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
              <BarChartIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Статистика" />
          </MenuItem>
        </Menu>
      </Box>

      {/* Диалог статистики */}
      <Dialog
        open={showStatsDialog}
        onClose={() => setShowStatsDialog(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: 'background.paper',
            color: 'text.primary',
          }
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <BarChartIcon />
            Статистика
          </Box>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Текущий чат
        </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Box>
                <Typography variant="h4" fontWeight="bold" color="primary">
                  {currentChat?.messages.length || 0}
            </Typography>
                <Typography variant="body2" color="text.secondary">
              Сообщений
            </Typography>
          </Box>
          <Box>
                <Typography variant="h4" fontWeight="bold" color="secondary">
                  {currentChat?.messages.reduce((total, msg) => total + estimateTokens(msg.content), 0) || 0}
          </Typography>
                <Typography variant="body2" color="text.secondary">
              Токенов
            </Typography>
          </Box>
        </Box>
      </Box>

          <Divider sx={{ my: 2 }} />

          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Общая статистика
        </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Box>
                <Typography variant="h4" fontWeight="bold" color="primary">
                  {state.chats.length}
            </Typography>
                <Typography variant="body2" color="text.secondary">
                  Всего чатов
            </Typography>
          </Box>
          <Box>
                <Typography variant="h4" fontWeight="bold" color="secondary">
                  {state.stats.totalMessages}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Всего сообщений
                </Typography>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" fontWeight="bold" color="success.main">
              {state.stats.totalTokens}
            </Typography>
                <Typography variant="body2" color="text.secondary">
                  Всего токенов
                </Typography>
              </Box>
              <Box>
                <Typography variant="h4" fontWeight="bold" color="info.main">
                  {state.stats.sessionsToday}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Сессий сегодня
            </Typography>
          </Box>
        </Box>
      </Box>

          <Divider sx={{ my: 2 }} />

          <Box>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Информация о модели
            </Typography>
            {state.currentModel?.loaded ? (
              <Box>
                <Typography variant="body1" fontWeight="500">
                  {state.currentModel.metadata?.['general.name'] || 'Загружена'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {state.currentModel.metadata?.['general.architecture'] || 'Неизвестная архитектура'}
                </Typography>
                {state.currentModel.metadata?.['general.size_label'] && (
                  <Typography variant="body2" color="text.secondary">
                    Размер: {state.currentModel.metadata['general.size_label']}
                  </Typography>
                )}
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Модель не загружена
              </Typography>
            )}
            </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowStatsDialog(false)}>
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>

      {/* Выпадающее меню для чатов */}
      <Menu
        anchorEl={chatMenuAnchor}
        open={chatMenuOpen}
        onClose={handleChatMenuClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: {
            backgroundColor: 'rgba(30, 30, 30, 0.95)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 150,
          },
        }}
      >
        <MenuItem
          onClick={() => handleChatMenuAction('edit')}
              sx={{
                  color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Редактировать" />
        </MenuItem>
        
        <MenuItem
          onClick={() => setShowMoveToFolderMenu(true)}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Переместить в папку" />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleChatMenuAction('delete')}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Удалить" />
        </MenuItem>
      </Menu>

      {/* Диалог подтверждения удаления */}
      <Dialog
        open={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: '#1e1e1e',
            color: 'white',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle sx={{ color: 'white', fontWeight: 'bold' }}>
          Удалить чат
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: 'white', mt: 1 }}>
            Это действие навсегда удалит выбранный чат и не может быть отменено. 
            Пожалуйста, подтвердите для продолжения.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => setShowDeleteDialog(false)}
            sx={{
              backgroundColor: 'black',
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(0,0,0,0.8)' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Отменить
          </Button>
          <Button
            onClick={handleConfirmDelete}
            sx={{
              backgroundColor: '#f44336',
              color: 'white',
              '&:hover': { backgroundColor: '#d32f2f' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Удалить
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог создания папки */}
      <Dialog
        open={showCreateFolderDialog}
        onClose={() => setShowCreateFolderDialog(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: '#1e1e1e',
            color: 'white',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle sx={{ color: 'white', fontWeight: 'bold' }}>
          Создать папку
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            placeholder="Название папки"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleCreateFolder();
              }
            }}
              sx={{
              mt: 2,
              '& .MuiOutlinedInput-root': {
                  color: 'white',
                '& fieldset': {
                  borderColor: 'rgba(255,255,255,0.3)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(255,255,255,0.5)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'rgba(255,255,255,0.7)',
                },
                },
              }}
            />
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => setShowCreateFolderDialog(false)}
            sx={{
              backgroundColor: 'black',
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(0,0,0,0.8)' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Отменить
          </Button>
          <Button
            onClick={handleCreateFolder}
            disabled={!newFolderName.trim()}
            sx={{
              backgroundColor: '#2196f3',
              color: 'white',
              '&:hover': { backgroundColor: '#1976d2' },
              '&:disabled': { backgroundColor: 'rgba(255,255,255,0.1)' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Создать
          </Button>
        </DialogActions>
      </Dialog>

      {/* Меню перемещения в папку */}
      <Menu
        anchorEl={chatMenuAnchor}
        open={showMoveToFolderMenu}
        onClose={() => setShowMoveToFolderMenu(false)}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: {
            backgroundColor: 'rgba(30, 30, 30, 0.95)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 200,
          },
        }}
      >
        {/* Опция перемещения в ЧАТЫ */}
        <MenuItem
          onClick={() => selectedChatId && handleRemoveFromFolder(selectedChatId)}
          sx={{
            color: selectedChatId && !getChatFolder(selectedChatId) ? 'rgba(255,255,255,0.5)' : 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
          disabled={selectedChatId ? !getChatFolder(selectedChatId) : false}
        >
          <ListItemIcon sx={{ color: selectedChatId && !getChatFolder(selectedChatId) ? 'rgba(255,255,255,0.5)' : 'white', minWidth: 36 }}>
            <ChatIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Все чаты" />
        </MenuItem>
        
        {folders
          .filter(folder => {
            // Исключаем папку, в которой уже находится чат
            const currentFolder = selectedChatId ? getChatFolder(selectedChatId) : null;
            return !currentFolder || folder.id !== currentFolder.id;
          })
          .map((folder) => (
            <MenuItem
              key={folder.id}
              onClick={() => selectedChatId && handleMoveToFolder(selectedChatId, folder.id)}
              sx={{
                color: 'white',
                '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
              }}
            >
              <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
                <FolderIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText primary={folder.name} />
            </MenuItem>
          ))}
        {folders.filter(folder => {
          const currentFolder = selectedChatId ? getChatFolder(selectedChatId) : null;
          return !currentFolder || folder.id !== currentFolder.id;
        }).length === 0 && (
          <MenuItem disabled sx={{ color: 'rgba(255,255,255,0.5)' }}>
            <ListItemText primary="Нет доступных папок" />
          </MenuItem>
        )}
      </Menu>

      {/* Меню папки */}
      <Menu
        anchorEl={folderMenuAnchor}
        open={folderMenuOpen}
        onClose={handleFolderMenuClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: {
            backgroundColor: 'rgba(30, 30, 30, 0.95)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 200,
          },
        }}
      >
        <MenuItem
          onClick={() => handleFolderMenuAction('rename')}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Переименовать" />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleFolderMenuAction('delete')}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Удалить" />
        </MenuItem>
      </Menu>

      {/* Диалог переименования папки */}
      <Dialog
        open={showRenameFolderDialog}
        onClose={() => {
          setShowRenameFolderDialog(false);
          handleFolderMenuClose();
        }}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: '#1e1e1e',
            color: 'white',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle sx={{ color: 'white', fontWeight: 'bold' }}>
          Переименовать папку
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            placeholder="Название папки"
            value={renamingFolderName}
            onChange={(e) => setRenamingFolderName(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleRenameFolder();
              }
            }}
            sx={{
              mt: 2,
              '& .MuiOutlinedInput-root': {
                color: 'white',
                '& fieldset': {
                  borderColor: 'rgba(255,255,255,0.3)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(255,255,255,0.5)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'rgba(255,255,255,0.7)',
                },
              },
            }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => {
              setShowRenameFolderDialog(false);
              handleFolderMenuClose();
            }}
            sx={{
              backgroundColor: 'black',
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(0,0,0,0.8)' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Отменить
          </Button>
          <Button
            onClick={handleRenameFolder}
            disabled={!renamingFolderName.trim()}
            sx={{
              backgroundColor: '#2196f3',
              color: 'white',
              '&:hover': { backgroundColor: '#1976d2' },
              '&:disabled': { backgroundColor: 'rgba(255,255,255,0.1)' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Переименовать
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог удаления папки */}
      <Dialog
        open={showDeleteFolderDialog}
        onClose={() => {
          setShowDeleteFolderDialog(false);
          handleFolderMenuClose();
        }}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: '#1e1e1e',
            color: 'white',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle sx={{ color: 'white', fontWeight: 'bold' }}>
          Удалить папку
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: 'white', mt: 1, mb: 2 }}>
            Что делать с чатами в этой папке?
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Button
              fullWidth
              variant={deleteWithContent ? 'contained' : 'outlined'}
              onClick={() => setDeleteWithContent(true)}
              sx={{
                justifyContent: 'flex-start',
                textTransform: 'none',
                color: deleteWithContent ? 'white' : 'rgba(255,255,255,0.7)',
                borderColor: 'rgba(255,255,255,0.3)',
                '&:hover': {
                  borderColor: 'rgba(255,255,255,0.5)',
                  backgroundColor: 'rgba(255,255,255,0.1)',
                },
              }}
            >
              Удалить со всем содержимым
            </Button>
            
            <Button
              fullWidth
              variant={!deleteWithContent ? 'contained' : 'outlined'}
              onClick={() => setDeleteWithContent(false)}
              sx={{
                justifyContent: 'flex-start',
                textTransform: 'none',
                color: !deleteWithContent ? 'white' : 'rgba(255,255,255,0.7)',
                borderColor: 'rgba(255,255,255,0.3)',
                '&:hover': {
                  borderColor: 'rgba(255,255,255,0.5)',
                  backgroundColor: 'rgba(255,255,255,0.1)',
                },
              }}
            >
              Переместить чаты в "Все чаты"
            </Button>
      </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => {
              setShowDeleteFolderDialog(false);
              handleFolderMenuClose();
            }}
            sx={{
              backgroundColor: 'black',
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(0,0,0,0.8)' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Отменить
          </Button>
          <Button
            onClick={handleDeleteFolder}
            sx={{
              backgroundColor: '#f44336',
              color: 'white',
              '&:hover': { backgroundColor: '#d32f2f' },
              textTransform: 'none',
              px: 3,
            }}
          >
            Удалить
          </Button>
        </DialogActions>
      </Dialog>

      {/* Модальное окно настроек */}
      <SettingsModal
        open={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        isDarkMode={isDarkMode}
        onToggleTheme={onToggleTheme}
      />
    </Drawer>
  );
}
