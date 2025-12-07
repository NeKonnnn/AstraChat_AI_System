import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAppActions } from './AppContext';
import { API_CONFIG } from '../config/api';

interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  isConnecting: boolean;
  sendMessage: (message: string, chatId: string, streaming?: boolean) => void;
  regenerateResponse: (userMessage: string, assistantMessageId: string, chatId: string, alternativeResponses: string[], currentIndex: number, streaming?: boolean) => void;
  stopGeneration: () => void;
  reconnect: () => void;
  onMultiLLMEvent?: (event: string, handler: (data: any) => void) => void;
  offMultiLLMEvent?: (event: string, handler: (data: any) => void) => void;
}

const SocketContext = createContext<SocketContextType | null>(null);

export function SocketProvider({ children }: { children: ReactNode }) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const { addMessage, updateMessage, setLoading, showNotification, getCurrentChat, getChatById } = useAppActions();
  const currentMessageRef = useRef<string | null>(null);
  const currentChatIdRef = useRef<string | null>(null);
  
  // Ref для отслеживания режима перегенерации
  const regenerationStateRef = useRef<{
    isRegenerating: boolean;
    alternativeResponses: string[];
    currentIndex: number;
  } | null>(null);

  const connectSocket = () => {
    console.log('[SocketContext/connectSocket] ======== СОЗДАНИЕ НОВОГО SOCKET.IO СОЕДИНЕНИЯ ========');
    console.log('[SocketContext/connectSocket] URL:', API_CONFIG.BASE_URL);
    
    // Устанавливаем флаг подключения
    setIsConnecting(true);
    
    const newSocket = io(API_CONFIG.BASE_URL, {
      transports: ['websocket', 'polling'], // Добавляем fallback на polling
      autoConnect: false,
      timeout: 10000, // Уменьшаем timeout для более быстрой реакции
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 10, // Увеличиваем количество попыток
      forceNew: true, // Принудительно создаем новое соединение
    });
    console.log('[SocketContext/connectSocket] Socket.IO клиент создан, ID:', newSocket.id);

    // Подключение
    newSocket.on('connect', () => {
      console.log('[SocketContext/connect] ✓ СОЕДИНЕНИЕ УСТАНОВЛЕНО, Socket ID:', newSocket.id);
      setIsConnected(true);
      setIsConnecting(false);
      showNotification('success', 'Соединение с сервером установлено');
    });

    // Отключение
    newSocket.on('disconnect', (reason) => {
      console.log('[SocketContext/disconnect] ✗ СОЕДИНЕНИЕ ПОТЕРЯНО, причина:', reason);
      setIsConnected(false);
      showNotification('warning', 'Соединение с сервером потеряно');
    });

    // Ошибки подключения
    newSocket.on('connect_error', (error: any) => {
      console.error('[SocketContext/connect_error] ✗ ОШИБКА ПОДКЛЮЧЕНИЯ Socket.IO:');
      console.error('[SocketContext/connect_error]   - Тип:', error.type || 'unknown');
      console.error('[SocketContext/connect_error]   - Сообщение:', error.message || 'No message');
      console.error('[SocketContext/connect_error]   - Описание:', error.description || 'No description');
      console.error('[SocketContext/connect_error]   - URL:', API_CONFIG.BASE_URL);
      console.error('[SocketContext/connect_error]   - Transport:', newSocket.io?.engine?.transport?.name || 'unknown');
      setIsConnected(false);
      setIsConnecting(false);
      // Не показываем уведомление при каждой ошибке - только при критических
      if (error.message && !error.message.includes('xhr poll error')) {
        showNotification('error', `Ошибка подключения: ${error.message || 'Неизвестная ошибка'}`);
      }
    });

    // Дополнительные события для отладки
    newSocket.on('disconnect', (reason, details) => {
      setIsConnected(false);
      showNotification('warning', `Соединение потеряно: ${reason}`);
    });

    newSocket.on('reconnect', (attemptNumber) => {
      console.log('[SocketContext/reconnect] ✓ ПЕРЕПОДКЛЮЧЕНИЕ УСПЕШНО, попытка:', attemptNumber);
      setIsConnected(true);
      setIsConnecting(false);
      showNotification('success', 'Соединение восстановлено');
    });

    newSocket.on('reconnect_error', (error) => {
      console.error('[SocketContext/reconnect_error] Ошибка переподключения Socket.IO:', error);
    });

    // ОТЛАДКА: Логируем ВСЕ события Socket.IO
    newSocket.onAny((eventName, ...args) => {
      console.log(`[SocketContext/onAny] <<<< Получено событие: ${eventName}`, args);
    });

    // Обработка событий Socket.IO
    newSocket.on('chat_thinking', (data) => {
      console.log('[SocketContext/chat_thinking] Обработка события chat_thinking');
      handleServerMessage({ type: 'thinking', ...data });
    });

    newSocket.on('chat_chunk', (data) => {
      handleServerMessage({ type: 'chunk', ...data });
    });

    newSocket.on('chat_complete', (data) => {
      console.log('[SocketContext] ПОЛУЧЕНО СОБЫТИЕ chat_complete:', data);
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
    console.log('[SocketContext/connectSocket] Вызываем newSocket.connect()...');
    newSocket.connect();
    console.log('[SocketContext/connectSocket] newSocket.connect() вызван');
  };

  // Реф для хранения multi-llm сообщения
  const multiLLMMessageRef = useRef<string | null>(null);
  const multiLLMResponsesRef = useRef<Map<string, { model: string; content: string; isStreaming: boolean; error?: boolean }>>(new Map());
  const expectedModelsCountRef = useRef<number>(0); // Количество моделей, от которых ожидаем ответы

  const handleServerMessage = (data: any) => {
    switch (data.type) {
      case 'thinking':
        // Обработка heartbeat сообщения о статусе обработки
        // Не создаем сообщение, так как это промежуточный статус
        break;

      case 'multi_llm_start':
        // Начало генерации от нескольких моделей
        if (!currentChatIdRef.current) return;
        
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
          updateMessage(
            currentChatIdRef.current,
            multiLLMMessageRef.current,
            undefined,
            true,
            Array.from(multiLLMResponsesRef.current.values())
          );
        }
        break;

      case 'multi_llm_complete':
        // Генерация от одной модели завершена
        if (!currentChatIdRef.current) return;
        
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
        const allResponses = Array.from(multiLLMResponsesRef.current.values());
        updateMessage(
          currentChatIdRef.current,
          multiLLMMessageRef.current,
          undefined,
          false,
          allResponses
        );
        
        // Проверяем, все ли модели завершили генерацию
        const receivedCount = multiLLMResponsesRef.current.size;
        const expectedCount = expectedModelsCountRef.current;
        
        console.log('[SocketContext/multi_llm_complete] Получено ответов:', receivedCount, 'из', expectedCount);
        
        if (expectedCount > 0 && receivedCount >= expectedCount) {
          // Все модели ответили
          console.log('[SocketContext/multi_llm_complete] ВСЕ МОДЕЛИ ЗАВЕРШИЛИ - сбрасываем loading');
          setLoading(false);
          // Финализируем сообщение - убираем флаг стриминга
          const finalResponses = Array.from(multiLLMResponsesRef.current.values());
          updateMessage(
            currentChatIdRef.current,
            multiLLMMessageRef.current,
            undefined,
            false,
            finalResponses
          );
          // Очищаем рефы после завершения всех моделей
          multiLLMMessageRef.current = null;
          multiLLMResponsesRef.current.clear();
          expectedModelsCountRef.current = 0;
          currentMessageRef.current = null;
          // НЕ очищаем currentChatIdRef - он нужен для следующих запросов
          // currentChatIdRef.current = null; // УДАЛЕНО
        }
        
        break;

      case 'chunk':
        // Потоковая генерация - обновляем существующее сообщение
        if (!currentChatIdRef.current) {
          console.log('[SocketContext/chunk] ОШИБКА: currentChatIdRef.current === null, не можем обработать chunk!');
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
        } else {
          // Создаем новое сообщение для стриминга
          console.log('[SocketContext/chunk] Создаём новое сообщение для стриминга, chatId:', currentChatIdRef.current);
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: data.accumulated || data.chunk,
            timestamp: new Date().toISOString(),
            isStreaming: true,
          });
          currentMessageRef.current = messageId;
          console.log('[SocketContext/chunk] Новое сообщение создано, messageId:', messageId);
        }
        break;

      case 'complete':
        // Генерация завершена
        console.log('[SocketContext/complete] ============ ПОЛУЧЕНО СОБЫТИЕ chat_complete ============');
        console.log('[SocketContext/complete] data:', data);
        console.log('[SocketContext/complete] currentChatIdRef:', currentChatIdRef.current);
        console.log('[SocketContext/complete] currentMessageRef:', currentMessageRef.current);
        
        // КРИТИЧЕСКИ ВАЖНО: ВСЕГДА сбрасываем состояние загрузки В ПЕРВУЮ ОЧЕРЕДЬ
        setLoading(false);
        console.log('[SocketContext/complete] ✓ setLoading(false) вызван - индикатор загрузки должен исчезнуть');
        
        // ВАЖНО: Сначала пробуем получить chatId из ref, затем используем getCurrentChat
        const chatId = currentChatIdRef.current || getCurrentChat()?.id;
        console.log('[SocketContext] chatId из ref или getCurrentChat:', chatId);
        
        if (!chatId) {
          console.log('[SocketContext] Нет chatId, выходим');
          // Даже если нет chatId, пытаемся сбросить currentMessageRef
          if (currentMessageRef.current) {
            currentMessageRef.current = null;
          }
          return;
        }
        
        // КРИТИЧЕСКИ ВАЖНО: Сбрасываем isStreaming у currentMessageRef СРАЗУ
        // НЕЗАВИСИМО от того, найден ли чат в getChatById
        if (currentMessageRef.current) {
          console.log('[SocketContext] ПРИОРИТЕТНЫЙ сброс isStreaming для currentMessageRef:', currentMessageRef.current);
          console.log('[SocketContext] Параметры updateMessage:', {
            chatId,
            messageId: currentMessageRef.current,
            content: data.response ? `${data.response.substring(0, 30)}...` : 'undefined',
            isStreaming: false
          });
          updateMessage(chatId, currentMessageRef.current, data.response || undefined, false);
          console.log('[SocketContext] updateMessage вызван с isStreaming=false, ожидаем обновление UI');
          currentMessageRef.current = null;
        } else {
          console.log('[SocketContext] ВНИМАНИЕ: currentMessageRef.current === null, не можем сбросить isStreaming!');
        }
        
        // Получаем чат - пробуем сначала getChatById, затем getCurrentChat
        let currentChat = getChatById(chatId);
        if (!currentChat) {
          // FALLBACK: Если getChatById не нашёл чат, пробуем getCurrentChat
          const fallbackChat = getCurrentChat();
          if (fallbackChat?.id === chatId) {
            currentChat = fallbackChat;
            console.log('[SocketContext] FALLBACK: используем getCurrentChat');
          } else {
            console.log('[SocketContext] ПРОБЛЕМА: чат не найден ни через getChatById, ни через getCurrentChat');
            console.log('[SocketContext] chatId который ищем:', chatId);
            console.log('[SocketContext] getCurrentChat().id:', fallbackChat?.id);
          }
        }
        
        console.log('[SocketContext] currentChat найден:', !!currentChat, 'messages:', currentChat?.messages?.length);
        
        let messageUpdated = false;
        const wasStreaming = data.was_streaming || false;
        
        console.log('[SocketContext] data.response:', data.response ? `есть (${data.response.length} символов)` : 'НЕТ!');
        console.log('[SocketContext] currentChat:', currentChat ? 'есть' : 'НЕТ');
        console.log('[SocketContext] chatId:', chatId);
        
        if (currentChat && chatId && data.response) {
          // Ищем последнее сообщение со стримингом
          const streamingMessages = currentChat.messages.filter(msg => msg.isStreaming && msg.role === 'assistant');
          console.log('[SocketContext] Сообщений со стримингом:', streamingMessages.length);
          
          if (streamingMessages.length > 0) {
            // Обновляем последнее сообщение со стримингом - просто убираем флаг стриминга
            // Текст уже был обновлен через chat_chunk
            const lastStreamingMessage = streamingMessages[streamingMessages.length - 1];
            // Если был стриминг, используем текущий контент сообщения (он уже обновлен через чанки)
            // Иначе обновляем полным ответом
            const finalContent = wasStreaming ? lastStreamingMessage.content : data.response;
            console.log('[SocketContext] Обновляем сообщение:', lastStreamingMessage.id, 'isStreaming: false');
            updateMessage(chatId, lastStreamingMessage.id, finalContent, false);
            messageUpdated = true;
            // Очищаем ref, так как сообщение уже обновлено
            if (currentMessageRef.current === lastStreamingMessage.id) {
              currentMessageRef.current = null;
            }
          } else if (currentMessageRef.current && chatId) {
            // Если есть currentMessageRef, обновляем его
            // Проверяем, находимся ли мы в режиме перегенерации
            if (regenerationStateRef.current && regenerationStateRef.current.isRegenerating) {
              // Это перегенерация - используем данные из ref
              const updatedAlternatives = [...regenerationStateRef.current.alternativeResponses];
              const currentIndex = regenerationStateRef.current.currentIndex;
              
              // Обновляем или добавляем ответ по текущему индексу
              if (currentIndex < updatedAlternatives.length) {
                updatedAlternatives[currentIndex] = data.response;
              } else {
                updatedAlternatives.push(data.response);
              }
              
              updateMessage(
                chatId,
                currentMessageRef.current,
                data.response,
                false,
                undefined,
                updatedAlternatives,
                currentIndex
              );
              
              // Очищаем состояние перегенерации
              regenerationStateRef.current = null;
            } else {
              // Обычное обновление
              updateMessage(chatId, currentMessageRef.current, data.response, false);
            }
            messageUpdated = true;
            currentMessageRef.current = null;
          } else {
            // Проверяем, нет ли уже сообщения с таким же содержимым (защита от дублирования)
            const existingMessage = currentChat.messages.find(
              msg => msg.role === 'assistant' && msg.content === data.response && !msg.isStreaming
            );
            console.log('[SocketContext] existingMessage:', existingMessage ? 'найдено' : 'НЕТ');
            if (!existingMessage && chatId) {
              // Создаем новое сообщение только если его еще нет
              console.log('[SocketContext] СОЗДАЕМ НОВОЕ СООБЩЕНИЕ с контентом:', data.response.substring(0, 50));
              addMessage(chatId, {
                role: 'assistant',
                content: data.response,
                timestamp: data.timestamp || new Date().toISOString(),
                isStreaming: false,
              });
              messageUpdated = true;
            }
          }
        } else {
          console.log('[SocketContext] НЕ ВЫПОЛНЕНО условие для обработки response!');
          console.log('[SocketContext] currentChat:', !!currentChat, 'chatId:', !!chatId, 'data.response:', !!data.response);
        }
        
        // КРИТИЧЕСКИ ВАЖНО: ВСЕГДА сбрасываем флаги стриминга у ВСЕХ сообщений
        // независимо от того, было ли обновлено сообщение выше
        if (currentChat && chatId) {
          const allStreamingMessages = currentChat.messages.filter(msg => msg.isStreaming);
          console.log('[SocketContext] ГАРАНТИРОВАННЫЙ сброс ВСЕХ флагов стриминга. Найдено:', allStreamingMessages.length);
          if (allStreamingMessages.length > 0) {
            allStreamingMessages.forEach(msg => {
              console.log('[SocketContext] ГАРАНТИРОВАННЫЙ сброс isStreaming для:', msg.id, 'role:', msg.role);
              updateMessage(chatId, msg.id, undefined, false);
            });
          } else {
            console.log('[SocketContext] Нет сообщений со стримингом для сброса');
          }
        } else {
          console.log('[SocketContext] ПРЕДУПРЕЖДЕНИЕ: currentChat не найден через getChatById');
          console.log('[SocketContext] НО loading уже сброшен в false, так что кнопка должна исчезнуть');
        }
        
        // ДОПОЛНИТЕЛЬНАЯ ГАРАНТИЯ: НЕ ОЧИЩАЕМ currentChatIdRef здесь!
        // Он нужен для следующих сообщений
        // currentChatIdRef.current = null; // УДАЛЕНО - не очищаем
        
        console.log('[SocketContext] Обработка complete завершена, loading должен быть false');
        console.log('[SocketContext] currentChatIdRef после complete:', currentChatIdRef.current);
        break;

      case 'error':
        console.error('Ошибка от сервера:', data.error);
        showNotification('error', `Ошибка сервера: ${data.error}`);
        setLoading(false);
        
        // Убираем флаг стриминга у текущего сообщения при ошибке
        if (currentChatIdRef.current && currentMessageRef.current) {
          updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
        }
        
        currentMessageRef.current = null;
        // НЕ очищаем currentChatIdRef при ошибке - он нужен для следующих запросов
        // currentChatIdRef.current = null; // УДАЛЕНО
        multiLLMMessageRef.current = null;
        multiLLMResponsesRef.current.clear();
        break;
        
      case 'stopped':
        setLoading(false);
        
        // Убираем флаг стриминга у текущего сообщения
        if (currentChatIdRef.current && currentMessageRef.current) {
          updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
          currentMessageRef.current = null;
        }
        if (multiLLMMessageRef.current) {
          multiLLMMessageRef.current = null;
          multiLLMResponsesRef.current.clear();
        }
        // НЕ очищаем currentChatIdRef при остановке - он нужен для следующих запросов
        // currentChatIdRef.current = null; // УДАЛЕНО
        break;

      default:
        console.warn('Неизвестный тип сообщения:', data.type);
    }
  };

  const sendMessage = (message: string, chatId: string, streaming: boolean = true) => {
    console.log('[SocketContext/sendMessage] ==== НАЧАЛО ОТПРАВКИ СООБЩЕНИЯ ====');
    console.log('[SocketContext/sendMessage] Сообщение:', message.substring(0, 100) + (message.length > 100 ? '...' : ''));
    console.log('[SocketContext/sendMessage] Chat ID:', chatId);
    console.log('[SocketContext/sendMessage] Streaming:', streaming);
    console.log('[SocketContext/sendMessage] Socket:', socket ? 'есть' : 'НЕТ');
    console.log('[SocketContext/sendMessage] isConnected:', isConnected);
    
    if (!socket || !isConnected) {
      console.error('[SocketContext/sendMessage] ✗ НЕТ СОЕДИНЕНИЯ С СЕРВЕРОМ');
      showNotification('error', 'Нет соединения с сервером');
      return;
    }
    
    // Сохраняем chatId для обработки ответов
    currentChatIdRef.current = chatId;
    console.log('[SocketContext/sendMessage] ✓ currentChatIdRef.current установлен:', currentChatIdRef.current);
    
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
    setLoading(true);
    currentMessageRef.current = null;
    console.log('[SocketContext/sendMessage] Состояние: loading=true, currentMessageRef=null');

    // Отправляем сообщение через Socket.IO
    const messageData = {
      message,
      streaming,
      timestamp: new Date().toISOString(),
      message_id: userMessageId,  // Передаем ID сообщения с фронтенда
      conversation_id: chatId,     // Передаем ID диалога
    };

    console.log('[SocketContext/sendMessage] >>>> Отправка события chat_message:', messageData);
    socket.emit('chat_message', messageData);
    console.log('[SocketContext/sendMessage] ✓ Событие chat_message отправлено в Socket.IO');
    console.log('[SocketContext/sendMessage] ==== КОНЕЦ ОТПРАВКИ СООБЩЕНИЯ ====');
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
    
    // Устанавливаем состояние загрузки
    setLoading(true);

    // Отправляем запрос на перегенерацию через Socket.IO
    // Используем тот же endpoint, но без создания нового сообщения пользователя
    const messageData = {
      message: userMessage,
      streaming,
      timestamp: new Date().toISOString(),
      regenerate: true, // Флаг перегенерации
      assistant_message_id: assistantMessageId, // ID сообщения помощника для обновления
    };

    socket.emit('chat_message', messageData);
  };

  const stopGeneration = () => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }
    
    // Отправляем команду остановки через Socket.IO
    socket.emit('stop_generation', {
      timestamp: new Date().toISOString(),
    });
    
    // Сразу останавливаем загрузку на фронтенде
    setLoading(false);
    
    // Очищаем текущее сообщение и убираем флаг стриминга у всех сообщений
    if (currentChatIdRef.current && currentMessageRef.current) {
      // Убираем флаг стриминга у текущего сообщения
      updateMessage(currentChatIdRef.current, currentMessageRef.current, undefined, false);
      currentMessageRef.current = null;
    }
    // НЕ очищаем currentChatIdRef при остановке - он нужен для следующих запросов
    // currentChatIdRef.current = null; // УДАЛЕНО
    
    showNotification('info', 'Генерация остановлена');
  };

  const reconnect = () => {
    if (socket) {
      socket.disconnect();
    }
    setTimeout(connectSocket, 1000);
  };

  useEffect(() => {
    connectSocket();

    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
