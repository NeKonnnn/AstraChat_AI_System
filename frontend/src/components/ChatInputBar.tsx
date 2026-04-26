import React, { RefObject, useState, useEffect, useRef } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Tooltip,
  Typography,
  CircularProgress,
} from '@mui/material';
import {
  CHAT_INPUT_BORDER_DARK,
  CHAT_INPUT_BORDER_LIGHT,
  CHAT_INPUT_SURFACE_DARK,
  CHAT_INPUT_SURFACE_LIGHT,
} from '../constants/workZoneBackground';
import {
  Add as AddIcon,
  Send as SendIcon,
  Widgets as WidgetsIcon,
  Mic as MicIcon,
  GraphicEq as DictationIcon,
  Close as CloseIcon,
  Check as CheckIcon,
  Assessment as AssessmentIcon,
  Square as SquareIcon,
  Description as DocumentIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
} from '@mui/icons-material';

export interface UploadedFile {
  name: string;
  type: string;
}

export interface ChatInputBarProps {
  value: string;
  onChange: (value: string) => void;
  onKeyPress: (e: React.KeyboardEvent) => void;
  onPaste?: (e: React.ClipboardEvent) => void | Promise<void>;
  placeholder?: string;
  inputDisabled?: boolean;
  inputRef?: RefObject<HTMLInputElement | HTMLTextAreaElement | null>;

  isDarkMode?: boolean;
  containerSx?: object;
  maxWidth?: string | number;

  fileInputRef?: RefObject<HTMLInputElement | null>;
  onAttachClick?: () => void;
  onFileSelect?: (files: FileList) => void;
  attachDisabled?: boolean;
  accept?: string;

  uploadedFiles?: UploadedFile[];
  onFileRemove?: (file: UploadedFile, index: number) => void;
  isUploading?: boolean;

  showReportButton?: boolean;
  onReportClick?: () => void;
  reportDisabled?: boolean;

  onSettingsClick?: (event: React.MouseEvent<HTMLElement>) => void;
  settingsDisabled?: boolean;

  showStopButton?: boolean;
  onStopClick?: () => void;
  onSendClick?: () => void;
  sendDisabled?: boolean;
  isSending?: boolean;

  onVoiceClick?: () => void;
  voiceDisabled?: boolean;
  voiceTooltip?: string;

  extraActions?: React.ReactNode;

  /** Между «вложения» и «инструменты»: например индикатор «Библиотека» при включённом RAG */
  libraryBadge?: React.ReactNode;

  /** 'compact' — текущий пилюльный стиль (по умолчанию);
   *  'classic' — прямоугольник с тулбаром кнопок снизу */
  styleVariant?: 'compact' | 'classic';

  /** Как на стандартном фоне рабочей зоны (тёмный / #fafafa), чтобы не терялось на чёрном «звёздном» фоне */
  solidWorkZoneBackground?: boolean;

  /** Верхняя граница всей «пилюли» ввода — для Popover «Инструменты» над полем, а не по кнопке (она съезжает при многострочном вводе) */
  toolsMenuAnchorRef?: RefObject<HTMLDivElement | null>;
}

const iconButtonSx = (isDark: boolean, isClassic: boolean) => ({
  flexShrink: 0,
  width: 36,
  height: 36,
  borderRadius: isClassic ? '8px' : '50%',
  p: 0,
  '&:active': { transform: 'none' },
});

