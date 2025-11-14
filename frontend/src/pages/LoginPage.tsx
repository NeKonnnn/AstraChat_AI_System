import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Container,
  IconButton,
  InputAdornment,
} from '@mui/material';
import {
  RemoveRedEye as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  WbSunny as SunIcon,
  Brightness3 as MoonIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved ? saved === 'dark' : false;
  });
  
  const { login } = useAuth();
  const navigate = useNavigate();

  const toggleTheme = () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    localStorage.setItem('theme', newMode ? 'dark' : 'light');
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  // Устанавливаем фон при монтировании
  React.useEffect(() => {
    document.body.style.backgroundColor = isDarkMode ? '#121212' : '#f5f5f5';
    return () => {
      // Очищаем стиль при размонтировании
      document.body.style.backgroundColor = '';
    };
  }, [isDarkMode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Ошибка при входе в систему');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      {/* Кнопка переключения темы в углу */}
      <IconButton
        onClick={toggleTheme}
        disableRipple
        sx={{
          position: 'fixed',
          top: 16,
          right: 16,
          zIndex: 1000,
          '&:hover': {
            backgroundColor: 'transparent',
            transform: 'scale(1.1)',
            transition: 'transform 0.2s ease-in-out',
          },
        }}
      >
        {isDarkMode ? (
          <SunIcon sx={{ color: '#ffb300', fontSize: 28 }} />
        ) : (
          <MoonIcon sx={{ color: '#5c6bc0', fontSize: 28 }} />
        )}
      </IconButton>

      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Card
          sx={{
            width: '100%',
            maxWidth: 450,
            boxShadow: isDarkMode ? '0 8px 32px rgba(0,0,0,0.4)' : 3,
            bgcolor: isDarkMode ? '#1e1e1e' : '#ffffff',
          }}
        >
          <CardContent sx={{ p: 4 }}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                mb: 3,
              }}
            >
              {/* Логотип вместо иконки замка */}
              <Box
                component="img"
                src="/astra.png"
                alt="Astra Logo"
                sx={{
                  width: 100,
                  height: 100,
                  mb: 2,
                  objectFit: 'contain',
                }}
              />
              <Typography 
                variant="h4" 
                component="h1" 
                fontWeight="bold"
                sx={{ color: isDarkMode ? '#fff' : '#000' }}
              >
                Вход в систему
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ 
                  mt: 1,
                  color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)'
                }}
              >
                Используйте ваши учетные данные
              </Typography>
            </Box>

            {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Имя пользователя"
                variant="outlined"
                margin="normal"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isLoading}
                required
                autoFocus
                sx={{
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: isDarkMode ? 'rgba(255,255,255,0.05)' : '#ffffff',
                    '& fieldset': {
                      borderColor: isDarkMode ? 'rgba(255,255,255,0.23)' : 'rgba(0,0,0,0.23)',
                    },
                    '&:hover fieldset': {
                      borderColor: isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: 'primary.main',
                      borderWidth: '2px',
                    },
                  },
                  '& .MuiInputLabel-root': {
                    color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
                    '&.Mui-focused': {
                      color: 'primary.main',
                    },
                  },
                  '& .MuiInputBase-input': {
                    color: isDarkMode ? '#fff' : '#000',
                  },
                }}
              />

              <TextField
                fullWidth
                label="Пароль"
                type={showPassword ? 'text' : 'password'}
                variant="outlined"
                margin="normal"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                required
                sx={{
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: isDarkMode ? 'rgba(255,255,255,0.05)' : '#ffffff',
                    '& fieldset': {
                      borderColor: isDarkMode ? 'rgba(255,255,255,0.23)' : 'rgba(0,0,0,0.23)',
                    },
                    '&:hover fieldset': {
                      borderColor: isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: 'primary.main',
                      borderWidth: '2px',
                    },
                  },
                  '& .MuiInputLabel-root': {
                    color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
                    '&.Mui-focused': {
                      color: 'primary.main',
                    },
                  },
                  '& .MuiInputBase-input': {
                    color: isDarkMode ? '#fff' : '#000',
                  },
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={togglePasswordVisibility}
                        edge="end"
                        disabled={isLoading}
                        disableRipple
                        sx={{
                          color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
                          backgroundColor: 'transparent',
                          '&:hover': {
                            backgroundColor: 'transparent',
                            color: isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.87)',
                            transform: 'scale(1.1)',
                            transition: 'all 0.2s ease-in-out',
                          },
                          '&:active': {
                            transform: 'scale(0.95)',
                          },
                          '& .MuiSvgIcon-root': {
                            fontSize: '22px',
                          },
                        }}
                      >
                        {showPassword ? <VisibilityIcon /> : <VisibilityOffIcon />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />

              <Button
                fullWidth
                type="submit"
                variant="contained"
                size="large"
                disabled={isLoading}
                sx={{ 
                  mt: 3, 
                  mb: 2, 
                  py: 1.5,
                  bgcolor: 'primary.main',
                  '&:hover': {
                    bgcolor: 'primary.dark',
                  },
                }}
              >
                {isLoading ? (
                  <CircularProgress size={24} color="inherit" />
                ) : (
                  'Войти'
                )}
              </Button>
            </form>

            <Box sx={{ mt: 2, textAlign: 'center' }}>
              <Typography 
                variant="body2" 
                sx={{ 
                  color: isDarkMode ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.6)'
                }}
              >
                Проблемы со входом? Обратитесь к системному администратору
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}



