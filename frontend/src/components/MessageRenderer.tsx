import React, { useState } from 'react';
import { Box, IconButton, Typography, Tooltip, Link, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { ContentCopy as CopyIcon, Check as CheckIcon, Info as InfoIcon, Warning as WarningIcon, Error as ErrorIcon, CheckCircle as SuccessIcon, GetApp as DownloadIcon } from '@mui/icons-material';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import * as XLSX from 'xlsx';

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

  // Функция для определения ASCII таблицы
  const isAsciiTable = (text: string): boolean => {
    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length < 3) return false;
    
    // Проверяем наличие характерных символов ASCII таблиц
    const hasTableChars = lines.some(line => 
      (line.includes('+---') || line.includes('|---') || line.includes('==='))
    );
    
    // Проверяем, что большинство строк содержат |
    const linesWithPipe = lines.filter(line => line.includes('|')).length;
    
    return hasTableChars && linesWithPipe >= lines.length * 0.6;
  };

  // Парсинг ASCII таблицы в структурированные данные
  const parseAsciiTable = (text: string) => {
    const allLines = text.split('\n');
    const lines: string[] = [];
    
    // Определяем границы таблицы - собираем только строки, которые являются частью таблицы
    let inTable = false;
    let lastTableLineIndex = -1;
    
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i].trim();
      if (!line) continue;
      
      // Строка с разделителями или строка с |
      const isTableLine = line.includes('|') || 
                         line.includes('+---') || 
                         line.includes('|---') || 
                         line.includes('===') ||
                         line.match(/^[\s]*[-=+|]+[\s]*$/);
      
      if (isTableLine) {
        inTable = true;
        lines.push(line);
        lastTableLineIndex = i;
      } else if (inTable) {
        // Если мы были в таблице, но встретили строку без символов таблицы - таблица закончилась
        break;
      }
    }
    
    // Находим строки с разделителями
    const separatorIndices = lines
      .map((line, idx) => ({ line, idx }))
      .filter(({ line }) => 
        line.includes('+---') || 
        line.includes('|---') || 
        line.includes('===') ||
        line.match(/^[\s]*[-=+|]+[\s]*$/)
      )
      .map(({ idx }) => idx);
    
    // Извлекаем содержимое ячеек из строки
    const parseCells = (line: string): string[] => {
      return line
        .split('|')
        .map(cell => cell.trim())
        .filter(cell => cell.length > 0);
    };
    
    const headers: string[] = [];
    const rows: string[][] = [];
    
    let currentSection: 'header' | 'body' = 'header';
    
    lines.forEach((line, idx) => {
      // Пропускаем строки-разделители
      if (separatorIndices.includes(idx)) {
        if (currentSection === 'header') {
          currentSection = 'body';
        }
        return;
      }
      
      const cells = parseCells(line);
      if (cells.length === 0) return;
      
      if (currentSection === 'header' && headers.length === 0) {
        headers.push(...cells);
      } else {
        rows.push(cells);
      }
    });
    
    // Возвращаем также количество использованных строк для правильного парсинга остального текста
    return { headers, rows, linesUsed: lastTableLineIndex + 1 };
  };

  // Парсинг Markdown таблицы
  const parseMarkdownTable = (text: string) => {
    const lines = text.split('\n').filter(line => line.trim());
    if (lines.length < 2) return null;
    
    const parseCells = (line: string): string[] => {
      return line
        .split('|')
        .map(cell => cell.trim())
        .filter(cell => cell.length > 0);
    };
    
    const headers = parseCells(lines[0]);
    
    // Проверяем строку разделителя (должна содержать --- или :---: и т.п.)
    if (!lines[1].includes('---')) return null;
    
    const rows = lines.slice(2).map(parseCells);
    
    return { headers, rows };
  };

  // Обработка Markdown внутри ячейки таблицы
  const processCellMarkdown = (cellText: string): string => {
    let processed = cellText;
    
    // Обрабатываем жирный текст
    processed = processed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    processed = processed.replace(/__(.*?)__/g, '<strong>$1</strong>');
    
    // Обрабатываем курсив
    processed = processed.replace(/\*(.*?)\*/g, '<em>$1</em>');
    processed = processed.replace(/_(.*?)_/g, '<em>$1</em>');
    
    // Обрабатываем зачеркнутый текст
    processed = processed.replace(/~~(.*?)~~/g, '<del>$1</del>');
    
    // Обрабатываем инлайн код
    processed = processed.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Обрабатываем ссылки
    processed = processed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    
    return processed;
  };

  // Функция для экспорта таблицы в Excel
  const exportTableToExcel = (headers: string[], rows: string[][], tableIndex: number) => {
    try {
      // Очищаем ячейки от HTML и Markdown тегов для Excel
      const cleanText = (text: string): string => {
        if (!text) return '';
        
        let cleaned = text;
        
        // Удаляем HTML теги
        cleaned = cleaned.replace(/<[^>]+>/g, '');
        
        // Удаляем Markdown форматирование
        cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1'); // Жирный текст
        cleaned = cleaned.replace(/__([^_]+)__/g, '$1'); // Жирный текст (альтернативный)
        cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1'); // Курсив
        cleaned = cleaned.replace(/_([^_]+)_/g, '$1'); // Курсив (альтернативный)
        cleaned = cleaned.replace(/~~([^~]+)~~/g, '$1'); // Зачеркнутый текст
        cleaned = cleaned.replace(/`([^`]+)`/g, '$1'); // Инлайн код
        cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // Ссылки
        cleaned = cleaned.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1'); // Изображения
        
        // Декодируем HTML сущности
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = cleaned;
        cleaned = tempDiv.textContent || tempDiv.innerText || cleaned;
        
        // Убираем лишние пробелы
        cleaned = cleaned.trim();
        
        return cleaned;
      };

      // Подготавливаем данные для Excel
      const excelData: any[][] = [];
      
      // Добавляем заголовки
      if (headers.length > 0) {
        excelData.push(headers.map(header => cleanText(header)));
      }
      
      // Добавляем строки данных
      rows.forEach(row => {
        excelData.push(row.map(cell => cleanText(cell)));
      });

      // Создаем рабочую книгу
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.aoa_to_sheet(excelData);

      // Настраиваем ширину колонок
      const colWidths = headers.map((_, colIndex) => {
        let maxLength = headers[colIndex] ? cleanText(headers[colIndex]).length : 10;
        rows.forEach(row => {
          if (row[colIndex]) {
            const cellLength = cleanText(row[colIndex]).length;
            if (cellLength > maxLength) {
              maxLength = cellLength;
            }
          }
        });
        return { wch: Math.min(Math.max(maxLength + 2, 10), 50) };
      });
      ws['!cols'] = colWidths;

      // Добавляем лист в книгу
      XLSX.utils.book_append_sheet(wb, ws, 'Таблица');

      // Генерируем имя файла с датой и временем
      const now = new Date();
      const dateStr = now.toISOString().slice(0, 19).replace(/:/g, '-').replace('T', '_');
      const fileName = `table_${dateStr}.xlsx`;

      // Сохраняем файл
      XLSX.writeFile(wb, fileName);
    } catch (error) {
      console.error('Ошибка при экспорте таблицы в Excel:', error);
    }
  };

  // Рендеринг таблицы
  const renderTable = (headers: string[], rows: string[][], index: number) => {
    return (
      <Box key={index} sx={{ my: 2, position: 'relative' }}>
        {/* Кнопка экспорта в Excel */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            mb: 1,
          }}
        >
          <Tooltip title="Скачать таблицу в Excel">
            <IconButton
              size="small"
              onClick={() => exportTableToExcel(headers, rows, index)}
              sx={{
                color: 'primary.main',
                '&:hover': {
                  backgroundColor: 'action.hover',
                },
              }}
            >
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        
        <TableContainer component={Paper} sx={{ maxWidth: '100%', overflow: 'auto' }}>
          <Table size="small" sx={{ minWidth: 650 }}>
            {headers.length > 0 && (
              <TableHead>
                <TableRow sx={{ backgroundColor: 'primary.dark' }}>
                  {headers.map((header, idx) => (
                    <TableCell 
                      key={idx} 
                      sx={{ 
                        fontWeight: 'bold',
                        color: 'white',
                        border: '1px solid rgba(224, 224, 224, 0.3)',
                        fontSize: '0.875rem',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {parseInlineMarkdown(processCellMarkdown(header))}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
            )}
            <TableBody>
              {rows.map((row, rowIdx) => (
                <TableRow 
                  key={rowIdx}
                  sx={{ 
                    '&:nth-of-type(odd)': { backgroundColor: 'action.hover' },
                    '&:hover': { backgroundColor: 'action.selected' }
                  }}
                >
                  {row.map((cell, cellIdx) => (
                    <TableCell 
                      key={cellIdx}
                      sx={{ 
                        border: '1px solid rgba(224, 224, 224, 0.3)',
                        fontSize: '0.875rem',
                        whiteSpace: 'pre-wrap',
                        fontFamily: cell.match(/^\d+$/) ? 'monospace' : 'inherit',
                      }}
                    >
                      {parseInlineMarkdown(processCellMarkdown(cell))}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  // Извлечение ASCII таблицы и остального текста
  const extractAsciiTable = (text: string): { table: string; remaining: string } | null => {
    const allLines = text.split('\n');
    let tableLines: string[] = [];
    let tableEndIndex = -1;
    
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i].trim();
      
      const isTableLine = line.includes('|') || 
                         line.includes('+---') || 
                         line.includes('|---') || 
                         line.includes('===') ||
                         line.match(/^[\s]*[-=+|]+[\s]*$/);
      
      if (isTableLine && line) {
        tableLines.push(allLines[i]);
        tableEndIndex = i;
      } else if (tableLines.length > 0) {
        // Таблица закончилась
        break;
      }
    }
    
    if (tableLines.length === 0) return null;
    
    const table = tableLines.join('\n');
    const remaining = allLines.slice(tableEndIndex + 1).join('\n');
    
    return { table, remaining };
  };

  // Извлечение Markdown таблицы из текста
  const extractMarkdownTable = (text: string): { table: string; before: string; after: string } | null => {
    const lines = text.split('\n');
    let tableStart = -1;
    let tableEnd = -1;
    
    // Ищем начало таблицы (строка с |)
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        // Проверяем следующую строку - должна быть разделитель
        if (i + 1 < lines.length && lines[i + 1].trim().includes('---')) {
          tableStart = i;
          // Ищем конец таблицы
          for (let j = i + 2; j < lines.length; j++) {
            const nextLine = lines[j].trim();
            // Таблица заканчивается, если строка не начинается с |
            if (nextLine && !nextLine.startsWith('|')) {
              tableEnd = j;
              break;
            }
          }
          if (tableEnd === -1) {
            tableEnd = lines.length;
          }
          break;
        }
      }
    }
    
    if (tableStart === -1) return null;
    
    const before = lines.slice(0, tableStart).join('\n');
    const table = lines.slice(tableStart, tableEnd).join('\n');
    const after = lines.slice(tableEnd).join('\n');
    
    return { table, before, after };
  };

  // Функция для парсинга Markdown
  const parseMarkdown = (text: string) => {
    // Обрабатываем кодовые блоки (включая незавершенные при стриминге)
    // Сначала ищем полные блоки, потом незавершенные
    const parts = text.split(/(```[\s\S]*?```|```[\s\S]*$)/g);
    
    return parts.map((part, index) => {
      // Проверяем полные кодовые блоки
      if (part.startsWith('```') && part.endsWith('```')) {
        return renderCodeBlock(part, index);
      }
      
      // Проверяем незавершенные кодовые блоки (при стриминге)
      if (part.startsWith('```') && !part.endsWith('```') && isStreaming) {
        // Добавляем временные закрывающие ```, чтобы код отрендерился
        return renderCodeBlock(part + '\n```', index);
      }
      
      // Проверяем на ASCII таблицу
      if (isAsciiTable(part)) {
        const extraction = extractAsciiTable(part);
        if (extraction) {
          const { headers, rows } = parseAsciiTable(extraction.table);
          
          return (
            <React.Fragment key={index}>
              {renderTable(headers, rows, index)}
              {extraction.remaining.trim() && renderMarkdownText(extraction.remaining, index + 1000)}
            </React.Fragment>
          );
        }
      }
      
      // Проверяем на Markdown таблицу (может быть в любом месте текста)
      const tableExtraction = extractMarkdownTable(part);
      if (tableExtraction) {
        const tableData = parseMarkdownTable(tableExtraction.table);
        if (tableData) {
          return (
            <React.Fragment key={index}>
              {tableExtraction.before.trim() && renderMarkdownText(tableExtraction.before, index * 1000 + 1)}
              {renderTable(tableData.headers, tableData.rows, index * 1000 + 2)}
              {tableExtraction.after.trim() && renderMarkdownText(tableExtraction.after, index * 1000 + 3)}
            </React.Fragment>
          );
        }
      }
      
      // Обрабатываем обычный текст с Markdown
      return renderMarkdownText(part, index);
    });
  };

  // Рендер кодового блока с подсветкой синтаксиса
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
      // Маппинг языков для SyntaxHighlighter
      const languageMap: { [key: string]: string } = {
        'js': 'javascript',
        'ts': 'typescript',
        'py': 'python',
        'rb': 'ruby',
        'sh': 'bash',
        'yml': 'yaml',
        'cmd': 'batch',
        'ps1': 'powershell',
      };
      
      const highlightLanguage = languageMap[language] || language;
      
      return (
        <Box key={index} sx={{ position: 'relative', my: 2 }}>
          <Box
            sx={{
              backgroundColor: '#1e1e1e',
              borderRadius: 1,
              p: 0,
              position: 'relative',
              overflow: 'hidden',
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
                  fontWeight: 'bold',
                }}
              >
                {language}
              </Typography>
              <Tooltip title={copiedCode === code ? '✓ Скопировано!' : 'Копировать код'}>
                <IconButton
                  size="small"
                  onClick={() => handleCopyCode(code)}
                  sx={{
                    color: '#cccccc',
                    transition: 'all 0.2s',
                    '&:hover': {
                      backgroundColor: 'rgba(255,255,255,0.1)',
                      color: '#4ec9b0',
                    },
                  }}
                >
                  {copiedCode === code ? (
                    <CheckIcon fontSize="small" sx={{ color: '#4ec9b0' }} />
                  ) : (
                    <CopyIcon fontSize="small" />
                  )}
                </IconButton>
              </Tooltip>
            </Box>
            
            {/* Код с подсветкой синтаксиса */}
            <SyntaxHighlighter
              language={highlightLanguage}
              style={vscDarkPlus}
              customStyle={{
                margin: 0,
                padding: '16px',
                backgroundColor: '#1e1e1e',
                fontSize: '0.875rem',
                lineHeight: 1.5,
                borderRadius: '0 0 4px 4px',
              }}
              wrapLines={true}
              wrapLongLines={true}
              showLineNumbers={code.split('\n').length > 5}
              lineNumberStyle={{
                minWidth: '2.5em',
                paddingRight: '1em',
                color: '#858585',
                textAlign: 'right',
              }}
            >
              {code}
            </SyntaxHighlighter>
          </Box>
        </Box>
      );
    }
    return null;
  };

  // Рендер специальных блоков (Info, Warning, Error, Success)
  const renderSpecialBlock = (type: 'info' | 'warning' | 'error' | 'success', content: string, key: any) => {
    const configs = {
      info: { icon: <InfoIcon />, color: '#2196f3', bgColor: 'rgba(33, 150, 243, 0.1)', title: 'Информация' },
      warning: { icon: <WarningIcon />, color: '#ff9800', bgColor: 'rgba(255, 152, 0, 0.1)', title: 'Внимание' },
      error: { icon: <ErrorIcon />, color: '#f44336', bgColor: 'rgba(244, 67, 54, 0.1)', title: 'Ошибка' },
      success: { icon: <SuccessIcon />, color: '#4caf50', bgColor: 'rgba(76, 175, 80, 0.1)', title: 'Успех' },
    };
    
    const config = configs[type];
    
    return (
      <Box
        key={key}
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1.5,
          p: 2,
          my: 2,
          borderRadius: 1,
          backgroundColor: config.bgColor,
          borderLeft: `4px solid ${config.color}`,
        }}
      >
        <Box sx={{ color: config.color, mt: 0.25, flexShrink: 0 }}>
          {config.icon}
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {parseInlineMarkdown(content)}
          </Typography>
        </Box>
      </Box>
    );
  };

  // Рендер Markdown текста
  const renderMarkdownText = (text: string, index: number) => {
    if (!text.trim()) return null;

    // Обрабатываем специальные блоки с эмодзи (✅, ⚠️, ❌, ℹ️, 📝, 💡)
    const specialBlockRegex = /^[►✅⚠️❌ℹ️📝💡🔔]\s*(.+)$/gim;
    const specialLines: { type: 'info' | 'warning' | 'error' | 'success', content: string }[] = [];
    
    text = text.replace(specialBlockRegex, (match, content) => {
      let type: 'info' | 'warning' | 'error' | 'success' = 'info';
      
      if (match.startsWith('✅') || match.startsWith('►')) {
        type = 'success';
      } else if (match.startsWith('⚠️') || match.startsWith('🔔')) {
        type = 'warning';
      } else if (match.startsWith('❌')) {
        type = 'error';
      } else {
        type = 'info';
      }
      
      specialLines.push({ type, content });
      return `<special-block type="${type}">${content}</special-block>`;
    });

    // Обрабатываем заголовки
    text = text.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Обрабатываем вложенные форматирования правильно
    // Сначала обрабатываем самые внешние теги (жирный), потом внутренние (курсив)
    // Используем жадное совпадение для внешних тегов
    
    // Обрабатываем жирный текст с возможным вложенным курсивом: **текст *курсив* текст**
    text = text.replace(/\*\*([^*]*(?:\*[^*]+\*[^*]*)*)\*\*/g, (match, content) => {
      // Обрабатываем курсив внутри жирного
      const processed = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      return `<strong>${processed}</strong>`;
    });
    
    // Обрабатываем жирный с __
    text = text.replace(/__([^_]*(?:_[^_]+_[^_]*)*)__/g, (match, content) => {
      const processed = content.replace(/_([^_]+)_/g, '<em>$1</em>');
      return `<strong>${processed}</strong>`;
    });
    
    // Обрабатываем оставшийся курсив (который не внутри жирного)
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    text = text.replace(/_([^_]+)_/g, '<em>$1</em>');

    // Обрабатываем зачеркнутый текст
    text = text.replace(/~~(.*?)~~/g, '<del>$1</del>');

    // Обрабатываем подчеркнутый текст (Markdown не поддерживает, но может быть в HTML)
    text = text.replace(/<u>(.*?)<\/u>/g, '<u>$1</u>');
    text = text.replace(/<U>(.*?)<\/U>/g, '<u>$1</u>');

    // Обрабатываем верхние индексы (superscript) для формул
    text = text.replace(/(\w+)\^(\d+)/g, '$1<sup>$2</sup>');
    text = text.replace(/(\w+)²/g, '$1<sup>2</sup>');
    text = text.replace(/(\w+)³/g, '$1<sup>3</sup>');
    text = text.replace(/(\w+)¹/g, '$1<sup>1</sup>');
    text = text.replace(/(\w+)⁰/g, '$1<sup>0</sup>');

    // Обрабатываем нижние индексы (subscript)
    text = text.replace(/(\w+)_(\d+)/g, '$1<sub>$2</sub>');

    // Обрабатываем ссылки
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Обрабатываем изображения
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; height: auto;" />');

    // Обрабатываем инлайн код
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Обрабатываем списки - различаем маркированные и нумерованные
    // Сначала нумерованные (чтобы не конфликтовали с маркированными)
    text = text.replace(/^[\s]*(\d+)\.\s+(.+)$/gim, '<li data-list-type="ordered" data-list-number="$1">$2</li>');
    // Затем маркированные
    text = text.replace(/^[\s]*[-*+]\s+(.+)$/gim, '<li data-list-type="unordered">$1</li>');

    // Обрабатываем цитаты
    text = text.replace(/^>\s+(.+)$/gim, '<blockquote>$1</blockquote>');

    // Обрабатываем горизонтальные линии
    text = text.replace(/^---$/gim, '<hr>');

         // Разбиваем на строки для обработки списков
     const lines = text.split('\n');
     let inList = false;
     let listType: 'ordered' | 'unordered' | null = null;
     let listItems: React.ReactElement[] = [];
     let specialBlockIndex = 0;
     
     const processedLines = lines.map((line, lineIndex) => {
      // Обрабатываем специальные блоки
      if (line.includes('<special-block')) {
        const typeMatch = line.match(/type="(\w+)"/);
        const contentMatch = line.match(/<special-block[^>]*>(.*?)<\/special-block>/);
        
        if (typeMatch && contentMatch && specialLines[specialBlockIndex]) {
          const block = renderSpecialBlock(
            specialLines[specialBlockIndex].type,
            specialLines[specialBlockIndex].content,
            `${index}-special-${lineIndex}`
          );
          specialBlockIndex++;
          return block;
        }
      }

      if (line.startsWith('<h1>') || line.startsWith('<h2>') || line.startsWith('<h3>') || line.startsWith('<h4>')) {
        const level = line.match(/<h(\d)>/)?.[1] || '1';
        const content = line.replace(/<h\d>(.*?)<\/h\d>/, '$1');
        return (
          <Typography
            key={`${index}-${lineIndex}`}
            variant={`h${level}` as any}
            sx={{
              mt: level === '1' ? 3 : level === '2' ? 2.5 : level === '3' ? 2 : 1.5,
              mb: 1,
              fontWeight: 'bold',
              color: 'inherit',
            }}
          >
            {parseInlineMarkdown(content)}
          </Typography>
        );
      }

      // Обрабатываем элементы списка
      if (line.includes('<li')) {
        const listTypeMatch = line.match(/data-list-type="(ordered|unordered)"/);
        const currentListType = listTypeMatch ? (listTypeMatch[1] as 'ordered' | 'unordered') : 'unordered';
        const content = line.replace(/<li[^>]*>(.*?)<\/li>/, '$1');
        
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
        
        if (!inList || listType !== currentListType) {
          // Начинаем новый список или меняем тип
          if (inList && listItems.length > 0) {
            // Завершаем предыдущий список
            const prevList = (
              <Box
                key={`${index}-list-${lineIndex}-prev`}
                component={listType === 'ordered' ? 'ol' : 'ul'}
                sx={{
                  margin: '8px 0',
                  paddingLeft: '20px',
                }}
              >
                {listItems}
              </Box>
            );
            listItems = [];
            inList = false;
            // Начинаем новый список
            inList = true;
            listType = currentListType;
            listItems.push(listItem);
            return prevList;
          } else {
            // Начинаем первый список
            inList = true;
            listType = currentListType;
            listItems.push(listItem);
            return null;
          }
        } else {
          // Продолжаем текущий список
          listItems.push(listItem);
          return null;
        }
      } else if (inList) {
        // Завершаем список
        inList = false;
        const list = (
          <Box
            key={`${index}-list-${lineIndex}`}
            component={listType === 'ordered' ? 'ol' : 'ul'}
            sx={{
              margin: '8px 0',
              paddingLeft: '20px',
            }}
          >
            {listItems}
          </Box>
        );
        listItems = [];
        listType = null;
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
           component={listType === 'ordered' ? 'ol' : 'ul'}
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

  // Функция для поиска соответствующего закрывающего тега
  const findClosingTag = (str: string, tagName: string, startIndex: number): number => {
    const openTag = `<${tagName}`;
    const closeTag = `</${tagName}>`;
    let depth = 1;
    let i = startIndex + openTag.length;
    
    // Находим конец открывающего тега
    while (i < str.length && str[i] !== '>') i++;
    i++; // Пропускаем >
    
    while (i < str.length && depth > 0) {
      if (str.substring(i).startsWith(openTag)) {
        depth++;
        i += openTag.length;
        while (i < str.length && str[i] !== '>') i++;
        i++;
      } else if (str.substring(i).startsWith(closeTag)) {
        depth--;
        if (depth === 0) {
          return i + closeTag.length;
        }
        i += closeTag.length;
      } else {
        i++;
      }
    }
    
    return -1; // Не найдено
  };

  // Парсинг инлайн Markdown с поддержкой вложенных тегов
  const parseInlineMarkdown = (text: string): React.ReactNode => {
    if (!text) return null;
    
    // Рекурсивная функция для обработки вложенных тегов
    const parseWithNestedTags = (str: string): React.ReactNode[] => {
      const parts: React.ReactNode[] = [];
      let lastIndex = 0;
      const supportedTags = ['strong', 'em', 'u', 'del', 'sup', 'sub', 'code', 'a'];
      
      // Сначала обрабатываем самозакрывающиеся теги (img)
      const imgRegex = /<img\s+([^>]+)\/>/gi;
      let imgMatch;
      const imgMatches: Array<{index: number; match: string; attrs: string}> = [];
      
      while ((imgMatch = imgRegex.exec(str)) !== null) {
        imgMatches.push({
          index: imgMatch.index,
          match: imgMatch[0],
          attrs: imgMatch[1]
        });
      }
      
      // Ищем все открывающие теги
      const openTagRegex = /<(strong|em|u|del|sup|sub|code|a)(?:\s[^>]*)?>/gi;
      let match;
      const tagMatches: Array<{index: number; tagName: string; endIndex: number; content: string; fullMatch: string}> = [];
      
      while ((match = openTagRegex.exec(str)) !== null) {
        const tagName = match[1].toLowerCase();
        const openTagEnd = match.index + match[0].length;
        const closeTagIndex = findClosingTag(str, tagName, match.index);
        
        if (closeTagIndex > 0) {
          const content = str.substring(openTagEnd, closeTagIndex - `</${tagName}>`.length);
          tagMatches.push({
            index: match.index,
            tagName,
            endIndex: closeTagIndex,
            content,
            fullMatch: str.substring(match.index, closeTagIndex)
          });
        }
      }
      
      // Объединяем все совпадения и сортируем
      const allMatches: Array<{index: number; type: 'tag' | 'img'; data: any}> = [];
      
      tagMatches.forEach(tag => {
        allMatches.push({
          index: tag.index,
          type: 'tag',
          data: {
            tagName: tag.tagName,
            content: tag.content,
            fullMatch: tag.fullMatch,
            endIndex: tag.endIndex
          }
        });
      });
      
      imgMatches.forEach(img => {
        allMatches.push({
          index: img.index,
          type: 'img',
          data: {
            attrs: img.attrs,
            fullMatch: img.match
          }
        });
      });
      
      // Сортируем по индексу
      allMatches.sort((a, b) => a.index - b.index);
      
      // Удаляем перекрывающиеся теги (вложенные теги уже обработаны в content)
      const filteredMatches: typeof allMatches = [];
      for (let i = 0; i < allMatches.length; i++) {
        const current = allMatches[i];
        let isNested = false;
        
        for (let j = 0; j < i; j++) {
          const prev = allMatches[j];
          if (prev.type === 'tag' && 
              current.index > prev.index && 
              current.index < prev.data.endIndex) {
            isNested = true;
            break;
          }
        }
        
        if (!isNested) {
          filteredMatches.push(current);
        }
      }
      
      filteredMatches.forEach((matchData) => {
        // Добавляем текст до тега
        if (matchData.index > lastIndex) {
          const beforeText = str.substring(lastIndex, matchData.index);
          if (beforeText) {
            parts.push(beforeText);
          }
        }
        
        if (matchData.type === 'img') {
          // Обработка изображения
          const srcMatch = matchData.data.attrs.match(/src="([^"]+)"/);
          const altMatch = matchData.data.attrs.match(/alt="([^"]*)"/);
          if (srcMatch) {
            parts.push(
              <Box
                key={`${matchData.index}-img`}
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
          lastIndex = matchData.index + matchData.data.fullMatch.length;
        } else {
          // Обработка обычных тегов
          const tagName = matchData.data.tagName;
          const content = matchData.data.content;
        
          // Рекурсивно обрабатываем содержимое тега
          const processedContent = parseWithNestedTags(content);
          
          switch (tagName) {
            case 'strong':
              parts.push(
                <Box key={`${matchData.index}-strong`} component="span" sx={{ fontWeight: 'bold' }}>
                  {processedContent}
                </Box>
              );
              break;
            case 'em':
              parts.push(
                <Box key={`${matchData.index}-em`} component="span" sx={{ fontStyle: 'italic' }}>
                  {processedContent}
                </Box>
              );
              break;
            case 'u':
              parts.push(
                <Box key={`${matchData.index}-u`} component="span" sx={{ textDecoration: 'underline' }}>
                  {processedContent}
                </Box>
              );
              break;
            case 'del':
              parts.push(
                <Box key={`${matchData.index}-del`} component="span" sx={{ textDecoration: 'line-through' }}>
                  {processedContent}
                </Box>
              );
              break;
            case 'sup':
              parts.push(
                <Box key={`${matchData.index}-sup`} component="sup" sx={{ fontSize: '0.75em', lineHeight: 0 }}>
                  {processedContent}
                </Box>
              );
              break;
            case 'sub':
              parts.push(
                <Box key={`${matchData.index}-sub`} component="sub" sx={{ fontSize: '0.75em', lineHeight: 0 }}>
                  {processedContent}
                </Box>
              );
              break;
            case 'code':
              parts.push(
                <Box
                  key={`${matchData.index}-code`}
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
                  {processedContent}
                </Box>
              );
              break;
            case 'a':
              const hrefMatch = matchData.data.fullMatch.match(/href="([^"]+)"/);
              if (hrefMatch) {
                parts.push(
                  <Link
                    key={`${matchData.index}-a`}
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
                    {processedContent}
                  </Link>
                );
              }
              break;
            default:
              parts.push(<span key={`${matchData.index}-default`}>{processedContent}</span>);
          }
          
          lastIndex = matchData.data.endIndex;
        }
      });
      
      // Добавляем оставшийся текст
      if (lastIndex < str.length) {
        const remainingText = str.substring(lastIndex);
        if (remainingText) {
          parts.push(remainingText);
        }
      }
      
      return parts.length > 0 ? parts : [str];
    };
    
    const result = parseWithNestedTags(text);
    return result.length === 1 ? result[0] : <>{result}</>;
  };

  return (
    <Box sx={{ position: 'relative' }}>
      {parseMarkdown(content)}
      
    </Box>
  );
};

export default MessageRenderer;
