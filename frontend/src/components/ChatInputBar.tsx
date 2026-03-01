import React, { RefObject, useState, useEffect } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Tooltip,
  Typography,
  CircularProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Send as SendIcon,
  Settings as SettingsIcon,
  Mic as MicIcon,
  Close as CloseIcon,
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

  /** 'compact' — текущий пилюльный стиль (по умолчанию);
   *  'classic' — прямоугольник с тулбаром кнопок снизу */
  styleVariant?: 'compact' | 'classic';
}

const iconButtonSx = (isDark: boolean, isClassic: boolean) => ({
  flexShrink: 0,
  width: 36,
  height: 36,
  borderRadius: isClassic ? '8px' : '50%',
  p: 0,
  '&:active': { transform: 'none' },
});

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
  styleVariant = 'compact',
}: ChatInputBarProps) {
  const getFileIcon = (file: UploadedFile) => {
    if (file.type?.includes('pdf')) return <PdfIcon fontSize="small" />;
    if (file.type?.includes('sheet') || file.type?.includes('excel')) return <ExcelIcon fontSize="small" />;
    return <DocumentIcon fontSize="small" />;
  };

  const isClassic = styleVariant === 'classic';

  // В компактном режиме: одна строка — кнопки по бокам; со 2-й строки — кнопки снизу
  const [compactMultiline, setCompactMultiline] = useState(false);
  useEffect(() => {
    if (isClassic) return;
    const el = inputRef?.current;
    if (!el) return;
    const raf = requestAnimationFrame(() => {
      const textarea = inputRef?.current;
      if (!textarea || typeof textarea.scrollHeight !== 'number') return;
      // одна строка ~24–28px; порог ниже, чтобы переключение было уже со 2-й строки
      setCompactMultiline(textarea.scrollHeight > 38);
    });
    return () => cancelAnimationFrame(raf);
  }, [value, isClassic, inputRef]);

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
    <Tooltip title="Дополнительные действия">
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
          <SettingsIcon sx={{ fontSize: '1.25rem' }} />
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
        sx={{
          width: '100%',
          maxWidth,
          borderRadius: '28px',
          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.04)',
          border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)'}`,
          overflow: 'hidden',
          ...containerSx,
        }}
      >
        {fileInput}
        <Box sx={{ px: 1.5, pt: 2.75, pb: 1 }}>
          {filesSection}
          {uploadingSection}
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
            {settingsBtn}
            {extraActions}
          </Box>

          {/* Правая группа: отчёт, отправить/стоп, голос */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            {reportBtn}
            {stopOrSendBtn}
            {voiceBtn}
          </Box>
        </Box>
      </Box>
    );
  }

  // ─── КОМПАКТНЫЙ стиль: 1 строка — кнопки по бокам; со 2-й строки — кнопки снизу ─
  const textFieldSx = {
    minWidth: 0,
    '& .MuiOutlinedInput-root': {
      bgcolor: 'transparent',
      border: 'none',
      fontSize: '0.875rem',
      py: 0.75,
      px: 2,
      '& fieldset': { border: 'none' },
      '&:hover': { bgcolor: 'transparent' },
      '&.Mui-focused': { bgcolor: 'transparent', '& fieldset': { border: 'none' } },
    },
  };

  return (
    <Box
      sx={{
        width: '100%',
        maxWidth,
        p: 1.5,
        px: 2,
        borderRadius: '28px',
        bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
        border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
        ...containerSx,
      }}
    >
      {fileInput}
      {filesSection}
      {uploadingSection}

      {compactMultiline ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, minHeight: 40 }}>
          <TextField
            inputRef={inputRef}
            multiline
            maxRows={8}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyPress={onKeyPress}
            onPaste={onPaste}
            placeholder={placeholder}
            variant="outlined"
            size="small"
            disabled={inputDisabled}
            fullWidth
            sx={textFieldSx}
          />
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'nowrap' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
              {attachBtn}
              {settingsBtn}
              {extraActions}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
              {reportBtn}
              {stopOrSendBtn}
              {voiceBtn}
            </Box>
          </Box>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'nowrap', minHeight: 40 }}>
          {attachBtn}
          <TextField
            inputRef={inputRef}
            multiline
            maxRows={8}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyPress={onKeyPress}
            onPaste={onPaste}
            placeholder={placeholder}
            variant="outlined"
            size="small"
            disabled={inputDisabled}
            sx={{ flex: 1, ...textFieldSx }}
          />
          {reportBtn}
          {settingsBtn}
          {extraActions}
          {stopOrSendBtn}
          {voiceBtn}
        </Box>
      )}
    </Box>
  );
}
