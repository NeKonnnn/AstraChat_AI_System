import React, { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Typography,
  Card,
  CardContent,
  Avatar,
  Chip,
  Tooltip,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  OutlinedInput,
  InputAdornment,
  Slider,
  CircularProgress,
  Popover,
  type PopoverActions,
  Collapse,
  Drawer,
  Divider,
  Checkbox,
  FormControlLabel,
  Paper,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import {
  Send as SendIcon,
  Person as PersonIcon,
  Clear as ClearIcon,
  ContentCopy as CopyIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Edit as EditIcon,
  Mic as MicIcon,
  VolumeUp as VolumeUpIcon,
  Close as CloseIcon,
  Upload as UploadIcon,
  Square as SquareIcon,
  SmartToyOutlined as GearMenuAgentsIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Add as AddIcon,
  Share as ShareIcon,
  AutoStories as KbIcon,
  Check as CheckIcon,
  YouTube as YouTubeIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import type { SxProps, Theme } from '@mui/material/styles';
import { useTheme, alpha } from '@mui/material/styles';
import { useAppContext, useAppActions, Message, MultiLLMResponseSlot } from '../contexts/AppContext';
import { useSocket } from '../contexts/SocketContext';
import { getApiUrl, getWsUrl, API_ENDPOINTS } from '../config/api';
import MessageRenderer from '../components/MessageRenderer';
import { DocumentSearchPanel } from '../components/DocumentSearchPanel';
import { useNavigate } from 'react-router-dom';
import TranscriptionResultModal from '../components/TranscriptionResultModal';
import ModelSelector from '../components/ModelSelector';
import MessageNavigationBar from '../components/MessageNavigationBar';
import ShareConfirmDialog from '../components/ShareConfirmDialog';
import ChatInputBar from '../components/ChatInputBar';
import ChatGearAgentsPanel from '../components/ChatGearAgentsPanel';
import VoiceChatDialog from '../components/VoiceChatDialog';
import AgentConstructorPanel from '../components/AgentConstructorPanel';
import AgentSelector from '../components/AgentSelector';
import ChatInputStatusCluster from '../components/ChatInputStatusCluster';
import { useMyAgentSelection, useOrchestratorAgentsAnyActive } from '../hooks/useChatInputAgentIndicators';
import { getSidebarPanelBackground } from '../constants/sidebarPanelColor';
import { getWorkZoneBackgroundColor, isWorkZoneAnimatedMode } from '../constants/workZoneBackground';
import { useWorkZoneBgMode } from '../hooks/useWorkZoneBgMode';
import WorkZoneStarrySky from '../components/WorkZoneStarrySky';
import WorkZoneSnowfall from '../components/WorkZoneSnowfall';
import {
  isKnowledgeRagEnabled,
  setKnowledgeRagEnabled,
  KNOWLEDGE_RAG_STORAGE_EVENT,
} from '../utils/knowledgeRagStorage';
import {
  ASTRA_TRIGGER_ATTACH,
  ASTRA_OPEN_AGENT_CONSTRUCTOR,
  ASTRA_OPEN_TRANSCRIPTION_SIDEBAR,
} from '../constants/hotkeys';
import {
  getDropdownPanelSx,
  getDropdownItemSx,
  getFormFieldInputSx,
  DROPDOWN_CHEVRON_SX,
  DROPDOWN_PAPER_MARGIN_TOP,
  DROPDOWN_PAPER_MIN_WIDTH_PX,
  DROPDOWN_PAPER_DEFAULT_WIDTH_PX,
  DROPDOWN_ITEM_HOVER_BG_DARK,
  DROPDOWN_ITEM_HOVER_BG_LIGHT,
  MENU_ACTION_TEXT_SIZE,
  CHAT_GEAR_MENU_PANEL_WIDTH_PX,
  CHAT_GEAR_MENU_LEFT_RAIL_WIDTH_PX,
  CHAT_GEAR_MENU_EXPANDED_WIDTH_PX,
  CHAT_GEAR_MENU_AGENTS_RIGHT_MIN_PX,
  CHAT_GEAR_MENU_PANELS_GAP_PX,
  CHAT_GEAR_MENU_ANCHOR_VERTICAL_OFFSET,
  CHAT_GEAR_MENU_PAPER_MAX_HEIGHT,
  CHAT_GEAR_MENU_PAPER_MAX_HEIGHT_PX,
  getChatGearMenuPaperHeightPx,
  CHAT_GEAR_MENU_MARGIN_THRESHOLD_PX,
  CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX,
  SIDEBAR_CHAT_ROW_LIST_ITEM_BUTTON_SX,
  SIDEBAR_LIST_ICON_SX,
  SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX,
  SIDEBAR_HIDE_SCROLLBAR_SX,
  getSidebarRailCollapsedListItemButtonSx,
} from '../constants/menuStyles';
import SidebarRailMenuGlyph from '../components/SidebarRailMenuGlyph';
import {
  SidebarRailTranscribeIcon,
  SidebarRailPromptsIcon,
  SidebarRailAgentIcon,
} from '../constants/sidebarRailIcons';

interface UnifiedChatPageProps {
  isDarkMode: boolean;
  sidebarOpen?: boolean;
}

interface ModelWindow {
  id: string;
  selectedModel: string;
}

/** Иконка «сравнение моделей» для тёмной темы (светлый глиф на тёмной кнопке). */
const MULTI_LLM_COMPARE_ICON_DARK_THEME_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAA7DAAAOwwHHb6hkAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAKhJREFUOI2tkTEOwkAQA22EQJSQf+QVNPwqBaKAt9BS8Qv+QEfPVUNzh6KwURIUN9btWV7vrjQHgBOQGEYCjpFBAnYjGlXAO/ogqNVAHWl/kvQYNEDTY/BNshiKHcH2S9JaklxcbTtHPmTdPvM98832o6XFtpdBg23mTefdj6k7aPNfO2gjGqHgOtol37Uaofuer4xQElwkPYHVgEeSdJ41SXcH8ySZgg8Dm7tpcrd/HwAAAABJRU5ErkJggg==';

/** Иконка для светлой темы (тёмный глиф на светлой кнопке). */
const MULTI_LLM_COMPARE_ICON_LIGHT_THEME_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAB2AAAAdgFOeyYIAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAJ5JREFUOI2tkksOwjAMRF8QEmIJ3INTsOFWCFXchi2r3qLn6L5ZhUVNlLbTph9GskZxrMnYMfwJL8ADIRMeKJSAB84zHroAjboIIne1ULUDJ0rgYaEEopPdiNUcauAA4BJVR2v5brmbcWn8AaqkNgBuL9RPxsfeeRJLZxB57QwiVAs/vJcIedqvySFdpE7bBfNWuQGeSmCLkw7WONmGL2KrPMuVWrUJAAAAAElFTkSuQmCC';

function MultiLlmModeToggleIcon({ isDarkMode }: { isDarkMode: boolean }): React.ReactElement {
  const src = isDarkMode
    ? MULTI_LLM_COMPARE_ICON_DARK_THEME_DATA_URL
    : MULTI_LLM_COMPARE_ICON_LIGHT_THEME_DATA_URL;
  return (
    <Box
      component="img"
      src={src}
      alt=""
      draggable={false}
      sx={{
        width: 16,
        height: 16,
        display: 'block',
        flexShrink: 0,
        objectFit: 'contain',
        pointerEvents: 'none',
      }}
    />
  );
}

/** Значение для Select / POST multi-llm: для llm-svc нужен полный path, иначе бэкенд не маршрутизирует хост. */
function availableModelSelectValue(m: { name: string; path: string }): string {
  return m.path?.startsWith('llm-svc://') ? m.path : m.path || m.name;
}

/** Текст одного столбца multi-LLM как на экране (варианты перегенерации). */
function getMultiLlmColumnDisplayText(slot: MultiLLMResponseSlot): string {
  if (slot.alternativeResponses?.length && slot.currentResponseIndex !== undefined) {
    const i = slot.currentResponseIndex;
    if (i >= 0 && i < slot.alternativeResponses.length) {
      const t = slot.alternativeResponses[i];
      if (t !== undefined) return t;
    }
  }
  return slot.content;
}

interface AgentStatus {
  is_initialized: boolean;
  mode: string;
  available_agents: number;
  orchestrator_active: boolean;
}

/** Drag файлов из ОС; выделенный текст даёт text/plain без Files — не показываем зону загрузки */
function dataTransferHasFiles(dt: DataTransfer | null): boolean {
  if (!dt) return false;
  try {
    if (dt.items?.length) {
      for (let i = 0; i < dt.items.length; i++) {
        if (dt.items[i].kind === 'file') return true;
      }
    }
  } catch {
    /* ignore */
  }
  const types = dt.types;
  if (!types || types.length === 0) return false;
  const domTypes = types as unknown as { contains?: (s: string) => boolean };
  if (typeof domTypes.contains === 'function') {
    return domTypes.contains('Files');
  }
  return Array.from(types).includes('Files');
}

// ================================
// ИНТЕРФЕЙС ДАННЫХ ДЛЯ КАРТОЧКИ СООБЩЕНИЯ
// (callback-и передаются через ref, чтобы React.memo не реагировал на их пересоздание)
// ================================
interface MessageCardData {
  handleSendMessageFromRenderer: (prompt: string) => void;
  handleCopyMessage: (content: string) => void;
  handleEditClick: (message: Message) => void;
  handleRegenerate: (message: Message) => void;
  handleEditMultiLlmColumn: (message: Message, slotIndex: number) => void;
  handleRegenerateMultiLlmColumn: (message: Message, slotIndex: number) => void;
  synthesizeSpeech: (text: string) => void;
  handleEnterShareMode: () => void;
  handleToggleMessage: (userMsgId: string, assistantMsgId: string) => void;
  updateMessage: (
    chatId: string,
    messageId: string,
    content?: string,
    isStreaming?: boolean,
    multiLLMResponses?: MultiLLMResponseSlot[],
    alternativeResponses?: string[],
    currentResponseIndex?: number,
  ) => void;
  formatTimestamp: (ts: string) => string;
  currentChatId: string | undefined;
  messageRefs: React.MutableRefObject<(HTMLDivElement | null)[]>;
}

interface MessageCardProps {
  message: Message;
  index: number;
  isPairStart: boolean;
  isSelected: boolean;
  nextMessageId: string | null;
  shareMode: boolean;
  isSpeaking: boolean;
  isDarkMode: boolean;
  interfaceSettings: {
    userNoBorder: boolean;
    assistantNoBorder: boolean;
    leftAlignMessages: boolean;
    showUserName: boolean;
  };
  username: string | undefined;
  dataRef: React.MutableRefObject<MessageCardData>;
}

const MessageCardComponent = ({
  message, index, isPairStart, isSelected, nextMessageId,
  shareMode, isSpeaking, isDarkMode, interfaceSettings, username, dataRef,
}: MessageCardProps): React.ReactElement => {
  const isUser = message.role === 'user';
  const [isHovered, setIsHovered] = useState(false);
  const [hoveredMultiLlmCol, setHoveredMultiLlmCol] = useState<number | null>(null);
  const hideOuterActionBar = !isUser && (message.multiLLMResponses?.length ?? 0) > 0;
  const multiLlmActionIconSx = {
    opacity: 0.7,
    p: 0.5,
    borderRadius: '6px',
    minWidth: '28px',
    width: '28px',
    height: '28px',
    '&:hover': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
    '&:hover:not(:disabled)': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
    '& .MuiSvgIcon-root': { fontSize: '18px !important', width: '18px !important', height: '18px !important' },
  } as const;
  const shouldShowBorder = isUser
    ? !interfaceSettings.userNoBorder
    : !interfaceSettings.assistantNoBorder;

  const messageContent = (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.3 }}>
        <Avatar
          sx={{ width: 24, height: 24, mr: 1, bgcolor: isUser ? 'primary.dark' : 'transparent' }}
          src={isUser ? undefined : '/astra.png'}
        >
          {isUser ? <PersonIcon /> : null}
        </Avatar>
        <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}>
          {isUser ? (interfaceSettings.showUserName && username ? username : 'Вы') : 'AstraChat'}
        </Typography>
        <Typography variant="caption" sx={{ ml: 'auto', opacity: 0.6, fontSize: '0.7rem' }}>
          {dataRef.current.formatTimestamp(message.timestamp)}
        </Typography>
      </Box>

      <Box sx={{ width: '100%' }}>
        {!isUser && message.documentSearch && (
          <DocumentSearchPanel trace={message.documentSearch} />
        )}
        {message.multiLLMResponses && message.multiLLMResponses.length > 0 ? (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: `repeat(${Math.min(message.multiLLMResponses.length, 4)}, minmax(0, 1fr))`,
              },
              gap: 1.5,
            }}
          >
            {message.multiLLMResponses.map((response, respIndex) => {
              const displayBody = (() => {
                if (response.alternativeResponses?.length && response.currentResponseIndex !== undefined) {
                  const ci = response.currentResponseIndex;
                  if (ci >= 0 && ci < response.alternativeResponses.length) {
                    const alt = response.alternativeResponses[ci];
                    if (alt !== undefined) return response.isStreaming ? alt : alt.trimEnd();
                  }
                }
                return response.isStreaming ? response.content : response.content.trimEnd();
              })();
              return (
                <Card
                  key={`${response.model}-${respIndex}`}
                  onMouseEnter={() => setHoveredMultiLlmCol(respIndex)}
                  onMouseLeave={() => setHoveredMultiLlmCol((h) => (h === respIndex ? null : h))}
                  sx={{
                    border: '1px solid',
                    borderColor: response.error ? 'error.main' : 'divider',
                    bgcolor: response.error ? 'error.light' : 'background.paper',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', pb: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="caption" fontWeight="bold" color={response.error ? 'error' : 'primary'}>
                        {response.model}
                      </Typography>
                      {response.isStreaming && <Chip label="Генерируется..." size="small" color="info" />}
                      {response.error && <Chip label="Ошибка" size="small" color="error" />}
                    </Box>
                    {response.error ? (
                      <Alert severity="error" sx={{ mt: 1 }}>
                        <Typography variant="body2">{response.content}</Typography>
                      </Alert>
                    ) : (
                      <MessageRenderer
                        content={displayBody}
                        isStreaming={response.isStreaming}
                        onSendMessage={dataRef.current.handleSendMessageFromRenderer}
                      />
                    )}
                  </CardContent>
                  {!isUser && !response.error ? (
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: 0.5,
                        px: 1,
                        pb: 1,
                        pt: 0,
                        minHeight: 28,
                        opacity: hoveredMultiLlmCol === respIndex ? 1 : 0,
                        visibility: hoveredMultiLlmCol === respIndex ? 'visible' : 'hidden',
                      }}
                    >
                      {response.alternativeResponses && response.alternativeResponses.length > 1 ? (
                        <>
                          <Tooltip title="Предыдущий вариант">
                            <span>
                              <IconButton
                                size="small"
                                onClick={() => {
                                  const ci = response.currentResponseIndex ?? 0;
                                  if (ci <= 0 || !dataRef.current.currentChatId || !message.multiLLMResponses) return;
                                  const ni = ci - 1;
                                  const nextText = response.alternativeResponses![ni] ?? '';
                                  const newCols = message.multiLLMResponses.map((r, i) =>
                                    i === respIndex
                                      ? { ...r, currentResponseIndex: ni, content: nextText }
                                      : r,
                                  );
                                  dataRef.current.updateMessage(
                                    dataRef.current.currentChatId,
                                    message.id,
                                    undefined,
                                    false,
                                    newCols,
                                  );
                                }}
                                disabled={(response.currentResponseIndex ?? 0) === 0}
                                sx={multiLlmActionIconSx}
                              >
                                <ChevronLeftIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Typography
                            variant="caption"
                            sx={{ opacity: 0.7, fontSize: '0.7rem', minWidth: '35px', textAlign: 'center' }}
                          >
                            {((response.currentResponseIndex ?? 0) + 1)}/{response.alternativeResponses.length}
                          </Typography>
                          <Tooltip title="Следующий вариант">
                            <span>
                              <IconButton
                                size="small"
                                onClick={() => {
                                  const ci = response.currentResponseIndex ?? 0;
                                  const al = response.alternativeResponses!;
                                  if (
                                    ci >= al.length - 1 ||
                                    !dataRef.current.currentChatId ||
                                    !message.multiLLMResponses
                                  )
                                    return;
                                  const ni = ci + 1;
                                  const nextText = al[ni] ?? '';
                                  const newCols = message.multiLLMResponses.map((r, i) =>
                                    i === respIndex
                                      ? { ...r, currentResponseIndex: ni, content: nextText }
                                      : r,
                                  );
                                  dataRef.current.updateMessage(
                                    dataRef.current.currentChatId,
                                    message.id,
                                    undefined,
                                    false,
                                    newCols,
                                  );
                                }}
                                disabled={
                                  (response.currentResponseIndex ?? 0) >= response.alternativeResponses.length - 1
                                }
                                sx={multiLlmActionIconSx}
                              >
                                <ChevronRightIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                          <Box sx={{ width: '1px', height: '16px', bgcolor: 'divider', mx: 0.5 }} />
                        </>
                      ) : null}
                      <Tooltip title="Копировать">
                        <IconButton
                          size="small"
                          onClick={() =>
                            dataRef.current.handleCopyMessage(getMultiLlmColumnDisplayText(response))
                          }
                          sx={multiLlmActionIconSx}
                        >
                          <CopyIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Редактировать">
                        <IconButton
                          size="small"
                          onClick={() => dataRef.current.handleEditMultiLlmColumn(message, respIndex)}
                          sx={multiLlmActionIconSx}
                        >
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Перегенерировать">
                        <span>
                          <IconButton
                            size="small"
                            onClick={() => dataRef.current.handleRegenerateMultiLlmColumn(message, respIndex)}
                            disabled={Boolean(response.isStreaming)}
                            sx={multiLlmActionIconSx}
                          >
                            <RefreshIcon />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Прочесть вслух">
                        <IconButton
                          size="small"
                          onClick={() =>
                            dataRef.current.synthesizeSpeech(getMultiLlmColumnDisplayText(response))
                          }
                          disabled={isSpeaking}
                          sx={multiLlmActionIconSx}
                        >
                          <VolumeUpIcon />
                        </IconButton>
                      </Tooltip>
                      {!shareMode ? (
                        <Tooltip title="Поделиться">
                          <IconButton
                            size="small"
                            onClick={() => dataRef.current.handleEnterShareMode()}
                            sx={multiLlmActionIconSx}
                          >
                            <ShareIcon />
                          </IconButton>
                        </Tooltip>
                      ) : null}
                    </Box>
                  ) : null}
                </Card>
              );
            })}
          </Box>
        ) : (
          <MessageRenderer
            content={(() => {
              if (message.alternativeResponses && message.alternativeResponses.length > 0 && message.currentResponseIndex !== undefined) {
                const currentIndex = message.currentResponseIndex;
                if (currentIndex >= 0 && currentIndex < message.alternativeResponses.length) {
                  const alt = message.alternativeResponses[currentIndex];
                  return alt !== undefined
                    ? (message.isStreaming ? alt : alt.trimEnd())
                    : message.content;
                }
              }
              return message.isStreaming ? message.content : message.content.trimEnd();
            })()}
            isStreaming={message.isStreaming}
            onSendMessage={dataRef.current.handleSendMessageFromRenderer}
          />
        )}
      </Box>
    </>
  );

  return (
    <Box
      ref={(el: HTMLDivElement | null) => { dataRef.current.messageRefs.current[index] = el; }}
      data-message-index={index}
      sx={{ display: 'flex', flexDirection: 'row', alignItems: 'flex-start', mb: 1.5, width: '100%' }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {shareMode && isPairStart && (
        <Checkbox
          checked={isSelected}
          onChange={() => dataRef.current.handleToggleMessage(message.id, nextMessageId!)}
          sx={{ mt: 1, mr: 1, p: 0.5 }}
        />
      )}

      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: interfaceSettings.leftAlignMessages ? 'flex-start' : (isUser ? 'flex-end' : 'flex-start'),
          flex: 1,
        }}
      >
        {shouldShowBorder ? (
          <Card
            className="message-bubble"
            data-theme={isDarkMode ? 'dark' : 'light'}
            sx={{
              maxWidth: interfaceSettings.leftAlignMessages ? '100%' : (isUser ? '75%' : '100%'),
              minWidth: '180px',
              width: interfaceSettings.leftAlignMessages ? '100%' : (isUser ? undefined : '100%'),
              backgroundColor: isUser ? 'primary.main' : isDarkMode ? 'background.paper' : '#f8f9fa',
              color: isUser ? 'primary.contrastText' : isDarkMode ? 'text.primary' : '#333',
              boxShadow: isDarkMode ? '0 2px 8px rgba(0,0,0,0.15)' : '0 2px 8px rgba(0,0,0,0.1)',
            }}
          >
            <CardContent sx={{ p: 1.2, '&:last-child': { pb: 1.2 } }}>
              {messageContent}
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ width: '100%', p: 1.2 }}>
            {messageContent}
          </Box>
        )}

        {/* Кнопки действий снизу карточки (для multi-LLM — только под каждой колонкой) */}
        {!hideOuterActionBar && (
        <Box sx={{
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.5,
          mt: 1, minHeight: 28,
          opacity: isHovered ? 1 : 0,
          visibility: isHovered ? 'visible' : 'hidden',
        }}>
          {/* Навигация по вариантам ответов */}
          {!isUser && message.alternativeResponses && message.alternativeResponses.length > 1 && (
            <>
              <Tooltip title="Предыдущий вариант">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => {
                      const ci = message.currentResponseIndex ?? 0;
                      if (ci > 0) {
                        const ni = ci - 1;
                        dataRef.current.updateMessage(
                          dataRef.current.currentChatId!, message.id,
                          message.alternativeResponses![ni],
                          undefined, undefined, message.alternativeResponses, ni,
                        );
                      }
                    }}
                    disabled={(message.currentResponseIndex ?? 0) === 0}
                    sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                      '&:hover:not(:disabled)': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } } }}
                  >
                    <ChevronLeftIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Typography variant="caption" sx={{ opacity: 0.7, fontSize: '0.7rem', minWidth: '35px', textAlign: 'center' }}>
                {((message.currentResponseIndex ?? 0) + 1)}/{message.alternativeResponses.length}
              </Typography>
              <Tooltip title="Следующий вариант">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => {
                      const ci = message.currentResponseIndex ?? 0;
                      if (ci < message.alternativeResponses!.length - 1) {
                        const ni = ci + 1;
                        dataRef.current.updateMessage(
                          dataRef.current.currentChatId!, message.id,
                          message.alternativeResponses![ni],
                          undefined, undefined, message.alternativeResponses, ni,
                        );
                      }
                    }}
                    disabled={(message.currentResponseIndex ?? 0) >= message.alternativeResponses!.length - 1}
                    sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                      '&:hover:not(:disabled)': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } } }}
                  >
                    <ChevronRightIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Box sx={{ width: '1px', height: '16px', bgcolor: 'divider', mx: 0.5 }} />
            </>
          )}

          <Tooltip title="Копировать">
            <IconButton
              size="small"
              onClick={() => {
                if (message.multiLLMResponses && message.multiLLMResponses.length > 0) {
                  dataRef.current.handleCopyMessage(
                    message.multiLLMResponses.map(r => `[${r.model}]\n${r.content}`).join('\n\n---\n\n')
                  );
                } else {
                  dataRef.current.handleCopyMessage(message.content);
                }
              }}
              className="message-copy-button"
              data-theme={isDarkMode ? 'dark' : 'light'}
              sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                '&:hover': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
                '& .MuiSvgIcon-root': { fontSize: '18px !important', width: '18px !important', height: '18px !important' } }}
            >
              <CopyIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Редактировать">
            <IconButton
              size="small"
              onClick={() => dataRef.current.handleEditClick(message)}
              className="message-edit-button"
              data-theme={isDarkMode ? 'dark' : 'light'}
              sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                '&:hover': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
                '& .MuiSvgIcon-root': { fontSize: '18px !important', width: '18px !important', height: '18px !important' } }}
            >
              <EditIcon />
            </IconButton>
          </Tooltip>

          {!isUser && (
            <Tooltip title="Перегенерировать">
              <IconButton
                size="small"
                onClick={() => dataRef.current.handleRegenerate(message)}
                className="message-regenerate-button"
                data-theme={isDarkMode ? 'dark' : 'light'}
                sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                  '&:hover': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
                  '& .MuiSvgIcon-root': { fontSize: '18px !important', width: '18px !important', height: '18px !important' } }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          )}

          <Tooltip title="Прочесть вслух">
            <IconButton
              size="small"
              onClick={() => {
                let textToSpeak = message.content;
                if (!isUser && message.alternativeResponses && message.alternativeResponses.length > 0 && message.currentResponseIndex !== undefined) {
                  const ci = message.currentResponseIndex;
                  if (ci >= 0 && ci < message.alternativeResponses.length) textToSpeak = message.alternativeResponses[ci];
                }
                if (!isUser && message.multiLLMResponses && message.multiLLMResponses.length > 0) {
                  textToSpeak = message.multiLLMResponses.filter(r => !r.error).map(r => r.content).join(' ');
                }
                dataRef.current.synthesizeSpeech(textToSpeak);
              }}
              className="message-speak-button"
              data-theme={isDarkMode ? 'dark' : 'light'}
              disabled={isSpeaking}
              sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                '&:hover:not(:disabled)': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
                '&:disabled': { opacity: 0.4 },
                '& .MuiSvgIcon-root': { fontSize: '18px !important', width: '18px !important', height: '18px !important' } }}
            >
              <VolumeUpIcon />
            </IconButton>
          </Tooltip>

          {!isUser && !shareMode && (
            <Tooltip title="Поделиться">
              <IconButton
                size="small"
                onClick={() => dataRef.current.handleEnterShareMode()}
                className="message-share-button"
                data-theme={isDarkMode ? 'dark' : 'light'}
                sx={{ opacity: 0.7, p: 0.5, borderRadius: '6px', minWidth: '28px', width: '28px', height: '28px',
                  '&:hover': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
                  '& .MuiSvgIcon-root': { fontSize: '18px !important', width: '18px !important', height: '18px !important' } }}
              >
                <ShareIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
        )}
      </Box>
    </Box>
  );
};

