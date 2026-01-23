import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';

// Типы данных
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  // Для режима multi-llm: несколько ответов от разных моделей
  multiLLMResponses?: Array<{
    model: string;
    content: string;
    isStreaming?: boolean;
    error?: boolean;
  }>;
  // Для хранения нескольких вариантов ответов (при перегенерации)
  alternativeResponses?: string[];
  currentResponseIndex?: number; // Индекс текущего отображаемого варианта (0-based)
}

export interface Chat {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
  isArchived?: boolean;
  projectId?: string;
  isPinnedInProject?: boolean;
}

export interface ModelInfo {
  loaded: boolean;
  metadata?: {
    'general.name': string;
    'general.architecture': string;
    'general.size_label': string;
  };
  path?: string;
  n_ctx?: number;
  n_gpu_layers?: number;
}

export interface ModelSettings {
  context_size: number;
  output_tokens: number;
  temperature: number;
  top_p: number;
  repeat_penalty: number;
  top_k: number;
  min_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  use_gpu: boolean;
  streaming: boolean;
  streaming_speed: number; // Скорость потоковой генерации в миллисекундах
}

export interface Folder {
  id: string;
  name: string;
  chatIds: string[];
  expanded: boolean;
}

export interface Project {
  id: string;
  name: string;
  icon?: string;
  iconType?: 'icon' | 'emoji';
  iconColor?: string;
  memory: 'default' | 'project-only';
  instructions: string;
  createdAt: string;
  updatedAt: string;
}

export interface AppState {
  // Чаты
  chats: Chat[];
  currentChatId: string | null;
  folders: Folder[];
  projects: Project[];
  isLoading: boolean;
  isInitialized: boolean;
  
  // Модель
  currentModel: ModelInfo | null;
  modelSettings: ModelSettings;
  availableModels: any[];
  
  // Голос
  isRecording: boolean;
  isSpeaking: boolean;
  voiceSettings: {
    voice_id: string;
    speech_rate: number;
  };
  
  // Транскрибация
  transcriptionSettings: {
    engine: 'whisperx' | 'vosk';
    language: string;
    auto_detect: boolean;
  };
  
  // Документы
  loadedDocument: string | null;
  
  // Системные уведомления
  notifications: Array<{
    id: string;
    type: 'success' | 'error' | 'info' | 'warning';
    message: string;
    timestamp: string;
  }>;
  
  // Статистика
  stats: {
    totalMessages: number;
    totalTokens: number;
    sessionsToday: number;
  };
}

