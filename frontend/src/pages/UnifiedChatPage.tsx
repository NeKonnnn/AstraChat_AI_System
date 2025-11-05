import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Container,
  Card,
  CardContent,
  Avatar,
  Chip,
  Fab,
  Tooltip,
  LinearProgress,
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
  Fade,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Menu,
  Collapse,
} from '@mui/material';
import {
  Send as SendIcon,
  Person as PersonIcon,
  SmartToy as BotIcon,
  Clear as ClearIcon,
  ContentCopy as CopyIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Mic as MicIcon,
  VolumeUp as VolumeUpIcon,
  AttachFile as AttachFileIcon,
  Close as CloseIcon,
  Upload as UploadIcon,
  Description as DocumentIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
  Delete as DeleteIcon,
  GetApp as DownloadIcon,
  Settings as SettingsIcon,
  Square as SquareIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions, Message } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import { getApiUrl, getWsUrl } from '../config/api';
import MessageRenderer from '../components/MessageRenderer';

interface UnifiedChatPageProps {
  isDarkMode: boolean;
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

export default function UnifiedChatPage({ isDarkMode }: UnifiedChatPageProps) {
  // Состояние для текстового чата
  const [inputMessage, setInputMessage] = useState('');
  const [showCopyAlert, setShowCopyAlert] = useState(false);
  
  // Состояние для голосового чата
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [recordedText, setRecordedText] = useState('');
  const [recordingTime, setRecordingTime] = useState(0);
  const [voiceSettings, setVoiceSettings] = useState(() => {
    // Загружаем сохраненные настройки голоса из localStorage
    const savedVoiceSpeaker = localStorage.getItem('voice_speaker');
    const savedVoiceId = localStorage.getItem('voice_id');
    const savedSpeechRate = localStorage.getItem('speech_rate');
    
    console.log('Инициализация voiceSettings из localStorage:', {
      savedVoiceSpeaker,
      savedVoiceId,
      savedSpeechRate,
      parsedSpeechRate: savedSpeechRate ? parseFloat(savedSpeechRate) : 1.0
    });
    
    const settings = {
      voice_id: savedVoiceId || 'ru',
      speech_rate: savedSpeechRate ? parseFloat(savedSpeechRate) : 1.0,
      voice_speaker: savedVoiceSpeaker || 'baya',
    };
    
    console.log('Инициализированные настройки:', settings);
    return settings;
  });
  const [showVoiceDialog, setShowVoiceDialog] = useState(false);
  
  // Состояние для отслеживания тестируемого голоса
  const [currentTestVoice, setCurrentTestVoice] = useState<string | null>(null);
  
  // Предзаписанные тестовые сообщения для каждого голоса
  const voiceTestMessages = {
    baya: "Привет! Я Газик И И. Что обсудим?",
    xenia: "Привет! Я Газик И И. Что обсудим?",
    kseniya: "Привет! Я Газик И И. Что обсудим?",
    aidar: "Привет! Я Газик И И. Что обсудим?",
    eugene: "Привет! Я Газик И И. Что обсудим?"
  };
  
  // WebSocket для голосового чата
  const [voiceSocket, setVoiceSocket] = useState<WebSocket | null>(null);
  const [isVoiceConnected, setIsVoiceConnected] = useState(false);
  const [shouldReconnect, setShouldReconnect] = useState(true);
  
  // Real-time распознавание
  const [realtimeText, setRealtimeText] = useState('');
  
  // Состояние для документов
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryResponse, setQueryResponse] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<Array<{
    name: string;
    size: number;
    type: string;
    uploadDate: string;
  }>>([]);
  const [showDocumentDialog, setShowDocumentDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const currentStreamRef = useRef<MediaStream | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastAudioLevelRef = useRef<number>(0);
  
  // Константы
  const silenceThreshold = 0.1;
  const silenceTimeout = 5000;
  
  // Context и Socket
  const { state } = useAppContext();
  const { 
    clearMessages, 
    showNotification, 
    setSpeaking, 
    setRecording, 
    addMessage, 
    updateMessage, 
    appendChunk, 
    getCurrentMessages, 
    getCurrentChat,
    createChat,
    setCurrentChat,
    updateChatTitle
  } = useAppActions();
  const { sendMessage, isConnected, reconnect, stopGeneration, socket, onMultiLLMEvent, offMultiLLMEvent } = useSocket();

  // Получаем текущий чат и сообщения
  const currentChat = getCurrentChat();
  const messages = getCurrentMessages();
  
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

  // Автоматически обновляем название чата на основе первого сообщения пользователя
  useEffect(() => {
    if (currentChat && messages.length === 1) {
      const firstMessage = messages[0];
      if (firstMessage.role === 'user' && currentChat.title === 'Новый чат') {
        const title = firstMessage.content.length > 50 
          ? firstMessage.content.substring(0, 50) + '...'
          : firstMessage.content;
        updateChatTitle(currentChat.id, title);
      }
    }
  }, [currentChat, messages, updateChatTitle]);

  // Убираем автоматическую остановку генерации при смене чата
  // Генерация должна происходить в том чате, где был задан вопрос

  // Добавляем состояние для текущего индекса голоса
  const [currentVoiceIndex, setCurrentVoiceIndex] = useState(0);
  
  // Состояние для показа/скрытия настроек голоса
  const [showVoiceSettings, setShowVoiceSettings] = useState(false);

  // Отладочная информация при инициализации
  console.log('Инициализация: voiceSettings.voice_speaker =', voiceSettings.voice_speaker, 'currentVoiceIndex =', currentVoiceIndex);

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
          setAgentStatus(data);
        }
      } catch (error) {
        console.error('Ошибка загрузки статуса агента:', error);
      }
    };

    const loadAvailableModels = async () => {
      try {
        const response = await fetch(`${getApiUrl('/api/models/available')}`);
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data.models || []);
        }
      } catch (error) {
        console.error('Ошибка загрузки моделей:', error);
      }
    };

    loadAgentStatus();
    loadAvailableModels();
    
    // Периодически обновляем статус и модели
    const interval = setInterval(() => {
      loadAgentStatus();
      // Обновляем модели только в режиме multi-llm
      if (agentStatus?.mode === 'multi-llm') {
        loadAvailableModels();
      }
    }, 5000);
    
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
            console.log('Загружены модели:', data.models);
            setAvailableModels(data.models || []);
          } else {
            console.error('Ошибка загрузки моделей: статус', response.status);
          }
        } catch (error) {
          console.error('Ошибка загрузки моделей:', error);
        }
      };
      
      loadAvailableModels();
    }
  }, [agentStatus?.mode]);

  // Подписка на события Socket.IO для режима multi-llm
  useEffect(() => {
    if (agentStatus?.mode !== 'multi-llm' || !socket || !onMultiLLMEvent || !offMultiLLMEvent) return;
    
    const handleMultiLLMStart = (data: any) => {
      console.log('multi_llm_start получен:', data);
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
      console.log('multi_llm_chunk получен:', data);
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
      console.log('multi_llm_complete получен:', data);
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
        console.error('Ошибка при загрузке списка документов:', error);
      }
    };

    loadDocuments();
  }, []);

  // Синхронизируем currentVoiceIndex с voiceSettings.voice_speaker при инициализации
  useEffect(() => {
    const voices = Object.keys(voiceTestMessages);
    const currentIndex = voices.indexOf(voiceSettings.voice_speaker);
    console.log('useEffect [voiceSettings.voice_speaker]: voice_speaker =', voiceSettings.voice_speaker, 'найденный index =', currentIndex);
    if (currentIndex !== -1) {
      setCurrentVoiceIndex(currentIndex);
      console.log('Синхронизация при изменении voice_speaker: voice_speaker =', voiceSettings.voice_speaker, 'index =', currentIndex);
    } else {
      console.log('Голос не найден в списке: voice_speaker =', voiceSettings.voice_speaker);
    }
  }, [voiceSettings.voice_speaker]);

  // Принудительная синхронизация при загрузке страницы
  useEffect(() => {
    const voices = Object.keys(voiceTestMessages);
    const currentIndex = voices.indexOf(voiceSettings.voice_speaker);
    console.log('useEffect [] (загрузка): voice_speaker =', voiceSettings.voice_speaker, 'найденный index =', currentIndex);
    if (currentIndex !== -1) {
      setCurrentVoiceIndex(currentIndex);
      console.log('Принудительная синхронизация при загрузке: voice_speaker =', voiceSettings.voice_speaker, 'index =', currentIndex);
    } else {
      console.log('Голос не найден при загрузке: voice_speaker =', voiceSettings.voice_speaker);
    }
  }, []); // Пустой массив зависимостей - выполняется только при монтировании

  // Дополнительная проверка синхронизации после рендера
  useEffect(() => {
    const voices = Object.keys(voiceTestMessages);
    const currentIndex = voices.indexOf(voiceSettings.voice_speaker);
    if (currentIndex !== -1 && currentIndex !== currentVoiceIndex) {
      console.log('🔧 Исправляю рассинхронизацию: currentVoiceIndex =', currentVoiceIndex, 'должен быть =', currentIndex);
      setCurrentVoiceIndex(currentIndex);
    }
  });

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
    } catch (error) {
      console.error('Ошибка отправки сообщения:', error);
      showNotification('error', 'Ошибка отправки сообщения');
    }
  };

  const handleSendMessage = (): void => {
    // Если режим multi-llm, используем специальную функцию
    if (agentStatus?.mode === 'multi-llm') {
      handleSendMessageMultiLLM();
      return;
    }

    if (!inputMessage.trim() || !isConnected || state.isLoading || !currentChat) {
      return;
    }

    sendMessage(inputMessage.trim(), currentChat.id);
    setInputMessage('');
  };

  const handleKeyPress = (event: React.KeyboardEvent): void => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
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

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Функция для определения приветствия по времени суток (Московское время)
  const getGreeting = (): string => {
    const now = new Date();
    const moscowTime = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Moscow"}));
    const hour = moscowTime.getHours();
    
    if (hour >= 5 && hour < 12) {
      return "Доброе утро";
    } else if (hour >= 12 && hour < 18) {
      return "Добрый день";
    } else if (hour >= 18 && hour < 22) {
      return "Добрый вечер";
    } else {
      return "Доброй ночи";
    }
  };

  // ================================
  // ФУНКЦИИ ГОЛОСОВОГО ЧАТА
  // ================================

  // Подключение к WebSocket голосового чата
  const connectVoiceWebSocket = () => {
    if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
      return; // Уже подключен
    }
    
    const ws = new WebSocket(getWsUrl('/ws/voice'));
    setVoiceSocket(ws);
    
    ws.onopen = () => {
      setIsVoiceConnected(true);
      showNotification('success', 'Голосовой чат подключен');
      console.log('Voice WebSocket подключен');
    };
    
    ws.onmessage = (event) => {
      try {
        if (typeof event.data === 'string') {
          const data = JSON.parse(event.data);
          console.log('Получено сообщение от WebSocket:', data);
          
          switch (data.type) {
            case 'listening_started':
              showNotification('success', 'Готов к приему голоса');
              console.log('WebSocket: Подтверждение начала прослушивания получено');
              break;
              
            case 'speech_recognized':
              // Обновляем real-time текст
              console.log('РАСПОЗНАННЫЙ ТЕКСТ:', data.text);
              console.log('ОТЛАДКА: Распознанный текст будет отправлен в LLM для обработки');
              setRealtimeText(prev => prev + ' ' + data.text);
              showNotification('success', 'Речь распознана в реальном времени');
              break;
              
            case 'ai_response':
              // Получаем ответ от AI
              console.log('ОТВЕТ ОТ LLM:', data.text);
              console.log('ОТЛАДКА: LLM обработал запрос и предоставил ответ, начинаю синтез речи');
              setRecordedText(data.text);
              showNotification('success', 'Получен ответ от Газик ИИ');
              break;
              
            case 'speech_error':
              console.error('WebSocket: Ошибка распознавания речи:', data.error);
              showNotification('warning', data.error || 'Ошибка распознавания речи');
              break;
              
            case 'tts_error':
              console.error('WebSocket: Ошибка синтеза речи:', data.error);
              showNotification('error', data.error || 'Ошибка синтеза речи');
              break;
              
            case 'error':
              console.error('WebSocket: Общая ошибка:', data.error);
              showNotification('error', data.error || 'Ошибка WebSocket');
              break;
              
            default:
              console.log('WebSocket: Неизвестный тип сообщения:', data.type);
          }
        } else if (event.data instanceof Blob) {
          // Получены аудио данные для воспроизведения
          console.log('WebSocket: Получены аудио данные для воспроизведения размером:', event.data.size, 'байт');
          playAudioResponse(event.data);
        }
      } catch (error) {
        console.error('Ошибка обработки WebSocket сообщения:', error);
      }
    };
    
    ws.onerror = (error) => {
      setIsVoiceConnected(false);
      showNotification('error', 'Ошибка подключения к голосовому чату');
      console.error('WebSocket error:', error);
      
      // Автоматически переподключаемся через 5 секунд, только если разрешено
      setTimeout(() => {
        if (!isVoiceConnected && shouldReconnect) {
          showNotification('info', 'Попытка переподключения...');
          connectVoiceWebSocket();
        }
      }, 5000);
    };
    
    ws.onclose = (event) => {
      setIsVoiceConnected(false);
      setVoiceSocket(null);
      
      // Автоматически переподключаемся если соединение закрылось неожиданно, только если разрешено
      if (event.code !== 1000 && shouldReconnect) { // 1000 = нормальное закрытие
        showNotification('warning', 'Соединение с голосовым чатом закрыто, переподключаюсь...');
        setTimeout(() => {
          if (!isVoiceConnected && shouldReconnect) {
            connectVoiceWebSocket();
          }
        }, 3000);
      } else {
        console.log('WebSocket закрыт нормально или переподключение отключено');
      }
    };
  };

  // Функция очистки всех ресурсов
  const cleanupVoiceResources = () => {
    console.log('🔧 cleanupVoiceResources вызвана');
    
    // Останавливаем таймер тишины
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
      console.log('🔧 Таймер тишины остановлен');
    }
    
    // Останавливаем анимацию
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
      console.log('🔧 Анимация остановлена');
    }
    
    // Останавливаем запись
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
      console.log('🔧 Запись остановлена');
    }
    
    // Останавливаем медиа поток
    if (currentStreamRef.current) {
      currentStreamRef.current.getTracks().forEach(track => track.stop());
      currentStreamRef.current = null;
      console.log('🔧 Медиа поток остановлен');
    }
    
    // Закрываем аудио контекст
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
      console.log('🔧 Аудио контекст закрыт');
    }
    
    // Останавливаем воспроизведение
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = '';
      currentAudioRef.current = null;
      console.log('🔧 Воспроизведение остановлено');
    }
    
    // Закрываем WebSocket соединение
    if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
      voiceSocket.close();
      setVoiceSocket(null);
      console.log('🔧 WebSocket соединение закрыто');
    }
    
    // Сбрасываем локальные состояния
    setIsRecording(false);
    setIsProcessing(false);
    setIsSpeaking(false);
    setRecordingTime(0);
    setRealtimeText('');
    setAudioLevel(0);
    
    // Сбрасываем глобальные состояния
    setRecording(false);
    setSpeaking(false);
    
    console.log('🔧 Все состояния сброшены');
    showNotification('info', 'Все процессы остановлены');
  };

  // Функция для проверки тишины и автоматической остановки
  const checkSilence = () => {
    if (audioLevel < silenceThreshold) {
      // Если уровень звука ниже порога, запускаем таймер
      if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          console.log('Автоматическая остановка из-за тишины');
          stopRecording();
          showNotification('info', 'Автоматическая остановка: не обнаружена речь');
        }, silenceTimeout);
      }
    } else {
      // Если есть звук, сбрасываем таймер
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
    }
  };

  // Функция воспроизведения аудио ответа
  const playAudioResponse = async (audioBlob: Blob) => {
    try {
      console.log('Воспроизведение аудио ответа размером:', audioBlob.size, 'байт');
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;
      
      audio.onended = () => {
        setIsSpeaking(false);
        setIsProcessing(false);
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
        console.log('Аудио ответ воспроизведен полностью');
        showNotification('success', 'Готов к следующему запросу');
      };
      
      audio.onerror = () => {
        setIsSpeaking(false);
        setIsProcessing(false);
        showNotification('error', 'Ошибка воспроизведения речи');
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
        console.error('Ошибка воспроизведения аудио ответа');
      };
      
      setIsSpeaking(true);
      await audio.play();
      console.log('Начато воспроизведение аудио ответа');
    } catch (error) {
      console.error('Ошибка воспроизведения аудио:', error);
      setIsSpeaking(false);
      setIsProcessing(false);
      showNotification('error', 'Ошибка воспроизведения речи');
    }
  };

  // Функция отправки real-time чанка для распознавания
  const sendRealtimeChunk = async () => {
    if (audioChunksRef.current.length > 0 && voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
      try {
        // Берем последний чанк для real-time распознавания
        const lastChunk = audioChunksRef.current[audioChunksRef.current.length - 1];
        console.log(`Отправляю real-time чанк размером: ${lastChunk.size} байт`);
        
        // Отправляем через WebSocket для быстрого распознавания
        voiceSocket.send(lastChunk);
        console.log('Real-time чанк отправлен через WebSocket');
        
      } catch (error) {
        console.error('Ошибка real-time распознавания:', error);
      }
    }
  };

  const startRecording = async (): Promise<void> => {
    try {
      // Включаем автопереподключение
      setShouldReconnect(true);
      
      // Подключаем WebSocket если не подключен
      if (!isVoiceConnected || !voiceSocket || voiceSocket.readyState !== WebSocket.OPEN) {
        showNotification('info', 'Подключаю голосовой чат...');
        connectVoiceWebSocket();
      }
      
      // Отправляем команду start_listening
      if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
        voiceSocket.send(JSON.stringify({ type: 'start_listening' }));
        showNotification('info', 'Отправляю команду начала прослушивания...');
      }
    
      // Очищаем предыдущие ресурсы перед началом новой записи
      if (currentStreamRef.current) {
        currentStreamRef.current.getTracks().forEach(track => track.stop());
      }
      
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      currentStreamRef.current = stream;
      
      // Настройка аудио контекста для визуализации
      audioContextRef.current = new AudioContext();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);
      
      analyserRef.current.fftSize = 256;
      const bufferLength = analyserRef.current.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      // Настройка MediaRecorder - пытаемся выбрать лучший формат для распознавания речи
      let selectedOptions = undefined;
      
      // Попробуем различные форматы в порядке предпочтения
      const preferredMimeTypes = [
        'audio/wav',
        'audio/webm;codecs=pcm',
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/ogg;codecs=opus'
      ];
      
      for (const mimeType of preferredMimeTypes) {
        if (MediaRecorder.isTypeSupported(mimeType)) {
          selectedOptions = { mimeType };
          break;
        }
      }
      
      if (!selectedOptions) {
        mediaRecorderRef.current = new MediaRecorder(stream);
      } else {
        mediaRecorderRef.current = new MediaRecorder(stream, selectedOptions);
      }
      
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          console.log(`Получен аудио чанк размером: ${event.data.size} байт`);
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        console.log('Запись остановлена, обрабатываю аудио...');
        console.log(`Количество чанков: ${audioChunksRef.current.length}`);
        console.log(`Общий размер чанков: ${audioChunksRef.current.reduce((sum, chunk) => sum + chunk.size, 0)} байт`);
        
        setIsProcessing(true);
        
        try {
          // Создаем Blob из записанных чанков
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
          console.log(`Создан Blob размером: ${audioBlob.size} байт, тип: ${audioBlob.type}`);
          
          // Проверяем размер аудио данных
          if (audioBlob.size < 100) {
            showNotification('warning', 'Запись слишком короткая, попробуйте еще раз');
            setIsProcessing(false);
            return;
          }
          
          // Отправляем аудио через WebSocket для real-time обработки
          if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
            console.log(`Отправляю аудио через WebSocket размером: ${audioBlob.size} байт`);
            voiceSocket.send(audioBlob);
            showNotification('info', 'Отправляю голос на обработку...');
          } else {
            // Fallback на старый метод, если WebSocket не работает
            console.log('WebSocket не подключен, использую fallback...');
            showNotification('warning', 'WebSocket не подключен, использую fallback...');
            await processAudio(audioBlob);
            setIsProcessing(false);
          }
        } catch (error) {
          console.error('Ошибка обработки аудио:', error);
          showNotification('error', 'Ошибка обработки аудио');
          setIsProcessing(false);
        }
      };

      mediaRecorderRef.current.onerror = (event) => {
        showNotification('error', 'Ошибка записи аудио');
        setIsRecording(false);
      };

      mediaRecorderRef.current.start(1000); // Записываем по 1 секунде
      console.log('Запись началась, MediaRecorder запущен');
      setIsRecording(true);
      
      // Запускаем отслеживание аудио уровня и тишины
      updateAudioLevel();
      
      showNotification('info', 'Запись началась. Говорите...');
       
     } catch (error) {
        const errorObj = error as any;
        if (errorObj?.name === 'NotAllowedError') {
          showNotification('error', 'Доступ к микрофону заблокирован. Разрешите доступ в браузере.');
        } else if (errorObj?.name === 'NotFoundError') {
          showNotification('error', 'Микрофон не найден');
        } else {
          showNotification('error', 'Не удалось получить доступ к микрофону');
        }
        setIsRecording(false);
      }
  };

  const stopRecording = (): void => {
    console.log('Остановка записи...');
    
    // Отключаем автопереподключение WebSocket
    setShouldReconnect(false);
    
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
      console.log('📱 MediaRecorder остановлен');
    }
    
    // Останавливаем медиа поток
    if (currentStreamRef.current) {
      currentStreamRef.current.getTracks().forEach(track => {
        track.stop();
        console.log('Аудио трек остановлен:', track.kind, track.label);
      });
      currentStreamRef.current = null;
    }
    
    // Останавливаем анимацию
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
      console.log('Анимация остановлена');
    }
    
    // Закрываем аудио контекст
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
      console.log('Аудио контекст закрыт');
    }
    
    // Останавливаем таймер тишины
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
      console.log('Таймер тишины остановлен');
    }
    
    setIsRecording(false);
    setAudioLevel(0);
    setRealtimeText('');
    setRecordingTime(0);
    
    console.log('Запись полностью остановлена');
    showNotification('info', 'Прослушивание остановлено');
    
    // WebSocket остается активным для следующего использования, но переподключение отключено
  };

  // Обновляем функцию updateAudioLevel для отслеживания тишины
  const updateAudioLevel = () => {
    if (analyserRef.current && isRecording) {
      analyserRef.current.getByteFrequencyData(new Uint8Array(analyserRef.current.frequencyBinCount));
      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
      analyserRef.current.getByteFrequencyData(dataArray);
      
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
      const normalizedLevel = average / 255;
      
      setAudioLevel(normalizedLevel);
      lastAudioLevelRef.current = normalizedLevel;
      
      // Проверяем тишину
      checkSilence();
      
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
    }
  };

  const processAudio = async (audioBlob: Blob): Promise<void> => {
    if (!isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }

    console.log('Fallback: Обрабатываю аудио через HTTP API');
    setIsProcessing(true);
    
    try {
      // Отправляем аудио на сервер для распознавания
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'recording.wav');

      console.log('Fallback: Отправляю аудио на сервер для распознавания');
      const response = await fetch('http://localhost:8000/api/voice/recognize', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Fallback: Ошибка распознавания:', response.status, errorText);
        showNotification('error', `Ошибка распознавания: ${response.status}`);
        return;
      }

      const result = await response.json();
      console.log('Fallback: Результат распознавания:', result);
      
      if (result.success) {
        const recognizedText = result.text;
        console.log('РАСПОЗНАННЫЙ ТЕКСТ (Fallback):', recognizedText);
        console.log('ОТЛАДКА: Используется fallback метод, распознанный текст будет отправлен в LLM');
        setRecordedText(recognizedText);
        
        if (recognizedText && recognizedText.trim()) {
          showNotification('success', 'Речь распознана');
          console.log('ОТПРАВЛЯЮ В LLM (Fallback):', recognizedText);
          // Автоматически отправляем распознанный текст на обработку
          await sendVoiceMessage(recognizedText);
        } else {
          showNotification('warning', 'Речь не распознана. Попробуйте еще раз.');
        }
      } else {
        showNotification('error', 'Ошибка распознавания речи');
      }
    } catch (error) {
      console.error('Fallback: Ошибка обработки аудио:', error);
      showNotification('error', 'Ошибка подключения к серверу распознавания');
    } finally {
      setIsProcessing(false);
    }
  };

  const sendVoiceMessage = async (text: string) => {
    try {
      console.log('ОТПРАВЛЯЮ В LLM:', text);
      console.log('ОТЛАДКА: Данные для LLM - сообщение:', text);
      
      // Отправляем текст в чат
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          streaming: false,
        }),
      });

      const result = await response.json();
      console.log('ОТВЕТ ОТ LLM:', result.response);
      console.log('ОТЛАДКА: LLM вернул результат, начинаю синтез речи');
      
      if (result.success) {
        console.log('Ответ LLM успешно получен, синтезирую речь');
        // Синтезируем речь из ответа
        await synthesizeSpeech(result.response);
      } else {
        console.error('Ошибка получения ответа от LLM:', result);
        showNotification('error', 'Ошибка получения ответа от Газик ИИ');
      }
    } catch (error) {
      console.error('Ошибка отправки голосового сообщения:', error);
      showNotification('error', 'Ошибка отправки сообщения');
    }
  };

  const synthesizeSpeech = async (text: string) => {
    if (!text.trim()) return;

    console.log('synthesizeSpeech вызвана с текстом:', text);
    console.log('Текущие настройки голоса:', voiceSettings);
    console.log('Значение speech_rate:', voiceSettings.speech_rate, 'тип:', typeof voiceSettings.speech_rate);

    // Останавливаем предыдущее воспроизведение
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = '';
      currentAudioRef.current = null;
    }

    setIsSpeaking(true);
    
    try {
      const requestBody = {
        text: text,
        voice_id: voiceSettings.voice_id,
        voice_speaker: voiceSettings.voice_speaker,
        speech_rate: voiceSettings.speech_rate
      };
      
      console.log('Отправляю запрос на синтез речи:', requestBody);
      console.log('Проверяю speech_rate в requestBody:', requestBody.speech_rate, 'тип:', typeof requestBody.speech_rate);
      
      const response = await fetch('http://localhost:8000/api/voice/synthesize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        console.log('Получен аудио ответ размером:', audioBlob.size, 'байт');
        
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        currentAudioRef.current = audio;
        
        audio.onended = () => {
          setIsSpeaking(false);
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
          console.log('Синтезированная речь воспроизведена полностью');
        };
        
        audio.onerror = () => {
          setIsSpeaking(false);
          showNotification('error', 'Ошибка воспроизведения речи');
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
          console.error('Ошибка воспроизведения синтезированной речи');
        };
        
        await audio.play();
        console.log('Начато воспроизведение синтезированной речи');
      } else {
        const errorText = await response.text();
        console.error('Ошибка синтеза речи:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
    } catch (error) {
      console.error('Ошибка синтеза речи:', error);
      showNotification('error', 'Ошибка синтеза речи');
      setIsSpeaking(false);
    }
  };

  const handleManualSend = () => {
    if (recordedText.trim()) {
      sendVoiceMessage(recordedText);
      setRecordedText('');
    }
  };

  // Функция для сохранения настроек голоса в localStorage
  const saveVoiceSettings = (settings: typeof voiceSettings) => {
    console.log('Сохраняю настройки голоса в localStorage:', settings);
    localStorage.setItem('voice_speaker', settings.voice_speaker);
    localStorage.setItem('voice_id', settings.voice_id);
    localStorage.setItem('speech_rate', settings.speech_rate.toString());
    console.log('Настройки голоса сохранены в localStorage:', settings);
    console.log('Проверяю сохраненное значение speech_rate:', localStorage.getItem('speech_rate'));
  };

  // Функция для переключения голоса
  const switchVoice = (direction: 'next' | 'prev') => {
    const voices = Object.keys(voiceTestMessages);
    let newIndex;
    
    if (direction === 'next') {
      newIndex = currentVoiceIndex === voices.length - 1 ? 0 : currentVoiceIndex + 1;
    } else {
      newIndex = currentVoiceIndex === 0 ? voices.length - 1 : currentVoiceIndex - 1;
    }
    
    const newVoice = voices[newIndex];
    
    // Останавливаем предыдущее воспроизведение перед переключением
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = '';
      currentAudioRef.current = null;
    }
    
    // Сбрасываем состояние воспроизведения
    setIsSpeaking(false);
    setCurrentTestVoice(null);
    
    setCurrentVoiceIndex(newIndex);
    const newSettings = { ...voiceSettings, voice_speaker: newVoice };
    setVoiceSettings(newSettings);
    saveVoiceSettings(newSettings); // Сохраняем в localStorage
    console.log('Переключение голоса: newIndex =', newIndex, 'newVoice =', newVoice);
    testVoice(newVoice);
  };

  // Функция тестирования голоса
  const testVoice = async (voiceName: string) => {
    try {
      console.log('testVoice вызвана для голоса:', voiceName);
      console.log('Текущие настройки голоса:', voiceSettings);
      console.log('Значение speech_rate:', voiceSettings.speech_rate, 'тип:', typeof voiceSettings.speech_rate);
      
      // Останавливаем предыдущее воспроизведение
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = '';
        currentAudioRef.current = null;
      }
      
      // Сбрасываем состояние воспроизведения, но НЕ устанавливаем isSpeaking для тестирования
      setCurrentTestVoice(voiceName);
      
      // Используем предзаписанное сообщение для быстрого тестирования
      const testMessage = voiceTestMessages[voiceName as keyof typeof voiceTestMessages];
      
      const requestBody = {
        text: testMessage,
        voice_id: voiceSettings.voice_id,
        voice_speaker: voiceName,
        speech_rate: voiceSettings.speech_rate
      };
      
      console.log('Отправляю тестовый запрос на синтез речи:', requestBody);
      console.log('Проверяю speech_rate в тестовом requestBody:', requestBody.speech_rate, 'тип:', typeof requestBody.speech_rate);
      
      const response = await fetch('http://localhost:8000/api/voice/synthesize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        console.log('Воспроизведение тестового аудио...');
        
        audio.onended = () => {
          console.log('Тестирование голоса завершено');
          setCurrentTestVoice(null);
          // НЕ устанавливаем setIsSpeaking(false) для тестирования
          URL.revokeObjectURL(audioUrl);
        };
        
        audio.onerror = () => {
          console.error('Ошибка воспроизведения тестового голоса');
          setCurrentTestVoice(null);
          // НЕ устанавливаем setIsSpeaking(false) для тестирования
          showNotification('error', 'Ошибка воспроизведения тестового голоса');
          URL.revokeObjectURL(audioUrl);
        };
        
        // Сохраняем ссылку на текущий аудио элемент
        currentAudioRef.current = audio;
        
        try {
          await audio.play();
          console.log('Тестовое аудио успешно запущено');
          // НЕ устанавливаем setIsSpeaking(true) для тестирования
          showNotification('success', `Тестирую голос ${voiceName}...`);
        } catch (playError) {
          console.error('Ошибка запуска воспроизведения:', playError);
          showNotification('error', 'Ошибка запуска воспроизведения тестового голоса');
          setCurrentTestVoice(null);
        }
      } else {
        const errorText = await response.text();
        console.error('Ошибка тестирования голоса:', response.status, errorText);
        setCurrentTestVoice(null);
        // НЕ устанавливаем setIsSpeaking(false) для тестирования
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
    } catch (error) {
      console.error('Ошибка тестирования голоса:', error);
      setCurrentTestVoice(null);
      // НЕ устанавливаем setIsSpeaking(false) для тестирования
      showNotification('error', `Ошибка тестирования голоса: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
    }
  };

  // Таймер записи и real-time распознавание
  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingTime(prev => prev + 1);
        
        // Каждые 2 секунды отправляем текущий чанк для real-time распознавания
        if (recordingTime > 0 && recordingTime % 2 === 0 && audioChunksRef.current.length > 0) {
          sendRealtimeChunk();
        }
      }, 1000);
    } else {
      setRecordingTime(0);
      setRealtimeText(''); // Очищаем real-time текст при остановке
    }
    
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [isRecording, recordingTime]);

  // Обновление глобального состояния
  useEffect(() => {
    setRecording(isRecording);
  }, [isRecording]);
  
  useEffect(() => {
    setSpeaking(isSpeaking);
  }, [isSpeaking]);

  // Очистка ресурсов при размонтировании компонента
  useEffect(() => {
    return () => {
      // Очищаем только аудио ресурсы, WebSocket оставляем активным
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
        mediaRecorderRef.current = null;
      }
      if (currentStreamRef.current) {
        currentStreamRef.current.getTracks().forEach(track => track.stop());
        currentStreamRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = '';
        currentAudioRef.current = null;
      }
      // Сбрасываем глобальное состояние
      setRecording(false);
      setSpeaking(false);
    };
  }, []); // Убираем зависимости, чтобы избежать бесконечного цикла

  // Принудительная очистка при любых попытках навигации
  useEffect(() => {
    // Обработчик события beforeunload для принудительной очистки
    const handleBeforeUnload = () => {
      // Очищаем только аудио ресурсы, WebSocket оставляем активным
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
        mediaRecorderRef.current = null;
      }
      if (currentStreamRef.current) {
        currentStreamRef.current.getTracks().forEach(track => track.stop());
        currentStreamRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = '';
        currentAudioRef.current = null;
      }
      setRecording(false);
      setSpeaking(false);
    };

    // Добавляем обработчик
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    // Очистка при размонтировании компонента
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Очищаем только аудио ресурсы, WebSocket оставляем активным
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
        mediaRecorderRef.current = null;
      }
      if (currentStreamRef.current) {
        currentStreamRef.current.getTracks().forEach(track => track.stop());
        currentStreamRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = '';
        currentAudioRef.current = null;
      }
      setRecording(false);
      setSpeaking(false);
    };
  }, []); // Убираем зависимости, чтобы избежать бесконечного цикла

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
    ];

    if (!allowedTypes.includes(file.type)) {
      showNotification('error', 'Поддерживаются только файлы PDF, Word (.docx), Excel (.xlsx) и TXT');
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
        const result: any = await response.json();
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
              console.log('Список документов обновлен:', files);
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
          console.error('Ошибка при обновлении списка документов:', error);
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
      console.error('Ошибка при загрузке файла:', error);
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
      console.error('Ошибка при удалении файла:', error);
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

  const handleReconnect = (): void => {
    reconnect();
    handleMenuClose();
  };

  const handleStopGeneration = (): void => {
    // Останавливаем генерацию через WebSocket
    stopGeneration();
    showNotification('info', 'Генерация остановлена');
  };

  // ================================
  // КОМПОНЕНТЫ СООБЩЕНИЙ
  // ================================

    const MessageCard = ({ message }: { message: Message }): React.ReactElement => {
    const isUser = message.role === 'user';
    const [isHovered, setIsHovered] = useState(false);
    
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
          mb: 1.5, /* Увеличиваем отступ между сообщениями (соответствует CSS margin-bottom: 28px) */
          width: '100%',
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <Card
          className="message-bubble"
          data-theme={isDarkMode ? 'dark' : 'light'}
          sx={{
            maxWidth: '75%',
            minWidth: '180px',
            backgroundColor: isUser 
              ? 'primary.main' 
              : isDarkMode ? 'background.paper' : '#f8f9fa',
            color: isUser ? 'primary.contrastText' : isDarkMode ? 'text.primary' : '#333',
            boxShadow: isDarkMode 
              ? '0 2px 8px rgba(0, 0, 0, 0.15)' 
              : '0 2px 8px rgba(0, 0, 0, 0.1)',
          }}
        >
          <CardContent sx={{ p: 1.2, pb: 0.8 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.3 }}>
              <Avatar
                sx={{
                  width: 24,
                  height: 24,
                  mr: 1,
                  bgcolor: isUser ? 'primary.dark' : 'secondary.main',
                }}
              >
                {isUser ? <PersonIcon /> : <BotIcon />}
              </Avatar>
                             <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}>
                 {isUser ? 'Вы' : 'Газик ИИ'}
               </Typography>
              <Typography variant="caption" sx={{ ml: 'auto', opacity: 0.6, fontSize: '0.7rem' }}>
                {formatTimestamp(message.timestamp)}
              </Typography>
            </Box>
            
            <Box sx={{ mb: 0.3 }}>
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
                          <MessageRenderer content={response.content} isStreaming={response.isStreaming} />
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              ) : (
                // Обычное отображение одного ответа
                <MessageRenderer content={message.content} isStreaming={message.isStreaming} />
              )}
            </Box>
          </CardContent>
        </Card>
        
        {/* Кнопка копирования снизу карточки - для всех сообщений при наведении */}
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'center',
          mt: 1,
          height: 20, /* Фиксированная высота для кнопки */
          opacity: isHovered ? 1 : 0, /* Мгновенное появление/исчезновение */
          visibility: isHovered ? 'visible' : 'hidden', /* Скрываем кнопку, но сохраняем место */
        }}>
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
                 /* Убираем hover эффекты, чтобы кнопка была статичной */
               }}
            >
              <CopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    );
  };

  // ================================
  // ДИАЛОГИ
  // ================================

  const VoiceDialog = (): React.ReactElement => (
    <Dialog
      open={showVoiceDialog}
      onClose={() => setShowVoiceDialog(false)}
      maxWidth="md"
      fullWidth
      TransitionComponent={undefined}
      transitionDuration={0}
      PaperProps={{
        sx: {
          bgcolor: 'background.paper',
          borderRadius: 3,
        }
      }}
    >
      <DialogTitle sx={{ textAlign: 'center', pb: 1 }}>
        Голосовой чат
      </DialogTitle>
      <DialogContent sx={{ textAlign: 'center', py: 3 }}>
        {/* Индикатор подключения WebSocket */}
        <Box sx={{ mb: 3, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              backgroundColor: isVoiceConnected ? 'success.main' : 'warning.main',
              animation: isVoiceConnected ? 'pulse 2s ease-in-out infinite' : 'none',
              border: isVoiceConnected ? '2px solid rgba(76, 175, 80, 0.3)' : '2px solid rgba(255, 152, 0, 0.3)',
            }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
            {isVoiceConnected ? 'Real-Time Голосовой Чат' : 'WebSocket подключится при записи'}
          </Typography>
        </Box>

        {/* Кнопка настроек голоса - в левом нижнем углу */}
        <Box sx={{ 
          position: 'absolute', 
          bottom: 20, 
          left: 20,
          zIndex: 10
        }}>
          <Tooltip title="Настройки голоса">
            <IconButton
              onClick={() => setShowVoiceSettings(!showVoiceSettings)}
              sx={{
                color: 'primary.main',
                bgcolor: 'background.default',
                border: '2px solid',
                borderColor: 'primary.main',
                width: 48,
                height: 48,
                '&:hover': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  transform: 'scale(1.05)',
                },
                transition: 'all 0.3s ease',
                animation: showVoiceSettings ? 'spin 2s linear infinite' : 'none',
                '@keyframes spin': {
                  '0%': { transform: 'rotate(0deg)' },
                  '100%': { transform: 'rotate(360deg)' },
                },
              }}
            >
              <SettingsIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Кнопка остановки всех процессов - справа на уровне кнопки настроек */}
        <Box sx={{ 
          position: 'absolute', 
          bottom: 20, 
          right: 20,
          zIndex: 10
        }}>
          {(isRecording || isProcessing || isSpeaking || (voiceSocket && voiceSocket.readyState === WebSocket.OPEN)) && (
            <Tooltip title="Остановить все процессы">
              <IconButton
                onClick={cleanupVoiceResources}
                sx={{
                  color: 'error.main',
                  bgcolor: 'background.default',
                  border: '2px solid',
                  borderColor: 'error.main',
                  width: 48,
                  height: 48,
                  '&:hover': {
                    bgcolor: 'error.main',
                    color: 'white',
                    transform: 'scale(1.05)',
                  },
                  transition: 'all 0.3s ease',
                }}
              >
                <StopIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Меню выбора голоса - скрыто по умолчанию */}
        <Collapse in={showVoiceSettings}>
          <Card sx={{ mb: 3, p: 2, backgroundColor: 'background.default' }}>
            <Typography variant="subtitle2" color="primary" gutterBottom sx={{ textAlign: 'center', mb: 3 }}>
              Выберите голос:
            </Typography>
            
            {/* Слайдер с кружками */}
            <Box sx={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              gap: 1,
              position: 'relative',
              height: 120,
              overflow: 'hidden'
            }}>
              {/* Стрелка влево - максимально близко к левому кругу */}
              <IconButton
                onClick={() => switchVoice('prev')}
                sx={{ 
                  color: 'text.secondary',
                  '&:hover': { color: 'primary.main' },
                  zIndex: 2,
                  position: 'absolute',
                  left: 220,
                  top: '50%',
                  transform: 'translateY(-50%)'
                }}
              >
                <ChevronLeftIcon />
              </IconButton>

              {/* Контейнер для кружков - центрируем точно над счетчиком */}
              <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 2,
                position: 'relative',
                width: 400,
                height: 100,
                mx: 'auto', // Центрируем контейнер
                ml: '168px' // Сдвигаем левее для совпадения с счетчиком
              }}>
                {Object.entries(voiceTestMessages).map(([voiceKey, testMessage], index) => {
                  const isSelected = voiceSettings.voice_speaker === voiceKey;
                  const isPlaying = isSpeaking && currentTestVoice === voiceKey;
                  
                                     // Вычисляем позицию и размер для каждого кружка
                   const distance = Math.abs(index - currentVoiceIndex);
                   let size, opacity, scale, zIndex, translateX;
                   
                   // Отладочная информация для всех кружков
                   console.log(`Кружок ${voiceKey}: index = ${index}, currentVoiceIndex = ${currentVoiceIndex}, distance = ${distance}`);
                   
                   if (distance === 0) {
                     // Активный кружок - большой и по центру
                     size = 80;
                     opacity = 1;
                     scale = 1;
                     zIndex = 3;
                     translateX = 0;
                     console.log(`${voiceKey} - АКТИВНЫЙ: size = ${size}, opacity = ${opacity}, scale = ${scale}`);
                   } else if (distance === 1) {
                     // Соседние кружки - средние и по бокам
                     size = 60;
                     opacity = 0.7;
                     scale = 0.8;
                     zIndex = 2;
                     translateX = index < currentVoiceIndex ? -62 : 81; // Одинаковое расстояние в обе стороны
                     console.log(`${voiceKey} - Соседний: size = ${size}, opacity = ${opacity}, scale = ${scale}`);
                   } else {
                     // Дальние кружки - маленькие и на заднем плане
                     size = 40;
                     opacity = 0.3;
                     scale = 0.6;
                     zIndex = 1;
                     translateX = index < currentVoiceIndex ? -95 : 134 // Одинаковое расстояние в обе стороны
                     console.log(`${voiceKey} - Дальний: size = ${size}, opacity = ${opacity}, scale = ${scale}`);
                   }
                  
                  return (
                    <Box
                      key={voiceKey}
                      sx={{
                        position: 'absolute',
                        left: '50%',
                        transform: `translateX(${translateX}px)`,
                        cursor: 'pointer',
                        transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                        zIndex,
                      }}
                      onClick={() => {
                        setCurrentVoiceIndex(index);
                        const newSettings = { ...voiceSettings, voice_speaker: voiceKey };
                        setVoiceSettings(newSettings);
                        saveVoiceSettings(newSettings); // Сохраняем в localStorage
                        console.log('Клик по кружку: index =', index, 'voiceKey =', voiceKey);
                        testVoice(voiceKey);
                      }}
                    >
                      {/* Основной круг с анимацией переливания */}
                      <Box
                        sx={{
                          width: size,
                          height: size,
                          borderRadius: '50%',
                          background: isSelected 
                            ? 'linear-gradient(135deg, #ff6b9d 0%, #c44569 50%, #ff6b9d 100%)'
                            : 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #667eea 100%)',
                          backgroundSize: '200% 200%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          boxShadow: isSelected 
                            ? '0 8px 25px rgba(255, 107, 157, 0.4)'
                            : '0 4px 15px rgba(102, 126, 234, 0.3)',
                          transition: 'all 0.3s ease',
                          opacity,
                          transform: `scale(${scale})`,
                          outline: 'none',
                          border: 'none',
                          animation: isSelected 
                            ? 'gradientShift 3s ease-in-out infinite, float 2s ease-in-out infinite'
                            : 'gradientShift 4s ease-in-out infinite',
                          '@keyframes gradientShift': {
                            '0%': { backgroundPosition: '0% 50%' },
                            '50%': { backgroundPosition: '100% 50%' },
                            '100%': { backgroundPosition: '0% 50%' },
                          },
                          '@keyframes float': {
                            '0%, 100%': { transform: `scale(${scale}) translateY(0px)` },
                            '50%': { transform: `scale(${scale}) translateY(-3px)` },
                          },
                          '&:hover': {
                            transform: `scale(${scale * 1.05})`,
                            boxShadow: isSelected 
                              ? '0 12px 35px rgba(255, 107, 157, 0.6)'
                              : '0 8px 25px rgba(102, 126, 234, 0.5)',
                            animation: 'gradientShift 1.5s ease-in-out infinite, float 1s ease-in-out infinite',
                            outline: 'none',
                            border: 'none',
                          },
                          '&:focus': {
                            outline: 'none',
                            border: 'none',
                          }
                        }}
                      >
                        {/* Добавляем внутренний блеск */}
                        <Box
                          sx={{
                            position: 'absolute',
                            top: '15%',
                            left: '15%',
                            width: '30%',
                            height: '30%',
                            borderRadius: '50%',
                            background: 'radial-gradient(circle, rgba(255,255,255,0.4) 0%, transparent 70%)',
                            animation: 'sparkle 2s ease-in-out infinite',
                            '@keyframes sparkle': {
                              '0%, 100%': { opacity: 0.4, transform: 'scale(1)' },
                              '50%': { opacity: 0.8, transform: 'scale(1.2)' },
                            }
                          }}
                        />
                      </Box>

                      {/* Индикатор воспроизведения */}
                      {isPlaying && (
                        <Box
                          sx={{
                            position: 'absolute',
                            top: -5,
                            right: -5,
                            width: 20,
                            height: 20,
                            borderRadius: '50%',
                            backgroundColor: 'success.main',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            animation: 'pulse 1s infinite',
                            '@keyframes pulse': {
                              '0%': { transform: 'scale(1)', opacity: 1 },
                              '50%': { transform: 'scale(1.2)', opacity: 0.7 },
                              '100%': { transform: 'scale(1)', opacity: 1 },
                            }
                          }}
                        >
                          <VolumeUpIcon sx={{ fontSize: 12, color: 'white' }} />
                        </Box>
                      )}

                      {/* Название голоса - показываем только для активного */}
                      {isSelected && (
                        <Typography
                          variant="caption"
                          sx={{
                            textAlign: 'center',
                            mt: 1,
                            display: 'block',
                            fontWeight: 'bold',
                            color: 'primary.main',
                            opacity: 1,
                            fontSize: size * 0.2,
                            whiteSpace: 'nowrap'
                          }}
                        >
                          {voiceKey === 'baya' && 'Baya'}
                          {voiceKey === 'xenia' && 'Xenia'}
                          {voiceKey === 'kseniya' && 'Kseniya'}
                          {voiceKey === 'aidar' && 'Aidar'}
                          {voiceKey === 'eugene' && 'Eugene'}
                        </Typography>
                      )}                    
                    </Box>
                  );
                })}
              </Box>

              {/* Стрелка вправо - максимально близко к правому кругу */}
              <IconButton
                onClick={() => switchVoice('next')}
                sx={{ 
                  color: 'text.secondary',
                  '&:hover': { color: 'primary.main' },
                  zIndex: 2,
                  position: 'absolute',
                  right: 220,
                  top: '50%',
                  transform: 'translateY(-50%)'
                }}
              >
                <ChevronRightIcon />
              </IconButton>
            </Box>

            {/* Индикатор текущего выбора */}
            <Box sx={{ textAlign: 'center', mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                {currentVoiceIndex + 1} / {Object.keys(voiceTestMessages).length}
              </Typography>
            </Box>

            {/* Настройка скорости речи ассистента */}
            <Box sx={{ mt: 3, px: 2 }}>
              <Typography variant="subtitle2" color="primary" gutterBottom sx={{ textAlign: 'center', mb: 2 }}>
                Скорость речи ассистента:
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 40 }}>
                  Медленно
                </Typography>
                <Slider
                  value={voiceSettings.speech_rate}
                  onChange={(_, value) => {
                    const newSettings = { ...voiceSettings, speech_rate: value as number };
                    console.log('Слайдер скорости речи изменен:', {
                      старое_значение: voiceSettings.speech_rate,
                      новое_значение: value,
                      тип_значения: typeof value
                    });
                    setVoiceSettings(newSettings);
                    saveVoiceSettings(newSettings);
                    console.log('Новые настройки установлены:', newSettings);
                  }}
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  marks={[
                    { value: 0.5, label: '0.5x' },
                    { value: 1.0, label: '1.0x' },
                    { value: 1.5, label: '1.5x' },
                    { value: 2.0, label: '2.0x' }
                  ]}
                  valueLabelDisplay="auto"
                  sx={{
                    flex: 1,
                    '& .MuiSlider-mark': {
                      backgroundColor: 'primary.main',
                    },
                    '& .MuiSlider-markLabel': {
                      color: 'text.secondary',
                      fontSize: '0.75rem',
                    },
                    '& .MuiSlider-valueLabel': {
                      backgroundColor: 'primary.main',
                      color: 'white',
                    }
                  }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 40 }}>
                  Быстро
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center', display: 'block' }}>
                Текущая скорость: {voiceSettings.speech_rate.toFixed(1)}x
              </Typography>
              
              {/* Кнопка тестирования скорости речи */}
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<VolumeUpIcon />}
                  onClick={() => {
                    const testMessage = "Это тест скорости речи ассистента. Настройте скорость по вашему вкусу.";
                    synthesizeSpeech(testMessage);
                  }}
                  disabled={isSpeaking}
                  sx={{
                    fontSize: '0.75rem',
                    px: 2,
                    py: 0.5,
                    borderColor: 'primary.main',
                    color: 'primary.main',
                    '&:hover': {
                      borderColor: 'primary.dark',
                      backgroundColor: 'primary.light',
                      color: 'primary.dark',
                    }
                  }}
                >
                  Тестировать скорость
                </Button>
              </Box>
            </Box>
          </Card>
        </Collapse>

        {!isRecording ? (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Нажмите кнопку микрофона для начала записи
            </Typography>
            <IconButton
              size="large"
              onClick={startRecording}
              disabled={state.isLoading && !messages.some(msg => msg.isStreaming)}
              sx={{
                width: 80,
                height: 80,
                bgcolor: 'primary.main',
                color: 'white',
                '&:hover': { bgcolor: 'primary.dark' },
                '&:disabled': {
                  bgcolor: 'action.disabledBackground',
                  color: 'action.disabled',
                },
              }}
            >
              <MicIcon sx={{ fontSize: 40 }} />
            </IconButton>
          </Box>
        ) : (
          <Box>
            {/* Визуализация аудио */}
            <Box sx={{ mb: 4, position: 'relative', display: 'inline-block' }}>
              <Box
                sx={{
                  width: 200,
                  height: 200,
                  borderRadius: '50%',
                  background: isRecording
                    ? `conic-gradient(#f44336 ${audioLevel * 360}deg, #e0e0e0 0deg)`
                    : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  animation: isRecording ? 'pulse 1.5s ease-in-out infinite' : 'none',
                  transition: 'all 0.3s ease',
                  '@keyframes pulse': {
                    '0%': { transform: 'scale(1)', opacity: 1 },
                    '50%': { transform: 'scale(1.2)', opacity: 0.7 },
                    '100%': { transform: 'scale(1)', opacity: 1 },
                  },
                }}
              >
                <IconButton
                  onClick={stopRecording}
                  disabled={isProcessing || isSpeaking}
                  sx={{
                    width: 120,
                    height: 120,
                    backgroundColor: 'white',
                    color: 'error.main',
                    '&:hover': {
                      backgroundColor: 'grey.100',
                    },
                  }}
                >
                  <StopIcon sx={{ fontSize: 48 }} />
                </IconButton>
              </Box>

              {/* Индикаторы состояния */}
              {isProcessing && (
                <Box sx={{ position: 'absolute', top: -10, right: -10 }}>
                  <CircularProgress size={24} color="secondary" />
                </Box>
              )}
              
              {isSpeaking && (
                <Box sx={{ position: 'absolute', bottom: -10, right: -10 }}>
                  <Box sx={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 0.5,
                    height: 32
                  }}>
                    {[...Array(5)].map((_, index) => (
                      <Box
                        key={index}
                        sx={{
                          width: 4,
                          height: 16,
                          background: 'linear-gradient(180deg, #4caf50 0%, #66bb6a 50%, #81c784 100%)',
                          borderRadius: 2,
                          animation: 'soundWave 1s infinite ease-in-out',
                          animationDelay: `${index * 0.1}s`,
                          boxShadow: '0 2px 6px rgba(76, 175, 80, 0.4)',
                          '@keyframes soundWave': {
                            '0%, 100%': { 
                              transform: 'scaleY(0.2)',
                              opacity: 0.6
                            },
                            '50%': { 
                              transform: 'scaleY(1)',
                              opacity: 1
                            },
                          },
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              )}
            </Box>

            {/* Статус записи */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" color="error.main" gutterBottom>
                Прослушивание... {Math.floor(recordingTime / 60)}:{(recordingTime % 60).toString().padStart(2, '0')}
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'error.main', animation: 'pulse 1s infinite' }} />
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'error.main', animation: 'pulse 1s infinite', animationDelay: '0.2s' }} />
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'error.main', animation: 'pulse 1s infinite', animationDelay: '0.4s' }} />
              </Box>
            </Box>

            {/* Инструкции */}
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              Говорите четко и ясно. Real-time распознавание каждые 2 секунды. Автоматическая остановка через 5 секунд тишины.
            </Typography>
          </Box>
        )}
        
        {/* Real-time распознавание */}
        {isRecording && realtimeText && (
          <Card sx={{ mb: 3, p: 2, backgroundColor: 'warning.light' }}>
            <Typography variant="subtitle2" color="warning.dark" gutterBottom>
              Real-time распознавание (каждые 2 сек):
            </Typography>
            <Typography variant="body1" sx={{ fontStyle: 'italic', color: 'warning.dark' }}>
              "{realtimeText}"
            </Typography>
          </Card>
        )}

        {/* Финальный распознанный текст */}
        {recordedText && (
          <Card sx={{ mb: 3, p: 2, backgroundColor: 'background.default' }}>
            <Typography variant="subtitle2" color="primary" gutterBottom>
              Финальный распознанный текст:
            </Typography>
            <Typography variant="body1" sx={{ fontStyle: 'italic' }}>
              "{recordedText}"
            </Typography>
            <Box sx={{ mt: 2, display: 'flex', gap: 1, justifyContent: 'center' }}>
              <Button
                variant="contained"
                startIcon={<SendIcon />}
                onClick={handleManualSend}
                disabled={isProcessing || isSpeaking}
              >
                Отправить
              </Button>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={() => setRecordedText('')}
              >
                Очистить
              </Button>
            </Box>
          </Card>
        )}

        {/* Индикатор загрузки */}
        {isProcessing && (
          <Box sx={{ mb: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="primary" sx={{ mb: 1 }}>
              Ассистент думает...
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.5 }}>
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: 'primary.main',
                  animation: 'thinkingDot 1.4s ease-in-out infinite both',
                  '@keyframes thinkingDot': {
                    '0%, 80%, 100%': { transform: 'scale(0)' },
                    '40%': { transform: 'scale(1)' },
                  },
                }}
              />
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: 'primary.main',
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
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: 'primary.main',
                  animation: 'thinkingDot 1.4s ease-in-out infinite both',
                  animationDelay: '0.4s',
                  '@keyframes thinkingDot': {
                    '0%, 80%, 100%': { transform: 'scale(0)' },
                    '40%': { transform: 'scale(1)' },
                  },
                }}
              />
            </Box>
          </Box>
        )}

        {/* Индикатор речи */}
        {isSpeaking && (
          <Box sx={{ mb: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="success.main" sx={{ mb: 1 }}>
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
              {[...Array(9)].map((_, index) => (
                <Box
                  key={index}
                  sx={{
                    width: 4,
                    height: 22,
                    background: 'linear-gradient(180deg, #4caf50 0%, #66bb6a 50%, #81c784 100%)',
                    borderRadius: 2,
                    animation: 'soundWave2 1.2s infinite ease-in-out',
                    animationDelay: `${index * 0.08}s`,
                    boxShadow: '0 3px 8px rgba(76, 175, 80, 0.5)',
                    '@keyframes soundWave2': {
                      '0%, 100%': { 
                        transform: 'scaleY(0.3)',
                        opacity: 0.5
                      },
                      '50%': { 
                        transform: 'scaleY(1)',
                        opacity: 1
                      },
                    },
                  }}
                />
              ))}
            </Box>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ justifyContent: 'center', pb: 3 }}>
        <Button onClick={() => setShowVoiceDialog(false)}>
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );

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
            Поддерживаются PDF, Word, Excel и текстовые файлы до 50MB
          </Typography>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.txt"
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
            // Находим текущий ответ для этой модели (последний запрос)
            const currentResponse = conversationHistory.length > 0 
              ? conversationHistory[conversationHistory.length - 1].responses.find(r => r.model === window.selectedModel)
              : null;
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
                                  <MessageRenderer content={response.content} />
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
          {/* Объединенное поле ввода с кнопками */}
          <Box
            sx={{
              p: 2,
              borderRadius: 2,
              bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
              border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
              maxWidth: '800px',
              width: '100%',
            }}
          >
            {/* Скрытый input для выбора файла */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.xlsx,.txt"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />

            {/* Прикрепленные файлы - выше поля ввода */}
            {uploadedFiles.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {uploadedFiles.map((file, index) => (
                    <Box
                      key={index}
                      className="file-attachment"
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        p: 1,
                        borderRadius: 2,
                        maxWidth: '300px',
                        bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                        border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'}`,
                      }}
                    >
                      <Box
                        sx={{
                          width: 32,
                          height: 32,
                          borderRadius: 1,
                          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: isDarkMode ? 'white' : '#333',
                          flexShrink: 0,
                          border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)'}`,
                        }}
                      >
                        {file.type.includes('pdf') ? <PdfIcon fontSize="small" /> : 
                         file.type.includes('word') ? <DocumentIcon fontSize="small" /> : 
                         file.type.includes('excel') ? <ExcelIcon fontSize="small" /> : <DocumentIcon fontSize="small" />}
                      </Box>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography 
                          variant="caption" 
                          sx={{ 
                            fontWeight: 'medium', 
                            display: 'block', 
                            color: isDarkMode ? 'white' : '#333',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}
                          title={file.name}
                        >
                          {file.name}
                        </Typography>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={() => handleFileDelete(file.name)}
                        sx={{ 
                          color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                          '&:hover': { 
                            color: '#ff6b6b',
                            bgcolor: isDarkMode ? 'rgba(255, 107, 107, 0.2)' : 'rgba(255, 107, 107, 0.1)',
                          },
                          p: 0.5,
                          borderRadius: 1,
                          flexShrink: 0,
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
                  <CircularProgress size={16} sx={{ color: isDarkMode ? 'white' : '#333' }} />
                  <Typography variant="caption" sx={{ color: isDarkMode ? 'white' : '#333' }}>
                    Загрузка документа...
                  </Typography>
                </Box>
              </Box>
            )}

            {/* Поле ввода текста */}
            <TextField
              ref={inputRef}
              fullWidth
              multiline
              maxRows={4}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                !isConnected 
                  ? "Нет соединения с сервером. Запустите backend на порту 8000" 
                  : modelWindows.some(w => w.isStreaming)
                    ? "Модели генерируют ответ... Нажмите ⏹️ чтобы остановить"
                    : !modelWindows.some(w => w.selectedModel)
                      ? "Выберите модель для начала диалога"
                      : "Чем я могу помочь вам сегодня?"
              }
              variant="outlined"
              size="small"
              disabled={!isConnected || !modelWindows.some(w => w.selectedModel) || modelWindows.some(w => w.isStreaming)}
              sx={{
                mb: 1.5,
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'transparent',
                  border: 'none',
                  fontSize: '0.875rem',
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
                    onClick={() => {
                      // Используем setTimeout для гарантии, что input уже отрендерился
                      setTimeout(() => {
                        if (fileInputRef.current) {
                          fileInputRef.current.click();
                        } else {
                          console.error('fileInputRef.current is null');
                        }
                      }, 0);
                    }}
                    sx={{ 
                      color: '#2196f3',
                      bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      '&:hover': {
                        bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                      },
                      '&:active': {
                        transform: 'none',
                      }
                    }}
                    disableRipple
                    disabled={isUploading || modelWindows.some(w => w.isStreaming)}
                  >
                    {isUploading ? <CircularProgress size={16} /> : <AttachFileIcon sx={{ color: '#2196f3', fontSize: '1.2rem' }} />}
                  </IconButton>
                </Tooltip>

                {/* Кнопка добавления модели */}
                {modelWindows.length < 4 && (
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
                        '&:active': {
                          transform: 'none',
                        }
                      }}
                      disableRipple
                      disabled={modelWindows.some(w => w.isStreaming)}
                    >
                      <AddIcon sx={{ fontSize: '1.2rem' }} />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>

              {/* Правая группа кнопок */}
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {/* Кнопка отправки/остановки генерации */}
                {modelWindows.some(w => w.isStreaming) ? (
                  <Tooltip title="Прервать генерацию">
                    <IconButton
                      onClick={handleStopGeneration}
                      color="error"
                      sx={{
                        bgcolor: 'error.main',
                        color: 'white',
                        '&:hover': {
                          bgcolor: 'error.dark',
                        },
                        animation: 'pulse 2s ease-in-out infinite',
                        '@keyframes pulse': {
                          '0%': { opacity: 1 },
                          '50%': { opacity: 0.7 },
                          '100%': { opacity: 1 },
                        },
                      }}
                    >
                      <StopIcon sx={{ fontSize: '1.2rem' }} />
                    </IconButton>
                  </Tooltip>
                ) : (
                  <Tooltip title="Отправить">
                    <IconButton
                      onClick={handleSendMessage}
                      disabled={!inputMessage.trim() || !isConnected || !modelWindows.some(w => w.selectedModel)}
                      color="primary"
                      sx={{
                        bgcolor: 'primary.main',
                        color: 'white',
                        '&:hover': {
                          bgcolor: 'primary.dark',
                        },
                        '&:disabled': {
                          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
                          color: isDarkMode ? 'rgba(255, 255, 255, 0.6)' : 'rgba(0, 0, 0, 0.26)',
                          border: isDarkMode ? '1px solid rgba(255, 255, 255, 0.2)' : 'none',
                        }
                      }}
                    >
                      <SendIcon sx={{ fontSize: '1.2rem' }} />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    );
  }

  return (
    <Box 
      className="fullscreen-chat" 
      sx={{ 
        pt: 8,
        background: isDarkMode 
          ? 'linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 50%, #1a1a1a 100%)'
          : 'linear-gradient(135deg, #f5f5f5 0%, #ffffff 50%, #fafafa 100%)',
        color: isDarkMode ? 'white' : '#333',
      }}
    >
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
              maxWidth: '800px', 
              mx: 'auto',
              px: 2,
            }}>
              {messages.map((message, index) => (
                <MessageCard key={index} message={message} />
              ))}
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

                 {/* Индикатор размышления - показывается только до начала потоковой генерации */}
         {state.isLoading && !messages.some(msg => msg.isStreaming) && (
           <Box sx={{ 
             width: '100%', 
             maxWidth: '800px', 
             mx: 'auto',
             px: 2,
             mb: 3,
             // Для новых чатов позиционируем в центре
             ...(messages.length === 0 && {
               position: 'absolute',
               top: '50%',
               left: '50%',
               transform: 'translate(-50%, 20%)',
               mb: 0,
             }),
           }}>
             <Box
               sx={{
                 display: 'flex',
                 flexDirection: 'column',
                 alignItems: 'flex-start',
                 maxWidth: '75%',
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
                       sx={{
                         width: 24,
                         height: 24,
                         mr: 1,
                         bgcolor: 'secondary.main',
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
                     >
                       <BotIcon />
                     </Avatar>
                     <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}>
                       Газик ИИ
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
                         maxWidth: '800px',
                         mx: 'auto',
                         px: 2,
                         position: 'absolute',
                         top: '45%',
                         left: '50%',
                         transform: 'translate(-50%, -120%)',
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
           <Box
             sx={{
               mt: 2,
               p: 2,
               borderRadius: 2,
               bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
               border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
               maxWidth: '800px', // Расширяем до ширины карточек сообщений
               width: '100%', // Занимает всю доступную ширину до maxWidth
               mx: 'auto', // Центрируем по горизонтали
               // Центрируем по вертикали при пустом чате
               ...(messages.length === 0 && {
                 position: 'absolute',
                 top: '50%',
                 left: '50%',
                 transform: 'translate(-50%, -50%)',
                 mt: 0,
               }),
             }}
           >

                           {/* Скрытый input для выбора файла */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.xlsx,.txt"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />

              {/* Прикрепленные файлы - выше поля ввода */}
              {uploadedFiles.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {uploadedFiles.map((file, index) => (
                      <Box
                        key={index}
                        className="file-attachment"
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          p: 1,
                          borderRadius: 2,
                          maxWidth: '300px',
                          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                          border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'}`,
                        }}
                      >
                        <Box
                          sx={{
                            width: 32,
                            height: 32,
                            borderRadius: 1,
                            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: isDarkMode ? 'white' : '#333',
                            flexShrink: 0,
                            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)'}`,
                          }}
                        >
                          {file.type.includes('pdf') ? <PdfIcon fontSize="small" /> : 
                           file.type.includes('word') ? <DocumentIcon fontSize="small" /> : 
                           file.type.includes('excel') ? <DocumentIcon fontSize="small" /> : <DocumentIcon fontSize="small" />}
                        </Box>
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography 
                            variant="caption" 
                            sx={{ 
                              fontWeight: 'medium', 
                              display: 'block', 
                              color: isDarkMode ? 'white' : '#333',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap'
                            }}
                            title={file.name}
                          >
                            {file.name}
                          </Typography>
                        </Box>
                        <IconButton
                          size="small"
                          onClick={() => handleFileDelete(file.name)}
                          sx={{ 
                            color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                            '&:hover': { 
                              color: '#ff6b6b',
                              bgcolor: isDarkMode ? 'rgba(255, 107, 107, 0.2)' : 'rgba(255, 107, 107, 0.1)',
                            },
                            p: 0.5,
                            borderRadius: 1,
                            flexShrink: 0,
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
                    <CircularProgress size={16} sx={{ color: isDarkMode ? 'white' : '#333' }} />
                    <Typography variant="caption" sx={{ color: isDarkMode ? 'white' : '#333' }}>
                      Загрузка документа...
                    </Typography>
                  </Box>
                </Box>
              )}

              {/* Поле ввода текста */}
              <TextField
                ref={inputRef}
                fullWidth
                multiline
                maxRows={4}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={
                  !isConnected 
                    ? "Нет соединения с сервером. Запустите backend на порту 8000" 
                    : state.isLoading && !messages.some(msg => msg.isStreaming)
                      ? "ГазикИИ думает..." 
                      : state.isLoading && messages.some(msg => msg.isStreaming)
                        ? "ГазикИИ генерирует ответ... Нажмите ⏹️ чтобы остановить"
                        : "Чем я могу помочь вам сегодня?"
                }
                variant="outlined"
                size="small"
                disabled={!isConnected || (state.isLoading && !messages.some(msg => msg.isStreaming))}
                sx={{
                  mb: 1.5,
                  '& .MuiOutlinedInput-root': {
                    bgcolor: 'transparent',
                    border: 'none',
                    fontSize: '0.875rem',
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
                       onClick={() => fileInputRef.current?.click()}
                       sx={{ 
                         color: '#2196f3',
                         bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                         '&:hover': {
                           bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                         },
                         '&:active': {
                           transform: 'none',
                         }
                       }}
                       disableRipple
                       disabled={isUploading || (state.isLoading && !messages.some(msg => msg.isStreaming))}
                     >
                       {isUploading ? <CircularProgress size={16} /> : <AttachFileIcon sx={{ color: '#2196f3', fontSize: '1.2rem' }} />}
                     </IconButton>
                   </Tooltip>

                                       {/* Кнопка меню с шестеренкой */}
                    <Tooltip title="Дополнительные действия">
                      <IconButton
                        onClick={handleMenuOpen}
                        disabled={state.isLoading && !messages.some(msg => msg.isStreaming)}
                        sx={{ 
                          color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
                          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                          '&:hover': {
                            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
                          },
                          '&:disabled': {
                            color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
                            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
                          }
                        }}
                      >
                        <SettingsIcon sx={{ fontSize: '1.2rem' }} />
                      </IconButton>
                    </Tooltip>
                 </Box>

                                 {/* Правая группа кнопок */}
                 <Box sx={{ display: 'flex', gap: 0.5 }}>
                   {/* Кнопка отправки/остановки генерации */}
                   {messages.some(msg => msg.isStreaming) ? (
                     <Tooltip title="Прервать генерацию">
                       <IconButton
                         onClick={handleStopGeneration}
                         color="error"
                         sx={{
                           bgcolor: 'error.main',
                           color: 'white',
                           '&:hover': {
                             bgcolor: 'error.dark',
                           },
                           animation: 'pulse 2s ease-in-out infinite',
                           '@keyframes pulse': {
                             '0%': { opacity: 1 },
                             '50%': { opacity: 0.7 },
                             '100%': { opacity: 1 },
                           },
                         }}
                       >
                         <SquareIcon sx={{ fontSize: '1.2rem' }} />
                       </IconButton>
                     </Tooltip>
                   ) : (
                     <Tooltip title="Отправить">
                       <IconButton
                         onClick={handleSendMessage}
                         disabled={!inputMessage.trim() || !isConnected || (state.isLoading && !messages.some(msg => msg.isStreaming))}
                         color="primary"
                         sx={{
                           bgcolor: 'primary.main',
                           color: 'white',
                           '&:hover': {
                             bgcolor: 'primary.dark',
                           },
                           '&:disabled': {
                             bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
                             color: isDarkMode ? 'rgba(255, 255, 255, 0.6)' : 'rgba(0, 0, 0, 0.26)',
                               border: isDarkMode ? '1px solid rgba(255, 255, 255, 0.2)' : 'none',
                           }
                         }}
                       >
                         <SendIcon sx={{ fontSize: '1.2rem' }} />
                       </IconButton>
                     </Tooltip>
                   )}

                  {/* Кнопка голосового ввода */}
                  <Tooltip title="Голосовой ввод">
                    <IconButton
                      onClick={() => setShowVoiceDialog(true)}
                      disabled={state.isLoading && !messages.some(msg => msg.isStreaming)}
                      sx={{
                        bgcolor: 'secondary.main',
                        color: 'white',
                        '&:hover': { 
                          bgcolor: 'secondary.dark' 
                        },
                        '&:disabled': {
                          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
                          color: isDarkMode ? 'rgba(255, 255, 255, 0.6)' : 'rgba(0, 0, 0, 0.26)',
                        }
                      }}
                    >
                      <MicIcon sx={{ fontSize: '1.2rem' }} />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
           </Box>
        </Box>

             {/* Диалоги */}
       <VoiceDialog />
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
         <MenuItem onClick={handleReconnect} sx={{ gap: 1 }}>
           <RefreshIcon fontSize="small" />
           Переподключиться
         </MenuItem>
       </Menu>

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
   );
 }
