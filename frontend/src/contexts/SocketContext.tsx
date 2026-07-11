import React, { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAppActions } from './AppContext';
import type { Chat, Message, MultiLLMResponseSlot } from './AppContext';
import { useAuth } from './AuthContext';
import { getSettings, initSettings } from '../settings';
import {
  LAST_SELECTED_MODEL_PATH_STORAGE_KEY,
  MODEL_THINKING_MODE_STORAGE_KEY,
  ModelThinkingMode,
  resolveEnableThinkingByMode,
} from '../utils/modelThinking';
import { 
  showBrowserNotification, 
  areNotificationsEnabled, 
  isNotificationSupported,
  requestNotificationPermission 
} from '../utils/browserNotifications';
import { incrementTabNotification } from '../utils/tabNotifications';
import { getMcpToolIdsForChat } from '../mcp/selectionStorage';
import type { McpToolCallRecord } from '../mcp/types';
import { getApiUrl } from '../config/api';
import { isLikelyImageGenerationPrompt } from '../utils/imageGenerationPrompt';
import { readSelectedImageGenPresetId } from '../utils/imageGenerationPresets';

function dispatchMcpToolActivity(record: McpToolCallRecord, phase: 'start' | 'end') {
  window.dispatchEvent(new CustomEvent('astrachatMcpToolActivity', { detail: { record, phase } }));
}

function clearMcpToolActivity() {
  window.dispatchEvent(new CustomEvent('astrachatMcpToolActivityClear'));
}

function isImageGenThinkingPayload(data: Record<string, unknown>): boolean {
  if (data.image_generation === true) return true;
  const msg = data.message;
  return typeof msg === 'string' && /изображен|comfyui/i.test(msg);
}

function mapServerInlineAttachments(raw: unknown): Message['inlineAttachments'] | undefined {
  if (!Array.isArray(raw) || raw.length === 0) return undefined;
  const items = raw
    .filter((a): a is Record<string, unknown> => Boolean(a) && typeof a === 'object')
    .map((a) => {
      const contentType = a.contentType === 'image' ? ('image' as const) : ('text' as const);
      const dataUri = a.data_uri ? String(a.data_uri) : undefined;
      const minioObject = a.minio_object ? String(a.minio_object) : undefined;
      const minioBucket = a.minio_bucket ? String(a.minio_bucket) : undefined;
      let preview: string | undefined;
      if (contentType === 'image' && dataUri) {
        preview = dataUri;
      } else if (contentType === 'image' && minioObject && minioBucket) {
        preview = getApiUrl(
          `/api/documents/inline-file?bucket=${encodeURIComponent(minioBucket)}&object=${encodeURIComponent(minioObject)}`,
        );
      }
      return {
        name: String(a.name || 'file'),
        contentType,
        ...(preview ? { preview } : {}),
        ...(typeof a.size === 'number' && a.size > 0 ? { size: a.size } : {}),
      };
    });
  return items.length > 0 ? items : undefined;
}

/** Лимит тела Socket.IO (inline-картинки в base64; дефолт engine.io ~1 МБ). */
const SOCKET_MAX_HTTP_BUFFER_BYTES = 52 * 1024 * 1024;

interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  isConnecting: boolean;
  sendMessage: (
    message: string,
    chatId: string,
    streaming?: boolean,
    overrideProjectId?: string | null,
    /** true — ответ только через multi_llm_*; chat_chunk/chat_complete игнорируются (иначе дубль сообщения) */
    expectMultiLlm?: boolean,
    /** Inline-вложения: текст и/или изображения, передаются напрямую без RAG */
    inlineData?: {
      inline_context?: string;
      inline_images?: string[];
      /** Метаданные для отображения в пузыре сообщения (не идут на бэкенд) */
      attachments_meta?: Array<{
        name: string;
        contentType: 'text' | 'image';
        preview?: string;
        minio_object?: string;
        minio_bucket?: string;
        size?: number;
      }>;
      inline_attachments?: Array<{
        name: string;
        contentType: 'text' | 'image';
        minio_object?: string;
        minio_bucket?: string;
        size?: number;
      }>;
    },
  ) => void;
  regenerateResponse: (userMessage: string, assistantMessageId: string, chatId: string, alternativeResponses: string[], currentIndex: number, streaming?: boolean) => void;
  /** Перегенерация одного столбца multi-LLM (тот же assistant message, без нового сообщения пользователя). */
  regenerateMultiLlmSlot: (
    userMessage: string,
    assistantMessageId: string,
    chatId: string,
    slotModel: string,
    streaming?: boolean,
    overrideProjectId?: string | null,
  ) => void;
  stopGeneration: () => void;
  reconnect: () => void;
  onMultiLLMEvent?: (event: string, handler: (data: any) => void) => void;
  offMultiLLMEvent?: (event: string, handler: (data: any) => void) => void;
}

type PendingSendPayload = {
  message: string;
  chatId: string;
  streaming?: boolean;
  overrideProjectId?: string | null;
  expectMultiLlm?: boolean;
  inlineData?: {
    inline_context?: string;
    inline_images?: string[];
    attachments_meta?: Array<{
      name: string;
      contentType: 'text' | 'image';
      preview?: string;
      minio_object?: string;
      minio_bucket?: string;
      size?: number;
    }>;
  };
};

const SocketContext = createContext<SocketContextType | null>(null);

