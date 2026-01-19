import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  IconButton,
  TextField,
  InputAdornment,
  CircularProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  ContentCopy as CopyIcon,
  Check as CheckIcon,
} from '@mui/icons-material';

interface ShareConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<string>; // Функция создания ссылки, возвращает URL
  isDarkMode: boolean;
  selectedCount: number;
}

export const ShareConfirmDialog: React.FC<ShareConfirmDialogProps> = ({
  open,
  onClose,
  onConfirm,
  isDarkMode,
  selectedCount,
}) => {
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      const url = await onConfirm();
      setShareUrl(url);
      // Автоматически копируем в буфер обмена
      await navigator.clipboard.writeText(url);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (error) {
      console.error('Ошибка создания ссылки:', error);
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopy = async () => {
    if (shareUrl) {
      await navigator.clipboard.writeText(shareUrl);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const handleClose = () => {
    setShareUrl(null);
    setIsCopied(false);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
          backgroundImage: 'none',
          borderRadius: '12px',
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
          Создать публичную ссылку
        </Typography>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {!shareUrl ? (
          // Форма подтверждения
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Любой, у кого есть ссылка, может просмотреть ваш общий диалог. Проверьте наличие
              конфиденциальной или личной информации. Управлять общими ссылками можно в Настройки
              {'>'} Данные.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Выбрано пар сообщений: <strong>{selectedCount}</strong>
            </Typography>
          </Box>
        ) : (
          // Созданная ссылка
          <Box>
            <TextField
              fullWidth
              value={shareUrl}
              InputProps={{
                readOnly: true,
                endAdornment: (
                  <InputAdornment position="end">
                    {isCopied ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'success.main' }}>
                        <CheckIcon fontSize="small" />
                        <Typography variant="caption">Скопировано</Typography>
                      </Box>
                    ) : null}
                  </InputAdornment>
                ),
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)',
                },
              }}
            />
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        {!shareUrl ? (
          <Button
            onClick={handleCreate}
            variant="contained"
            fullWidth
            disabled={isCreating}
            startIcon={isCreating ? <CircularProgress size={20} /> : null}
            sx={{
              borderRadius: '8px',
              textTransform: 'none',
              py: 1.5,
            }}
          >
            {isCreating ? 'Создание...' : 'Создать и скопировать'}
          </Button>
        ) : (
          <Button
            onClick={handleCopy}
            variant="contained"
            fullWidth
            startIcon={isCopied ? <CheckIcon /> : <CopyIcon />}
            sx={{
              borderRadius: '8px',
              textTransform: 'none',
              py: 1.5,
            }}
          >
            {isCopied ? 'Скопировано' : 'Копировать'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ShareConfirmDialog;


