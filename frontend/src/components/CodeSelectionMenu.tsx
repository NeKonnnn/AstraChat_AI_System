import React, { useState, useRef } from 'react';
import {
  Box,
  Paper,
  Tooltip,
  Divider,
  Menu,
  MenuItem,
  ListItemText,
  TextField,
  IconButton,
  Button,
} from '@mui/material';
import {
  ContentCopy as CopyIcon,
  QuestionAnswer as AskIcon,
  Info as ExplainIcon,
  Translate as TranslateIcon,
  KeyboardArrowDown as ArrowDownIcon,
  Send as SendIcon,
  Close as CloseIcon,
} from '@mui/icons-material';

interface CodeSelectionMenuProps {
  anchorEl: HTMLElement | null;
  position?: { top: number; left: number };
  open: boolean;
  onClose: () => void;
  selectedText: string;
  onCopy: () => void;
  onAsk: (prompt: string) => void;
  onExplain: (prompt: string) => void;
  onTranslate: (prompt: string, targetLanguage: string) => void;
}

const languages = [
  { code: 'ru-RU', name: 'Russian (Russia)' },
  { code: 'en-US', name: 'English (United States)' },
  { code: 'de-DE', name: 'German (Germany)' },
  { code: 'fr-FR', name: 'French (France)' },
  { code: 'es-ES', name: 'Spanish (Spain)' },
  { code: 'it-IT', name: 'Italian (Italy)' },
  { code: 'pt-PT', name: 'Portuguese (Portugal)' },
  { code: 'ja-JP', name: 'Japanese (Japan)' },
  { code: 'ko-KR', name: 'Korean (Korea)' },
  { code: 'zh-CN', name: 'Chinese (China)' },
];