export function SocketProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const { addMessage, updateMessage, setChatLoading, showNotification, getCurrentChat, getChatById, getProjectById } = useAppActions();
  const currentMessageRef = useRef<string | null>(null);
  const currentChatIdRef = useRef<string | null>(null);
  const socketAuthTokenRef = useRef<string | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const connectingRef = useRef<boolean>(false);
  const tokenRef = useRef<string | null>(null);
  const socketRecreateIntentRef = useRef(false);
  const reconnectScheduleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSendRef = useRef<PendingSendPayload | null>(null);
  const hasEverConnectedRef = useRef<boolean>(false);
  tokenRef.current = token;

  const clearReconnectSchedule = () => {
    if (reconnectScheduleRef.current) {
      clearTimeout(reconnectScheduleRef.current);
      reconnectScheduleRef.current = null;
    }
  };
  // Флаг: генерация была остановлена — блокирует создание дублей из in-flight событий
  const isStoppedRef = useRef<boolean>(false);
  const thinkingTraceRef = useRef<string>('');
  // Накопленный текст ответа (без thinking) для корректного совмещения при стриминге
  const responseAccumulatedRef = useRef<string>('');
  const mcpToolCallsRef = useRef<McpToolCallRecord[]>([]);

  const resolveMcpToolIds = (chatId: string): string[] => getMcpToolIdsForChat(chatId);

  const normalizeRagStrategy = (raw: string | null): string => {
    const s = (raw || 'auto').trim().toLowerCase();
    if (s === 'reranking') return 'hybrid';
    if (s === 'auto' || s === 'hierarchical' || s === 'hybrid' || s === 'standard' || s === 'graph') {
      return s;
    }
    return 'auto';
  };

  /** Собирает итоговое содержимое сообщения из thinking + response для отображения. */
  const buildCombinedContent = (thinking: string, response: string): string => {
    if (!thinking.trim()) return response;
    if (!response.trim()) return `<think>${thinking}</think>`;
    return `<think>${thinking}</think>\n\n${response}`;
  };

  const resolveEnableThinking = (): boolean => {
    const rawMode = (localStorage.getItem(MODEL_THINKING_MODE_STORAGE_KEY) || 'fast') as ModelThinkingMode;
    const mode: ModelThinkingMode =
      rawMode === 'thinking' || rawMode === 'auto' || rawMode === 'fast' ? rawMode : 'fast';
    const modelPath = localStorage.getItem(LAST_SELECTED_MODEL_PATH_STORAGE_KEY);
    return resolveEnableThinkingByMode(mode, modelPath);
  };
  
  // Ref для отслеживания режима перегенерации
  const regenerationStateRef = useRef<{
    isRegenerating: boolean;
    alternativeResponses: string[];
    currentIndex: number;
  } | null>(null);

  const resetStreamingRefs = () => {
    if (currentChatIdRef.current) {
      setChatLoading(currentChatIdRef.current, false);
    }
    isStoppedRef.current = true;
    expectMultiLlmResponseRef.current = false;
    regenerationStateRef.current = null;
    thinkingTraceRef.current = '';
    responseAccumulatedRef.current = '';

    if (currentChatIdRef.current && currentMessageRef.current) {
      updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
    }

    if (currentChatIdRef.current && multiLLMMessageRef.current) {
      updateMessage(currentChatIdRef.current, multiLLMMessageRef.current, undefined, false);
    }

    currentMessageRef.current = null;
    multiLLMMessageRef.current = null;
    multiLLMResponsesRef.current.clear();
    expectedModelsCountRef.current = 0;
  };

  const forceReconnect = async () => {
    if (!tokenRef.current) return;

    clearReconnectSchedule();
    socketRecreateIntentRef.current = true;
    connectingRef.current = false;

    setSocket((current) => {
      if (current) {
        current.io.off('reconnect');
        current.removeAllListeners();
        current.disconnect();
      }
      return null;
    });
    setIsConnected(false);
    setIsConnecting(true);

    await connectSocket();
  };

  const scheduleReconnect = (delayMs = 1000) => {
    clearReconnectSchedule();
    if (!tokenRef.current) return;
    reconnectScheduleRef.current = setTimeout(() => {
      reconnectScheduleRef.current = null;
      if (!tokenRef.current || connectingRef.current) return;
      void forceReconnect().catch((error) => {
        console.error('Не удалось переподключить WebSocket:', error);
        scheduleReconnect(Math.min(delayMs * 2, 10000));
      });
    }, delayMs);
  };

  const connectSocket = async () => {
    if (connectingRef.current) {
      return;
    }
    if (!tokenRef.current) {
      setIsConnecting(false);
      return;
    }
    connectingRef.current = true;

    // Устанавливаем флаг подключения
    setIsConnecting(true);
    
    // Гарантируем инициализацию конфигурации перед использованием getSettings().
    // Иначе при первом логине можно попасть в гонку: сокет стартует раньше загрузки config.yml.
    let settings;
    try {
      await initSettings();
      settings = getSettings();
    } catch (error) {
      console.error('Не удалось загрузить настройки для WebSocket:', error);
      setIsConnecting(false);
      connectingRef.current = false;
      // Повторяем подключение автоматически, чтобы не требовать ручной перезагрузки страницы.
      window.setTimeout(() => {
        connectSocket().catch((connectError) => {
          console.error('Повторная попытка подключения WebSocket завершилась ошибкой:', connectError);
        });
      }, 1000);
      return;
    }
    
    // Получаем настройки WebSocket из settings
    const wsConfig = settings.websocket;
    
    // Socket.IO ожидает HTTP/HTTPS URL, а не ws:// URL
    // Преобразуем ws:// обратно в http:// для Socket.IO
    let socketUrl = wsConfig.baseUrl;
    if (socketUrl.startsWith('ws://')) {
      socketUrl = socketUrl.replace('ws://', 'http://');
    } else if (socketUrl.startsWith('wss://')) {
      socketUrl = socketUrl.replace('wss://', 'https://');
    }
    
    // Логируем URL для отладки
    console.log('Socket.IO подключение к:', socketUrl);
    
    socketAuthTokenRef.current = tokenRef.current;

    const newSocket = io(socketUrl, {
      transports: ['websocket', 'polling'], // Добавляем fallback на polling
      autoConnect: false,
      timeout: wsConfig.timeout,
      reconnectionDelay: wsConfig.reconnectionDelay,
      reconnectionDelayMax: wsConfig.reconnectionDelayMax,
      reconnectionAttempts: wsConfig.reconnectionAttempts,
      forceNew: true, // Принудительно создаем новое соединение
      auth: {
        token: tokenRef.current,
      },
    });

    // engine.io ManagerOptions; в typings socket.io-client 4.x поле не объявлено
    Object.assign(newSocket.io.opts, { maxHttpBufferSize: SOCKET_MAX_HTTP_BUFFER_BYTES });

    newSocket.io.on('reconnect', () => {
      clearReconnectSchedule();
      setIsConnected(true);
      setIsConnecting(false);
      connectingRef.current = false;
    });

    // Подключение
    newSocket.on('connect', () => {
      clearReconnectSchedule();
      setIsConnected(true);
      setIsConnecting(false);
      connectingRef.current = false;
      const wasConnectedBefore = hasEverConnectedRef.current;
      hasEverConnectedRef.current = true;
      showNotification(
        'success',
        wasConnectedBefore ? 'Соединение восстановлено' : 'Соединение с сервером установлено',
      );
    });

    // Отключение
    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      const isIntentionalClientDisconnect = reason === 'io client disconnect';
      const isRecreate = socketRecreateIntentRef.current;
      if (isRecreate) {
        socketRecreateIntentRef.current = false;
      }
      const shouldNotifyDisconnect =
        hasEverConnectedRef.current && !isIntentionalClientDisconnect && !isRecreate;
      const shouldKeepConnecting = Boolean(tokenRef.current) && (!isIntentionalClientDisconnect || isRecreate);
      setIsConnecting(shouldKeepConnecting);
      if (shouldNotifyDisconnect) {
        showNotification('warning', 'Соединение с сервером потеряно. Переподключаемся...');
      }
      if (shouldKeepConnecting && !isRecreate) {
        scheduleReconnect(1500);
      }
    });

    // Ошибки подключения
    newSocket.on('connect_error', (error: any) => {
      setIsConnected(false);
      setIsConnecting(Boolean(tokenRef.current));
      connectingRef.current = false;
      if (hasEverConnectedRef.current && error.message && !error.message.includes('xhr poll error')) {
        showNotification('error', `Ошибка подключения: ${error.message || 'Неизвестная ошибка'}`);
      }
      scheduleReconnect(hasEverConnectedRef.current ? 2000 : 1500);
    });

    newSocket.io.on('reconnect_failed', () => {
      connectingRef.current = false;
      setIsConnected(false);
      setIsConnecting(Boolean(tokenRef.current));
      scheduleReconnect(1000);
    });

    // Обработка событий Socket.IO
    newSocket.on('chat_thinking', (data) => {
      
      handleServerMessage({ type: 'thinking', ...data });
    });

    newSocket.on('chat_chunk', (data) => {
      handleServerMessage({ type: 'chunk', ...data });
    });

    newSocket.on('chat_complete', (data) => {
      
      handleServerMessage({ type: 'complete', ...data });
    });

    newSocket.on('chat_error', (data) => {
      handleServerMessage({ type: 'error', ...data });
    });

    newSocket.on('generation_stopped', (data) => {
      handleServerMessage({ type: 'stopped', ...data });
    });

    // Обработка событий для режима multi-llm
    newSocket.on('multi_llm_start', (data) => {
      handleServerMessage({ type: 'multi_llm_start', ...data });
    });

    newSocket.on('multi_llm_chunk', (data) => {
      handleServerMessage({ type: 'multi_llm_chunk', ...data });
    });

    newSocket.on('multi_llm_complete', (data) => {
      handleServerMessage({ type: 'multi_llm_complete', ...data });
    });

    newSocket.on('chat_mcp_event', (data) => {
      handleServerMessage({ ...data, type: 'mcp_event', mcp_event_type: data.type });
    });

    setSocket(newSocket);
    
    newSocket.connect();
    
  };

  // Реф для хранения multi-llm сообщения
  const multiLLMMessageRef = useRef<string | null>(null);
  const multiLLMResponsesRef = useRef<Map<string, { model: string; content: string; isStreaming: boolean; error?: boolean }>>(new Map());
  const expectedModelsCountRef = useRef<number>(0); // Количество моделей, от которых ожидаем ответы
  /** Активен запрос multi-LLM с чата — блокирует обработку chat_chunk/chat_complete от старого tool-context и т.п. */
  const expectMultiLlmResponseRef = useRef<boolean>(false);

  /** Текст слота как на экране (учёт alternativeResponses / currentResponseIndex). */
  const multiSlotDisplayText = (slot: MultiLLMResponseSlot): string => {
    if (slot.alternativeResponses?.length && slot.currentResponseIndex !== undefined) {
      const i = slot.currentResponseIndex;
      if (i >= 0 && i < slot.alternativeResponses.length) return slot.alternativeResponses[i] ?? '';
    }
    return slot.content;
  };

  /** Сохраняем alternativeResponses и индекс при стриминге multi-LLM. */
  const mergeMultiLlmSocketPayload = (
    chatId: string,
    messageId: string,
    incoming: Array<{ model: string; content: string; isStreaming: boolean; error?: boolean }>,
  ): MultiLLMResponseSlot[] => {
    const chat = getChatById(chatId) as Chat | undefined;
    const msg = chat?.messages.find((m) => m.id === messageId);
    const prev = msg?.multiLLMResponses ?? [];
    if (prev.length === 0) {
      return incoming.map((r) => ({ ...r }));
    }
    const incomingByModel = new Map(incoming.map((r) => [r.model, r]));
    const order = prev.map((p) => p.model);
    for (const m of Array.from(incomingByModel.keys())) {
      if (!order.includes(m)) order.push(m);
    }
    return order.map((model) => {
      const inc = incomingByModel.get(model);
      const p = prev.find((x) => x.model === model);
      if (!inc && p) return p;
      if (!inc) return p!;
      if (!p) return { ...inc };
      const hasAlts =
        Array.isArray(p.alternativeResponses) &&
        p.alternativeResponses.length > 0 &&
        p.currentResponseIndex !== undefined &&
        p.currentResponseIndex >= 0;
      if (hasAlts) {
        const ci = p.currentResponseIndex!;
        const alts = [...p.alternativeResponses!];
        if (ci < alts.length) alts[ci] = inc.content;
        return {
          ...p,
          ...inc,
          alternativeResponses: alts,
          content: inc.content,
          currentResponseIndex: p.currentResponseIndex,
        };
      }
      return {
        ...p,
        ...inc,
        alternativeResponses: p.alternativeResponses,
        currentResponseIndex: p.currentResponseIndex,
      };
    });
  };

  const handleServerMessage = (data: any) => {
    const incomingRequestId = typeof data?.request_id === 'string' ? data.request_id : '';
    if (incomingRequestId && activeRequestIdRef.current && incomingRequestId !== activeRequestIdRef.current) {
      return;
    }

    switch (data.type) {
      case 'thinking':
        {
          if (
            isImageGenThinkingPayload(data) &&
            currentChatIdRef.current &&
            !isStoppedRef.current &&
            !expectMultiLlmResponseRef.current
          ) {
            const chatId = currentChatIdRef.current;
            if (currentMessageRef.current) {
              updateMessage(
                chatId,
                currentMessageRef.current,
                '',
                true,
                undefined,
                undefined,
                undefined,
                undefined,
                undefined,
                undefined,
                undefined,
                true,
              );
            } else {
              const messageId = addMessage(chatId, {
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                isStreaming: true,
                isImageGenerating: true,
              });
              currentMessageRef.current = messageId;
            }
            break;
          }

          const accumulated = typeof data?.accumulated === 'string' ? data.accumulated : '';
          const chunk = typeof data?.chunk === 'string' ? data.chunk : '';
          const thought = typeof data?.thinking === 'string' ? data.thinking : '';
          if (accumulated) {
            thinkingTraceRef.current = accumulated;
          } else if (thought || chunk) {
            thinkingTraceRef.current += thought || chunk;
          }

          // Обновляем сообщение в реальном времени, чтобы блок рассуждений
          // отображался по мере поступления, а не только после chat_complete
          if (!currentChatIdRef.current || isStoppedRef.current || expectMultiLlmResponseRef.current) {
            break;
          }
          const thinkingCombined = buildCombinedContent(
            thinkingTraceRef.current,
            responseAccumulatedRef.current,
          );
          if (currentMessageRef.current) {
            updateMessage(currentChatIdRef.current, currentMessageRef.current, thinkingCombined, true);
          } else {
            // Создаём сообщение заранее, чтобы thinking был виден до первого chunk
            const messageId = addMessage(currentChatIdRef.current, {
              role: 'assistant',
              content: thinkingCombined,
              timestamp: new Date().toISOString(),
              isStreaming: true,
            });
            currentMessageRef.current = messageId;
          }
        }
        break;

      case 'multi_llm_start':
        // Начало генерации от нескольких моделей
        if (!currentChatIdRef.current) return;

        expectMultiLlmResponseRef.current = true;

        expectedModelsCountRef.current = data.total_models || 0;
        
        // Создаем сообщение для multi-llm режима
        if (!multiLLMMessageRef.current) {
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            isStreaming: true,
            multiLLMResponses: [],
          });
          multiLLMMessageRef.current = messageId;
          multiLLMResponsesRef.current.clear();
        }
        break;

      case 'multi_llm_chunk':
        // Потоковая генерация от одной модели в режиме multi-llm
        if (!currentChatIdRef.current) return;
        if (isStoppedRef.current) return;

        expectMultiLlmResponseRef.current = true;

        const modelName = data.model || 'unknown';
        
        // Создаем или обновляем сообщение для multi-llm режима
        if (!multiLLMMessageRef.current) {
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            isStreaming: true,
            multiLLMResponses: [],
          });
          multiLLMMessageRef.current = messageId;
          multiLLMResponsesRef.current.clear();
        }
        
        // Обновляем ответ для конкретной модели
        const existingResponse = multiLLMResponsesRef.current.get(modelName);
        if (existingResponse) {
          existingResponse.content = data.accumulated || data.chunk;
          existingResponse.isStreaming = true;
        } else {
          multiLLMResponsesRef.current.set(modelName, {
            model: modelName,
            content: data.accumulated || data.chunk,
            isStreaming: true,
          });
        }
        
        // Обновляем сообщение с новыми данными
        if (multiLLMMessageRef.current) {
          const merged = mergeMultiLlmSocketPayload(
            currentChatIdRef.current,
            multiLLMMessageRef.current,
            Array.from(multiLLMResponsesRef.current.values()),
          );
          updateMessage(currentChatIdRef.current, multiLLMMessageRef.current, undefined, true, merged);
        }
        break;

      case 'multi_llm_complete':
        // Генерация от одной модели завершена
        if (!currentChatIdRef.current) return;
        if (isStoppedRef.current) return;
        
        const completedModel = data.model || 'unknown';
        const completedContent = data.response || '';
        const hasError = data.error || false;
        
        // Создаем сообщение для multi-llm режима, если его еще нет
        if (!multiLLMMessageRef.current) {
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            isStreaming: true,
            multiLLMResponses: [],
          });
          multiLLMMessageRef.current = messageId;
        }
        
        // Обновляем или добавляем ответ для завершенной модели
        multiLLMResponsesRef.current.set(completedModel, {
          model: completedModel,
          content: completedContent,
          isStreaming: false,
          error: hasError,
        });
        
        // Обновляем сообщение с актуальными данными
        const allResponses = mergeMultiLlmSocketPayload(
          currentChatIdRef.current,
          multiLLMMessageRef.current,
          Array.from(multiLLMResponsesRef.current.values()),
        );
        updateMessage(currentChatIdRef.current, multiLLMMessageRef.current, undefined, false, allResponses);
        
        // Считаем только РЕАЛЬНО завершённые модели (isStreaming === false),
        // а не .size — в Map могут быть модели, которые ещё стримят чанки.
        const completedCount = Array.from(multiLLMResponsesRef.current.values())
          .filter(r => !r.isStreaming).length;
        const expectedCount = expectedModelsCountRef.current;
        const totalFromEvent = typeof data.total === 'number' ? data.total : 0;
        const threshold = Math.max(expectedCount, totalFromEvent);

        if (threshold > 0 && completedCount >= threshold) {
          incrementTabNotification();
          if (currentChatIdRef.current) {
            setChatLoading(currentChatIdRef.current, false);
          }
          // НЕ сбрасываем expectMultiLlmResponseRef здесь — он должен оставаться true
          // до следующего sendMessage(), чтобы блокировать любой запоздалый chat_complete.
          const finalResponses = mergeMultiLlmSocketPayload(
            currentChatIdRef.current,
            multiLLMMessageRef.current,
            Array.from(multiLLMResponsesRef.current.values()),
          );
          updateMessage(
            currentChatIdRef.current,
            multiLLMMessageRef.current,
            undefined,
            false,
            finalResponses,
          );
          multiLLMMessageRef.current = null;
          multiLLMResponsesRef.current.clear();
          expectedModelsCountRef.current = 0;
          currentMessageRef.current = null;
          activeRequestIdRef.current = null;
          clearMcpToolActivity();
        }
        
        break;

      case 'chunk':
        // Потоковая генерация - обновляем существующее сообщение
        if (!currentChatIdRef.current) {
          
          return;
        }

        if (expectMultiLlmResponseRef.current || multiLLMMessageRef.current) {
          return;
        }
        
        // Накапливаем чистый текст ответа (без thinking) отдельно
        responseAccumulatedRef.current = data.accumulated || data.chunk;
        // Итоговый контент = thinking (если есть) + ответ
        const chunkCombined = buildCombinedContent(
          thinkingTraceRef.current,
          responseAccumulatedRef.current,
        );

        if (currentMessageRef.current) {
          // Проверяем, находимся ли мы в режиме перегенерации (используем ref вместо getCurrentChat)
          if (regenerationStateRef.current && regenerationStateRef.current.isRegenerating) {
            // Это перегенерация - используем данные из ref
            const updatedAlternatives = [...regenerationStateRef.current.alternativeResponses];
            const currentIndex = regenerationStateRef.current.currentIndex;
            
            // Обновляем ответ по текущему индексу
            if (currentIndex < updatedAlternatives.length) {
              updatedAlternatives[currentIndex] = chunkCombined;
            } else {
              updatedAlternatives.push(chunkCombined);
            }
            
            // Обновляем ref с новым содержимым
            regenerationStateRef.current.alternativeResponses = updatedAlternatives;
            
            updateMessage(
              currentChatIdRef.current,
              currentMessageRef.current,
              chunkCombined,
              true,
              undefined,
              updatedAlternatives,
              currentIndex
            );
          } else {
            // Обычное обновление
            updateMessage(currentChatIdRef.current, currentMessageRef.current, chunkCombined, true);
          }
        } else if (!isStoppedRef.current) {
          // Создаем новое сообщение для стриминга (только если генерация не была остановлена)
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: chunkCombined,
            timestamp: new Date().toISOString(),
            isStreaming: true,
          });
          currentMessageRef.current = messageId;
        }
        break;

      case 'complete': {
        // Если текущий запрос является multi-LLM (флаг остаётся true весь жизненный
        // цикл запроса, до следующего sendMessage), полностью игнорируем chat_complete:
        // финализация уже выполнена в multi_llm_complete, создавать обычное сообщение
        // или вызывать setLoading нельзя — это приведёт к дублю и зависанию кнопки стоп.
        if (expectMultiLlmResponseRef.current || multiLLMMessageRef.current) {
          break;
        }

        const rawDs = data.document_search;
        let docSearch:
          | {
              query: string;
              sourceFiles: string[];
              hits: Array<{
                file: string;
                anchor: string;
                relevance: number;
                content: string;
                chunkIndex: number;
                documentId: number;
                store: string;
              }>;
            }
          | undefined;
        if (rawDs && typeof rawDs === 'object') {
          const hits = Array.isArray(rawDs.hits) ? rawDs.hits : [];
          docSearch = {
            query: String(rawDs.query ?? ''),
            sourceFiles: Array.isArray(rawDs.sourceFiles)
              ? rawDs.sourceFiles.map(String)
              : Array.from(
                  new Set(hits.map((h: any) => String(h?.file ?? '')).filter(Boolean))
                ),
            hits: hits.map((h: any) => ({
              file: String(h?.file ?? ''),
              anchor: String(h?.anchor ?? ''),
              relevance: Number(h?.relevance ?? 0),
              content: String(h?.content ?? ''),
              chunkIndex: Number(h?.chunkIndex ?? h?.chunk_index ?? 0),
              documentId: Number(h?.documentId ?? h?.document_id ?? 0),
              store: String(h?.store ?? ''),
            })),
          };
        }

        // Показываем браузерное уведомление, если уведомления включены
        if (areNotificationsEnabled() && isNotificationSupported()) {
          try {
            showBrowserNotification('Сообщение готово', {
              body: 'Ассистент завершил генерацию ответа',
              icon: '/favicon.ico',
            });
          } catch (error) {
            console.error('Ошибка при показе уведомления:', error);
          }
        }
        incrementTabNotification();

        // КРИТИЧЕСКИ ВАЖНО: ВСЕГДА сбрасываем состояние загрузки В ПЕРВУЮ ОЧЕРЕДЬ
        if (currentChatIdRef.current) {
          setChatLoading(currentChatIdRef.current, false);
        }
        
        
        // ВАЖНО: Сначала пробуем получить chatId из ref, затем используем getCurrentChat
        const chatId = currentChatIdRef.current || getCurrentChat()?.id;
        
        
        if (!chatId) {
          
          // Даже если нет chatId, пытаемся сбросить currentMessageRef
          if (currentMessageRef.current) {
            currentMessageRef.current = null;
          }
          return;
        }
        
        const response = data.response || '';
        const responseWithReasoning =
          thinkingTraceRef.current.trim() && !response.includes('<think>')
            ? `<think>${thinkingTraceRef.current.trim()}</think>\n\n${response}`
            : response;
        const wasStreaming = Boolean(data.was_streaming);
        const genInlineAttachments = mapServerInlineAttachments(data.inline_attachments);

        if (currentMessageRef.current) {
          // Путь 1: сообщение отслеживалось через ref (потоковый режим)
          const trackedId = currentMessageRef.current;
          currentMessageRef.current = null;

          if (regenerationStateRef.current?.isRegenerating) {
            const regen = regenerationStateRef.current;
            const updatedAlts = [...regen.alternativeResponses];
            if (regen.currentIndex < updatedAlts.length) {
              updatedAlts[regen.currentIndex] = responseWithReasoning;
            } else {
              updatedAlts.push(responseWithReasoning);
            }
            const existingMsg = getChatById(chatId)?.messages.find((m) => m.id === trackedId);
            let variants = existingMsg?.inlineAttachmentVariants
              ? [...existingMsg.inlineAttachmentVariants]
              : [];
            if (!variants.length && existingMsg?.inlineAttachments?.length) {
              variants = [existingMsg.inlineAttachments];
            }
            if (genInlineAttachments?.length) {
              while (variants.length <= regen.currentIndex) {
                variants.push([]);
              }
              variants[regen.currentIndex] = genInlineAttachments;
            }
            const altResponses =
              variants.length > 1
                ? Array.from({ length: variants.length }, (_, i) => updatedAlts[i] ?? responseWithReasoning)
                : updatedAlts;
            updateMessage(
              chatId,
              trackedId,
              responseWithReasoning,
              false,
              undefined,
              altResponses,
              regen.currentIndex,
              docSearch,
              undefined,
              undefined,
              genInlineAttachments ?? variants[regen.currentIndex] ?? existingMsg?.inlineAttachments,
              false,
              variants.length ? variants : undefined,
            );
            regenerationStateRef.current = null;
          } else {
            const attachmentVariants = genInlineAttachments?.length ? [genInlineAttachments] : undefined;
            updateMessage(
              chatId,
              trackedId,
              responseWithReasoning,
              false,
              undefined,
              undefined,
              undefined,
              docSearch,
              undefined,
              undefined,
              genInlineAttachments,
              false,
              attachmentVariants,
            );
          }
        } else {
          // Путь 2: ref не установлен — ищем любое незавершённое сообщение
          const currentChat = getChatById(chatId) || getCurrentChat();
          const streamingMsgs = currentChat?.messages.filter(
            (m: Message) => m.isStreaming && m.role === 'assistant'
          ) ?? [];

          if (streamingMsgs.length > 0) {
            const last = streamingMsgs[streamingMsgs.length - 1];
            updateMessage(chatId, last.id, responseWithReasoning, false, undefined, undefined, undefined, docSearch, undefined, undefined, genInlineAttachments, false);
          } else if (!isStoppedRef.current && response) {
            // Непотоковый режим: создаём сообщение только если его ещё нет
            const alreadyExists = currentChat?.messages.some(
              (m: Message) => m.role === 'assistant' && m.content === response && !m.isStreaming
            );
            if (!alreadyExists) {
              addMessage(chatId, {
                role: 'assistant',
                content: responseWithReasoning,
                timestamp: data.timestamp || new Date().toISOString(),
                isStreaming: false,
                isImageGenerating: false,
                ...(docSearch ? { documentSearch: docSearch } : {}),
                ...(genInlineAttachments ? { inlineAttachments: genInlineAttachments } : {}),
              });
            }
          }
        }

        if (data.image_generation === true || genInlineAttachments?.length) {
          window.dispatchEvent(new CustomEvent('astrachatCreationsUpdated'));
        }

        thinkingTraceRef.current = '';
        responseAccumulatedRef.current = '';
        activeRequestIdRef.current = null;
        clearMcpToolActivity();
        break;
      }

      case 'error':
        if (typeof data.error === 'string') {
          const normalizedError = data.error.toLowerCase();
          if (normalizedError.includes('сессия завершена') || normalizedError.includes('не авторизован')) {
            resetStreamingRefs();
            if (socket) {
              socket.disconnect();
              setSocket(null);
            }
            localStorage.removeItem('auth_token');
            localStorage.removeItem('auth_user');
            showNotification('error', 'Сессия завершена. Выполнен вход в другом окне.');
            window.location.href = '/login';
            return;
          }
        }

        showNotification('error', `Ошибка сервера: ${data.error}`);
        if (currentChatIdRef.current) {
          setChatLoading(currentChatIdRef.current, false);
        }
        expectMultiLlmResponseRef.current = false;
        
        // Убираем флаг стриминга у текущего сообщения при ошибке
        if (currentChatIdRef.current && currentMessageRef.current) {
          updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
        }
        
        currentMessageRef.current = null;
        // НЕ очищаем currentChatIdRef при ошибке - он нужен для следующих запросов
        // currentChatIdRef.current = null; // УДАЛЕНО
        multiLLMMessageRef.current = null;
        multiLLMResponsesRef.current.clear();
        thinkingTraceRef.current = '';
        responseAccumulatedRef.current = '';
        activeRequestIdRef.current = null;
        break;
        
      case 'stopped':
        if (currentChatIdRef.current) {
          setChatLoading(currentChatIdRef.current, false);
        }
        isStoppedRef.current = true;
        expectMultiLlmResponseRef.current = false;
        
        // Убираем флаг стриминга у текущего сообщения
        if (currentChatIdRef.current && currentMessageRef.current) {
          updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
          currentMessageRef.current = null;
        }
        // Multi-LLM: снять стриминг у сообщения, затем полностью очистить refs,
        // чтобы запоздалые multi_llm_chunk/complete (уже в полёте) не создали новых сообщений.
        if (multiLLMMessageRef.current && currentChatIdRef.current) {
          const snap = Array.from(multiLLMResponsesRef.current.values()).map((r) => ({
            ...r,
            isStreaming: false,
          }));
          if (snap.length > 0) {
            const merged = mergeMultiLlmSocketPayload(
              currentChatIdRef.current,
              multiLLMMessageRef.current,
              snap,
            );
            updateMessage(
              currentChatIdRef.current,
              multiLLMMessageRef.current,
              undefined,
              false,
              merged,
            );
          } else {
            updateMessage(
              currentChatIdRef.current,
              multiLLMMessageRef.current,
              undefined,
              false,
            );
          }
        }
        multiLLMMessageRef.current = null;
        multiLLMResponsesRef.current.clear();
        expectedModelsCountRef.current = 0;
        thinkingTraceRef.current = '';
        responseAccumulatedRef.current = '';
        activeRequestIdRef.current = null;
        clearMcpToolActivity();
        break;

      case 'mcp_event': {
        if (isStoppedRef.current) break;
        const eventType = data.mcp_event_type === 'mcp_tool_end' ? 'mcp_tool_end' : 'mcp_tool_start';
        const record: McpToolCallRecord = {
          type: eventType,
          server_id: String(data.server_id || ''),
          tool: String(data.tool || ''),
          qualified_name: String(data.qualified_name || ''),
          success: data.success,
          duration_ms: data.duration_ms,
          error: data.error,
          model: data.model,
          timestamp: data.timestamp,
          result_preview: data.result_preview,
          has_image: data.has_image,
          has_audio: data.has_audio,
          has_resource: data.has_resource,
        };
        dispatchMcpToolActivity(record, eventType === 'mcp_tool_start' ? 'start' : 'end');
        mcpToolCallsRef.current = [...mcpToolCallsRef.current, record];
        const chatId = currentChatIdRef.current;
        const msgId = currentMessageRef.current || multiLLMMessageRef.current;
        if (chatId && msgId) {
          updateMessage(
            chatId,
            msgId,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            [...mcpToolCallsRef.current],
          );
        }
        break;
      }

      default:
        console.warn('Неизвестный тип сообщения:', data.type);
    }
  };

  const sendMessage = (
    message: string,
    chatId: string,
    streaming: boolean = true,
    overrideProjectId?: string | null,
    expectMultiLlm?: boolean,
    inlineData?: {
      inline_context?: string;
      inline_images?: string[];
      attachments_meta?: Array<{
        name: string;
        contentType: 'text' | 'image';
        preview?: string;
        minio_object?: string;
        minio_bucket?: string;
        size?: number;
      }>;
      inline_attachments?: Array<{
        name: string;
        contentType: 'text' | 'image';
        minio_object?: string;
        minio_bucket?: string;
        size?: number;
      }>;
    },
  ) => {
    if (!socket || !isConnected) {
      // При первом входе сокет может быть в фазе коннекта.
      // Сохраняем одно ожидающее сообщение и отправляем его после connect.
      pendingSendRef.current = { message, chatId, streaming, overrideProjectId, expectMultiLlm, inlineData };
      // Не прерываем активную попытку подключения — connect-обработчик сам отправит
      // отложенное сообщение. Reconnect нужен только если сокет не подключается прямо сейчас.
      if (!connectingRef.current) {
        reconnect();
      }
      showNotification('info', 'Подключаемся к серверу, сообщение будет отправлено автоматически');
      return;
    }
    
    // Сохраняем chatId для обработки ответов
    currentChatIdRef.current = chatId;
    
    // Новый запрос — снимаем флаг остановки
    isStoppedRef.current = false;

    expectMultiLlmResponseRef.current = Boolean(expectMultiLlm);
    const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    activeRequestIdRef.current = requestId;
    
    // Сбрасываем состояние для multi-llm режима
    multiLLMMessageRef.current = null;
    multiLLMResponsesRef.current.clear();
    expectedModelsCountRef.current = 0;
    thinkingTraceRef.current = '';
    responseAccumulatedRef.current = '';
    mcpToolCallsRef.current = [];
    clearMcpToolActivity();
    
    // Добавляем сообщение пользователя (с inline-вложениями для отображения в пузыре)
    const userMessageId = addMessage(chatId, {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
      ...(inlineData?.attachments_meta?.length
        ? { inlineAttachments: inlineData.attachments_meta }
        : {}),
    });

    // Устанавливаем состояние загрузки
    setChatLoading(chatId, true);
    currentMessageRef.current = null;

    if (!expectMultiLlm && isLikelyImageGenerationPrompt(message)) {
      const placeholderId = addMessage(chatId, {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
        isImageGenerating: true,
      });
      currentMessageRef.current = placeholderId;
    }

    // Читаем флаг "Base знаний" из localStorage (устанавливается в UnifiedChatPage)
    const useKbRag = localStorage.getItem('use_kb_rag') === 'true';
    const useMemoryLibraryRag = localStorage.getItem('use_memory_library_rag') === 'true';
    const ragStrategy = normalizeRagStrategy(localStorage.getItem('rag_strategy'));
    const rawAgentId = typeof localStorage !== 'undefined' ? localStorage.getItem('active_agent_id') : null;
    const parsedAgentId = rawAgentId ? parseInt(rawAgentId, 10) : NaN;
    const agentIdForChat = Number.isFinite(parsedAgentId) ? parsedAgentId : null;

    // Получаем данные проекта, к которому привязан чат.
    // overrideProjectId используется когда чат только что создан и state ещё не обновился.
    const chatForProject = getChatById(chatId);
    const projectId = overrideProjectId !== undefined ? overrideProjectId : (chatForProject?.projectId || null);
    const project = projectId ? getProjectById(projectId) : null;

    // Отправляем сообщение через Socket.IO
    const messageData = {
      message,
      streaming,
      timestamp: new Date().toISOString(),
      message_id: userMessageId,  // Передаем ID сообщения с фронтенда
      conversation_id: chatId,     // Передаем ID диалога
      use_kb_rag: useKbRag,
      use_memory_library_rag: useMemoryLibraryRag,
      rag_strategy: ragStrategy,
      /** Бэкенд подставит модель и model_settings из карточки агента (конструктор) */
      agent_id: agentIdForChat,
      project_id: projectId,
      project_memory: project?.memory || null,
      project_instructions: project?.instructions || null,
      model_comparison_enabled: Boolean(expectMultiLlm),
      enable_thinking: resolveEnableThinking(),
      // Inline-вложения (без RAG/эмбединга)
      inline_context: inlineData?.inline_context || undefined,
      inline_images: inlineData?.inline_images?.length ? inlineData.inline_images : undefined,
      inline_attachments: inlineData?.attachments_meta?.length
        ? inlineData.attachments_meta.map((a) => ({
            name: a.name,
            contentType: a.contentType,
            ...(a.minio_object ? { minio_object: a.minio_object } : {}),
            ...(a.minio_bucket ? { minio_bucket: a.minio_bucket } : {}),
            ...(typeof a.size === 'number' && a.size > 0 ? { size: a.size } : {}),
          }))
        : undefined,
      request_id: requestId,
      tool_ids: resolveMcpToolIds(chatId),
      image_gen_preset_id: readSelectedImageGenPresetId() || undefined,
    };

    socket!.emit('chat_message', messageData);
  };

  const regenerateMultiLlmSlot = (
    userMessage: string,
    assistantMessageId: string,
    chatId: string,
    slotModel: string,
    streaming: boolean = true,
    overrideProjectId?: string | null,
  ) => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }

    currentChatIdRef.current = chatId;
    currentMessageRef.current = null;
    regenerationStateRef.current = null;

    isStoppedRef.current = false;
    expectMultiLlmResponseRef.current = true;
    multiLLMMessageRef.current = assistantMessageId;
    multiLLMResponsesRef.current.clear();
    expectedModelsCountRef.current = 0;
    thinkingTraceRef.current = '';
    responseAccumulatedRef.current = '';
    const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    activeRequestIdRef.current = requestId;

    const chat = getChatById(chatId);
    const msg = chat?.messages.find((m) => m.id === assistantMessageId);
    if (msg?.multiLLMResponses) {
      for (const r of msg.multiLLMResponses) {
        multiLLMResponsesRef.current.set(r.model, {
          model: r.model,
          content: multiSlotDisplayText(r),
          isStreaming: r.model === slotModel,
          error: r.error,
        });
      }
    }

    setChatLoading(chatId, true);

    const useKbRag = localStorage.getItem('use_kb_rag') === 'true';
    const useMemoryLibraryRag = localStorage.getItem('use_memory_library_rag') === 'true';
    const ragStrategy = normalizeRagStrategy(localStorage.getItem('rag_strategy'));
    const rawAgentId = typeof localStorage !== 'undefined' ? localStorage.getItem('active_agent_id') : null;
    const parsedAgentId = rawAgentId ? parseInt(rawAgentId, 10) : NaN;
    const agentIdForChat = Number.isFinite(parsedAgentId) ? parsedAgentId : null;

    const chatForProject = getChatById(chatId);
    const projectId = overrideProjectId !== undefined ? overrideProjectId : (chatForProject?.projectId || null);
    const project = projectId ? getProjectById(projectId) : null;

    socket.emit('chat_message', {
      message: userMessage,
      streaming,
      timestamp: new Date().toISOString(),
      regenerate: true,
      assistant_message_id: assistantMessageId,
      conversation_id: chatId,
      multi_llm_slot_regenerate: slotModel,
      use_kb_rag: useKbRag,
      use_memory_library_rag: useMemoryLibraryRag,
      rag_strategy: ragStrategy,
      agent_id: agentIdForChat,
      project_id: projectId,
      project_memory: project?.memory || null,
      project_instructions: project?.instructions || null,
      model_comparison_enabled: true,
      enable_thinking: resolveEnableThinking(),
      request_id: requestId,
      tool_ids: resolveMcpToolIds(chatId),
    });
  };

  const regenerateResponse = (
    userMessage: string, 
    assistantMessageId: string, 
    chatId: string, 
    alternativeResponses: string[],
    currentIndex: number,
    streaming: boolean = true
  ) => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }
    
    // Сохраняем chatId и ID сообщения помощника для обработки ответов
    currentChatIdRef.current = chatId;
    currentMessageRef.current = assistantMessageId;
    
    // Новый запрос — снимаем флаг остановки
    isStoppedRef.current = false;
    
    // Сохраняем состояние перегенерации в ref
    regenerationStateRef.current = {
      isRegenerating: true,
      alternativeResponses: [...alternativeResponses], // Копируем массив
      currentIndex
    };
    
    // Сбрасываем состояние для multi-llm режима
    multiLLMMessageRef.current = null;
    multiLLMResponsesRef.current.clear();
    expectedModelsCountRef.current = 0;
    expectMultiLlmResponseRef.current = false;
    thinkingTraceRef.current = '';
    responseAccumulatedRef.current = '';
    mcpToolCallsRef.current = [];
    clearMcpToolActivity();
    const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    activeRequestIdRef.current = requestId;
    
    // Устанавливаем состояние загрузки
    setChatLoading(chatId, true);

    // Отправляем запрос на перегенерацию через Socket.IO
    // Используем тот же endpoint, но без создания нового сообщения пользователя
    const rawAgentId = typeof localStorage !== 'undefined' ? localStorage.getItem('active_agent_id') : null;
    const parsedAgentId = rawAgentId ? parseInt(rawAgentId, 10) : NaN;
    const agentIdForChat = Number.isFinite(parsedAgentId) ? parsedAgentId : null;
    const ragStrategy = normalizeRagStrategy(localStorage.getItem('rag_strategy'));

    const messageData = {
      message: userMessage,
      streaming,
      timestamp: new Date().toISOString(),
      regenerate: true, // Флаг перегенерации
      assistant_message_id: assistantMessageId, // ID сообщения помощника для обновления
      conversation_id: chatId,
      agent_id: agentIdForChat,
      rag_strategy: ragStrategy,
      enable_thinking: resolveEnableThinking(),
      request_id: requestId,
      tool_ids: resolveMcpToolIds(chatId),
      image_gen_preset_id: readSelectedImageGenPresetId() || undefined,
    };

    socket.emit('chat_message', messageData);
  };

  const stopGeneration = () => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }
    
    // Блокируем создание новых сообщений из in-flight событий (chunk/complete)
    isStoppedRef.current = true;
    
    // Отправляем команду остановки через Socket.IO
    socket.emit('stop_generation', {
      timestamp: new Date().toISOString(),
    });
    
    // Сразу останавливаем загрузку на фронтенде
    if (currentChatIdRef.current) {
      setChatLoading(currentChatIdRef.current, false);
    }
    expectMultiLlmResponseRef.current = false;
    clearMcpToolActivity();
    
    // Очищаем текущее сообщение и убираем флаг стриминга у всех сообщений
    if (currentChatIdRef.current && currentMessageRef.current) {
      updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
      currentMessageRef.current = null;
    }

    // Multi-LLM: снять стриминг и полностью очистить refs
    if (multiLLMMessageRef.current && currentChatIdRef.current) {
      const snap = Array.from(multiLLMResponsesRef.current.values()).map((r) => ({
        ...r,
        isStreaming: false,
      }));
      const merged =
        snap.length > 0
          ? mergeMultiLlmSocketPayload(
              currentChatIdRef.current,
              multiLLMMessageRef.current,
              snap,
            )
          : undefined;
      updateMessage(
        currentChatIdRef.current,
        multiLLMMessageRef.current,
        undefined,
        false,
        merged,
      );
    }
    multiLLMMessageRef.current = null;
    multiLLMResponsesRef.current.clear();
    expectedModelsCountRef.current = 0;
    thinkingTraceRef.current = '';
    responseAccumulatedRef.current = '';
    activeRequestIdRef.current = null;
    
    showNotification('info', 'Генерация остановлена');
  };

  const reconnect = () => {
    void forceReconnect().catch((error) => {
      console.error('Ошибка ручного переподключения WebSocket:', error);
      scheduleReconnect(2000);
    });
  };

  // До первого paint с токеном, но без сокета, isConnecting ещё false — чат показывал «нет соединения».
  useLayoutEffect(() => {
    if (!token) {
      setIsConnecting(false);
      return;
    }
    if (!isConnected) {
      setIsConnecting(true);
    }
  }, [token, isConnected]);

  useEffect(() => {
    if (!token) {
      clearReconnectSchedule();
      if (socket) {
        socketRecreateIntentRef.current = true;
        socket.removeAllListeners();
        socket.disconnect();
        setSocket(null);
      }
      setIsConnected(false);
      setIsConnecting(false);
      connectingRef.current = false;
      return;
    }

    const tokenChangedForActiveSocket =
      !!socket && !!socketAuthTokenRef.current && socketAuthTokenRef.current !== token;
    if (tokenChangedForActiveSocket) {
      void forceReconnect().catch((error) => {
        console.error('Ошибка переподключения WebSocket после смены токена:', error);
        scheduleReconnect(2000);
      });
      return;
    }

    if (!socket && !connectingRef.current) {
      void connectSocket().catch((error) => {
        console.error('Ошибка подключения WebSocket:', error);
        scheduleReconnect(2000);
      });
    }
  }, [token, socket]); // eslint-disable-line react-hooks/exhaustive-deps

  // Если сокет «завис» в disconnected-состоянии — пересоздаём соединение без F5.
  useEffect(() => {
    if (!token) return undefined;

    const watchdogId = window.setInterval(() => {
      if (!tokenRef.current || isConnected || connectingRef.current) return;
      scheduleReconnect(500);
    }, 8000);

    return () => {
      window.clearInterval(watchdogId);
    };
  }, [token, isConnected]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return;
      if (!tokenRef.current || isConnected || connectingRef.current) return;
      scheduleReconnect(300);
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [isConnected]);

  useEffect(() => {
    if (!isConnected || !socket || !pendingSendRef.current) return;
    const pending = pendingSendRef.current;
    pendingSendRef.current = null;
    sendMessage(pending.message, pending.chatId, pending.streaming, pending.overrideProjectId, pending.expectMultiLlm, pending.inlineData);
  }, [isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  const onMultiLLMEvent = (event: string, handler: (data: any) => void) => {
    if (socket) {
      socket.on(event, handler);
    }
  };

  const offMultiLLMEvent = (event: string, handler: (data: any) => void) => {
    if (socket) {
      socket.off(event, handler);
    }
  };

  const contextValue: SocketContextType = {
    socket,
    isConnected,
    isConnecting,
    sendMessage,
    regenerateResponse,
    regenerateMultiLlmSlot,
    stopGeneration,
    reconnect,
    onMultiLLMEvent,
    offMultiLLMEvent,
  };

  return (
    <SocketContext.Provider value={contextValue}>
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket() {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocket must be used within a SocketProvider');
  }
  return context;
}