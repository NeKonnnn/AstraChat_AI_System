import React, { useState, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Avatar,
  Card,
  CardContent,
  Button,
  Chip,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Divider,
  Paper,
  TextField,
  Collapse,
  CircularProgress,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
} from '@mui/material';
import {
  Chat as ChatIcon,
  ArrowBack as ArrowBackIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  Add as AddIcon,
  Folder as FolderIcon,
  AttachMoney as MoneyIcon,
  Lightbulb as LightbulbIcon,
  Image as ImageIcon,
  PlayArrow as PlayArrowIcon,
  MusicNote as MusicNoteIcon,
  AutoAwesome as SparkleIcon,
  Work as BriefcaseIcon,
  Language as GlobeIcon,
  School as GraduationIcon,
  AccountBalanceWallet as WalletIcon,
  Favorite as FavoriteIcon,
  SportsBaseball as BaseballIcon,
  Restaurant as CutleryIcon,
  LocalCafe as CoffeeIcon,
  Code as CodeIcon,
  LocalFlorist as LeafIcon,
  Pets as CatIcon,
  DirectionsCar as CarIcon,
  MenuBook as BookIcon,
  Cloud as UmbrellaIcon,
  CalendarToday as CalendarIcon,
  Computer as DesktopIcon,
  VolumeUp as SpeakerIcon,
  Assessment as ChartIcon,
  Email as MailIcon,
  Assignment as AssignmentIcon,
  Luggage as LuggageIcon,
  ExpandMore as ExpandMoreIcon,
  Send as SendIcon,
  Search as SearchIcon,
  Mic as MicIcon,
  AttachFile as AttachFileIcon,
  School as SchoolIcon,
  Archive as ArchiveIcon,
  PushPin as PushPinIcon,
  Close as CloseIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import VoiceChatDialog from '../components/VoiceChatDialog';
import ChatInputBar from '../components/ChatInputBar';
import { useTheme } from '@mui/material/styles';
import { MENU_BORDER_RADIUS_PX } from '../constants/menuStyles';

const projectIconMap: Record<string, React.ComponentType<any>> = {
  folder: FolderIcon,
  money: MoneyIcon,
  lightbulb: LightbulbIcon,
  gallery: ImageIcon,
  video: PlayArrowIcon,
  music: MusicNoteIcon,
  sparkle: SparkleIcon,
  edit: EditIcon,
  briefcase: BriefcaseIcon,
  globe: GlobeIcon,
  graduation: GraduationIcon,
  wallet: WalletIcon,
  heart: FavoriteIcon,
  baseball: BaseballIcon,
  cutlery: CutleryIcon,
  coffee: CoffeeIcon,
  code: CodeIcon,
  leaf: LeafIcon,
  cat: CatIcon,
  car: CarIcon,
  book: BookIcon,
  umbrella: UmbrellaIcon,
  calendar: CalendarIcon,
  desktop: DesktopIcon,
  speaker: SpeakerIcon,
  chart: ChartIcon,
  mail: MailIcon,
  assignment: AssignmentIcon,
  luggage: LuggageIcon,
};

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const { state } = useAppContext();
  const { getProjectById, setCurrentChat, createChat, moveChatToProject, updateChatTitle, deleteChat, archiveChat, getChatById, moveChatToFolder, togglePinInProject, showNotification } = useAppActions();
  const { sendMessage, isConnected } = useSocket();
  const [chatsExpanded, setChatsExpanded] = useState(true);
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [chatMenuAnchor, setChatMenuAnchor] = useState<null | HTMLElement>(null);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; type: string }>>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [transcriptionModalOpen, setTranscriptionModalOpen] = useState(false);
  const [chatInputStyle, setChatInputStyle] = useState<'compact' | 'classic'>(() =>
    (localStorage.getItem('chat_input_style') as 'compact' | 'classic') || 'compact'
  );

  // Слушаем изменение стиля поля ввода через настройки
  React.useEffect(() => {
    const handler = () => {
      setChatInputStyle((localStorage.getItem('chat_input_style') as 'compact' | 'classic') || 'compact');
    };
    window.addEventListener('interfaceSettingsChanged', handler);
    return () => window.removeEventListener('interfaceSettingsChanged', handler);
  }, []);

  const project = projectId ? getProjectById(projectId) : null;
  
  // Получаем чаты проекта и сортируем: запиненные сначала
  const projectChats = React.useMemo(() => {
    if (!project) return [];
    
    const chats = state.chats.filter(chat => chat.projectId === projectId && !chat.isArchived);
    
    // Сортируем: запиненные чаты сначала
    return chats.sort((a, b) => {
      const aIsPinned = a.isPinnedInProject || false;
      const bIsPinned = b.isPinnedInProject || false;
      
      if (aIsPinned && !bIsPinned) return -1;
      if (!aIsPinned && bIsPinned) return 1;
      
      // Если оба запинены или оба незапинены, сортируем по дате обновления
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });
  }, [project, projectId, state.chats]);

  const renderProjectIcon = () => {
    if (!project) return null;
    
    if (project.iconType === 'emoji' && project.icon) {
      return (
        <Avatar
          sx={{
            width: 32,
            height: 32,
            bgcolor: project.iconColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : project.iconColor || 'rgba(255,255,255,0.1)',
            fontSize: 18,
          }}
        >
          {project.icon}
        </Avatar>
      );
    }
    if (project.iconType === 'icon' && project.icon) {
      const IconComponent = projectIconMap[project.icon] || FolderIcon;
      return (
        <Avatar
          sx={{
            width: 32,
            height: 32,
            bgcolor: project.iconColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : project.iconColor || 'rgba(255,255,255,0.1)',
            color: 'white',
          }}
        >
          <IconComponent sx={{ fontSize: 18 }} />
        </Avatar>
      );
    }
    return (
      <Avatar
        sx={{
          width: 32,
          height: 32,
          bgcolor: 'rgba(255,255,255,0.1)',
          color: 'white',
        }}
      >
        <FolderIcon sx={{ fontSize: 18 }} />
      </Avatar>
    );
  };

  if (!project) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="h6">Проект не найден</Typography>
        <Button onClick={() => navigate('/')} sx={{ mt: 2 }}>
          Вернуться на главную
        </Button>
      </Box>
    );
  }

  const handleSelectChat = (chatId: string) => {
    setCurrentChat(chatId);
    navigate('/');
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !isConnected || isSending || !projectId) {
      return;
    }

    setIsSending(true);
    
    try {
      // Создаем новый чат
      const chatId = createChat();
      
      // Перемещаем чат в проект
      moveChatToProject(chatId, projectId);
      
      // Устанавливаем название чата на основе первого сообщения
      const title = inputMessage.length > 50 
        ? inputMessage.substring(0, 50) + '...'
        : inputMessage;
      updateChatTitle(chatId, title);
      
      // Устанавливаем как текущий чат
      setCurrentChat(chatId);
      
      // Отправляем сообщение
      await sendMessage(inputMessage.trim(), chatId);
      
      // Переходим на страницу чата
      navigate('/');
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setIsSending(false);
      setInputMessage('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleRemoveFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleChatMenuClick = (event: React.MouseEvent<HTMLElement>, chatId: string) => {
    event.stopPropagation();
    setChatMenuAnchor(event.currentTarget);
    setSelectedChatId(chatId);
  };

  const handleChatMenuClose = () => {
    setChatMenuAnchor(null);
  };

  const handleChatMenuAction = (action: string) => {
    if (!selectedChatId) {
      return;
    }

    switch (action) {
      case 'pin':
        // Переключаем закрепление внутри проекта
        togglePinInProject(selectedChatId);
        handleChatMenuClose();
        setSelectedChatId(null);
        break;
      case 'rename':
        const chat = projectChats.find(c => c.id === selectedChatId);
        if (chat) {
          setEditingChatId(selectedChatId);
          setEditingTitle(chat.title);
        }
        handleChatMenuClose();
        break;
      case 'archive':
        archiveChat(selectedChatId);
        handleChatMenuClose();
        setSelectedChatId(null);
        break;
      case 'removeFromProject':
        moveChatToProject(selectedChatId, null);
        handleChatMenuClose();
        setSelectedChatId(null);
        break;
      case 'delete':
        setShowDeleteDialog(true);
        handleChatMenuClose();
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
        const remainingChats = projectChats.filter(chat => chat.id !== selectedChatId);
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

  const handleSaveEdit = () => {
    if (editingChatId && editingTitle.trim()) {
      updateChatTitle(editingChatId, editingTitle.trim());
      setEditingChatId(null);
      setEditingTitle('');
    }
  };

  const handleKeyPressEdit = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      setEditingChatId(null);
      setEditingTitle('');
    }
  };

  const formatChatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return 'Сегодня';
    } else if (date.toDateString() === yesterday.toDateString()) {
      return 'Вчера';
    } else {
      return date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short',
      });
    }
  };

  return (
    <Box 
      sx={{ 
        height: '100vh', 
        display: 'flex', 
        flexDirection: 'column',
        background: theme.palette.mode === 'dark'
          ? 'linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 50%, #1a1a1a 100%)'
          : 'linear-gradient(135deg, #f5f5f5 0%, #ffffff 50%, #fafafa 100%)',
      }}
    >
      {/* Основной контент с центрированием */}
      <Box
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          px: 3,
          py: 8,
        }}
      >
        {/* Заголовок проекта */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 4 }}>
          {renderProjectIcon()}
          <Typography
            variant="h4"
            sx={{
              fontWeight: 600,
              color: theme.palette.mode === 'dark' ? 'white' : '#333',
            }}
          >
            {project.name}
          </Typography>
        </Box>

        {/* Объединенное поле ввода с кнопками */}
        <ChatInputBar
          value={inputMessage}
          onChange={setInputMessage}
          onKeyPress={handleKeyPress}
          placeholder={
            !isConnected
              ? 'Нет соединения с сервером'
              : isSending
                ? 'Отправка сообщения...'
                : 'Чем я могу помочь вам сегодня?'
          }
          inputDisabled={!isConnected || isSending}
          inputRef={inputRef}
          isDarkMode={theme.palette.mode === 'dark'}
          styleVariant={chatInputStyle}
          containerSx={{
            mb: 3,
            p: chatInputStyle === 'classic' ? 0 : 1.5,
            px: chatInputStyle === 'classic' ? 0 : 2,
            borderRadius: chatInputStyle === 'classic' ? '28px' : '28px',
            maxWidth: '800px',
            width: '100%',
            mx: 'auto',
          }}
          fileInputRef={fileInputRef}
          onAttachClick={() => fileInputRef.current?.click()}
          onFileSelect={(files) => {
            if (files?.length) {
              setUploadedFiles(prev => [...prev, ...Array.from(files).map(f => ({ name: f.name, type: f.type }))]);
            }
          }}
          uploadedFiles={uploadedFiles}
          onFileRemove={(_, index) => handleRemoveFile(index)}
          isUploading={isUploading}
          attachDisabled={isUploading || isSending}
          onSettingsClick={handleMenuOpen}
          settingsDisabled={isSending}
          onSendClick={handleSendMessage}
          sendDisabled={!inputMessage.trim() || !isConnected || isSending}
          isSending={isSending}
          onVoiceClick={() => setTranscriptionModalOpen(true)}
          voiceDisabled={isSending}
          voiceTooltip="Голосовой ввод"
        />

        {/* Список чатов */}
        {projectChats.length > 0 && (
          <Box
            sx={{
              width: '100%',
              maxWidth: '800px',
            }}
          >
            <Box
              onClick={() => setChatsExpanded(!chatsExpanded)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 2,
                py: 1.5,
                cursor: 'pointer',
                borderRadius: 2,
                mb: 1,
                '&:hover': {
                  bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
                },
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  fontWeight: 500,
                  color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.7)',
                }}
              >
                Чаты
              </Typography>
              <ExpandMoreIcon
                sx={{
                  fontSize: '1.2rem',
                  color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.7)',
                  transform: chatsExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                  transition: 'transform 0.2s ease',
                }}
              />
            </Box>

            <Collapse in={chatsExpanded}>
              <List sx={{ py: 0 }}>
                {projectChats.map((chat) => {
                  const isPinned = chat.isPinnedInProject || false;
                  
                  return (
                    <ListItem
                      key={chat.id}
                      disablePadding
                      sx={{ mb: 0.5 }}
                      secondaryAction={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography
                            variant="caption"
                            sx={{
                              color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
                              fontSize: '0.75rem',
                            }}
                          >
                            {formatChatDate(chat.updatedAt)}
                          </Typography>
                          <IconButton
                            size="small"
                            onClick={(e) => handleChatMenuClick(e, chat.id)}
                            sx={{
                              opacity: 0,
                              transition: 'opacity 0.2s',
                              '.MuiListItem-root:hover &': {
                                opacity: 1,
                              },
                              color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)',
                            }}
                          >
                            <MoreVertIcon fontSize="small" />
                          </IconButton>
                        </Box>
                      }
                    >
                      <ListItemButton
                        onClick={(e) => {
                          if (editingChatId === chat.id) {
                            e.stopPropagation();
                            return;
                          }
                          handleSelectChat(chat.id);
                        }}
                        sx={{
                          borderRadius: 2,
                          py: 1.5,
                          px: 2,
                          '&:hover': {
                            bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
                          },
                        }}
                      >
                        {isPinned && (
                          <PushPinIcon 
                            sx={{ 
                              fontSize: '0.9rem', 
                              mr: 1,
                              color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)',
                            }} 
                          />
                        )}
                        <ListItemText
                        primary={
                          editingChatId === chat.id ? (
                            <TextField
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onBlur={handleSaveEdit}
                              onKeyDown={handleKeyPressEdit}
                              onClick={(e) => e.stopPropagation()}
                              autoFocus
                              size="small"
                              fullWidth
                              sx={{
                                '& .MuiInputBase-input': {
                                  color: theme.palette.mode === 'dark' ? 'white' : '#333',
                                  fontSize: '0.875rem',
                                  py: 0.5,
                                },
                                '& .MuiOutlinedInput-notchedOutline': {
                                  borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)',
                                },
                                '&:hover .MuiOutlinedInput-notchedOutline': {
                                  borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
                                },
                                '& .MuiOutlinedInput-root': {
                                  '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                    borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)',
                                  },
                                },
                              }}
                            />
                          ) : (
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: 400,
                                color: theme.palette.mode === 'dark' ? 'white' : '#333',
                              }}
                            >
                              {chat.title}
                            </Typography>
                          )
                        }
                      />
                      </ListItemButton>
                    </ListItem>
                  );
                })}
              </List>
            </Collapse>

            {/* Меню чата */}
            <Menu
              anchorEl={chatMenuAnchor}
              open={Boolean(chatMenuAnchor)}
              onClose={handleChatMenuClose}
              PaperProps={{
                sx: {
                  bgcolor: theme.palette.mode === 'dark' ? 'rgba(30, 30, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(10px)',
                  border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
                  borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
                  minWidth: 180,
                },
              }}
            >
              <MenuItem
                onClick={() => handleChatMenuAction('pin')}
                sx={{
                  color: theme.palette.mode === 'dark' ? 'white' : '#333',
                  '&:hover': {
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333', minWidth: 36 }}>
                  <PushPinIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={selectedChatId && getChatById(selectedChatId)?.isPinnedInProject ? "Открепить" : "Пин"} />
              </MenuItem>
              <MenuItem
                onClick={() => handleChatMenuAction('rename')}
                sx={{
                  color: theme.palette.mode === 'dark' ? 'white' : '#333',
                  '&:hover': {
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333', minWidth: 36 }}>
                  <EditIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Переименовать" />
              </MenuItem>
              <MenuItem
                onClick={() => handleChatMenuAction('archive')}
                sx={{
                  color: theme.palette.mode === 'dark' ? 'white' : '#333',
                  '&:hover': {
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333', minWidth: 36 }}>
                  <ArchiveIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Архивировать" />
              </MenuItem>
              {selectedChatId && getChatById(selectedChatId)?.projectId && (
                <MenuItem
                  onClick={() => handleChatMenuAction('removeFromProject')}
                  sx={{
                    color: theme.palette.mode === 'dark' ? 'white' : '#333',
                    '&:hover': {
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                    },
                  }}
                >
                  <ListItemIcon sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333', minWidth: 36 }}>
                    <FolderIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText primary="Перенести из проекта" />
                </MenuItem>
              )}
              <Divider sx={{ my: 0.5, borderColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} />
              <MenuItem
                onClick={() => handleChatMenuAction('delete')}
                sx={{
                  color: '#d32f2f',
                  '&:hover': {
                    bgcolor: 'rgba(211, 47, 47, 0.1)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: '#d32f2f', minWidth: 36 }}>
                  <DeleteIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Удалить" primaryTypographyProps={{ sx: { color: '#d32f2f' } }} />
              </MenuItem>
            </Menu>

          </Box>
        )}

        {/* Меню дополнительных действий (шестеренка) — всегда доступно */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
          anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
          transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          PaperProps={{
            sx: {
              bgcolor: theme.palette.mode === 'dark' ? 'rgba(30, 30, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(10px)',
              border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
              borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
              minWidth: 180,
            },
          }}
        >
          <MenuItem
            onClick={() => {
              setInputMessage('');
              handleMenuClose();
            }}
            sx={{
              color: theme.palette.mode === 'dark' ? 'white' : '#333',
              gap: 1,
              '&:hover': {
                bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
              },
            }}
          >
            <ClearIcon fontSize="small" />
            <ListItemText primary="Очистить поле ввода" />
          </MenuItem>
        </Menu>

        <VoiceChatDialog
          open={transcriptionModalOpen}
          onClose={() => setTranscriptionModalOpen(false)}
        />

        {/* Диалог подтверждения удаления (как в сайдбаре) */}
        <Dialog
          open={showDeleteDialog}
          onClose={() => setShowDeleteDialog(false)}
          maxWidth="sm"
          fullWidth
          PaperProps={{
            sx: {
              backgroundColor: theme.palette.mode === 'dark' ? '#1e1e1e' : '#ffffff',
              color: theme.palette.mode === 'dark' ? 'white' : '#333',
              borderRadius: 2,
            },
          }}
        >
          <DialogTitle sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333', fontWeight: 'bold' }}>
            Удалить чат
          </DialogTitle>
          <DialogContent>
            <Typography sx={{ color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.8)', mt: 1 }}>
              Это действие навсегда удалит выбранный чат и не может быть отменено.
              Пожалуйста, подтвердите для продолжения.
            </Typography>
          </DialogContent>
          <DialogActions sx={{ p: 2, gap: 1 }}>
            <Button
              onClick={() => setShowDeleteDialog(false)}
              sx={{
                backgroundColor: theme.palette.mode === 'dark' ? 'black' : 'rgba(0,0,0,0.08)',
                color: theme.palette.mode === 'dark' ? 'white' : '#333',
                '&:hover': { backgroundColor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(0,0,0,0.12)' },
                textTransform: 'none',
                px: 3,
              }}
            >
              Отменить
            </Button>
            <Button
              onClick={handleConfirmDelete}
              sx={{
                backgroundColor: '#d32f2f',
                color: 'white',
                '&:hover': { backgroundColor: '#b71c1c' },
                textTransform: 'none',
                px: 3,
              }}
            >
              Удалить
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Box>
  );
}