// Мемоизируем: ре-рендер только когда меняется сам message, shareMode, isSelected, isSpeaking или настройки
const MessageCard = React.memo(MessageCardComponent, (prev, next) =>
  prev.message === next.message &&
  prev.shareMode === next.shareMode &&
  prev.isSelected === next.isSelected &&
  prev.isSpeaking === next.isSpeaking &&
  prev.isDarkMode === next.isDarkMode &&
  prev.interfaceSettings === next.interfaceSettings,
);

// ================================

export default function UnifiedChatPage({ isDarkMode, sidebarOpen = true }: UnifiedChatPageProps) {
  const navigate = useNavigate();
  const theme = useTheme();

  // Состояние для правой панели
  const [rightSidebarOpen, setRightSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('rightSidebarOpen');
    return saved !== null ? saved === 'true' : false;
  });
  const [rightSidebarHidden, setRightSidebarHidden] = useState(() => {
    const saved = localStorage.getItem('rightSidebarHidden');
    return saved !== null ? saved === 'true' : false;
  });
  const [rightSidebarPanelBg, setRightSidebarPanelBg] = useState(() => getSidebarPanelBackground());
  const [agentConstructorOpen, setAgentConstructorOpen] = useState(false);
  const workZoneMode = useWorkZoneBgMode();
  const workZoneAnimated = isWorkZoneAnimatedMode(workZoneMode);
  const workZoneBgColor = getWorkZoneBackgroundColor(isDarkMode, workZoneMode);

  useEffect(() => {
    const onColorChanged = () => setRightSidebarPanelBg(getSidebarPanelBackground());
    window.addEventListener('sidebarColorChanged', onColorChanged);
    return () => window.removeEventListener('sidebarColorChanged', onColorChanged);
  }, []);

  // Режим расположения выбора модели: 'settings' | 'workspace' | 'workspace_agent'
  type ModelSelectorMode = 'settings' | 'workspace' | 'workspace_agent';
  const readModelSelectorMode = (): ModelSelectorMode => {
    const saved = localStorage.getItem('model_selector_mode');
    if (saved === 'settings' || saved === 'workspace' || saved === 'workspace_agent') return saved;
    const oldBool = localStorage.getItem('show_model_selector_in_settings');
    return oldBool === 'true' ? 'settings' : 'workspace_agent';
  };
  const [modelSelectorMode, setModelSelectorMode] = useState<ModelSelectorMode>(readModelSelectorMode);

  // Состояние для панели с диалогами (навигация по сообщениям)
  const [showDialoguesPanel, setShowDialoguesPanel] = useState(() => {
    const saved = localStorage.getItem('show_dialogues_panel');
    return saved !== null ? saved === 'true' : true;
  });
  
  // Слушаем изменения настроек
  useEffect(() => {
    const handleSettingsChange = () => {
      setModelSelectorMode(readModelSelectorMode());
      const savedPanel = localStorage.getItem('show_dialogues_panel');
      setShowDialoguesPanel(savedPanel !== null ? savedPanel === 'true' : true);
    };
    
    window.addEventListener('interfaceSettingsChanged', handleSettingsChange);
    return () => window.removeEventListener('interfaceSettingsChanged', handleSettingsChange);
  }, []);

  // Сохранение состояния правой боковой панели
  useEffect(() => {
    localStorage.setItem('rightSidebarOpen', String(rightSidebarOpen));
  }, [rightSidebarOpen]);

  useEffect(() => {
    localStorage.setItem('rightSidebarHidden', String(rightSidebarHidden));
  }, [rightSidebarHidden]);
  
  // Состояние для модального окна транскрибации
  const [transcriptionModalOpen, setTranscriptionModalOpen] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptionResult, setTranscriptionResult] = useState('');
  const [transcriptionMenuOpen, setTranscriptionMenuOpen] = useState(false);
  const [transcriptionYoutubeUrl, setTranscriptionYoutubeUrl] = useState('');
  const [transcriptionId, setTranscriptionId] = useState<string | null>(null);
  const transcriptionFileInputRef = useRef<HTMLInputElement>(null);
  
  // Состояние для текстового чата
  const [inputMessage, setInputMessage] = useState('');
  const [showCopyAlert, setShowCopyAlert] = useState(false);
  
  // Состояние для редактирования сообщений
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingMessage, setEditingMessage] = useState<Message | null>(null);
  const [editingMultiLlmSlotIndex, setEditingMultiLlmSlotIndex] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  
  const [showVoiceDialog, setShowVoiceDialog] = useState(false);

  
  // Состояние для документов
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [query, setQuery] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [isQuerying, setIsQuerying] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [queryResponse, setQueryResponse] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<Array<{
    name: string;
    size: number;
    type: string;
    uploadDate: string;
  }>>([]);
  const [showDocumentDialog, setShowDocumentDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  /** Раскрытый подпункт меню «Инструменты» (колонка справа, как в LeChat). */
  const [gearToolsPanel, setGearToolsPanel] = useState<'main' | 'agents'>('main');
  const gearToolsPopoverActionRef = useRef<PopoverActions | null>(null);
  /** Якорь меню «Инструменты» — верх всей пилюли ввода (кнопка виджетов съезжает при многострочном тексте). */
  const chatInputToolsAnchorRef = useRef<HTMLDivElement>(null);
  /** Ширина меню «Инструменты» = ширина пилюли ввода (две колонки на всю длину поля). */
  const [gearToolsMenuWidthPx, setGearToolsMenuWidthPx] = useState<number | null>(null);
  /** Фиксированная высота бумаги Popover: левая колонка сразу «как с агентами», без роста вниз при раскрытии. */
  const [gearToolsPaperHeightPx, setGearToolsPaperHeightPx] = useState<number | null>(null);

  /** Геометрия меню от пилюли ввода + пересчёт позиции Popover. */
  useLayoutEffect(() => {
    if (!anchorEl) return;
    const shell = chatInputToolsAnchorRef.current;
    if (shell) {
      const rect = shell.getBoundingClientRect();
      setGearToolsMenuWidthPx(Math.round(rect.width));
      setGearToolsPaperHeightPx(getChatGearMenuPaperHeightPx(rect.top));
    }
    gearToolsPopoverActionRef.current?.updatePosition();
  }, [anchorEl, gearToolsPanel]);

  useEffect(() => {
    if (!anchorEl) return;
    const shell = chatInputToolsAnchorRef.current;
    if (!shell || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      const rect = shell.getBoundingClientRect();
      setGearToolsMenuWidthPx(Math.round(rect.width));
      setGearToolsPaperHeightPx(getChatGearMenuPaperHeightPx(rect.top));
      queueMicrotask(() => gearToolsPopoverActionRef.current?.updatePosition());
    });
    ro.observe(shell);
    return () => ro.disconnect();
  }, [anchorEl]);

  // База знаний в ответах LLM (страница KB + библиотека из настроек)
  const [useKbRag, setUseKbRag] = useState(() => isKnowledgeRagEnabled());

  useEffect(() => {
    const onRag = () => setUseKbRag(isKnowledgeRagEnabled());
    window.addEventListener(KNOWLEDGE_RAG_STORAGE_EVENT, onRag);
    return () => window.removeEventListener(KNOWLEDGE_RAG_STORAGE_EVENT, onRag);
  }, []);

  const toggleKbRag = useCallback(() => {
    setUseKbRag((prev) => {
      const next = !prev;
      setKnowledgeRagEnabled(next);
      return next;
    });
  }, []);

  const myAgentSelection = useMyAgentSelection();

  // Состояние для режима "Поделиться"
  const [shareMode, setShareMode] = useState(false);
  const [selectedMessages, setSelectedMessages] = useState<Set<string>>(new Set());
  const [isCreatingShareLink, setIsCreatingShareLink] = useState(false);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const onAttach = () => fileInputRef.current?.click();
    window.addEventListener(ASTRA_TRIGGER_ATTACH, onAttach);
    return () => window.removeEventListener(ASTRA_TRIGGER_ATTACH, onAttach);
  }, []);

  useEffect(() => {
    const onAgent = () => {
      setRightSidebarHidden(false);
      setRightSidebarOpen(true);
      setAgentConstructorOpen(true);
    };
    const onTranscription = () => {
      setRightSidebarHidden(false);
      setRightSidebarOpen(true);
      setTranscriptionMenuOpen(true);
    };
    window.addEventListener(ASTRA_OPEN_AGENT_CONSTRUCTOR, onAgent);
    window.addEventListener(ASTRA_OPEN_TRANSCRIPTION_SIDEBAR, onTranscription);
    return () => {
      window.removeEventListener(ASTRA_OPEN_AGENT_CONSTRUCTOR, onAgent);
      window.removeEventListener(ASTRA_OPEN_TRANSCRIPTION_SIDEBAR, onTranscription);
    };
  }, []);
  // Ref со всеми callback-ами для MessageCard (обновляется перед каждым рендером)
  const messageCardDataRef = useRef<MessageCardData>({} as MessageCardData);

  // Context и Socket
  const { state } = useAppContext();
  const { 
    clearMessages, 
    showNotification, 
    setSpeaking, 
    setRecording, 
    updateMessage, 
    getCurrentMessages, 
    getCurrentChat,
    createChat,
    setCurrentChat,
    updateChatTitle,
    getProjectById,
    setLoading,
  } = useAppActions();
  const { sendMessage, regenerateResponse, regenerateMultiLlmSlot, isConnected, isConnecting, stopGeneration } =
    useSocket();

  // Получаем текущий чат и сообщения
  const currentChat = getCurrentChat();
  const messages = getCurrentMessages();
  const project = currentChat?.projectId ? getProjectById(currentChat.projectId) : null;

  const hasActiveChatStreaming = useMemo(
    () =>
      messages.some(
        (m) =>
          m.isStreaming || (m.multiLLMResponses?.some((r) => r.isStreaming) ?? false),
      ),
    [messages],
  );

  const dropdownPanelSx = getDropdownPanelSx(isDarkMode);
  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);

  /** Как поле «Модель» / «Категория» в AgentConstructorPanel: outlined без синей обводки при «фокусе». */
  const multiLlmFormFieldInputSx = useMemo(() => getFormFieldInputSx(isDarkMode), [isDarkMode]);
  const multiLlmModelFieldSx = useMemo(
    () =>
      [
        multiLlmFormFieldInputSx,
        {
          '& .MuiOutlinedInput-root': { cursor: 'pointer' },
          '& .MuiOutlinedInput-root.Mui-focused fieldset': {
            borderColor: isDarkMode ? 'rgba(255,255,255,0.23)' : 'rgba(0,0,0,0.23)',
            borderWidth: '1px',
          },
          '& .MuiOutlinedInput-root:hover fieldset': {
            borderColor: isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
          },
          '& .MuiOutlinedInput-root.Mui-focused:hover fieldset': {
            borderColor: isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
          },
          '& .MuiInputLabel-root.Mui-focused': {
            color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
          },
          '& .MuiFormLabel-asterisk': { color: '#f44336' },
        },
      ] as SxProps<Theme>,
    [multiLlmFormFieldInputSx, isDarkMode],
  );

  /** Выровнять по высоте с триггером AgentSelector (py 0.75 + строка ~0.82rem) — компактнее 32px. */
  const multiLlmModeToggleIconButtonSx = useMemo(
    () => ({
      flexShrink: 0,
      boxSizing: 'border-box' as const,
      width: 30,
      height: 30,
      minWidth: 30,
      minHeight: 30,
      p: 0,
      m: 0,
      borderRadius: '10px',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'visible',
      lineHeight: 0,
      bgcolor: isDarkMode ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.9)',
      border: isDarkMode ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.12)',
      color: isDarkMode ? 'white' : 'text.primary',
      transition: 'background 0.15s, border-color 0.15s',
      '&:hover': {
        bgcolor: isDarkMode ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,1)',
        borderColor: isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.2)',
      },
    }),
    [isDarkMode],
  );

  // Сбрасываем поле ввода при переключении между чатами, чтобы черновик не "дублировался"
  useEffect(() => {
    setInputMessage('');
  }, [state.currentChatId]);

  // Стабильный обработчик для MessageRenderer (НЕ меняется при ререндерах!)
  const handleSendMessageFromRendererRef = useRef<((prompt: string) => void) | null>(null);
  
  // Обновляем ref при изменении зависимостей, но НЕ создаем новую функцию
  useEffect(() => {
    handleSendMessageFromRendererRef.current = (prompt: string) => {
      if (currentChat && isConnected && !state.isLoading) {
        sendMessage(prompt, currentChat.id);
      }
    };
  }, [currentChat, isConnected, state.isLoading, sendMessage]);
  
  // Создаем стабильную функцию ОДИН РАЗ (никогда не меняется!)
  const handleSendMessageFromRenderer = useCallback((prompt: string) => {
    handleSendMessageFromRendererRef.current?.(prompt);
  }, []); // ← Пустой массив! Функция НЕ пересоздается!
  
  // Состояние для режима multi-llm
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const orchestratorAgentsAnyActive = useOrchestratorAgentsAnyActive(Boolean(agentStatus?.is_initialized));
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; path: string; size_mb?: number }>>([]);
  const [modelWindows, setModelWindows] = useState<ModelWindow[]>([{ id: '1', selectedModel: '' }]);
  const [multiLlmModelMenu, setMultiLlmModelMenu] = useState<{ windowId: string; anchorEl: HTMLElement } | null>(null);
  const isMultiLlmMode = agentStatus?.mode === 'multi-llm';
  const multiLlmHasSelection = useMemo(
    () => modelWindows.some((w) => Boolean(w.selectedModel)),
    [modelWindows],
  );
  const multiLlmInputBlocked = isMultiLlmMode && !multiLlmHasSelection;
  const chatAwaitingTokens = state.isLoading && !hasActiveChatStreaming;
  const prevAgentModeRef = useRef<string | undefined>(undefined);
  const skipNextMultiLlmChatResetRef = useRef(false);
  const lastMultiLlmPostedKeyRef = useRef<string>('');
  /** Режим до входа в multi-llm с рабочей области — для возврата по кнопке. */
  const modeBeforeMultiLlmRef = useRef<string>('direct');

  const loadAgentStatus = useCallback(async () => {
    try {
      const response = await fetch(`${getApiUrl('/api/agent/status')}`);
      if (response.ok) {
        const data = await response.json();
        setAgentStatus((prev) => {
          if (JSON.stringify(prev) !== JSON.stringify(data)) {
            return data;
          }
          return prev;
        });
      }
    } catch {
      /* ignore */
    }
  }, []);

  const libraryInputBadge = useMemo(
    () => (
      <ChatInputStatusCluster
        isDarkMode={isDarkMode}
        libraryActive={useKbRag}
        onLibraryToggle={toggleKbRag}
        standardAgentsActive={orchestratorAgentsAnyActive}
        myAgentName={myAgentSelection?.name ?? null}
      />
    ),
    [isDarkMode, useKbRag, toggleKbRag, orchestratorAgentsAnyActive, myAgentSelection?.name],
  );

  const handleToggleMultiLlmMode = useCallback(async () => {
    if (!agentStatus?.is_initialized) {
      showNotification(
        'warning',
        'Агентная архитектура не инициализирована. Настройки → Агенты → инициализация.',
      );
      return;
    }
    if (state.isLoading || hasActiveChatStreaming) {
      showNotification('warning', 'Дождитесь окончания генерации перед сменой режима');
      return;
    }
    try {
      if (agentStatus.mode === 'multi-llm') {
        const restore =
          modeBeforeMultiLlmRef.current === 'multi-llm' ? 'direct' : modeBeforeMultiLlmRef.current;
        const response = await fetch(getApiUrl('/api/agent/mode'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: restore }),
        });
        if (!response.ok) throw new Error('mode');
        await loadAgentStatus();
        window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
        showNotification(
          'info',
          restore === 'agent' ? 'Включён агентный режим' : 'Включён прямой режим чата',
        );
        return;
      }
      modeBeforeMultiLlmRef.current = agentStatus.mode;
      const response = await fetch(getApiUrl('/api/agent/mode'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'multi-llm' }),
      });
      if (!response.ok) throw new Error('mode');
      await loadAgentStatus();
      window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
      showNotification('info', 'Режим: сравнение моделей');
    } catch {
      showNotification('error', 'Не удалось переключить режим');
    }
  }, [agentStatus, loadAgentStatus, showNotification, state.isLoading, hasActiveChatStreaming]);

  /** Кнопка multi-LLM в поле ввода, когда селектор модели/агента спрятан в настройках. */
  const multiLlmSettingsExtraAction = useMemo(
    () =>
      modelSelectorMode === 'settings' ? (
        <Tooltip title="Сравнение моделей">
          <span>
            <IconButton
              onClick={() => {
                void handleToggleMultiLlmMode();
              }}
              disabled={
                !agentStatus?.is_initialized ||
                !isConnected ||
                state.isLoading ||
                hasActiveChatStreaming
              }
              sx={multiLlmModeToggleIconButtonSx}
            >
              <MultiLlmModeToggleIcon isDarkMode={isDarkMode} />
            </IconButton>
          </span>
        </Tooltip>
      ) : null,
    [
      modelSelectorMode,
      handleToggleMultiLlmMode,
      agentStatus?.is_initialized,
      isConnected,
      state.isLoading,
      hasActiveChatStreaming,
      isDarkMode,
      multiLlmModeToggleIconButtonSx,
    ],
  );

  // Убираем автоматическое создание чатов - чаты создаются только по кнопке

  // Загружаем настройки интерфейса
  const [interfaceSettings, setInterfaceSettings] = useState(() => {
    const savedAutoTitle = localStorage.getItem('auto_generate_titles');
    const savedLargeTextAsFile = localStorage.getItem('large_text_as_file');
    const savedUserNoBorder = localStorage.getItem('user_no_border');
    const savedAssistantNoBorder = localStorage.getItem('assistant_no_border');
    const savedLeftAlignMessages = localStorage.getItem('left_align_messages');
    const savedWidescreenMode = localStorage.getItem('widescreen_mode');
    const savedShowUserName = localStorage.getItem('show_user_name');
    const savedEnableNotification = localStorage.getItem('enable_notification');
    const savedChatInputStyle = localStorage.getItem('chat_input_style');
    return {
      autoGenerateTitles: savedAutoTitle !== null ? savedAutoTitle === 'true' : true,
      largeTextAsFile: savedLargeTextAsFile !== null ? savedLargeTextAsFile === 'true' : false,
      userNoBorder: savedUserNoBorder !== null ? savedUserNoBorder === 'true' : false,
      assistantNoBorder: savedAssistantNoBorder !== null ? savedAssistantNoBorder === 'true' : false,
      leftAlignMessages: savedLeftAlignMessages !== null ? savedLeftAlignMessages === 'true' : false,
      widescreenMode: savedWidescreenMode !== null ? savedWidescreenMode === 'true' : false,
      showUserName: savedShowUserName !== null ? savedShowUserName === 'true' : false,
      enableNotification: savedEnableNotification !== null ? savedEnableNotification === 'true' : false,
      chatInputStyle: (savedChatInputStyle as 'compact' | 'classic') || 'compact',
    };
  });

  // Слушаем изменения настроек интерфейса в localStorage
  useEffect(() => {
    const handleStorageChange = () => {
      const savedAutoTitle = localStorage.getItem('auto_generate_titles');
      const savedLargeTextAsFile = localStorage.getItem('large_text_as_file');
      const savedUserNoBorder = localStorage.getItem('user_no_border');
      const savedAssistantNoBorder = localStorage.getItem('assistant_no_border');
      const savedLeftAlignMessages = localStorage.getItem('left_align_messages');
      const savedWidescreenMode = localStorage.getItem('widescreen_mode');
      const savedShowUserName = localStorage.getItem('show_user_name');
      const savedEnableNotification = localStorage.getItem('enable_notification');
      const savedChatInputStyle = localStorage.getItem('chat_input_style');
      setInterfaceSettings({
        autoGenerateTitles: savedAutoTitle !== null ? savedAutoTitle === 'true' : true,
        largeTextAsFile: savedLargeTextAsFile !== null ? savedLargeTextAsFile === 'true' : false,
        userNoBorder: savedUserNoBorder !== null ? savedUserNoBorder === 'true' : false,
        assistantNoBorder: savedAssistantNoBorder !== null ? savedAssistantNoBorder === 'true' : false,
        leftAlignMessages: savedLeftAlignMessages !== null ? savedLeftAlignMessages === 'true' : false,
        widescreenMode: savedWidescreenMode !== null ? savedWidescreenMode === 'true' : false,
        showUserName: savedShowUserName !== null ? savedShowUserName === 'true' : false,
        enableNotification: savedEnableNotification !== null ? savedEnableNotification === 'true' : false,
        chatInputStyle: (savedChatInputStyle as 'compact' | 'classic') || 'compact',
      });
    };

    window.addEventListener('storage', handleStorageChange);
    // Также проверяем изменения в том же окне через кастомное событие
    window.addEventListener('interfaceSettingsChanged', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('interfaceSettingsChanged', handleStorageChange);
    };
  }, []);

  // Автоматически обновляем название чата на основе первого сообщения пользователя
  useEffect(() => {
    if (currentChat && messages.length === 1 && interfaceSettings.autoGenerateTitles) {
      const firstMessage = messages[0];
      if (firstMessage.role === 'user' && currentChat.title === 'Новый чат') {
        const title = firstMessage.content.length > 50 
          ? firstMessage.content.substring(0, 50) + '...'
          : firstMessage.content;
        updateChatTitle(currentChat.id, title);
      }
    }
  }, [currentChat, messages, updateChatTitle, interfaceSettings.autoGenerateTitles]);

  // Убираем автоматическую остановку генерации при смене чата
  // Генерация должна происходить в том чате, где был задан вопрос

  // Состояние для кнопки "Прочесть вслух"
  const [isSpeaking, setIsSpeaking] = useState(false);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const [voiceSettingsTTS] = useState(() => ({
    voice_id: localStorage.getItem('voice_id') || 'ru',
    speech_rate: parseFloat(localStorage.getItem('speech_rate') || '1.0'),
    voice_speaker: localStorage.getItem('voice_speaker') || 'baya',
  }));

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Автоматический фокус на поле ввода при загрузке
  useEffect(() => {
    const timer = setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 300);
    
    return () => clearTimeout(timer);
  }, []);

  // Автоматический фокус на поле ввода при переключении чатов
  useEffect(() => {
    if (currentChat?.id) {
      const timer = setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 200);
      
      return () => clearTimeout(timer);
    }
  }, [currentChat?.id]);

  // Функция для воспроизведения звукового оповещения
  const playNotificationSound = useCallback(() => {
    if (!interfaceSettings.enableNotification) return;
    
    try {
      // Создаем простой звуковой сигнал через Web Audio API
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.value = 800; // Частота в Гц
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.3);
    } catch (error) {
    }
  }, [interfaceSettings.enableNotification]);

  // Отслеживаем завершение генерации сообщений для воспроизведения звука
  const prevStreamingRef = useRef<boolean>(false);
  useEffect(() => {
    const isCurrentlyStreaming = hasActiveChatStreaming;

    if (prevStreamingRef.current && !isCurrentlyStreaming) {
      playNotificationSound();
    }

    prevStreamingRef.current = isCurrentlyStreaming;
  }, [hasActiveChatStreaming, playNotificationSound]);

  // Фокус на поле ввода при загрузке
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const loadAvailableModelsOnce = async () => {
      try {
        const response = await fetch(`${getApiUrl('/api/models/available')}`);
        if (response.ok) {
          const data = await response.json();
          const newModels = data.models || [];
          setAvailableModels((prev) => {
            if (JSON.stringify(prev) !== JSON.stringify(newModels)) {
              return newModels;
            }
            return prev;
          });
        }
      } catch {
        /* ignore */
      }
    };

    loadAgentStatus();
    loadAvailableModelsOnce();

    const onAgentChange = () => {
      loadAgentStatus();
    };
    window.addEventListener('astrachatAgentStatusChanged', onAgentChange);
    const onVis = () => {
      if (document.visibilityState === 'visible') {
        loadAgentStatus();
      }
    };
    document.addEventListener('visibilitychange', onVis);
    const interval = setInterval(() => {
      loadAgentStatus();
    }, 10000);

    return () => {
      window.removeEventListener('astrachatAgentStatusChanged', onAgentChange);
      document.removeEventListener('visibilitychange', onVis);
      clearInterval(interval);
    };
  }, [loadAgentStatus]);

  // Список GGUF для multi-llm и после выхода из multi-llm
  useEffect(() => {
    if (!agentStatus?.mode) return;
    const loadAvailableModels = async () => {
      try {
        const response = await fetch(`${getApiUrl('/api/models/available')}`);
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data.models || []);
        }
      } catch {
        /* ignore */
      }
    };
    loadAvailableModels();
  }, [agentStatus?.mode]);

  useEffect(() => {
    if (skipNextMultiLlmChatResetRef.current) {
      skipNextMultiLlmChatResetRef.current = false;
      return;
    }
    setModelWindows((prev) => (prev.length === 0 ? [{ id: '1', selectedModel: '' }] : prev));
  }, [state.currentChatId]);

  // После переключения режима с multi-llm на другой — убираем многоколоночный layout со страницы чата
  useEffect(() => {
    const mode = agentStatus?.mode;
    const prev = prevAgentModeRef.current;
    if (prev === 'multi-llm' && mode && mode !== 'multi-llm') {
      setModelWindows([{ id: '1', selectedModel: '' }]);
    }
    prevAgentModeRef.current = mode;
  }, [agentStatus?.mode]);

  useEffect(() => {
    if (agentStatus?.mode !== 'multi-llm') {
      lastMultiLlmPostedKeyRef.current = '';
    }
  }, [agentStatus?.mode]);

  // Загружаем список документов при инициализации
  useEffect(() => {
    const loadDocuments = async () => {
      try {
        const response = await fetch(getApiUrl('/api/documents'));
        if (response.ok) {
          const result: any = await response.json();
          if (result.success && result.documents) {
            // Преобразуем список имен файлов в объекты файлов
            const files = result.documents.map((filename: string) => ({
              name: filename,
              size: 0, // Размер не сохраняется на бэкенде
              type: 'application/octet-stream', // Тип не сохраняется на бэкенде
              uploadDate: new Date().toISOString(),
            }));
            setUploadedFiles(files);
          }
        }
      } catch (error) {
        
      }
    };

    loadDocuments();
  }, []);


  // ================================
  // ФУНКЦИИ ТЕКСТОВОГО ЧАТА
  // ================================

  // ================================
  // ФУНКЦИИ ДЛЯ РЕЖИМА MULTI-LLM
  // ================================
  
  const addModelWindow = (): void => {
    if (modelWindows.length >= 4) {
      showNotification('warning', 'Можно добавить максимум 4 модели');
      return;
    }
    const newId = String(modelWindows.length + 1);
    setModelWindows([...modelWindows, { id: newId, selectedModel: '' }]);
  };

  const removeModelWindow = (id: string): void => {
    if (modelWindows.length <= 1) {
      showNotification('warning', 'Должна остаться хотя бы одна модель');
      return;
    }
    setModelWindows((prev) => prev.filter((w) => w.id !== id));
  };

  const updateModelWindow = (id: string, updates: Partial<ModelWindow>): void => {
    setModelWindows((prev) => prev.map((w) => (w.id === id ? { ...w, ...updates } : w)));
  };

  const getSelectedModels = (): string[] => {
    return modelWindows.map(w => w.selectedModel).filter(m => m !== '');
  };

  const handleModelSelect = (windowId: string, modelName: string): void => {
    const selectedModels = getSelectedModels();
    
    // Проверяем, не выбрана ли эта модель в другом окне
    if (selectedModels.includes(modelName) && modelWindows.find(w => w.id === windowId)?.selectedModel !== modelName) {
      showNotification('error', 'Эта модель уже выбрана в другом окне');
      return;
    }
    
    updateModelWindow(windowId, { selectedModel: modelName });
  };

  useEffect(() => {
    if (hasActiveChatStreaming) setMultiLlmModelMenu(null);
  }, [hasActiveChatStreaming]);

  useEffect(() => {
    setMultiLlmModelMenu((prev) =>
      prev && !modelWindows.some((w) => w.id === prev.windowId) ? null : prev,
    );
  }, [modelWindows]);

  const handleSendMessageMultiLLM = async (): Promise<void> => {
    if (!inputMessage.trim() || !isConnected) {
      return;
    }

    if (state.isLoading || hasActiveChatStreaming) {
      return;
    }

    const selectedModels = getSelectedModels();
    if (selectedModels.length === 0) {
      showNotification('error', 'Выберите хотя бы одну модель');
      return;
    }

    let chatId = currentChat?.id;
    if (!chatId) {
      chatId = createChat('Новый чат');
      skipNextMultiLlmChatResetRef.current = true;
      setCurrentChat(chatId);
    }

    setLoading(true);

    const modelsKey = [...selectedModels].sort().join('\u0001');

    try {
      if (lastMultiLlmPostedKeyRef.current !== modelsKey) {
        const response = await fetch(`${getApiUrl('/api/agent/multi-llm/models')}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ models: selectedModels }),
        });

        if (!response.ok) {
          throw new Error('Не удалось установить модели');
        }
        lastMultiLlmPostedKeyRef.current = modelsKey;
      }

      sendMessage(inputMessage.trim(), chatId, true, undefined, true);

      setInputMessage('');

      setTimeout(() => {
        inputRef.current?.focus();
      }, 10);
    } catch {
      setLoading(false);
      showNotification('error', 'Ошибка отправки сообщения');
    }
  };

  const handleSendMessage = (): void => {
    // Если режим multi-llm, используем специальную функцию
    if (agentStatus?.mode === 'multi-llm') {
      handleSendMessageMultiLLM();
      return;
    }

    if (!inputMessage.trim() || !isConnected || state.isLoading) {
      if (!isConnected) {
        showNotification('error', 'Нет соединения с сервером. Попробуйте переподключиться.');
      }
      return;
    }
    
    // Автоматически создаем новый чат, если его нет
    if (!currentChat) {
      const newChatId = createChat('Новый чат');
      setCurrentChat(newChatId);
      const messageText = inputMessage.trim();
      setInputMessage('');
      setTimeout(() => {
        sendMessage(messageText, newChatId);
        inputRef.current?.focus();
      }, 50);
      return;
    }

    sendMessage(inputMessage.trim(), currentChat.id);
    setInputMessage('');
    
    // Возвращаем фокус на поле ввода
    setTimeout(() => {
      inputRef.current?.focus();
    }, 10);
  };

  const handleKeyPress = (event: React.KeyboardEvent): void => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  // Обработчик вставки текста
  const handlePaste = async (event: React.ClipboardEvent<HTMLDivElement>): Promise<void> => {
    if (!interfaceSettings.largeTextAsFile) {
      return; // Если настройка выключена, используем стандартное поведение
    }

    const pastedText = event.clipboardData.getData('text');
    
    // Определяем, что считается "большим текстом" (например, больше 1000 символов)
    const LARGE_TEXT_THRESHOLD = 1000;
    
    if (pastedText.length > LARGE_TEXT_THRESHOLD) {
      event.preventDefault(); // Предотвращаем стандартную вставку
      
      try {
        // Создаем текстовый файл из вставленного текста
        const blob = new Blob([pastedText], { type: 'text/plain' });
        const fileName = `pasted_text_${Date.now()}.txt`;
        const file = new File([blob], fileName, { type: 'text/plain' });
        
        // Загружаем файл через handleFileUpload
        await handleFileUpload(file);
        
        // Очищаем поле ввода
        setInputMessage('');
        
        showNotification('success', 'Большой текст вставлен как файл');
      } catch (error) {
        
        showNotification('error', 'Ошибка при создании файла из вставленного текста');
        // В случае ошибки разрешаем стандартную вставку
      }
    }
  };

  const handleCopyMessage = async (content: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(content);
      setShowCopyAlert(true);
    } catch (error) {
      showNotification('error', 'Не удалось скопировать текст');
    }
  };

  // Функция для перегенерации ответа LLM
  const handleEditMultiLlmColumn = useCallback((message: Message, slotIndex: number): void => {
    const slot = message.multiLLMResponses?.[slotIndex];
    if (!slot) return;
    setEditingMessage(message);
    setEditingMultiLlmSlotIndex(slotIndex);
    setEditText(getMultiLlmColumnDisplayText(slot));
    setEditDialogOpen(true);
  }, []);

  const handleRegenerateMultiLlmColumn = useCallback(
    (message: Message, slotIndex: number): void => {
      if (!currentChat || !isConnected) {
        showNotification('error', 'Нет соединения с сервером');
        return;
      }
      const col = message.multiLLMResponses?.[slotIndex];
      if (!col || col.error) return;
      if (col.isStreaming) {
        showNotification('warning', 'Дождитесь окончания генерации этой модели');
        return;
      }
      const messageIndex = messages.findIndex((m) => m.id === message.id);
      let userMessage: Message | null = null;
      for (let i = messageIndex - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          userMessage = messages[i];
          break;
        }
      }
      if (!userMessage) {
        showNotification('error', 'Не найдено предыдущее сообщение пользователя');
        return;
      }
      const displayText = getMultiLlmColumnDisplayText(col);
      let alts =
        col.alternativeResponses && col.alternativeResponses.length > 0
          ? [...col.alternativeResponses]
          : [displayText];
      const ci = col.currentResponseIndex ?? 0;
      if (ci < alts.length) alts[ci] = displayText;
      const newIndex = alts.length;
      alts = [...alts, ''];

      const newCols = message.multiLLMResponses!.map((r, i) =>
        i === slotIndex
          ? {
              ...r,
              alternativeResponses: alts,
              currentResponseIndex: newIndex,
              isStreaming: true,
              content: '',
            }
          : { ...r, isStreaming: false },
      );
      updateMessage(currentChat.id, message.id, undefined, true, newCols);
      regenerateMultiLlmSlot(userMessage.content, message.id, currentChat.id, col.model);
    },
    [currentChat, isConnected, messages, regenerateMultiLlmSlot, showNotification, updateMessage],
  );

  const handleRegenerate = (message: Message, customUserMessage?: string): void => {
    if (!currentChat || !isConnected) {
      showNotification('error', 'Нет соединения с сервером');
      return;
    }

    if (message.multiLLMResponses && message.multiLLMResponses.length > 0) {
      showNotification('info', 'Используйте «Перегенерировать» под нужной моделью');
      return;
    }

    // Находим индекс текущего сообщения
    const messageIndex = messages.findIndex(m => m.id === message.id);
    if (messageIndex === -1) {
      showNotification('error', 'Сообщение не найдено');
      return;
    }

    // Ищем предыдущее сообщение пользователя
    let userMessage: Message | null = null;
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMessage = messages[i];
        break;
      }
    }

    if (!userMessage) {
      showNotification('error', 'Не найдено предыдущее сообщение пользователя');
      return;
    }
    
    // Используем customUserMessage если передан, иначе берем из userMessage
    const userMessageContent = customUserMessage || userMessage.content;

    // Сохраняем текущий ответ в альтернативные ответы
    const currentContent = message.content;
    let existingAlternatives = message.alternativeResponses || [];
    const currentIndex = message.currentResponseIndex ?? 0;
    
    // Если альтернативных ответов еще нет, инициализируем массив с текущим ответом
    if (existingAlternatives.length === 0) {
      existingAlternatives = [currentContent];
    } else {
      // Обновляем текущий вариант в альтернативных ответах, если он изменился
      const updated = [...existingAlternatives];
      if (currentIndex < updated.length) {
        // Обновляем текущий вариант
        updated[currentIndex] = currentContent;
      } else {
        // Если индекс выходит за границы, добавляем текущий ответ
        updated.push(currentContent);
      }
      existingAlternatives = updated;
    }
    
    // Устанавливаем новый индекс для нового ответа (будет последним)
    const newIndex = existingAlternatives.length;
    
    // Добавляем пустое место для нового ответа (будет заполнено при генерации)
    const updatedAlternatives = [...existingAlternatives, ''];
    
    // Обновляем сообщение с альтернативными ответами и новым индексом
    // Не обнуляем content, оставляем текущий
    updateMessage(
      currentChat.id,
      message.id,
      currentContent, // Оставляем текущий контент, не обнуляем
      true, // isStreaming - начинаем стриминг
      undefined, // multiLLMResponses
      updatedAlternatives,
      newIndex // Новый индекс для нового ответа
    );

    // Вызываем перегенерацию без создания нового сообщения пользователя
    // Передаем updatedAlternatives и newIndex для сохранения в SocketContext ref
    regenerateResponse(userMessageContent, message.id, currentChat.id, updatedAlternatives, newIndex);
  };

  // Функция для открытия диалога редактирования
  const handleEditClick = (message: Message): void => {
    setEditingMessage(message);
    setEditingMultiLlmSlotIndex(null);
    setEditText(message.content);
    setEditDialogOpen(true);
  };

  // Функция для сохранения отредактированного сообщения
  const handleSaveEdit = async (): Promise<void> => {
    if (!editingMessage || !currentChat || !editText.trim()) {
      return;
    }

    const trimmedContent = editText.trim();

    if (editingMultiLlmSlotIndex !== null && editingMessage.multiLLMResponses) {
      const idx = editingMultiLlmSlotIndex;
      const next = editingMessage.multiLLMResponses.map((r, i) =>
        i === idx
          ? {
              ...r,
              content: trimmedContent,
              alternativeResponses: undefined,
              currentResponseIndex: undefined,
            }
          : r,
      );
      updateMessage(currentChat.id, editingMessage.id, undefined, false, next);
      showNotification('success', 'Ответ модели обновлён');
      setEditDialogOpen(false);
      setEditingMessage(null);
      setEditingMultiLlmSlotIndex(null);
      setEditText('');
      return;
    }
    
    // Обновляем сообщение в локальном состоянии
    updateMessage(currentChat.id, editingMessage.id, trimmedContent);
    
    // Сохраняем в MongoDB через API
    try {
      const response = await fetch(
        `${getApiUrl(API_ENDPOINTS.UPDATE_MESSAGE)}/${currentChat.id}/${editingMessage.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            content: trimmedContent,
            old_content: editingMessage.content  // Передаем старое содержимое для поиска
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errorData.detail || 'Ошибка при сохранении сообщения');
      }
      
      showNotification('success', 'Сообщение обновлено и сохранено в базе данных');
    } catch (error) {
      
      showNotification('warning', 'Сообщение обновлено локально, но не сохранено в базе данных');
    }
    
    setEditDialogOpen(false);
    setEditingMessage(null);
    setEditText('');
  };

  // Функция для сохранения и отправки на повторную генерацию (только для сообщений пользователя)
  const handleSaveAndSend = async (): Promise<void> => {
    if (!editingMessage || !currentChat || !editText.trim() || !isConnected) {
      if (!isConnected) {
        showNotification('error', 'Нет соединения с сервером');
      }
      return;
    }

    const trimmedContent = editText.trim();
    
    // Обновляем сообщение пользователя в локальном состоянии
    updateMessage(currentChat.id, editingMessage.id, trimmedContent);
    
    // Сохраняем в MongoDB через API
    try {
      const response = await fetch(
        `${getApiUrl(API_ENDPOINTS.UPDATE_MESSAGE)}/${currentChat.id}/${editingMessage.id}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            content: trimmedContent,
            old_content: editingMessage.content  // Передаем старое содержимое для поиска
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errorData.detail || 'Ошибка при сохранении сообщения');
      }
    } catch (error) {
      
      showNotification('warning', 'Сообщение обновлено локально, но не сохранено в базе данных');
    }
    
    // Находим следующее сообщение LLM после этого сообщения пользователя
    const messageIndex = messages.findIndex(m => m.id === editingMessage.id);
    if (messageIndex !== -1) {
      // Ищем следующее сообщение LLM
      for (let i = messageIndex + 1; i < messages.length; i++) {
        if (messages[i].role === 'assistant') {
          // Найдено сообщение LLM - перегенерируем его с обновленным текстом пользователя
          handleRegenerate(messages[i], trimmedContent);
          break;
        }
      }
    }
    
    setEditDialogOpen(false);
    setEditingMessage(null);
    setEditText('');
    showNotification('success', 'Сообщение обновлено и отправлено на перегенерацию');
  };

  // Функция для отмены редактирования
  const handleCancelEdit = (): void => {
    setEditDialogOpen(false);
    setEditingMessage(null);
    setEditingMultiLlmSlotIndex(null);
    setEditText('');
  };

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Получаем данные пользователя
  const { user } = useAuth();
  
  // Функция для определения приветствия по времени суток (Московское время)
  const getGreeting = (): string => {
    const now = new Date();
    const moscowTime = new Date(now.toLocaleString("en-US", {timeZone: "Europe/Moscow"}));
    const hour = moscowTime.getHours();
    
    // Определяем имя пользователя для приветствия
    const userName = user?.full_name || user?.username || "";
    const nameToShow = userName ? `, ${userName}` : "";
    
    if (hour >= 5 && hour < 12) {
      return `Доброе утро${nameToShow}`;
    } else if (hour >= 12 && hour < 18) {
      return `Добрый день${nameToShow}`;
    } else if (hour >= 18 && hour < 22) {
      return `Добрый вечер${nameToShow}`;
    } else {
      return `Доброй ночи${nameToShow}`;
    }
  };

  // ================================
  // TTS ДЛЯ КНОПКИ "ПРОЧЕСТЬ ВСЛУХ"
  // ================================

  const synthesizeSpeech = async (text: string) => {
    if (!text.trim()) return;
    if (currentAudioRef.current) {
      currentAudioRef.current.pause(); currentAudioRef.current.src = ''; currentAudioRef.current = null;
    }
    setIsSpeaking(true);
    try {
      const response = await fetch(getApiUrl(API_ENDPOINTS.VOICE_SYNTHESIZE), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          voice_id: voiceSettingsTTS.voice_id,
          voice_speaker: voiceSettingsTTS.voice_speaker,
          speech_rate: voiceSettingsTTS.speech_rate,
        }),
      });
      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        currentAudioRef.current = audio;
        audio.onended = () => {
          setIsSpeaking(false); URL.revokeObjectURL(audioUrl); currentAudioRef.current = null;
        };
        audio.onerror = () => {
          setIsSpeaking(false); showNotification('error', 'Ошибка воспроизведения речи');
          URL.revokeObjectURL(audioUrl); currentAudioRef.current = null;
        };
        await audio.play();
      } else {
        setIsSpeaking(false);
        showNotification('error', 'Ошибка синтеза речи');
      }
    } catch {
      setIsSpeaking(false);
      showNotification('error', 'Ошибка синтеза речи');
    }
  };

  // ================================
  // ФУНКЦИИ РАБОТЫ С ДОКУМЕНТАМИ
  // ================================

  const handleFileUpload = async (file: File): Promise<void> => {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'text/plain',
      'image/jpeg',
      'image/jpg',
      'image/png',
      'image/webp',
    ];

    if (!allowedTypes.includes(file.type)) {
      showNotification('error', 'Поддерживаются только файлы PDF, Word (.docx), Excel (.xlsx), TXT и изображения (JPG, PNG, WebP)');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      showNotification('error', 'Размер файла не должен превышать 50MB');
      return;
    }

    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`${getApiUrl('/api/documents/upload')}`, {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        await response.json();
        showNotification('success', `Документ "${file.name}" успешно загружен. Теперь вы можете задать вопрос по нему в чате.`);
        
        // Обновляем список документов с бэкенда (это основной источник истины)
        try {
          const docsResponse = await fetch(getApiUrl('/api/documents'));
          if (docsResponse.ok) {
            const docsResult: any = await docsResponse.json();
            if (docsResult.success && docsResult.documents) {
              const files = docsResult.documents.map((filename: string) => ({
                name: filename,
                size: 0,
                type: 'application/octet-stream',
                uploadDate: new Date().toISOString(),
              }));
              setUploadedFiles(files);
              
            } else {
              // Если список пустой, добавляем загруженный файл
              setUploadedFiles(prev => {
                const exists = prev.some(f => f.name === file.name);
                if (!exists) {
                  return [...prev, {
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    uploadDate: new Date().toISOString(),
                  }];
                }
                return prev;
              });
            }
          } else {
            // Fallback: добавляем файл в список, если не удалось получить список с бэкенда
            setUploadedFiles(prev => {
              const exists = prev.some(f => f.name === file.name);
              if (!exists) {
                return [...prev, {
                  name: file.name,
                  size: file.size,
                  type: file.type,
                  uploadDate: new Date().toISOString(),
                }];
              }
              return prev;
            });
          }
        } catch (error) {
          
          // Fallback: добавляем файл в список, если произошла ошибка
          setUploadedFiles(prev => {
            const exists = prev.some(f => f.name === file.name);
            if (!exists) {
              return [...prev, {
                name: file.name,
                size: file.size,
                type: file.type,
                uploadDate: new Date().toISOString(),
              }];
            }
            return prev;
          });
        }
        
        // Закрываем диалог загрузки документов после успешной загрузки
        setShowDocumentDialog(false);
        
        // Очищаем input файла, чтобы можно было повторно загрузить тот же файл
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        
      } else {
        const error = await response.json();
        showNotification('error', error.detail || 'Ошибка при загрузке документа');
      }
    } catch (error) {
      
      showNotification('error', 'Ошибка при загрузке файла');
            } finally {
      setIsUploading(false);
    }
  };

  const handleFileDelete = async (fileName: string): Promise<void> => {
    try {
      const response = await fetch(`${getApiUrl(`/api/documents/${encodeURIComponent(fileName)}`)}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        const result: any = await response.json();
        // Обновляем список документов с бэкенда
        if (result.remaining_documents) {
          const files = result.remaining_documents.map((filename: string) => ({
            name: filename,
            size: 0,
            type: 'application/octet-stream',
            uploadDate: new Date().toISOString(),
          }));
          setUploadedFiles(files);
        } else {
          setUploadedFiles(prev => prev.filter(file => file.name !== fileName));
        }
        showNotification('success', `Документ "${fileName}" удален`);
        
        // Очищаем input файла после удаления
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        
      } else {
        const error = await response.json();
        showNotification('error', error.detail || 'Ошибка при удалении документа');
      }
    } catch (error) {
      
      showNotification('error', 'Ошибка при удалении файла');
    }
  };

  const handleDragOver = (e: React.DragEvent): void => {
    if (!dataTransferHasFiles(e.dataTransfer)) {
      return;
    }
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent): void => {
    if (!dataTransferHasFiles(e.dataTransfer)) {
      return;
    }
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent): void => {
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) {
      return;
    }
    e.preventDefault();
    handleFileUpload(files[0]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
    // Очищаем input файла, чтобы можно было повторно загрузить тот же файл
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleGenerateReport = async (): Promise<void> => {
    if (uploadedFiles.length === 0) {
      showNotification('warning', 'Нет загруженных документов для генерации отчета');
      return;
    }

    try {
      showNotification('info', 'Генерация отчета...');
      
      // Скачиваем отчет напрямую
      const response = await fetch(getApiUrl('/api/documents/report/download'));
      
      if (response.ok) {
        // Получаем blob для скачивания
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Получаем имя файла из заголовка Content-Disposition или используем дефолтное
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'confidence_report.xlsx'; // Дефолтное расширение - .xlsx
        if (contentDisposition) {
          // Пробуем разные форматы Content-Disposition
          // Формат: filename*=UTF-8''filename.xlsx
          const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
          if (utf8Match) {
            filename = decodeURIComponent(utf8Match[1]);
          } else {
            // Формат: filename="filename.xlsx" или filename=filename.xlsx
            const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (filenameMatch) {
              filename = filenameMatch[1].replace(/['"]/g, '');
            }
          }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('success', 'Отчет успешно сгенерирован и скачан');
      } else {
        const error = await response.json();
        showNotification('error', error.detail || 'Ошибка при генерации отчета');
      }
    } catch (error) {
      
      showNotification('error', 'Ошибка при генерации отчета');
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>): void => {
    setGearToolsPanel('main');
    setAnchorEl(chatInputToolsAnchorRef.current ?? event.currentTarget);
    const shell = chatInputToolsAnchorRef.current;
    if (shell) {
      const rect = shell.getBoundingClientRect();
      setGearToolsMenuWidthPx(Math.round(rect.width));
      setGearToolsPaperHeightPx(getChatGearMenuPaperHeightPx(rect.top));
    } else {
      setGearToolsMenuWidthPx(null);
      setGearToolsPaperHeightPx(null);
    }
  };

  const handleMenuClose = (): void => {
    setGearToolsPanel('main');
    setAnchorEl(null);
    setGearToolsMenuWidthPx(null);
    setGearToolsPaperHeightPx(null);
  };

  const handleTranscriptionFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    const file = files[0];
    const allowedTypes = [
      'audio/mpeg', 'audio/wav', 'audio/m4a', 'audio/aac', 'audio/flac',
      'video/mp4', 'video/avi', 'video/mov', 'video/mkv', 'video/webm',
    ];
    const isValidType = allowedTypes.some(type =>
      file.type.includes(type.split('/')[1]) || file.name.toLowerCase().includes(type.split('/')[1])
    );
    if (!isValidType) {
      showNotification('error', 'Поддерживаются только аудио и видео файлы');
      e.target.value = '';
      return;
    }
    if (file.size > 5 * 1024 * 1024 * 1024) {
      showNotification('error', 'Размер файла не должен превышать 5GB');
      e.target.value = '';
      return;
    }
    e.target.value = '';
    startFileTranscriptionFromSidebar(file);
  };

  /** Запуск транскрибации файла из правого сайдбара (без открытия модалки). */
  const startFileTranscriptionFromSidebar = async (file: File) => {
    setIsTranscribing(true);
    const currentId = `transcribe_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setTranscriptionId(currentId);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('request_id', currentId);
      const response = await fetch(getApiUrl(API_ENDPOINTS.TRANSCRIBE_UPLOAD), {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        if (response.status === 499) {
          const errorData = await response.json().catch(() => ({ detail: 'Транскрибация была остановлена' }));
          throw Object.assign(new Error(errorData.detail || 'Транскрибация была остановлена'), { status: 499 });
        }
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка при транскрибации' }));
        throw new Error(errorData.detail || 'Ошибка при транскрибации');
      }
      const result = await response.json();
      if (result.success) {
        if (result.transcription_id) setTranscriptionId(result.transcription_id);
        const text = result.transcription ?? '';
        setTranscriptionResult(text);
        showNotification('success', 'Транскрибация завершена');
      } else {
        showNotification('error', result.message || 'Ошибка при транскрибации');
      }
    } catch (err: any) {
      if (err?.status === 499 || err?.message?.includes('остановлена')) {
        showNotification('info', 'Транскрибация была остановлена');
      } else {
        showNotification('error', err?.message || 'Ошибка при отправке файла');
      }
    } finally {
      setIsTranscribing(false);
      setTranscriptionId(null);
    }
  };

  const handleStopTranscriptionFromSidebar = async () => {
    if (!transcriptionId) return;
    try {
      const response = await fetch(getApiUrl('/api/transcribe/stop'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcription_id: transcriptionId }),
      });
      const result = await response.json();
      if (result.success) {
        showNotification('info', 'Транскрибация остановлена');
      } else {
        showNotification('error', result.message || 'Ошибка остановки');
      }
    } catch {
      showNotification('error', 'Ошибка при остановке транскрибации');
    }
    setTranscriptionId(null);
    setIsTranscribing(false);
  };

  /** Транскрибация YouTube из правого сайдбара. */
  const startYouTubeTranscriptionFromSidebar = async () => {
    const url = transcriptionYoutubeUrl.trim();
    if (!url) {
      showNotification('warning', 'Введите URL YouTube видео');
      return;
    }
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
      showNotification('error', 'Некорректный URL YouTube');
      return;
    }
    setIsTranscribing(true);
    try {
      const response = await fetch(getApiUrl(API_ENDPOINTS.TRANSCRIBE_YOUTUBE), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const result = await response.json();
      if (result.success) {
        setTranscriptionResult(result.transcription ?? '');
        showNotification('success', 'Транскрибация YouTube завершена');
      } else {
        showNotification('error', result.message || 'Ошибка при транскрибации YouTube');
      }
    } catch {
      showNotification('error', 'Ошибка при обработке YouTube URL');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleClearChat = (): void => {
    if (currentChat) {
      clearMessages(currentChat.id);
    }
    handleMenuClose();
  };

  const handleStopGeneration = (): void => {
    stopGeneration();
    showNotification('info', 'Генерация остановлена');
  };

  // ================================
  // ФУНКЦИИ НАВИГАЦИИ ПО СООБЩЕНИЯМ
  // ================================

  const scrollToMessage = useCallback((index: number) => {
    const messageElement = messageRefs.current[index];
    if (messageElement) {
      messageElement.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, []);

  // ================================
  // ФУНКЦИИ ДЛЯ РЕЖИМА "ПОДЕЛИТЬСЯ"
  // ================================

  const handleEnterShareMode = () => {
    setShareMode(true);
    setSelectedMessages(new Set());
  };

  const handleExitShareMode = () => {
    setShareMode(false);
    setSelectedMessages(new Set());
  };

  const handleToggleMessage = (userMsgId: string, assistantMsgId: string) => {
    const newSelected = new Set(selectedMessages);
    
    if (newSelected.has(userMsgId) && newSelected.has(assistantMsgId)) {
      // Если оба выбраны, снимаем выбор
      newSelected.delete(userMsgId);
      newSelected.delete(assistantMsgId);
    } else {
      // Выбираем оба
      newSelected.add(userMsgId);
      newSelected.add(assistantMsgId);
    }
    
    setSelectedMessages(newSelected);
  };

  const handleSelectAll = () => {
    // Получаем все пары вопрос-ответ
    const allPairs: string[] = [];
    for (let i = 0; i < messages.length - 1; i++) {
      if (messages[i].role === 'user' && messages[i + 1].role === 'assistant') {
        allPairs.push(messages[i].id, messages[i + 1].id);
      }
    }
    
    if (selectedMessages.size === allPairs.length) {
      // Если все выбраны, снимаем выбор
      setSelectedMessages(new Set());
    } else {
      // Выбираем все
      setSelectedMessages(new Set(allPairs));
    }
  };

  const handleCreateShareLink = () => {
    if (selectedMessages.size === 0) {
      showNotification('error', 'Выберите хотя бы одно сообщение');
      return;
    }
    // Открываем диалог подтверждения
    setShareDialogOpen(true);
  };

  const createShareLinkConfirmed = async (): Promise<string> => {
    try {
      // Фильтруем выбранные сообщения в правильном порядке
      const selectedMessagesArray = messages.filter(msg => selectedMessages.has(msg.id));

      // Получаем токен для авторизации
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(getApiUrl('/api/share/create'), {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          messages: selectedMessagesArray,
        }),
      });

      if (!response.ok) {
        throw new Error('Ошибка создания публичной ссылки');
      }

      const data = await response.json();
      const fullUrl = `${window.location.origin}/share/${data.share_id}`;
      
      return fullUrl;
    } catch (err) {
      showNotification('error', err instanceof Error ? err.message : 'Произошла ошибка');
      throw err;
    }
  };

  const handleCloseShareDialog = () => {
    setShareDialogOpen(false);
    // Выходим из режима выбора после закрытия диалога
    handleExitShareMode();
  };

  // ================================
  // (MessageCard определён на уровне модуля, выше UnifiedChatPage)
  // ================================

  // NOTE: MessageCard теперь определён на уровне модуля (вне UnifiedChatPage).
  // Это предотвращает пересоздание типа компонента при каждом рендере родителя
  // (что вызывало полный unmount/remount Monaco Editor при каждом нажатии клавиши).


  // ================================
  // ДИАЛОГИ
  // ================================

  const DocumentDialog = (): React.ReactElement => (
    <Dialog
      open={showDocumentDialog}
      onClose={() => setShowDocumentDialog(false)}
      maxWidth="md"
      fullWidth
      TransitionComponent={undefined}
      transitionDuration={0}
    >
      <DialogTitle>Загрузка документов</DialogTitle>
      <DialogContent>
        <Box
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          sx={{
            border: '2px dashed',
            borderColor: isDragging ? 'primary.main' : 'divider',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            bgcolor: isDragging ? 'action.hover' : 'background.paper',
            cursor: 'pointer',
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" sx={{ mb: 1 }}>
            Перетащите файл сюда или нажмите для выбора
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Поддерживаются PDF, Word, Excel, текстовые файлы и изображения (JPG, PNG, WebP) до 50MB
          </Typography>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png,.webp"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </Box>
        

      </DialogContent>
      <DialogActions>
        <Button onClick={() => setShowDocumentDialog(false)}>
          Закрыть
        </Button>
      </DialogActions>
    </Dialog>
  );

  // ================================
  // ОСНОВНОЙ РЕНДЕР
  // ================================

  // Обновляем dataRef перед каждым рендером, чтобы MessageCard всегда видел актуальные callback-и
  // (MessageCard мемоизирован и не ре-рендерится при изменении inputMessage,
  //  но его onClick-обработчики через dataRef.current всегда получают свежие функции)
  messageCardDataRef.current = {
    handleSendMessageFromRenderer,
    handleCopyMessage,
    handleEditClick,
    handleRegenerate,
    handleEditMultiLlmColumn,
    handleRegenerateMultiLlmColumn,
    synthesizeSpeech,
    handleEnterShareMode,
    handleToggleMessage,
    updateMessage,
    formatTimestamp,
    currentChatId: currentChat?.id,
    messageRefs,
  };

  const renderMultiLlmModelToolbar = (): React.ReactNode => {
    if (!isMultiLlmMode) return null;
    const barMaxWidth = interfaceSettings.widescreenMode ? '100%' : messages.length === 0 ? '800px' : '1000px';
    const barPx =
      interfaceSettings.chatInputStyle === 'classic' ? 0 : interfaceSettings.widescreenMode ? 4 : 2;

    const displayModelLabel = (val: string): string => {
      if (!val) return '';
      const row = availableModels.find((x) => availableModelSelectValue(x) === val);
      return row?.name ?? val.replace('llm-svc://', '').split('/').pop() ?? val;
    };

    const menuWindowId = multiLlmModelMenu?.windowId ?? null;
    const menuAnchor = multiLlmModelMenu?.anchorEl ?? null;
    const menuOpen = Boolean(menuAnchor);
    const menuWin = menuWindowId ? modelWindows.find((w) => w.id === menuWindowId) : undefined;
    const selectedRowBg = isDarkMode ? DROPDOWN_ITEM_HOVER_BG_DARK : DROPDOWN_ITEM_HOVER_BG_LIGHT;
    const menuItemMuted = isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.87)';

    return (
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 1,
          width: '100%',
          maxWidth: barMaxWidth,
          mx: 'auto',
          px: barPx,
          mb: 1,
          position: 'relative',
          zIndex: workZoneAnimated ? 2 : undefined,
        }}
      >
        {modelWindows.map((window) => (
          <Box
            key={window.id}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              flex: '1 1 160px',
              minWidth: { xs: '100%', sm: 160 },
              maxWidth: { sm: 280 },
            }}
          >
            <FormControl
              variant="outlined"
              fullWidth
              size="small"
              required
              sx={multiLlmModelFieldSx}
              disabled={availableModels.length === 0 || hasActiveChatStreaming}
            >
              <InputLabel htmlFor={`multi-llm-model-${window.id}`}>Модель</InputLabel>
              <OutlinedInput
                id={`multi-llm-model-${window.id}`}
                label="Модель"
                value={displayModelLabel(window.selectedModel)}
                readOnly
                placeholder="Выберите модель"
                onClick={(e) => {
                  if (availableModels.length === 0 || hasActiveChatStreaming) return;
                  const root = (e.currentTarget as HTMLElement).closest('.MuiOutlinedInput-root') as HTMLElement | null;
                  if (!root) return;
                  setMultiLlmModelMenu((prev) =>
                    prev?.windowId === window.id && prev.anchorEl === root ? null : { windowId: window.id, anchorEl: root },
                  );
                }}
                endAdornment={
                  <InputAdornment position="end">
                    <ExpandMoreIcon
                      sx={{
                        ...DROPDOWN_CHEVRON_SX,
                        transform:
                          multiLlmModelMenu?.windowId === window.id && Boolean(multiLlmModelMenu?.anchorEl)
                            ? 'rotate(180deg)'
                            : 'none',
                      }}
                    />
                  </InputAdornment>
                }
              />
            </FormControl>
            {modelWindows.length > 1 ? (
              <Tooltip title="Убрать колонку">
                <span>
                  <IconButton
                    size="small"
                    onClick={() => removeModelWindow(window.id)}
                    color="error"
                    sx={{ flexShrink: 0 }}
                    disabled={hasActiveChatStreaming}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
            ) : null}
          </Box>
        ))}
        <Popover
          open={menuOpen}
          anchorEl={menuAnchor}
          onClose={() => setMultiLlmModelMenu(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          slotProps={{
            paper: {
              sx: {
                ...dropdownPanelSx,
                mt: DROPDOWN_PAPER_MARGIN_TOP,
                minWidth: DROPDOWN_PAPER_MIN_WIDTH_PX,
                width: menuAnchor
                  ? `${menuAnchor.getBoundingClientRect().width}px`
                  : DROPDOWN_PAPER_DEFAULT_WIDTH_PX,
              },
            },
          }}
        >
          <Box sx={{ py: 0.5, maxHeight: 320, overflow: 'auto', ...SIDEBAR_HIDE_SCROLLBAR_SX }}>
            {availableModels.length === 0 ? (
              <Typography
                sx={{
                  px: 1.5,
                  py: 1,
                  fontSize: MENU_ACTION_TEXT_SIZE,
                  color: isDarkMode ? 'rgba(255,255,255,0.45)' : 'text.secondary',
                }}
              >
                Загрузка моделей...
              </Typography>
            ) : (
              <>
                <Box
                  onClick={() => {
                    if (menuWindowId) {
                      handleModelSelect(menuWindowId, '');
                      setMultiLlmModelMenu(null);
                    }
                  }}
                  sx={{
                    ...dropdownItemSx,
                    color: !menuWin?.selectedModel ? (isDarkMode ? '#fff' : 'rgba(0,0,0,0.95)') : menuItemMuted,
                    fontWeight: !menuWin?.selectedModel ? 600 : 400,
                    bgcolor: !menuWin?.selectedModel ? selectedRowBg : 'transparent',
                  }}
                >
                  Не выбрано
                </Box>
                {availableModels
                  .filter((m) => {
                    const k = availableModelSelectValue(m);
                    const isSelectedElsewhere = modelWindows.some(
                      (w) => w.id !== menuWindowId && w.selectedModel === k,
                    );
                    return !isSelectedElsewhere || menuWin?.selectedModel === k;
                  })
                  .map((model) => {
                    const k = availableModelSelectValue(model);
                    const sel = menuWin?.selectedModel === k;
                    return (
                      <Box
                        key={k}
                        onClick={() => {
                          if (menuWindowId) {
                            handleModelSelect(menuWindowId, k);
                            setMultiLlmModelMenu(null);
                          }
                        }}
                        sx={{
                          ...dropdownItemSx,
                          color: sel ? (isDarkMode ? '#fff' : 'rgba(0,0,0,0.95)') : menuItemMuted,
                          fontWeight: sel ? 600 : 400,
                          bgcolor: sel ? selectedRowBg : 'transparent',
                        }}
                      >
                        {model.name}
                      </Box>
                    );
                  })}
              </>
            )}
          </Box>
        </Popover>
        {modelWindows.length < 4 ? (
          <Tooltip title="Добавить модель (максимум 4)">
            <span>
              <IconButton
                onClick={addModelWindow}
                sx={{
                  flexShrink: 0,
                  width: 40,
                  height: 40,
                  borderRadius: '10px',
                  color: 'primary.main',
                  bgcolor: isDarkMode ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.9)',
                  border: isDarkMode ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.12)',
                  '&:hover': {
                    bgcolor: isDarkMode ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,1)',
                  },
                }}
                disableRipple
                disabled={hasActiveChatStreaming}
              >
                <AddIcon sx={{ fontSize: '1.2rem' }} />
              </IconButton>
            </span>
          </Tooltip>
        ) : null}
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Основной контент */}
      <Box 
        className="fullscreen-chat" 
        sx={{ 
          flexGrow: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          marginRight: rightSidebarHidden ? 0 : (rightSidebarOpen ? 0 : '-64px'),
          transition: 'margin-right 0.3s ease',
          pt: 8,
          backgroundColor: workZoneBgColor,
          color: isDarkMode ? 'white' : '#333',
          position: 'relative',
        }}
      >
      {workZoneMode === 'starry' ? <WorkZoneStarrySky isDarkMode={isDarkMode} /> : null}
      {workZoneMode === 'snowfall' ? <WorkZoneSnowfall isDarkMode={isDarkMode} /> : null}
      {/* Заголовок с информацией о проекте и модели */}
      {currentChat && project && (
        <Box sx={{ 
          position: 'absolute',
          top: 16,
          left: sidebarOpen ? 16 : 80,
          zIndex: 1200,
          transition: 'left 0.3s ease',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 500,
              color: isDarkMode ? 'white' : '#333',
              cursor: 'pointer',
              '&:hover': {
                opacity: 0.8,
              },
              fontSize: '0.95rem',
            }}
            onClick={() => navigate(`/project/${project.id}`)}
          >
            {project.name}
          </Typography>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 400,
              color: isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
              fontSize: '0.95rem',
            }}
          >
            /
          </Typography>
          {modelSelectorMode === 'workspace' && (
            <ModelSelector 
              isDarkMode={isDarkMode}
              onModelSelect={(modelPath) => {
                
              }}
            />
          )}
          {modelSelectorMode === 'workspace_agent' && (
            <AgentSelector
              isDarkMode={isDarkMode}
              triggerMaxWidth={180}
              onModelSelect={() => {}}
            />
          )}
          {(modelSelectorMode === 'workspace' || modelSelectorMode === 'workspace_agent') && (
            <Tooltip title="Сравнение моделей">
              <span>
                <IconButton
                  onClick={() => {
                    void handleToggleMultiLlmMode();
                  }}
                  disabled={
                    !agentStatus?.is_initialized ||
                    !isConnected ||
                    state.isLoading ||
                    hasActiveChatStreaming
                  }
                  sx={multiLlmModeToggleIconButtonSx}
                >
                  <MultiLlmModeToggleIcon isDarkMode={isDarkMode} />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>
      )}
      
      {/* Селектор моделей - на одном уровне с кнопкой сворачивания боковой панели */}
      {/* Когда панель развернута - ближе к панели, когда закрыта - дальше от узкой полоски */}
      {(!currentChat || !project) && (
        <Box sx={{ 
          position: 'absolute',
          top: 16,
          left: sidebarOpen ? 16 : 80,
          zIndex: 1200,
          transition: 'left 0.3s ease',
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
        }}>
          {modelSelectorMode === 'workspace' && (
            <ModelSelector 
              isDarkMode={isDarkMode}
              onModelSelect={(modelPath) => {
                
              }}
            />
          )}
          {modelSelectorMode === 'workspace_agent' && (
            <AgentSelector
              isDarkMode={isDarkMode}
              triggerMaxWidth={180}
              onModelSelect={() => {}}
            />
          )}
          {(modelSelectorMode === 'workspace' || modelSelectorMode === 'workspace_agent') && (
            <Tooltip title="Сравнение моделей">
              <span>
                <IconButton
                  onClick={() => {
                    void handleToggleMultiLlmMode();
                  }}
                  disabled={
                    !agentStatus?.is_initialized ||
                    !isConnected ||
                    state.isLoading ||
                    hasActiveChatStreaming
                  }
                  sx={multiLlmModeToggleIconButtonSx}
                >
                  <MultiLlmModeToggleIcon isDarkMode={isDarkMode} />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>
      )}


      {/* Область сообщений */}
      <Box
        className="chat-messages-area"
                 sx={{
           border: isDragging ? '2px dashed' : 'none',
           borderColor: isDragging ? 'primary.main' : 'transparent',
           bgcolor: isDragging ? 'action.hover' : 'transparent',
           position: 'relative',
           zIndex: workZoneAnimated ? 1 : undefined,
           ...(messages.length === 0
             ? {
                 flex: '0 0 auto',
                 minHeight: 0,
                 height: 0,
                 overflow: 'hidden',
                 p: 0,
               }
             : {
                 minHeight: '60vh',
                 justifyContent: 'flex-start',
                 py: 4,
               }),
           display: 'flex',
           flexDirection: 'column',
           alignItems: 'center',
           // Селектор моделей в правом верхнем углу
           '&::before': {
             content: '""',
             position: 'absolute',
             top: 16,
             right: 16,
             zIndex: 10,
           },
           // Кастомные стили для скроллбара
           '&::-webkit-scrollbar': {
             width: '8px',
           },
           '&::-webkit-scrollbar-track': {
             background: isDarkMode 
               ? 'rgba(30, 30, 30, 0.5)' 
               : 'rgba(245, 245, 245, 0.5)',
             borderRadius: '4px',
           },
           '&::-webkit-scrollbar-thumb': {
             background: isDarkMode 
               ? 'rgba(45, 45, 45, 0.8)' 
               : 'rgba(200, 200, 200, 0.8)',
             borderRadius: '4px',
             '&:hover': {
               background: isDarkMode 
                 ? 'rgba(60, 60, 60, 0.9)' 
                 : 'rgba(180, 180, 180, 0.9)',
             },
           },
           // Для Firefox
           scrollbarWidth: 'thin',
           scrollbarColor: isDarkMode 
             ? 'rgba(45, 45, 45, 0.8) rgba(30, 30, 30, 0.5)' 
             : 'rgba(200, 200, 200, 0.8) rgba(245, 245, 245, 0.5)',
         }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
          {messages.length === 0 ? (
            null
          ) : (
            <Box sx={{ 
              width: '100%', 
              maxWidth: interfaceSettings.widescreenMode ? '100%' : '1000px', 
              mx: 'auto',
              px: interfaceSettings.widescreenMode ? 4 : 2,
            }}>
              {messages.map((message, index) => {
                const isUserMsg = message.role === 'user';
                const isPairStart = isUserMsg && index < messages.length - 1 && messages[index + 1].role === 'assistant';
                const isSelected = isPairStart &&
                  selectedMessages.has(message.id) &&
                  selectedMessages.has(messages[index + 1].id);
                const nextMessageId = isPairStart ? messages[index + 1].id : null;
                return (
                  <MessageCard
                    key={message.id || index}
                    message={message}
                    index={index}
                    isPairStart={isPairStart}
                    isSelected={isSelected}
                    nextMessageId={nextMessageId}
                    shareMode={shareMode}
                    isSpeaking={isSpeaking}
                    isDarkMode={isDarkMode}
                    interfaceSettings={interfaceSettings}
                    username={user?.username}
                    dataRef={messageCardDataRef}
                  />
                );
              })}
              
              {/* Индикатор размышления - показывается только до начала потоковой генерации, сразу после сообщений */}
              {chatAwaitingTokens && (
                <Box sx={{ 
                  width: '100%', 
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: interfaceSettings.leftAlignMessages ? 'flex-start' : 'flex-start',
                  mb: 1.5,
                }}>
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      maxWidth: interfaceSettings.widescreenMode ? '100%' : '75%',
                      minWidth: '180px',
                    }}
                  >
                    <Card
                      sx={{
                        backgroundColor: isDarkMode ? 'background.paper' : '#f8f9fa',
                        color: isDarkMode ? 'text.primary' : '#333',
                        boxShadow: isDarkMode 
                          ? '0 2px 8px rgba(0, 0, 0, 0.15)' 
                          : '0 2px 8px rgba(0, 0, 0, 0.1)',
                        width: '100%',
                      }}
                    >
                      <CardContent sx={{ p: 1.2, pb: 0.8 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.3 }}>
                          <Avatar
                            src="/astra.png"
                            sx={{
                              width: 24,
                              height: 24,
                              mr: 1,
                              bgcolor: 'transparent',
                              position: 'relative',
                              '&::before': {
                                content: '""',
                                position: 'absolute',
                                top: '-2px',
                                left: '-2px',
                                right: '-2px',
                                bottom: '-2px',
                                borderRadius: '50%',
                                background: 'radial-gradient(circle, rgba(33, 150, 243, 0.3) 0%, transparent 70%)',
                                animation: 'thinking-glow 2s ease-in-out infinite',
                                '@keyframes thinking-glow': {
                                  '0%, 100%': { 
                                    opacity: 0.3,
                                    transform: 'scale(1)',
                                  },
                                  '50%': { 
                                    opacity: 0.8,
                                    transform: 'scale(1.3)',
                                  },
                                },
                              },
                              animation: 'thinking 2s ease-in-out infinite',
                            }}
                          />
                          <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.75rem', fontWeight: 500 }}>
                            AstraChat
                          </Typography>
                          <Typography variant="caption" sx={{ ml: 'auto', opacity: 0.6, fontSize: '0.7rem' }}>
                            {new Date().toLocaleTimeString('ru-RU', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </Typography>
                        </Box>
                        
                        <Box sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: 1,
                          minHeight: '24px',
                        }}>
                          <Box sx={{ display: 'flex', gap: 0.5 }}>
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: '#2196f3',
                                animation: 'dot1 1.4s ease-in-out infinite both',
                                '@keyframes dot1': {
                                  '0%, 80%, 100%': { transform: 'scale(0)' },
                                  '40%': { transform: 'scale(1)' },
                                },
                              }}
                            />
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: '#2196f3',
                                animation: 'dot2 1.4s ease-in-out infinite both',
                                animationDelay: '0.2s',
                                '@keyframes dot2': {
                                  '0%, 80%, 100%': { transform: 'scale(0)' },
                                  '40%': { transform: 'scale(1)' },
                                },
                              }}
                            />
                            <Box
                              sx={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                bgcolor: '#2196f3',
                                animation: 'dot3 1.4s ease-in-out infinite both',
                                animationDelay: '0.4s',
                                '@keyframes dot3': {
                                  '0%, 80%, 100%': { transform: 'scale(0)' },
                                  '40%': { transform: 'scale(1)' },
                                },
                              }}
                            />
                          </Box>
                          <Typography variant="body2" sx={{ 
                            color: isDarkMode ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)',
                            fontSize: '0.875rem',
                          }}>
                            думает...
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Box>
                </Box>
              )}
            </Box>
          )}
          <div ref={messagesEndRef} />
          
          {/* Подсказка о перетаскивании в области сообщений */}
          {isDragging && (
            <Box
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                bgcolor: 'rgba(33, 150, 243, 0.9)',
                backdropFilter: 'blur(10px)',
                color: 'white',
                p: 3,
                borderRadius: 2,
                zIndex: 1000,
                textAlign: 'center',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
              }}
            >
              <UploadIcon sx={{ fontSize: 48, mb: 2 }} />
              <Typography variant="h6">
                Отпустите файл для загрузки
              </Typography>
            </Box>
          )}
        </Box>


                 {/* Поле ввода */}
         <Box
           className="chat-input-area"
           data-theme={isDarkMode ? 'dark' : 'light'}
                       sx={{
              position: 'relative',
              zIndex: workZoneAnimated ? 2 : undefined,
              borderColor: isDragging ? 'primary.main' : 'divider',
              bgcolor: isDragging ? 'action.hover' : 'transparent',
              ...(messages.length === 0 && {
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
              }),
            }}
           onDragOver={handleDragOver}
           onDragLeave={handleDragLeave}
           onDrop={handleDrop}
         >
          
                     {messages.length === 0 ? (
                       <Box
                         sx={{
                           flex: 1,
                           minHeight: 0,
                           width: '100%',
                           display: 'flex',
                           flexDirection: 'column',
                           justifyContent: 'center',
                           alignItems: 'center',
                           boxSizing: 'border-box',
                           /* верхний отступ рабочей зоны (pt у fullscreen-chat) смещает математический центр вниз — чуть поднимаем блок */
                           transform: 'translateY(calc(-1 * clamp(20px, 4vh, 72px)))',
                         }}
                       >
                         <Box
                           sx={{
                             textAlign: 'center',
                             mb: 2,
                             maxWidth: interfaceSettings.widescreenMode ? '100%' : '1000px',
                             mx: 'auto',
                             px: interfaceSettings.widescreenMode ? 4 : 2,
                             width: '100%',
                           }}
                         >
                           <Typography
                             variant="h4"
                             sx={{
                               color: isDarkMode ? 'white' : '#333',
                               fontWeight: 600,
                               mb: 1,
                             }}
                           >
                             {getGreeting()}
                           </Typography>
                         </Box>
                         {renderMultiLlmModelToolbar()}
                         <ChatInputBar
                           toolsMenuAnchorRef={chatInputToolsAnchorRef}
                           value={inputMessage}
                           onChange={setInputMessage}
                           onKeyPress={handleKeyPress}
                           onPaste={(e) => handlePaste(e as React.ClipboardEvent<HTMLDivElement>)}
                           placeholder={
                             !isConnected && !isConnecting
                               ? 'Нет соединения с сервером. Запустите backend на порту 8000'
                               : isConnecting
                                 ? 'Подключение к серверу...'
                                 : isMultiLlmMode && !multiLlmHasSelection
                                   ? 'Выберите модели для сравнения (до 4, хотя бы одну)'
                                   : chatAwaitingTokens
                                     ? 'astrachat думает...'
                                     : state.isLoading && hasActiveChatStreaming
                                       ? isMultiLlmMode
                                         ? 'Модели генерируют ответ... Нажмите ⏹️ чтобы остановить'
                                         : 'astrachat генерирует ответ... Нажмите ⏹️ чтобы остановить'
                                       : 'Чем я могу помочь вам сегодня?'
                           }
                           inputDisabled={!isConnected || multiLlmInputBlocked || chatAwaitingTokens}
                           inputRef={inputRef}
                           isDarkMode={isDarkMode}
                           solidWorkZoneBackground={workZoneAnimated}
                           styleVariant={interfaceSettings.chatInputStyle}
                           containerSx={{
                             mt: 0,
                             p: interfaceSettings.chatInputStyle === 'classic' ? 0 : 1.5,
                             borderRadius: interfaceSettings.chatInputStyle === 'classic' ? '28px' : '28px',
                             maxWidth: interfaceSettings.widescreenMode ? '100%' : '800px',
                             width: '100%',
                             mx: 'auto',
                             px: interfaceSettings.chatInputStyle === 'classic' ? 0 : (interfaceSettings.widescreenMode ? 4 : 2),
                           }}
                           fileInputRef={fileInputRef}
                           onAttachClick={() => fileInputRef.current?.click()}
                           onFileSelect={(files) => { if (files?.length) handleFileUpload(files[0]); }}
                           uploadedFiles={uploadedFiles.map(f => ({ name: f.name, type: f.type || 'application/octet-stream' }))}
                           onFileRemove={(file) => handleFileDelete(file.name)}
                           isUploading={isUploading}
                           attachDisabled={isUploading || multiLlmInputBlocked || chatAwaitingTokens}
                           showReportButton={uploadedFiles.length > 0}
                           onReportClick={handleGenerateReport}
                           reportDisabled={isUploading || multiLlmInputBlocked || chatAwaitingTokens}
                           onSettingsClick={handleMenuOpen}
                           settingsDisabled={multiLlmInputBlocked || chatAwaitingTokens}
                           showStopButton={state.isLoading || hasActiveChatStreaming}
                           onStopClick={handleStopGeneration}
                           onSendClick={handleSendMessage}
                           sendDisabled={!inputMessage.trim() || !isConnected || multiLlmInputBlocked || chatAwaitingTokens}
                           onVoiceClick={() => setShowVoiceDialog(true)}
                           voiceDisabled={multiLlmInputBlocked || chatAwaitingTokens}
                           voiceTooltip="Голосовой ввод"
                           libraryBadge={libraryInputBadge}
                           extraActions={multiLlmSettingsExtraAction}
                         />
                       </Box>
                     ) : null}

                     {/* Объединенное поле ввода с кнопками (есть сообщения) */}
           {messages.length > 0 ? (
           <>
             {renderMultiLlmModelToolbar()}
             <ChatInputBar
               toolsMenuAnchorRef={chatInputToolsAnchorRef}
               value={inputMessage}
               onChange={setInputMessage}
               onKeyPress={handleKeyPress}
               onPaste={(e) => handlePaste(e as React.ClipboardEvent<HTMLDivElement>)}
               placeholder={
                 !isConnected && !isConnecting
                   ? 'Нет соединения с сервером. Запустите backend на порту 8000'
                   : isConnecting
                     ? 'Подключение к серверу...'
                     : isMultiLlmMode && !multiLlmHasSelection
                       ? 'Выберите модели для сравнения (до 4, хотя бы одну)'
                       : chatAwaitingTokens
                         ? 'astrachat думает...'
                         : state.isLoading && hasActiveChatStreaming
                           ? isMultiLlmMode
                             ? 'Модели генерируют ответ... Нажмите ⏹️ чтобы остановить'
                             : 'astrachat генерирует ответ... Нажмите ⏹️ чтобы остановить'
                           : 'Чем я могу помочь вам сегодня?'
               }
               inputDisabled={!isConnected || multiLlmInputBlocked || chatAwaitingTokens}
               inputRef={inputRef}
               isDarkMode={isDarkMode}
               solidWorkZoneBackground={workZoneAnimated}
               styleVariant={interfaceSettings.chatInputStyle}
               containerSx={{
                 mt: 2,
                 p: interfaceSettings.chatInputStyle === 'classic' ? 0 : 1.5,
                 borderRadius: interfaceSettings.chatInputStyle === 'classic' ? '28px' : '28px',
                 maxWidth: interfaceSettings.widescreenMode ? '100%' : '1000px',
                 width: '100%',
                 mx: 'auto',
                 px: interfaceSettings.chatInputStyle === 'classic' ? 0 : (interfaceSettings.widescreenMode ? 4 : 2),
               }}
               fileInputRef={fileInputRef}
               onAttachClick={() => fileInputRef.current?.click()}
               onFileSelect={(files) => { if (files?.length) handleFileUpload(files[0]); }}
               uploadedFiles={uploadedFiles.map(f => ({ name: f.name, type: f.type || 'application/octet-stream' }))}
               onFileRemove={(file) => handleFileDelete(file.name)}
               isUploading={isUploading}
               attachDisabled={isUploading || multiLlmInputBlocked || chatAwaitingTokens}
               showReportButton={uploadedFiles.length > 0}
               onReportClick={handleGenerateReport}
               reportDisabled={isUploading || multiLlmInputBlocked || chatAwaitingTokens}
               onSettingsClick={handleMenuOpen}
               settingsDisabled={multiLlmInputBlocked || chatAwaitingTokens}
               showStopButton={state.isLoading || hasActiveChatStreaming}
               onStopClick={handleStopGeneration}
               onSendClick={handleSendMessage}
               sendDisabled={!inputMessage.trim() || !isConnected || multiLlmInputBlocked || chatAwaitingTokens}
               onVoiceClick={() => setShowVoiceDialog(true)}
               voiceDisabled={multiLlmInputBlocked || chatAwaitingTokens}
               voiceTooltip="Голосовой ввод"
               libraryBadge={libraryInputBadge}
               extraActions={multiLlmSettingsExtraAction}
             />
           </>
           ) : null}

             {/* Диалоги */}
       <VoiceChatDialog
         open={showVoiceDialog}
         onClose={() => setShowVoiceDialog(false)}
       />
       <DocumentDialog />

       {/* Инструменты: колонка как в LeChat — «Агенты» + правая панель с вкладками; БЗ и очистка в левой колонке */}
       <Popover
         open={Boolean(anchorEl)}
         anchorEl={anchorEl}
         action={gearToolsPopoverActionRef}
         onClose={handleMenuClose}
         anchorOrigin={{ vertical: CHAT_GEAR_MENU_ANCHOR_VERTICAL_OFFSET, horizontal: 'left' }}
         transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
         marginThreshold={CHAT_GEAR_MENU_MARGIN_THRESHOLD_PX}
         slotProps={{
           paper: {
             sx: {
               mt: 0,
               mb: 0,
               p: 0,
               overflowX: 'hidden',
               background: 'transparent !important',
               backgroundColor: 'transparent !important',
               boxShadow: 'none !important',
               border: 'none',
               ...(gearToolsPaperHeightPx != null
                 ? {
                     minHeight: `${gearToolsPaperHeightPx}px`,
                     maxHeight: `${gearToolsPaperHeightPx}px`,
                     height: `${gearToolsPaperHeightPx}px`,
                     overflowY:
                       gearToolsPaperHeightPx < CHAT_GEAR_MENU_PAPER_MAX_HEIGHT_PX ? 'auto' : 'hidden',
                   }
                 : { maxHeight: CHAT_GEAR_MENU_PAPER_MAX_HEIGHT, overflowY: 'auto' }),
               ...(gearToolsPanel === 'agents' ? CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX : {}),
             },
           },
         }}
       >
         <Box
           sx={{
             display: 'flex',
             flexDirection: 'row',
             alignItems: 'stretch',
             gap: gearToolsPanel === 'agents' ? `${CHAT_GEAR_MENU_PANELS_GAP_PX}px` : 0,
             width:
               gearToolsPanel === 'agents' && gearToolsMenuWidthPx != null
                 ? `${gearToolsMenuWidthPx}px`
                 : gearToolsPanel === 'agents'
                   ? CHAT_GEAR_MENU_EXPANDED_WIDTH_PX
                   : CHAT_GEAR_MENU_PANEL_WIDTH_PX,
             maxWidth:
               gearToolsPanel === 'agents' && gearToolsMenuWidthPx != null
                 ? `${gearToolsMenuWidthPx}px`
                 : 'min(96vw, 580px)',
             minHeight: gearToolsPaperHeightPx != null ? `${gearToolsPaperHeightPx}px` : undefined,
             height: gearToolsPaperHeightPx != null ? `${gearToolsPaperHeightPx}px` : undefined,
             maxHeight: gearToolsPaperHeightPx != null ? `${gearToolsPaperHeightPx}px` : 'inherit',
             boxSizing: 'border-box',
             overflow: 'hidden',
           }}
         >
           <Box
             sx={{
               ...dropdownPanelSx,
               width:
                 gearToolsPanel === 'agents' ? CHAT_GEAR_MENU_LEFT_RAIL_WIDTH_PX : '100%',
               flexShrink: 0,
               boxSizing: 'border-box',
               py: 0.5,
               px: 0.5,
               display: 'flex',
               flexDirection: 'column',
               justifyContent: 'flex-start',
               alignSelf: 'stretch',
               minHeight: 0,
               height: '100%',
             }}
           >
             <Box
               onClick={() => setGearToolsPanel((p) => (p === 'agents' ? 'main' : 'agents'))}
               sx={{
                 ...dropdownItemSx,
                 display: 'flex',
                 alignItems: 'center',
                 gap: 1,
                 color: isDarkMode ? 'white' : '#333',
                 bgcolor:
                   gearToolsPanel === 'agents'
                     ? isDarkMode
                       ? DROPDOWN_ITEM_HOVER_BG_DARK
                       : DROPDOWN_ITEM_HOVER_BG_LIGHT
                     : 'transparent',
               }}
             >
               <GearMenuAgentsIcon
                 sx={{ fontSize: 18, color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)', flexShrink: 0 }}
               />
               <Typography sx={{ flex: 1, minWidth: 0, fontSize: MENU_ACTION_TEXT_SIZE, whiteSpace: 'nowrap' }}>
                 Агенты
               </Typography>
               <ChevronRightIcon
                 sx={{
                   ...DROPDOWN_CHEVRON_SX,
                   flexShrink: 0,
                   transform: gearToolsPanel === 'agents' ? 'rotate(90deg)' : 'none',
                 }}
               />
             </Box>
             <Box
               onClick={() => {
                 toggleKbRag();
                 handleMenuClose();
               }}
               sx={{
                 ...dropdownItemSx,
                 display: 'flex',
                 alignItems: 'center',
                 gap: 1,
                 color: isDarkMode ? 'white' : '#333',
               }}
             >
               <KbIcon sx={{ fontSize: 18, color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)', flexShrink: 0 }} />
               <Typography sx={{ flex: 1, minWidth: 0, fontSize: MENU_ACTION_TEXT_SIZE, whiteSpace: 'nowrap' }}>
                 {useKbRag ? 'Отключить библиотеку' : 'Библиотека'}
               </Typography>
               {useKbRag ? (
                 <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />
               ) : null}
             </Box>
             <Box
               onClick={handleClearChat}
               sx={{
                 ...dropdownItemSx,
                 display: 'flex',
                 alignItems: 'center',
                 gap: 1,
                 color: isDarkMode ? 'white' : '#333',
               }}
             >
               <ClearIcon sx={{ fontSize: 18, color: isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)', flexShrink: 0 }} />
               <Typography sx={{ flex: 1, minWidth: 0, fontSize: MENU_ACTION_TEXT_SIZE, whiteSpace: 'nowrap' }}>
                 Очистить чат
               </Typography>
             </Box>
           </Box>
           {gearToolsPanel === 'agents' ? (
             <Box
               sx={{
                 ...dropdownPanelSx,
                 flex: 1,
                 minWidth: `${CHAT_GEAR_MENU_AGENTS_RIGHT_MIN_PX}px`,
                 minHeight: 0,
                 height: '100%',
                 display: 'flex',
                 flexDirection: 'column',
                 overflow: 'hidden',
               }}
             >
               <ChatGearAgentsPanel
                 isDarkMode={isDarkMode}
                 canUseAgents={Boolean(agentStatus?.is_initialized)}
               />
             </Box>
           ) : null}
         </Box>
       </Popover>

       {/* Диалог редактирования сообщения */}
       <Dialog
         open={editDialogOpen}
         onClose={handleCancelEdit}
         maxWidth="md"
         fullWidth
         PaperProps={{
           sx: {
             bgcolor: 'background.paper',
             borderRadius: 2,
           }
         }}
       >
        <DialogTitle>
          {editingMultiLlmSlotIndex !== null && editingMessage?.multiLLMResponses?.[editingMultiLlmSlotIndex]
            ? `Редактировать ответ (${editingMessage.multiLLMResponses[editingMultiLlmSlotIndex]!.model})`
            : 'Редактировать сообщение'}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Текст сообщения"
            fullWidth
            multiline
            rows={6}
            variant="outlined"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelEdit}>
            Отменить
          </Button>
          {editingMessage?.role === 'user' ? (
            // Кнопки для сообщений пользователя
            <>
              <Button onClick={handleSaveEdit} variant="outlined" color="primary">
                Сохранить
              </Button>
              <Button onClick={handleSaveAndSend} variant="contained" color="primary">
                Сохранить и отправить
              </Button>
            </>
          ) : (
            // Кнопки для сообщений LLM
            <Button onClick={handleSaveEdit} variant="contained" color="primary">
              Сохранить
            </Button>
          )}
        </DialogActions>
       </Dialog>

       {/* Уведомления */}
       <Snackbar
         open={showCopyAlert}
         autoHideDuration={2000}
         onClose={() => setShowCopyAlert(false)}
       >
         <Alert severity="success" onClose={() => setShowCopyAlert(false)}>
           Текст скопирован в буфер обмена
         </Alert>
       </Snackbar>
      </Box>

      {/* Правый сайдбар: кнопки действий → по клику «Конструктор агента» открывается панель */}
      {!rightSidebarHidden && (
      <Drawer
        variant="persistent"
        anchor="right"
        open={true}
        sx={{
          width: rightSidebarOpen ? 240 : 64,
          flexShrink: 0,
          transition: 'width 0.3s ease',
          '& .MuiDrawer-paper': {
            width: rightSidebarOpen ? 240 : 64,
            boxSizing: 'border-box',
            background: rightSidebarPanelBg,
            borderLeft: '1px solid rgba(255,255,255,0.08)',
            transition: 'width 0.3s ease',
            overflowX: 'hidden',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            ...SIDEBAR_HIDE_SCROLLBAR_SX,
          },
        }}
      >
        {/* Свёрнутое состояние: те же стили кнопок, что на левой панели; кнопка «Скрыть панель» — fixed по центру высоты экрана */}
        {!rightSidebarOpen && (
          <>
            {/* Хедер — как у левой панели: px/py/minHeight */}
            <Box
              sx={{
                px: 1,
                py: 1.5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 64,
                boxSizing: 'border-box',
              }}
            >
              <Tooltip title="Открыть панель" placement="left">
                <IconButton
                  onClick={() => setRightSidebarOpen(true)}
                  sx={{
                    color: 'white',
                    opacity: 1,
                    width: 40,
                    height: 40,
                    borderRadius: 1,
                    p: 0,
                    '&:hover': {
                      backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      opacity: 1,
                    },
                  }}
                >
                  <SidebarRailMenuGlyph side="right" />
                </IconButton>
              </Tooltip>
            </Box>
            {/* Узкая панель: List + ListItemButton как на левом сайдбаре */}
            <List disablePadding sx={{ px: 1, pt: 0, pb: 1, width: '100%', boxSizing: 'border-box' }}>
              <ListItem disablePadding sx={{ mb: 0.5, display: 'block' }}>
                <Tooltip title="Транскрибация" placement="left">
                  <Box component="span" sx={{ display: 'flex', width: '100%', justifyContent: 'center' }}>
                    <ListItemButton
                      onClick={() => {
                        setRightSidebarOpen(true);
                        setTranscriptionMenuOpen(true);
                      }}
                      sx={getSidebarRailCollapsedListItemButtonSx(isDarkMode)}
                    >
                      <SidebarRailTranscribeIcon sx={SIDEBAR_LIST_ICON_SX} />
                    </ListItemButton>
                  </Box>
                </Tooltip>
              </ListItem>
              <ListItem disablePadding sx={{ mb: 0.5, display: 'block' }}>
                <Tooltip title="Галерея промптов" placement="left">
                  <Box component="span" sx={{ display: 'flex', width: '100%', justifyContent: 'center' }}>
                    <ListItemButton
                      onClick={() => navigate('/prompts')}
                      sx={getSidebarRailCollapsedListItemButtonSx(isDarkMode)}
                    >
                      <SidebarRailPromptsIcon sx={SIDEBAR_LIST_ICON_SX} />
                    </ListItemButton>
                  </Box>
                </Tooltip>
              </ListItem>
              <ListItem disablePadding sx={{ mb: 0.5, display: 'block' }}>
                <Tooltip title="Конструктор агента" placement="left">
                  <Box component="span" sx={{ display: 'flex', width: '100%', justifyContent: 'center' }}>
                    <ListItemButton
                      onClick={() => {
                        setRightSidebarOpen(true);
                        setAgentConstructorOpen(true);
                      }}
                      sx={getSidebarRailCollapsedListItemButtonSx(isDarkMode)}
                    >
                      <SidebarRailAgentIcon sx={SIDEBAR_LIST_ICON_SX} />
                    </ListItemButton>
                  </Box>
                </Tooltip>
              </ListItem>
            </List>
            {/* Та же позиция и дизайн, что у кнопки «Скрыть панель» на левой панели: по центру высоты экрана */}
            <Box sx={{
              position: 'fixed',
              right: 0,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 64,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              zIndex: 1200,
            }}>
              <Tooltip title="Скрыть панель" placement="left">
                <IconButton
                  onClick={() => setRightSidebarHidden(true)}
                  sx={{
                    color: 'white',
                    opacity: 1,
                    width: 40,
                    height: 40,
                    borderRadius: 1,
                    '&:hover': {
                      backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      opacity: 1,
                    },
                  }}
                >
                  <ChevronRightIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </>
        )}

        {/* Развёрнутое состояние: кнопки всегда видны, меню конструктора открывается под кнопкой «Конструктор агента» */}
        {rightSidebarOpen && (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              overflow: 'hidden',
              // Пока drawer анимирует ширину 64→240, вёрстка считалась бы по узкой полосе → подписи в 2 строки.
              // Фиксируем минимальную ширину контента как у целевой панели; paper уже с overflowX: hidden.
              minWidth: 240,
              boxSizing: 'border-box',
            }}
          >
            <Box
              sx={{
                px: 2,
                py: 1.5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                minHeight: 64,
                flexShrink: 0,
                boxSizing: 'border-box',
              }}
            >
              <Tooltip title="Свернуть панель" placement="left">
                <IconButton
                  onClick={() => setRightSidebarOpen(false)}
                  sx={{
                    color: 'white',
                    opacity: 1,
                    width: 40,
                    height: 40,
                    borderRadius: 1,
                    p: 0,
                    '&:hover': {
                      backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                      opacity: 1,
                    },
                  }}
                >
                  <SidebarRailMenuGlyph side="right" />
                </IconButton>
              </Tooltip>
            </Box>
            <List sx={{ py: 0, px: 1, flexShrink: 0 }}>
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  onClick={() => setTranscriptionMenuOpen(prev => !prev)}
                  sx={{
                    ...SIDEBAR_CHAT_ROW_LIST_ITEM_BUTTON_SX,
                    color: 'white',
                    backgroundColor: transcriptionMenuOpen ? 'rgba(255,255,255,0.15)' : 'transparent',
                    '&:hover': {
                      backgroundColor: transcriptionMenuOpen ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      color: '#ffffff',
                      minWidth: 40,
                      mr: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px`,
                      '& .MuiSvgIcon-root': { fontSize: '1.375rem' },
                    }}
                  >
                    <SidebarRailTranscribeIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Транскрибация"
                    primaryTypographyProps={{
                      sx: { fontSize: '0.8rem', fontWeight: 400, color: '#ffffff' },
                    }}
                  />
                </ListItemButton>
              </ListItem>
              {/* Меню транскрибации — сразу под кнопкой «Транскрибация» */}
              {transcriptionMenuOpen && (
                <Box sx={{ borderTop: '1px solid rgba(255,255,255,0.08)', p: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <input
                    ref={transcriptionFileInputRef}
                    type="file"
                    accept="audio/*,video/*"
                    hidden
                    onChange={handleTranscriptionFileSelect}
                  />
                  {/* Прогресс: транскрибация идёт */}
                  {isTranscribing && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)', fontSize: '0.78rem' }}>
                        Транскрибация идёт...
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        <CircularProgress size={16} sx={{ color: 'primary.main' }} />
                        <Button
                          size="small"
                          startIcon={<SquareIcon sx={{ fontSize: '0.75rem' }} />}
                          onClick={handleStopTranscriptionFromSidebar}
                          disabled={!transcriptionId}
                          sx={{
                            fontSize: '0.7rem',
                            textTransform: 'none',
                            color: 'rgba(255,255,255,0.7)',
                            py: 0.5,
                            minWidth: 0,
                            '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' },
                          }}
                        >
                          Остановить
                        </Button>
                      </Box>
                    </Box>
                  )}
                  {/* Кнопка «Посмотреть результат» после завершения */}
                  {transcriptionResult && !isTranscribing && (
                    <Button
                      size="small"
                      fullWidth
                      variant="outlined"
                      onClick={() => setTranscriptionModalOpen(true)}
                      sx={{
                        fontSize: '0.78rem',
                        textTransform: 'none',
                        color: 'primary.main',
                        borderColor: 'primary.main',
                        py: 0.75,
                        '&:hover': { borderColor: 'primary.light', bgcolor: 'rgba(33,150,243,0.08)' },
                      }}
                    >
                      Посмотреть результат
                    </Button>
                  )}
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.7rem', display: 'block', lineHeight: 1.35 }}>
                    Форматы: MP3, WAV, M4A, AAC, FLAC, MP4, AVI, MOV, MKV, WebM
                    <br />
                    Максимальный размер: 5GB
                  </Typography>
                  <Button
                    size="small"
                    fullWidth
                    startIcon={<UploadIcon sx={{ fontSize: '0.85rem !important' }} />}
                    onClick={() => transcriptionFileInputRef.current?.click()}
                    disabled={isTranscribing}
                    sx={{
                      fontSize: '0.72rem',
                      textTransform: 'none',
                      color: 'rgba(255,255,255,0.6)',
                      border: '1px dashed rgba(255,255,255,0.2)',
                      py: 0.75,
                      justifyContent: 'flex-start',
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.35)' },
                      '&:disabled': { color: 'rgba(255,255,255,0.35)', borderColor: 'rgba(255,255,255,0.1)' },
                    }}
                  >
                    Загрузить файл
                  </Button>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.7rem', display: 'block', mt: 0.5 }}>
                    Вставить ссылку на ютуб
                  </Typography>
                  <TextField
                    size="small"
                    fullWidth
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={transcriptionYoutubeUrl}
                    onChange={(e) => setTranscriptionYoutubeUrl(e.target.value)}
                    disabled={isTranscribing}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        fontSize: '0.78rem',
                        bgcolor: 'rgba(255,255,255,0.06)',
                        color: 'rgba(255,255,255,0.9)',
                        borderColor: 'rgba(255,255,255,0.2)',
                        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.35)' },
                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.main' },
                      },
                      '& .MuiInputBase-input::placeholder': { color: 'rgba(255,255,255,0.4)', opacity: 1 },
                    }}
                  />
                  <Button
                    size="small"
                    fullWidth
                    startIcon={<YouTubeIcon sx={{ fontSize: '0.85rem !important' }} />}
                    onClick={startYouTubeTranscriptionFromSidebar}
                    disabled={!transcriptionYoutubeUrl.trim() || isTranscribing}
                    sx={{
                      fontSize: '0.72rem',
                      textTransform: 'none',
                      color: 'rgba(255,255,255,0.9)',
                      bgcolor: 'rgba(255,255,255,0.08)',
                      py: 0.65,
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.12)' },
                      '&:disabled': { color: 'rgba(255,255,255,0.4)' },
                    }}
                  >
                    Транскрибировать
                  </Button>
                </Box>
              )}
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  onClick={() => navigate('/prompts')}
                  sx={{
                    ...SIDEBAR_CHAT_ROW_LIST_ITEM_BUTTON_SX,
                    color: 'white',
                    '&:hover': {
                      backgroundColor: 'rgba(255,255,255,0.08)',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      color: '#ffffff',
                      minWidth: 40,
                      mr: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px`,
                      '& .MuiSvgIcon-root': { fontSize: '1.375rem' },
                    }}
                  >
                    <SidebarRailPromptsIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Галерея промптов"
                    primaryTypographyProps={{
                      sx: { fontSize: '0.8rem', fontWeight: 400, color: '#ffffff' },
                    }}
                  />
                </ListItemButton>
              </ListItem>
              <ListItem disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  onClick={() => setAgentConstructorOpen(prev => !prev)}
                  sx={{
                    ...SIDEBAR_CHAT_ROW_LIST_ITEM_BUTTON_SX,
                    color: 'white',
                    backgroundColor: agentConstructorOpen ? 'rgba(255,255,255,0.15)' : 'transparent',
                    '&:hover': {
                      backgroundColor: agentConstructorOpen ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      color: '#ffffff',
                      minWidth: 40,
                      mr: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px`,
                      '& .MuiSvgIcon-root': { fontSize: '1.375rem' },
                    }}
                  >
                    <SidebarRailAgentIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Конструктор агента"
                    primaryTypographyProps={{
                      sx: { fontSize: '0.8rem', fontWeight: 400, color: '#ffffff' },
                    }}
                  />
                </ListItemButton>
              </ListItem>
            </List>
            {/* Меню конструктора открывается прямо под кнопкой «Конструктор агента» */}
            {agentConstructorOpen && (
              <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                <AgentConstructorPanel isDarkMode={isDarkMode} isOpen={true} />
              </Box>
            )}
          </Box>
        )}
      </Drawer>
      )}

      {/* Кнопка для показа скрытой панели */}
      {rightSidebarHidden && (
        <Box
          sx={{
            position: 'fixed',
            right: 0,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 1200,
          }}
        >
          <Tooltip title="Показать панель" placement="left">
            <IconButton
              onClick={() => {
                setRightSidebarHidden(false);
                setRightSidebarOpen(false);
              }}
              sx={{
                bgcolor: 'transparent',
                color: 'white',
                opacity: 1,
                width: 40,
                height: 40,
                borderRadius: 1,
                '&:hover': {
                  bgcolor: 'transparent',
                  opacity: 1,
                },
              }}
            >
              <ChevronRightIcon sx={{ transform: 'rotate(180deg)' }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Модальное окно только с результатом транскрибации (открывается по «Посмотреть результат») */}
      <TranscriptionResultModal
        open={transcriptionModalOpen}
        onClose={() => setTranscriptionModalOpen(false)}
        transcriptionResult={transcriptionResult}
        onResultChange={(text) => setTranscriptionResult(text)}
        onInsertToChat={(text) => {
          setInputMessage(text);
          setTimeout(() => inputRef.current?.focus(), 100);
        }}
      />

      {/* Нижняя панель в режиме "Поделиться" */}
      {shareMode && (
        <Paper
          sx={{
            position: 'fixed',
            bottom: 0,
            left: sidebarOpen ? 240 : 64,
            right: 0,
            zIndex: 1200,
            borderRadius: 0,
            boxShadow: '0 -4px 12px rgba(0, 0, 0, 0.1)',
            backgroundColor: isDarkMode ? '#2d2d2d' : '#ffffff',
            transition: 'left 0.3s ease',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 3,
              py: 2,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={selectedMessages.size > 0 && (() => {
                      let totalPairs = 0;
                      for (let i = 0; i < messages.length - 1; i++) {
                        if (messages[i].role === 'user' && messages[i + 1].role === 'assistant') {
                          totalPairs++;
                        }
                      }
                      return selectedMessages.size === totalPairs * 2;
                    })()}
                    onChange={handleSelectAll}
                  />
                }
                label="Выбрать все"
              />
              <Typography variant="body2" color="text.secondary">
                Выбрано пар: {selectedMessages.size / 2}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                onClick={handleExitShareMode}
                disabled={isCreatingShareLink}
              >
                Отмена
              </Button>
              <Button
                variant="contained"
                onClick={handleCreateShareLink}
                disabled={selectedMessages.size === 0}
              >
                Создать публичную ссылку
              </Button>
            </Box>
          </Box>
        </Paper>
      )}

      {/* Навигационная панель для сообщений (панель с диалогами) */}
      {messages.length > 0 && showDialoguesPanel && (
        <MessageNavigationBar
          messages={messages}
          isDarkMode={isDarkMode}
          onNavigate={scrollToMessage}
          rightSidebarOpen={rightSidebarOpen}
          rightSidebarHidden={rightSidebarHidden}
        />
      )}

      {/* Диалог подтверждения создания публичной ссылки */}
      <ShareConfirmDialog
        open={shareDialogOpen}
        onClose={handleCloseShareDialog}
        onConfirm={createShareLinkConfirmed}
        isDarkMode={isDarkMode}
        selectedCount={selectedMessages.size}
      />
      </Box>
    </Box>
  );
}
