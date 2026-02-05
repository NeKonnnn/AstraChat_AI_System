import React, { useState } from 'react';
import {
  Box,
  Container,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Avatar,
  Divider,
  Alert,
  CircularProgress,
  Paper,
  Stack,
} from '@mui/material';
import {
  Person as PersonIcon,
  Email as EmailIcon,
  Save as SaveIcon,
  ExitToApp as LogoutIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_CONFIG } from '../config/api';

// Получаем базовый URL из конфига
const getApiBaseUrl = () => {
  return process.env.REACT_APP_API_URL || API_CONFIG.BASE_URL;
};
const API_BASE_URL = getApiBaseUrl();

export default function ProfilePage() {
  const { user, logout, updateUser, token } = useAuth();
  const navigate = useNavigate();
  
  const [email, setEmail] = useState(user?.email || '');
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const handleSave = async () => {
    setIsLoading(true);
    setSuccessMessage('');
    setErrorMessage('');

    try {
      const response = await axios.put(
        `${API_BASE_URL}/api/auth/me`,
        {
          email: email || null,
          full_name: fullName || null,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      updateUser(response.data);
      setSuccessMessage('Профиль успешно обновлен');
    } catch (error: any) {
      setErrorMessage(
        error.response?.data?.detail || 'Ошибка при обновлении профиля'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) {
    return null;
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        Личный кабинет
      </Typography>

      {successMessage && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage('')}>
          {successMessage}
        </Alert>
      )}

      {errorMessage && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setErrorMessage('')}>
          {errorMessage}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 4 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              mb: 4,
            }}
          >
            <Avatar
              sx={{
                width: 80,
                height: 80,
                bgcolor: 'primary.main',
                fontSize: 36,
                mr: 3,
              }}
            >
              {user.username.charAt(0).toUpperCase()}
            </Avatar>
            <Box>
              <Typography variant="h5" fontWeight="bold">
                {user.full_name || user.username}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                @{user.username}
              </Typography>
              {user.is_admin && (
                <Typography
                  variant="caption"
                  sx={{
                    bgcolor: 'primary.main',
                    color: 'white',
                    px: 1,
                    py: 0.5,
                    borderRadius: 1,
                    display: 'inline-block',
                    mt: 1,
                  }}
                >
                  Администратор
                </Typography>
              )}
            </Box>
          </Box>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom fontWeight="bold" sx={{ mb: 3 }}>
            Информация профиля
          </Typography>

          <Stack spacing={3}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <PersonIcon sx={{ mr: 2, color: 'text.secondary' }} />
              <TextField
                fullWidth
                label="Полное имя"
                variant="outlined"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={isLoading}
              />
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <EmailIcon sx={{ mr: 2, color: 'text.secondary' }} />
              <TextField
                fullWidth
                label="Email"
                type="email"
                variant="outlined"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <PersonIcon sx={{ mr: 2, color: 'text.secondary' }} />
              <TextField
                fullWidth
                label="Имя пользователя"
                variant="outlined"
                value={user.username}
                disabled
                helperText="Имя пользователя не может быть изменено"
              />
            </Box>
          </Stack>

          <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              startIcon={isLoading ? <CircularProgress size={20} /> : <SaveIcon />}
              onClick={handleSave}
              disabled={isLoading}
            >
              Сохранить изменения
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h6" gutterBottom fontWeight="bold" sx={{ mb: 2 }}>
            Статистика
          </Typography>
          
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
              gap: 2,
            }}
          >
            <Paper
              elevation={0}
              sx={{
                p: 2,
                bgcolor: 'action.hover',
                borderRadius: 2,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Статус аккаунта
              </Typography>
              <Typography variant="h6" fontWeight="bold" color="success.main">
                {user.is_active ? 'Активен' : 'Неактивен'}
              </Typography>
            </Paper>
            <Paper
              elevation={0}
              sx={{
                p: 2,
                bgcolor: 'action.hover',
                borderRadius: 2,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Роль
              </Typography>
              <Typography variant="h6" fontWeight="bold">
                {user.is_admin ? 'Администратор' : 'Пользователь'}
              </Typography>
            </Paper>
          </Box>

          <Divider sx={{ my: 3 }} />

          <Button
            variant="outlined"
            color="error"
            startIcon={<LogoutIcon />}
            onClick={handleLogout}
            fullWidth
          >
            Выйти из системы
          </Button>
        </CardContent>
      </Card>
    </Container>
  );
}



