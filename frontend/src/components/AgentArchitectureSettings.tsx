import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
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
  TextField,
} from '@mui/material';
import {
  SmartToy as AgentIcon,
  Computer as DirectIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { getApiUrl } from '../config/api';

// Backend URL

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
}

interface MCPStatus {
  initialized: boolean;
  servers: number;
  tools: number;
  active_processes?: number;
}

interface LangGraphStatus {
  initialized: boolean;
  tools_available: number;
  memory_enabled: boolean;
  graph_compiled?: boolean;
}

export default function AgentArchitectureSettings() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [langgraphStatus, setLanggraphStatus] = useState<LangGraphStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [agentsExpanded, setAgentsExpanded] = useState(true);
  const [editingAgent, setEditingAgent] = useState<string | null>(null);
  const [editingTool, setEditingTool] = useState<string | null>(null);

  // Загрузка статуса агентной архитектуры
  const loadAgentStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(getApiUrl('/api/agent/status'));
      if (response.ok) {
        const data = await response.json();
        setAgentStatus(data);
      } else {
        throw new Error('Не удалось загрузить статус агентной архитектуры');
      }
    } catch (err) {
      setError(`Ошибка загрузки статуса: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Загрузка статуса MCP серверов
  const loadMcpStatus = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/mcp/status'));
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

  // Загрузка статуса LangGraph агента
  const loadLanggraphStatus = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/langgraph/status'));
      if (response.ok) {
        const data = await response.json();
        setLanggraphStatus(data.langgraph_status);
      } else {
        console.warn('Не удалось загрузить статус LangGraph');
      }
    } catch (err) {
      console.error('Ошибка загрузки статуса LangGraph:', err);
    }
  };

  // Загрузка списка доступных агентов
  const loadAvailableAgents = async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/agents'));
      if (response.ok) {
        const data = await response.json();
        setAvailableAgents(data.agents || []);
      } else {
        throw new Error('Не удалось загрузить список агентов');
      }
    } catch (err) {
      console.error('Ошибка загрузки агентов:', err);
    }
  };

  // Изменение режима работы
  const changeMode = async (mode: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(getApiUrl('/api/agent/mode'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });

      if (response.ok) {
        setSuccess(`Режим изменен на: ${mode === 'agent' ? 'Агентный' : 'Прямой'}`);
        await loadAgentStatus();
      } else {
        throw new Error('Не удалось изменить режим');
      }
    } catch (err) {
      setError(`Ошибка изменения режима: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Изменение статуса агента
  const toggleAgentStatus = async (agentId: string, currentStatus: boolean) => {
    try {
      setError(null);
      
      const response = await fetch(getApiUrl(`/api/agent/agents/${agentId}/status`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !currentStatus }),
      });

      if (response.ok) {
        const data = await response.json();
        setSuccess(data.message);
        // Обновляем список агентов
        await loadAvailableAgents();
        await loadAgentStatus();
      } else {
        throw new Error('Не удалось изменить статус агента');
      }
    } catch (err) {
      setError(`Ошибка изменения статуса агента: ${err}`);
    }
  };

  // Функция для редактирования инструкций
  const editToolInstruction = (agentId: string, toolName: string) => {
    setEditingAgent(agentId);
    setEditingTool(toolName);
  };

  // Функция для сохранения изменений инструкции
  const saveToolInstruction = async (agentId: string, toolName: string, newInstruction: string) => {
    try {
      // Здесь можно добавить API вызов для сохранения инструкции
      // Пока что просто обновляем локальное состояние
      setAvailableAgents(prev => prev.map(agent => {
        if (agent.agent_id === agentId) {
          return {
            ...agent,
            tools: agent.tools?.map(tool => 
              tool.name === toolName 
                ? { ...tool, instruction: newInstruction }
                : tool
            )
          };
        }
        return agent;
      }));
      
      setEditingAgent(null);
      setEditingTool(null);
      setSuccess(`Инструкция для ${toolName} обновлена`);
    } catch (err) {
      setError(`Ошибка сохранения инструкции: ${err}`);
    }
  };

  // Загрузка данных при монтировании
  useEffect(() => {
    loadAgentStatus();
    loadAvailableAgents();
    loadMcpStatus();
    loadLanggraphStatus();
  }, []);

  if (isLoading && !agentStatus) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Уведомления */}
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

      {/* Статус агентной архитектуры */}
      {agentStatus && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Статус системы
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
            <Chip
              icon={agentStatus.is_initialized ? <CheckIcon /> : <ErrorIcon />}
              label={agentStatus.is_initialized ? 'Инициализирована' : 'Не инициализирована'}
              color={agentStatus.is_initialized ? 'success' : 'error'}
              size="small"
            />
            <Chip
              label={`Режим: ${agentStatus.mode === 'agent' ? 'Агентный' : 'Прямой'}`}
              color={agentStatus.mode === 'agent' ? 'primary' : 'default'}
              size="small"
            />
            <Chip
              label={`Агентов: ${agentStatus.available_agents}`}
              color="info"
              size="small"
            />
            <Chip
              icon={agentStatus.orchestrator_active ? <CheckIcon /> : <ErrorIcon />}
              label={agentStatus.orchestrator_active ? 'Оркестратор активен' : 'Оркестратор неактивен'}
              color={agentStatus.orchestrator_active ? 'success' : 'error'}
              size="small"
            />
            {mcpStatus && (
              <Chip
                icon={mcpStatus.initialized ? <CheckIcon /> : <ErrorIcon />}
                label={`MCP: ${mcpStatus.servers} серверов, ${mcpStatus.tools} инструментов`}
                color={mcpStatus.initialized ? 'success' : 'error'}
                size="small"
              />
            )}
            {langgraphStatus && (
              <Chip
                icon={langgraphStatus.initialized ? <CheckIcon /> : <ErrorIcon />}
                label={`LangGraph: ${langgraphStatus.tools_available} инструментов`}
                color={langgraphStatus.initialized ? 'success' : 'error'}
                size="small"
              />
            )}
          </Box>
        </Box>
      )}

      {/* Выбор режима работы */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle1" gutterBottom>
          Режим работы
        </Typography>
        
        <FormControl component="fieldset" disabled={isLoading}>
          <RadioGroup
            value={agentStatus?.mode || 'direct'}
            onChange={(e) => changeMode(e.target.value)}
          >
            <FormControlLabel
              value="direct"
              control={<Radio />}
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DirectIcon color="action" />
                  <Box>
                    <Typography variant="body1">Прямой режим</Typography>
                    <Typography variant="body2" color="text.secondary">
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
                  <AgentIcon color="primary" />
                  <Box>
                    <Typography variant="body1">Агентный режим</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Использование специализированных агентов для различных задач
                    </Typography>
                  </Box>
                </Box>
              }
            />
          </RadioGroup>
        </FormControl>
      </Box>

      {/* Список доступных агентов */}
      {agentStatus?.mode === 'agent' && availableAgents.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Box 
            sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between', 
              mb: 1,
              cursor: 'pointer',
              p: 1,
              borderRadius: 1,
              '&:hover': { bgcolor: 'action.hover' }
            }}
            onClick={() => setAgentsExpanded(!agentsExpanded)}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle1">
                Доступные агенты ({availableAgents.length})
              </Typography>
              <Chip 
                label={`Активно: ${availableAgents.filter(a => a.is_active).length}`}
                size="small"
                color="primary"
              />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button
                variant="outlined"
                size="small"
                startIcon={<RefreshIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  loadAvailableAgents();
                }}
                disabled={isLoading}
              >
                Обновить
              </Button>
              <IconButton size="small">
                {agentsExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
            </Box>
          </Box>
          
          <Collapse in={agentsExpanded}>
            <List>
              {availableAgents && availableAgents.length > 0 ? availableAgents.map((agent, index) => (
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
                          
                          {/* Инструменты с инструкциями */}
                          {agent.tools && agent.tools.length > 0 && (
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}>
                                Инструменты и инструкции:
                              </Typography>
                              {agent.tools.map((tool, toolIndex) => (
                                <Box key={toolIndex} sx={{ 
                                  border: '1px solid', 
                                  borderColor: 'grey.200', 
                                  borderRadius: 1, 
                                  p: 1, 
                                  mb: 1,
                                  bgcolor: tool.is_active ? 'action.hover' : 'grey.50'
                                }}>
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                    <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                                      {tool.name}
                                    </Typography>
                                    <Chip 
                                      label={tool.is_active ? 'Активен' : 'Неактивен'} 
                                      size="small" 
                                      color={tool.is_active ? 'success' : 'default'}
                                    />
                                  </Box>
                                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                                    {tool.description}
                                  </Typography>
                                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                                    <Typography variant="caption" color="primary" sx={{ display: 'block', fontStyle: 'italic', flex: 1 }}>
                                      💡 Инструкция: {tool.instruction}
                                    </Typography>
                                    <IconButton
                                      size="small"
                                      onClick={() => editToolInstruction(agent.agent_id, tool.name)}
                                      sx={{ p: 0.5 }}
                                    >
                                      <EditIcon fontSize="small" />
                                    </IconButton>
                                  </Box>
                                </Box>
                              ))}
                            </Box>
                          )}
                          
                          {/* Примеры использования */}
                          {agent.usage_examples && agent.usage_examples.length > 0 && (
                            <Box sx={{ mb: 1 }}>
                              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}>
                                Примеры использования:
                              </Typography>
                              {agent.usage_examples.map((example, exampleIndex) => (
                                <Typography key={exampleIndex} variant="caption" color="text.secondary" sx={{ 
                                  display: 'block', 
                                  mb: 0.5,
                                  pl: 1,
                                  borderLeft: '2px solid',
                                  borderColor: 'primary.main'
                                }}>
                                  • {example}
                                </Typography>
                              ))}
                            </Box>
                          )}
                          
                          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                            {agent.capabilities && agent.capabilities.length > 0 ? agent.capabilities.map((capability) => (
                              <Chip
                                key={capability}
                                label={capability}
                                size="small"
                                variant="outlined"
                              />
                            )) : <Typography variant="caption">Нет возможностей</Typography>}
                          </Box>
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                            Инструментов: {agent.tools_count}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                  {index < availableAgents.length - 1 && <Divider />}
                </React.Fragment>
              )) : (
                <ListItem>
                  <ListItemText 
                    primary="Агенты не загружены" 
                    secondary="Нажмите 'Обновить' для загрузки списка агентов"
                  />
                </ListItem>
              )}
            </List>
          </Collapse>
        </Box>
      )}

      {/* Информация о режимах */}
      <Alert severity="info" sx={{ mb: 2 }}>
        <Typography variant="body2">
          <strong>Прямой режим:</strong> Ассистент работает напрямую с выбранной моделью без дополнительной обработки.
        </Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>Агентный режим:</strong> Ассистент использует специализированных агентов для различных задач: 
          поиск в документах, веб-поиск, вычисления, работа с памятью, MCP серверы, планирование задач.
        </Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>MCP интеграция:</strong> Подключение к внешним сервисам через Model Context Protocol 
          (файловая система, браузер, база данных, поиск).
        </Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>LangGraph:</strong> Планирование и выполнение сложных многошаговых задач с сохранением состояния.
        </Typography>
      </Alert>

      {/* Кнопка обновления */}
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={() => {
            loadAgentStatus();
            loadAvailableAgents();
            loadMcpStatus();
            loadLanggraphStatus();
          }}
          disabled={isLoading}
        >
          Обновить статус
        </Button>
      </Box>

      {/* Модальное окно для редактирования инструкций */}
      {editingAgent && editingTool && (
        <Box sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          bgcolor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <Box sx={{
            bgcolor: 'background.paper',
            p: 3,
            borderRadius: 2,
            maxWidth: 600,
            width: '90%',
            maxHeight: '80%',
            overflow: 'auto'
          }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Редактирование инструкции для {editingTool}
            </Typography>
            
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Инструкция"
              defaultValue={
                availableAgents
                  .find(agent => agent.agent_id === editingAgent)
                  ?.tools?.find(tool => tool.name === editingTool)
                  ?.instruction || ''
              }
              variant="outlined"
              sx={{ mb: 2 }}
              inputRef={(input) => {
                if (input) {
                  setTimeout(() => input.focus(), 100);
                }
              }}
            />
            
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                onClick={() => {
                  setEditingAgent(null);
                  setEditingTool(null);
                }}
              >
                Отмена
              </Button>
              <Button
                variant="contained"
                onClick={() => {
                  const input = document.querySelector('textarea') as HTMLTextAreaElement;
                  if (input) {
                    saveToolInstruction(editingAgent, editingTool, input.value);
                  }
                }}
              >
                Сохранить
              </Button>
            </Box>
          </Box>
        </Box>
      )}
    </Box>
  );
}
