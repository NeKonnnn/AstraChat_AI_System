import React, { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Avatar,
  Alert,
  CircularProgress,
  Paper,
  Divider,
} from '@mui/material';
import {
  Person as PersonIcon,
  Email as EmailIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { API_CONFIG } from '../../config/api';

// Получаем базовый URL из конфига
const getApiBaseUrl = () => {
  return process.env.REACT_APP_API_URL || API_CONFIG.BASE_URL;
};
const API_BASE_URL = getApiBaseUrl();

export default function ProfileSettings() {
  const { user, updateUser, token } = useAuth();
  
  const [email, setEmail] = useState(user?.email || '');
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  if (!user) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          Необходимо авторизоваться
        </Typography>
      </Box>
    );
  }

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
      setSuccessMessage('Профиль успешно обновлен!');
      
      // Автоматически скрываем сообщение через 3 секунды
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err: any) {
      console.error("Failed to update profile:", err);
      if (axios.isAxiosError(err) && err.response) {
        setErrorMessage(err.response.data.detail || "Ошибка обновления профиля");
      } else {
        setErrorMessage("Произошла непредвиденная ошибка");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
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

      {/* Информация о пользователе */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          mb: 3,
          backgroundColor: 'action.hover',
          borderRadius: 2,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            mb: 3,
          }}
        >
          <Avatar
            sx={{
              width: 64,
              height: 64,
              bgcolor: 'primary.main',
              fontSize: 28,
              mr: 2,
            }}
          >
            {user.username.charAt(0).toUpperCase()}
          </Avatar>
          <Box>
            <Typography variant="h6" fontWeight="bold">
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
                  mt: 0.5,
                }}
              >
                Администратор
              </Typography>
            )}
          </Box>
        </Box>

        <Divider sx={{ mb: 3 }} />

        {/* Поля редактирования */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <PersonIcon sx={{ color: 'text.secondary' }} />
            <TextField
              fullWidth
              label="Полное имя"
              variant="outlined"
              size="small"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              disabled={isLoading}
            />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <EmailIcon sx={{ color: 'text.secondary' }} />
            <TextField
              fullWidth
              label="Email"
              type="email"
              variant="outlined"
              size="small"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
            />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <PersonIcon sx={{ color: 'text.secondary' }} />
            <TextField
              fullWidth
              label="Имя пользователя"
              variant="outlined"
              size="small"
              value={user.username}
              disabled
              helperText="Имя пользователя не может быть изменено"
            />
          </Box>
        </Box>

        <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            startIcon={isLoading ? <CircularProgress size={20} /> : <SaveIcon />}
            onClick={handleSave}
            disabled={isLoading}
          >
            Сохранить изменения
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}



