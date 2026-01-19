import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Tooltip,
  Divider,
} from '@mui/material';
import {
  Close as CloseIcon,
  ContentCopy as CopyIcon,
  Delete as DeleteIcon,
  Link as LinkIcon,
} from '@mui/icons-material';
import { getApiUrl } from '../config/api';

interface SharedConversation {
  share_id: string;
  messages: any[];
  created_at: string;
  created_by?: string;
}

interface ManageSharesDialogProps {
  open: boolean;
  onClose: () => void;
  isDarkMode: boolean;
}

export const ManageSharesDialog: React.FC<ManageSharesDialogProps> = ({
  open,
  onClose,
  isDarkMode,
}) => {
  const [shares, setShares] = useState<SharedConversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      fetchShares();
    }
  }, [open]);

  const fetchShares = async () => {
    setLoading(true);
    try {
      // Получаем токен для авторизации
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(getApiUrl('/api/share/my-shares'), {
        credentials: 'include',
        headers,
      });
      
      if (response.ok) {
        const data = await response.json();
        setShares(data);
      } else {
        console.error('Ошибка при загрузке публичных ссылок:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('Ошибка при загрузке публичных ссылок:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async (shareId: string) => {
    const url = `${window.location.origin}/share/${shareId}`;
    await navigator.clipboard.writeText(url);
    setCopiedId(shareId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleDelete = async (shareId: string) => {
    if (!window.confirm('Вы уверены, что хотите удалить эту публичную ссылку?')) {
      return;
    }

    try {
      // Получаем токен для авторизации
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(getApiUrl(`/api/share/${shareId}`), {
        method: 'DELETE',
        credentials: 'include',
        headers,
      });

      if (response.ok) {
        setShares(shares.filter(s => s.share_id !== shareId));
      } else {
        window.alert('Ошибка при удалении ссылки');
      }
    } catch (error) {
      console.error('Ошибка при удалении публичной ссылки:', error);
      window.alert('Ошибка при удалении ссылки');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return 'Сегодня';
    } else if (diffDays === 1) {
      return 'Вчера';
    } else if (diffDays < 7) {
      return `${diffDays} дн. назад`;
    } else {
      return date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      });
    }
  };

  const getFirstUserMessage = (messages: any[]) => {
    const userMsg = messages.find(m => m.role === 'user');
    if (!userMsg) return 'Без названия';
    const content = userMsg.content || '';
    return content.length > 50 ? content.substring(0, 50) + '...' : content;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
          backgroundImage: 'none',
          borderRadius: '12px',
          minHeight: '400px',
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
          Общие ссылки
        </Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ px: 0 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : shares.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4, px: 3 }}>
            <LinkIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="body1" color="text.secondary">
              У вас пока нет публичных ссылок
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Создайте публичную ссылку, нажав на кнопку "Поделиться" под сообщением ассистента
            </Typography>
          </Box>
        ) : (
          <List sx={{ py: 0 }}>
            {shares.map((share, index) => (
              <React.Fragment key={share.share_id}>
                {index > 0 && <Divider />}
                <ListItem
                  sx={{
                    px: 3,
                    py: 2,
                    '&:hover': {
                      backgroundColor: isDarkMode
                        ? 'rgba(255, 255, 255, 0.05)'
                        : 'rgba(0, 0, 0, 0.02)',
                    },
                  }}
                  secondaryAction={
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Tooltip title={copiedId === share.share_id ? 'Скопировано!' : 'Копировать ссылку'}>
                        <IconButton
                          edge="end"
                          size="small"
                          onClick={() => handleCopy(share.share_id)}
                          sx={{ 
                            opacity: 0.7,
                            p: 0.5,
                            borderRadius: '6px',
                            minWidth: '28px',
                            width: '28px',
                            height: '28px',
                            '&:hover': {
                              opacity: 1,
                              '& .MuiSvgIcon-root': {
                                color: copiedId === share.share_id ? 'success.main' : 'primary.main',
                              },
                            },
                            '& .MuiSvgIcon-root': {
                              fontSize: '18px !important',
                              width: '18px !important',
                              height: '18px !important',
                              color: copiedId === share.share_id ? 'success.main' : 'inherit',
                            },
                          }}
                        >
                          <CopyIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton
                          edge="end"
                          size="small"
                          onClick={() => handleDelete(share.share_id)}
                          sx={{ 
                            opacity: 0.7,
                            p: 0.5,
                            borderRadius: '6px',
                            minWidth: '28px',
                            width: '28px',
                            height: '28px',
                            '&:hover': {
                              opacity: 1,
                              '& .MuiSvgIcon-root': {
                                color: 'error.main',
                              },
                            },
                            '& .MuiSvgIcon-root': {
                              fontSize: '18px !important',
                              width: '18px !important',
                              height: '18px !important',
                            },
                          }}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  }
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <LinkIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                        <Typography
                          variant="body1"
                          sx={{
                            fontWeight: 500,
                            maxWidth: '400px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {getFirstUserMessage(share.messages)}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Typography variant="caption" color="text.secondary">
                        Опубликовано {formatDate(share.created_at)}
                      </Typography>
                    }
                  />
                </ListItem>
              </React.Fragment>
            ))}
          </List>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ManageSharesDialog;

