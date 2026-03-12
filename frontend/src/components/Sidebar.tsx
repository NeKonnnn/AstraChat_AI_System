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
  ChatOutlined as ChatIcon,
  SettingsOutlined as SettingsIcon,
  InfoOutlined as InfoIcon,
  Add as AddIcon,
  DeleteOutlined as DeleteIcon,
  EditOutlined as EditIcon,
  MoreVert as MoreVertIcon,
  ExpandMore as ExpandMoreIcon,
  Search as SearchIcon,
  FolderOutlined as FolderIcon,
  CreateNewFolderOutlined as AddFolderIcon,
  Menu as MenuIcon,
  LogoutOutlined as LogoutIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  ArchiveOutlined as ArchiveIcon,
  PushPinOutlined as PushPinIcon,
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
  KeyboardOutlined as KeyboardIcon,
  HelpOutline as HelpOutlineIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import { useAuth } from '../contexts/AuthContext';
import SettingsModal from './SettingsModal';
import ArchiveModal from './ArchiveModal';
import NewProjectModal from './NewProjectModal';
import EditProjectModal from './EditProjectModal';
import { useMoveToFolderAndProjectMenus, MoveToFolderAndProjectSubmenus } from './MoveToFolderAndProjectMenus';
import { MENU_BORDER_RADIUS_PX, getMenuColors, MENU_ICON_MIN_WIDTH, MENU_ICON_TO_TEXT_GAP_PX, MENU_ICON_FONT_SIZE_PX, MENU_MIN_WIDTH_PX, SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX, SIDEBAR_PROJECT_AVATAR_SIZE } from '../constants/menuStyles';
import { getSidebarPanelBackground } from '../constants/sidebarPanelColor';

