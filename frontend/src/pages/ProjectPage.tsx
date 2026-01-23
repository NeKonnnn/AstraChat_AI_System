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
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import { useTheme } from '@mui/material/styles';

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
  const { getProjectById, setCurrentChat, createChat, moveChatToProject, updateChatTitle, deleteChat, archiveChat, getChatById, moveChatToFolder, togglePinInProject } = useAppActions();
  const { sendMessage, isConnected } = useSocket();
  const [chatsExpanded, setChatsExpanded] = useState(true);
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [chatMenuAnchor, setChatMenuAnchor] = useState<null | HTMLElement>(null);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; type: string }>>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

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
        <Box
          sx={{
            width: '100%',
            maxWidth: '800px',
            mb: 3,
            p: 2,
            borderRadius: 2,
            bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
            border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
          }}
        >
          {/* Скрытый input для выбора файла */}
          <input
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png,.webp"
            style={{ display: 'none' }}
          />

          {/* Прикрепленные файлы */}
          {uploadedFiles.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {uploadedFiles.map((file, index) => (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      p: 1,
                      borderRadius: 2,
                      maxWidth: '300px',
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'}`,
                    }}
                  >
                    <Typography 
                      variant="caption" 
                      sx={{ 
                        color: theme.palette.mode === 'dark' ? 'white' : '#333',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {file.name}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={() => handleRemoveFile(index)}
                      sx={{ 
                        color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                        p: 0.5,
                      }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          {/* Индикатор загрузки файла */}
          {isUploading && (
            <Box sx={{ mb: 2, p: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333' }} />
                <Typography variant="caption" sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333' }}>
                  Загрузка документа...
                </Typography>
              </Box>
            </Box>
          )}

          {/* Поле ввода текста */}
          <TextField
            inputRef={inputRef}
            fullWidth
            multiline
            maxRows={4}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              !isConnected
                ? "Нет соединения с сервером" 
                : isSending
                  ? "Отправка сообщения..."
                  : "Чем я могу помочь вам сегодня?"
            }
            variant="outlined"
            size="small"
            disabled={!isConnected || isSending}
            sx={{
              mb: 1.5,
              '& .MuiOutlinedInput-root': {
                bgcolor: 'transparent',
                border: 'none',
                fontSize: '0.875rem',
                '& fieldset': {
                  border: 'none',
                },
                '&:hover fieldset': {
                  border: 'none',
                },
                '&.Mui-focused fieldset': {
                  border: 'none',
                },
                '&:hover': {
                  bgcolor: 'transparent',
                },
                '&.Mui-focused': {
                  bgcolor: 'transparent',
                }
              }
            }}
          />

          {/* Кнопки снизу */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              justifyContent: 'space-between',
            }}
          >
            {/* Левая группа кнопок */}
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {/* Кнопка загрузки документов */}
              <Tooltip title="Загрузить документ">
                <IconButton
                  sx={{ 
                    color: '#2196f3',
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    '&:hover': {
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                    },
                  }}
                  disabled={isUploading || isSending}
                >
                  <AttachFileIcon sx={{ fontSize: '1.2rem' }} />
                </IconButton>
              </Tooltip>

              {/* Кнопка меню с шестеренкой */}
              <Tooltip title="Дополнительные действия">
                <IconButton
                  onClick={handleMenuOpen}
                  disabled={isSending}
                  sx={{ 
                    color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    '&:hover': {
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                    },
                  }}
                >
                  <SettingsIcon sx={{ fontSize: '1.2rem' }} />
                </IconButton>
              </Tooltip>
            </Box>

            {/* Правая группа кнопок */}
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {/* Кнопка отправки */}
              <Tooltip title="Отправить">
                <span>
                  <IconButton
                    onClick={handleSendMessage}
                    disabled={!inputMessage.trim() || !isConnected || isSending}
                    color="primary"
                    sx={{
                      bgcolor: 'primary.main',
                      color: 'white',
                      '&:hover': {
                        bgcolor: 'primary.dark',
                      },
                      '&:disabled': {
                        bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
                        color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.6)' : 'rgba(0, 0, 0, 0.26)',
                      }
                    }}
                  >
                    {isSending ? (
                      <CircularProgress size={20} sx={{ color: 'inherit' }} />
                    ) : (
                      <SendIcon sx={{ fontSize: '1.2rem' }} />
                    )}
                  </IconButton>
                </span>
              </Tooltip>

              {/* Кнопка голосового ввода */}
              <Tooltip title="Голосовой ввод">
                <IconButton
                  disabled={isSending}
                  sx={{
                    bgcolor: 'secondary.main',
                    color: 'white',
                    '&:hover': { 
                      bgcolor: 'secondary.dark' 
                    },
                    '&:disabled': {
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
                      color: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.6)' : 'rgba(0, 0, 0, 0.26)',
                    }
                  }}
                >
                  <MicIcon sx={{ fontSize: '1.2rem' }} />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </Box>

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
                  borderRadius: 2,
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
                  color: '#ff6b6b',
                  '&:hover': {
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 107, 107, 0.1)' : 'rgba(255, 107, 107, 0.1)',
                  },
                }}
              >
                <ListItemIcon sx={{ color: '#ff6b6b', minWidth: 36 }}>
                  <DeleteIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Удалить" />
              </MenuItem>
            </Menu>

            {/* Меню дополнительных действий (шестеренка) */}
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              PaperProps={{
                sx: {
                  bgcolor: theme.palette.mode === 'dark' ? 'rgba(30, 30, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(10px)',
                  border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
                  borderRadius: 2,
                  minWidth: 180,
                },
              }}
            >
              <MenuItem
                onClick={() => {
                  handleMenuClose();
                }}
                sx={{
                  color: theme.palette.mode === 'dark' ? 'white' : '#333',
                  '&:hover': {
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                  },
                }}
              >
                <ListItemText primary="Настройки" />
              </MenuItem>
            </Menu>

            {/* Диалог подтверждения удаления */}
            <Dialog
              open={showDeleteDialog}
              onClose={() => setShowDeleteDialog(false)}
              PaperProps={{
                sx: {
                  bgcolor: theme.palette.mode === 'dark' ? 'rgba(30, 30, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                  backdropFilter: 'blur(10px)',
                  border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
                  borderRadius: 2,
                },
              }}
            >
              <DialogTitle sx={{ color: theme.palette.mode === 'dark' ? 'white' : '#333' }}>
                Удалить чат?
              </DialogTitle>
              <DialogContent>
                <Typography sx={{ color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)' }}>
                  Это действие нельзя отменить. Чат будет удален навсегда.
                </Typography>
              </DialogContent>
              <DialogActions>
                <Button
                  onClick={() => setShowDeleteDialog(false)}
                  sx={{
                    color: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.7)',
                  }}
                >
                  Отмена
                </Button>
                <Button
                  onClick={handleConfirmDelete}
                  color="error"
                  variant="contained"
                >
                  Удалить
                </Button>
              </DialogActions>
            </Dialog>
          </Box>
        )}
      </Box>
    </Box>
  );
}
