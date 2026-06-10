import React, { useState, useEffect } from 'react';
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
import { useAuth, AuthLoginError } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import {
  initSettings,
  formatRemainingAttemptsHint,
  LOGIN_LOCKOUT_EXHAUSTED_MESSAGE,
  type LoginLockoutConfig,
} from '../settings';
import { fetchLoginLockoutPolicy } from '../config/api';
import LoginSessionNotice from '../components/LoginSessionNotice';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [attemptHint, setAttemptHint] = useState('');
  const [lockoutPolicy, setLockoutPolicy] = useState<LoginLockoutConfig | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved ? saved === 'dark' : false;
  });

  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await initSettings();
        const cfg = await fetchLoginLockoutPolicy();
        if (!cancelled) {
          setLockoutPolicy(cfg);
        }
      } catch (e) {
        console.warn(
          'Не удалось загрузить политику блокировки с backend (GET /api/auth/login-lockout-policy):',
          e,
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleTheme = () => {
    const newMode = !isDarkMode;
    setIsDarkMode(newMode);
    localStorage.setItem('theme', newMode ? 'dark' : 'light');
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };
  const inputBackgroundColor = isDarkMode ? '#2a2a2a' : '#ffffff';
  const inputTextColor = isDarkMode ? '#fff' : '#000';

  React.useEffect(() => {
    document.body.style.backgroundColor = isDarkMode ? '#121212' : '#f5f5f5';
    return () => {
      document.body.style.backgroundColor = '';
    };
  }, [isDarkMode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setAttemptHint('');
    setIsLoading(true);

    try {
      await login(username, password);
      navigate('/');
    } catch (err: unknown) {
      if (err instanceof AuthLoginError && err.meta.retryAfterSeconds !== undefined) {
        setError(LOGIN_LOCKOUT_EXHAUSTED_MESSAGE);
        setAttemptHint('');
      } else if (err instanceof AuthLoginError) {
        const message =
          err.message === 'Сервис аутентификации временно недоступен'
            ? err.message
            : 'Неверное имя пользователя или пароль';
        setError(message);

        const { remainingAttempts, maxFailedAttempts, lockoutDurationSeconds } = err.meta;
        const max = maxFailedAttempts ?? lockoutPolicy?.maxFailedAttempts;
        const lockSec =
          lockoutDurationSeconds ?? lockoutPolicy?.lockoutDurationSeconds ?? 900;
        if (remainingAttempts !== undefined && max !== undefined) {
          setAttemptHint(formatRemainingAttemptsHint(remainingAttempts, max, lockSec));
        } else {
          setAttemptHint('');
        }
      } else {
        const message =
          err instanceof Error ? err.message : 'Ошибка при входе в систему';
        setError(message);
        setAttemptHint('');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <LoginSessionNotice />
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
                  color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
                }}
              >
                Используйте ваши учетные данные
              </Typography>
            </Box>

            {(error || attemptHint) && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
                {error && attemptHint ? (
                  <Typography component="p" variant="body2" sx={{ mt: 1, mb: 0 }}>
                    {attemptHint}
                  </Typography>
                ) : (
                  attemptHint
                )}
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
                autoComplete="username"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: inputBackgroundColor,
                    colorScheme: isDarkMode ? 'dark' : 'light',
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
                    color: inputTextColor,
                    colorScheme: isDarkMode ? 'dark' : 'light',
                  },
                  '& input:-webkit-autofill, & input:-webkit-autofill:hover, & input:-webkit-autofill:focus, & input:-webkit-autofill:active, & .MuiOutlinedInput-input:-webkit-autofill, & .MuiOutlinedInput-input:-webkit-autofill:hover, & .MuiOutlinedInput-input:-webkit-autofill:focus, & .MuiOutlinedInput-input:-webkit-autofill:active': {
                    WebkitBoxShadow: `0 0 0 1000px ${inputBackgroundColor} inset !important`,
                    boxShadow: `0 0 0 1000px ${inputBackgroundColor} inset !important`,
                    WebkitTextFillColor: `${inputTextColor} !important`,
                    color: `${inputTextColor} !important`,
                    caretColor: `${inputTextColor} !important`,
                    backgroundColor: `${inputBackgroundColor} !important`,
                    WebkitBackgroundClip: 'padding-box !important',
                    transition: 'background-color 999999s ease-in-out 0s',
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
                autoComplete="current-password"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: inputBackgroundColor,
                    colorScheme: isDarkMode ? 'dark' : 'light',
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
                    color: inputTextColor,
                    colorScheme: isDarkMode ? 'dark' : 'light',
                  },
                  '& input:-webkit-autofill, & input:-webkit-autofill:hover, & input:-webkit-autofill:focus, & input:-webkit-autofill:active, & .MuiOutlinedInput-input:-webkit-autofill, & .MuiOutlinedInput-input:-webkit-autofill:hover, & .MuiOutlinedInput-input:-webkit-autofill:focus, & .MuiOutlinedInput-input:-webkit-autofill:active': {
                    WebkitBoxShadow: `0 0 0 1000px ${inputBackgroundColor} inset !important`,
                    boxShadow: `0 0 0 1000px ${inputBackgroundColor} inset !important`,
                    WebkitTextFillColor: `${inputTextColor} !important`,
                    color: `${inputTextColor} !important`,
                    caretColor: `${inputTextColor} !important`,
                    backgroundColor: `${inputBackgroundColor} !important`,
                    WebkitBackgroundClip: 'padding-box !important',
                    transition: 'background-color 999999s ease-in-out 0s',
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
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}