// Действия
type AppAction =
  | { type: 'CREATE_CHAT'; payload: Chat }
  | { type: 'RESTORE_CHATS'; payload: { chats: Chat[]; currentChatId: string | null; folders: Folder[] } }
  | { type: 'SET_CURRENT_CHAT'; payload: string | null }
  | { type: 'UPDATE_CHAT_TITLE'; payload: { chatId: string; title: string } }
  | { type: 'UPDATE_CHAT_MESSAGES'; payload: { chatId: string; messages: Message[] } }
  | { type: 'DELETE_CHAT'; payload: string }
  | { type: 'DELETE_ALL_CHATS' }
  | { type: 'ADD_MESSAGE'; payload: { chatId: string; message: Message } }
  | { type: 'UPDATE_MESSAGE'; payload: { chatId: string; messageId: string; content?: string; isStreaming?: boolean; multiLLMResponses?: Array<{ model: string; content: string; isStreaming?: boolean; error?: boolean }>; alternativeResponses?: string[]; currentResponseIndex?: number } }
  | { type: 'APPEND_CHUNK'; payload: { chatId: string; messageId: string; chunk: string; isStreaming?: boolean } }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_CURRENT_MODEL'; payload: ModelInfo }
  | { type: 'SET_MODEL_SETTINGS'; payload: ModelSettings }
  | { type: 'SET_AVAILABLE_MODELS'; payload: any[] }
  | { type: 'SET_RECORDING'; payload: boolean }
  | { type: 'SET_SPEAKING'; payload: boolean }
  | { type: 'SET_VOICE_SETTINGS'; payload: { voice_id: string; speech_rate: number } }
  | { type: 'SET_TRANSCRIPTION_SETTINGS'; payload: { engine: 'whisperx' | 'vosk'; language: string; auto_detect: boolean } }
  | { type: 'SET_LOADED_DOCUMENT'; payload: string | null }
  | { type: 'ADD_NOTIFICATION'; payload: { type: string; message: string } }
  | { type: 'REMOVE_NOTIFICATION'; payload: string }
  | { type: 'CLEAR_MESSAGES'; payload: string }
  | { type: 'CREATE_FOLDER'; payload: Folder }
  | { type: 'UPDATE_FOLDER'; payload: { folderId: string; name: string } }
  | { type: 'DELETE_FOLDER'; payload: string }
  | { type: 'MOVE_CHAT_TO_FOLDER'; payload: { chatId: string; folderId: string | null } }
  | { type: 'TOGGLE_FOLDER'; payload: string }
  | { type: 'ARCHIVE_ALL_CHATS' }
  | { type: 'ARCHIVE_CHAT'; payload: string }
  | { type: 'ARCHIVE_FOLDER'; payload: string }
  | { type: 'UNARCHIVE_CHAT'; payload: string }
  | { type: 'UNARCHIVE_ALL_CHATS' }
  | { type: 'UPDATE_STATS'; payload: Partial<AppState['stats']> }
  | { type: 'SET_INITIALIZED'; payload: boolean }
  | { type: 'CREATE_PROJECT'; payload: Project }
  | { type: 'UPDATE_PROJECT'; payload: { projectId: string; updates: Partial<Project> } }
  | { type: 'DELETE_PROJECT'; payload: string }
  | { type: 'RESTORE_PROJECTS'; payload: Project[] }
  | { type: 'MOVE_CHAT_TO_PROJECT'; payload: { chatId: string; projectId: string | null } }
  | { type: 'TOGGLE_PIN_IN_PROJECT'; payload: { chatId: string } };

// Функция для оценки количества токенов в тексте
function estimateTokens(text: string): number {
  if (!text) return 0;
  
  // Простая эвристика: 1 токен ≈ 4 символа для смешанного текста
  // Для русского текста может быть немного больше из-за длинных слов
  const baseTokens = Math.ceil(text.length / 4);
  
  // Дополнительные токены для специальных символов и форматирования
  const specialChars = (text.match(/[^\w\sа-яё]/g) || []).length;
  const newlines = (text.match(/\n/g) || []).length;
  
  return baseTokens + Math.ceil(specialChars / 2) + Math.ceil(newlines / 2);
}

// Функция для склеивания чанков (минимальные исправления)
function smartConcatenateChunk(existingContent: string, newChunk: string): string {
  if (!existingContent) return newChunk;
  if (!newChunk) return existingContent;
  
  // ТОЛЬКО критические исправления для кодовых блоков
  
  // 1. После ``` и языка программирования должен быть перенос строки
  const languageEndPattern = /```(python|javascript|typescript|java|cpp|c|php|ruby|go|rust|swift|kotlin|scala|html|css|sql|bash|shell|json|xml|yaml)$/;
  if (languageEndPattern.test(existingContent)) {
    return existingContent + '\n' + newChunk;
  }
  
  // 2. Начало кодового блока после текста
  if (newChunk.startsWith('```')) {
    const lastChar = existingContent[existingContent.length - 1];
    if (/[а-яёa-z]/i.test(lastChar)) {
      return existingContent + '\n\n' + newChunk;
    }
  }
  
  // ВСЕ ОСТАЛЬНОЕ - как было в оригинале (простое склеивание)
  return existingContent + newChunk;
}

// Начальное состояние
const initialState: AppState = {
  chats: [],
  currentChatId: null,
  folders: [],
  projects: [],
  isLoading: false,
  isInitialized: false,
  currentModel: null,
  modelSettings: {
    context_size: 2048,
    output_tokens: 512,
    temperature: 0.7,
    top_p: 0.95,
    repeat_penalty: 1.05,
    top_k: 40,
    min_p: 0.05,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    use_gpu: false,
    streaming: true,
    streaming_speed: 100, // Default streaming speed
  },
  availableModels: [],
  isRecording: false,
  isSpeaking: false,
  voiceSettings: {
    voice_id: 'ru',
    speech_rate: 1.0,
  },
  transcriptionSettings: {
    engine: 'whisperx',
    language: 'ru',
    auto_detect: true,
  },
  loadedDocument: null,
  notifications: [],
  stats: {
    totalMessages: 0,
    totalTokens: 0,
    sessionsToday: 0,
  },
};

