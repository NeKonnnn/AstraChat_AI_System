import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Typography,
  Card,
  CardContent,
  Avatar,
  Chip,
  Tooltip,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  CircularProgress,
  Menu,
  Collapse,
  Drawer,
  Divider,
  Checkbox,
  FormControlLabel,
  Paper,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import {
  Send as SendIcon,
  Person as PersonIcon,
  Clear as ClearIcon,
  ContentCopy as CopyIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Edit as EditIcon,
  Mic as MicIcon,
  VolumeUp as VolumeUpIcon,
  Close as CloseIcon,
  Upload as UploadIcon,
  Settings as SettingsIcon,
  Square as SquareIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Add as AddIcon,
  Menu as MenuIcon,
  Transcribe as TranscribeIcon,
  AutoAwesome as PromptsIcon,
  Share as ShareIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions, Message } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import { getApiUrl, getWsUrl, API_ENDPOINTS } from '../config/api';
import MessageRenderer from '../components/MessageRenderer';
import { useNavigate } from 'react-router-dom';
import TranscriptionModal from '../components/TranscriptionModal';
import ModelSelector from '../components/ModelSelector';
import MessageNavigationBar from '../components/MessageNavigationBar';
import ShareConfirmDialog from '../components/ShareConfirmDialog';
import ChatInputBar from '../components/ChatInputBar';
import VoiceChatDialog from '../components/VoiceChatDialog';
import { getSidebarPanelBackground } from '../constants/sidebarPanelColor';

interface UnifiedChatPageProps {
  isDarkMode: boolean;
  sidebarOpen?: boolean;
}

interface ModelWindow {
  id: string;
  selectedModel: string;
  response: string;
  isStreaming: boolean;
  error?: boolean;
}

interface AgentStatus {
  is_initialized: boolean;
  mode: string;
  available_agents: number;
  orchestrator_active: boolean;
}

