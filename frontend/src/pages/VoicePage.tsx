import React, { useState, useRef, useEffect, useCallback } from 'react';
import { getApiUrl, getWsUrl, API_CONFIG } from '../config/api';
import { useLocation } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Container,
  Card,
  CardContent,
  IconButton,
  Button,
  Chip,
  LinearProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  CircularProgress,
  Fade,
} from '@mui/material';
import {
  Mic as MicIcon,
  VolumeUp as VolumeUpIcon,
  Send as SendIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useAppContext, useAppActions } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';

export default function VoicePage() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [recordedText, setRecordedText] = useState('');
  const [recordingTime, setRecordingTime] = useState(0);
  const [voiceSettings, setVoiceSettings] = useState({
    voice_id: 'ru',
    speech_rate: 1.0,
    voice_speaker: 'baya', // Добавляем выбор конкретного голоса
  });
  
  const { showNotification, setSpeaking, setRecording } = useAppActions();
  const { isConnected } = useSocket();
  
  // WebSocket для голосового чата
  const [voiceSocket, setVoiceSocket] = useState<WebSocket | null>(null);
  const [isVoiceConnected, setIsVoiceConnected] = useState(false);
  const [shouldReconnect, setShouldReconnect] = useState(true);
  
  // Real-time распознавание
  const [realtimeText, setRealtimeText] = useState('');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const currentStreamRef = useRef<MediaStream | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  
  // Таймер для автоматической остановки при тишине
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastAudioLevelRef = useRef<number>(0);
  const silenceThreshold = 0.1; // Порог тишины
  const silenceTimeout = 5000; // 5 секунд тишины для автоматической остановки

  // Функция очистки всех ресурсов
  const cleanupResources = () => {
    console.log('Начинаю очистку ресурсов...');
    
    // Сначала останавливаем локальные ресурсы
    // Останавливаем таймер тишины
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    
    // Останавливаем анимацию
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    
    // Останавливаем запись
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    }
    
    // Останавливаем медиа поток
    if (currentStreamRef.current) {
      currentStreamRef.current.getTracks().forEach(track => track.stop());
      currentStreamRef.current = null;
    }
    
    // Закрываем аудио контекст
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // Останавливаем воспроизведение
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = '';
      currentAudioRef.current = null;
    }
    
    // Сбрасываем состояние
    setIsRecording(false);
    setIsProcessing(false);
    setIsSpeaking(false);
    setRecordingTime(0);
    setRealtimeText('');
    setAudioLevel(0);
    
    // Сбрасываем глобальное состояние
    setRecording(false);
    setSpeaking(false);
    
    // Теперь отправляем команду остановки на backend (если WebSocket активен)
    if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
      try {
        console.log('Отправляю команду остановки на backend...');
        voiceSocket.send(JSON.stringify({
          type: "stop_processing",
          timestamp: new Date().toISOString()
        }));
        console.log('Команда остановки отправлена успешно');
      } catch (error) {
        console.error('Ошибка отправки команды остановки:', error);
        // Не критично - локальные ресурсы уже очищены
      }
    } else {
      console.log('WebSocket не активен, пропускаю отправку команды остановки');
    }
    
    console.log('Все ресурсы очищены, генерация остановлена');
    showNotification('info', 'Все процессы остановлены');
  };

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
              showNotification('success', 'Получен ответ от astrachat');
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
              
            case 'processing_stopped':
              console.log('WebSocket: Обработка остановлена');
              showNotification('info', 'Обработка остановлена');
              break;
              
            case 'processing_reset':
              console.log('WebSocket: Обработка возобновлена');
              showNotification('success', 'Обработка возобновлена');
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
      console.error('WebSocket error:', error);
      // Не устанавливаем isVoiceConnected в false при ошибке
      // Ошибки могут быть временными и не должны разрывать соединение
      showNotification('warning', 'Временная ошибка WebSocket, пытаюсь восстановить...');
      
      // Проверяем состояние соединения
      if (ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
        setIsVoiceConnected(false);
        // Автоматически переподключаемся через 3 секунды, только если разрешено
        setTimeout(() => {
          if (!isVoiceConnected && shouldReconnect) {
            showNotification('info', 'Попытка переподключения...');
            connectVoiceWebSocket();
          }
        }, 3000);
      }
    };
    
    ws.onclose = (event) => {
      console.log('WebSocket закрыт, код:', event.code, 'причина:', event.reason);
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

  // Убираем автоматическое подключение WebSocket
  // Теперь подключаемся только при нажатии на микрофон

  // Обновление глобального состояния
  useEffect(() => {
    setRecording(isRecording);
  }, [isRecording]);
  
  useEffect(() => {
    setSpeaking(isSpeaking);
  }, [isSpeaking]);

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

  // Функция переключения записи
  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
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

     const startRecording = async () => {
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
          
          // Также отправляем команду сброса флага остановки
          voiceSocket.send(JSON.stringify({ type: 'reset_processing' }));
          console.log('Отправлена команда сброса флага остановки');
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

     const stopRecording = () => {
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

  const processAudio = async (audioBlob: Blob) => {
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
      const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.VOICE_RECOGNIZE), {
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
      const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.CHAT), {
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
        showNotification('error', 'Ошибка получения ответа от astrachat');
      }
    } catch (error) {
      console.error('Ошибка отправки голосового сообщения:', error);
      showNotification('error', 'Ошибка отправки сообщения');
    }
  };

  const synthesizeSpeech = async (text: string) => {
    if (!text.trim()) return;

    console.log('Синтезирую речь из текста:', text);
    console.log('Используемые настройки голоса:', voiceSettings);

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
        voice_speaker: voiceSettings.voice_speaker
      };
      
      console.log('Отправляю запрос на синтез речи:', requestBody);
      
      const response = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.VOICE_SYNTHESIZE), {
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

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Заголовок */}
      <Paper elevation={2} sx={{ p: 2, borderRadius: 0 }}>
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="h5" fontWeight="600">
                🎤 Голосовой чат
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Общайтесь с astrachat голосом
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Chip
                label={isConnected ? 'Подключено' : 'Отключено'}
                color={isConnected ? 'success' : 'error'}
                size="small"
              />
            </Box>
          </Box>
        </Container>
      </Paper>

      {/* Основная область */}
      <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
        <Container maxWidth="md">
          <Card sx={{ p: 4, textAlign: 'center' }}>
            <CardContent>
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
                    onClick={toggleRecording}
                    disabled={isProcessing || isSpeaking}
                    sx={{
                      width: 120,
                      height: 120,
                      backgroundColor: 'white',
                      color: isRecording ? 'error.main' : 'primary.main',
                      '&:hover': {
                        backgroundColor: 'grey.100',
                      },
                    }}
                  >
                    {isRecording ? (
                      <StopIcon sx={{ fontSize: 48 }} />
                    ) : (
                      <MicIcon sx={{ fontSize: 48 }} />
                    )}
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
                    <Chip
                      icon={<VolumeUpIcon />}
                      label="Говорю"
                      color="success"
                      size="small"
                    />
                  </Box>
                )}
              </Box>

              {/* Кнопка экстренной остановки - перемещена в более видимое место */}
              {(isRecording || isProcessing || isSpeaking) && (
                <Box sx={{ mb: 3, display: 'flex', justifyContent: 'center' }}>
                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<StopIcon />}
                    onClick={cleanupResources}
                    sx={{
                      px: 3,
                      py: 1.5,
                      fontSize: '1.1rem',
                      fontWeight: 'bold',
                    }}
                  >
                    Остановить все процессы
                  </Button>
                </Box>
              )}

              {/* Статус записи */}
              <Box sx={{ mb: 2 }}>
                {isRecording && (
                  <Box sx={{ textAlign: 'center', mb: 2 }}>
                    <Typography variant="h6" color="error.main" gutterBottom>
                      Прослушивание... {Math.floor(recordingTime / 60)}:{(recordingTime % 60).toString().padStart(2, '0')}
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'error.main', animation: 'pulse 1s infinite' }} />
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'error.main', animation: 'pulse 1s infinite', animationDelay: '0.2s' }} />
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'error.main', animation: 'pulse 1s infinite', animationDelay: '0.4s' }} />
                    </Box>
                  </Box>
                )}
                
                <Typography variant="h6" gutterBottom>
                  {isRecording && 'Говорите четко и ясно...'}
                  {isProcessing && 'Обрабатываю речь...'}
                  {isSpeaking && 'Говорю ответ...'}
                  {!isRecording && !isProcessing && !isSpeaking && 'Нажмите для прослушивания'}
                </Typography>
              </Box>

              {/* Индикатор подключения WebSocket */}
              <Box sx={{ mb: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1 }}>
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

              {/* Инструкции */}
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                {isRecording 
                  ? 'Говорите четко и ясно. Real-time распознавание каждые 2 секунды. Автоматическая остановка через 5 секунд тишины.'
                  : isProcessing || isSpeaking
                    ? 'Микрофон заблокирован пока astrachat обрабатывает ваш запрос...'
                    : 'Нажмите на микрофон и задайте свой вопрос голосом. WebSocket подключится автоматически.'
                }
              </Typography>

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
              {(isProcessing || isSpeaking) && (
                <LinearProgress sx={{ mb: 2 }} />
              )}

              {/* Предупреждения */}
              {!isConnected && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Нет соединения с сервером. Голосовой чат недоступен.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Container>
      </Box>
    </Box>
  );
}