// Reducer
function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'CREATE_CHAT':
      return {
        ...state,
        chats: [...state.chats, action.payload],
        currentChatId: action.payload.id,
      };
      
    case 'RESTORE_CHATS':
      return {
        ...state,
        chats: action.payload.chats,
        currentChatId: action.payload.currentChatId,
        folders: action.payload.folders || [],
        isInitialized: true,
      };
      
    case 'SET_CURRENT_CHAT':
      return {
        ...state,
        currentChatId: action.payload,
      };
      
    case 'UPDATE_CHAT_TITLE':
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === action.payload.chatId
            ? { ...chat, title: action.payload.title, updatedAt: new Date().toISOString() }
            : chat
        ),
      };
      
    case 'UPDATE_CHAT_MESSAGES':
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === action.payload.chatId
            ? { ...chat, messages: action.payload.messages, updatedAt: new Date().toISOString() }
            : chat
        ),
      };
      
    case 'DELETE_CHAT':
      return {
        ...state,
        chats: state.chats.filter(chat => chat.id !== action.payload),
        currentChatId: state.currentChatId === action.payload ? null : state.currentChatId,
      };
      
    case 'DELETE_ALL_CHATS':
      return {
        ...state,
        chats: [],
        currentChatId: null,
        folders: [], // Также удаляем все папки, так как они пустые
      };
      
    case 'ADD_MESSAGE': {
      const { chatId, message } = action.payload;
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === chatId
            ? {
                ...chat,
                messages: [...chat.messages, message],
                updatedAt: new Date().toISOString(),
              }
            : chat
        ),
        stats: {
          ...state.stats,
          totalMessages: state.stats.totalMessages + 1,
          totalTokens: state.stats.totalTokens + estimateTokens(message.content),
        },
      };
    }
      
    case 'UPDATE_MESSAGE': {
      const { chatId, messageId, content, isStreaming, multiLLMResponses, alternativeResponses, currentResponseIndex } = action.payload;
      
      const currentChat = state.chats.find(chat => chat.id === chatId);
      const updatedMessage = currentChat?.messages.find(msg => msg.id === messageId);
      
      const newState = {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === chatId
            ? {
                ...chat,
                messages: chat.messages.map(msg =>
                  msg.id === messageId
                    ? { 
                        ...msg, 
                        ...(content !== undefined ? { content } : {}),
                        ...(isStreaming !== undefined ? { isStreaming } : {}),
                        ...(multiLLMResponses !== undefined ? { multiLLMResponses } : {}),
                        ...(alternativeResponses !== undefined ? { alternativeResponses } : {}),
                        ...(currentResponseIndex !== undefined ? { currentResponseIndex } : {})
                      }
                    : msg
                ),
                updatedAt: new Date().toISOString(),
              }
            : chat
        ),
        stats: {
          ...state.stats,
          // Обновляем токены при изменении содержимого сообщения
          totalTokens: state.stats.totalTokens - estimateTokens(updatedMessage?.content || '') + estimateTokens(content || ''),
        },
      };
      
      return newState;
    }
      
    case 'APPEND_CHUNK': {
      const { chatId, messageId, chunk, isStreaming } = action.payload;
      
      const currentChat = state.chats.find(chat => chat.id === chatId);
      const chunkMessage = currentChat?.messages.find(msg => msg.id === messageId);
      
      const newContent = chunkMessage ? smartConcatenateChunk(chunkMessage.content, chunk) : chunk;
      
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === chatId
            ? {
                ...chat,
                messages: chat.messages.map(msg =>
                  msg.id === messageId
                    ? {
                        ...msg,
                        content: newContent,
                        ...(isStreaming !== undefined && { isStreaming })
                      }
                    : msg
                ),
                updatedAt: new Date().toISOString(),
              }
            : chat
        ),
        stats: {
          ...state.stats,
          // Добавляем токены для нового чанка
          totalTokens: state.stats.totalTokens + estimateTokens(chunk),
        },
      };
    }
      
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload,
      };
      
    case 'SET_CURRENT_MODEL':
      return {
        ...state,
        currentModel: action.payload,
      };
      
    case 'SET_MODEL_SETTINGS':
      return {
        ...state,
        modelSettings: action.payload,
      };
      
    case 'SET_AVAILABLE_MODELS':
      return {
        ...state,
        availableModels: action.payload,
      };
      
    case 'SET_RECORDING':
      return {
        ...state,
        isRecording: action.payload,
      };
      
    case 'SET_SPEAKING':
      return {
        ...state,
        isSpeaking: action.payload,
      };
      
    case 'SET_VOICE_SETTINGS':
      return {
        ...state,
        voiceSettings: action.payload,
      };
      
    case 'SET_TRANSCRIPTION_SETTINGS':
      return {
        ...state,
        transcriptionSettings: action.payload,
      };
      
    case 'SET_LOADED_DOCUMENT':
      return {
        ...state,
        loadedDocument: action.payload,
      };
      
    case 'ADD_NOTIFICATION': {
      const notification = {
        id: Date.now().toString(),
        type: action.payload.type as 'success' | 'error' | 'info' | 'warning',
        message: action.payload.message,
        timestamp: new Date().toISOString(),
      };
      return {
        ...state,
        notifications: [...state.notifications, notification],
      };
    }
      
    case 'REMOVE_NOTIFICATION':
      return {
        ...state,
        notifications: state.notifications.filter(n => n.id !== action.payload),
      };
      
    case 'CLEAR_MESSAGES': {
      const chatId = action.payload;
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === chatId
            ? { ...chat, messages: [], updatedAt: new Date().toISOString() }
            : chat
        ),
        stats: {
          ...state.stats,
          totalMessages: 0,
          totalTokens: 0,
        },
      };
    }
      
    case 'UPDATE_STATS':
      return {
        ...state,
        stats: {
          ...state.stats,
          ...action.payload,
        },
      };
      
    case 'CREATE_FOLDER':
      return {
        ...state,
        folders: [...state.folders, action.payload],
      };
      
    case 'UPDATE_FOLDER':
      return {
        ...state,
        folders: state.folders.map(folder =>
          folder.id === action.payload.folderId
            ? { ...folder, name: action.payload.name }
            : folder
        ),
      };
      
    case 'DELETE_FOLDER':
      return {
        ...state,
        folders: state.folders.filter(folder => folder.id !== action.payload),
      };
      
    case 'MOVE_CHAT_TO_FOLDER': {
      // Обновляем папки
      const updatedFolders = state.folders.map(folder => ({
        ...folder,
        chatIds: folder.id === action.payload.folderId
          ? [...folder.chatIds, action.payload.chatId]
          : folder.chatIds.filter(id => id !== action.payload.chatId)
      }));
      
      // Удаляем папку "Закреплено" если она стала пустой
      const pinnedFolder = updatedFolders.find(f => f.name === 'Закреплено');
      const finalFolders = pinnedFolder && pinnedFolder.chatIds.length === 0
        ? updatedFolders.filter(f => f.id !== pinnedFolder.id)
        : updatedFolders;
      
      return {
        ...state,
        folders: finalFolders,
      };
    }
      
    case 'TOGGLE_FOLDER':
      return {
        ...state,
        folders: state.folders.map(folder =>
          folder.id === action.payload
            ? { ...folder, expanded: !folder.expanded }
            : folder
        ),
      };
      
    case 'ARCHIVE_ALL_CHATS': {
      // Помечаем все неархивированные чаты как архивированные
      // Если текущий чат архивируется, сбрасываем currentChatId
      return {
        ...state,
        chats: state.chats.map(chat => ({
          ...chat,
          isArchived: true,
        })),
        currentChatId: null, // Сбрасываем текущий чат, так как все архивируются
      };
    }
    
    case 'ARCHIVE_CHAT': {
      // Помечаем конкретный чат как архивированный
      // Если архивируется текущий чат, сбрасываем currentChatId
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === action.payload
            ? { ...chat, isArchived: true }
            : chat
        ),
        currentChatId: state.currentChatId === action.payload ? null : state.currentChatId,
      };
    }
    
    case 'ARCHIVE_FOLDER': {
      // Архивируем все чаты в папке
      const folder = state.folders.find(f => f.id === action.payload);
      if (!folder) {
        return state;
      }
      
      const chatIdsToArchive = folder.chatIds;
      const newCurrentChatId = chatIdsToArchive.includes(state.currentChatId || '') 
        ? null 
        : state.currentChatId;
      
      return {
        ...state,
        chats: state.chats.map(chat =>
          chatIdsToArchive.includes(chat.id)
            ? { ...chat, isArchived: true }
            : chat
        ),
        currentChatId: newCurrentChatId,
      };
    }
    
    case 'UNARCHIVE_CHAT': {
      // Убираем пометку архивирования у конкретного чата
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === action.payload
            ? { ...chat, isArchived: false }
            : chat
        ),
      };
    }
    
    case 'UNARCHIVE_ALL_CHATS': {
      // Убираем пометку архивирования у всех чатов
      return {
        ...state,
        chats: state.chats.map(chat => ({
          ...chat,
          isArchived: false,
        })),
      };
    }
      
    case 'SET_INITIALIZED':
      return {
        ...state,
        isInitialized: action.payload,
      };
    
    case 'CREATE_PROJECT':
      return {
        ...state,
        projects: [...state.projects, action.payload],
      };
    
    case 'UPDATE_PROJECT':
      return {
        ...state,
        projects: state.projects.map(project =>
          project.id === action.payload.projectId
            ? { ...project, ...action.payload.updates, updatedAt: new Date().toISOString() }
            : project
        ),
      };
    
    case 'DELETE_PROJECT':
      return {
        ...state,
        projects: state.projects.filter(project => project.id !== action.payload),
      };
    
    case 'RESTORE_PROJECTS':
      return {
        ...state,
        projects: action.payload,
      };
    
    case 'MOVE_CHAT_TO_PROJECT':
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === action.payload.chatId
            ? { ...chat, projectId: action.payload.projectId ?? undefined }
            : chat
        ),
      };
    
    case 'TOGGLE_PIN_IN_PROJECT':
      return {
        ...state,
        chats: state.chats.map(chat =>
          chat.id === action.payload.chatId
            ? { ...chat, isPinnedInProject: !chat.isPinnedInProject }
            : chat
        ),
      };
      
    default:
      return state;
  }
}

