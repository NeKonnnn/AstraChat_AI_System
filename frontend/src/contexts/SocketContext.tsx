import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAppActions } from './AppContext';
import type { Chat, Message, MultiLLMResponseSlot } from './AppContext';
import { useAuth } from './AuthContext';
import { getSettings } from '../settings';
import { 
  showBrowserNotification, 
  areNotificationsEnabled, 
  isNotificationSupported,
  requestNotificationPermission 
} from '../utils/browserNotifications';

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
  // Флаг: генерация была остановлена — блокирует создание дублей из in-flight событий
  const isStoppedRef = useRef<boolean>(false);

  const normalizeRagStrategy = (raw: string | null): string => {
    const s = (raw || 'auto').trim().toLowerCase();
    if (s === 'reranking') return 'hybrid';
    if (s === 'auto' || s === 'hierarchical' || s === 'hybrid' || s === 'standard' || s === 'graph') {
      return s;
    }
    return 'auto';
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

  const connectSocket = async () => {
    if (connectingRef.current) {
      return;
    }
    connectingRef.current = true;

    // Устанавливаем флаг подключения
    setIsConnecting(true);
    
    // Ждем инициализации настроек, если они еще не загружены
    let settings;
    const maxRetries = 50; // Максимум 5 секунд (50 * 100мс)
    let retries = 0;
    
    while (retries < maxRetries) {
      try {
        // Пробуем получить настройки
        settings = getSettings();
        break; // Успешно загружены
      } catch (error) {
        retries++;
        if (retries >= maxRetries) {
          console.error('Не удалось загрузить настройки для WebSocket после всех попыток:', error);
          setIsConnecting(false);
          connectingRef.current = false;
          return;
        }
        // Ждем перед следующей попыткой
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
    
    // Проверяем, что settings загружены (TypeScript guard)
    if (!settings) {
      console.error('Настройки не загружены после всех попыток');
      setIsConnecting(false);
      connectingRef.current = false;
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
    
    if (!token) {
      setIsConnecting(false);
      connectingRef.current = false;
      return;
    }

    socketAuthTokenRef.current = token;

    if (socket) {
      socket.disconnect();
      setSocket(null);
    }

    const newSocket = io(socketUrl, {
      transports: ['websocket', 'polling'], // Добавляем fallback на polling
      autoConnect: false,
      timeout: wsConfig.timeout,
      reconnectionDelay: wsConfig.reconnectionDelay,
      reconnectionDelayMax: wsConfig.reconnectionDelayMax,
      reconnectionAttempts: wsConfig.reconnectionAttempts,
      forceNew: true, // Принудительно создаем новое соединение
      auth: {
        token,
      },
    });

    // Подключение
    newSocket.on('connect', () => {
      setIsConnected(true);
      setIsConnecting(false);
      connectingRef.current = false;
      showNotification('success', 'Соединение с сервером установлено');
    });

    // Отключение
    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      showNotification('warning', 'Соединение с сервером потеряно');
    });

    // Ошибки подключения
    newSocket.on('connect_error', (error: any) => {
      
      setIsConnected(false);
      setIsConnecting(false);
      connectingRef.current = false;
      // Не показываем уведомление при каждой ошибке - только при критических
      if (error.message && !error.message.includes('xhr poll error')) {
        showNotification('error', `Ошибка подключения: ${error.message || 'Неизвестная ошибка'}`);
      }
    });

    newSocket.on('reconnect', (attemptNumber) => {
      setIsConnected(true);
      setIsConnecting(false);
      showNotification('success', 'Соединение восстановлено');
    });

    newSocket.on('reconnect_error', (error) => {
      
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
        // Обработка heartbeat сообщения о статусе обработки
        // Не создаем сообщение, так как это промежуточный статус
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
        
        if (currentMessageRef.current) {
          // Проверяем, находимся ли мы в режиме перегенерации (используем ref вместо getCurrentChat)
          if (regenerationStateRef.current && regenerationStateRef.current.isRegenerating) {
            // Это перегенерация - используем данные из ref
            const updatedAlternatives = [...regenerationStateRef.current.alternativeResponses];
            const currentIndex = regenerationStateRef.current.currentIndex;
            const newContent = data.accumulated || data.chunk;
            
            // Обновляем ответ по текущему индексу
            if (currentIndex < updatedAlternatives.length) {
              updatedAlternatives[currentIndex] = newContent;
            } else {
              updatedAlternatives.push(newContent);
            }
            
            // Обновляем ref с новым содержимым
            regenerationStateRef.current.alternativeResponses = updatedAlternatives;
            
            updateMessage(
              currentChatIdRef.current,
              currentMessageRef.current,
              newContent, // Обновляем message.content, чтобы он соответствовал текущему индексу
              true,
              undefined,
              updatedAlternatives,
              currentIndex
            );
          } else {
            // Обычное обновление
            updateMessage(currentChatIdRef.current, currentMessageRef.current, data.accumulated || data.chunk, true);
          }
        } else if (!isStoppedRef.current) {
          // Создаем новое сообщение для стриминга (только если генерация не была остановлена)
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: data.accumulated || data.chunk,
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
        const wasStreaming = Boolean(data.was_streaming);

        if (currentMessageRef.current) {
          // Путь 1: сообщение отслеживалось через ref (потоковый режим)
          const trackedId = currentMessageRef.current;
          currentMessageRef.current = null;

          if (regenerationStateRef.current?.isRegenerating) {
            const regen = regenerationStateRef.current;
            const updatedAlts = [...regen.alternativeResponses];
            if (regen.currentIndex < updatedAlts.length) {
              updatedAlts[regen.currentIndex] = response;
            } else {
              updatedAlts.push(response);
            }
            updateMessage(chatId, trackedId, response, false, undefined, updatedAlts, regen.currentIndex, docSearch);
            regenerationStateRef.current = null;
          } else {
            // В потоковом режиме контент уже накоплен через chunk-и,
            // поэтому принудительно перезаписываем только если НЕ был стриминг
            updateMessage(chatId, trackedId, wasStreaming ? undefined : response, false, undefined, undefined, undefined, docSearch);
          }
        } else {
          // Путь 2: ref не установлен — ищем любое незавершённое сообщение
          const currentChat = getChatById(chatId) || getCurrentChat();
          const streamingMsgs = currentChat?.messages.filter(
            (m: Message) => m.isStreaming && m.role === 'assistant'
          ) ?? [];

          if (streamingMsgs.length > 0) {
            const last = streamingMsgs[streamingMsgs.length - 1];
            updateMessage(chatId, last.id, wasStreaming ? last.content : response, false, undefined, undefined, undefined, docSearch);
          } else if (!isStoppedRef.current && response) {
            // Непотоковый режим: создаём сообщение только если его ещё нет
            const alreadyExists = currentChat?.messages.some(
              (m: Message) => m.role === 'assistant' && m.content === response && !m.isStreaming
            );
            if (!alreadyExists) {
              addMessage(chatId, {
                role: 'assistant',
                content: response,
                timestamp: data.timestamp || new Date().toISOString(),
                isStreaming: false,
                ...(docSearch ? { documentSearch: docSearch } : {}),
              });
            }
          }
        }

        activeRequestIdRef.current = null;
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
        activeRequestIdRef.current = null;
        break;

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
  ) => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
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
    
    // Добавляем сообщение пользователя
    const userMessageId = addMessage(chatId, {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    });

    // Устанавливаем состояние загрузки
    setChatLoading(chatId, true);
    currentMessageRef.current = null;
    

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
      request_id: requestId,
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
      request_id: requestId,
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
      request_id: requestId,
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
    activeRequestIdRef.current = null;
    
    showNotification('info', 'Генерация остановлена');
  };

  const reconnect = () => {
    if (socket) {
      socket.disconnect();
      setSocket(null);
    }
    setTimeout(connectSocket, 1000);
  };

  useEffect(() => {
    if (!token) {
      if (socket) {
        socket.disconnect();
        setSocket(null);
      }
      setIsConnected(false);
      setIsConnecting(false);
      return;
    }

    const tokenChangedForActiveSocket =
      !!socket && !!socketAuthTokenRef.current && socketAuthTokenRef.current !== token;
    if (tokenChangedForActiveSocket) {
      socket.disconnect();
      setSocket(null);
      setIsConnected(false);
      setIsConnecting(false);
      return;
    }

    if (!socket) {
      connectSocket().catch((error) => {
        console.error('Ошибка подключения WebSocket:', error);
      });
    }

    return () => {
      if (socket && !tokenChangedForActiveSocket) {
        socket.disconnect();
      }
    };
  }, [token, socket]); // eslint-disable-line react-hooks/exhaustive-deps

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
