import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  RadioGroup,
  Radio,
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
  Checkbox,
  FormGroup,
} from '@mui/material';
import {
  SmartToy as AgentIcon,
  Computer as DirectIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ViewModule as MultiLLMIcon,
} from '@mui/icons-material';

const API_BASE_URL = 'http://localhost:8000';

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
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [langgraphStatus, setLanggraphStatus] = useState<LangGraphStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [agentsExpanded, setAgentsExpanded] = useState(true);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingOrchestratorAction, setPendingOrchestratorAction] = useState<boolean | null>(null);
  const [availableModels, setAvailableModels] = useState<Model[]>([]);
  const [selectedMultiLLMModels, setSelectedMultiLLMModels] = useState<string[]>([]);

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

      const response = await fetch(`${API_BASE_URL}/api/agent/status`);
      if (response.ok) {
        const data = await response.json();
        
        // ОТЛАДКА: Выводим что приходит с бэкенда для агентного статуса
        console.log('=== ОТЛАДКА АГЕНТНОГО СТАТУСА ===');
        console.log('Полные данные агентного статуса с бэкенда:', data);
        console.log('Режим:', data.mode);
        console.log('Инициализирован:', data.is_initialized);
        console.log('Доступно агентов:', data.available_agents);
        console.log('Оркестратор активен:', data.orchestrator_active);
        console.log('=== КОНЕЦ ОТЛАДКИ АГЕНТНОГО СТАТУСА ===');
        
        // Если режим не установлен, устанавливаем прямой режим по умолчанию
        if (!data.mode) {
          data.mode = 'direct';
          // Автоматически переключаем режим на сервере
          try {
            await fetch(`${API_BASE_URL}/api/agent/mode`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ mode: 'direct' }),
            });
          } catch (err) {
            console.warn('Не удалось переключить режим на сервере:', err);
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
      const response = await fetch(`${API_BASE_URL}/api/agent/mcp/status`);
      if (response.ok) {
        const data = await response.json();
        setMcpStatus(data.mcp_status);
      } else {
        console.warn('Не удалось загрузить статус MCP');
      }
    } catch (err) {
      console.error('Ошибка загрузки статуса MCP:', err);
    }
  };

  const loadLanggraphStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/langgraph/status`);
      if (response.ok) {
        const data = await response.json();
        
        // ОТЛАДКА: Выводим что приходит с бэкенда для LangGraph
        console.log('=== ОТЛАДКА LANGGRAPH СТАТУСА ===');
        console.log('Полные данные LangGraph с бэкенда:', data);
        console.log('LangGraph статус:', data.langgraph_status);
        console.log('=== КОНЕЦ ОТЛАДКИ LANGGRAPH ===');
        
        setLanggraphStatus(data.langgraph_status);
      } else {
        console.warn('Не удалось загрузить статус LangGraph');
      }
    } catch (err) {
      console.error('Ошибка загрузки статуса LangGraph:', err);
    }
  };

  const loadAgents = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/agents`);
      if (response.ok) {
        const data = await response.json();
        const agents = data.agents || [];
        
        // ОТЛАДКА: Выводим что приходит с бэкенда
        console.log('=== ОТЛАДКА ЗАГРУЗКИ АГЕНТОВ ===');
        console.log('Полные данные с бэкенда:', data);
        console.log('Количество агентов:', agents.length);
        agents.forEach((agent: any, index: number) => {
          console.log(`Агент ${index + 1}:`, {
            name: agent.name,
            agent_id: agent.agent_id,
            tools_count: agent.tools?.length || 0,
            tools: agent.tools,
            capabilities: agent.capabilities,
            usage_examples: agent.usage_examples
          });
        });
        console.log('=== КОНЕЦ ОТЛАДКИ ===');
        
        setAvailableAgents(agents);
      } else {
        throw new Error('Не удалось загрузить список агентов');
      }
    } catch (err) {
      console.error('Ошибка загрузки агентов:', err);
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
      const response = await fetch(`${API_BASE_URL}/api/agent/orchestrator/toggle`, {
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
      const response = await fetch(`${API_BASE_URL}/api/models/available`);
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
      const response = await fetch(`${API_BASE_URL}/api/agent/multi-llm/models`);
      if (response.ok) {
        const data = await response.json();
        setSelectedMultiLLMModels(data.models || []);
      }
    } catch (err) {
      console.error('Ошибка загрузки выбранных моделей:', err);
    }
  };

  const saveMultiLLMModels = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/multi-llm/models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models: selectedMultiLLMModels }),
      });

      if (response.ok) {
        setSuccess(`Выбрано моделей: ${selectedMultiLLMModels.length}`);
      } else {
        throw new Error('Не удалось сохранить выбранные модели');
      }
    } catch (err) {
      setError(`Ошибка сохранения моделей: ${err}`);
    }
  };

  const switchMode = async (mode: 'direct' | 'agent' | 'multi-llm') => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });

      if (response.ok) {
        setAgentStatus(prev => prev ? { ...prev, mode } : null);
        const modeNames = {
          'direct': 'прямой',
          'agent': 'агентный',
          'multi-llm': 'прямой с несколькими LLM'
        };
        setSuccess(`Режим переключен на ${modeNames[mode]}`);
        
        // Если переключаемся на агентный режим, загружаем агентов
        if (mode === 'agent') {
          // Загружаем список агентов
          await loadAgents();
          
          // Принудительно обновляем статус LangGraph
          await loadLanggraphStatus();
          
          setSuccess('Агентный режим активирован');
        } else if (mode === 'multi-llm') {
          // Загружаем список моделей
          await loadAvailableModels();
          await loadMultiLLMModels();
        }
        
        // Перезагружаем статус для обновления данных
        await loadAgentStatus();
        await loadLanggraphStatus();
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
      const response = await fetch(`${API_BASE_URL}/api/agent/initialize`, {
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
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <AgentIcon color="primary" />
        Настройки агентов
      </Typography>

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
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <CheckIcon color="success" />
                <Typography variant="body1" fontWeight="500">
                  Агентная архитектура активна
                </Typography>
                <Chip 
                  label={`${agentStatus.available_agents} агентов`} 
                  size="small" 
                  color="primary" 
                />
              </Box>

              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2, mb: 2 }}>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">
                    Режим работы
                  </Typography>
                  <Typography variant="body1" fontWeight="500">
                    {agentStatus.mode === 'direct' ? 'Прямой режим' : 'Агентный режим'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">
                    Доступно агентов
                  </Typography>
                  <Typography variant="body1" fontWeight="500">
                    {agentStatus.available_agents}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">
                    Оркестратор
                  </Typography>
                  <Typography variant="body1" fontWeight="500">
                    {agentStatus.orchestrator_active ? 'Активен' : 'Неактивен'}
                  </Typography>
                </Box>
              </Box>

              {/* Переключение режима */}
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Режим работы
                </Typography>
                <FormControl component="fieldset">
                  <RadioGroup
                    value={agentStatus.mode}
                    onChange={(e) => switchMode(e.target.value as 'direct' | 'agent' | 'multi-llm')}
                  >
                    <FormControlLabel
                      value="direct"
                      control={<Radio />}
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <DirectIcon fontSize="small" />
                          <Box>
                            <Typography variant="body2" fontWeight="500">
                              Прямой режим
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Общение с моделью напрямую без использования агентов
                            </Typography>
                          </Box>
                        </Box>
                      }
                    />
                    <FormControlLabel
                      value="agent"
                      control={<Radio />}
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <AgentIcon fontSize="small" />
                          <Box>
                            <Typography variant="body2" fontWeight="500">
                              Агентный режим
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Использование специализированных агентов для решения задач
                            </Typography>
                          </Box>
                        </Box>
                      }
                    />
                    <FormControlLabel
                      value="multi-llm"
                      control={<Radio />}
                      label={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <MultiLLMIcon fontSize="small" />
                          <Box>
                            <Typography variant="body2" fontWeight="500">
                              Прямой режим с несколькими LLM
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Параллельная генерация ответов от нескольких моделей одновременно
                            </Typography>
                          </Box>
                        </Box>
                      }
                    />
                  </RadioGroup>
                </FormControl>
              </Box>

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
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

      {/* Статус MCP серверов */}
      {mcpStatus && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              MCP Серверы
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
            
            {(mcpStatus.servers_connected || 0) === 0 && agentStatus?.mode === 'agent' && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  <strong>Внимание:</strong> В агентном режиме рекомендуется подключить MCP серверы для расширенной функциональности агентов.
                </Typography>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Статус LangGraph */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            LangGraph Оркестратор
          </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
              {langgraphStatus?.orchestrator_active ? (
                <CheckIcon color="success" />
              ) : (
                <ErrorIcon color="error" />
              )}
              <Typography variant="body1">
                {langgraphStatus?.orchestrator_active ? 'Активен' : 'Неактивен'}
              </Typography>
              {agentStatus?.mode === 'agent' && !langgraphStatus?.is_active && (
                <Chip 
                  label="Требуется активация" 
                  size="small" 
                  color="warning" 
                  variant="outlined"
                />
              )}
            </Box>
            
            {/* Переключатель оркестратора */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Оркестратор:
              </Typography>
              <Switch
                checked={langgraphStatus?.orchestrator_active || false}
                disabled={!langgraphStatus?.is_active}
                onChange={(e) => {
                  const isActive = e.target.checked;
                  handleOrchestratorToggle(isActive);
                }}
                color="primary"
              />
              <Typography variant="body2" color="text.secondary">
                {langgraphStatus?.orchestrator_active ? 'Включен' : 'Отключен'}
              </Typography>
              {!langgraphStatus?.is_active && (
                <Chip 
                  label="LangGraph не активен" 
                  size="small" 
                  color="error" 
                  variant="outlined"
                />
              )}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Память: {langgraphStatus?.memory_enabled ? 'Включена' : 'Отключена'}
            </Typography>
            {langgraphStatus?.graph_compiled !== undefined && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Граф: {langgraphStatus.graph_compiled ? 'Скомпилирован' : 'Не скомпилирован'}
              </Typography>
            )}
            
            {!langgraphStatus?.is_active && agentStatus?.mode === 'agent' && (
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  <strong>Информация:</strong> Оркестратор неактивен. В агентном режиме агенты будут работать напрямую без оркестратора.
                </Typography>
              </Alert>
            )}
            
            {langgraphStatus?.is_active && agentStatus?.mode === 'agent' && (
              <Alert 
                severity={langgraphStatus?.orchestrator_active ? "success" : "warning"} 
                sx={{ mt: 2 }}
              >
                <Typography variant="body2">
                  <strong>
                    {langgraphStatus?.orchestrator_active ? 'Режим оркестратора:' : 'Режим прямого управления:'}
                  </strong>
                  {' '}
                  {langgraphStatus?.orchestrator_active 
                    ? 'Оркестратор автоматически выберет лучшего агента для решения вашей задачи.'
                    : 'Вы должны самостоятельно выбирать подходящего агента для каждой задачи.'
                  }
                </Typography>
              </Alert>
            )}
          </CardContent>
        </Card>

      {/* Список агентов */}
      {agentStatus?.mode === 'agent' && availableAgents && availableAgents.length > 0 && (
        <Card>
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
                      <ListItemIcon>
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
                                    // Переключаем состояние развернутости инструментов для этого агента
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
        <Card>
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