// Контекст
const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

// Провайдер
export function AppProvider({ children }: { children: ReactNode }) {
  // Загружаем состояние из localStorage при инициализации
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Инициализация из localStorage
  useEffect(() => {
    try {
      const savedState = localStorage.getItem('memo-chats');
      if (savedState) {
        const parsed = JSON.parse(savedState);
        if (parsed.chats && parsed.chats.length > 0) {
          // Восстанавливаем чаты и папки напрямую в состояние
          dispatch({ 
            type: 'RESTORE_CHATS', 
            payload: {
              chats: parsed.chats || [],
              currentChatId: parsed.currentChatId || null,
              folders: parsed.folders || []
            }
          });
        }
        // Восстанавливаем проекты
        if (parsed.projects && parsed.projects.length > 0) {
          dispatch({ type: 'RESTORE_PROJECTS', payload: parsed.projects });
        }
        if (!parsed.chats || parsed.chats.length === 0) {
          // Если нет сохраненных чатов, помечаем как инициализированное
          dispatch({ type: 'SET_INITIALIZED', payload: true });
        }
      } else {
        // Если нет сохраненного состояния, помечаем как инициализированное
        dispatch({ type: 'SET_INITIALIZED', payload: true });
      }
    } catch (error) {
      console.error('Ошибка загрузки состояния из localStorage:', error);
      // В случае ошибки тоже помечаем как инициализированное
      dispatch({ type: 'SET_INITIALIZED', payload: true });
    }
  }, []);

  // Сохраняем состояние в localStorage при изменении
  useEffect(() => {
    try {
      const stateToSave = {
        chats: state.chats,
        currentChatId: state.currentChatId,
        folders: state.folders,
        projects: state.projects,
      };
      localStorage.setItem('memo-chats', JSON.stringify(stateToSave));
    } catch (error) {
      console.error('Ошибка сохранения состояния в localStorage:', error);
    }
  }, [state.chats, state.currentChatId, state.folders, state.projects]);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

// Хук для использования контекста
export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
}