const CHAT_INPUT_CONTRAST_KEY = 'chat_input_contrast';
const CHAT_INPUT_COLOR_KEY = 'chat_input_color';
const CHAT_INPUT_CONTRAST_DEFAULT = 35;
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export default function ChatInputBar({
  value,
  onChange,
  onKeyPress,
  onPaste,
  placeholder = 'Чем я могу помочь вам сегодня?',
  inputDisabled = false,
  inputRef,
  isDarkMode = false,
  containerSx,
  maxWidth = '100%',
  fileInputRef,
  onAttachClick,
  onFileSelect,
  attachDisabled = false,
  accept = '.pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png,.webp',
  uploadedFiles = [],
  onFileRemove,
  isUploading = false,
  showReportButton = false,
  onReportClick,
  reportDisabled = false,
  onSettingsClick,
  settingsDisabled = false,
  showStopButton = false,
  onStopClick,
  onSendClick,
  sendDisabled = false,
  isSending = false,
  onVoiceClick,
  voiceDisabled = false,
  voiceTooltip = 'Голосовой ввод',
  extraActions,
  libraryBadge,
  styleVariant = 'compact',
  solidWorkZoneBackground = false,
  toolsMenuAnchorRef,
}: ChatInputBarProps) {
  const getFileIcon = (file: UploadedFile) => {
    if (file.type?.includes('pdf')) return <PdfIcon fontSize="small" />;
    if (file.type?.includes('sheet') || file.type?.includes('excel')) return <ExcelIcon fontSize="small" />;
    return <DocumentIcon fontSize="small" />;
  };

  const isClassic = styleVariant === 'classic';
  const [isDictating, setIsDictating] = useState(false);
  const [dictationPreview, setDictationPreview] = useState('');
  const [waveLevels, setWaveLevels] = useState<number[]>(() => Array.from({ length: 72 }, () => 0.1));
  const recognitionRef = useRef<any>(null);
  const keepRunningRef = useRef(false);
  const dictationBaseTextRef = useRef('');
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const wavePhaseRef = useRef(0);
  const noiseFloorRef = useRef(0.004);
  const speakingRef = useRef(false);
  const silenceFramesRef = useRef(0);
  const finalTranscriptRef = useRef('');
  const interimTranscriptRef = useRef('');
  const [chatInputContrast, setChatInputContrast] = useState<number>(() => {
    if (typeof window === 'undefined') return CHAT_INPUT_CONTRAST_DEFAULT;
    const raw = Number(localStorage.getItem(CHAT_INPUT_CONTRAST_KEY));
    if (!Number.isFinite(raw)) return CHAT_INPUT_CONTRAST_DEFAULT;
    return clamp(raw, 20, 100);
  });
  const [chatInputColor, setChatInputColor] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    return localStorage.getItem(CHAT_INPUT_COLOR_KEY) || '';
  });

  const speechCtor =
    typeof window !== 'undefined'
      ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      : null;
  const canUseDictation = Boolean(speechCtor) && typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia);

  const concatText = (base: string, addition: string): string => {
    const left = base.trim();
    const right = addition.trim();
    if (!left) return right;
    if (!right) return left;
    return `${left} ${right}`;
  };

  const stopWave = () => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }
    analyserRef.current = null;
    speakingRef.current = false;
    silenceFramesRef.current = 0;
    setWaveLevels(Array.from({ length: 72 }, () => 0.1));
  };

  const stopDictation = (cancel: boolean) => {
    keepRunningRef.current = false;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch {
        // noop
      }
      recognitionRef.current = null;
    }
    stopWave();
    if (cancel) {
      onChange(dictationBaseTextRef.current);
    }
    setDictationPreview('');
    finalTranscriptRef.current = '';
    interimTranscriptRef.current = '';
    setIsDictating(false);
  };

  const startWave = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioStreamRef.current = stream;
    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext;
    const audioCtx = new Ctx();
    audioContextRef.current = audioCtx;
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.88;
    source.connect(analyser);
    analyserRef.current = analyser;
    const data = new Uint8Array(analyser.fftSize);
    const bars = 72;

    const tick = () => {
      if (!analyserRef.current) return;
      analyserRef.current.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i += 1) {
        const centered = (data[i] - 128) / 128;
        sumSquares += centered * centered;
      }
      const rms = Math.sqrt(sumSquares / Math.max(1, data.length));
      // Адаптивный шумовой пол: подстраивается к фоновой тишине/микрошуму микрофона.
      if (!speakingRef.current) {
        noiseFloorRef.current = noiseFloorRef.current * 0.97 + rms * 0.03;
      }
      const gateOn = noiseFloorRef.current + 0.0035;
      const gateOff = noiseFloorRef.current + 0.0018;
      if (speakingRef.current) {
        if (rms < gateOff) silenceFramesRef.current += 1;
        else silenceFramesRef.current = 0;
        if (silenceFramesRef.current > 8) speakingRef.current = false;
      } else if (rms > gateOn) {
        speakingRef.current = true;
        silenceFramesRef.current = 0;
      }

      const voiceLevel = clamp((rms - noiseFloorRef.current - 0.001) * 100, 0, 1);
      const speaking = speakingRef.current && voiceLevel > 0.015;

      // Паттерн справа налево только во время речи.
      if (speaking) wavePhaseRef.current += 0.22;
      const phase = wavePhaseRef.current;
      const next = new Array<number>(bars).fill(0).map((_, index) => {
        if (!speaking) return 0.1;
        const travel = Math.sin(index * 0.42 + phase) * 0.5 + 0.5;
        const ripple = Math.sin(index * 0.17 + phase * 0.63) * 0.5 + 0.5;
        const spread = travel * 0.7 + ripple * 0.3;
        return clamp(0.12 + voiceLevel * (0.25 + spread * 0.75), 0.1, 1);
      });
      setWaveLevels((prev) =>
        prev.map((p, i) => clamp(p * (speaking ? 0.74 : 0.86) + next[i] * (speaking ? 0.26 : 0.14), 0.1, 1)),
      );
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  const startDictation = async () => {
    if (!canUseDictation || isDictating || inputDisabled || voiceDisabled) return;
    try {
      await startWave();
    } catch {
      return;
    }

    const recognition = new speechCtor();
    recognition.lang = 'ru-RU';
    recognition.interimResults = true;
    recognition.continuous = true;

    dictationBaseTextRef.current = value;
    finalTranscriptRef.current = '';
    interimTranscriptRef.current = '';
    setDictationPreview('');
    keepRunningRef.current = true;
    setIsDictating(true);

    recognition.onresult = (event: any) => {
      let interim = '';
      let finalAppend = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i]?.[0]?.transcript ?? '';
        if (!text) continue;
        if (event.results[i].isFinal) finalAppend += ` ${text}`;
        else interim += ` ${text}`;
      }

      if (finalAppend.trim()) finalTranscriptRef.current = concatText(finalTranscriptRef.current, finalAppend);
      interimTranscriptRef.current = interim.trim();
      const merged = concatText(finalTranscriptRef.current, interimTranscriptRef.current);
      setDictationPreview(merged);
      onChange(concatText(dictationBaseTextRef.current, merged));
    };

    recognition.onerror = () => {
      stopDictation(false);
    };

    recognition.onend = () => {
      if (!keepRunningRef.current) return;
      try {
        recognition.start();
      } catch {
        stopDictation(false);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      stopDictation(false);
    }
  };

  useEffect(() => {
    return () => {
      stopDictation(false);
    };
  }, []);

  useEffect(() => {
    const syncContrast = () => {
      const raw = Number(localStorage.getItem(CHAT_INPUT_CONTRAST_KEY));
      setChatInputColor(localStorage.getItem(CHAT_INPUT_COLOR_KEY) || '');
      if (!Number.isFinite(raw)) {
        setChatInputContrast(CHAT_INPUT_CONTRAST_DEFAULT);
        return;
      }
      setChatInputContrast(clamp(raw, 20, 100));
    };
    syncContrast();
    window.addEventListener('interfaceSettingsChanged', syncContrast);
    return () => window.removeEventListener('interfaceSettingsChanged', syncContrast);
  }, []);

  const contrastDelta = chatInputContrast - CHAT_INPUT_CONTRAST_DEFAULT;
  const nonSolidBgAlpha = clamp(0.05 + contrastDelta * 0.004, 0.03, 0.32);
  const nonSolidBorderAlpha = clamp(0.1 + contrastDelta * 0.005, 0.06, 0.45);
  const nonSolidBoxShadowAlpha = clamp(0.08 + contrastDelta * 0.004, 0.06, 0.4);

  const shellBg = solidWorkZoneBackground
    ? isDarkMode
      ? CHAT_INPUT_SURFACE_DARK
      : CHAT_INPUT_SURFACE_LIGHT
    : isDarkMode
      ? `rgba(255, 255, 255, ${nonSolidBgAlpha})`
      : `rgba(0, 0, 0, ${nonSolidBgAlpha})`;
  const resolvedShellBg = chatInputColor || shellBg;

  const shellBorder = solidWorkZoneBackground
    ? isDarkMode
      ? isClassic
        ? 'rgba(255, 255, 255, 0.12)'
        : CHAT_INPUT_BORDER_DARK
      : isClassic
        ? 'rgba(0, 0, 0, 0.12)'
        : CHAT_INPUT_BORDER_LIGHT
    : isClassic
      ? isDarkMode
        ? `rgba(255, 255, 255, ${clamp(nonSolidBorderAlpha + 0.02, 0.08, 0.52)})`
        : `rgba(0, 0, 0, ${clamp(nonSolidBorderAlpha + 0.02, 0.08, 0.52)})`
      : isDarkMode
        ? `rgba(255, 255, 255, ${nonSolidBorderAlpha})`
        : `rgba(0, 0, 0, ${nonSolidBorderAlpha})`;

  const shellChrome = solidWorkZoneBackground
    ? {
        bgcolor: resolvedShellBg,
        backgroundColor: resolvedShellBg,
        border: `1px solid ${shellBorder}`,
        boxShadow: isDarkMode
          ? '0 2px 16px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)'
          : '0 2px 12px rgba(0,0,0,0.08)',
        position: 'relative' as const,
        zIndex: 1,
      }
    : {
        boxShadow: isDarkMode
          ? `0 2px 16px rgba(0,0,0,${nonSolidBoxShadowAlpha})`
          : `0 2px 12px rgba(0,0,0,${clamp(nonSolidBoxShadowAlpha * 0.9, 0.05, 0.35)})`,
        backdropFilter: `blur(${clamp(2 + contrastDelta * 0.12, 2, 9)}px)`,
      };

  // В компактном режиме: одна строка — кнопки по бокам; со 2-й строки — кнопки снизу.
  // Переключение по числу символов + гистерезис, чтобы не скакало (scrollHeight давал дребезг).
  const CHARS_FIRST_LINE = 100;   // примерно столько символов влезает в одну строку (шрифт 0.875rem, кнопки по бокам)
  const CHARS_SINGLE_BACK = 100;  // обратно в одну строку только когда короче (гистерезис)
  const [compactMultiline, setCompactMultiline] = useState(false);
  useEffect(() => {
    if (isClassic) return;
    const hasNewline = value.includes('\n');
    const len = value.length;
    setCompactMultiline((prev) => {
      if (hasNewline || len > CHARS_FIRST_LINE) return true;
      if (len <= CHARS_SINGLE_BACK) return false;
      return prev; // между 45 и 52 — не переключаем
    });
  }, [value, isClassic]);

  // ─── Переиспользуемые кнопки ────────────────────────────────────────────────

  const attachBtn = onAttachClick ? (
    <Tooltip title="Добавить файлы">
      <IconButton
        size="small"
        onClick={onAttachClick}
        disabled={attachDisabled}
        disableRipple
        sx={{
          color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
          bgcolor: 'transparent',
          border: '1px solid transparent',
          '&:hover:not(:disabled)': {
            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.18)' : 'rgba(0, 0, 0, 0.15)'}`,
            borderRadius: isClassic ? '8px' : '50%',
            color: 'primary.main',
            '& .MuiSvgIcon-root': { color: 'primary.main' },
          },
          '&:disabled': {
            color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
          },
          ...iconButtonSx(isDarkMode, isClassic),
        }}
      >
        <AddIcon sx={{ fontSize: '1.25rem' }} />
      </IconButton>
    </Tooltip>
  ) : null;

  const settingsBtn = onSettingsClick ? (
    <Tooltip title="Инструменты">
      <span>
        <IconButton
          size="small"
          onClick={onSettingsClick}
          disabled={settingsDisabled}
          sx={{
            color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
            bgcolor: 'transparent',
            border: '1px solid transparent',
            '&:hover:not(:disabled)': {
              bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
              border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.18)' : 'rgba(0, 0, 0, 0.15)'}`,
              borderRadius: isClassic ? '8px' : '50%',
              color: 'primary.main',
              '& .MuiSvgIcon-root': { color: 'primary.main' },
            },
            '&:disabled': {
              color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
            },
            ...iconButtonSx(isDarkMode, isClassic),
          }}
        >
          <WidgetsIcon sx={{ fontSize: '1.25rem' }} />
        </IconButton>
      </span>
    </Tooltip>
  ) : null;

  const reportBtn = showReportButton && onReportClick ? (
    <Tooltip title="Сгенерировать отчет об уверенности">
      <IconButton
        size="small"
        onClick={onReportClick}
        disabled={reportDisabled}
        disableRipple
        sx={{
          color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
          bgcolor: 'transparent',
          border: '1px solid transparent',
          '&:hover:not(:disabled)': {
            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.18)' : 'rgba(0, 0, 0, 0.15)'}`,
            borderRadius: isClassic ? '8px' : '50%',
            color: 'primary.main',
            '& .MuiSvgIcon-root': { color: 'primary.main' },
          },
          '&:disabled': {
            color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
          },
          ...iconButtonSx(isDarkMode, isClassic),
        }}
      >
        <AssessmentIcon sx={{ fontSize: '1.25rem' }} />
      </IconButton>
    </Tooltip>
  ) : null;

  const stopOrSendBtn = showStopButton && onStopClick ? (
    <Tooltip title="Прервать генерацию">
      <IconButton
        size="small"
        onClick={onStopClick}
        color="error"
        sx={{
          bgcolor: 'error.main',
          color: 'white',
          ...iconButtonSx(isDarkMode, isClassic),
          '&:hover': { bgcolor: 'error.dark' },
          animation: 'pulse 2s ease-in-out infinite',
          '@keyframes pulse': { '0%': { opacity: 1 }, '50%': { opacity: 0.7 }, '100%': { opacity: 1 } },
        }}
      >
        <SquareIcon sx={{ fontSize: '1.25rem' }} />
      </IconButton>
    </Tooltip>
  ) : onSendClick ? (
    <Tooltip title="Отправить">
      <span>
        <IconButton
          size="small"
          onClick={onSendClick}
          disabled={sendDisabled}
          sx={{
            color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
            bgcolor: 'transparent',
            border: '1px solid transparent',
            ...iconButtonSx(isDarkMode, isClassic),
            '&:hover:not(:disabled)': {
              bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
              border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.18)' : 'rgba(0, 0, 0, 0.15)'}`,
              borderRadius: isClassic ? '8px' : '50%',
              color: 'primary.main',
              '& .MuiSvgIcon-root': { color: 'primary.main' },
            },
            '&:disabled': {
              color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
            },
          }}
        >
          {isSending ? <CircularProgress size={18} sx={{ color: 'inherit' }} /> : <SendIcon sx={{ fontSize: '1.25rem' }} />}
        </IconButton>
      </span>
    </Tooltip>
  ) : null;

  const voiceBtn = onVoiceClick ? (
    <Tooltip title={voiceTooltip}>
      <IconButton
        size="small"
        onClick={onVoiceClick}
        disabled={voiceDisabled}
        sx={{
          color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
          bgcolor: 'transparent',
          border: '1px solid transparent',
          ...iconButtonSx(isDarkMode, isClassic),
          '&:hover:not(:disabled)': {
            bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.18)' : 'rgba(0, 0, 0, 0.15)'}`,
            borderRadius: isClassic ? '8px' : '50%',
            color: 'primary.main',
            '& .MuiSvgIcon-root': { color: 'primary.main' },
          },
          '&:disabled': {
            color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
          },
        }}
      >
        <MicIcon sx={{ fontSize: '1.25rem' }} />
      </IconButton>
    </Tooltip>
  ) : null;

  const dictationBtn = canUseDictation ? (
    <Tooltip title={isDictating ? 'Остановить диктовку' : 'Диктовка в поле ввода'}>
      <IconButton
        size="small"
        onClick={() => {
          if (isDictating) stopDictation(false);
          else void startDictation();
        }}
        disabled={voiceDisabled || inputDisabled}
        sx={{
          color: isDictating ? 'white' : isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)',
          bgcolor: isDictating ? 'primary.main' : 'transparent',
          border: `1px solid ${isDictating ? 'rgba(91, 105, 255, 0.65)' : 'transparent'}`,
          ...iconButtonSx(isDarkMode, isClassic),
          '&:hover:not(:disabled)': {
            bgcolor: isDictating ? 'primary.dark' : isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)',
            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.18)' : 'rgba(0, 0, 0, 0.15)'}`,
            borderRadius: isClassic ? '8px' : '50%',
            color: isDictating ? 'white' : 'primary.main',
            '& .MuiSvgIcon-root': { color: isDictating ? 'white' : 'primary.main' },
          },
          '&:disabled': {
            color: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
          },
        }}
      >
        <DictationIcon sx={{ fontSize: '1.25rem' }} />
      </IconButton>
    </Tooltip>
  ) : null;

  const dictationPanel = isDictating ? (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minHeight: 42, width: '100%' }}>
      <IconButton
        size="small"
        onClick={() => stopDictation(true)}
        sx={{
          ...iconButtonSx(isDarkMode, isClassic),
          color: isDarkMode ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.78)',
          bgcolor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
        }}
      >
        <CloseIcon sx={{ fontSize: '1.1rem' }} />
      </IconButton>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{ color: isDarkMode ? 'white' : '#1f1f1f', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', mb: 0.5 }}
        >
          {dictationPreview || 'Слушаю...'}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1px', height: 14, width: '100%' }}>
          {waveLevels.map((level, idx) => (
            <Box
              key={`dict-bar-${idx}`}
              sx={{
                flex: 1,
                borderRadius: 2,
                height: `${Math.max(3, Math.round(level * 14))}px`,
                bgcolor: isDarkMode ? 'rgba(255,255,255,0.86)' : 'rgba(33,33,33,0.86)',
                opacity: 0.45 + level * 0.55,
                transition: 'height 90ms linear, opacity 90ms linear',
                animation: 'dictationPulse 900ms ease-in-out infinite',
                animationDelay: `${idx * 28}ms`,
                '@keyframes dictationPulse': {
                  '0%': { transform: 'scaleY(0.72)' },
                  '50%': { transform: 'scaleY(1)' },
                  '100%': { transform: 'scaleY(0.72)' },
                },
              }}
            />
          ))}
        </Box>
      </Box>
      <IconButton
        size="small"
        onClick={() => stopDictation(false)}
        sx={{ ...iconButtonSx(isDarkMode, isClassic), color: 'white', bgcolor: 'primary.main', '&:hover': { bgcolor: 'primary.dark' } }}
      >
        <CheckIcon sx={{ fontSize: '1.1rem' }} />
      </IconButton>
    </Box>
  ) : null;

  // ─── Вложения и индикатор загрузки (общие для обоих стилей) ─────────────────

  const filesSection = uploadedFiles.length > 0 && onFileRemove ? (
    <Box sx={{ mb: isClassic ? 1.5 : 2 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {uploadedFiles.map((file, index) => (
          <Box
            key={`${file.name}-${index}`}
            className="file-attachment"
            sx={{
              display: 'flex', alignItems: 'center', gap: 1, p: 1,
              borderRadius: 2, maxWidth: '300px',
              bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
              border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'}`,
            }}
          >
            <Box sx={{ width: 32, height: 32, borderRadius: 1, bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: isDarkMode ? 'white' : '#333', flexShrink: 0, border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)'}` }}>
              {getFileIcon(file)}
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="caption" sx={{ fontWeight: 'medium', display: 'block', color: isDarkMode ? 'white' : '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={file.name}>
                {file.name}
              </Typography>
            </Box>
            <IconButton size="small" onClick={() => onFileRemove(file, index)} sx={{ color: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)', '&:hover': { color: '#ff6b6b', bgcolor: isDarkMode ? 'rgba(255, 107, 107, 0.2)' : 'rgba(255, 107, 107, 0.1)' }, p: 0.5, borderRadius: 1, flexShrink: 0 }}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        ))}
      </Box>
    </Box>
  ) : null;

  const uploadingSection = isUploading ? (
    <Box sx={{ mb: isClassic ? 1 : 2, p: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={16} sx={{ color: isDarkMode ? 'white' : '#333' }} />
        <Typography variant="caption" sx={{ color: isDarkMode ? 'white' : '#333' }}>Загрузка документа...</Typography>
      </Box>
    </Box>
  ) : null;

  // ─── Скрытый input для файлов ────────────────────────────────────────────────

  const fileInput = fileInputRef ? (
    <input
      ref={fileInputRef}
      type="file"
      accept={accept}
      style={{ display: 'none' }}
      onChange={(e) => {
        const files = e.target.files;
        if (files?.length && onFileSelect) onFileSelect(files);
        e.target.value = '';
      }}
    />
  ) : null;

  // ─── КЛАССИЧЕСКИЙ стиль ──────────────────────────────────────────────────────
  if (isClassic) {
    return (
      <Box
        ref={toolsMenuAnchorRef}
        sx={{
          width: '100%',
          maxWidth,
          borderRadius: '28px',
          overflow: 'hidden',
          ...containerSx,
          bgcolor: resolvedShellBg,
          border: `1px solid ${shellBorder}`,
          ...shellChrome,
        }}
      >
        {fileInput}
        <Box sx={{ px: 1.5, pt: 2.75, pb: 1 }}>
          {filesSection}
          {uploadingSection}
          {isDictating ? (
            dictationPanel
          ) : (
            <TextField
              inputRef={inputRef}
              multiline
              minRows={2}
              maxRows={8}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyPress={onKeyPress}
              onPaste={onPaste}
              placeholder={placeholder}
              variant="outlined"
              disabled={inputDisabled}
              fullWidth
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'transparent',
                  border: 'none',
                  fontSize: '0.95rem',
                  lineHeight: 1.6,
                  p: 0,
                  px: 0,
                  '& fieldset': { border: 'none' },
                  '&:hover': { bgcolor: 'transparent' },
                  '&.Mui-focused': { bgcolor: 'transparent', '& fieldset': { border: 'none' } },
                  '& textarea': { resize: 'none' },
                },
              }}
            />
          )}
        </Box>

        {/* Тулбар снизу */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 1.5,
            pb: 2.5,
            pt: 0,
            mt: 0,
          }}
        >
          {/* Левая группа: вложения, настройки, доп. действия */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            {attachBtn}
            {libraryBadge}
            {settingsBtn}
            {extraActions}
          </Box>

          {/* Правая группа: отчёт, отправить/стоп, голос */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            {isDictating ? null : reportBtn}
            {isDictating ? null : stopOrSendBtn}
            {isDictating ? null : voiceBtn}
            {dictationBtn}
          </Box>
        </Box>
      </Box>
    );
  }

  // ─── КОМПАКТНЫЙ стиль: 1 строка — кнопки по бокам; со 2-й строки — кнопки снизу ─
  // Один TextField всегда в DOM: при смене compactMultiline меняется только order и обёртка кнопок, фокус и перенос по ширине сохраняются
  const textFieldSx = {
    minWidth: 0,
    flex: compactMultiline ? undefined : 1,
    order: compactMultiline ? 0 : 1,
    '& .MuiOutlinedInput-root': {
      bgcolor: 'transparent',
      border: 'none',
      fontSize: '0.875rem',
      py: 0.75,
      px: 2,
      '& fieldset': { border: 'none' },
      '&:hover': { bgcolor: 'transparent' },
      '&.Mui-focused': { bgcolor: 'transparent', '& fieldset': { border: 'none' } },
      '& textarea': { resize: 'none', whiteSpace: 'pre-wrap', wordBreak: 'break-word' },
    },
  };

  return (
    <Box
      ref={toolsMenuAnchorRef}
      sx={{
        width: '100%',
        maxWidth,
        p: 1.5,
        px: 2,
        borderRadius: '28px',
        ...containerSx,
        bgcolor: resolvedShellBg,
        border: `1px solid ${shellBorder}`,
        ...shellChrome,
      }}
    >
      {fileInput}
      {filesSection}
      {uploadingSection}

      <Box
        sx={{
          display: 'flex',
          flexDirection: compactMultiline ? 'column' : 'row',
          alignItems: compactMultiline ? 'stretch' : 'center',
          gap: 0.5,
          flexWrap: 'nowrap',
          minHeight: 40,
        }}
      >
        {/* Один TextField на всё время — не переключаем разметку через два разных инпута, чтобы не терять фокус и курсор */}
        {isDictating ? (
          <Box sx={{ width: '100%' }}>{dictationPanel}</Box>
        ) : (
          <TextField
            inputRef={inputRef}
            multiline
            minRows={1}
            maxRows={8}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyPress={onKeyPress}
            onPaste={onPaste}
            placeholder={placeholder}
            variant="outlined"
            size="small"
            disabled={inputDisabled}
            fullWidth={compactMultiline}
            sx={textFieldSx}
          />
        )}
        {isDictating ? null : compactMultiline ? (
          <Box sx={{ order: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'nowrap' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
              {attachBtn}
              {libraryBadge}
              {settingsBtn}
              {extraActions}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
              {reportBtn}
              {stopOrSendBtn}
              {voiceBtn}
              {dictationBtn}
            </Box>
          </Box>
        ) : (
          <>
            <Box sx={{ order: 0, display: 'flex', alignItems: 'center', gap: 0.25 }}>
              {attachBtn}
              {libraryBadge}
              {settingsBtn}
              {extraActions}
            </Box>
            <Box sx={{ order: 2, display: 'flex', alignItems: 'center', gap: 0.25 }}>
              {reportBtn}
              {stopOrSendBtn}
              {voiceBtn}
              {dictationBtn}
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}