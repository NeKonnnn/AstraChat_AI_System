import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Checkbox,
  FormControlLabel,
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Link,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { Close as CloseIcon, ContentCopy as CopyIcon } from '@mui/icons-material';
import { Message } from '../contexts/AppContext';

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
  messages: Message[];
  isDarkMode: boolean;
}

export const ShareDialog: React.FC<ShareDialogProps> = ({
  open,
  onClose,
  messages,
  isDarkMode,
}) => {
  const [selectedMessages, setSelectedMessages] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectAll, setSelectAll] = useState(false);

  // Получаем пары вопрос-ответ
  const messagePairs = React.useMemo(() => {
    const pairs: Array<{ user: Message; assistant: Message; index: number }> = [];
    for (let i = 0; i < messages.length - 1; i++) {
      if (messages[i].role === 'user' && messages[i + 1].role === 'assistant') {
        pairs.push({
          user: messages[i],
          assistant: messages[i + 1],
          index: i,
        });
      }
    }
    return pairs;
  }, [messages]);

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedMessages(new Set());
    } else {
      const allIds = new Set(messagePairs.flatMap(pair => [pair.user.id, pair.assistant.id]));
      setSelectedMessages(allIds);
    }
    setSelectAll(!selectAll);
  };

  const handleToggleMessage = (userMsgId: string, assistantMsgId: string) => {
    const newSelected = new Set(selectedMessages);
    
    if (newSelected.has(userMsgId) && newSelected.has(assistantMsgId)) {
      // Если оба выбраны, снимаем выбор
      newSelected.delete(userMsgId);
      newSelected.delete(assistantMsgId);
    } else {
      // Выбираем оба
      newSelected.add(userMsgId);
      newSelected.add(assistantMsgId);
    }
    
    setSelectedMessages(newSelected);
    setSelectAll(newSelected.size === messagePairs.length * 2);
  };

  const handleCreateShareLink = async () => {
    if (selectedMessages.size === 0) {
      setError('Выберите хотя бы одно сообщение');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Фильтруем выбранные сообщения в правильном порядке
      const selectedMessagesArray = messages.filter(msg => selectedMessages.has(msg.id));

      const response = await fetch('/api/share/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          messages: selectedMessagesArray,
        }),
      });

      if (!response.ok) {
        throw new Error('Ошибка создания публичной ссылки');
      }

      const data = await response.json();
      const fullUrl = `${window.location.origin}/share/${data.share_id}`;
      setShareUrl(fullUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyLink = () => {
    if (shareUrl) {
      navigator.clipboard.writeText(shareUrl);
    }
  };

  const handleClose = () => {
    setSelectedMessages(new Set());
    setSelectAll(false);
    setShareUrl(null);
    setError(null);
    onClose();
  };

  const getShortText = (text: string, maxLength: number = 100) => {
    const plainText = text.replace(/[#*`]/g, '').trim();
    return plainText.length > maxLength ? plainText.substring(0, maxLength) + '...' : plainText;
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
          backgroundImage: 'none',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pb: 1,
        }}
      >
        <Typography variant="h6" component="div">
          Поделиться сообщениями
        </Typography>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {shareUrl ? (
          // Показываем созданную ссылку
          <Box>
            <Alert severity="success" sx={{ mb: 2 }}>
              Публичная ссылка успешно создана!
            </Alert>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                p: 2,
                backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
                borderRadius: 1,
              }}
            >
              <Link
                href={shareUrl}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  flex: 1,
                  wordBreak: 'break-all',
                  color: 'primary.main',
                }}
              >
                {shareUrl}
              </Link>
              <IconButton onClick={handleCopyLink} size="small" color="primary">
                <CopyIcon />
              </IconButton>
            </Box>
          </Box>
        ) : (
          // Показываем выбор сообщений
          <Box>
            <FormControlLabel
              control={
                <Checkbox
                  checked={selectAll}
                  onChange={handleSelectAll}
                  color="primary"
                />
              }
              label="Выбрать все"
              sx={{ mb: 2 }}
            />

            <Box sx={{ maxHeight: '400px', overflowY: 'auto', mb: 2 }}>
              {messagePairs.map((pair, index) => {
                const isSelected = selectedMessages.has(pair.user.id) && selectedMessages.has(pair.assistant.id);
                
                return (
                  <Box
                    key={pair.index}
                    sx={{
                      mb: 2,
                      p: 2,
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
                      backgroundColor: isSelected
                        ? isDarkMode ? 'rgba(33, 150, 243, 0.08)' : 'rgba(33, 150, 243, 0.04)'
                        : 'transparent',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)',
                      },
                    }}
                    onClick={() => handleToggleMessage(pair.user.id, pair.assistant.id)}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <Checkbox
                        checked={isSelected}
                        color="primary"
                        sx={{ mt: -1 }}
                      />
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="body2" sx={{ mb: 1, fontWeight: 500 }}>
                          Вопрос {index + 1}:
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                          {getShortText(pair.user.content)}
                        </Typography>
                        <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 500 }}>
                          Ответ:
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {getShortText(pair.assistant.content, 150)}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                );
              })}
            </Box>

            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}

            {/* Информация о выбранных сообщениях */}
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Выбрано пар сообщений: {selectedMessages.size / 2}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button onClick={handleClose} color="inherit">
          {shareUrl ? 'Закрыть' : 'Отмена'}
        </Button>
        {!shareUrl && (
          <Button
            onClick={handleCreateShareLink}
            variant="contained"
            disabled={isLoading || selectedMessages.size === 0}
            startIcon={isLoading ? <CircularProgress size={20} /> : null}
          >
            {isLoading ? 'Создание...' : 'Создать публичную ссылку'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ShareDialog;


