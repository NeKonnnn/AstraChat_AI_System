import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAppActions } from './AppContext';
import { API_CONFIG } from '../config/api';

interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
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

  const { addMessage, updateMessage, setLoading, showNotification, getCurrentChat } = useAppActions();
  const currentMessageRef = useRef<string | null>(null);
  const currentChatIdRef = useRef<string | null>(null);
  
  // Ref для отслеживания режима перегенерации
  const regenerationStateRef = useRef<{
    isRegenerating: boolean;
    alternativeResponses: string[];
    currentIndex: number;
  } | null>(null);

  const connectSocket = () => {
    const newSocket = io(API_CONFIG.BASE_URL, {
      transports: ['websocket', 'polling'], // Добавляем fallback на polling
      autoConnect: false,
      timeout: 60000, // Увеличиваем timeout до 60 секунд
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
      forceNew: true, // Принудительно создаем новое соединение
    });

    // Подключение
    newSocket.on('connect', () => {
      setIsConnected(true);
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
      showNotification('error', `Ошибка подключения Socket.IO: ${error.message || 'Неизвестная ошибка'}`);
    });

    // Дополнительные события для отладки
    newSocket.on('disconnect', (reason, details) => {
      setIsConnected(false);
      showNotification('warning', `Соединение потеряно: ${reason}`);
    });

    newSocket.on('reconnect', (attemptNumber) => {
      setIsConnected(true);
      showNotification('success', 'Соединение восстановлено');
    });

    newSocket.on('reconnect_error', (error) => {
      console.error('Ошибка переподключения Socket.IO:', error);
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
        
        if (expectedCount > 0 && receivedCount >= expectedCount) {
          // Все модели ответили
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
        // Потоковая генерация - обновляем существующее сообщение
        if (!currentChatIdRef.current) return;
        
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
          const messageId = addMessage(currentChatIdRef.current, {
            role: 'assistant',
            content: data.accumulated || data.chunk,
            timestamp: new Date().toISOString(),
            isStreaming: true,
          });
          currentMessageRef.current = messageId;
        }
        break;

      case 'complete':
        // Генерация завершена
        if (!currentChatIdRef.current) {
          setLoading(false);
          return;
        }
        
        if (currentMessageRef.current) {
          // Обновляем сообщение и ЯВНО убираем флаг стриминга
          
          // Проверяем, находимся ли мы в режиме перегенерации (используем ref вместо getCurrentChat)
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
              currentChatIdRef.current,
              currentMessageRef.current,
              data.response, // Обновляем message.content, чтобы он соответствовал текущему индексу
              false,
              undefined,
              updatedAlternatives,
              currentIndex
            );
            
            // Очищаем состояние перегенерации
            regenerationStateRef.current = null;
          } else {
            // Обычное обновление
            updateMessage(currentChatIdRef.current, currentMessageRef.current, data.response, false);
          }
          
          currentMessageRef.current = null;
        } else {
          // Если нет текущего сообщения, но есть ответ, пытаемся найти сообщение со стримингом
          if (data.response) {
            // Пытаемся найти последнее сообщение с isStreaming: true в текущем чате
            const currentChat = getCurrentChat();
            if (currentChat && currentChat.id === currentChatIdRef.current) {
              const streamingMessages = currentChat.messages.filter(msg => msg.isStreaming && msg.role === 'assistant');
              if (streamingMessages.length > 0) {
                // Обновляем последнее сообщение со стримингом
                const lastStreamingMessage = streamingMessages[streamingMessages.length - 1];
                updateMessage(currentChatIdRef.current, lastStreamingMessage.id, data.response, false);
              } else {
                // Создаем новое сообщение (например, в агентном режиме без потоковой генерации)
                addMessage(currentChatIdRef.current, {
                  role: 'assistant',
                  content: data.response,
                  timestamp: data.timestamp || new Date().toISOString(),
                  isStreaming: false,
                });
              }
            } else {
              // Создаем новое сообщение, если не удалось найти чат
              addMessage(currentChatIdRef.current, {
                role: 'assistant',
                content: data.response,
                timestamp: data.timestamp || new Date().toISOString(),
                isStreaming: false,
              });
            }
          } else {
            // Если нет ответа, просто сбрасываем флаги стриминга у всех сообщений в чате
            const currentChat = getCurrentChat();
            if (currentChat && currentChat.id === currentChatIdRef.current) {
              const streamingMessages = currentChat.messages.filter(msg => msg.isStreaming && msg.role === 'assistant');
              streamingMessages.forEach(msg => {
                updateMessage(currentChatIdRef.current!, msg.id, undefined, false);
              });
            }
          }
        }
        setLoading(false);
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
        currentChatIdRef.current = null; // Очищаем при ошибке
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

    // Устанавливаем состояние загрузки
    setLoading(true);
    currentMessageRef.current = null;

    // Отправляем сообщение через Socket.IO
    const messageData = {
      message,
      streaming,
      timestamp: new Date().toISOString(),
      message_id: userMessageId,  // Передаем ID сообщения с фронтенда
      conversation_id: chatId,     // Передаем ID диалога
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