export default function CodeSelectionMenu({
  anchorEl,
  position,
  open,
  onClose,
  selectedText,
  onCopy,
  onAsk,
  onExplain,
  onTranslate,
}: CodeSelectionMenuProps) {
  const [translateMenuOpen, setTranslateMenuOpen] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('ru-RU');
  const [askInputOpen, setAskInputOpen] = useState(false);
  const [askQuestion, setAskQuestion] = useState('');
  const translateButtonRef = useRef<HTMLDivElement>(null);
  const askInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleCopy = () => {
    onCopy();
    onClose();
  };

  const handleAskClick = () => {
    setAskInputOpen(true);
    setTimeout(() => {
      askInputRef.current?.focus();
    }, 10);
  };

  const handleAskSubmit = () => {
    if (askQuestion.trim()) {
      const prompt = `\`\`\`\n${selectedText}\n\`\`\`\n\n${askQuestion.trim()}`;
      onAsk(prompt);
      setAskQuestion('');
      setAskInputOpen(false);
      onClose();
    }
  };

  const handleAskCancel = () => {
    setAskQuestion('');
    setAskInputOpen(false);
  };

  const handleAskKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleAskSubmit();
    } else if (event.key === 'Escape') {
      handleAskCancel();
    }
  };

  const handleExplain = () => {
    const prompt = `Объясни мне эту секцию более подробно\n\n\`\`\`\n${selectedText}\n\`\`\``;
    onExplain(prompt);
    onClose();
  };

  const handleLanguageSelect = (languageCode: string) => {
    setSelectedLanguage(languageCode);
    const language = languages.find(l => l.code === languageCode);
    const languageName = language ? language.name : languageCode;
    const prompt = `Переведите следующий текст на ${languageName}:\n\n"${selectedText}"`;
    onTranslate(prompt, languageCode);
    setTranslateMenuOpen(false);
    onClose();
  };

  // Обработчик ESC для закрытия меню
  React.useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) {
        event.preventDefault();
        event.stopPropagation();
        if (askInputOpen) {
          handleAskCancel();
        } else {
          onClose();
        }
      }
    };

    if (open) {
      document.addEventListener('keydown', handleEscape, true);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape, true);
    };
  }, [open, askInputOpen, onClose]);

  // Не закрываем меню, если open=true, даже если anchorEl стал null
  // Меню должно закрываться только через onClose
  if (!open) return null;
  
  // Если anchorEl стал null, используем последнюю известную позицию
  if (!anchorEl && !position) return null;

  // Используем переданную позицию или вычисляем из anchorEl
  // Если anchorEl стал null, используем только position
  let menuTop: number;
  let menuLeft: number;
  
  if (position) {
    menuTop = position.top;
    menuLeft = position.left;
  } else if (anchorEl) {
    const rect = anchorEl.getBoundingClientRect();
    menuTop = rect.bottom + 8;
    menuLeft = rect.left + (rect.width / 2);
  } else {
    // Если нет ни position, ни anchorEl, используем последнюю известную позицию
    return null;
  }

  if (askInputOpen) {
    return (
      <Paper
        ref={menuRef}
        data-menu="code-selection"
        elevation={8}
        sx={{
          position: 'fixed',
          top: `${menuTop}px`,
          left: `${menuLeft}px`,
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          p: 0.75,
          borderRadius: 1,
          backgroundColor: 'background.paper',
          boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.15)',
          zIndex: 1300,
          minWidth: 300,
        }}
      >
        <TextField
          inputRef={askInputRef}
          size="small"
          placeholder="Введите ваш вопрос..."
          value={askQuestion}
          onChange={(e) => setAskQuestion(e.target.value)}
          onKeyDown={handleAskKeyPress}
          autoFocus
          sx={{
            flex: 1,
            '& .MuiOutlinedInput-root': {
              fontSize: '0.875rem',
              py: 0.5,
            },
          }}
        />
        <IconButton
          size="small"
          onClick={handleAskSubmit}
          disabled={!askQuestion.trim()}
          sx={{ p: 0.5 }}
        >
          <SendIcon fontSize="small" />
        </IconButton>
        <IconButton
          size="small"
          onClick={handleAskCancel}
          sx={{ p: 0.5 }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Paper>
    );
  }

  return (
    <>
      <Paper
        ref={menuRef}
        data-menu="code-selection"
        elevation={8}
        sx={{
          position: 'fixed',
          top: `${menuTop}px`,
          left: `${menuLeft}px`,
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          p: 0.5,
          borderRadius: 1,
          backgroundColor: 'background.paper',
          boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.15)',
          zIndex: 1300,
        }}
      >
        <Tooltip title="Копировать">
          <Box
            onClick={handleCopy}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 0.75,
              py: 0.25,
              cursor: 'pointer',
              borderRadius: 0.5,
              '&:hover': {
                backgroundColor: 'action.hover',
              },
            }}
          >
            <CopyIcon sx={{ fontSize: '0.875rem' }} />
            <Box component="span" sx={{ fontSize: '0.75rem', lineHeight: 1.2 }}>
              Копировать
            </Box>
          </Box>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.25, height: 16 }} />

        <Tooltip title="Спросить">
          <Box
            onClick={handleAskClick}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 0.75,
              py: 0.25,
              cursor: 'pointer',
              borderRadius: 0.5,
              '&:hover': {
                backgroundColor: 'action.hover',
              },
            }}
          >
            <AskIcon sx={{ fontSize: '0.875rem' }} />
            <Box component="span" sx={{ fontSize: '0.75rem', lineHeight: 1.2 }}>
              Спросить
            </Box>
          </Box>
        </Tooltip>

        <Tooltip title="Объяснить">
          <Box
            onClick={handleExplain}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 0.75,
              py: 0.25,
              cursor: 'pointer',
              borderRadius: 0.5,
              '&:hover': {
                backgroundColor: 'action.hover',
              },
            }}
          >
            <ExplainIcon sx={{ fontSize: '0.875rem' }} />
            <Box component="span" sx={{ fontSize: '0.75rem', lineHeight: 1.2 }}>
              Объяснить
            </Box>
          </Box>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.25, height: 16 }} />

        <Tooltip title="Перевести">
          <Box
            component="div"
            ref={translateButtonRef}
            onClick={() => setTranslateMenuOpen(!translateMenuOpen)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              px: 0.75,
              py: 0.25,
              cursor: 'pointer',
              borderRadius: 0.5,
              position: 'relative',
              '&:hover': {
                backgroundColor: 'action.hover',
              },
            }}
          >
            <TranslateIcon sx={{ fontSize: '0.875rem' }} />
            <Box
              component="span"
              sx={{
                fontSize: '0.75rem',
                lineHeight: 1.2,
                display: 'flex',
                alignItems: 'center',
                gap: 0.25,
              }}
            >
              Перевести
              <ArrowDownIcon sx={{ fontSize: '0.7rem' }} />
            </Box>
          </Box>
        </Tooltip>

        <Menu
          open={translateMenuOpen}
          onClose={(event, reason) => {
            // Не закрываем при клике на backdrop
            if (reason !== 'backdropClick') {
              setTranslateMenuOpen(false);
            }
          }}
          anchorEl={translateButtonRef.current as HTMLElement}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'center',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'center',
          }}
          disableAutoFocus
          disableEnforceFocus
          disableRestoreFocus
          PaperProps={{
            sx: {
              mt: 0.5,
              minWidth: 250,
              maxHeight: 300,
              overflow: 'auto',
            },
          }}
        >
          {languages.map((lang) => (
            <MenuItem
              key={lang.code}
              onClick={() => handleLanguageSelect(lang.code)}
              selected={selectedLanguage === lang.code}
            >
              <ListItemText>{lang.name}</ListItemText>
            </MenuItem>
          ))}
        </Menu>
      </Paper>
    </>
  );
}

