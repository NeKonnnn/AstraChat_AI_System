import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  Avatar,
  Paper,
} from '@mui/material';
import { Person as PersonIcon } from '@mui/icons-material';
import MessageRenderer from '../components/MessageRenderer';

interface Message {
  id: string;
  role: string;
  content: string;
  timestamp?: string;
  model?: string;
}

interface SharedConversation {
  share_id: string;
  messages: Message[];
  created_at: string;
  created_by?: string;
}

export default function ShareViewPage() {
  const { shareId } = useParams<{ shareId: string }>();
  const [conversation, setConversation] = useState<SharedConversation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSharedConversation = async () => {
      if (!shareId) {
        setError('ID публичной ссылки не указан');
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`/api/share/${shareId}`, {
          headers: {
            'Content-Type': 'application/json',
          },
        });
        
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Публичная ссылка не найдена');
          }
          throw new Error('Ошибка при загрузке');
        }

        const data = await response.json();
        setConversation(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Произошла ошибка');
      } finally {
        setIsLoading(false);
      }
    };

    fetchSharedConversation();
  }, [shareId]);

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return '';
    try {
      return new Date(timestamp).toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#121212',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#121212',
          p: 3,
        }}
      >
        <Alert severity="error" sx={{ maxWidth: 600 }}>
          {error}
        </Alert>
      </Box>
    );
  }

  if (!conversation) {
    return null;
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundColor: '#121212',
        color: 'white',
        py: 4,
      }}
    >
      <Container maxWidth="lg">
        {/* Заголовок */}
        <Paper
          sx={{
            p: 3,
            mb: 4,
            backgroundColor: '#1e1e1e',
            backgroundImage: 'none',
          }}
        >
          <Typography variant="h5" gutterBottom>
            Публичная беседа
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Создано: {formatTimestamp(conversation.created_at)}
          </Typography>
        </Paper>

        {/* Сообщения */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {conversation.messages.map((message, index) => {
            const isUser = message.role === 'user';
            
            return (
              <Box
                key={message.id || index}
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start',
                }}
              >
                <Card
                  sx={{
                    maxWidth: '75%',
                    minWidth: '200px',
                    backgroundColor: isUser ? 'primary.main' : '#1e1e1e',
                    color: isUser ? 'primary.contrastText' : 'text.primary',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
                  }}
                >
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                      <Avatar
                        sx={{
                          width: 24,
                          height: 24,
                          mr: 1,
                          bgcolor: isUser ? 'primary.dark' : 'transparent',
                        }}
                        src={isUser ? undefined : '/astra.png'}
                      >
                        {isUser ? <PersonIcon /> : null}
                      </Avatar>
                      <Typography
                        variant="caption"
                        sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}
                      >
                        {isUser ? 'Пользователь' : 'AstraChat'}
                      </Typography>
                      {message.timestamp && (
                        <Typography
                          variant="caption"
                          sx={{ ml: 'auto', opacity: 0.6, fontSize: '0.7rem' }}
                        >
                          {formatTimestamp(message.timestamp)}
                        </Typography>
                      )}
                    </Box>
                    
                    <Box sx={{ width: '100%' }}>
                      <MessageRenderer content={message.content} isStreaming={false} />
                    </Box>

                    {message.model && (
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block',
                          mt: 1,
                          opacity: 0.6,
                          fontSize: '0.7rem',
                        }}
                      >
                        Модель: {message.model}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Box>
            );
          })}
        </Box>

        {/* Футер */}
        <Box sx={{ mt: 6, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Создано с помощью AstraChat
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}