export default function UnifiedChatPage({ isDarkMode, sidebarOpen = true }: UnifiedChatPageProps) {
  const navigate = useNavigate();
  
  // Состояние для правой панели
  const [rightSidebarOpen, setRightSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('rightSidebarOpen');
    return saved !== null ? saved === 'true' : false;
  });
  const [rightSidebarHidden, setRightSidebarHidden] = useState(() => {
    const saved = localStorage.getItem('rightSidebarHidden');
    return saved !== null ? saved === 'true' : false;
  });
  const [rightSidebarPanelBg, setRightSidebarPanelBg] = useState(() => getSidebarPanelBackground());

  useEffect(() => {
    const onColorChanged = () => setRightSidebarPanelBg(getSidebarPanelBackground());
    window.addEventListener('sidebarColorChanged', onColorChanged);
    return () => window.removeEventListener('sidebarColorChanged', onColorChanged);
  }, []);

  // Состояние для отображения выбора модели
  const [showModelSelectorInSettings, setShowModelSelectorInSettings] = useState(() => {
    const saved = localStorage.getItem('show_model_selector_in_settings');
    return saved !== null ? saved === 'true' : false;
  });

  // Состояние для панели с диалогами (навигация по сообщениям)
  const [showDialoguesPanel, setShowDialoguesPanel] = useState(() => {
    const saved = localStorage.getItem('show_dialogues_panel');
    return saved !== null ? saved === 'true' : true;
  });
  
  // Слушаем изменения настроек
  useEffect(() => {
    const handleSettingsChange = () => {
      const savedModel = localStorage.getItem('show_model_selector_in_settings');
      setShowModelSelectorInSettings(savedModel !== null ? savedModel === 'true' : false);
      const savedPanel = localStorage.getItem('show_dialogues_panel');
      setShowDialoguesPanel(savedPanel !== null ? savedPanel === 'true' : true);
    };
    
    window.addEventListener('interfaceSettingsChanged', handleSettingsChange);
    return () => window.removeEventListener('interfaceSettingsChanged', handleSettingsChange);
  }, []);

  // Сохранение состояния правой боковой панели
  useEffect(() => {
    localStorage.setItem('rightSidebarOpen', String(rightSidebarOpen));
  }, [rightSidebarOpen]);

  useEffect(() => {
    localStorage.setItem('rightSidebarHidden', String(rightSidebarHidden));
  }, [rightSidebarHidden]);
  
  // Состояние для модального окна транскрибации
  const [transcriptionModalOpen, setTranscriptionModalOpen] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptionResult, setTranscriptionResult] = useState('');
  
  // Состояние для текстового чата
  const [inputMessage, setInputMessage] = useState('');
  const [showCopyAlert, setShowCopyAlert] = useState(false);
  
  // Состояние для редактирования сообщений
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingMessage, setEditingMessage] = useState<Message | null>(null);
  const [editText, setEditText] = useState('');
  
  const [showVoiceDialog, setShowVoiceDialog] = useState(false);

  
  // Состояние для документов
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [query, setQuery] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [isQuerying, setIsQuerying] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [queryResponse, setQueryResponse] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<Array<{
    name: string;
    size: number;
    type: string;
    uploadDate: string;
  }>>([]);
  const [showDocumentDialog, setShowDocumentDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  
  // Состояние для режима "Поделиться"
  const [shareMode, setShareMode] = useState(false);
  const [selectedMessages, setSelectedMessages] = useState<Set<string>>(new Set());
  const [isCreatingShareLink, setIsCreatingShareLink] = useState(false);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageRefs = useRef<(HTMLDivElement | null)[]>([]);
  
  // Context и Socket
  const { state } = useAppContext();
  const { 
    clearMessages, 
    showNotification, 
    setSpeaking, 
    setRecording, 
    updateMessage, 
    getCurrentMessages, 
    getCurrentChat,
    createChat,
    setCurrentChat,
    updateChatTitle,
    getProjectById,
  } = useAppActions();
  const { sendMessage, regenerateResponse, isConnected, isConnecting, stopGeneration, socket, onMultiLLMEvent, offMultiLLMEvent } = useSocket();

  // Получаем текущий чат и сообщения
  const currentChat = getCurrentChat();
  const messages = getCurrentMessages();
  const project = currentChat?.projectId ? getProjectById(currentChat.projectId) : null;

  // Сбрасываем поле ввода при переключении между чатами, чтобы черновик не "дублировался"
  useEffect(() => {
    setInputMessage('');
  }, [state.currentChatId]);

  // Стабильный обработчик для MessageRenderer (НЕ меняется при ререндерах!)
  const handleSendMessageFromRendererRef = useRef<((prompt: string) => void) | null>(null);
  
  // Обновляем ref при изменении зависимостей, но НЕ создаем новую функцию
  useEffect(() => {
    handleSendMessageFromRendererRef.current = (prompt: string) => {
      if (currentChat && isConnected && !state.isLoading) {
        sendMessage(prompt, currentChat.id);
      }
    };
  }, [currentChat, isConnected, state.isLoading, sendMessage]);
  
  // Создаем стабильную функцию ОДИН РАЗ (никогда не меняется!)
  const handleSendMessageFromRenderer = useCallback((prompt: string) => {
    handleSendMessageFromRendererRef.current?.(prompt);
  }, []); // ← Пустой массив! Функция НЕ пересоздается!
  
  // Состояние для режима multi-llm
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [availableModels, setAvailableModels] = useState<Array<{name: string; path: string; size_mb?: number}>>([]);
  const [modelWindows, setModelWindows] = useState<ModelWindow[]>([
    { id: '1', selectedModel: '', response: '', isStreaming: false }
  ]);
  const [conversationHistory, setConversationHistory] = useState<Array<{
    userMessage: string;
    responses: Array<{model: string; content: string; error?: boolean}>;
    timestamp: string;
  }>>([]);
  const currentMultiLLMRequestRef = useRef<string | null>(null);

  // Убираем автоматическое создание чатов - чаты создаются только по кнопке

  // Загружаем настройки интерфейса
  const [interfaceSettings, setInterfaceSettings] = useState(() => {
    const savedAutoTitle = localStorage.getItem('auto_generate_titles');
    const savedLargeTextAsFile = localStorage.getItem('large_text_as_file');
    const savedUserNoBorder = localStorage.getItem('user_no_border');
    const savedAssistantNoBorder = localStorage.getItem('assistant_no_border');
    const savedLeftAlignMessages = localStorage.getItem('left_align_messages');
    const savedWidescreenMode = localStorage.getItem('widescreen_mode');
    const savedShowUserName = localStorage.getItem('show_user_name');
    const savedEnableNotification = localStorage.getItem('enable_notification');
    const savedChatInputStyle = localStorage.getItem('chat_input_style');
    return {
      autoGenerateTitles: savedAutoTitle !== null ? savedAutoTitle === 'true' : true,
      largeTextAsFile: savedLargeTextAsFile !== null ? savedLargeTextAsFile === 'true' : false,
      userNoBorder: savedUserNoBorder !== null ? savedUserNoBorder === 'true' : false,
      assistantNoBorder: savedAssistantNoBorder !== null ? savedAssistantNoBorder === 'true' : false,
      leftAlignMessages: savedLeftAlignMessages !== null ? savedLeftAlignMessages === 'true' : false,
      widescreenMode: savedWidescreenMode !== null ? savedWidescreenMode === 'true' : false,
      showUserName: savedShowUserName !== null ? savedShowUserName === 'true' : false,
      enableNotification: savedEnableNotification !== null ? savedEnableNotification === 'true' : false,
      chatInputStyle: (savedChatInputStyle as 'compact' | 'classic') || 'compact',
    };
  });

  // Слушаем изменения настроек интерфейса в localStorage
  useEffect(() => {
    const handleStorageChange = () => {
      const savedAutoTitle = localStorage.getItem('auto_generate_titles');
      const savedLargeTextAsFile = localStorage.getItem('large_text_as_file');
      const savedUserNoBorder = localStorage.getItem('user_no_border');
      const savedAssistantNoBorder = localStorage.getItem('assistant_no_border');
      const savedLeftAlignMessages = localStorage.getItem('left_align_messages');
      const savedWidescreenMode = localStorage.getItem('widescreen_mode');
      const savedShowUserName = localStorage.getItem('show_user_name');
      const savedEnableNotification = localStorage.getItem('enable_notification');
      const savedChatInputStyle = localStorage.getItem('chat_input_style');
      setInterfaceSettings({
        autoGenerateTitles: savedAutoTitle !== null ? savedAutoTitle === 'true' : true,
        largeTextAsFile: savedLargeTextAsFile !== null ? savedLargeTextAsFile === 'true' : false,
        userNoBorder: savedUserNoBorder !== null ? savedUserNoBorder === 'true' : false,
        assistantNoBorder: savedAssistantNoBorder !== null ? savedAssistantNoBorder === 'true' : false,
        leftAlignMessages: savedLeftAlignMessages !== null ? savedLeftAlignMessages === 'true' : false,
        widescreenMode: savedWidescreenMode !== null ? savedWidescreenMode === 'true' : false,
        showUserName: savedShowUserName !== null ? savedShowUserName === 'true' : false,
        enableNotification: savedEnableNotification !== null ? savedEnableNotification === 'true' : false,
        chatInputStyle: (savedChatInputStyle as 'compact' | 'classic') || 'compact',
      });
    };

    window.addEventListener('storage', handleStorageChange);
    // Также проверяем изменения в том же окне через кастомное событие
    window.addEventListener('interfaceSettingsChanged', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('interfaceSettingsChanged', handleStorageChange);
    };
  }, []);

  // Автоматически обновляем название чата на основе первого сообщения пользователя
  useEffect(() => {
    if (currentChat && messages.length === 1 && interfaceSettings.autoGenerateTitles) {
      const firstMessage = messages[0];
      if (firstMessage.role === 'user' && currentChat.title === 'Новый чат') {
        const title = firstMessage.content.length > 50 
          ? firstMessage.content.substring(0, 50) + '...'
          : firstMessage.content;
        updateChatTitle(currentChat.id, title);
      }
    }
  }, [currentChat, messages, updateChatTitle, interfaceSettings.autoGenerateTitles]);

  // Убираем автоматическую остановку генерации при смене чата
  // Генерация должна происходить в том чате, где был задан вопрос

  // Состояние для кнопки "Прочесть вслух"
  const [isSpeaking, setIsSpeaking] = useState(false);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const [voiceSettingsTTS] = useState(() => ({
    voice_id: localStorage.getItem('voice_id') || 'ru',
    speech_rate: parseFloat(localStorage.getItem('speech_rate') || '1.0'),
    voice_speaker: localStorage.getItem('voice_speaker') || 'baya',
  }));

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Автоматический фокус на поле ввода при загрузке
  useEffect(() => {
    const timer = setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 300);
    
    return () => clearTimeout(timer);
  }, []);

  // Автоматический фокус на поле ввода при переключении чатов
  useEffect(() => {
    if (currentChat?.id) {
      const timer = setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 200);
      
      return () => clearTimeout(timer);
    }
  }, [currentChat?.id]);

  // Функция для воспроизведения звукового оповещения
  const playNotificationSound = useCallback(() => {
    if (!interfaceSettings.enableNotification) return;
    
    try {
      // Создаем простой звуковой сигнал через Web Audio API
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.value = 800; // Частота в Гц
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.3);
    } catch (error) {
    }
  }, [interfaceSettings.enableNotification]);

  // Отслеживаем завершение генерации сообщений для воспроизведения звука
  const prevStreamingRef = useRef<boolean>(false);
  useEffect(() => {
    const hasStreamingMessages = messages.some(msg => msg.isStreaming);
    const hasStreamingMultiLLM = modelWindows.some(w => w.isStreaming);
    const isCurrentlyStreaming = hasStreamingMessages || hasStreamingMultiLLM;
    
    // Если стриминг только что завершился (был true, стал false), воспроизводим звук
    if (prevStreamingRef.current && !isCurrentlyStreaming) {
      playNotificationSound();
    }
    
    prevStreamingRef.current = isCurrentlyStreaming;
  }, [messages, modelWindows, playNotificationSound]);

  // Фокус на поле ввода при загрузке
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Загружаем статус агента и модели при инициализации
  useEffect(() => {
    const loadAgentStatus = async () => {
      try {
        const response = await fetch(`${getApiUrl('/api/agent/status')}`);
        if (response.ok) {
          const data = await response.json();
          // Обновляем ТОЛЬКО если данные изменились (предотвращаем лишние ререндеры)
          setAgentStatus(prev => {
            if (JSON.stringify(prev) !== JSON.stringify(data)) {
              return data;
            }
            return prev;
          });
        }
      } catch (error) {
      }
    };

    const loadAvailableModels = async () => {
      try {
        const response = await fetch(`${getApiUrl('/api/models/available')}`);
        if (response.ok) {
          const data = await response.json();
          const newModels = data.models || [];
          // Обновляем ТОЛЬКО если данные изменились
          setAvailableModels(prev => {
            if (JSON.stringify(prev) !== JSON.stringify(newModels)) {
              return newModels;
            }
            return prev;
          });
        }
      } catch (error) {
      }
    };

    loadAgentStatus();
    loadAvailableModels();
    
    // Периодически обновляем статус, но реже (30 сек вместо 5)
    // Это предотвращает лишние ререндеры
    const interval = setInterval(() => {
      loadAgentStatus();
      // Обновляем модели только в режиме multi-llm
      if (agentStatus?.mode === 'multi-llm') {
        loadAvailableModels();
      }
    }, 30000); // Увеличено с 5000 до 30000 (30 секунд)
    
    return () => clearInterval(interval);
  }, [agentStatus?.mode]);

  // Загружаем модели отдельно при переключении на режим multi-llm
  useEffect(() => {
    if (agentStatus?.mode === 'multi-llm') {
      const loadAvailableModels = async () => {
        try {
          const response = await fetch(`${getApiUrl('/api/models/available')}`);
          if (response.ok) {
            const data = await response.json();
            setAvailableModels(data.models || []);
          } else {
            
          }
        } catch (error) {
        }
      };
      
      loadAvailableModels();
    }
  }, [agentStatus?.mode]);

  // Подписка на событие остановки генерации и завершения генерации
  useEffect(() => {
    if (!socket) return;
    
    const handleGenerationStopped = () => {
      // Обновляем состояние всех окон моделей - останавливаем стриминг
      setModelWindows(prev => prev.map(w => ({ ...w, isStreaming: false })));
      
      // Также обновляем состояние сообщений в истории
      setConversationHistory(prev => {
        if (prev.length === 0) return prev;
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        if (updated[lastIndex]) {
          updated[lastIndex] = {
            ...updated[lastIndex],
            responses: updated[lastIndex].responses.map(r => ({ ...r, isStreaming: false }))
          };
        }
        return updated;
      });
    };
    
    const handleChatComplete = (data: any) => {
      // Когда генерация завершена, обновляем состояние всех окон моделей
      
      setModelWindows(prev => {
        const updated = prev.map(w => ({ ...w, isStreaming: false }));
        
        return updated;
      });
      
      // Также обновляем состояние сообщений в истории
      setConversationHistory(prev => {
        if (prev.length === 0) return prev;
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        if (updated[lastIndex]) {
          updated[lastIndex] = {
            ...updated[lastIndex],
            responses: updated[lastIndex].responses.map(r => ({ ...r, isStreaming: false }))
          };
        }
        return updated;
      });
    };
    
    socket.on('generation_stopped', handleGenerationStopped);
    socket.on('chat_complete', handleChatComplete);
    
    
    
    return () => {
      
      socket.off('generation_stopped', handleGenerationStopped);
      socket.off('chat_complete', handleChatComplete);
    };
  }, [socket]);

  // Подписка на события Socket.IO для режима multi-llm
  useEffect(() => {
    if (agentStatus?.mode !== 'multi-llm' || !socket || !onMultiLLMEvent || !offMultiLLMEvent) return;
    
    const handleMultiLLMStart = (data: any) => {
      
      currentMultiLLMRequestRef.current = new Date().toISOString();
      
      // Устанавливаем isStreaming: true для соответствующей модели
      const modelName = data.model || '';
      if (modelName) {
        setModelWindows(prev => prev.map(w => 
          w.selectedModel === modelName 
            ? { ...w, isStreaming: true, error: false }
            : w
        ));
      }
    };

    const handleMultiLLMChunk = (data: any) => {
      
      const modelName = data.model || 'unknown';
      const accumulated = data.accumulated || '';
      
      // Обновляем ответ в истории для текущего запроса
      setConversationHistory(prev => {
        if (prev.length === 0) return prev;
        const lastIndex = prev.length - 1;
        const updated = [...prev];
        const existingResponseIndex = updated[lastIndex].responses.findIndex(r => r.model === modelName);
        
        if (existingResponseIndex >= 0) {
          updated[lastIndex].responses[existingResponseIndex] = {
            ...updated[lastIndex].responses[existingResponseIndex],
            content: accumulated
          };
        } else {
          updated[lastIndex].responses.push({
            model: modelName,
            content: accumulated
          });
        }
        
        return updated;
      });
      
      // Обновляем состояние окна для потоковой генерации
      setModelWindows(prev => prev.map(w => 
        w.selectedModel === modelName 
          ? { ...w, response: accumulated, isStreaming: true }
          : w
      ));
    };

    const handleMultiLLMComplete = (data: any) => {
      
      const modelName = data.model || 'unknown';
      const response = data.response || '';
      const hasError = data.error || false;
      
      // Обновляем ответ в истории
      setConversationHistory(prev => {
        if (prev.length === 0) return prev;
        const lastIndex = prev.length - 1;
        const updated = [...prev];
        const existingResponseIndex = updated[lastIndex].responses.findIndex(r => r.model === modelName);
        
        if (existingResponseIndex >= 0) {
          updated[lastIndex].responses[existingResponseIndex] = {
            model: modelName,
            content: response,
            error: hasError
          };
        } else {
          updated[lastIndex].responses.push({
            model: modelName,
            content: response,
            error: hasError
          });
        }
        
        return updated;
      });
      
      // Обновляем состояние окна - завершаем стриминг
      setModelWindows(prev => prev.map(w => 
        w.selectedModel === modelName 
          ? { ...w, response, isStreaming: false, error: hasError }
          : w
      ));
    };

    // Подписываемся на события
    onMultiLLMEvent('multi_llm_start', handleMultiLLMStart);
    onMultiLLMEvent('multi_llm_chunk', handleMultiLLMChunk);
    onMultiLLMEvent('multi_llm_complete', handleMultiLLMComplete);

    return () => {
      // Отписываемся от событий
      if (offMultiLLMEvent) {
        offMultiLLMEvent('multi_llm_start', handleMultiLLMStart);
        offMultiLLMEvent('multi_llm_chunk', handleMultiLLMChunk);
        offMultiLLMEvent('multi_llm_complete', handleMultiLLMComplete);
      }
    };
  }, [agentStatus?.mode, socket, onMultiLLMEvent, offMultiLLMEvent]);

  // Загружаем список документов при инициализации
  useEffect(() => {
    const loadDocuments = async () => {
      try {
        const response = await fetch(getApiUrl('/api/documents'));
        if (response.ok) {
          const result: any = await response.json();
          if (result.success && result.documents) {
            // Преобразуем список имен файлов в объекты файлов
            const files = result.documents.map((filename: string) => ({
              name: filename,
              size: 0, // Размер не сохраняется на бэкенде
              type: 'application/octet-stream', // Тип не сохраняется на бэкенде
              uploadDate: new Date().toISOString(),
            }));
            setUploadedFiles(files);
          }
        }
      } catch (error) {
        
      }
    };

    loadDocuments();
  }, []);


  // ================================
  // ФУНКЦИИ ТЕКСТОВОГО ЧАТА
  // ================================

  // ================================
  // ФУНКЦИИ ДЛЯ РЕЖИМА MULTI-LLM
  // ================================
  
  const addModelWindow = (): void => {
    if (modelWindows.length >= 4) {
      showNotification('warning', 'Можно добавить максимум 4 модели');
      return;
    }
    const newId = String(modelWindows.length + 1);
    setModelWindows([...modelWindows, { id: newId, selectedModel: '', response: '', isStreaming: false }]);
  };

  const removeModelWindow = (id: string): void => {
    if (modelWindows.length <= 1) {
      showNotification('warning', 'Должна остаться хотя бы одна модель');
      return;
    }
    setModelWindows(modelWindows.filter(w => w.id !== id));
  };

  const updateModelWindow = (id: string, updates: Partial<ModelWindow>): void => {
    setModelWindows(modelWindows.map(w => w.id === id ? { ...w, ...updates } : w));
  };

  const getSelectedModels = (): string[] => {
    return modelWindows.map(w => w.selectedModel).filter(m => m !== '');
  };

  const handleModelSelect = (windowId: string, modelName: string): void => {
    const selectedModels = getSelectedModels();
    
    // Проверяем, не выбрана ли эта модель в другом окне
    if (selectedModels.includes(modelName) && modelWindows.find(w => w.id === windowId)?.selectedModel !== modelName) {
      showNotification('error', 'Эта модель уже выбрана в другом окне');
      return;
    }
    
    updateModelWindow(windowId, { selectedModel: modelName });
  };

  const handleSendMessageMultiLLM = async (): Promise<void> => {
    if (!inputMessage.trim() || !isConnected) {
      return;
    }

    const selectedModels = getSelectedModels();
    if (selectedModels.length === 0) {
      showNotification('error', 'Выберите хотя бы одну модель');
      return;
    }

    // Сохраняем сообщение пользователя в историю
    setConversationHistory([
      ...conversationHistory,
      {
        userMessage: inputMessage.trim(),
        responses: [],
        timestamp: new Date().toISOString()
      }
    ]);

    // Устанавливаем состояние генерации для всех выбранных окон
    modelWindows.forEach(window => {
      if (window.selectedModel) {
        updateModelWindow(window.id, { response: '', isStreaming: true, error: false });
      }
    });

    // Отправляем запрос на сервер с выбранными моделями
    try {
      // Устанавливаем модели в оркестраторе
      const response = await fetch(`${getApiUrl('/api/agent/multi-llm/models')}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: selectedModels }),
      });

      if (!response.ok) {
        throw new Error('Не удалось установить модели');
      }

      // Отправляем сообщение через Socket.IO
      // Сообщение будет обработано через SocketContext, который отследит режим multi-llm
      // и разошлет запросы ко всем выбранным моделям
      
      // Временно используем обычный sendMessage, но нужно будет модифицировать SocketContext
      // для работы с выбранными моделями напрямую в чате
      if (currentChat) {
        sendMessage(inputMessage.trim(), currentChat.id);
      }
      
      setInputMessage('');
      
      // Возвращаем фокус на поле ввода
      setTimeout(() => {
        inputRef.current?.focus();
      }, 10);
    } catch (error) {
      
      showNotification('error', 'Ошибка отправки сообщения');
    }
  };

  const handleSendMessage = (): void => {
    // Если режим multi-llm, используем специальную функцию
    if (agentStatus?.mode === 'multi-llm') {
      handleSendMessageMultiLLM();
      return;
    }

    if (!inputMessage.trim() || !isConnected || state.isLoading) {
      if (!isConnected) {
        showNotification('error', 'Нет соединения с сервером. Попробуйте переподключиться.');
      }
      return;
    }
    
    // Автоматически создаем новый чат, если его нет
    if (!currentChat) {
      const newChatId = createChat('Новый чат');
      setCurrentChat(newChatId);
      const messageText = inputMessage.trim();
      setInputMessage('');
      setTimeout(() => {
        sendMessage(messageText, newChatId);
        inputRef.current?.focus();
      }, 50);
      return;
    }

    sendMessage(inputMessage.trim(), currentChat.id);
    setInputMessage('');
    
    // Возвращаем фокус на поле ввода
    setTimeout(() => {
      inputRef.current?.focus();
    }, 10);
  };

  const handleKeyPress = (event: React.KeyboardEvent): void => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  // Обработчик вставки текста
  const handlePaste = async (event: React.ClipboardEvent<HTMLDivElement>): Promise<void> => {
    if (!interfaceSettings.largeTextAsFile) {
      return; // Если настройка выключена, используем стандартное поведение
    }

    const pastedText = event.clipboardData.getData('text');
    
    // Определяем, что считается "большим текстом" (например, больше 1000 символов)
    const LARGE_TEXT_THRESHOLD = 1000;
    
    if (pastedText.length > LARGE_TEXT_THRESHOLD) {
      event.preventDefault(); // Предотвращаем стандартную вставку
      
      try {
        // Создаем текстовый файл из вставленного текста
        const blob = new Blob([pastedText], { type: 'text/plain' });
        const fileName = `pasted_text_${Date.now()}.txt`;
        const file = new File([blob], fileName, { type: 'text/plain' });
        
        // Загружаем файл через handleFileUpload
        await handleFileUpload(file);
        
        // Очищаем поле ввода
        setInputMessage('');
        
        showNotification('success', 'Большой текст вставлен как файл');
      } catch (error) {
        
        showNotification('error', 'Ошибка при создании файла из вставленного текста');
        // В случае ошибки разрешаем стандартную вставку
      }
    }
  };

  const handleCopyMessage = async (content: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(content);
      setShowCopyAlert(true);
    } catch (error) {
      showNotification('error', 'Не удалось скопировать текст');
    }
  };

  // Функция для перегенерации ответа LLM
  const handleRegenerate = (message: Message, customUserMessage?: string): void => {
    if (!currentChat || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }

    // Находим индекс текущего сообщения
    const messageIndex = messages.findIndex(m => m.id === message.id);
    if (messageIndex === -1) {
      showNotification('error', 'Сообщение не найдено');
      return;
    }

    // Ищем предыдущее сообщение пользователя
    let userMessage: Message | null = null;
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMessage = messages[i];
        break;
      }
    }

    if (!userMessage) {
      showNotification('error', 'Не найдено предыдущее сообщение пользователя');
      return;
    }
    
    // Используем customUserMessage если передан, иначе берем из userMessage
    const userMessageContent = customUserMessage || userMessage.content;

    // Сохраняем текущий ответ в альтернативные ответы
    const currentContent = message.content;
    let existingAlternatives = message.alternativeResponses || [];
    const currentIndex = message.currentResponseIndex ?? 0;
    
    // Если альтернативных ответов еще нет, инициализируем массив с текущим ответом
    if (existingAlternatives.length === 0) {
      existingAlternatives = [currentContent];
    } else {
      // Обновляем текущий вариант в альтернативных ответах, если он изменился
      const updated = [...existingAlternatives];
      if (currentIndex < updated.length) {
        // Обновляем текущий вариант
        updated[currentIndex] = currentContent;
      } else {
        // Если индекс выходит за границы, добавляем текущий ответ
        updated.push(currentContent);
      }
      existingAlternatives = updated;
    }
    
    // Устанавливаем новый индекс для нового ответа (будет последним)
    const newIndex = existingAlternatives.length;
    
    // Добавляем пустое место для нового ответа (будет заполнено при генерации)
    const updatedAlternatives = [...existingAlternatives, ''];
    
    // Обновляем сообщение с альтернативными ответами и новым индексом
    // Не обнуляем content, оставляем текущий
    updateMessage(
      currentChat.id,
      message.id,
      currentContent, // Оставляем текущий контент, не обнуляем
      true, // isStreaming - начинаем стриминг
      undefined, // multiLLMResponses
      updatedAlternatives,
      newIndex // Новый индекс для нового ответа
    );

    // Вызываем перегенерацию без создания нового сообщения пользователя
    // Передаем updatedAlternatives и newIndex для сохранения в SocketContext ref
    regenerateResponse(userMessageContent, message.id, currentChat.id, updatedAlternatives, newIndex);
  };

  // Функция для открытия диалога редактирования
  const handleEditClick = (message: Message): void => {
    setEditingMessage(message);
    setEditText(message.content);
    setEditDialogOpen(true);
  };

  // Функция для сохранения отредактированного сообщения
  const handleSaveEdit = async (): Promise<void> => {
    if (!editingMessage || !currentChat || !editText.trim()) {
      return;
    }

    const trimmedContent = editText.trim();
    
    // Обновляем сообщение в локальном состоянии
    updateMessage(currentChat.id, editingMessage.id, trimmedContent);
    
    // Сохраняем в MongoDB через API
    try {
      const response = await fetch(
        `${getApiUrl(API_ENDPOINTS.UPDATE_MESSAGE)}/${currentChat.id}/${editingMessage.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            content: trimmedContent,
            old_content: editingMessage.content  // Передаем старое содержимое для поиска
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errorData.detail || 'Ошибка при сохранении сообщения');
      }
      
      showNotification('success', 'Сообщение обновлено и сохранено в базе данных');
    } catch (error) {
      
      showNotification('warning', 'Сообщение обновлено локально, но не сохранено в базе данных');
    }
    
    setEditDialogOpen(false);
    setEditingMessage(null);
    setEditText('');
  };

  // Функция для сохранения и отправки на повторную генерацию (только для сообщений пользователя)
  const handleSaveAndSend = async (): Promise<void> => {
    if (!editingMessage || !currentChat || !editText.trim() || !isConnected) {
      if (!isConnected) {
        showNotification('error', 'Нет соединения с сервером');
      }
      return;
    }

    const trimmedContent = editText.trim();
    
    // Обновляем сообщение пользователя в локальном состоянии
    updateMessage(currentChat.id, editingMessage.id, trimmedContent);
    
    // Сохраняем в MongoDB через API
    try {
      const response = await fetch(
        `${getApiUrl(API_ENDPOINTS.UPDATE_MESSAGE)}/${currentChat.id}/${editingMessage.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            content: trimmedContent,
            old_content: editingMessage.content  // Передаем старое содержимое для поиска
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errorData.detail || 'Ошибка при сохранении сообщения');
      }
    } catch (error) {
      
      showNotification('warning', 'Сообщение обновлено локально, но не сохранено в базе данных');
    }
    
    // Находим следующее сообщение LLM после этого сообщения пользователя
    const messageIndex = messages.findIndex(m => m.id === editingMessage.id);
    if (messageIndex !== -1) {
      // Ищем следующее сообщение LLM
      for (let i = messageIndex + 1; i < messages.length; i++) {
        if (messages[i].role === 'assistant') {
          // Найдено сообщение LLM - перегенерируем его с обновленным текстом пользователя
          handleRegenerate(messages[i], trimmedContent);
          break;
        }
      }
    }
    
    setEditDialogOpen(false);
    setEditingMessage(null);
    setEditText('');
    showNotification('success', 'Сообщение обновлено и отправлено на перегенерацию');
  };

  // Функция для отмены редактирования
  const handleCancelEdit = (): void => {
    setEditDialogOpen(false);
    setEditingMessage(null);
    setEditText('');
  };

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Получаем данные пользователя
  const { user } = useAuth();
  
  // Функция для определения приветствия по времени суток (Московское время)
  const getGreeting = (): string => {
    const now = new Date();
    const moscowTime = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Moscow"}));
    const hour = moscowTime.getHours();
    
    // Определяем имя пользователя для приветствия
    const userName = user?.full_name || user?.username || "";
    const nameToShow = userName ? `, ${userName}` : "";
    
    if (hour >= 5 && hour < 12) {
      return `Доброе утро${nameToShow}`;
    } else if (hour >= 12 && hour < 18) {
      return `Добрый день${nameToShow}`;
    } else if (hour >= 18 && hour < 22) {
      return `Добрый вечер${nameToShow}`;
    } else {
      return `Доброй ночи${nameToShow}`;
    }
  };

  // ================================
  // TTS ДЛЯ КНОПКИ "ПРОЧЕСТЬ ВСЛУХ"
  // ================================

  const synthesizeSpeech = async (text: string) => {
    if (!text.trim()) return;
    if (currentAudioRef.current) {
      currentAudioRef.current.pause(); currentAudioRef.current.src = ''; currentAudioRef.current = null;
    }
    setIsSpeaking(true);
    try {
      const response = await fetch(getApiUrl(API_ENDPOINTS.VOICE_SYNTHESIZE), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          voice_id: voiceSettingsTTS.voice_id,
          voice_speaker: voiceSettingsTTS.voice_speaker,
          speech_rate: voiceSettingsTTS.speech_rate,
        }),
      });
      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        currentAudioRef.current = audio;
        audio.onended = () => {
          setIsSpeaking(false); URL.revokeObjectURL(audioUrl); currentAudioRef.current = null;
        };
        audio.onerror = () => {
          setIsSpeaking(false); showNotification('error', 'Ошибка воспроизведения речи');
          URL.revokeObjectURL(audioUrl); currentAudioRef.current = null;
        };
        await audio.play();
      } else {
        setIsSpeaking(false);
        showNotification('error', 'Ошибка синтеза речи');
      }
    } catch {
      setIsSpeaking(false);
      showNotification('error', 'Ошибка синтеза речи');
    }
  };

  // ================================
  // ФУНКЦИИ РАБОТЫ С ДОКУМЕНТАМИ
  // ================================

  const handleFileUpload = async (file: File): Promise<void> => {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'text/plain',
      'image/jpeg',
      'image/jpg',
      'image/png',
      'image/webp',
    ];

    if (!allowedTypes.includes(file.type)) {
      showNotification('error', 'Поддерживаются только файлы PDF, Word (.docx), Excel (.xlsx), TXT и изображения (JPG, PNG, WebP)');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      showNotification('error', 'Размер файла не должен превышать 50MB');
      return;
    }

    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`${getApiUrl('/api/documents/upload')}`, {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        await response.json();
        showNotification('success', `Документ "${file.name}" успешно загружен. Теперь вы можете задать вопрос по нему в чате.`);
        
        // Обновляем список документов с бэкенда (это основной источник истины)
        try {
          const docsResponse = await fetch(getApiUrl('/api/documents'));
          if (docsResponse.ok) {
            const docsResult: any = await docsResponse.json();
            if (docsResult.success && docsResult.documents) {
              const files = docsResult.documents.map((filename: string) => ({
                name: filename,
                size: 0,
                type: 'application/octet-stream',
                uploadDate: new Date().toISOString(),
              }));
              setUploadedFiles(files);
              
            } else {
              // Если список пустой, добавляем загруженный файл
              setUploadedFiles(prev => {
                const exists = prev.some(f => f.name === file.name);
                if (!exists) {
                  return [...prev, {
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    uploadDate: new Date().toISOString(),
                  }];
                }
                return prev;
              });
            }
          } else {
            // Fallback: добавляем файл в список, если не удалось получить список с бэкенда
            setUploadedFiles(prev => {
              const exists = prev.some(f => f.name === file.name);
              if (!exists) {
                return [...prev, {
                  name: file.name,
                  size: file.size,
                  type: file.type,
                  uploadDate: new Date().toISOString(),
                }];
              }
              return prev;
            });
          }
        } catch (error) {
          
          // Fallback: добавляем файл в список, если произошла ошибка
          setUploadedFiles(prev => {
            const exists = prev.some(f => f.name === file.name);
            if (!exists) {
              return [...prev, {
                name: file.name,
                size: file.size,
                type: file.type,
                uploadDate: new Date().toISOString(),
              }];
            }
            return prev;
          });
        }
        
        // Закрываем диалог загрузки документов после успешной загрузки
        setShowDocumentDialog(false);
        
        // Очищаем input файла, чтобы можно было повторно загрузить тот же файл
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        
      } else {
        const error = await response.json();
        showNotification('error', error.detail || 'Ошибка при загрузке документа');
      }
    } catch (error) {
      
      showNotification('error', 'Ошибка при загрузке файла');
            } finally {
      setIsUploading(false);
    }
  };

  const handleFileDelete = async (fileName: string): Promise<void> => {
    try {
      const response = await fetch(`${getApiUrl(`/api/documents/${encodeURIComponent(fileName)}`)}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        const result: any = await response.json();
        // Обновляем список документов с бэкенда
        if (result.remaining_documents) {
          const files = result.remaining_documents.map((filename: string) => ({
            name: filename,
            size: 0,
            type: 'application/octet-stream',
            uploadDate: new Date().toISOString(),
          }));
          setUploadedFiles(files);
        } else {
          setUploadedFiles(prev => prev.filter(file => file.name !== fileName));
        }
        showNotification('success', `Документ "${fileName}" удален`);
        
        // Очищаем input файла после удаления
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        
      } else {
        const error = await response.json();
        showNotification('error', error.detail || 'Ошибка при удалении документа');
      }
    } catch (error) {
      
      showNotification('error', 'Ошибка при удалении файла');
    }
  };

  const handleDragOver = (e: React.DragEvent): void => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent): void => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent): void => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
    // Очищаем input файла, чтобы можно было повторно загрузить тот же файл
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleGenerateReport = async (): Promise<void> => {
    if (uploadedFiles.length === 0) {
      showNotification('warning', 'Нет загруженных документов для генерации отчета');
      return;
    }

    try {
      showNotification('info', 'Генерация отчета...');
      
      // Скачиваем отчет напрямую
      const response = await fetch(getApiUrl('/api/documents/report/download'));
      
      if (response.ok) {
        // Получаем blob для скачивания
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Получаем имя файла из заголовка Content-Disposition или используем дефолтное
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'confidence_report.xlsx'; // Дефолтное расширение - .xlsx
        if (contentDisposition) {
          // Пробуем разные форматы Content-Disposition
          // Формат: filename*=UTF-8''filename.xlsx
          const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
          if (utf8Match) {
            filename = decodeURIComponent(utf8Match[1]);
          } else {
            // Формат: filename="filename.xlsx" или filename=filename.xlsx
            const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (filenameMatch) {
              filename = filenameMatch[1].replace(/['"]/g, '');
            }
          }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('success', 'Отчет успешно сгенерирован и скачан');
      } else {
        const error = await response.json();
        showNotification('error', error.detail || 'Ошибка при генерации отчета');
      }
    } catch (error) {
      
      showNotification('error', 'Ошибка при генерации отчета');
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>): void => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = (): void => {
    setAnchorEl(null);
  };

  const handleClearChat = (): void => {
    if (currentChat) {
      clearMessages(currentChat.id);
    }
    handleMenuClose();
  };

  const handleStopGeneration = (): void => {
    // Останавливаем генерацию через WebSocket
    stopGeneration();
    
    // Обновляем состояние всех окон моделей - останавливаем стриминг
    setModelWindows(prev => prev.map(w => ({ ...w, isStreaming: false })));
    
    // Также обновляем состояние сообщений в истории
    setConversationHistory(prev => {
      if (prev.length === 0) return prev;
      const updated = [...prev];
      const lastIndex = updated.length - 1;
      if (updated[lastIndex]) {
        updated[lastIndex] = {
          ...updated[lastIndex],
          responses: updated[lastIndex].responses.map(r => ({ ...r, isStreaming: false }))
        };
      }
      return updated;
    });
    
    showNotification('info', 'Генерация остановлена');
  };

  // ================================
  // ФУНКЦИИ НАВИГАЦИИ ПО СООБЩЕНИЯМ
  // ================================

  const scrollToMessage = useCallback((index: number) => {
    const messageElement = messageRefs.current[index];
    if (messageElement) {
      messageElement.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, []);

  // ================================
  // ФУНКЦИИ ДЛЯ РЕЖИМА "ПОДЕЛИТЬСЯ"
  // ================================

  const handleEnterShareMode = () => {
    setShareMode(true);
    setSelectedMessages(new Set());
  };

  const handleExitShareMode = () => {
    setShareMode(false);
    setSelectedMessages(new Set());
  };

  const handleToggleMessage = (userMsgId: string, assistantMsgId: string) => {
    const newSelected = new Set(selectedMessages);
    
    if (newSelected.has(userMsgId) && newSelected.has(assistantMsgId)) {
      // Если оба выбраны, снимаем выбор
      newSelected.delete(userMsgId);
      newSelected.delete(assistantMsgId);
    } else {
      // Выбираем оба
      newSelected.add(userMsgId);
      newSelected.add(assistantMsgId);
    }
    
    setSelectedMessages(newSelected);
  };

  const handleSelectAll = () => {
    // Получаем все пары вопрос-ответ
    const allPairs: string[] = [];
    for (let i = 0; i < messages.length - 1; i++) {
      if (messages[i].role === 'user' && messages[i + 1].role === 'assistant') {
        allPairs.push(messages[i].id, messages[i + 1].id);
      }
    }
    
    if (selectedMessages.size === allPairs.length) {
      // Если все выбраны, снимаем выбор
      setSelectedMessages(new Set());
    } else {
      // Выбираем все
      setSelectedMessages(new Set(allPairs));
    }
  };

  const handleCreateShareLink = () => {
    if (selectedMessages.size === 0) {
      showNotification('error', 'Выберите хотя бы одно сообщение');
      return;
    }
    // Открываем диалог подтверждения
    setShareDialogOpen(true);
  };

  const createShareLinkConfirmed = async (): Promise<string> => {
    try {
      // Фильтруем выбранные сообщения в правильном порядке
      const selectedMessagesArray = messages.filter(msg => selectedMessages.has(msg.id));

      // Получаем токен для авторизации
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(getApiUrl('/api/share/create'), {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          messages: selectedMessagesArray,
        }),
      });

      if (!response.ok) {
        throw new Error('Ошибка создания публичной ссылки');
      }

      const data = await response.json();
      const fullUrl = `${window.location.origin}/share/${data.share_id}`;
      
      return fullUrl;
    } catch (err) {
      showNotification('error', err instanceof Error ? err.message : 'Произошла ошибка');
      throw err;
    }
  };

  const handleCloseShareDialog = () => {
    setShareDialogOpen(false);
    // Выходим из режима выбора после закрытия диалога
    handleExitShareMode();
  };

  // ================================
  // КОМПОНЕНТЫ СООБЩЕНИЙ
  // ================================

    const MessageCard = ({ message, index }: { message: Message; index: number }): React.ReactElement => {
    const isUser = message.role === 'user';
    const [isHovered, setIsHovered] = useState(false);
    const shouldShowBorder = isUser 
      ? !interfaceSettings.userNoBorder 
      : !interfaceSettings.assistantNoBorder;
    
    const messageContent = (
      <>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.3 }}>
          <Avatar
            sx={{
              width: 24,
              height: 24,
              mr: 1,
              bgcolor: isUser ? 'primary.dark' : 'transparent',
            }}
            src={isUser ? undefined : '/astra.png'}
          >
            {isUser ? <PersonIcon /> : null}
          </Avatar>
          <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}>
            {isUser 
              ? (interfaceSettings.showUserName && user?.username ? user.username : 'Вы')
              : 'astrachat'}
          </Typography>
          <Typography variant="caption" sx={{ ml: 'auto', opacity: 0.6, fontSize: '0.7rem' }}>
            {formatTimestamp(message.timestamp)}
          </Typography>
        </Box>
        
        <Box sx={{ width: '100%' }}>
          {message.multiLLMResponses && message.multiLLMResponses.length > 0 ? (
            // Отображение нескольких ответов от разных моделей
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {message.multiLLMResponses.map((response, index) => (
                <Card
                  key={index}
                  sx={{
                    border: '1px solid',
                    borderColor: response.error ? 'error.main' : 'divider',
                    bgcolor: response.error ? 'error.light' : 'background.paper',
                  }}
                >
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="caption" fontWeight="bold" color={response.error ? 'error' : 'primary'}>
                        {response.model}
                      </Typography>
                      {response.isStreaming && (
                        <Chip label="Генерируется..." size="small" color="info" />
                      )}
                      {response.error && (
                        <Chip label="Ошибка" size="small" color="error" />
                      )}
                    </Box>
                    {response.error ? (
                      <Alert severity="error" sx={{ mt: 1 }}>
                        <Typography variant="body2">{response.content}</Typography>
                      </Alert>
                    ) : (
                      <MessageRenderer 
                        content={response.content} 
                        isStreaming={response.isStreaming}
                        onSendMessage={handleSendMessageFromRenderer}
                      />
                    )}
                  </CardContent>
                </Card>
              ))}
            </Box>
          ) : (
            // Обычное отображение одного ответа (с поддержкой альтернативных вариантов)
            <MessageRenderer 
              content={(() => {
                // Если есть альтернативные ответы, показываем текущий вариант
                if (message.alternativeResponses && message.alternativeResponses.length > 0 && message.currentResponseIndex !== undefined) {
                  const currentIndex = message.currentResponseIndex;
                  
                  if (currentIndex >= 0 && currentIndex < message.alternativeResponses.length) {
                    const alternativeContent = message.alternativeResponses[currentIndex];
                    // Убираем лишние пробелы и переносы строк в конце (только если не идет стриминг)
                    const resultContent = alternativeContent !== undefined 
                      ? (message.isStreaming ? alternativeContent : alternativeContent.trimEnd())
                      : message.content;
                    
                    // Всегда используем альтернативный контент, если установлен currentResponseIndex
                    // Это важно для стриминга - alternativeContent обновляется при каждом чанке
                    return resultContent;
                  }
                }
                // Fallback на message.content, если нет альтернативных ответов
                // Убираем лишние пробелы и переносы строк в конце (только если не идет стриминг)
                return message.isStreaming ? message.content : message.content.trimEnd();
              })()} 
              isStreaming={message.isStreaming}
              onSendMessage={handleSendMessageFromRenderer}
            />
          )}
        </Box>
      </>
    );
    
    // Проверяем, является ли это сообщение частью пары для выбора
    const isPairStart = isUser && index < messages.length - 1 && messages[index + 1].role === 'assistant';
    const isSelected = isPairStart && 
      selectedMessages.has(message.id) && 
      selectedMessages.has(messages[index + 1].id);

    return (
      <Box
        ref={(el: HTMLDivElement | null) => {
          messageRefs.current[index] = el;
        }}
        data-message-index={index}
        sx={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-start',
          mb: 1.5,
          width: '100%',
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Чекбокс в режиме "Поделиться" */}
        {shareMode && isPairStart && (
          <Checkbox
            checked={isSelected}
            onChange={() => handleToggleMessage(message.id, messages[index + 1].id)}
            sx={{
              mt: 1,
              mr: 1,
              p: 0.5,
            }}
          />
        )}

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: interfaceSettings.leftAlignMessages ? 'flex-start' : (isUser ? 'flex-end' : 'flex-start'),
            flex: 1,
          }}
        >
        {shouldShowBorder ? (
          <Card
            className="message-bubble"
            data-theme={isDarkMode ? 'dark' : 'light'}
            sx={{
              maxWidth: interfaceSettings.leftAlignMessages ? '100%' : (isUser ? '75%' : '100%'),
              minWidth: '180px',
              width: interfaceSettings.leftAlignMessages ? '100%' : (isUser ? undefined : '100%'),
              backgroundColor: isUser 
                ? 'primary.main' 
                : isDarkMode ? 'background.paper' : '#f8f9fa',
              color: isUser ? 'primary.contrastText' : isDarkMode ? 'text.primary' : '#333',
              boxShadow: isDarkMode 
                ? '0 2px 8px rgba(0, 0, 0, 0.15)' 
                : '0 2px 8px rgba(0, 0, 0, 0.1)',
            }}
          >
            <CardContent sx={{ p: 1.2, '&:last-child': { pb: 1.2 } }}>
              {messageContent}
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ width: '100%', p: 1.2 }}>
            {messageContent}
          </Box>
        )}
        
        {/* Кнопки действий снизу карточки - для всех сообщений при наведении */}
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'center',
          alignItems: 'center',
          gap: 0.5,
          mt: 1,
          minHeight: 28, /* Минимальная высота для кнопок */
          opacity: isHovered ? 1 : 0, /* Мгновенное появление/исчезновение */
          visibility: isHovered ? 'visible' : 'hidden', /* Скрываем кнопку, но сохраняем место */
        }}>
          {/* Навигация по вариантам ответов (только для сообщений помощника с альтернативными ответами) */}
          {!isUser && message.alternativeResponses && message.alternativeResponses.length > 1 && (
            <>
              <Tooltip title="Предыдущий вариант">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => {
                      const currentIndex = message.currentResponseIndex ?? 0;
                      if (currentIndex > 0) {
                        const newIndex = currentIndex - 1;
                        const newContent = message.alternativeResponses![newIndex];
                        updateMessage(
                          currentChat!.id,
                          message.id,
                          newContent,
                          undefined,
                          undefined,
                          message.alternativeResponses,
                          newIndex
                        );
                      }
                    }}
                    disabled={(message.currentResponseIndex ?? 0) === 0}
                    sx={{
                      opacity: 0.7,
                      p: 0.5,
                      borderRadius: '6px',
                      minWidth: '28px',
                      width: '28px',
                      height: '28px',
                      '&:hover:not(:disabled)': {
                        opacity: 1,
                        '& .MuiSvgIcon-root': {
                          color: 'primary.main',
                        },
                      },
                    }}
                  >
                    <ChevronLeftIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              
              <Typography variant="caption" sx={{
                opacity: 0.7,
                fontSize: '0.7rem',
                minWidth: '35px',
                textAlign: 'center',
              }}>
                {((message.currentResponseIndex ?? 0) + 1)}/{message.alternativeResponses.length}
              </Typography>
              
              <Tooltip title="Следующий вариант">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => {
                      const currentIndex = message.currentResponseIndex ?? 0;
                      if (currentIndex < message.alternativeResponses!.length - 1) {
                        const newIndex = currentIndex + 1;
                        const newContent = message.alternativeResponses![newIndex];
                        updateMessage(
                          currentChat!.id,
                          message.id,
                          newContent,
                          undefined,
                          undefined,
                          message.alternativeResponses,
                          newIndex
                        );
                      }
                    }}
                    disabled={(message.currentResponseIndex ?? 0) >= message.alternativeResponses!.length - 1}
                    sx={{
                      opacity: 0.7,
                      p: 0.5,
                      borderRadius: '6px',
                      minWidth: '28px',
                      width: '28px',
                      height: '28px',
                      '&:hover:not(:disabled)': {
                        opacity: 1,
                        '& .MuiSvgIcon-root': {
                          color: 'primary.main',
                        },
                      },
                    }}
                  >
                    <ChevronRightIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              
              {/* Разделитель между навигацией и остальными кнопками */}
              <Box sx={{ width: '1px', height: '16px', bgcolor: 'divider', mx: 0.5 }} />
            </>
          )}
          
          <Tooltip title="Копировать">
            <IconButton
              size="small"
              onClick={() => {
                if (message.multiLLMResponses && message.multiLLMResponses.length > 0) {
                  // Для multi-llm копируем все ответы
                  const allResponses = message.multiLLMResponses
                    .map(r => `[${r.model}]\n${r.content}`)
                    .join('\n\n---\n\n');
                  handleCopyMessage(allResponses);
                } else {
                  handleCopyMessage(message.content);
                }
              }}
              className="message-copy-button"
              data-theme={isDarkMode ? 'dark' : 'light'}
              sx={{ 
                opacity: 0.7,
                p: 0.5,
                borderRadius: '6px',
                minWidth: '28px',
                width: '28px',
                height: '28px',
                '&:hover': {
                  opacity: 1,
                  '& .MuiSvgIcon-root': {
                    color: 'primary.main',
                  },
                },
                '& .MuiSvgIcon-root': {
                  fontSize: '18px !important',
                  width: '18px !important',
                  height: '18px !important',
                },
              }}
            >
              <CopyIcon />
            </IconButton>
          </Tooltip>
          
          {/* Кнопка редактирования - для всех сообщений */}
          <Tooltip title="Редактировать">
            <IconButton
              size="small"
              onClick={() => handleEditClick(message)}
              className="message-edit-button"
              data-theme={isDarkMode ? 'dark' : 'light'}
              sx={{ 
                opacity: 0.7,
                p: 0.5,
                borderRadius: '6px',
                minWidth: '28px',
                width: '28px',
                height: '28px',
                '&:hover': {
                  opacity: 1,
                  '& .MuiSvgIcon-root': {
                    color: 'primary.main',
                  },
                },
                '& .MuiSvgIcon-root': {
                  fontSize: '18px !important',
                  width: '18px !important',
                  height: '18px !important',
                },
              }}
            >
              <EditIcon />
            </IconButton>
          </Tooltip>
          
          {/* Кнопка перегенерации - только для сообщений LLM/агента */}
          {!isUser && (
            <Tooltip title="Перегенерировать">
              <IconButton
                size="small"
                onClick={() => handleRegenerate(message)}
                className="message-regenerate-button"
                data-theme={isDarkMode ? 'dark' : 'light'}
                sx={{ 
                  opacity: 0.7,
                  p: 0.5,
                  borderRadius: '6px',
                  minWidth: '28px',
                  width: '28px',
                  height: '28px',
                  '&:hover': {
                    opacity: 1,
                    '& .MuiSvgIcon-root': {
                      color: 'primary.main',
                    },
                  },
                  '& .MuiSvgIcon-root': {
                    fontSize: '18px !important',
                    width: '18px !important',
                    height: '18px !important',
                  },
                }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          )}
          
          {/* Кнопка озвучивания - для всех сообщений */}
          <Tooltip title="Прочесть вслух">
            <IconButton
              size="small"
              onClick={() => {
                // Получаем текущий контент сообщения
                let textToSpeak = message.content;
                
                // Если есть альтернативные ответы, берём текущий вариант (только для LLM)
                if (!isUser && message.alternativeResponses && message.alternativeResponses.length > 0 && message.currentResponseIndex !== undefined) {
                  const currentIndex = message.currentResponseIndex;
                  if (currentIndex >= 0 && currentIndex < message.alternativeResponses.length) {
                    textToSpeak = message.alternativeResponses[currentIndex];
                  }
                }
                
                // Для multi-llm берём первый ответ или все ответы (только для LLM)
                if (!isUser && message.multiLLMResponses && message.multiLLMResponses.length > 0) {
                  textToSpeak = message.multiLLMResponses
                    .filter(r => !r.error)
                    .map(r => r.content)
                    .join(' ');
                }
                
                synthesizeSpeech(textToSpeak);
              }}
              className="message-speak-button"
              data-theme={isDarkMode ? 'dark' : 'light'}
              disabled={isSpeaking}
              sx={{ 
                opacity: 0.7,
                p: 0.5,
                borderRadius: '6px',
                minWidth: '28px',
                width: '28px',
                height: '28px',
                '&:hover:not(:disabled)': {
                  opacity: 1,
                  '& .MuiSvgIcon-root': {
                    color: 'primary.main',
                  },
                },
                '&:disabled': {
                  opacity: 0.4,
                },
                '& .MuiSvgIcon-root': {
                  fontSize: '18px !important',
                  width: '18px !important',
                  height: '18px !important',
                },
              }}
            >
              <VolumeUpIcon />
            </IconButton>
          </Tooltip>
          
          {/* Кнопка "Поделиться" - только для сообщений ассистента */}
          {!isUser && !shareMode && (
            <Tooltip title="Поделиться">
              <IconButton
                size="small"
                onClick={handleEnterShareMode}
                className="message-share-button"
                data-theme={isDarkMode ? 'dark' : 'light'}
                sx={{ 
                  opacity: 0.7,
                  p: 0.5,
                  borderRadius: '6px',
                  minWidth: '28px',
                  width: '28px',
                  height: '28px',
                  '&:hover': {
                    opacity: 1,
                    '& .MuiSvgIcon-root': {
                      color: 'primary.main',
                    },
                  },
                  '& .MuiSvgIcon-root': {
                    fontSize: '18px !important',
                    width: '18px !important',
                    height: '18px !important',
                  },
                }}
              >
                <ShareIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
        </Box>
      </Box>
    );
  };

  // ================================
  // ДИАЛОГИ
  // ================================

  const DocumentDialog = (): React.ReactElement => (
    <Dialog
      open={showDocumentDialog}
      onClose={() => setShowDocumentDialog(false)}
      maxWidth="md"
      fullWidth
      TransitionComponent={undefined}
      transitionDuration={0}
    >
      <DialogTitle>Загрузка документов</DialogTitle>
      <DialogContent>
        <Box
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          sx={{
            border: '2px dashed',
            borderColor: isDragging ? 'primary.main' : 'divider',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            bgcolor: isDragging ? 'action.hover' : 'background.paper',
            cursor: 'pointer',
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" sx={{ mb: 1 }}>
            Перетащите файл сюда или нажмите для выбора
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Поддерживаются PDF, Word, Excel, текстовые файлы и изображения (JPG, PNG, WebP) до 50MB
          </Typography>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png,.webp"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </Box>
        

      </DialogContent>
      <DialogActions>
        <Button onClick={() => setShowDocumentDialog(false)}>
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );

  // ================================
  // ОСНОВНОЙ РЕНДЕР
  // ================================

  // Если режим multi-llm, показываем специальный UI
  if (agentStatus?.mode === 'multi-llm') {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: 'background.default' }}>
        {/* Основная область с окнами моделей */}
        <Box sx={{ flex: 1, display: 'grid', gridTemplateColumns: `repeat(${modelWindows.length}, 1fr)`, gap: 2, p: 2, overflow: 'hidden' }}>
          {modelWindows.map((window) => {
            const isStreaming = modelWindows.find(w => w.id === window.id)?.isStreaming || false;
            
            return (
              <Box 
                key={window.id} 
                sx={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  border: '1px solid', 
                  borderColor: 'divider',
                  borderRadius: 2,
                  bgcolor: 'background.paper',
                  overflow: 'hidden'
                }}
              >
                {/* Выбор модели над окном */}
                <Box sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.default', display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Модель</InputLabel>
                    <Select
                      value={window.selectedModel}
                      label="Модель"
                      onChange={(e) => handleModelSelect(window.id, e.target.value)}
                      disabled={availableModels.length === 0}
                    >
                      <MenuItem value="">
                        <em>Не выбрано</em>
                      </MenuItem>
                      {availableModels.length === 0 ? (
                        <MenuItem disabled>
                          Загрузка моделей...
                        </MenuItem>
                      ) : (
                        availableModels
                          .filter(m => {
                            const isSelectedElsewhere = modelWindows.some(w => 
                              w.id !== window.id && w.selectedModel === m.name
                            );
                            return !isSelectedElsewhere || window.selectedModel === m.name;
                          })
                          .map((model) => (
                            <MenuItem key={model.name} value={model.name}>
                              {model.name}
                            </MenuItem>
                          ))
                      )}
                    </Select>
                  </FormControl>
                  {modelWindows.length > 1 && (
                    <IconButton
                      size="small"
                      onClick={() => removeModelWindow(window.id)}
                      color="error"
                      sx={{ flexShrink: 0 }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
                
                {/* Область истории и ответов */}
                <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                  {conversationHistory.length === 0 ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                      <Typography variant="body2" color="text.secondary" align="center">
                        Выберите модель и отправьте сообщение для начала диалога
                      </Typography>
                    </Box>
                  ) : (
                    conversationHistory.map((conv, idx) => {
                      const response = conv.responses.find(r => r.model === window.selectedModel);
                      return (
                        <Box key={idx} sx={{ mb: 2 }}>
                          {/* Сообщение пользователя */}
                          <Card sx={{ mb: 1, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
                            <CardContent sx={{ p: 1.5, pb: 1.5 }}>
                              <Typography variant="body2">{conv.userMessage}</Typography>
                            </CardContent>
                          </Card>
                          
                          {/* Ответ модели */}
                          <Card sx={{ bgcolor: response?.error ? 'error.light' : 'background.paper' }}>
                            <CardContent sx={{ p: 1.5 }}>
                              {response ? (
                                response.error ? (
                                  <Alert severity="error" sx={{ mb: 0 }}>
                                    <Typography variant="body2">{response.content}</Typography>
                                  </Alert>
                                ) : (
                                  <MessageRenderer 
                                    content={response.content}
                                    onSendMessage={(prompt) => {
                                      if (currentChat && isConnected && !state.isLoading) {
                                        sendMessage(prompt, currentChat.id);
                                      }
                                    }}
                                  />
                                )
                              ) : (
                                idx === conversationHistory.length - 1 && isStreaming ? (
                                  // Анимация "думает..." для текущей генерации
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                                      <Box
                                        sx={{
                                          width: 6,
                                          height: 6,
                                          borderRadius: '50%',
                                          bgcolor: 'primary.main',
                                          animation: 'thinkingDot 1.4s ease-in-out infinite both',
                                          '@keyframes thinkingDot': {
                                            '0%, 80%, 100%': { transform: 'scale(0)' },
                                            '40%': { transform: 'scale(1)' },
                                          },
                                        }}
                                      />
                                      <Box
                                        sx={{
                                          width: 6,
                                          height: 6,
                                          borderRadius: '50%',
                                          bgcolor: 'primary.main',
                                          animation: 'thinkingDot 1.4s ease-in-out infinite both',
                                          animationDelay: '0.2s',
                                          '@keyframes thinkingDot': {
                                            '0%, 80%, 100%': { transform: 'scale(0)' },
                                            '40%': { transform: 'scale(1)' },
                                          },
                                        }}
                                      />
                                      <Box
                                        sx={{
                                          width: 6,
                                          height: 6,
                                          borderRadius: '50%',
                                          bgcolor: 'primary.main',
                                          animation: 'thinkingDot 1.4s ease-in-out infinite both',
                                          animationDelay: '0.4s',
                                          '@keyframes thinkingDot': {
                                            '0%, 80%, 100%': { transform: 'scale(0)' },
                                            '40%': { transform: 'scale(1)' },
                                          },
                                        }}
                                      />
                                    </Box>
                                    <Typography variant="body2" sx={{ 
                                      color: isDarkMode ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)',
                                      fontSize: '0.875rem',
                                    }}>
                                      думает...
                                    </Typography>
                                  </Box>
                                ) : (
                                  <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                    Модель не отвечала
                                  </Typography>
                                )
                              )}
                            </CardContent>
                          </Card>
                        </Box>
                      );
                    })
                  )}
                  
                  {/* Индикатор потоковой генерации - показываем только если нет ответа в истории */}
                  {isStreaming && conversationHistory.length === 0 && (
                    <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        <Box
                          sx={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            bgcolor: 'primary.main',
                            animation: 'thinkingDot 1.4s ease-in-out infinite both',
                            '@keyframes thinkingDot': {
                              '0%, 80%, 100%': { transform: 'scale(0)' },
                              '40%': { transform: 'scale(1)' },
                            },
                          }}
                        />
                        <Box
                          sx={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            bgcolor: 'primary.main',
                            animation: 'thinkingDot 1.4s ease-in-out infinite both',
                            animationDelay: '0.2s',
                            '@keyframes thinkingDot': {
                              '0%, 80%, 100%': { transform: 'scale(0)' },
                              '40%': { transform: 'scale(1)' },
                            },
                          }}
                        />
                        <Box
                          sx={{
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            bgcolor: 'primary.main',
                            animation: 'thinkingDot 1.4s ease-in-out infinite both',
                            animationDelay: '0.4s',
                            '@keyframes thinkingDot': {
                              '0%, 80%, 100%': { transform: 'scale(0)' },
                              '40%': { transform: 'scale(1)' },
                            },
                          }}
                        />
                      </Box>
                      <Typography variant="body2" sx={{ 
                        color: isDarkMode ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)',
                        fontSize: '0.875rem',
                      }}>
                        думает...
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Box>
            );
          })}
        </Box>

        {/* Панель управления моделями и ввода */}
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
          <ChatInputBar
            value={inputMessage}
            onChange={setInputMessage}
            onKeyPress={handleKeyPress}
            onPaste={(e) => handlePaste(e as React.ClipboardEvent<HTMLDivElement>)}
            placeholder={
              !isConnected && !isConnecting
                ? 'Нет соединения с сервером. Запустите backend на порту 8000'
                : isConnecting
                  ? 'Подключение к серверу...'
                  : modelWindows.some(w => w.isStreaming)
                    ? 'Модели генерируют ответ... Нажмите ⏹️ чтобы остановить'
                    : !modelWindows.some(w => w.selectedModel)
                      ? 'Выберите модель для начала диалога'
                      : 'Чем я могу помочь вам сегодня?'
            }
            inputDisabled={!isConnected || !modelWindows.some(w => w.selectedModel) || modelWindows.some(w => w.isStreaming)}
            inputRef={inputRef}
            isDarkMode={isDarkMode}
            maxWidth="1000px"
            fileInputRef={fileInputRef}
            onAttachClick={() => fileInputRef.current?.click()}
            onFileSelect={(files) => { if (files?.length) handleFileUpload(files[0]); }}
            uploadedFiles={uploadedFiles.map(f => ({ name: f.name, type: f.type || 'application/octet-stream' }))}
            onFileRemove={(file) => handleFileDelete(file.name)}
            isUploading={isUploading}
            attachDisabled={isUploading || modelWindows.some(w => w.isStreaming)}
            showReportButton={uploadedFiles.length > 0}
            onReportClick={handleGenerateReport}
            reportDisabled={isUploading || modelWindows.some(w => w.isStreaming)}
            showStopButton={state.isLoading || modelWindows.some(w => w.isStreaming)}
            onStopClick={handleStopGeneration}
            onSendClick={handleSendMessage}
            sendDisabled={!inputMessage.trim() || !isConnected || !modelWindows.some(w => w.selectedModel)}
            styleVariant={interfaceSettings.chatInputStyle}
            extraActions={
              modelWindows.length < 4 ? (
                <Tooltip title="Добавить модель">
                  <IconButton
                    onClick={addModelWindow}
                    sx={{
                      color: 'primary.main',
                      bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'}`,
                      '&:hover': {
                        bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                      },
                      '&:active': { transform: 'none' },
                      flexShrink: 0,
                    }}
                    disableRipple
                    disabled={modelWindows.some(w => w.isStreaming)}
                  >
                    <AddIcon sx={{ fontSize: '1.2rem' }} />
                  </IconButton>
                </Tooltip>
              ) : null
            }
          />
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Основной контент */}
      <Box 
        className="fullscreen-chat" 
        sx={{ 
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          marginRight: rightSidebarHidden ? 0 : (rightSidebarOpen ? 0 : '-64px'),
          transition: 'margin-right 0.3s ease',
          pt: 8,
          background: isDarkMode 
            ? 'linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 50%, #1a1a1a 100%)'
            : 'linear-gradient(135deg, #f5f5f5 0%, #ffffff 50%, #fafafa 100%)',
          color: isDarkMode ? 'white' : '#333',
          position: 'relative',
        }}
      >
      {/* Заголовок с информацией о проекте и модели */}
      {currentChat && project && (
        <Box sx={{ 
          position: 'absolute',
          top: 16,
          left: sidebarOpen ? 16 : 80,
          zIndex: 1200,
          transition: 'left 0.3s ease',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 500,
              color: isDarkMode ? 'white' : '#333',
              cursor: 'pointer',
              '&:hover': {
                opacity: 0.8,
              },
              fontSize: '0.95rem',
            }}
            onClick={() => navigate(`/project/${project.id}`)}
          >
            {project.name}
          </Typography>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 400,
              color: isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
              fontSize: '0.95rem',
            }}
          >
            /
          </Typography>
          {!showModelSelectorInSettings && (
            <ModelSelector 
              isDarkMode={isDarkMode}
              onModelSelect={(modelPath) => {
                
              }}
            />
          )}
        </Box>
      )}
      
      {/* Селектор моделей - на одном уровне с кнопкой сворачивания боковой панели */}
      {/* Когда панель развернута - ближе к панели, когда закрыта - дальше от узкой полоски */}
      {(!currentChat || !project) && (
        <Box sx={{ 
          position: 'absolute',
          top: 16,
          left: sidebarOpen ? 16 : 80, // Ближе к панели когда развернута, дальше от узкой полоски (64px) когда закрыта
          zIndex: 1200,
          transition: 'left 0.3s ease', // Плавная анимация при изменении позиции
          display: 'flex',
          alignItems: 'center',
        }}>
          {!showModelSelectorInSettings && (
            <ModelSelector 
              isDarkMode={isDarkMode}
              onModelSelect={(modelPath) => {
                
              }}
            />
          )}
        </Box>
      )}

      {/* Область сообщений */}
      <Box
        className="chat-messages-area"
                 sx={{
           border: isDragging ? '2px dashed' : 'none',
           borderColor: isDragging ? 'primary.main' : 'transparent',
           bgcolor: isDragging ? 'action.hover' : 'transparent',
           position: 'relative',
           minHeight: '60vh',
           display: 'flex',
           flexDirection: 'column',
           justifyContent: messages.length === 0 ? 'center' : 'flex-start',
           alignItems: 'center',
           py: 4,
           // Селектор моделей в правом верхнем углу
           '&::before': {
             content: '""',
             position: 'absolute',
             top: 16,
             right: 16,
             zIndex: 10,
           },
           // Кастомные стили для скроллбара
           '&::-webkit-scrollbar': {
             width: '8px',
           },
           '&::-webkit-scrollbar-track': {
             background: isDarkMode 
               ? 'rgba(30, 30, 30, 0.5)' 
               : 'rgba(245, 245, 245, 0.5)',
             borderRadius: '4px',
           },
           '&::-webkit-scrollbar-thumb': {
             background: isDarkMode 
               ? 'rgba(45, 45, 45, 0.8)' 
               : 'rgba(200, 200, 200, 0.8)',
             borderRadius: '4px',
             '&:hover': {
               background: isDarkMode 
                 ? 'rgba(60, 60, 60, 0.9)' 
                 : 'rgba(180, 180, 180, 0.9)',
             },
           },
           // Для Firefox
           scrollbarWidth: 'thin',
           scrollbarColor: isDarkMode 
             ? 'rgba(45, 45, 45, 0.8) rgba(30, 30, 30, 0.5)' 
             : 'rgba(200, 200, 200, 0.8) rgba(245, 245, 245, 0.5)',
         }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
          {messages.length === 0 ? (
            null
          ) : (
            <Box sx={{ 
              width: '100%', 
              maxWidth: interfaceSettings.widescreenMode ? '100%' : '1000px', 
              mx: 'auto',
              px: interfaceSettings.widescreenMode ? 4 : 2,
            }}>
              {messages.map((message, index) => (
                <MessageCard key={message.id || index} message={message} index={index} />
              ))}
              
              {/* Индикатор размышления - показывается только до начала потоковой генерации, сразу после сообщений */}
              {state.isLoading && !messages.some(msg => msg.isStreaming) && (
                <Box sx={{ 
                  width: '100%', 
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: interfaceSettings.leftAlignMessages ? 'flex-start' : 'flex-start',
                  mb: 1.5,
                }}>
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      maxWidth: interfaceSettings.widescreenMode ? '100%' : '75%',
                      minWidth: '180px',
                    }}
                  >
                    <Card
                      sx={{
                        backgroundColor: isDarkMode ? 'background.paper' : '#f8f9fa',
                        color: isDarkMode ? 'text.primary' : '#333',
                        boxShadow: isDarkMode 
                          ? '0 2px 8px rgba(0, 0, 0, 0.15)' 
                          : '0 2px 8px rgba(0, 0, 0, 0.1)',
                        width: '100%',
                      }}
                    >
                      <CardContent sx={{ p: 1.2, pb: 0.8 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.3 }}>
                          <Avatar
                            src="/astra.png"
                            sx={{
                              width: 24,
                              height: 24,
                              mr: 1,
                              bgcolor: 'transparent',
                              position: 'relative',
                              '&::before': {
                                content: '""',
                                position: 'absolute',
                                top: '-2px',
                                left: '-2px',
                                right: '-2px',
                                bottom: '-2px',
                                borderRadius: '50%',
                                background: 'radial-gradient(circle, rgba(33, 150, 243, 0.3) 0%, transparent 70%)',
                                animation: 'thinking-glow 2s ease-in-out infinite',
                                '@keyframes thinking-glow': {
                                  '0%, 100%': { 
                                    opacity: 0.3,
                                    transform: 'scale(1)',
                                  },
                                  '50%': { 
                                    opacity: 0.8,
                                    transform: 'scale(1.3)',
                                  },
                                },
                              },
                              animation: 'thinking 2s ease-in-out infinite',
                            }}
                          />
                          <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}>
                            astrachat
                          </Typography>
                          <Typography variant="caption" sx={{ ml: 'auto', opacity: 0.6, fontSize: '0.7rem' }}>
                            {new Date().toLocaleTimeString('ru-RU', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </Typography>
                        </Box>
                        
                        <Box sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 1,
                          minHeight: '24px',
                        }}>
                          <Box sx={{ display: 'flex', gap: 0.5 }}>
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: '#2196f3',
                                animation: 'dot1 1.4s ease-in-out infinite both',
                                '@keyframes dot1': {
                                  '0%, 80%, 100%': { transform: 'scale(0)' },
                                  '40%': { transform: 'scale(1)' },
                                },
                              }}
                            />
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: '#2196f3',
                                animation: 'dot2 1.4s ease-in-out infinite both',
                                animationDelay: '0.2s',
                                '@keyframes dot2': {
                                  '0%, 80%, 100%': { transform: 'scale(0)' },
                                  '40%': { transform: 'scale(1)' },
                                },
                              }}
                            />
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: '#2196f3',
                                animation: 'dot3 1.4s ease-in-out infinite both',
                                animationDelay: '0.4s',
                                '@keyframes dot3': {
                                  '0%, 80%, 100%': { transform: 'scale(0)' },
                                  '40%': { transform: 'scale(1)' },
                                },
                              }}
                            />
                          </Box>
                          <Typography variant="body2" sx={{ 
                            color: isDarkMode ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)',
                            fontSize: '0.875rem',
                          }}>
                            думает...
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Box>
                </Box>
              )}
            </Box>
          )}
          <div ref={messagesEndRef} />
          
          {/* Подсказка о перетаскивании в области сообщений */}
          {isDragging && (
            <Box
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                bgcolor: 'rgba(33, 150, 243, 0.9)',
                backdropFilter: 'blur(10px)',
                color: 'white',
                p: 3,
                borderRadius: 2,
                zIndex: 1000,
                textAlign: 'center',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
              }}
            >
              <UploadIcon sx={{ fontSize: 48, mb: 2 }} />
              <Typography variant="h6">
                Отпустите файл для загрузки
              </Typography>
            </Box>
          )}
        </Box>


                 {/* Поле ввода */}
         <Box
           className="chat-input-area"
           data-theme={isDarkMode ? 'dark' : 'light'}
                       sx={{
              borderColor: isDragging ? 'primary.main' : 'divider',
              bgcolor: isDragging ? 'action.hover' : 'transparent',
            }}
           onDragOver={handleDragOver}
           onDragLeave={handleDragLeave}
           onDrop={handleDrop}
         >
          
                     {/* Приветствие НАД контейнером ввода при пустом чате */}
                     {messages.length === 0 && (
                       <Box sx={{ 
                         textAlign: 'center', 
                         mb: 3,
                         maxWidth: interfaceSettings.widescreenMode ? '100%' : '1000px',
                         mx: 'auto',
                         px: interfaceSettings.widescreenMode ? 4 : 2,
                         position: 'absolute',
                         top: '45%',
                         left: '50%',
                         transform: 'translate(-50%, -120%)',
                         width: '100%',
                       }}>
                         <Typography 
                           variant="h4" 
                           sx={{ 
                             color: isDarkMode ? 'white' : '#333', 
                             fontWeight: 600,
                             mb: 1,
                           }}
                         >
                           {getGreeting()}
                         </Typography>
                       </Box>
                     )}

                     {/* Объединенное поле ввода с кнопками */}
           <ChatInputBar
             value={inputMessage}
             onChange={setInputMessage}
             onKeyPress={handleKeyPress}
             onPaste={(e) => handlePaste(e as React.ClipboardEvent<HTMLDivElement>)}
             placeholder={
               !isConnected && !isConnecting
                 ? 'Нет соединения с сервером. Запустите backend на порту 8000'
                 : isConnecting
                   ? 'Подключение к серверу...'
                   : state.isLoading && !messages.some(msg => msg.isStreaming)
                     ? 'astrachat думает...'
                     : state.isLoading && messages.some(msg => msg.isStreaming)
                       ? 'astrachat генерирует ответ... Нажмите ⏹️ чтобы остановить'
                       : 'Чем я могу помочь вам сегодня?'
             }
             inputDisabled={!isConnected || (state.isLoading && !messages.some(msg => msg.isStreaming))}
             inputRef={inputRef}
             isDarkMode={isDarkMode}
             styleVariant={interfaceSettings.chatInputStyle}
             containerSx={{
               mt: 2,
               p: interfaceSettings.chatInputStyle === 'classic' ? 0 : 1.5,
               borderRadius: interfaceSettings.chatInputStyle === 'classic' ? '28px' : '28px',
               maxWidth: messages.length === 0 ? '800px' : (interfaceSettings.widescreenMode ? '100%' : '1000px'),
               width: '100%',
               mx: 'auto',
               px: interfaceSettings.chatInputStyle === 'classic' ? 0 : (interfaceSettings.widescreenMode ? 4 : 2),
               ...(messages.length === 0 && {
                 position: 'absolute',
                 top: '50%',
                 left: '50%',
                 transform: 'translate(-50%, 0)',
                 mt: 0,
               }),
             }}
             fileInputRef={fileInputRef}
             onAttachClick={() => fileInputRef.current?.click()}
             onFileSelect={(files) => { if (files?.length) handleFileUpload(files[0]); }}
             uploadedFiles={uploadedFiles.map(f => ({ name: f.name, type: f.type || 'application/octet-stream' }))}
             onFileRemove={(file) => handleFileDelete(file.name)}
             isUploading={isUploading}
             attachDisabled={isUploading || (state.isLoading && !messages.some(msg => msg.isStreaming))}
             showReportButton={uploadedFiles.length > 0}
             onReportClick={handleGenerateReport}
             reportDisabled={isUploading || (state.isLoading && !messages.some(msg => msg.isStreaming))}
             onSettingsClick={handleMenuOpen}
             settingsDisabled={state.isLoading && !messages.some(msg => msg.isStreaming)}
             showStopButton={state.isLoading || messages.some(msg => msg.isStreaming)}
             onStopClick={handleStopGeneration}
             onSendClick={handleSendMessage}
             sendDisabled={!inputMessage.trim() || !isConnected || (state.isLoading && !messages.some(msg => msg.isStreaming))}
             onVoiceClick={() => setShowVoiceDialog(true)}
             voiceDisabled={state.isLoading && !messages.some(msg => msg.isStreaming)}
             voiceTooltip="Голосовой ввод"
           />

             {/* Диалоги */}
       <VoiceChatDialog
         open={showVoiceDialog}
         onClose={() => setShowVoiceDialog(false)}
       />
       <DocumentDialog />

               {/* Выпадающее меню с дополнительными действиями (шестеренка) */}
       <Menu
         anchorEl={anchorEl}
         open={Boolean(anchorEl)}
         onClose={handleMenuClose}
         anchorOrigin={{
           vertical: 'top',
           horizontal: 'left',
         }}
         transformOrigin={{
           vertical: 'bottom',
           horizontal: 'left',
         }}
         PaperProps={{
           sx: {
             bgcolor: isDarkMode ? 'background.paper' : 'white',
             border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
             boxShadow: isDarkMode 
               ? '0 4px 20px rgba(0, 0, 0, 0.3)' 
               : '0 4px 20px rgba(0, 0, 0, 0.15)',
           }
         }}
       >
         <MenuItem onClick={handleClearChat} sx={{ gap: 1 }}>
           <ClearIcon fontSize="small" />
           Очистить чат
         </MenuItem>
       </Menu>

       {/* Диалог редактирования сообщения */}
       <Dialog
         open={editDialogOpen}
         onClose={handleCancelEdit}
         maxWidth="md"
         fullWidth
         PaperProps={{
           sx: {
             bgcolor: 'background.paper',
             borderRadius: 2,
           }
         }}
       >
        <DialogTitle>
          Редактировать сообщение
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Текст сообщения"
            fullWidth
            multiline
            rows={6}
            variant="outlined"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelEdit}>
            Отменить
          </Button>
          {editingMessage?.role === 'user' ? (
            // Кнопки для сообщений пользователя
            <>
              <Button onClick={handleSaveEdit} variant="outlined" color="primary">
                Сохранить
              </Button>
              <Button onClick={handleSaveAndSend} variant="contained" color="primary">
                Сохранить и отправить
              </Button>
            </>
          ) : (
            // Кнопки для сообщений LLM
            <Button onClick={handleSaveEdit} variant="contained" color="primary">
              Сохранить
            </Button>
          )}
        </DialogActions>
       </Dialog>

       {/* Уведомления */}
       <Snackbar
         open={showCopyAlert}
         autoHideDuration={2000}
         onClose={() => setShowCopyAlert(false)}
       >
         <Alert severity="success" onClose={() => setShowCopyAlert(false)}>
           Текст скопирован в буфер обмена
         </Alert>
       </Snackbar>
      </Box>

      {/* Правый сайдбар с кнопками */}
      {!rightSidebarHidden && (
      <Drawer
        variant="persistent"
        anchor="right"
        open={true}
        sx={{
          width: rightSidebarOpen ? 280 : 64,
          flexShrink: 0,
          transition: 'width 0.3s ease',
          '& .MuiDrawer-paper': {
            width: rightSidebarOpen ? 280 : 64,
            boxSizing: 'border-box',
            background: rightSidebarOpen 
              ? rightSidebarPanelBg
              : 'background.default',
            color: rightSidebarOpen ? 'white' : 'text.primary',
            borderLeft: '1px solid',
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
            p: rightSidebarOpen ? 2 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: rightSidebarOpen ? 'space-between' : 'center',
            background: rightSidebarOpen ? 'rgba(0,0,0,0.1)' : 'transparent',
            minHeight: 64,
          }}
        >
          {rightSidebarOpen && (
            <Typography variant="h6" fontWeight="bold" sx={{ color: 'white' }}>
              Действия
            </Typography>
          )}
          <IconButton
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            sx={{
              color: rightSidebarOpen ? 'white' : 'text.primary',
              '&:hover': {
                backgroundColor: rightSidebarOpen 
                  ? 'rgba(255,255,255,0.1)' 
                  : 'action.hover',
              },
            }}
          >
            <MenuIcon />
          </IconButton>
        </Box>

        {rightSidebarOpen && <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)' }} />}

        {/* Кнопки */}
        <Box sx={{ 
          p: rightSidebarOpen ? 2 : 1, 
          display: 'flex', 
          flexDirection: 'column', 
          gap: rightSidebarOpen ? 2 : 1,
          flex: 1,
        }}>
          {/* Кнопка "Транскрибация" */}
          <Tooltip title={rightSidebarOpen ? '' : 'Транскрибация'} placement="left">
            <Button
              fullWidth={rightSidebarOpen}
              variant={rightSidebarOpen ? 'contained' : 'text'}
              startIcon={<TranscribeIcon />}
              onClick={() => setTranscriptionModalOpen(true)}
              sx={{
                bgcolor: rightSidebarOpen ? 'rgba(255,255,255,0.2)' : 'transparent',
                color: rightSidebarOpen ? 'white' : 'text.primary',
                opacity: !rightSidebarOpen ? 0.7 : 1,
                '&:hover': {
                  bgcolor: rightSidebarOpen 
                    ? 'rgba(255,255,255,0.3)' 
                    : (isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'),
                  opacity: 1,
                  '& .MuiSvgIcon-root': !rightSidebarOpen ? {
                    color: 'primary.main',
                  } : {},
                },
                textTransform: 'none',
                py: rightSidebarOpen ? 1.5 : 1,
                minWidth: rightSidebarOpen ? 'auto' : 40,
                width: rightSidebarOpen ? '100%' : 40,
                justifyContent: rightSidebarOpen ? 'flex-start' : 'center',
                '& .MuiButton-startIcon': {
                  margin: rightSidebarOpen ? '0 8px 0 0' : 0,
                },
              }}
            >
              {rightSidebarOpen && 'Транскрибация'}
            </Button>
          </Tooltip>

          {/* Кнопка "Галерея промптов" */}
          <Tooltip title={rightSidebarOpen ? '' : 'Галерея промптов'} placement="left">
            <Button
              fullWidth={rightSidebarOpen}
              variant={rightSidebarOpen ? 'outlined' : 'text'}
              startIcon={<PromptsIcon />}
              onClick={() => navigate('/prompts')}
              sx={{
                bgcolor: rightSidebarOpen ? 'transparent' : 'transparent',
                color: rightSidebarOpen ? 'white' : 'text.primary',
                borderColor: rightSidebarOpen ? 'rgba(255,255,255,0.3)' : 'transparent',
                opacity: !rightSidebarOpen ? 0.7 : 1,
                '&:hover': {
                  bgcolor: rightSidebarOpen 
                    ? 'rgba(255,255,255,0.2)' 
                    : (isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'),
                  borderColor: rightSidebarOpen ? 'rgba(255,255,255,0.5)' : 'transparent',
                  opacity: 1,
                  '& .MuiSvgIcon-root': !rightSidebarOpen ? {
                    color: 'primary.main',
                  } : {},
                },
                textTransform: 'none',
                py: rightSidebarOpen ? 1.5 : 1,
                minWidth: rightSidebarOpen ? 'auto' : 40,
                width: rightSidebarOpen ? '100%' : 40,
                justifyContent: rightSidebarOpen ? 'flex-start' : 'center',
                '& .MuiButton-startIcon': {
                  margin: rightSidebarOpen ? '0 8px 0 0' : 0,
                },
              }}
            >
              {rightSidebarOpen && 'Галерея промптов'}
            </Button>
          </Tooltip>
        </Box>

        {/* Кнопка "Скрыть панель" - на том же расстоянии как "Показать панель" */}
        {!rightSidebarOpen && (
          <Box sx={{ 
            position: 'fixed',
            right: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 64,
            display: 'flex', 
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1200,
          }}>
            <Tooltip title="Скрыть панель" placement="left">
              <IconButton
                onClick={() => setRightSidebarHidden(true)}
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
                <ChevronRightIcon />
              </IconButton>
            </Tooltip>
          </Box>
        )}
      </Drawer>
      )}

      {/* Кнопка для показа скрытой панели */}
      {rightSidebarHidden && (
        <Box
          sx={{
            position: 'fixed',
            right: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 1200,
          }}
        >
          <Tooltip title="Показать панель" placement="left">
            <IconButton
              onClick={() => {
                setRightSidebarHidden(false);
                setRightSidebarOpen(false);
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
              <ChevronRightIcon sx={{ transform: 'rotate(180deg)' }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Модальное окно транскрибации */}
      <TranscriptionModal
        open={transcriptionModalOpen}
        onClose={() => setTranscriptionModalOpen(false)}
        isTranscribing={isTranscribing}
        transcriptionResult={transcriptionResult}
        onTranscriptionStart={() => setIsTranscribing(true)}
        onTranscriptionComplete={(result) => {
          setIsTranscribing(false);
          setTranscriptionResult(result);
          // Показываем уведомление, даже если окно закрыто
          showNotification('success', 'Транскрибация завершена! Откройте окно транскрибации для просмотра результата.');
        }}
        onTranscriptionError={() => setIsTranscribing(false)}
        onInsertToChat={(text) => {
          setInputMessage(text);
          // Фокусируемся на поле ввода после вставки текста
          setTimeout(() => {
            inputRef.current?.focus();
          }, 100);
        }}
      />

      {/* Нижняя панель в режиме "Поделиться" */}
      {shareMode && (
        <Paper
          sx={{
            position: 'fixed',
            bottom: 0,
            left: sidebarOpen ? 280 : 64,
            right: 0,
            zIndex: 1200,
            borderRadius: 0,
            boxShadow: '0 -4px 12px rgba(0, 0, 0, 0.1)',
            backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
            transition: 'left 0.3s ease',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 3,
              py: 2,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={selectedMessages.size > 0 && (() => {
                      let totalPairs = 0;
                      for (let i = 0; i < messages.length - 1; i++) {
                        if (messages[i].role === 'user' && messages[i + 1].role === 'assistant') {
                          totalPairs++;
                        }
                      }
                      return selectedMessages.size === totalPairs * 2;
                    })()}
                    onChange={handleSelectAll}
                  />
                }
                label="Выбрать все"
              />
              <Typography variant="body2" color="text.secondary">
                Выбрано пар: {selectedMessages.size / 2}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                onClick={handleExitShareMode}
                disabled={isCreatingShareLink}
              >
                Отмена
              </Button>
              <Button
                variant="contained"
                onClick={handleCreateShareLink}
                disabled={selectedMessages.size === 0}
              >
                Создать публичную ссылку
              </Button>
            </Box>
          </Box>
        </Paper>
      )}

      {/* Навигационная панель для сообщений (панель с диалогами) */}
      {messages.length > 0 && showDialoguesPanel && (
        <MessageNavigationBar
          messages={messages}
          isDarkMode={isDarkMode}
          onNavigate={scrollToMessage}
          rightSidebarOpen={rightSidebarOpen}
          rightSidebarHidden={rightSidebarHidden}
        />
      )}

      {/* Диалог подтверждения создания публичной ссылки */}
      <ShareConfirmDialog
        open={shareDialogOpen}
        onClose={handleCloseShareDialog}
        onConfirm={createShareLinkConfirmed}
        isDarkMode={isDarkMode}
        selectedCount={selectedMessages.size}
      />
      </Box>
    </Box>
  );
}
