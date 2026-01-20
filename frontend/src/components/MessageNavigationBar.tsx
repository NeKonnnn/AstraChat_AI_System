import React, { useState, useEffect, useRef } from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { Message } from '../contexts/AppContext';

interface MessageNavigationBarProps {
  messages: Message[];
  isDarkMode: boolean;
  onNavigate: (index: number) => void;
  rightSidebarOpen: boolean;
  rightSidebarHidden: boolean;
}

interface TooltipState {
  show: boolean;
  content: string;
  fullContent: string;
  top: number;
}

export const MessageNavigationBar: React.FC<MessageNavigationBarProps> = ({
  messages,
  isDarkMode,
  onNavigate,
  rightSidebarOpen,
  rightSidebarHidden,
}) => {
  const [activeMessageIndex, setActiveMessageIndex] = useState<number | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showListPanel, setShowListPanel] = useState(false);
  const [hoveredListItemIndex, setHoveredListItemIndex] = useState<number | null>(null);
  const [tooltipState, setTooltipState] = useState<TooltipState>({
    show: false,
    content: '',
    fullContent: '',
    top: 0,
  });
  const [showFullTooltip, setShowFullTooltip] = useState(false);
  const navigationRef = useRef<HTMLDivElement>(null);
  const listPanelRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Фильтруем только сообщения пользователя
  const userMessages = messages
    .map((msg, index) => ({ msg, originalIndex: index }))
    .filter(({ msg }) => msg.role === 'user');

  // Отслеживание активного сообщения при скролле
  useEffect(() => {
    const handleScroll = () => {
      const messageElements = document.querySelectorAll('[data-message-index]');
      const viewportMiddle = window.innerHeight / 2;

      let closestIndex: number | null = null;
      let closestDistance = Infinity;

      messageElements.forEach((element) => {
        const messageIndex = parseInt(element.getAttribute('data-message-index') || '-1');
        if (messageIndex === -1) return;

        const rect = element.getBoundingClientRect();
        const elementMiddle = rect.top + rect.height / 2;
        const distance = Math.abs(elementMiddle - viewportMiddle);

        // Проверяем что элемент видим на экране
        if (rect.top < window.innerHeight && rect.bottom > 0) {
          if (distance < closestDistance) {
            closestDistance = distance;
            closestIndex = messageIndex;
          }
        }
      });

      setActiveMessageIndex(closestIndex);
    };

    // Слушаем скролл на всех элементах (включая контейнеры с overflow)
    const scrollContainer = document.querySelector('.chat-messages-area');
    
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll);
    }
    window.addEventListener('scroll', handleScroll, true);
    handleScroll(); // Начальная проверка

    return () => {
      if (scrollContainer) {
        scrollContainer.removeEventListener('scroll', handleScroll);
      }
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [messages]);

  // Очистка таймера при размонтировании компонента
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
    };
  }, []);

  // Получение краткого текста (первые 50 символов)
  const getShortText = (text: string): string => {
    const plainText = text.replace(/[#*`]/g, '').trim();
    return plainText.length > 50 ? plainText.substring(0, 50) + '...' : plainText;
  };

  // Обработка наведения на область навигации
  const handleNavigationMouseEnter = () => {
    setShowListPanel(true);
  };

  const handleNavigationMouseLeave = () => {
    // Проверяем что курсор не над панелью списка
    setTimeout(() => {
      if (!listPanelRef.current?.matches(':hover')) {
        setShowListPanel(false);
        setHoveredListItemIndex(null);
        setTooltipState({ show: false, content: '', fullContent: '', top: 0 });
        setShowFullTooltip(false);
      }
    }, 100);
  };

  // Обработка наведения на элемент списка
  const handleListItemMouseEnter = (index: number, event: React.MouseEvent<HTMLDivElement>) => {
    const { msg, originalIndex } = userMessages[index];
    const rect = event.currentTarget.getBoundingClientRect();
    
    setHoveredListItemIndex(index);
    setHoveredIndex(originalIndex);
    
    // Отменяем предыдущий таймер, если есть
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    
    // Устанавливаем таймер для показа полного текста через 2 секунды
    hoverTimeoutRef.current = setTimeout(() => {
      setTooltipState({
        show: true,
        content: getShortText(msg.content),
        fullContent: msg.content,
        top: rect.top,
      });
      setShowFullTooltip(true);
    }, 2000);
  };

  const handleListItemMouseLeave = () => {
    // Отменяем таймер при уходе курсора
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = null;
    }
    
    setHoveredListItemIndex(null);
    setTooltipState({ show: false, content: '', fullContent: '', top: 0 });
    setShowFullTooltip(false);
  };

  // Обработка клика на черточку для навигации
  const handleClick = (originalIndex: number) => {
    onNavigate(originalIndex);
    setShowListPanel(false);
  };

  // Вычисляем правую позицию в зависимости от состояния боковой панели
  const getRightPosition = () => {
    if (rightSidebarHidden) {
      return '50px'; // Если панель полностью скрыта - оставляем место для стрелки
    }
    if (rightSidebarOpen) {
      return '300px'; // Если панель открыта - прямо у края панели (панель 400px + 8px отступ)
    }
    return '95px'; // Если панель свернута - оставляем место для узкой полоски и стрелки
  };

  return (
    <>
      {/* Навигационная панель с черточками */}
      <Box
        ref={navigationRef}
        onMouseEnter={handleNavigationMouseEnter}
        onMouseLeave={handleNavigationMouseLeave}
        sx={{
          position: 'fixed',
          right: getRightPosition(),
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'flex',
          flexDirection: 'row',
          gap: 1,
          padding: 1,
          writingMode: 'vertical-lr',
          zIndex: 1000,
          pointerEvents: 'all',
          transition: 'right 0.3s ease',
        }}
      >
        {userMessages.map(({ msg, originalIndex }, index) => {
          const isActive = activeMessageIndex === originalIndex;
          const isHovered = hoveredIndex === originalIndex;
          const isLong = index % 2 === 0; // Четные индексы - длинные, нечетные - короткие

          return (
            <Box
              key={originalIndex}
              onClick={() => handleClick(originalIndex)}
              sx={{
                width: isLong ? '24px' : '16px',
                height: isActive ? '3px' : '2px',
                alignSelf: isLong ? 'stretch' : 'center',
                backgroundColor: isActive
                  ? '#2196f3'
                  : isHovered
                  ? '#64b5f6'
                  : isDarkMode
                  ? 'rgba(255, 255, 255, 0.25)'
                  : 'rgba(0, 0, 0, 0.15)',
                borderRadius: '2px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: isActive 
                  ? '0 0 8px rgba(33, 150, 243, 0.5)' 
                  : 'none',
                '&:hover': {
                  height: '4px',
                  backgroundColor: '#2196f3',
                  boxShadow: '0 0 8px rgba(33, 150, 243, 0.4)',
                },
              }}
            />
          );
        })}
      </Box>

      {/* Панель со списком всех вопросов */}
      {showListPanel && (
        <Paper
          ref={listPanelRef}
          onMouseLeave={() => {
            setShowListPanel(false);
            setHoveredListItemIndex(null);
            setTooltipState({ show: false, content: '', fullContent: '', top: 0 });
            setShowFullTooltip(false);
            if (hoverTimeoutRef.current) {
              clearTimeout(hoverTimeoutRef.current);
              hoverTimeoutRef.current = null;
            }
          }}
          sx={{
            position: 'fixed',
            right: rightSidebarHidden ? '90px' : (rightSidebarOpen ? '360px' : '154px'),
            top: '50%',
            transform: 'translateY(-50%)',
            minWidth: '220px',
            maxWidth: '280px',
            maxHeight: `calc(5 * 56px + 8px)`, // Максимум 5 элементов (высота элемента ~56px + отступы)
            overflow: 'auto',
            padding: '4px',
            zIndex: 1001,
            backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
            boxShadow: isDarkMode 
              ? '0 8px 32px rgba(0, 0, 0, 0.6)' 
              : '0 8px 32px rgba(0, 0, 0, 0.12)',
            borderRadius: '12px',
            border: 'none',
            pointerEvents: 'all',
            transition: 'right 0.3s ease',
            // Стили для скроллбара
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: 'transparent',
            },
            '&::-webkit-scrollbar-thumb': {
              background: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
              borderRadius: '3px',
              '&:hover': {
                background: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
              },
            },
            scrollbarWidth: 'thin',
            scrollbarColor: isDarkMode 
              ? 'rgba(255, 255, 255, 0.2) transparent' 
              : 'rgba(0, 0, 0, 0.2) transparent',
          }}
        >
          {userMessages.map(({ msg, originalIndex }, index) => {
            const isActive = activeMessageIndex === originalIndex;
            const isListItemHovered = hoveredListItemIndex === index;
            const shortText = getShortText(msg.content);

            return (
              <Box
                key={originalIndex}
                onMouseEnter={(e) => handleListItemMouseEnter(index, e)}
                onMouseLeave={handleListItemMouseLeave}
                onClick={() => handleClick(originalIndex)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '12px 16px',
                  marginBottom: '2px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  backgroundColor: isListItemHovered
                    ? isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)'
                    : 'transparent',
                  transition: 'background-color 0.2s ease',
                  '&:hover': {
                    backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)',
                  },
                }}
              >
                {/* Индикатор активности */}
                {isActive && (
                  <Box
                    sx={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#2196f3',
                      marginRight: '12px',
                      flexShrink: 0,
                    }}
                  />
                )}
                
                <Typography
                  variant="body2"
                  sx={{
                    color: isDarkMode ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.87)',
                    fontSize: '0.875rem',
                    lineHeight: 1.5,
                    fontWeight: 400,
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}
                >
                  {shortText}
                </Typography>
              </Box>
            );
          })}
        </Paper>
      )}

      {/* Всплывающее окно с полным текстом сообщения (появляется через 2 секунды) */}
      {tooltipState.show && showListPanel && showFullTooltip && (
        <Paper
          onMouseLeave={() => {
            setTooltipState({ show: false, content: '', fullContent: '', top: 0 });
            setShowFullTooltip(false);
          }}
          sx={{
            position: 'fixed',
            right: rightSidebarHidden 
              ? '380px' 
              : (rightSidebarOpen ? '788px' : '444px'), // Слева от панели со списком
            top: tooltipState.top,
            maxWidth: '400px',
            maxHeight: '300px',
            overflow: 'auto',
            padding: 2,
            paddingX: 2.5,
            zIndex: 1002,
            backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
            boxShadow: isDarkMode 
              ? '0 8px 32px rgba(0, 0, 0, 0.6)' 
              : '0 8px 32px rgba(0, 0, 0, 0.12)',
            borderRadius: '12px',
            border: 'none',
            pointerEvents: 'all',
            transition: 'right 0.3s ease',
            // Стили для скроллбара
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: 'transparent',
            },
            '&::-webkit-scrollbar-thumb': {
              background: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)',
              borderRadius: '3px',
              '&:hover': {
                background: isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.3)',
              },
            },
            scrollbarWidth: 'thin',
            scrollbarColor: isDarkMode 
              ? 'rgba(255, 255, 255, 0.2) transparent' 
              : 'rgba(0, 0, 0, 0.2) transparent',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: isDarkMode ? 'rgba(255, 255, 255, 0.9)' : 'rgba(0, 0, 0, 0.87)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: '0.875rem',
              lineHeight: 1.6,
            }}
          >
            {tooltipState.fullContent}
          </Typography>
        </Paper>
      )}
    </>
  );
};

export default MessageNavigationBar;