// Хелперы для часто используемых действий
export function useAppActions() {
  const { dispatch, state } = useAppContext();

  return {
    createChat: (title: string = 'Новый чат') => {
      const chatId = Date.now().toString() + Math.random().toString(36).substr(2, 9);
      const now = new Date().toISOString();
      
      const newChat: Chat = {
        id: chatId,
        title,
        messages: [],
        createdAt: now,
        updatedAt: now,
      };
      
      dispatch({
        type: 'CREATE_CHAT',
        payload: newChat,
      });
      
      return chatId;
    },
    
    setCurrentChat: (chatId: string | null) => {
      dispatch({
        type: 'SET_CURRENT_CHAT',
        payload: chatId,
      });
    },
    
    updateChatTitle: (chatId: string, title: string) => {
      dispatch({
        type: 'UPDATE_CHAT_TITLE',
        payload: { chatId, title },
      });
    },
    
    updateChatMessages: (chatId: string, messages: Message[]) => {
      dispatch({
        type: 'UPDATE_CHAT_MESSAGES',
        payload: { chatId, messages },
      });
    },
    
    deleteChat: (chatId: string) => {
      dispatch({
        type: 'DELETE_CHAT',
        payload: chatId,
      });
    },
    
    deleteAllChats: () => {
      dispatch({
        type: 'DELETE_ALL_CHATS',
      });
    },
    
    addMessage: (chatId: string, message: Omit<Message, 'id'>) => {
      // Генерируем ID в формате msg_{12 hex символов}, как в MongoDB
      const randomHex = Array.from({ length: 12 }, () => 
        Math.floor(Math.random() * 16).toString(16)
      ).join('');
      const messageId = `msg_${randomHex}`;
      
      dispatch({
        type: 'ADD_MESSAGE',
        payload: {
          chatId,
          message: {
            ...message,
            id: messageId,
          },
        },
      });
      return messageId;
    },
    
    updateMessage: (chatId: string, messageId: string, content?: string, isStreaming?: boolean, multiLLMResponses?: Array<{ model: string; content: string; isStreaming?: boolean; error?: boolean }>, alternativeResponses?: string[], currentResponseIndex?: number) => {
      dispatch({ type: 'UPDATE_MESSAGE', payload: { chatId, messageId, content, isStreaming, multiLLMResponses, alternativeResponses, currentResponseIndex } });
    },
    
    appendChunk: (chatId: string, messageId: string, chunk: string, isStreaming?: boolean) => {
      dispatch({ type: 'APPEND_CHUNK', payload: { chatId, messageId, chunk, isStreaming } });
    },
    
    setLoading: (loading: boolean) => {
      dispatch({ type: 'SET_LOADING', payload: loading });
    },
    
    showNotification: (type: 'success' | 'error' | 'info' | 'warning', message: string) => {
      dispatch({ type: 'ADD_NOTIFICATION', payload: { type, message } });
    },
    
    removeNotification: (id: string) => {
      dispatch({ type: 'REMOVE_NOTIFICATION', payload: id });
    },
    
    clearMessages: (chatId: string) => {
      dispatch({ type: 'CLEAR_MESSAGES', payload: chatId });
    },
    
    setCurrentModel: (model: ModelInfo) => {
      dispatch({ type: 'SET_CURRENT_MODEL', payload: model });
    },
    
    setModelSettings: (settings: ModelSettings) => {
      dispatch({ type: 'SET_MODEL_SETTINGS', payload: settings });
    },
    
    setRecording: (recording: boolean) => {
      dispatch({ type: 'SET_RECORDING', payload: recording });
    },
    
    setSpeaking: (speaking: boolean) => {
      dispatch({ type: 'SET_SPEAKING', payload: speaking });
    },
    
    setTranscriptionSettings: (settings: { engine: 'whisperx' | 'vosk'; language: string; auto_detect: boolean }) => {
      dispatch({ type: 'SET_TRANSCRIPTION_SETTINGS', payload: settings });
    },
    
    // Хелперы для получения данных
    getCurrentChat: () => {
      return state.chats.find(chat => chat.id === state.currentChatId) || null;
    },
    
    getCurrentMessages: () => {
      const currentChat = state.chats.find(chat => chat.id === state.currentChatId);
      return currentChat?.messages || [];
    },
    
    // Функции для работы с папками
    createFolder: (name: string) => {
      const folderId = Date.now().toString() + Math.random().toString(36).substr(2, 9);
      const newFolder: Folder = {
        id: folderId,
        name,
        chatIds: [],
        expanded: true,
      };
      dispatch({ type: 'CREATE_FOLDER', payload: newFolder });
      return folderId;
    },
    
    updateFolder: (folderId: string, name: string) => {
      dispatch({ type: 'UPDATE_FOLDER', payload: { folderId, name } });
    },
    
    deleteFolder: (folderId: string) => {
      dispatch({ type: 'DELETE_FOLDER', payload: folderId });
    },
    
    moveChatToFolder: (chatId: string, folderId: string | null) => {
      dispatch({ type: 'MOVE_CHAT_TO_FOLDER', payload: { chatId, folderId } });
    },
    
    toggleFolder: (folderId: string) => {
      dispatch({ type: 'TOGGLE_FOLDER', payload: folderId });
    },
    
    getFolders: () => {
      return state.folders;
    },
    
    exportChats: () => {
      const exportData = {
        chats: state.chats,
        folders: state.folders,
        exportDate: new Date().toISOString(),
        version: '1.0',
      };
      const dataStr = JSON.stringify(exportData, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `chats_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    },
    
    importChats: (file: File): Promise<boolean> => {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const content = e.target?.result as string;
            const importData = JSON.parse(content);
            
            // Валидация структуры данных
            if (!importData.chats || !Array.isArray(importData.chats)) {
              throw new Error('Неверный формат файла: отсутствует массив чатов');
            }
            
            // Восстанавливаем чаты и папки
            dispatch({
              type: 'RESTORE_CHATS',
              payload: {
                chats: importData.chats,
                currentChatId: importData.currentChatId || null,
                folders: importData.folders || [],
              },
            });
            
            resolve(true);
          } catch (error) {
            reject(error);
          }
        };
        reader.onerror = () => reject(new Error('Ошибка чтения файла'));
        reader.readAsText(file);
      });
    },
    
    archiveAllChats: () => {
      dispatch({ type: 'ARCHIVE_ALL_CHATS' });
    },
    
    archiveChat: (chatId: string) => {
      dispatch({ type: 'ARCHIVE_CHAT', payload: chatId });
    },
    
    archiveFolder: (folderId: string) => {
      dispatch({ type: 'ARCHIVE_FOLDER', payload: folderId });
    },
    
    unarchiveChat: (chatId: string) => {
      dispatch({ type: 'UNARCHIVE_CHAT', payload: chatId });
    },
    
    unarchiveAllChats: () => {
      dispatch({ type: 'UNARCHIVE_ALL_CHATS' });
    },
    
    getChatById: (chatId: string) => {
      return state.chats.find(chat => chat.id === chatId) || null;
    },
    
    getArchivedChats: () => {
      return state.chats.filter(chat => chat.isArchived === true);
    },
    
    // Функции для работы с проектами
    createProject: (projectData: Omit<Project, 'id' | 'createdAt' | 'updatedAt'>) => {
      const projectId = Date.now().toString() + Math.random().toString(36).substr(2, 9);
      const newProject: Project = {
        id: projectId,
        ...projectData,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      dispatch({ type: 'CREATE_PROJECT', payload: newProject });
      return projectId;
    },
    
    updateProject: (projectId: string, updates: Partial<Project>) => {
      dispatch({ type: 'UPDATE_PROJECT', payload: { projectId, updates } });
    },
    
    deleteProject: (projectId: string) => {
      dispatch({ type: 'DELETE_PROJECT', payload: projectId });
    },
    
    getProjects: () => {
      return state.projects;
    },
    
    getProjectById: (projectId: string) => {
      return state.projects.find(project => project.id === projectId) || null;
    },
    
    moveChatToProject: (chatId: string, projectId: string | null) => {
      dispatch({ type: 'MOVE_CHAT_TO_PROJECT', payload: { chatId, projectId } });
    },
    
    togglePinInProject: (chatId: string) => {
      dispatch({ type: 'TOGGLE_PIN_IN_PROJECT', payload: { chatId } });
    },
  };
}
