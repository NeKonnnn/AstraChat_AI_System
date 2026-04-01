import React, { useState, useEffect, useMemo } from 'react';
import { useTheme } from '@mui/material/styles';
import {
  Box,
  Typography,
  Card,
  CardContent,
  FormControlLabel,
  Button,
  Alert,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Collapse,
  Switch,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  Popover,
} from '@mui/material';
import {
  SmartToyOutlined as AgentIcon,
  ComputerOutlined as DirectIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ViewModuleOutlined as MultiLLMIcon,
  HelpOutline as HelpOutlineIcon,
} from '@mui/icons-material';
import { getApiUrl } from '../../config/api';
import {
  MENU_ICON_MIN_WIDTH,
  MENU_ICON_TO_TEXT_GAP_PX,
  MENU_ICON_FONT_SIZE_PX,
  DROPDOWN_TRIGGER_BUTTON_SX,
  DROPDOWN_CHEVRON_SX,
  getDropdownPopoverPaperSx,
  getDropdownItemSx,
  DROPDOWN_ITEM_HOVER_BG,
} from '../../constants/menuStyles';


interface AgentStatus {
  is_initialized: boolean;
  mode: string;
  available_agents: number;
  orchestrator_active: boolean;
}

interface Agent {
  name: string;
  description: string;
  capabilities: string[];
  tools_count: number;
  is_active: boolean;
  agent_id: string;
  tools?: Array<{
    name: string;
    description: string;
    is_active: boolean;
    instruction: string;
  }>;
  usage_examples?: string[];
  toolsExpanded?: boolean; // Для управления развернутостью инструментов
}

interface MCPStatus {
  servers_connected?: number;
  total_servers?: number;
  active_servers?: string[];
}

interface LangGraphStatus {
  is_active?: boolean;
  memory_enabled?: boolean;
  graph_compiled?: boolean;
  orchestrator_active?: boolean;
}

interface Model {
  name: string;
  path: string;
  size?: number;
  size_mb?: number;
}

