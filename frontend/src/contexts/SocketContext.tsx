import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAppActions } from './AppContext';
import { API_CONFIG } from '../config/api';

interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  sendMessage: (message: string, chatId: string, streaming?: boolean) => void;
  stopGeneration: () => void;
  reconnect: () => void;
  onMultiLLMEvent?: (event: string, handler: (data: any) => void) => void;
  offMultiLLMEvent?: (event: string, handler: (data: any) => void) => void;
}

const SocketContext = createContext<SocketContextType | null>(null);

export function SocketProvider({ children }: { children: ReactNode }) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const { addMessage, updateMessage, setLoading, showNotification, getCurrentChat } = useAppActions();
  const currentMessageRef = useRef<string | null>(null);
  const currentChatIdRef = useRef<string | null>(null);

  const connectSocket = () => {
    console.log('🔌 Подключение к Socket.IO...');
    
    const newSocket = io(API_CONFIG.BASE_URL, {
      transports: ['websocket', 'polling'], // Добавляем fallback на polling
      autoConnect: false,
      timeout: 20000, // Увеличиваем timeout
      forceNew: true, // Принудительно создаем новое соединение
    });

    // Подключение
    newSocket.on('connect', () => {
      console.log('WebSocket подключен');
      setIsConnected(true);
      showNotification('success', 'Соединение с сервером установлено');
    });

    // Отключение
    newSocket.on('disconnect', (reason) => {
      console.log('WebSocket отключен:', reason);
      setIsConnected(false);
      showNotification('warning', 'Соединение с сервером потеряно');
    });

    // Ошибки подключения
    newSocket.on('connect_error', (error: any) => {
      console.error('Ошибка подключения Socket.IO:', error);
      console.error('Тип ошибки:', error.type || 'unknown');
      console.error('Сообщение:', error.message || 'No message');
      console.error('Описание:', error.description || 'No description');
      setIsConnected(false);
      showNotification('error', `Ошибка подключения Socket.IO: ${error.message || 'Неизвестная ошибка'}`);
    });

    // Дополнительные события для отладки
    newSocket.on('disconnect', (reason, details) => {
      console.log('🔌 Socket.IO отключен:', reason, details);
      setIsConnected(false);
      showNotification('warning', `Соединение потеряно: ${reason}`);
    });

    newSocket.on('reconnect', (attemptNumber) => {
      console.log('Socket.IO переподключен, попытка:', attemptNumber);
      setIsConnected(true);
      showNotification('success', 'Соединение восстановлено');
    });

    newSocket.on('reconnect_error', (error) => {
      console.error('Ошибка переподключения Socket.IO:', error);
    });

    // Обработка событий Socket.IO
    newSocket.on('chat_chunk', (data) => {
      console.log('Получен chunk:', data);
      handleServerMessage({ type: 'chunk', ...data });
    });

    newSocket.on('chat_complete', (data) => {
      console.log('Чат завершен:', data);
      handleServerMessage({ type: 'complete', ...data });
    });

    newSocket.on('chat_error', (data) => {
      console.log('Ошибка чата:', data);
      handleServerMessage({ type: 'error', ...data });
    });

    newSocket.on('generation_stopped', (data) => {
      console.log('Генерация остановлена:', data);
      handleServerMessage({ type: 'stopped', ...data });
    });

    // Обработка событий для режима multi-llm
    newSocket.on('multi_llm_start', (data) => {
      console.log('Получен multi_llm_start:', data);
      handleServerMessage({ type: 'multi_llm_start', ...data });
    });

    newSocket.on('multi_llm_chunk', (data) => {
      console.log('Получен multi_llm_chunk:', data);
      handleServerMessage({ type: 'multi_llm_chunk', ...data });
    });

    newSocket.on('multi_llm_complete', (data) => {
      console.log('Получен multi_llm_complete:', data);
      handleServerMessage({ type: 'multi_llm_complete', ...data });
    });

    setSocket(newSocket);
    newSocket.connect();
  };

  // Реф для хранения multi-llm сообщения
  const multiLLMMessageRef = useRef<string | null>(null);
  const multiLLMResponsesRef = useRef<Map<string, { model: string; content: string; isStreaming: boolean; error?: boolean }>>(new Map());
  const expectedModelsCountRef = useRef<number>(0); // Количество моделей, от которых ожидаем ответы

  const handleServerMessage = (data: any) => {
    console.log('Получено сообщение:', data.type, data);

    switch (data.type) {
      case 'multi_llm_start':
        // Начало генерации от нескольких моделей
        if (!currentChatIdRef.current) return;
        
        console.log('multi_llm_start: ожидаем ответы от', data.total_models, 'моделей');
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
        
        console.log('multi_llm_complete получен для модели:', data.model);
        
        const completedModel = data.model || 'unknown';
        const completedContent = data.response || '';
        const hasError = data.error || false;
        
        // Создаем сообщение для multi-llm режима, если его еще нет
        if (!multiLLMMessageRef.current) {
          console.log('Создаем новое multi-llm сообщение');
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
        
        console.log('Текущее количество ответов от моделей:', multiLLMResponsesRef.current.size);
        console.log('Ответы от моделей:', Array.from(multiLLMResponsesRef.current.keys()));
        console.log('Ожидаем ответов от моделей:', expectedModelsCountRef.current);
        
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
        
        if (expectedCount > 0 && receivedCount >= expectedCount) {
          // Все модели ответили
          console.log('Все модели завершили генерацию:', receivedCount, '/', expectedCount);
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
          // Не очищаем рефы сразу, так как сообщение может быть просмотрено позже
          // Очистим их при следующем сообщении
        }
        
        break;

      case 'chunk':
        console.log('Обрабатывается chunk, current ID:', currentMessageRef.current);
        // Потоковая генерация - обновляем существующее сообщение
        if (!currentChatIdRef.current) return;
        
        if (currentMessageRef.current) {
          console.log('Обновляем существующее сообщение:', currentMessageRef.current);
          updateMessage(currentChatIdRef.current, currentMessageRef.current, data.accumulated || data.chunk, true);
        } else {
          // Создаем новое сообщение для стриминга
          console.log('Создаем новое сообщение для стриминга');
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: data.accumulated || data.chunk,
            timestamp: new Date().toISOString(),
            isStreaming: true,
          });
          currentMessageRef.current = messageId;
          console.log('Новое сообщение создано, ID:', messageId);
        }
        break;

      case 'complete':
        console.log('Генерация завершена, current ID:', currentMessageRef.current);
        // Генерация завершена
        if (!currentChatIdRef.current) return;
        
        if (currentMessageRef.current) {
          // Обновляем сообщение и убираем флаг стриминга
          console.log('Финализируем сообщение:', currentMessageRef.current);
          updateMessage(currentChatIdRef.current, currentMessageRef.current, data.response, false);
          currentMessageRef.current = null;
        } else {
          // Если нет текущего сообщения, создаем новое
          console.log('Создаем финальное сообщение');
          const finalMessageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: data.response,
            timestamp: data.timestamp || new Date().toISOString(),
            isStreaming: false,
          });
          console.log('Финальное сообщение создано, ID:', finalMessageId);
        }
        setLoading(false);
        currentChatIdRef.current = null; // Очищаем после завершения

        break;

      case 'error':
        console.error('Ошибка от сервера:', data.error);
        showNotification('error', `Ошибка сервера: ${data.error}`);
        setLoading(false);
        currentMessageRef.current = null;
        currentChatIdRef.current = null; // Очищаем при ошибке
        multiLLMMessageRef.current = null;
        multiLLMResponsesRef.current.clear();

        break;
        
      case 'stopped':
        console.log('Генерация остановлена сервером');

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
        currentChatIdRef.current = null; // Очищаем при остановке
        break;

      default:
        console.warn('Неизвестный тип сообщения:', data.type);
    }
  };

  const sendMessage = (message: string, chatId: string, streaming: boolean = true) => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }

    console.log('Отправка сообщения:', message.substring(0, 50) + '...');
    
    // Сохраняем chatId для обработки ответов
    currentChatIdRef.current = chatId;
    
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
    console.log('Сообщение пользователя добавлено, ID:', userMessageId);

    // Устанавливаем состояние загрузки
    setLoading(true);
    currentMessageRef.current = null;

    // Отправляем сообщение через Socket.IO
    const messageData = {
      message,
      streaming,
      timestamp: new Date().toISOString(),
    };

    socket.emit('chat_message', messageData);
    
    // Для режима multi-llm устанавливаем таймаут для завершения загрузки
    // если все модели не ответят в течение разумного времени
    setTimeout(() => {
      if (multiLLMMessageRef.current && currentChatIdRef.current) {
        // Если есть хотя бы один ответ от модели, завершаем загрузку
        if (multiLLMResponsesRef.current.size > 0) {
          setLoading(false);
          // Финализируем сообщение - убираем флаг стриминга
          const allResponses = Array.from(multiLLMResponsesRef.current.values());
          updateMessage(
            currentChatIdRef.current,
            multiLLMMessageRef.current,
            undefined,
            false,
            allResponses
          );
        }
      }
    }, 30000); // 30 секунд таймаут
  };

  const stopGeneration = () => {
    if (!socket || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }

    console.log('Отправка команды остановки генерации...');
    
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
    currentChatIdRef.current = null; // Очищаем при остановке
    
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
        console.log('🔌 Закрытие WebSocket соединения');
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
    sendMessage,
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
