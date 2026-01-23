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
  Tooltip,
} from '@mui/material';
import {
  Chat as ChatIcon,
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
  Logout as LogoutIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Archive as ArchiveIcon,
  PushPin as PushPinIcon,
  AttachMoney as MoneyIcon,
  Assignment as AssignmentIcon,
  Favorite as FavoriteIcon,
  Luggage as LuggageIcon,
  Lightbulb as LightbulbIcon,
  Image as ImageIcon,
  PlayArrow as PlayArrowIcon,
  MusicNote as MusicNoteIcon,
  AutoAwesome as SparkleIcon,
  Work as BriefcaseIcon,
  Language as GlobeIcon,
  School as GraduationIcon,
  AccountBalanceWallet as WalletIcon,
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
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import { useAuth } from '../contexts/AuthContext';
import SettingsModal from './SettingsModal';
import ArchiveModal from './ArchiveModal';
import NewProjectModal from './NewProjectModal';

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
  onHide?: () => void;
}

const menuItems: any[] = [];

// Маппинг иконок для проектов
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

export default function Sidebar({ open, onToggle, isDarkMode, onToggleTheme, onHide }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state } = useAppContext();
  const { user, logout } = useAuth();
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
    getFolders,
    archiveChat,
    archiveFolder,
    createProject,
    updateProject,
    deleteProject,
    getProjects,
    moveChatToProject,
    getChatById,
    togglePinInProject
  } = useAppActions();
  const { isConnected } = useSocket();
  
  // Получаем папки из состояния и сортируем (папка "Закреплено" должна быть первой)
  const allFolders = getFolders();
  const folders = React.useMemo(() => {
    const pinnedFolder = allFolders.find(f => f.name === 'Закреплено');
    const otherFolders = allFolders.filter(f => f.name !== 'Закреплено');
    return pinnedFolder ? [pinnedFolder, ...otherFolders] : otherFolders;
  }, [allFolders]);
  
  const [editingChatId, setEditingChatId] = React.useState<string | null>(null);
  const [editingTitle, setEditingTitle] = React.useState('');
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [showStatsDialog, setShowStatsDialog] = React.useState(false);
  const [chatMenuAnchor, setChatMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [selectedChatId, setSelectedChatId] = React.useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [chatsExpanded, setChatsExpanded] = React.useState(true);
  const [showSettingsModal, setShowSettingsModal] = React.useState(false);
  const [showArchiveModal, setShowArchiveModal] = React.useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = React.useState(false);
  const [pendingChatIdForProject, setPendingChatIdForProject] = React.useState<string | null>(null);
  const [projectsExpanded, setProjectsExpanded] = React.useState(true);
  const [expandedProjects, setExpandedProjects] = React.useState<Set<string>>(new Set());
  const [projectMenuAnchor, setProjectMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [selectedProjectId, setSelectedProjectId] = React.useState<string | null>(null);
  const [showDeleteProjectDialog, setShowDeleteProjectDialog] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [showCreateFolderDialog, setShowCreateFolderDialog] = React.useState(false);
  const [newFolderName, setNewFolderName] = React.useState('');
  const [showMoveToFolderMenu, setShowMoveToFolderMenu] = React.useState(false);
  const [showMoveToProjectMenu, setShowMoveToProjectMenu] = React.useState(false);
  const [projectMenuAnchorForChat, setProjectMenuAnchorForChat] = React.useState<null | HTMLElement>(null);
  const [folderMenuAnchorForChat, setFolderMenuAnchorForChat] = React.useState<null | HTMLElement>(null);
  const folderMenuCloseTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const projectMenuCloseTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const [folderMenuAnchor, setFolderMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(null);
  const [showRenameFolderDialog, setShowRenameFolderDialog] = React.useState(false);
  const [renamingFolderName, setRenamingFolderName] = React.useState('');
  const [showDeleteFolderDialog, setShowDeleteFolderDialog] = React.useState(false);
  const [deleteWithContent, setDeleteWithContent] = React.useState(false);
  const searchInputRef = React.useRef<HTMLInputElement>(null);
  const menuOpen = Boolean(anchorEl);
  const chatMenuOpen = Boolean(chatMenuAnchor);
  const folderMenuOpen = Boolean(folderMenuAnchor);
  const projectMenuOpen = Boolean(projectMenuAnchor);
  
  // Получаем проекты
  const projects = getProjects();

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
    setSelectedChatId(null); // Сбрасываем selectedChatId после завершения редактирования
  };

  const handleCancelEdit = () => {
    setEditingChatId(null);
    setEditingTitle('');
    setSelectedChatId(null); // Сбрасываем selectedChatId после отмены редактирования
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

  // Функция для закрепления/открепления чата
  const handleTogglePin = (chatId: string) => {
    const chat = getChatById(chatId);
    
    // Если чат находится в проекте, используем локальное закрепление
    if (chat?.projectId) {
      togglePinInProject(chatId);
      handleChatMenuClose();
      return;
    }
    
    // Для чатов вне проекта используем старую логику с папкой "Закреплено"
    const pinnedFolder = folders.find(f => f.name === 'Закреплено');
    const currentFolder = getChatFolder(chatId);
    
    if (currentFolder?.name === 'Закреплено') {
      // Открепляем чат - убираем из папки "Закреплено"
      // Папка автоматически удалится в reducer, если станет пустой
      moveChatToFolder(chatId, null);
    } else {
      // Закрепляем чат - перемещаем в папку "Закреплено"
      if (!pinnedFolder) {
        // Создаем папку "Закреплено" если её нет
        const pinnedFolderId = createFolder('Закреплено');
        moveChatToFolder(chatId, pinnedFolderId);
      } else {
        moveChatToFolder(chatId, pinnedFolder.id);
      }
    }
    handleChatMenuClose();
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
      case 'archive':
        setShowArchiveModal(true);
        break;
      case 'prompts':
        navigate('/prompts');
        break;
      case 'statistics':
        // Показываем статистику в диалоге
        setShowStatsDialog(true);
        break;
      case 'logout':
        logout();
        navigate('/login');
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
    // Не сбрасываем selectedChatId сразу, чтобы не потерять его при редактировании
    // Он будет сброшен после завершения редактирования
  };

  const handleChatMenuAction = (action: string) => {
    if (!selectedChatId) {
      return;
    }
    
    // Сохраняем selectedChatId перед закрытием меню
    const chatIdToAction = selectedChatId;
    
    switch (action) {
      case 'pin':
        handleTogglePin(chatIdToAction);
        break;
      case 'edit':
        const chatToEdit = state.chats.find(chat => chat.id === chatIdToAction);
        if (chatToEdit) {
          handleChatMenuClose();
          // Используем requestAnimationFrame для гарантированного обновления после закрытия меню
          requestAnimationFrame(() => {
            setEditingChatId(chatIdToAction);
            setEditingTitle(chatToEdit.title);
          });
        }
        break;
      case 'archive':
        handleChatMenuClose();
        archiveChat(chatIdToAction);
        break;
      case 'removeFromProject':
        handleChatMenuClose();
        moveChatToProject(chatIdToAction, null);
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

  // Функция для фильтрации чатов по поисковому запросу
  const filteredChats = React.useMemo(() => {
    // Исключаем чаты, которые уже находятся в папках, в проектах, и архивированные чаты
    const chatsInFolders = new Set(folders.flatMap(folder => folder.chatIds));
    const chatsInProjects = new Set(state.chats.filter(chat => chat.projectId).map(chat => chat.id));
    const availableChats = state.chats.filter(chat => 
      !chatsInFolders.has(chat.id) && !chatsInProjects.has(chat.id) && !chat.isArchived
    );
    
    if (!searchQuery.trim()) {
      return availableChats;
    }
    return availableChats.filter(chat => 
      chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.messages.some(msg => 
        msg.content.toLowerCase().includes(searchQuery.toLowerCase())
      )
    );
  }, [state.chats, searchQuery, folders, projects]);
  
  // Функция для получения чатов проекта
  const getProjectChats = (projectId: string) => {
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
  };
  
  // Функция для переключения раскрытия проекта
  const handleToggleProject = (projectId: string) => {
    setExpandedProjects(prev => {
      const newSet = new Set(prev);
      if (newSet.has(projectId)) {
        newSet.delete(projectId);
      } else {
        newSet.add(projectId);
      }
      return newSet;
    });
  };


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
    handleChatMenuClose(); // Закрываем основное меню чата после перемещения
  };

  const handleRemoveFromFolder = (chatId: string) => {
    moveChatToFolder(chatId, null);
    setShowMoveToFolderMenu(false);
    handleChatMenuClose(); // Закрываем основное меню чата после удаления из папки
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
    } else if (action === 'archive') {
      handleFolderMenuClose();
      archiveFolder(folderIdToAction);
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

  // Функции для работы с проектами
  const handleProjectMenuClick = (event: React.MouseEvent<HTMLElement>, projectId: string) => {
    event.stopPropagation();
    setProjectMenuAnchor(event.currentTarget);
    setSelectedProjectId(projectId);
  };

  const handleProjectMenuClose = () => {
    setProjectMenuAnchor(null);
    setSelectedProjectId(null);
  };

  const handleProjectMenuAction = (action: string) => {
    if (!selectedProjectId) {
      return;
    }
    
    const projectIdToAction = selectedProjectId;
    
    switch (action) {
      case 'edit':
        handleProjectMenuClose();
        // Здесь можно добавить логику редактирования проекта
        break;
      case 'delete':
        handleProjectMenuClose();
        setSelectedProjectId(projectIdToAction);
        setShowDeleteProjectDialog(true);
        break;
      default:
        handleProjectMenuClose();
        break;
    }
  };

  const handleConfirmDeleteProject = () => {
    if (selectedProjectId) {
      deleteProject(selectedProjectId);
      setShowDeleteProjectDialog(false);
      setSelectedProjectId(null);
    }
  };

  return (
    <Drawer
      variant="persistent"
      anchor="left"
      open={true}
      sx={{
        width: open ? 280 : 64,
        flexShrink: 0,
        transition: 'width 0.3s ease',
        '& .MuiDrawer-paper': {
          width: open ? 280 : 64,
          boxSizing: 'border-box',
          background: open 
            ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
            : 'background.default',
          color: open ? 'white' : 'text.primary',
          borderRight: '1px solid',
          borderColor: 'divider',
          transition: 'width 0.3s ease, background 0.3s ease, color 0.3s ease',
          overflowX: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      {/* Заголовок */}
      <Box
        sx={{
          p: open ? 2 : 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: open ? 'space-between' : 'center',
          background: open ? 'rgba(0,0,0,0.1)' : 'transparent',
          minHeight: 64,
        }}
      >
        {open && (
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
                  width: '70%',
                  height: '70%',
                  objectFit: 'cover',
                  transform: 'scale(1.2)',
                }}
              />
            </Box>
            <Box>
              <Typography variant="h6" fontWeight="bold">
                astrachat
              </Typography>
            </Box>
          </Box>
        )}
        <IconButton
          onClick={onToggle}
          sx={{
            color: open ? 'white' : 'text.primary',
            width: 40,
            height: 40,
            '&:hover': {
              backgroundColor: open 
                ? 'rgba(255,255,255,0.1)' 
                : 'action.hover',
            },
          }}
        >
          <MenuIcon />
        </IconButton>
      </Box>

      {open && (
        <>
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
              inputRef={searchInputRef}
              fullWidth
              placeholder="Поиск в чатах"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              size="small"
              InputProps={{
                startAdornment: <SearchIcon sx={{ color: 'rgba(255,255,255,0.7)', mr: 1, fontSize: '1rem' }} />,
                endAdornment: (
                  <Tooltip title="Создать папку">
                    <IconButton
                      size="small"
                      onClick={() => setShowCreateFolderDialog(true)}
                      sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                    >
                      <AddFolderIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
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
        </>
      )}

      {/* Кнопки в свернутом состоянии */}
      {!open && (
        <>
          <Box sx={{ 
            p: 1, 
            display: 'flex', 
            flexDirection: 'column', 
            gap: 1,
          }}>
            {/* Кнопка поиска */}
            <Tooltip title="Поиск в чатах" placement="right">
              <IconButton
                onClick={() => {
                  if (!open) {
                    onToggle(); // Раскрываем сайдбар для показа поиска
                    // Устанавливаем фокус на поле поиска после небольшой задержки
                    setTimeout(() => {
                      searchInputRef.current?.focus();
                    }, 300);
                  } else {
                    // Если сайдбар уже открыт, просто фокусируемся на поиске
                    searchInputRef.current?.focus();
                  }
                }}
                sx={{
                  color: 'text.primary',
                  opacity: 0.7,
                  width: 40,
                  height: 40,
                  borderRadius: 1,
                  '&:hover': {
                    backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    opacity: 1,
                    '& .MuiSvgIcon-root': {
                      color: 'primary.main',
                    },
                  },
                }}
              >
                <SearchIcon />
              </IconButton>
            </Tooltip>

            {/* Кнопка нового чата */}
            <Tooltip title="Новый чат" placement="right">
              <IconButton
                onClick={handleCreateChat}
                sx={{
                  color: 'text.primary',
                  opacity: 0.7,
                  width: 40,
                  height: 40,
                  borderRadius: 1,
                  '&:hover': {
                    backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    opacity: 1,
                    '& .MuiSvgIcon-root': {
                      color: 'primary.main',
                    },
                  },
                }}
              >
                <AddIcon />
              </IconButton>
            </Tooltip>
          </Box>

          {/* Кнопка "Скрыть панель" - на том же расстоянии как "Показать панель" */}
          {onHide && (
            <Box sx={{ 
              position: 'fixed',
              left: 0,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 64,
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center',
              zIndex: 1200,
            }}>
              <Tooltip title="Скрыть панель" placement="right">
                <IconButton
                  onClick={onHide}
                  sx={{
                    color: 'text.primary',
                    opacity: 0.7,
                    width: 40,
                    height: 40,
                    borderRadius: 1,
                    '&:hover': {
                      backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      opacity: 1,
                      '& .MuiSvgIcon-root': {
                        color: 'primary.main',
                      },
                    },
                  }}
                >
                  <ChevronLeftIcon />
                </IconButton>
              </Tooltip>
            </Box>
          )}

          {/* Кнопка пользователя внизу (как в раскрытом состоянии) */}
          <Box sx={{ p: 1, mt: 'auto' }}>
            <Tooltip title={user ? (user.full_name || user.username) : 'Меню'} placement="right">
              <IconButton
                onClick={handleMenuClick}
                sx={{
                  color: 'text.primary',
                  opacity: 0.7,
                  width: 40,
                  height: 40,
                  borderRadius: 1,
                  p: 0,
                  '&:hover': {
                    backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    opacity: 1,
                  },
                }}
              >
                <Avatar
                  sx={{
                    width: 40,
                    height: 40,
                    bgcolor: 'primary.main',
                    fontSize: 16,
                    fontWeight: 600,
                  }}
                >
                  {user ? user.username.charAt(0).toUpperCase() : 'М'}
                </Avatar>
              </IconButton>
            </Tooltip>
          </Box>
        </>
      )}

      {/* Раздел Проекты */}
      {open && (
        <Box sx={{ px: 1.5, mb: 1 }}>
          <Box
            onClick={() => setProjectsExpanded(!projectsExpanded)}
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
              Проекты
            </Typography>
            <ExpandMoreIcon
              sx={{
                fontSize: '1rem',
                opacity: 0.8,
                transform: projectsExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                transition: 'transform 0.2s ease',
              }}
            />
          </Box>
          {projectsExpanded && (
            <List sx={{ py: 0 }}>
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  onClick={() => setShowNewProjectModal(true)}
                  sx={{
                    borderRadius: 2,
                    backgroundColor: 'transparent',
                    '&:hover': {
                      backgroundColor: 'rgba(255,255,255,0.08)',
                    },
                    transition: 'all 0.2s ease',
                    py: 1,
                    px: 2,
                  }}
                >
                  <ListItemIcon sx={{ color: 'white', minWidth: 28 }}>
                    <AddFolderIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography
                        variant="body2"
                        sx={{
                          color: 'white',
                          fontWeight: 400,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontSize: '0.8rem',
                        }}
                      >
                        Новый проект
                      </Typography>
                    }
                  />
                </ListItemButton>
              </ListItem>
              {projects.map((project) => {
                const renderProjectIcon = () => {
                  if (project.iconType === 'emoji' && project.icon) {
                    return (
                      <Avatar
                        sx={{
                          width: 24,
                          height: 24,
                          bgcolor: project.iconColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : project.iconColor || 'rgba(255,255,255,0.1)',
                          fontSize: 14,
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
                          width: 24,
                          height: 24,
                          bgcolor: project.iconColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : project.iconColor || 'rgba(255,255,255,0.1)',
                          color: 'white',
                        }}
                      >
                        <IconComponent sx={{ fontSize: 14 }} />
                      </Avatar>
                    );
                  }
                  return (
                    <Avatar
                      sx={{
                        width: 24,
                        height: 24,
                        bgcolor: 'rgba(255,255,255,0.1)',
                        color: 'white',
                      }}
                    >
                      <FolderIcon sx={{ fontSize: 14 }} />
                    </Avatar>
                  );
                };

                const projectChats = getProjectChats(project.id);
                const isExpanded = expandedProjects.has(project.id);
                
                return (
                  <Box key={project.id} sx={{ mb: 0.5 }}>
                    <ListItem disablePadding>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          width: '100%',
                          px: 2,
                          py: 1,
                          borderRadius: 2,
                          '&:hover': {
                            backgroundColor: 'rgba(255,255,255,0.05)',
                          },
                          transition: 'background-color 0.2s ease',
                        }}
                      >
                        <Box
                          onClick={(e) => {
                            e.stopPropagation();
                            if (e.detail === 2) {
                              // Двойной клик - открываем страницу проекта
                              navigate(`/project/${project.id}`);
                            } else {
                              // Одинарный клик - раскрываем/сворачиваем
                              handleToggleProject(project.id);
                            }
                          }}
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            flex: 1,
                            cursor: 'pointer',
                            gap: 1,
                          }}
                        >
                          <ListItemIcon sx={{ color: 'white', minWidth: 28 }}>
                            {renderProjectIcon()}
                          </ListItemIcon>
                          <ListItemText
                            primary={
                              <Typography
                                variant="body2"
                                sx={{
                                  color: 'white',
                                  fontWeight: 400,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  fontSize: '0.8rem',
                                }}
                              >
                                {project.name}
                              </Typography>
                            }
                          />
                          <ExpandMoreIcon
                            sx={{
                              fontSize: '1rem',
                              opacity: 0.8,
                              transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                              transition: 'transform 0.2s ease',
                            }}
                          />
                        </Box>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            setProjectMenuAnchor(e.currentTarget);
                            setSelectedProjectId(project.id);
                          }}
                          sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                        >
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </ListItem>
                    {isExpanded && projectChats.length > 0 && (
                      <List sx={{ py: 0, pl: 2 }}>
                        {projectChats.map((chat) => {
                          const isPinned = chat.isPinnedInProject || false;
                          
                          return (
                            <ListItem key={chat.id} disablePadding sx={{ mb: 0.5 }}>
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
                                  backgroundColor: state.currentChatId === chat.id ? 'rgba(255,255,255,0.15)' : 'transparent',
                                  '&:hover': {
                                    backgroundColor: state.currentChatId === chat.id ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                                  },
                                  transition: 'all 0.2s ease',
                                  py: 1,
                                  px: 2,
                                }}
                              >
                                {isPinned && (
                                  <PushPinIcon 
                                    sx={{ 
                                      fontSize: '0.9rem', 
                                      mr: 0.5,
                                      color: 'rgba(255,255,255,0.7)',
                                    }} 
                                  />
                                )}
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
                                      onClick={(e) => e.stopPropagation()}
                                      autoFocus
                                      size="small"
                                      fullWidth
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
                                        '& .MuiOutlinedInput-root': {
                                          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                            borderColor: 'rgba(255,255,255,0.7)',
                                          },
                                        },
                                      }}
                                    />
                                  ) : (
                                    <Typography
                                      variant="body2"
                                      sx={{
                                        color: 'white',
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
                          );
                        })}
                      </List>
                    )}
                  </Box>
                );
              })}
            </List>
          )}
        </Box>
      )}

      {/* Список чатов */}
      {open && (
      <Box sx={{ 
        flexGrow: 1, 
        overflow: 'auto',
        // Кастомные стили для скроллбара под фиолетовый градиент сайдбара
        '&::-webkit-scrollbar': {
          width: '8px',
        },
        '&::-webkit-scrollbar-track': {
          background: 'rgba(102, 126, 234, 0.3)', // Полупрозрачный фиолетовый из градиента
          borderRadius: '4px',
        },
        '&::-webkit-scrollbar-thumb': {
          background: 'rgba(118, 75, 162, 0.6)', // Полупрозрачный фиолетовый из градиента
          borderRadius: '4px',
          '&:hover': {
            background: 'rgba(118, 75, 162, 0.8)',
          },
        },
        // Для Firefox
        scrollbarWidth: 'thin',
        scrollbarColor: 'rgba(118, 75, 162, 0.6) rgba(102, 126, 234, 0.3)',
      }}>
        <Box sx={{ p: 1 }}>
          {/* Отображение папки "Закреплено" первой, если она существует */}
          {folders.find(f => f.name === 'Закреплено') && (() => {
            const pinnedFolder = folders.find(f => f.name === 'Закреплено');
            if (!pinnedFolder) return null;
            return (
              <Box key={pinnedFolder.id} sx={{ mb: 1 }}>
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
                    onClick={() => handleToggleFolder(pinnedFolder.id)}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      flex: 1,
                      cursor: 'pointer',
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ opacity: 0.8, fontSize: '0.75rem' }}>
                      {pinnedFolder.name}
                    </Typography>
                    <ExpandMoreIcon
                      sx={{
                        fontSize: '1rem',
                        opacity: 0.8,
                        transform: pinnedFolder.expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                        transition: 'transform 0.2s ease',
                        ml: 1,
                      }}
                    />
                  </Box>
                  <IconButton
                    size="small"
                    onClick={(e) => handleFolderMenuClick(e, pinnedFolder.id)}
                    sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                  >
                    <MoreVertIcon fontSize="small" />
                  </IconButton>
                </Box>
                {pinnedFolder.expanded && (
                  <List sx={{ py: 0 }}>
                    {(() => {
                      const filteredFolderChats = pinnedFolder.chatIds
                        .map(chatId => ({ chatId, chat: state.chats.find(c => c.id === chatId) }))
                        .filter(({ chat }) => {
                          if (!chat) return false;
                          if (chat.isArchived) return false;
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
                            onClick={(e) => {
                              if (editingChatId === chatId) {
                                e.stopPropagation();
                                return;
                              }
                              handleSelectChat(chatId);
                            }}
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
                                    onClick={(e) => e.stopPropagation()}
                                    autoFocus
                                    size="small"
                                    fullWidth
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
                                      '& .MuiOutlinedInput-root': {
                                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                          borderColor: 'rgba(255,255,255,0.7)',
                                        },
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
            );
          })()}

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
                    onClick={(e) => {
                      // Не открываем чат, если идет редактирование
                      if (editingChatId === chat.id) {
                        e.stopPropagation();
                        return;
                      }
                      handleSelectChat(chat.id);
                    }}
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
                            onClick={(e) => e.stopPropagation()}
                            autoFocus
                            size="small"
                            fullWidth
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
                              '& .MuiOutlinedInput-root': {
                                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                  borderColor: 'rgba(255,255,255,0.7)',
                                },
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

          {/* Отображение остальных папок (кроме "Закреплено") */}
          {folders.filter(f => f.name !== 'Закреплено').map((folder) => (
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
                        // Исключаем архивированные чаты
                        if (chat.isArchived) return false;
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
                          onClick={(e) => {
                            // Не открываем чат, если идет редактирование
                            if (editingChatId === chatId) {
                              e.stopPropagation();
                              return;
                            }
                            handleSelectChat(chatId);
                          }}
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
                                  onClick={(e) => e.stopPropagation()}
                                  autoFocus
                                  size="small"
                                  fullWidth
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
                                    '& .MuiOutlinedInput-root': {
                                      '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                        borderColor: 'rgba(255,255,255,0.7)',
                                      },
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
      )}

      {/* Навигационное меню */}
      {open && (
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
      )}


      {/* Кнопка пользователя внизу */}
      {open && (
      <Box sx={{ p: 1.5, background: 'rgba(0,0,0,0.2)' }}>
        {user ? (
          <Box
            onClick={handleMenuClick}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              p: 1,
              borderRadius: 2,
              backgroundColor: 'rgba(255,255,255,0.05)',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              '&:hover': {
                backgroundColor: 'rgba(255,255,255,0.1)',
              },
            }}
          >
            <Avatar
              sx={{
                width: 36,
                height: 36,
                bgcolor: 'primary.main',
                fontSize: 16,
              }}
            >
              {user.username.charAt(0).toUpperCase()}
            </Avatar>
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="body2" fontWeight="600" noWrap sx={{ fontSize: '0.875rem' }}>
                {user.full_name || user.username}
              </Typography>
            </Box>
            <MoreVertIcon sx={{ opacity: 0.5, fontSize: '1.2rem' }} />
          </Box>
        ) : (
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
        )}
      </Box>
      )}

      {/* Меню пользователя (доступно в обоих состояниях) */}
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
          onClick={() => handleMenuAction('archive')}
          sx={{ 
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <ArchiveIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Архив" />
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
        
        <MenuItem 
          onClick={() => handleMenuAction('logout')}
          sx={{ 
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Выйти из аккаунта" />
        </MenuItem>
      </Menu>

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
        onClose={(event, reason) => {
          // Закрываем подменю при закрытии основного меню
          setShowMoveToFolderMenu(false);
          setShowMoveToProjectMenu(false);
          setFolderMenuAnchorForChat(null);
          setProjectMenuAnchorForChat(null);
          handleChatMenuClose();
        }}
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
            pointerEvents: 'auto',
          },
        }}
        MenuListProps={{
          sx: {
            pointerEvents: 'auto',
          },
        }}
        disableAutoFocus
        disableEnforceFocus
      >
        <MenuItem
          onClick={() => handleChatMenuAction('pin')}
          onMouseEnter={() => {
            // Закрываем подменю при наведении на другие пункты меню
            setShowMoveToFolderMenu(false);
            setShowMoveToProjectMenu(false);
            setFolderMenuAnchorForChat(null);
            setProjectMenuAnchorForChat(null);
          }}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <PushPinIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary={
            (() => {
              const chat = selectedChatId ? getChatById(selectedChatId) : null;
              if (chat?.projectId) {
                return chat.isPinnedInProject ? 'Открепить' : 'Пин';
              }
              return getChatFolder(selectedChatId || '')?.name === 'Закреплено' ? 'Открепить' : 'Пин';
            })()
          } />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleChatMenuAction('edit')}
          onMouseEnter={() => {
            // Закрываем подменю при наведении на другие пункты меню
            setShowMoveToFolderMenu(false);
            setShowMoveToProjectMenu(false);
            setFolderMenuAnchorForChat(null);
            setProjectMenuAnchorForChat(null);
          }}
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
          onMouseEnter={(e) => {
            // Отменяем закрытие подменю, если курсор вернулся на пункт меню
            if (folderMenuCloseTimeoutRef.current) {
              clearTimeout(folderMenuCloseTimeoutRef.current);
              folderMenuCloseTimeoutRef.current = null;
            }
            
            const target = e.currentTarget;
            // Устанавливаем anchor и открываем меню одновременно
            setFolderMenuAnchorForChat(target);
            setShowMoveToFolderMenu(true);
            // Закрываем подменю проекта, если оно было открыто
            setShowMoveToProjectMenu(false);
            setProjectMenuAnchorForChat(null);
          }}
          onMouseLeave={(e) => {
            // Очищаем предыдущий таймер, если он был
            if (folderMenuCloseTimeoutRef.current) {
              clearTimeout(folderMenuCloseTimeoutRef.current);
              folderMenuCloseTimeoutRef.current = null;
            }
            
            // Проверяем, переходит ли курсор к подменю или другому пункту меню
            const relatedTarget = e.relatedTarget as HTMLElement;
            if (relatedTarget) {
              // Если курсор переходит к подменю, не закрываем
              const submenu = relatedTarget.closest('[role="menu"]');
              const currentMenu = e.currentTarget.closest('[role="menu"]');
              if (submenu && submenu !== currentMenu) {
                return;
              }
              // Если курсор переходит к другому пункту меню в основном меню, закрываем подменю сразу
              const menuItem = relatedTarget.closest('[role="menuitem"]');
              if (menuItem && menuItem !== e.currentTarget && currentMenu?.contains(menuItem)) {
                setShowMoveToFolderMenu(false);
                setFolderMenuAnchorForChat(null);
                return;
              }
            }
            
            // Если relatedTarget null, проверяем сразу, где находится курсор
            const activeElement = document.elementFromPoint(
              e.clientX || 0,
              e.clientY || 0
            ) as HTMLElement;
            
            if (activeElement) {
              const currentMenu = e.currentTarget.closest('[role="menu"]');
              const submenu = activeElement.closest('[role="menu"]');
              
              // Если курсор на подменю, не закрываем
              if (submenu && submenu !== currentMenu) {
                return;
              }
              
              // Если курсор на другом пункте меню в основном меню, закрываем подменю сразу
              const menuItem = activeElement.closest('[role="menuitem"]');
              if (menuItem && menuItem !== e.currentTarget && currentMenu?.contains(menuItem)) {
                setShowMoveToFolderMenu(false);
                setFolderMenuAnchorForChat(null);
                return;
              }
              
              // Если курсор на текущем пункте меню, не закрываем
              if (activeElement.closest('[role="menuitem"]') === e.currentTarget) {
                return;
              }
            }
            
            // Если курсор не на подменю и не на пункте меню, используем небольшую задержку
            // Это позволяет курсору перейти на подменю, если он движется в его сторону
            folderMenuCloseTimeoutRef.current = setTimeout(() => {
              const checkElement = document.elementFromPoint(
                e.clientX || 0,
                e.clientY || 0
              ) as HTMLElement;
              if (checkElement) {
                const submenu = checkElement.closest('[role="menu"]');
                const currentMenu = e.currentTarget.closest('[role="menu"]');
                if (submenu && submenu !== currentMenu) {
                  return;
                }
              }
              setShowMoveToFolderMenu(false);
              setFolderMenuAnchorForChat(null);
              folderMenuCloseTimeoutRef.current = null;
            }, 100);
          }}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Переместить в папку" />
          <ChevronRightIcon sx={{ ml: 'auto', fontSize: '1rem' }} />
        </MenuItem>
        
        <MenuItem
          onMouseEnter={(e) => {
            // Отменяем закрытие подменю, если курсор вернулся на пункт меню
            if (projectMenuCloseTimeoutRef.current) {
              clearTimeout(projectMenuCloseTimeoutRef.current);
              projectMenuCloseTimeoutRef.current = null;
            }
            
            const target = e.currentTarget;
            // Устанавливаем anchor и открываем меню одновременно
            setProjectMenuAnchorForChat(target);
            setShowMoveToProjectMenu(true);
            // Закрываем подменю папки, если оно было открыто
            setShowMoveToFolderMenu(false);
            setFolderMenuAnchorForChat(null);
          }}
          onMouseLeave={(e) => {
            // Очищаем предыдущий таймер, если он был
            if (projectMenuCloseTimeoutRef.current) {
              clearTimeout(projectMenuCloseTimeoutRef.current);
              projectMenuCloseTimeoutRef.current = null;
            }
            
            // Проверяем, переходит ли курсор к подменю или другому пункту меню
            const relatedTarget = e.relatedTarget as HTMLElement;
            if (relatedTarget) {
              // Если курсор переходит к подменю, не закрываем
              const submenu = relatedTarget.closest('[role="menu"]');
              const currentMenu = e.currentTarget.closest('[role="menu"]');
              if (submenu && submenu !== currentMenu) {
                return;
              }
              // Если курсор переходит к другому пункту меню в основном меню, закрываем подменю сразу
              const menuItem = relatedTarget.closest('[role="menuitem"]');
              if (menuItem && menuItem !== e.currentTarget && currentMenu?.contains(menuItem)) {
                setShowMoveToProjectMenu(false);
                setProjectMenuAnchorForChat(null);
                return;
              }
            }
            
            // Если relatedTarget null, проверяем сразу, где находится курсор
            const activeElement = document.elementFromPoint(
              e.clientX || 0,
              e.clientY || 0
            ) as HTMLElement;
            
            if (activeElement) {
              const currentMenu = e.currentTarget.closest('[role="menu"]');
              const submenu = activeElement.closest('[role="menu"]');
              
              // Если курсор на подменю, не закрываем
              if (submenu && submenu !== currentMenu) {
                return;
              }
              
              // Если курсор на другом пункте меню в основном меню, закрываем подменю сразу
              const menuItem = activeElement.closest('[role="menuitem"]');
              if (menuItem && menuItem !== e.currentTarget && currentMenu?.contains(menuItem)) {
                setShowMoveToProjectMenu(false);
                setProjectMenuAnchorForChat(null);
                return;
              }
              
              // Если курсор на текущем пункте меню, не закрываем
              if (activeElement.closest('[role="menuitem"]') === e.currentTarget) {
                return;
              }
            }
            
            // Если курсор не на подменю и не на пункте меню, используем небольшую задержку
            // Это позволяет курсору перейти на подменю, если он движется в его сторону
            projectMenuCloseTimeoutRef.current = setTimeout(() => {
              const checkElement = document.elementFromPoint(
                e.clientX || 0,
                e.clientY || 0
              ) as HTMLElement;
              if (checkElement) {
                const submenu = checkElement.closest('[role="menu"]');
                const currentMenu = e.currentTarget.closest('[role="menu"]');
                if (submenu && submenu !== currentMenu) {
                  return;
                }
              }
              setShowMoveToProjectMenu(false);
              setProjectMenuAnchorForChat(null);
              projectMenuCloseTimeoutRef.current = null;
            }, 100);
          }}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Перенести в проект" />
          <ChevronRightIcon sx={{ ml: 'auto', fontSize: '1rem' }} />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleChatMenuAction('archive')}
          onMouseEnter={() => {
            // Закрываем подменю при наведении на другие пункты меню
            setShowMoveToFolderMenu(false);
            setShowMoveToProjectMenu(false);
            setFolderMenuAnchorForChat(null);
            setProjectMenuAnchorForChat(null);
          }}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <ArchiveIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Архив" />
        </MenuItem>
        {selectedChatId && getChatById(selectedChatId)?.projectId && (
          <MenuItem
            onClick={() => handleChatMenuAction('removeFromProject')}
            onMouseEnter={() => {
              // Закрываем подменю при наведении на другие пункты меню
              setShowMoveToFolderMenu(false);
              setShowMoveToProjectMenu(false);
              setFolderMenuAnchorForChat(null);
              setProjectMenuAnchorForChat(null);
            }}
            sx={{
              color: 'white',
              '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
            }}
          >
            <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
              <FolderIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Перенести из проекта" />
          </MenuItem>
        )}
        <Divider sx={{ my: 0.5, borderColor: 'rgba(255,255,255,0.1)' }} />
        <MenuItem
          onClick={() => handleChatMenuAction('delete')}
          onMouseEnter={() => {
            // Закрываем подменю при наведении на другие пункты меню
            setShowMoveToFolderMenu(false);
            setShowMoveToProjectMenu(false);
            setFolderMenuAnchorForChat(null);
            setProjectMenuAnchorForChat(null);
          }}
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

      {/* Подменю для перемещения в проект */}
      <Menu
        anchorEl={projectMenuAnchorForChat}
        open={showMoveToProjectMenu}
        onClose={(event, reason) => {
          setShowMoveToProjectMenu(false);
          setProjectMenuAnchorForChat(null);
        }}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            backgroundColor: 'rgba(30, 30, 30, 0.95)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 200,
            pointerEvents: 'auto',
          },
          onMouseEnter: () => {
            // Держим подменю открытым, когда курсор на нем
            setShowMoveToProjectMenu(true);
          },
          onMouseLeave: (e: React.MouseEvent<HTMLDivElement>) => {
            // Проверяем, не переходит ли курсор обратно к кнопке или основному меню
            const relatedTarget = e.relatedTarget as HTMLElement;
            if (relatedTarget) {
              // Если курсор переходит к основному меню или кнопке, не закрываем
              if (relatedTarget.closest('[role="menu"]') ||
                  relatedTarget === projectMenuAnchorForChat ||
                  relatedTarget.closest('[role="menuitem"]') === projectMenuAnchorForChat) {
                return;
              }
            }
            // Курсор покидает подменю и не переходит к основному меню - закрываем
            setShowMoveToProjectMenu(false);
            setProjectMenuAnchorForChat(null);
          },
        }}
        MenuListProps={{
          onMouseEnter: () => {
            // Держим подменю открытым, когда курсор на нем
            setShowMoveToProjectMenu(true);
          },
          onMouseLeave: (e: React.MouseEvent<HTMLUListElement>) => {
            // Проверяем, не переходит ли курсор обратно к кнопке или основному меню
            const relatedTarget = e.relatedTarget as HTMLElement;
            if (relatedTarget) {
              // Если курсор переходит к основному меню или кнопке, не закрываем
              if (relatedTarget.closest('[role="menu"]') ||
                  relatedTarget === projectMenuAnchorForChat ||
                  relatedTarget.closest('[role="menuitem"]') === projectMenuAnchorForChat) {
                return;
              }
            }
            // Курсор покидает подменю и не переходит к основному меню - закрываем
            setShowMoveToProjectMenu(false);
            setProjectMenuAnchorForChat(null);
          },
        }}
        disableAutoFocusItem
        disableAutoFocus
        disableEnforceFocus
      >
        <MenuItem
          onClick={() => {
            if (selectedChatId) {
              setPendingChatIdForProject(selectedChatId);
              setShowNewProjectModal(true);
              setShowMoveToProjectMenu(false);
              setProjectMenuAnchorForChat(null);
              handleChatMenuClose();
            }
          }}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <AddFolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Новый проект" />
        </MenuItem>
        {projects.map((project) => {
          const renderProjectIcon = () => {
            if (project.iconType === 'emoji' && project.icon) {
              return (
                <Avatar
                  sx={{
                    width: 20,
                    height: 20,
                    bgcolor: project.iconColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : project.iconColor || 'rgba(255,255,255,0.1)',
                    fontSize: 12,
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
                    width: 20,
                    height: 20,
                    bgcolor: project.iconColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : project.iconColor || 'rgba(255,255,255,0.1)',
                    color: 'white',
                  }}
                >
                  <IconComponent sx={{ fontSize: 12 }} />
                </Avatar>
              );
            }
            return (
              <Avatar
                sx={{
                  width: 20,
                  height: 20,
                  bgcolor: 'rgba(255,255,255,0.1)',
                  color: 'white',
                }}
              >
                <FolderIcon sx={{ fontSize: 12 }} />
              </Avatar>
            );
          };

          const chat = selectedChatId ? state.chats.find(c => c.id === selectedChatId) : null;
          const isSelected = chat?.projectId === project.id;

          return (
            <MenuItem
              key={project.id}
              onClick={() => {
                if (selectedChatId) {
                  moveChatToProject(selectedChatId, isSelected ? null : project.id);
                  setShowMoveToProjectMenu(false);
                  setProjectMenuAnchorForChat(null);
                  handleChatMenuClose();
                }
              }}
              sx={{
                color: isSelected ? 'rgba(255,255,255,0.5)' : 'white',
                '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
              }}
              disabled={isSelected}
            >
              <ListItemIcon sx={{ color: isSelected ? 'rgba(255,255,255,0.5)' : 'white', minWidth: 36 }}>
                {renderProjectIcon()}
              </ListItemIcon>
              <ListItemText primary={project.name} />
            </MenuItem>
          );
        })}
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
        anchorEl={folderMenuAnchorForChat}
        open={showMoveToFolderMenu}
        onClose={(event, reason) => {
          setShowMoveToFolderMenu(false);
          setFolderMenuAnchorForChat(null);
        }}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            backgroundColor: 'rgba(30, 30, 30, 0.95)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 200,
            pointerEvents: 'auto',
          },
          onMouseEnter: () => {
            // Держим подменю открытым, когда курсор на нем
            setShowMoveToFolderMenu(true);
          },
          onMouseLeave: (e: React.MouseEvent<HTMLDivElement>) => {
            // Проверяем, не переходит ли курсор обратно к кнопке или основному меню
            const relatedTarget = e.relatedTarget as HTMLElement;
            if (relatedTarget) {
              // Если курсор переходит к основному меню или кнопке, не закрываем
              if (relatedTarget.closest('[role="menu"]') ||
                  relatedTarget === folderMenuAnchorForChat ||
                  relatedTarget.closest('[role="menuitem"]') === folderMenuAnchorForChat) {
                return;
              }
            }
            // Курсор покидает подменю и не переходит к основному меню - закрываем
            setShowMoveToFolderMenu(false);
            setFolderMenuAnchorForChat(null);
          },
        }}
        MenuListProps={{
          onMouseEnter: () => {
            // Держим подменю открытым, когда курсор на нем
            setShowMoveToFolderMenu(true);
          },
          onMouseLeave: (e: React.MouseEvent<HTMLUListElement>) => {
            // Проверяем, не переходит ли курсор обратно к кнопке или основному меню
            const relatedTarget = e.relatedTarget as HTMLElement;
            if (relatedTarget) {
              // Если курсор переходит к основному меню или кнопке, не закрываем
              if (relatedTarget.closest('[role="menu"]') ||
                  relatedTarget === folderMenuAnchorForChat ||
                  relatedTarget.closest('[role="menuitem"]') === folderMenuAnchorForChat) {
                return;
              }
            }
            // Курсор покидает подменю и не переходит к основному меню - закрываем
            setShowMoveToFolderMenu(false);
            setFolderMenuAnchorForChat(null);
          },
        }}
        disableAutoFocusItem
        disableAutoFocus
        disableEnforceFocus
      >
        {/* Создать папку */}
        <MenuItem
          onClick={() => {
            setShowCreateFolderDialog(true);
            setShowMoveToFolderMenu(false);
            setFolderMenuAnchorForChat(null);
            handleChatMenuClose();
          }}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <AddFolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Создать папку" />
        </MenuItem>
        
        {/* Опция перемещения в ЧАТЫ */}
        <MenuItem
          onClick={() => {
            if (selectedChatId) {
              handleRemoveFromFolder(selectedChatId);
              setShowMoveToFolderMenu(false);
              setFolderMenuAnchorForChat(null);
              handleChatMenuClose();
            }
          }}
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
              onClick={() => {
                if (selectedChatId) {
                  handleMoveToFolder(selectedChatId, folder.id);
                  setShowMoveToFolderMenu(false);
                  setFolderMenuAnchorForChat(null);
                  handleChatMenuClose();
                }
              }}
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
          onClick={() => handleFolderMenuAction('archive')}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <ArchiveIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Архив" />
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

      {/* Модальное окно архива */}
      <ArchiveModal
        open={showArchiveModal}
        onClose={() => setShowArchiveModal(false)}
        isDarkMode={isDarkMode}
      />

      {/* Модальное окно создания проекта */}
      <NewProjectModal
        open={showNewProjectModal}
        onClose={() => {
          setShowNewProjectModal(false);
          setPendingChatIdForProject(null);
        }}
        onCreateProject={(projectData) => {
          const projectId = createProject({
            name: projectData.name,
            icon: projectData.icon,
            iconType: projectData.iconType,
            iconColor: projectData.iconColor,
            memory: projectData.memory,
            instructions: projectData.instructions,
          });
          // Если проект создается из меню чата, перемещаем чат в проект
          if (pendingChatIdForProject) {
            moveChatToProject(pendingChatIdForProject, projectId);
            setPendingChatIdForProject(null);
          }
        }}
      />

      {/* Меню проекта */}
      <Menu
        anchorEl={projectMenuAnchor}
        open={projectMenuOpen}
        onClose={handleProjectMenuClose}
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
          onClick={() => handleProjectMenuAction('edit')}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: 'white', minWidth: 36 }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Редактировать проект" />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleProjectMenuAction('delete')}
          sx={{
            color: 'white',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: '#f44336', minWidth: 36 }}>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Удалить проект" primaryTypographyProps={{ sx: { color: '#f44336' } }} />
        </MenuItem>
      </Menu>

      {/* Диалог подтверждения удаления проекта */}
      <Dialog
        open={showDeleteProjectDialog}
        onClose={() => setShowDeleteProjectDialog(false)}
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
          Удалить проект
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: 'white', mt: 1 }}>
            Это действие навсегда удалит выбранный проект и не может быть отменено. 
            Пожалуйста, подтвердите для продолжения.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => setShowDeleteProjectDialog(false)}
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
            onClick={handleConfirmDeleteProject}
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
    </Drawer>
  );
}