// Задержки подменю «Справка» — как в MoveToFolderAndProjectMenus (убирает мигание)
const HELP_SUBMENU_GRACE_PERIOD_MS = 280;
const HELP_SUBMENU_CLOSE_CHECK_DELAY_MS = 120;

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
  const [showHelpSubmenu, setShowHelpSubmenu] = React.useState(false);
  const [helpSubmenuAnchor, setHelpSubmenuAnchor] = React.useState<HTMLElement | null>(null);
  const [showHelpDialog, setShowHelpDialog] = React.useState(false);
  const [showShortcutsDialog, setShowShortcutsDialog] = React.useState(false);
  const submenuHelpOpenedAtRef = React.useRef(0);
  const helpSubmenuOpenRef = React.useRef(false);
  const helpMenuAnchorRef = React.useRef<HTMLElement | null>(null);
  const closeHelpTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const helpSubmenuMousePositionRef = React.useRef({ clientX: 0, clientY: 0 });
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
  const [showEditProjectModal, setShowEditProjectModal] = React.useState(false);
  const [projectIdToEdit, setProjectIdToEdit] = React.useState<string | null>(null);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [showCreateFolderDialog, setShowCreateFolderDialog] = React.useState(false);
  const [newFolderName, setNewFolderName] = React.useState('');
  const [folderMenuAnchor, setFolderMenuAnchor] = React.useState<null | HTMLElement>(null);
  const [selectedFolderId, setSelectedFolderId] = React.useState<string | null>(null);
  const [showRenameFolderDialog, setShowRenameFolderDialog] = React.useState(false);
  const [renamingFolderName, setRenamingFolderName] = React.useState('');
  const [showDeleteFolderDialog, setShowDeleteFolderDialog] = React.useState(false);
  const [deleteWithContent, setDeleteWithContent] = React.useState(false);
  const [sidebarPanelBg, setSidebarPanelBg] = React.useState(() => getSidebarPanelBackground());
  const searchInputRef = React.useRef<HTMLInputElement>(null);
  const menuOpen = Boolean(anchorEl);

  React.useEffect(() => {
    const onColorChanged = () => setSidebarPanelBg(getSidebarPanelBackground());
    window.addEventListener('sidebarColorChanged', onColorChanged);
    return () => window.removeEventListener('sidebarColorChanged', onColorChanged);
  }, []);
  const chatMenuOpen = Boolean(chatMenuAnchor);
  const folderMenuOpen = Boolean(folderMenuAnchor);
  const projectMenuOpen = Boolean(projectMenuAnchor);

  const { menuBg, menuBorder, menuItemColor, menuItemHover, menuDividerBorder, menuDisabledColor } = getMenuColors(isDarkMode);

  // Отслеживание позиции мыши при открытом меню пользователя (для подменю «Справка» — как в MoveToFolderAndProjectMenus)
  React.useEffect(() => {
    if (!menuOpen) return;
    const onMove = (e: MouseEvent) => {
      helpSubmenuMousePositionRef.current = { clientX: e.clientX, clientY: e.clientY };
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, [menuOpen]);

  // При открытом подменю «Справка»: закрывать, если курсор над другим пунктом основного меню (как в MoveToFolderAndProjectMenus)
  React.useEffect(() => {
    if (!showHelpSubmenu) return;
    const onMove = () => {
      if (!helpSubmenuOpenRef.current) return;
      const anchor = helpMenuAnchorRef.current;
      const menu = anchor?.closest('[role="menu"]') as HTMLElement | null;
      if (!menu) return;
      const { clientX, clientY } = helpSubmenuMousePositionRef.current;
      const elements = document.elementsFromPoint(clientX, clientY);
      for (const el of elements) {
        if (!menu.contains(el)) continue;
        const item = (el as HTMLElement).closest?.('[role="menuitem"]');
        if (!item) continue;
        if (item.getAttribute?.('data-submenu-trigger') === 'help') break;
        if (closeHelpTimerRef.current) {
          clearTimeout(closeHelpTimerRef.current);
          closeHelpTimerRef.current = null;
        }
        helpSubmenuOpenRef.current = false;
        helpMenuAnchorRef.current = null;
        setShowHelpSubmenu(false);
        setHelpSubmenuAnchor(null);
        break;
      }
    };
    const id = setInterval(onMove, 80);
    return () => clearInterval(id);
  }, [showHelpSubmenu]);
  
  // Получаем проекты
  const projects = getProjects();

  // Загружаем настройку использования папок/проектов
  const [useFoldersMode, setUseFoldersMode] = React.useState(() => {
    const saved = localStorage.getItem('use_folders_mode');
    return saved !== null ? saved === 'true' : true; // По умолчанию папки
  });

  // Слушаем изменения настроек интерфейса
  React.useEffect(() => {
    const handleSettingsChange = () => {
      const saved = localStorage.getItem('use_folders_mode');
      setUseFoldersMode(saved !== null ? saved === 'true' : true);
    };
    
    window.addEventListener('interfaceSettingsChanged', handleSettingsChange);
    return () => {
      window.removeEventListener('interfaceSettingsChanged', handleSettingsChange);
    };
  }, []);

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

  const closeHelpSubmenu = React.useCallback(() => {
    if (closeHelpTimerRef.current) {
      clearTimeout(closeHelpTimerRef.current);
      closeHelpTimerRef.current = null;
    }
    helpSubmenuOpenRef.current = false;
    helpMenuAnchorRef.current = null;
    setShowHelpSubmenu(false);
    setHelpSubmenuAnchor(null);
  }, []);

  const handleMenuClose = () => {
    closeHelpSubmenu();
    setAnchorEl(null);
  };

  const handleHelpSubmenuEnter = React.useCallback((e: React.MouseEvent<HTMLElement>) => {
    const target = e.currentTarget;
    if (helpSubmenuOpenRef.current && helpMenuAnchorRef.current === target) return;
    helpMenuAnchorRef.current = target;
    helpSubmenuOpenRef.current = true;
    submenuHelpOpenedAtRef.current = Date.now();
    setHelpSubmenuAnchor(target);
    setShowHelpSubmenu(true);
  }, []);

  const handleHelpSubmenuLeave = React.useCallback((e: React.MouseEvent<HTMLElement>) => {
    const to = e.relatedTarget as HTMLElement | null;
    const currentTarget = e.currentTarget;
    const mainMenu = currentTarget.closest('[role="menu"]') as HTMLElement | null;
    const targetMenu = to?.closest?.('[role="menu"]');
    const msSinceOpen = Date.now() - submenuHelpOpenedAtRef.current;
    if (!showHelpSubmenu) {
      helpSubmenuOpenRef.current = false;
      helpMenuAnchorRef.current = null;
      setShowHelpSubmenu(false);
      setHelpSubmenuAnchor(null);
      return;
    }
    if (closeHelpTimerRef.current) {
      clearTimeout(closeHelpTimerRef.current);
      closeHelpTimerRef.current = null;
    }
    if (msSinceOpen < HELP_SUBMENU_GRACE_PERIOD_MS) return;
    const toMenuItem = to?.closest?.('[role="menuitem"]');
    const wentToOurTrigger = toMenuItem?.getAttribute?.('data-submenu-trigger') === 'help';
    const wentToOtherMainMenuItem =
      to && mainMenu?.contains(to) && toMenuItem !== currentTarget && !wentToOurTrigger;
    if (wentToOtherMainMenuItem) {
      helpSubmenuOpenRef.current = false;
      helpMenuAnchorRef.current = null;
      setShowHelpSubmenu(false);
      setHelpSubmenuAnchor(null);
      return;
    }
    if (targetMenu && targetMenu !== mainMenu) return;
    const closeHelpSubmenuLocal = () => {
      helpSubmenuOpenRef.current = false;
      helpMenuAnchorRef.current = null;
      setShowHelpSubmenu(false);
      setHelpSubmenuAnchor(null);
    };
    const checkPosition = () => {
      closeHelpTimerRef.current = null;
      const { clientX, clientY } = helpSubmenuMousePositionRef.current;
      const el = document.elementFromPoint(clientX, clientY) as HTMLElement | null;
      if (!el) {
        closeHelpSubmenuLocal();
        return;
      }
      if (el.closest('[data-help-submenu]')) return;
      if (mainMenu?.contains(el)) {
        const underMenuItem = el.closest('[role="menuitem"]');
        if (underMenuItem === currentTarget) return;
        if (underMenuItem && underMenuItem.getAttribute?.('data-submenu-trigger') !== 'help') {
          closeHelpSubmenuLocal();
          return;
        }
      }
      closeHelpSubmenuLocal();
    };
    const scheduleCheck = () => {
      const { clientX, clientY } = helpSubmenuMousePositionRef.current;
      const el = document.elementFromPoint(clientX, clientY) as HTMLElement | null;
      if (el && mainMenu?.contains(el)) {
        const underMenuItem = el.closest('[role="menuitem"]');
        if (underMenuItem && underMenuItem.getAttribute?.('data-submenu-trigger') !== 'help') {
          closeHelpSubmenuLocal();
          return;
        }
      }
      if (closeHelpTimerRef.current) clearTimeout(closeHelpTimerRef.current);
      closeHelpTimerRef.current = setTimeout(checkPosition, HELP_SUBMENU_CLOSE_CHECK_DELAY_MS);
    };
    requestAnimationFrame(scheduleCheck);
  }, [showHelpSubmenu]);

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

  const moveToMenus = useMoveToFolderAndProjectMenus({
    chatMenuOpen,
    moveChatToFolder,
    handleChatMenuClose,
  });

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
    // Исключаем чаты, которые уже находятся в папках или проектах (в зависимости от режима), и архивированные чаты
    const chatsInFolders = useFoldersMode ? new Set(folders.flatMap(folder => folder.chatIds)) : new Set();
    const chatsInProjects = !useFoldersMode ? new Set(state.chats.filter(chat => chat.projectId).map(chat => chat.id)) : new Set();
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
        setProjectIdToEdit(projectIdToAction);
        handleProjectMenuClose();
        setShowEditProjectModal(true);
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
            ? sidebarPanelBg
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
                AstraChat
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
                endAdornment: useFoldersMode ? (
                  <Tooltip title="Создать папку">
                    <IconButton
                      size="small"
                      onClick={() => setShowCreateFolderDialog(true)}
                      sx={{ color: 'rgba(255,255,255,0.7)', p: 0.5 }}
                    >
                      <AddFolderIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ) : null,
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
      {!useFoldersMode && open && (
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
                  <ListItemIcon sx={{ color: 'white', minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`, marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px` }}>
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
                  const sizePx = SIDEBAR_PROJECT_AVATAR_SIZE;
                  const iconFontSizePx = sizePx - 4;
                  const iconColor = project.iconColor || '#9ca3af';
                  const outlineStyle = {
                    width: `${sizePx}px`,
                    height: `${sizePx}px`,
                    bgcolor: 'transparent',
                    border: '1.5px solid',
                    borderColor: iconColor,
                    color: iconColor,
                  };
                  if (project.iconType === 'emoji' && project.icon) {
                    return (
                      <Avatar sx={{ ...outlineStyle, fontSize: `${iconFontSizePx}px` }}>
                        {project.icon}
                      </Avatar>
                    );
                  }
                  if (project.iconType === 'icon' && project.icon) {
                    const IconComponent = projectIconMap[project.icon] || FolderIcon;
                    return (
                      <Avatar sx={outlineStyle}>
                        <IconComponent sx={{ fontSize: `${iconFontSizePx}px` }} />
                      </Avatar>
                    );
                  }
                  return (
                    <Avatar sx={outlineStyle}>
                      <FolderIcon sx={{ fontSize: `${iconFontSizePx}px` }} />
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
                            gap: 0.5,
                          }}
                        >
                          <ListItemIcon sx={{ color: 'white', minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`, marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px` }}>
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
                                <ListItemIcon sx={{ color: 'white', minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`, marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px` }}>
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
          {/* Отображение папок - только если включен режим папок */}
          {useFoldersMode && (
            <>
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
                            <ListItemIcon sx={{ color: 'white', minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`, marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px` }}>
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
            </>
          )}

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
                    <ListItemIcon sx={{ color: 'white', minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`, marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px` }}>
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
                          <ListItemIcon sx={{ color: 'white', minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`, marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px` }}>
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
        disableAutoFocus
        disableEnforceFocus
        disableAutoFocusItem
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
            backgroundColor: menuBg,
            backdropFilter: 'blur(10px)',
            border: `1px solid ${menuBorder}`,
            borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
            minWidth: `${MENU_MIN_WIDTH_PX}px`,
          },
        }}
        MenuListProps={{
          sx: { '& .MuiListItemText-root': { marginLeft: 0 } },
        }}
      >
        <MenuItem 
          onClick={() => handleMenuAction('settings')}
          sx={{ 
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <SettingsIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Настройки" />
        </MenuItem>
        
        <MenuItem 
          onClick={() => handleMenuAction('archive')}
          sx={{ 
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <ArchiveIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Архив" />
        </MenuItem>
        
        <MenuItem
          data-submenu-trigger="help"
          onMouseEnter={handleHelpSubmenuEnter}
          onMouseLeave={handleHelpSubmenuLeave}
          sx={{ 
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover },
            ...(showHelpSubmenu && { backgroundColor: menuItemHover }),
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <InfoIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Справка" />
          <ChevronRightIcon sx={{ ml: 'auto', fontSize: '1rem' }} />
        </MenuItem>
        
        <MenuItem 
          onClick={() => handleMenuAction('logout')}
          sx={{ 
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <LogoutIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Выйти из аккаунта" />
        </MenuItem>
      </Menu>

      {/* Подменю «Справка» */}
      <Menu
        anchorEl={helpSubmenuAnchor}
        open={showHelpSubmenu}
        onClose={closeHelpSubmenu}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{
          root: { sx: { zIndex: 1301 } },
          backdrop: { style: { pointerEvents: 'none' } },
        }}
        PaperProps={{
          'data-help-submenu': true,
          sx: {
            backgroundColor: menuBg,
            backdropFilter: 'blur(10px)',
            border: `1px solid ${menuBorder}`,
            borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
            minWidth: `${MENU_MIN_WIDTH_PX}px`,
            zIndex: 1301,
          },
          onMouseEnter: () => {
            if (closeHelpTimerRef.current) {
              clearTimeout(closeHelpTimerRef.current);
              closeHelpTimerRef.current = null;
            }
          },
          onMouseLeave: (e: React.MouseEvent<HTMLDivElement>) => {
            const to = e.relatedTarget as HTMLElement;
            const mainPaper = helpSubmenuAnchor?.closest('.MuiPopover-paper');
            if (mainPaper?.contains(to)) return;
            setShowHelpSubmenu(false);
            setHelpSubmenuAnchor(null);
          },
        }}
        MenuListProps={{
          sx: { '& .MuiListItemText-root': { marginLeft: 0 } },
        }}
        disableAutoFocusItem
        disableAutoFocus
        disableEnforceFocus
        disableScrollLock
      >
        <MenuItem
          onClick={() => {
            closeHelpSubmenu();
            handleMenuClose();
            setShowHelpDialog(true);
          }}
          sx={{ color: menuItemColor, '&:hover': { backgroundColor: menuItemHover } }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <HelpOutlineIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Помощь" />
        </MenuItem>
        <MenuItem
          onClick={() => {
            closeHelpSubmenu();
            handleMenuClose();
            setShowShortcutsDialog(true);
          }}
          sx={{ color: menuItemColor, '&:hover': { backgroundColor: menuItemHover } }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <KeyboardIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Сочетание клавиш" />
        </MenuItem>
      </Menu>

      {/* Диалог «Помощь» */}
      <Dialog
        open={showHelpDialog}
        onClose={() => setShowHelpDialog(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: isDarkMode ? '#1e1e1e' : '#ffffff',
            color: isDarkMode ? 'white' : '#333',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            p: 2,
            borderBottom: `1px solid ${isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
            backgroundColor: isDarkMode ? '#2a2a2a' : '#f5f5f5',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <HelpOutlineIcon />
            <Typography component="span" variant="h6" fontWeight="600">
              Помощь
            </Typography>
          </Box>
          <IconButton
            onClick={() => setShowHelpDialog(false)}
            size="small"
            sx={{
              color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
              '&:hover': {
                backgroundColor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
              },
            }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.8)' }}>
            Раздел помощи. Здесь можно разместить инструкции и ответы на частые вопросы.
          </Typography>
        </DialogContent>
      </Dialog>

      {/* Диалог «Сочетание клавиш» */}
      <Dialog
        open={showShortcutsDialog}
        onClose={() => setShowShortcutsDialog(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: isDarkMode ? '#1e1e1e' : '#ffffff',
            color: isDarkMode ? 'white' : '#333',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            p: 2,
            borderBottom: `1px solid ${isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)'}`,
            backgroundColor: isDarkMode ? '#2a2a2a' : '#f5f5f5',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <KeyboardIcon />
            <Typography component="span" variant="h6" fontWeight="600">
              Сочетание клавиш
            </Typography>
          </Box>
          <IconButton
            onClick={() => setShowShortcutsDialog(false)}
            size="small"
            sx={{
              color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
              '&:hover': {
                backgroundColor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
              },
            }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.8)' }}>
            Список горячих клавиш приложения. Раздел в разработке.
          </Typography>
        </DialogContent>
      </Dialog>

      {/* Выпадающее меню для чатов */}
      <Menu
        anchorEl={chatMenuAnchor}
        open={chatMenuOpen}
        onClose={(event, reason) => {
          moveToMenus.closeSubmenus();
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
            backgroundColor: menuBg,
            backdropFilter: 'blur(10px)',
            border: `1px solid ${menuBorder}`,
            borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
            minWidth: `${MENU_MIN_WIDTH_PX}px`,
            pointerEvents: 'auto',
          },
        }}
        MenuListProps={{
          sx: {
            pointerEvents: 'auto',
            '& .MuiListItemText-root': { marginLeft: 0 },
          },
        }}
        disableAutoFocus
        disableEnforceFocus
      >
        <MenuItem
          onClick={() => handleChatMenuAction('pin')}
          onMouseEnter={moveToMenus.closeSubmenus}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
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
          onMouseEnter={moveToMenus.closeSubmenus}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Переименовать" />
        </MenuItem>
        
        {useFoldersMode && (
        <MenuItem
          data-submenu-trigger="folder"
          onMouseEnter={moveToMenus.handleFolderSubmenuEnter}
          onMouseLeave={moveToMenus.handleFolderSubmenuLeave}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover },
            ...(moveToMenus.showMoveToFolderMenu && { backgroundColor: menuItemHover }),
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Переместить в папку" />
          <ChevronRightIcon sx={{ ml: 'auto', fontSize: '1rem' }} />
        </MenuItem>
        )}
        
        {!useFoldersMode && (
        <MenuItem
          data-submenu-trigger="project"
          onMouseEnter={moveToMenus.handleProjectSubmenuEnter}
          onMouseLeave={moveToMenus.handleProjectSubmenuLeave}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover },
            ...(moveToMenus.showMoveToProjectMenu && { backgroundColor: menuItemHover }),
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Перенести в проект" />
          <ChevronRightIcon sx={{ ml: 'auto', fontSize: '1rem' }} />
        </MenuItem>
        )}
        
        <MenuItem
          onClick={() => handleChatMenuAction('archive')}
          onMouseEnter={moveToMenus.closeSubmenus}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <ArchiveIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Архив" />
        </MenuItem>
        {!useFoldersMode && selectedChatId && getChatById(selectedChatId)?.projectId && (
          <MenuItem
            onClick={() => handleChatMenuAction('removeFromProject')}
            onMouseEnter={moveToMenus.closeSubmenus}
            sx={{
              color: menuItemColor,
              '&:hover': { backgroundColor: menuItemHover }
            }}
          >
            <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
              <FolderIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Перенести из проекта" />
          </MenuItem>
        )}
        <Divider sx={{ my: 0.5, borderColor: menuDividerBorder }} />
        <MenuItem
          onClick={() => handleChatMenuAction('delete')}
          onMouseEnter={moveToMenus.closeSubmenus}
          sx={{
            color: '#d32f2f',
            '&:hover': { backgroundColor: 'rgba(211, 47, 47, 0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: '#d32f2f', minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Удалить" primaryTypographyProps={{ sx: { color: '#d32f2f' } }} />
        </MenuItem>
      </Menu>

      <MoveToFolderAndProjectSubmenus
        moveTo={moveToMenus}
        menuBg={menuBg}
        menuBorder={menuBorder}
        menuItemColor={menuItemColor}
        menuItemHover={menuItemHover}
        menuDisabledColor={menuDisabledColor}
        folders={folders}
        projects={projects}
        selectedChatId={selectedChatId}
        getChatFolder={getChatFolder}
        chats={state.chats}
        isDarkMode={isDarkMode}
        useFoldersMode={useFoldersMode}
        projectIconMap={projectIconMap}
        setShowCreateFolderDialog={setShowCreateFolderDialog}
        setPendingChatIdForProject={setPendingChatIdForProject}
        setShowNewProjectModal={setShowNewProjectModal}
        handleChatMenuClose={handleChatMenuClose}
        moveChatToProject={moveChatToProject}
      />

      {/* Диалог подтверждения удаления (адаптивный к светлой/тёмной теме, как в проекте) */}
      <Dialog
        open={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: isDarkMode ? '#1e1e1e' : '#ffffff',
            color: isDarkMode ? 'white' : '#333',
            borderRadius: 2,
          }
        }}
      >
        <DialogTitle sx={{ color: isDarkMode ? 'white' : '#333', fontWeight: 'bold' }}>
          Удалить чат
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.8)', mt: 1 }}>
            Это действие навсегда удалит выбранный чат и не может быть отменено.
            Пожалуйста, подтвердите для продолжения.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => setShowDeleteDialog(false)}
            sx={{
              backgroundColor: isDarkMode ? 'black' : 'rgba(0,0,0,0.08)',
              color: isDarkMode ? 'white' : '#333',
              '&:hover': { backgroundColor: isDarkMode ? 'rgba(0,0,0,0.8)' : 'rgba(0,0,0,0.12)' },
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
            backgroundColor: menuBg,
            backdropFilter: 'blur(10px)',
            border: `1px solid ${menuBorder}`,
            borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
            minWidth: `${MENU_MIN_WIDTH_PX}px`,
          },
        }}
        MenuListProps={{
          sx: { '& .MuiListItemText-root': { marginLeft: 0 } },
        }}
      >
        <MenuItem
          onClick={() => handleFolderMenuAction('rename')}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Переименовать" />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleFolderMenuAction('archive')}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <ArchiveIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Архив" />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleFolderMenuAction('delete')}
          sx={{
            color: '#d32f2f',
            '&:hover': { backgroundColor: 'rgba(211, 47, 47, 0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: '#d32f2f', minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Удалить" primaryTypographyProps={{ sx: { color: '#d32f2f' } }} />
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
      <EditProjectModal
        open={showEditProjectModal}
        onClose={() => {
          setShowEditProjectModal(false);
          setProjectIdToEdit(null);
        }}
        project={projectIdToEdit ? (projects.find((p) => p.id === projectIdToEdit) ?? null) : null}
        onSave={(projectId, updates) => {
          updateProject(projectId, updates);
          setShowEditProjectModal(false);
          setProjectIdToEdit(null);
        }}
      />

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
            backgroundColor: menuBg,
            backdropFilter: 'blur(10px)',
            border: `1px solid ${menuBorder}`,
            borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
            minWidth: `${MENU_MIN_WIDTH_PX}px`,
          },
        }}
        MenuListProps={{
          sx: { '& .MuiListItemText-root': { marginLeft: 0 } },
        }}
      >
        <MenuItem
          onClick={() => handleProjectMenuAction('edit')}
          sx={{
            color: menuItemColor,
            '&:hover': { backgroundColor: menuItemHover }
          }}
        >
          <ListItemIcon sx={{ color: menuItemColor, minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Редактировать проект" />
        </MenuItem>
        
        <MenuItem
          onClick={() => handleProjectMenuAction('delete')}
          sx={{
            color: '#d32f2f',
            '&:hover': { backgroundColor: 'rgba(211, 47, 47, 0.1)' }
          }}
        >
          <ListItemIcon sx={{ color: '#d32f2f', minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
            <DeleteIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Удалить проект" primaryTypographyProps={{ sx: { color: '#d32f2f' } }} />
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
    </Drawer>
  );
}
