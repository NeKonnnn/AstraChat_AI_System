import React, { useState } from 'react';
import { Box, IconButton, Typography, Tooltip, Link } from '@mui/material';
import { ContentCopy as CopyIcon, Check as CheckIcon } from '@mui/icons-material';

interface MessageRendererProps {
  content: string;
  isStreaming?: boolean;
}

const MessageRenderer: React.FC<MessageRendererProps> = ({ content, isStreaming = false }) => {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const handleCopyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (error) {
      console.error('Failed to copy code:', error);
    }
  };

  // Функция для парсинга Markdown
  const parseMarkdown = (text: string) => {
    // Сначала обрабатываем кодовые блоки
    const parts = text.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith('```') && part.endsWith('```')) {
        return renderCodeBlock(part, index);
      }
      
      // Обрабатываем обычный текст с Markdown
      return renderMarkdownText(part, index);
    });
  };

  // Рендер кодового блока
  const renderCodeBlock = (codeBlock: string, index: number) => {
    let codeMatch = codeBlock.match(/```(\w+)\n([\s\S]*?)```/);
    let language = 'text';
    let code = '';
    
    if (codeMatch) {
      language = codeMatch[1];
      code = codeMatch[2];
    } else {
      const simpleMatch = codeBlock.match(/```\n?([\s\S]*?)```/);
      if (simpleMatch) {
        code = simpleMatch[1];
      }
    }
    
    if (code !== undefined) {
      return (
        <Box key={index} sx={{ position: 'relative', my: 2 }}>
          <Box
            sx={{
              backgroundColor: '#1e1e1e',
              borderRadius: 1,
              p: 0,
              position: 'relative',
            }}
          >
            {/* Заголовок блока кода */}
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                px: 2,
                py: 1,
                backgroundColor: '#2d2d30',
                borderRadius: '4px 4px 0 0',
                borderBottom: '1px solid #3e3e42',
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: '#cccccc',
                  fontFamily: 'monospace',
                  textTransform: 'uppercase',
                  fontSize: '0.75rem',
                }}
              >
                {language}
              </Typography>
              <Tooltip title={copiedCode === code ? 'Скопировано!' : 'Копировать код'}>
                <IconButton
                  size="small"
                  onClick={() => handleCopyCode(code)}
                  sx={{
                    color: '#cccccc',
                    '&:hover': {
                      backgroundColor: 'rgba(255,255,255,0.1)',
                    },
                  }}
                >
                  {copiedCode === code ? (
                    <CheckIcon fontSize="small" />
                  ) : (
                    <CopyIcon fontSize="small" />
                  )}
                </IconButton>
              </Tooltip>
            </Box>
            
            {/* Код */}
            <Box
              component="pre"
              sx={{
                margin: 0,
                padding: 2,
                backgroundColor: '#1e1e1e',
                color: '#d4d4d4',
                fontFamily: '"Fira Code", "Monaco", "Menlo", "Consolas", monospace',
                fontSize: '0.875rem',
                lineHeight: 1.5,
                overflow: 'auto',
                borderRadius: '0 0 4px 4px',
                whiteSpace: 'pre-wrap',
                tabSize: 4,
                WebkitTabSize: 4,
                MozTabSize: 4,
              }}
            >
              <code>{code}</code>
            </Box>
          </Box>
        </Box>
      );
    }
    return null;
  };

  // Рендер Markdown текста
  const renderMarkdownText = (text: string, index: number) => {
    if (!text.trim()) return null;

    // Обрабатываем заголовки
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Обрабатываем жирный текст
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Обрабатываем курсив
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/_(.*?)_/g, '<em>$1</em>');

    // Обрабатываем зачеркнутый текст
    text = text.replace(/~~(.*?)~~/g, '<del>$1</del>');

    // Обрабатываем ссылки
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Обрабатываем изображения
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; height: auto;" />');

    // Обрабатываем инлайн код
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Обрабатываем списки
    text = text.replace(/^[\s]*[-*+]\s+(.+)$/gim, '<li>$1</li>');
    text = text.replace(/^[\s]*\d+\.\s+(.+)$/gim, '<li>$1</li>');

    // Обрабатываем цитаты
    text = text.replace(/^>\s+(.+)$/gim, '<blockquote>$1</blockquote>');

    // Обрабатываем горизонтальные линии
    text = text.replace(/^---$/gim, '<hr>');

         // Разбиваем на строки для обработки списков
     const lines = text.split('\n');
     let inList = false;
     let listItems: React.ReactElement[] = [];
     
     const processedLines = lines.map((line, lineIndex) => {
      if (line.startsWith('<h1>') || line.startsWith('<h2>') || line.startsWith('<h3>')) {
        const level = line.match(/<h(\d)>/)?.[1] || '1';
        const content = line.replace(/<h\d>(.*?)<\/h\d>/, '$1');
        return (
          <Typography
            key={`${index}-${lineIndex}`}
            variant={`h${level}` as any}
            sx={{
              mt: level === '1' ? 3 : level === '2' ? 2 : 1,
              mb: 1,
              fontWeight: 'bold',
              color: 'inherit',
            }}
          >
            {content}
          </Typography>
        );
      }

             if (line.startsWith('<li>')) {
         const content = line.replace(/<li>(.*?)<\/li>/, '$1');
         const listItem = (
           <Box
             key={`${index}-${lineIndex}`}
             component="li"
             sx={{
               ml: 2,
               mb: 0.5,
               '&::marker': {
                 color: 'primary.main',
               },
             }}
           >
             {parseInlineMarkdown(content)}
           </Box>
         );
         
         if (!inList) {
           inList = true;
           listItems = [];
         }
         
         listItems.push(listItem);
         return null; // Не рендерим сразу, собираем в список
       } else if (inList) {
         // Завершаем список
         inList = false;
         const list = (
           <Box
             key={`${index}-list-${lineIndex}`}
             component="ul"
             sx={{
               margin: '8px 0',
               paddingLeft: '20px',
             }}
           >
             {listItems}
           </Box>
         );
         listItems = [];
         return list;
       }

      if (line.startsWith('<blockquote>')) {
        const content = line.replace(/<blockquote>(.*?)<\/blockquote>/, '$1');
        return (
          <Box
            key={`${index}-${lineIndex}`}
            sx={{
              borderLeft: '4px solid',
              borderColor: 'primary.main',
              pl: 2,
              ml: 2,
              my: 1,
              fontStyle: 'italic',
              color: 'text.secondary',
            }}
          >
            {parseInlineMarkdown(content)}
          </Box>
        );
      }

      if (line === '<hr>') {
        return (
          <Box
            key={`${index}-${lineIndex}`}
            sx={{
              borderTop: '1px solid',
              borderColor: 'divider',
              my: 2,
            }}
          />
        );
      }

      if (line.trim()) {
        return (
          <Typography
            key={`${index}-${lineIndex}`}
            variant="body1"
            component="div"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              lineHeight: 1.5,
              mb: 0.5,
            }}
          >
            {parseInlineMarkdown(line)}
          </Typography>
        );
      }

      return <br key={`${index}-${lineIndex}`} />;
    });

         // Проверяем, не остался ли незавершенный список
     if (inList && listItems.length > 0) {
       const finalList = (
         <Box
           key={`${index}-final-list`}
           component="ul"
           sx={{
             margin: '8px 0',
             paddingLeft: '20px',
           }}
         >
           {listItems}
         </Box>
       );
       processedLines.push(finalList);
     }
     
     return (
       <Box key={index} sx={{ mb: 1 }}>
         {processedLines.filter(line => line !== null)}
       </Box>
     );
  };

  // Парсинг инлайн Markdown
  const parseInlineMarkdown = (text: string) => {
    const parts = text.split(/(<[^>]+>.*?<\/[^>]+>|<[^>]+\/>)/g);
    
    return parts.map((part, partIndex) => {
      if (part.startsWith('<strong>')) {
        const content = part.replace(/<strong>(.*?)<\/strong>/, '$1');
        return (
          <Box
            key={partIndex}
            component="span"
            sx={{ fontWeight: 'bold' }}
          >
            {content}
          </Box>
        );
      }

      if (part.startsWith('<em>')) {
        const content = part.replace(/<em>(.*?)<\/em>/, '$1');
        return (
          <Box
            key={partIndex}
            component="span"
            sx={{ fontStyle: 'italic' }}
          >
            {content}
          </Box>
        );
      }

      if (part.startsWith('<del>')) {
        const content = part.replace(/<del>(.*?)<\/del>/, '$1');
        return (
          <Box
            key={partIndex}
            component="span"
            sx={{ textDecoration: 'line-through' }}
          >
            {content}
          </Box>
        );
      }

      if (part.startsWith('<code>')) {
        const content = part.replace(/<code>(.*?)<\/code>/, '$1');
        return (
          <Box
            key={partIndex}
            component="code"
            sx={{
              backgroundColor: 'rgba(175, 184, 193, 0.2)',
              padding: '2px 4px',
              borderRadius: '3px',
              fontFamily: 'monospace',
              fontSize: '0.875em',
              color: 'inherit',
            }}
          >
            {content}
          </Box>
        );
      }

      if (part.startsWith('<a ')) {
        const hrefMatch = part.match(/href="([^"]+)"/);
        const contentMatch = part.match(/>([^<]+)</);
        if (hrefMatch && contentMatch) {
          return (
            <Link
              key={partIndex}
              href={hrefMatch[1]}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                color: 'primary.main',
                textDecoration: 'underline',
                '&:hover': {
                  textDecoration: 'none',
                },
              }}
            >
              {contentMatch[1]}
            </Link>
          );
        }
      }

      if (part.startsWith('<img ')) {
        const srcMatch = part.match(/src="([^"]+)"/);
        const altMatch = part.match(/alt="([^"]*)"/);
        if (srcMatch) {
          return (
            <Box
              key={partIndex}
              component="img"
              src={srcMatch[1]}
              alt={altMatch ? altMatch[1] : ''}
              sx={{
                maxWidth: '100%',
                height: 'auto',
                borderRadius: 1,
                my: 1,
                display: 'block',
              }}
            />
          );
        }
      }

      return part;
    });
  };

  return (
    <Box sx={{ position: 'relative' }}>
      {parseMarkdown(content)}
      
    </Box>
  );
};

export default MessageRenderer;