export default function AgentsSettings() {
  const theme = useTheme();
  const dropdownItemSx = useMemo(() => getDropdownItemSx(theme.palette.mode === 'dark'), [theme.palette.mode]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [langgraphStatus, setLanggraphStatus] = useState<LangGraphStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [agentsExpanded, setAgentsExpanded] = useState(true);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [modePopoverAnchor, setModePopoverAnchor] = useState<HTMLElement | null>(null);
  const [pendingOrchestratorAction, setPendingOrchestratorAction] = useState<boolean | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [, setAvailableModels] = useState<Model[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [, setSelectedMultiLLMModels] = useState<string[]>([]);

  useEffect(() => {
    loadAgentStatus();
    loadMcpStatus();
    loadLanggraphStatus();
  }, []);

  // Загружаем агентов если режим уже агентный
  useEffect(() => {
    if (agentStatus?.mode === 'agent') {
      loadAgents();
    } else if (agentStatus?.mode === 'multi-llm') {
      loadAvailableModels();
      loadMultiLLMModels();
    }
  }, [agentStatus?.mode]);

  const loadAgentStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(getApiUrl('/api/agent/status'));
      if (response.ok) {
        const data = await response.json();
        
        // Если режим не установлен, устанавливаем прямой режим по умолчанию
        if (!data.mode) {
          data.mode = 'direct';
          // Автоматически переключаем режим на сервере
          try {
            await fetch(getApiUrl('/api/agent/mode'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ mode: 'direct' }),
            });
          } catch (err) {
            // Игнорируем ошибку переключения режима
          }
        }
        setAgentStatus(data);
      } else {
        // Если не удалось загрузить статус, устанавливаем прямой режим по умолчанию
        setAgentStatus({
          is_initialized: false,
          mode: 'direct',
          available_agents: 0,
          orchestrator_active: false,
        });
      }
    } catch (err) {
      // При ошибке также устанавливаем прямой режим по умолчанию
      setAgentStatus({
        is_initialized: false,
        mode: 'direct',
        available_agents: 0,
        orchestrator_active: false,
      });
      setError(`Ошибка загрузки статуса: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMcpStatus = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/mcp/status'));
      if (response.ok) {
        const data = await response.json();
        setMcpStatus(data.mcp_status);
      }
    } catch (err) {
      // Ошибка загрузки статуса MCP
    }
  };

  const loadLanggraphStatus = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/langgraph/status'));
      if (response.ok) {
        const data = await response.json();
        setLanggraphStatus(data.langgraph_status);
      }
    } catch (err) {
      // Ошибка загрузки статуса LangGraph
    }
  };

  type AgentMode = 'direct' | 'agent' | 'multi-llm';
  const getModeLabel = (mode: AgentMode): string => {
    switch (mode) {
      case 'direct': return 'Прямой режим';
      case 'agent': return 'Агентный режим';
      case 'multi-llm': return 'Прямой режим с несколькими LLM';
      default: return 'Прямой режим';
    }
  };
  const getModeDescription = (mode: AgentMode): string => {
    switch (mode) {
      case 'direct': return 'Общение с моделью напрямую без использования агентов. Подходит для простых диалогов и задач.';
      case 'agent': return 'Использование специализированных агентов для решения задач. Каждый агент отвечает за свою область.';
      case 'multi-llm': return 'Параллельная генерация ответов от нескольких моделей одновременно. Сравнивайте результаты разных LLM.';
      default: return '';
    }
  };
  const getModeUseCase = (mode: AgentMode): string => {
    switch (mode) {
      case 'direct': return 'Используйте для обычных диалогов, когда не нужны специализированные агенты.';
      case 'agent': return 'Используйте когда нужны агенты с разными возможностями (поиск, расчёты, код и т.д.).';
      case 'multi-llm': return 'Используйте для сравнения ответов разных моделей или ансамблевых сценариев.';
      default: return '';
    }
  };

  const loadAgents = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/agents'));
      if (response.ok) {
        const data = await response.json();
        const agents = data.agents || [];
        setAvailableAgents(agents);
      } else {
        throw new Error('Не удалось загрузить список агентов');
      }
    } catch (err) {
      setError(`Ошибка загрузки агентов: ${err}`);
    }
  };

  const toggleAgentStatus = async (agentId: string, currentStatus: boolean) => {
    try {
      // Пока эндпоинт /api/agent/toggle не реализован, обновляем только локальное состояние
      setAvailableAgents(prev => 
        prev.map(agent => 
          agent.agent_id === agentId 
            ? { ...agent, is_active: !currentStatus }
            : agent
        )
      );
      setSuccess(`Агент ${currentStatus ? 'отключен' : 'включен'}`);
      
      // В будущем можно будет добавить реальный API вызов:
      // const response = await fetch(`${API_BASE_URL}/api/agent/toggle`, {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ agent_id: agentId, enable: !currentStatus }),
      // });
      // if (response.ok) { ... } else { throw new Error('Не удалось изменить статус агента'); }
    } catch (err) {
      setError(`Ошибка изменения статуса агента: ${err}`);
    }
  };

  const toggleToolStatus = async (agentId: string, toolName: string, currentStatus: boolean) => {
    try {
      // Пока эндпоинт /api/agent/tool/toggle не реализован, обновляем только локальное состояние
      setAvailableAgents(prev => 
        prev.map(agent => 
          agent.agent_id === agentId 
            ? {
                ...agent,
                tools: agent.tools ? agent.tools.map(tool => 
                  tool.name === toolName 
                    ? { ...tool, is_active: !currentStatus }
                    : tool
                ) : []
              }
            : agent
        )
      );
      setSuccess(`Инструмент ${currentStatus ? 'отключен' : 'включен'}`);
      
      // В будущем можно будет добавить реальный API вызов:
      // const response = await fetch(`${API_BASE_URL}/api/agent/tool/toggle`, {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ 
      //     agent_id: agentId, 
      //     tool_name: toolName, 
      //     enable: !currentStatus 
      //   }),
      // });
      // if (response.ok) { ... } else { throw new Error('Не удалось изменить статус инструмента'); }
    } catch (err) {
      setError(`Ошибка изменения статуса инструмента: ${err}`);
    }
  };

  const handleOrchestratorToggle = (isActive: boolean) => {
    if (!isActive) {
      // Показываем модальное окно при отключении
      setPendingOrchestratorAction(isActive);
      setConfirmDialogOpen(true);
    } else {
      // Включаем сразу
      toggleOrchestrator(isActive);
    }
  };

  const handleConfirmDialog = () => {
    if (pendingOrchestratorAction !== null) {
      toggleOrchestrator(pendingOrchestratorAction);
    }
    setConfirmDialogOpen(false);
    setPendingOrchestratorAction(null);
  };

  const handleCancelDialog = () => {
    setConfirmDialogOpen(false);
    setPendingOrchestratorAction(null);
  };

  const toggleOrchestrator = async (isActive: boolean) => {
    try {
      const response = await fetch(getApiUrl('/api/agent/orchestrator/toggle'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: isActive }),
      });

      if (response.ok) {
        const data = await response.json();
        setSuccess(data.message);
        
        // Обновляем статус LangGraph
        await loadLanggraphStatus();
      } else {
        throw new Error('Не удалось переключить оркестратор');
      }
    } catch (err) {
      setError(`Ошибка переключения оркестратора: ${err}`);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const response = await fetch(getApiUrl('/api/models/available'));
      if (response.ok) {
        const data = await response.json();
        setAvailableModels(data.models || []);
      } else {
        setError('Не удалось загрузить список моделей');
      }
    } catch (err) {
      setError(`Ошибка загрузки моделей: ${err}`);
    }
  };

  const loadMultiLLMModels = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/multi-llm/models'));
      if (response.ok) {
        const data = await response.json();
        setSelectedMultiLLMModels(data.models || []);
      }
    } catch (err) {
      // Ошибка загрузки выбранных моделей
    }
  };

  const switchMode = async (mode: 'direct' | 'agent' | 'multi-llm') => {
    try {
      const response = await fetch(getApiUrl('/api/agent/mode'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });

      if (response.ok) {
        setAgentStatus(prev => prev ? { ...prev, mode } : null);
        
        // Если переключаемся на агентный режим, загружаем агентов
        if (mode === 'agent') {
          // Загружаем список агентов
          await loadAgents();
          
          // Принудительно обновляем статус LangGraph
          await loadLanggraphStatus();
        } else if (mode === 'multi-llm') {
          // Загружаем список моделей
          await loadAvailableModels();
          await loadMultiLLMModels();
        }
        
        // Перезагружаем статус для обновления данных
        await loadAgentStatus();
        await loadLanggraphStatus();
        window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
      } else {
        throw new Error('Не удалось переключить режим');
      }
    } catch (err) {
      setError(`Ошибка переключения режима: ${err}`);
    }
  };

  const initializeAgents = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(getApiUrl('/api/agent/initialize'), {
        method: 'POST',
      });

      if (response.ok) {
        setSuccess('Агентная архитектура инициализирована');
        await loadAgentStatus();
        await loadAgents();
      } else {
        throw new Error('Не удалось инициализировать агентную архитектуру');
      }
    } catch (err) {
      setError(`Ошибка инициализации: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (agentStatus?.is_initialized) {
      loadAgents();
    }
  }, [agentStatus?.is_initialized]);

  return (
    <Box sx={{ p: 3 }}>
      {/* Статус агентной архитектуры */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AgentIcon color="primary" />
            Статус агентной архитектуры
          </Typography>

          {isLoading && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <CircularProgress size={20} />
              <Typography variant="body2">Загрузка...</Typography>
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
              {success}
            </Alert>
          )}

          {agentStatus ? (
            <Box>
              <List sx={{ p: 0 }}>
                <ListItem
                  sx={{
                    px: 0,
                    py: 2,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        Режим работы
                        <Tooltip
                          title="Выберите режим работы: прямой (только модель), агентный (специализированные агенты) или прямой с несколькими LLM."
                          arrow
                        >
                          <IconButton
                            size="small"
                            sx={{
                              p: 0,
                              ml: 0.5,
                              opacity: 0.7,
                              '&:hover': {
                                opacity: 1,
                                '& .MuiSvgIcon-root': {
                                  color: 'primary.main',
                                },
                              },
                            }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <HelpOutlineIcon fontSize="small" color="action" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    }
                    primaryTypographyProps={{
                      variant: 'body1',
                      fontWeight: 500,
                    }}
                  />
                  <Box sx={{ minWidth: 280 }}>
                    <Box
                      onClick={(e) => !isLoading && setModePopoverAnchor(e.currentTarget)}
                      sx={{
                        ...DROPDOWN_TRIGGER_BUTTON_SX,
                        opacity: isLoading ? 0.7 : 1,
                        pointerEvents: isLoading ? 'none' : 'auto',
                      }}
                    >
                      <Typography sx={{ color: 'white', fontWeight: 500, fontSize: '0.875rem' }}>
                        {getModeLabel(agentStatus.mode as AgentMode)}
                      </Typography>
                      <ExpandMoreIcon sx={{ ...DROPDOWN_CHEVRON_SX, transform: modePopoverAnchor ? 'rotate(180deg)' : 'none' }} />
                    </Box>
                    <Popover
                      open={Boolean(modePopoverAnchor)}
                      anchorEl={modePopoverAnchor}
                      onClose={() => setModePopoverAnchor(null)}
                      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                      slotProps={{ paper: { sx: getDropdownPopoverPaperSx(modePopoverAnchor) } }}
                    >
                      <Box sx={{ py: 0.5 }}>
                        {(['direct', 'agent', 'multi-llm'] as const).map((mode) => (
                          <Box
                            key={mode}
                            onClick={() => { switchMode(mode); setModePopoverAnchor(null); }}
                            sx={{
                              ...dropdownItemSx,
                              color: agentStatus.mode === mode ? 'white' : 'rgba(255,255,255,0.9)',
                              fontWeight: agentStatus.mode === mode ? 600 : 400,
                              bgcolor: agentStatus.mode === mode ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                            }}
                          >
                            {getModeLabel(mode)}
                          </Box>
                        ))}
                      </Box>
                    </Popover>
                  </Box>
                </ListItem>
              </List>

              <Alert
                severity="info"
                sx={{
                  mt: 2,
                  '& .MuiAlert-message': { width: '100%' },
                }}
              >
                <Box>
                  <Typography variant="subtitle2" fontWeight="600" gutterBottom>
                    {getModeLabel(agentStatus.mode as AgentMode)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {getModeDescription(agentStatus.mode as AgentMode)}
                  </Typography>
                  <Typography variant="body2" fontWeight="500" sx={{ mt: 1 }}>
                    {getModeUseCase(agentStatus.mode as AgentMode)}
                  </Typography>
                </Box>
              </Alert>

              <Divider />

              <ListItem
                sx={{
                  px: 0,
                  py: 2,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Оркестратор
                      <Tooltip
                        title="Оркестратор автоматически выберет лучшего агента для решения вашей задачи."
                        arrow
                      >
                        <IconButton
                          size="small"
                          sx={{
                            p: 0,
                            ml: 0.5,
                            opacity: 0.7,
                            '&:hover': {
                              opacity: 1,
                              '& .MuiSvgIcon-root': {
                                color: 'primary.main',
                              },
                            },
                          }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <HelpOutlineIcon fontSize="small" color="action" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  }
                  primaryTypographyProps={{
                    variant: 'body1',
                    fontWeight: 500,
                  }}
                />
                <Switch
                  checked={langgraphStatus?.orchestrator_active ?? agentStatus?.orchestrator_active ?? false}
                  disabled={!langgraphStatus?.is_active}
                  onChange={(e) => handleOrchestratorToggle(e.target.checked)}
                  color="primary"
                />
              </ListItem>

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
                <Button
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  onClick={loadAgentStatus}
                  disabled={isLoading}
                >
                  Обновить статус
                </Button>
              </Box>
            </Box>
          ) : (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <ErrorIcon color="error" />
                <Typography variant="body1" fontWeight="500">
                  Агентная архитектура не инициализирована
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Для использования агентного режима необходимо инициализировать агентную архитектуру.
              </Typography>
              <Button
                variant="contained"
                startIcon={<AgentIcon />}
                onClick={initializeAgents}
                disabled={isLoading}
              >
                Инициализировать агентную архитектуру
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Список агентов */}
      {agentStatus?.mode === 'agent' && availableAgents && availableAgents.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="h6" gutterBottom sx={{ mb: 0 }}>
                  Доступные агенты ({availableAgents.length})
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip 
                    label={`Активно: ${availableAgents.filter(a => a.is_active).length}`}
                    size="small"
                    color="primary"
                  />
                  <Chip 
                    label={`Инструментов: ${availableAgents.reduce((total, agent) => total + (agent.tools?.length || 0), 0)}`}
                    size="small"
                    color="secondary"
                    variant="outlined"
                  />
                </Box>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<RefreshIcon />}
                  onClick={loadAgents}
                >
                  Обновить
                </Button>
                <IconButton
                  onClick={() => setAgentsExpanded(!agentsExpanded)}
                  size="small"
                >
                  {agentsExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>
            </Box>
            
            <Collapse in={agentsExpanded}>
              <List>
                {availableAgents.map((agent, index) => (
                  <React.Fragment key={agent.agent_id || agent.name}>
                    <ListItem sx={{ 
                      border: '1px solid', 
                      borderColor: 'grey.300', 
                      borderRadius: 1, 
                      mb: 1,
                      bgcolor: 'background.default'
                    }}>
                      <ListItemIcon sx={{ minWidth: `${MENU_ICON_MIN_WIDTH}px`, marginRight: `${MENU_ICON_TO_TEXT_GAP_PX}px`, '& .MuiSvgIcon-root': { fontSize: `${MENU_ICON_FONT_SIZE_PX}px` } }}>
                        <AgentIcon color={agent.is_active ? 'primary' : 'disabled'} />
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'space-between' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="subtitle2">
                                {agent.name}
                              </Typography>
                              <Chip 
                                label={agent.is_active ? 'Активен' : 'Неактивен'} 
                                size="small" 
                                color={agent.is_active ? 'success' : 'default'}
                              />
                            </Box>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={agent.is_active}
                                  onChange={() => toggleAgentStatus(agent.agent_id || agent.name, agent.is_active)}
                                  color="primary"
                                  size="small"
                                />
                              }
                              label=""
                              sx={{ m: 0 }}
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              {agent.description}
                            </Typography>
                            
                            {agent.capabilities && agent.capabilities.length > 0 && (
                              <Box sx={{ mb: 1 }}>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                                  Возможности:
                                </Typography>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                  {agent.capabilities.map((capability, capIndex) => (
                                    <Chip key={capIndex} label={capability} size="small" variant="outlined" />
                                  ))}
                                </Box>
                              </Box>
                            )}
                            
                            {agent.tools && Array.isArray(agent.tools) && agent.tools.length > 0 && (
                              <Box>
                                <Box 
                                  sx={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: 1, 
                                    mb: 1, 
                                    cursor: 'pointer',
                                    p: 0.5,
                                    borderRadius: 1,
                                    '&:hover': { bgcolor: 'action.hover' }
                                  }}
                                  onClick={() => {
                                    setAvailableAgents(prev => 
                                      prev.map(a => 
                                        a.agent_id === agent.agent_id 
                                          ? { ...a, toolsExpanded: !a.toolsExpanded }
                                          : a
                                      )
                                    );
                                  }}
                                >
                                  <Typography variant="caption" color="text.secondary">
                                    Инструменты ({agent.tools.length}):
                                  </Typography>
                                  {agent.toolsExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                </Box>
                                
                                <Collapse in={agent.toolsExpanded || false}>
                                  <Box sx={{ pl: 2, borderLeft: '2px solid', borderColor: 'divider' }}>
                                    {agent.tools.map((tool, toolIndex) => (
                                      <Box key={toolIndex} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, py: 0.5 }}>
                                        <Switch
                                          checked={tool.is_active}
                                          onChange={() => toggleToolStatus(agent.agent_id || agent.name, tool.name, tool.is_active)}
                                          size="small"
                                        />
                                        <Box sx={{ flex: 1 }}>
                                          <Typography variant="caption" fontWeight="500">
                                            {tool.name}
                                          </Typography>
                                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                            {tool.description}
                                          </Typography>
                                        </Box>
                                      </Box>
                                    ))}
                                  </Box>
                                </Collapse>
                              </Box>
                            )}
                            
                            {agent.usage_examples && agent.usage_examples.length > 0 && (
                              <Box sx={{ mt: 1 }}>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                                  Примеры использования:
                                </Typography>
                                {agent.usage_examples.map((example, exIndex) => (
                                  <Typography key={exIndex} variant="caption" color="text.secondary" sx={{ display: 'block', fontStyle: 'italic' }}>
                                    • {example}
                                  </Typography>
                                ))}
                              </Box>
                            )}
                          </Box>
                        }
                      />
                    </ListItem>
                    {availableAgents && index < availableAgents.length - 1 && <Divider sx={{ my: 1 }} />}
                  </React.Fragment>
                ))}
              </List>
            </Collapse>
          </CardContent>
        </Card>
      )}

      {/* Сообщение если агенты не загружены */}
      {agentStatus?.mode === 'agent' && (!availableAgents || availableAgents.length === 0) && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 3 }}>
              <AgentIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Агенты не загружены
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Нажмите "Обновить" для загрузки списка агентов
              </Typography>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={loadAgents}
              >
                Загрузить агентов
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Статус MCP серверов */}
      {mcpStatus && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              MCP Серверы
              <Tooltip 
                title="В агентном режиме рекомендуется подключить MCP серверы для расширенной функциональности агентов." 
                arrow
              >
                <IconButton 
                  size="small" 
                  sx={{ 
                    ml: 0.5,
                    opacity: 0.7,
                    '&:hover': {
                      opacity: 1,
                      '& .MuiSvgIcon-root': {
                        color: 'primary.main',
                      },
                    },
                  }}
                >
                  <HelpOutlineIcon fontSize="small" color="action" />
                </IconButton>
              </Tooltip>
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              {(mcpStatus.servers_connected || 0) > 0 ? (
                <CheckIcon color="success" />
              ) : (
                <ErrorIcon color="error" />
              )}
              <Typography variant="body1">
                Подключено: {mcpStatus.servers_connected || 0} из {mcpStatus.total_servers || 0}
              </Typography>
            </Box>
            {mcpStatus.active_servers && mcpStatus.active_servers.length > 0 && (
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Активные серверы:
                </Typography>
                {mcpStatus.active_servers.map((server, index) => (
                  <Chip key={index} label={server} size="small" sx={{ mr: 1, mb: 1 }} />
                ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Модальное окно подтверждения отключения оркестратора */}
      <Dialog
        open={confirmDialogOpen}
        onClose={handleCancelDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: 'warning.main', display: 'flex', alignItems: 'center', gap: 1 }}>
          ⚠️ ВНИМАНИЕ!
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Вы собираетесь отключить LangGraph оркестратор.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            При отключении оркестратора вы будете работать с агентами напрямую.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            <strong>Важно:</strong> Вы должны правильно выбрать соответствующего агента для решения своей задачи, 
            иначе решение может быть некорректным.
          </Typography>
          <Alert severity="warning" sx={{ mt: 2 }}>
            Убедитесь, что вы понимаете последствия этого действия!
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleCancelDialog} color="primary">
            Отмена
          </Button>
          <Button 
            onClick={handleConfirmDialog} 
            color="warning" 
            variant="contained"
          >
            Да, отключить оркестратор
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
