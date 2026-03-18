import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  Checkbox,
  FormControlLabel,
  Switch,
  Tooltip,
  CircularProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Avatar,
  Chip,
  Alert,
  InputLabel,
  InputAdornment,
  Popover,
  alpha,
} from '@mui/material';
import {
  Add as AddIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
  Upload as UploadIcon,
  SmartToy as AgentIcon,
  Code as CodeIcon,
  Search as SearchIcon,
  AttachFile as AttachIcon,
  Extension as ToolsIcon,
  ContactSupport as SupportIcon,
  Settings as SettingsIcon,
  History as VersionIcon,
  Save as SaveIcon,
  Description as FileIcon,
  PictureAsPdf as PdfIcon,
  TableChart as ExcelIcon,
  TextSnippet as TxtIcon,
  Article as DocxIcon,
  HelpOutline as HelpIcon,
  AutoAwesome as SparkleIcon,
  CheckBox as CheckBoxIcon,
  CheckBoxOutlineBlank as CheckBoxBlankIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { getApiUrl, API_ENDPOINTS } from '../config/api';
import { useAuth } from '../contexts/AuthContext';
import { useAppActions } from '../contexts/AppContext';
import { applyAgentModelAndSettings } from '../utils/applyAgentServer';
import {
  DROPDOWN_CHEVRON_SX,
  getDropdownPopoverPaperSx,
  DROPDOWN_ITEM_HOVER_BG,
  DROPDOWN_ITEM_SX,
  FORM_FIELD_INPUT_SX,
  FORM_FIELD_TRIGGER_SX,
  FORM_FIELD_TRIGGER_VALUE_TYPOGRAPHY_SX,
  FIELD_TEXT,
  FIELD_PLACEHOLDER,
} from '../constants/menuStyles';
import ModelParametersModal, { type ModelParamsState } from './ModelParametersModal';
import { MODEL_SETTINGS_DEFAULT, type ModelSettingsState } from '../constants/modelSettingsStyles';

// ─── Types ───────────────────────────────────────────────────────────────────

interface KbDocument {
  id: number;
  filename: string;
  created_at: string | null;
  size: number | null;
  file_type: string | null;
}

interface Agent {
  id: number;
  name: string;
  description?: string;
  system_prompt: string;
  config?: Record<string, any>;
  tools?: string[];
  author_id: string;
  author_name: string;
  is_public: boolean;
  tags?: any[];
}

interface AgentConstructorPanelProps {
  isDarkMode: boolean;
  isOpen: boolean;
}

const CATEGORIES = ['Общий', 'Код', 'Письмо', 'Анализ', 'Исследование', 'Обучение', 'Другое'];

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Цвет квадратика-иконки по типу файла. */
function getFileIconBg(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return '#e53935';
  if (['docx', 'doc'].includes(ext)) return '#1976d2';
  if (['xlsx', 'xls', 'csv'].includes(ext)) return '#43a047';
  if (ext === 'txt') return '#607d8b';
  return '#5c6bc0';
}

/** Подпись типа файла для карточки. */
function getFileTypeLabel(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return 'PDF';
  if (['docx', 'doc'].includes(ext)) return 'Word';
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'Excel';
  if (ext === 'txt') return 'TXT';
  return 'File';
}

const fileIconSx = { fontSize: 18, color: 'white' };

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return <PdfIcon sx={fileIconSx} />;
  if (['xlsx', 'xls', 'csv'].includes(ext)) return <ExcelIcon sx={fileIconSx} />;
  if (ext === 'txt') return <TxtIcon sx={fileIconSx} />;
  if (['docx', 'doc'].includes(ext)) return <DocxIcon sx={fileIconSx} />;
  return <FileIcon sx={fileIconSx} />;
}

function shortFileName(name: string, max = 22): string {
  if (name.length <= max) return name;
  const ext = name.includes('.') ? '.' + name.split('.').pop() : '';
  return name.slice(0, max - ext.length - 3) + '...' + ext;
}

// ─── Label with tooltip ───────────────────────────────────────────────────────

function FieldLabel({ text, help, required }: { text: string; help?: string; required?: boolean }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.85)', fontWeight: 500, fontSize: '0.8rem' }}>
        {text}{required && <span style={{ color: '#f44336', marginLeft: 2 }}>*</span>}
      </Typography>
      {help && (
        <Tooltip title={help} placement="top" arrow>
          <HelpIcon sx={{ fontSize: 13, color: 'rgba(255,255,255,0.35)', cursor: 'help' }} />
        </Tooltip>
      )}
    </Box>
  );
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.7rem' }}>
      {children}
    </Typography>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AgentConstructorPanel({ isDarkMode, isOpen }: AgentConstructorPanelProps) {
  const { token } = useAuth();
  const { showNotification } = useAppActions();

  // Agent list & selection
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<number | 'new'>('new');
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);

  // Form fields
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('Общий');
  const [instructions, setInstructions] = useState('');
  const [model, setModel] = useState('');
  const [availableModels, setAvailableModels] = useState<string[]>([]);

  // Capabilities
  const [codeInterpreter, setCodeInterpreter] = useState(false);
  const [webSearch, setWebSearch] = useState(false);

  // Artifacts
  const [artifactsEnabled, setArtifactsEnabled] = useState(false);
  const [shadcnEnabled, setShadcnEnabled] = useState(false);
  const [userPromptMode, setUserPromptMode] = useState(false);

  // File search (KB)
  const [fileSearchEnabled, setFileSearchEnabled] = useState(false);
  const [kbDocuments, setKbDocuments] = useState<KbDocument[]>([]);
  const [isLoadingKb, setIsLoadingKb] = useState(false);
  const [isUploadingKb, setIsUploadingKb] = useState(false);

  // Support contacts
  const [supportName, setSupportName] = useState('');
  const [supportEmail, setSupportEmail] = useState('');

  // Saving
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showModelParamsPanel, setShowModelParamsPanel] = useState(false);
  const [modelParams, setModelParams] = useState<Partial<ModelParamsState>>({});
  const [agentModelSettings, setAgentModelSettings] = useState<ModelSettingsState>({ ...MODEL_SETTINGS_DEFAULT });
  const [agentSearchQuery, setAgentSearchQuery] = useState('');
  const [agentPopoverAnchor, setAgentPopoverAnchor] = useState<HTMLElement | null>(null);
  const [categoryPopoverAnchor, setCategoryPopoverAnchor] = useState<HTMLElement | null>(null);

  const kbFileInputRef = useRef<HTMLInputElement>(null);

  // ─── Load agents ────────────────────────────────────────────────────────────

  const loadAgents = useCallback(async () => {
    setIsLoadingAgents(true);
    try {
      const url = getApiUrl('/api/agents/my/agents');
      const resp = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) return;
      const data = await resp.json();
      setAgents(data.agents || []);
    } catch (e) {
      // silent
    } finally {
      setIsLoadingAgents(false);
    }
  }, [token]);

  const loadModels = useCallback(async () => {
    try {
      const url = getApiUrl('/api/models');
      const resp = await fetch(url);
      if (!resp.ok) return;
      const data = await resp.json();
      const names: string[] = (data.models || data || []).map((m: any) =>
        typeof m === 'string' ? m : m.name || m.path || ''
      ).filter(Boolean);
      setAvailableModels(names);
    } catch (e) {
      // silent
    }
  }, []);

  const loadKbDocuments = useCallback(async () => {
    setIsLoadingKb(true);
    try {
      const url = getApiUrl(API_ENDPOINTS.KB_DOCUMENTS_LIST);
      const resp = await fetch(url);
      if (!resp.ok) return;
      const data = await resp.json();
      setKbDocuments(data.documents || data || []);
    } catch (e) {
      // silent
    } finally {
      setIsLoadingKb(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadAgents();
      loadModels();
      loadKbDocuments();
    }
  }, [isOpen, loadAgents, loadModels, loadKbDocuments]);

  // ─── Load selected agent into form ──────────────────────────────────────────

  useEffect(() => {
    if (selectedAgentId === 'new') {
      resetForm();
      return;
    }
    const agent = agents.find(a => a.id === selectedAgentId);
    if (!agent) return;
    setName(agent.name);
    setDescription(agent.description || '');
    setInstructions(agent.system_prompt || '');
    const cfg = agent.config || {};
    setCategory(cfg.category || 'Общий');
    setModel(cfg.model || '');
    setModelParams((cfg.model_params as Partial<ModelParamsState>) || {});
    setAgentModelSettings(
      (cfg.model_settings as Partial<ModelSettingsState>)
        ? { ...MODEL_SETTINGS_DEFAULT, ...(cfg.model_settings as Partial<ModelSettingsState>) }
        : { ...MODEL_SETTINGS_DEFAULT }
    );
    setCodeInterpreter(!!cfg.code_interpreter);
    setWebSearch(!!cfg.web_search);
    setArtifactsEnabled(!!cfg.artifacts_enabled);
    setShadcnEnabled(!!cfg.shadcn_enabled);
    setUserPromptMode(!!cfg.user_prompt_mode);
    setFileSearchEnabled(!!cfg.file_search_enabled);
    setSupportName(cfg.support_name || '');
    setSupportEmail(cfg.support_email || '');
  }, [selectedAgentId, agents]);

  function resetForm() {
    setName('');
    setDescription('');
    setCategory('Общий');
    setInstructions('');
    setModel(availableModels[0] || '');
    setModelParams({});
    setAgentModelSettings({ ...MODEL_SETTINGS_DEFAULT });
    setCodeInterpreter(false);
    setWebSearch(false);
    setArtifactsEnabled(false);
    setShadcnEnabled(false);
    setUserPromptMode(false);
    setFileSearchEnabled(false);
    setSupportName('');
    setSupportEmail('');
  }

  // ─── KB Upload ───────────────────────────────────────────────────────────────

  const handleKbUpload = async (files: FileList) => {
    if (!files.length) return;
    setIsUploadingKb(true);
    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const url = getApiUrl(API_ENDPOINTS.KB_DOCUMENTS_UPLOAD);
        await fetch(url, { method: 'POST', body: formData });
      } catch (e) { /* silent */ }
    }
    setIsUploadingKb(false);
    await loadKbDocuments();
  };

  const handleKbDelete = async (docId: number) => {
    try {
      const url = `${getApiUrl(API_ENDPOINTS.KB_DOCUMENTS_DELETE)}/${docId}`;
      await fetch(url, { method: 'DELETE' });
      setKbDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (e) { /* silent */ }
  };

  // ─── Save agent ──────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!name.trim()) {
      setSaveError('Заполните обязательное поле: Имя');
      return;
    }
    setSaveError('');
    setIsSaving(true);
    const payload = {
      name: name.trim(),
      description: description.trim() || undefined,
      system_prompt: instructions.trim() || 'Системные инструкции не заданы.',
      is_public: false,
      tools: [
        ...(codeInterpreter ? ['code_interpreter'] : []),
        ...(webSearch ? ['web_search'] : []),
      ],
      config: {
        category,
        model: model.replace(/^1lm-svc:\/\//i, 'llm-svc://').replace(/\s+/g, ''),
        model_params: modelParams,
        model_settings: agentModelSettings,
        code_interpreter: codeInterpreter,
        web_search: webSearch,
        artifacts_enabled: artifactsEnabled,
        shadcn_enabled: shadcnEnabled,
        user_prompt_mode: userPromptMode,
        file_search_enabled: fileSearchEnabled,
        support_name: supportName,
        support_email: supportEmail,
      },
      tag_ids: [],
      new_tags: [],
    };

    try {
      const isEdit = selectedAgentId !== 'new';
      const url = isEdit
        ? getApiUrl(`/api/agents/${selectedAgentId}`)
        : getApiUrl('/api/agents/');
      const method = isEdit ? 'PUT' : 'POST';
      const resp = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || resp.statusText);
      }
      const result = await resp.json();
      if (!isEdit && result.agent_id) {
        setSelectedAgentId(result.agent_id);
      }
      const savedId = isEdit ? selectedAgentId : result.agent_id;
      if (savedId && savedId !== 'new') {
        try {
          localStorage.setItem('active_agent_id', String(savedId));
          localStorage.setItem('active_agent_name', name.trim());
          localStorage.setItem('active_agent_prompt', instructions.trim() || 'Системные инструкции не заданы.');
        } catch {
          /* */
        }
        window.dispatchEvent(new CustomEvent('agentSelected'));
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      await loadAgents();

      if (token) {
        const sp = instructions.trim() || 'Системные инструкции не заданы.';
        const applied = await applyAgentModelAndSettings(token, {
          system_prompt: sp,
          model_path: model.trim() || null,
          model_settings: agentModelSettings as unknown as Record<string, unknown>,
        });
        if (applied.ok && model.trim()) {
          showNotification('success', 'Модель и настройки применены на сервере — ответы в чате пойдут с этой моделью');
        } else if (applied.ok && !model.trim()) {
          showNotification('info', 'Промпт и настройки применены; укажите модель в параметрах — пока чат без смены модели');
        } else if (!applied.ok) {
          showNotification('warning', `Агент сохранён; не удалось применить на сервер: ${applied.message}`);
        }
      }
    } catch (e: any) {
      setSaveError(e.message);
    } finally {
      setIsSaving(false);
    }
  };

  // ─── Delete agent ────────────────────────────────────────────────────────────

  const handleDelete = async () => {
    if (selectedAgentId === 'new') return;
    if (!window.confirm(`Удалить агента «${name}»?`)) return;
    try {
      const url = getApiUrl(`/api/agents/${selectedAgentId}`);
      await fetch(url, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setSelectedAgentId('new');
      resetForm();
      await loadAgents();
    } catch (e) { /* silent */ }
  };

  // ─── "Use agent" — sets system prompt as context ─────────────────────────────

  const handleUseAgent = () => {
    if (selectedAgentId === 'new') return;
    const agent = agents.find(a => a.id === selectedAgentId);
    if (!agent) return;
    // Store selected agent in localStorage so chat can pick it up
    localStorage.setItem('active_agent_id', String(agent.id));
    localStorage.setItem('active_agent_prompt', agent.system_prompt);
    localStorage.setItem('active_agent_name', agent.name);
    window.dispatchEvent(new CustomEvent('agentSelected', { detail: agent }));
  };

  if (!isOpen) return null;

  const agentIdStr = selectedAgentId !== 'new'
    ? `agent_${String(selectedAgentId).padStart(6, '0')}`
    : '';

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        color: 'white',
      }}
    >
      {showModelParamsPanel ? (
        <ModelParametersModal
          variant="panel"
          open={true}
          onClose={() => setShowModelParamsPanel(false)}
          currentModel={model}
          availableModels={availableModels}
          initialParams={Object.keys(modelParams).length ? modelParams : undefined}
          initialModelSettings={agentModelSettings}
          onSaveModelSettings={setAgentModelSettings}
          onSave={(newModel, params) => {
            setModel(newModel);
            setModelParams(params ?? {});
            setShowModelParamsPanel(false);
          }}
        />
      ) : (
        <>
      {/* ── Выбор агента ─────────────────────────────────────────────────────── */}
      <Box sx={{ px: 2, pt: 1.5, pb: 1 }}>
        {/* Кнопка «Агенты» */}
        <Box
          onClick={e => setAgentPopoverAnchor(e.currentTarget)}
          sx={FORM_FIELD_TRIGGER_SX}
        >
          <Typography sx={{ ...FORM_FIELD_TRIGGER_VALUE_TYPOGRAPHY_SX, fontWeight: 600 }}>
            Агенты
          </Typography>
          <ExpandMoreIcon
            sx={{ ...DROPDOWN_CHEVRON_SX, transform: Boolean(agentPopoverAnchor) ? 'rotate(180deg)' : 'none' }}
          />
        </Box>

        {/* Всплывающий список — стиль из constants/menuStyles */}
        <Popover
          open={Boolean(agentPopoverAnchor)}
          anchorEl={agentPopoverAnchor}
          onClose={() => { setAgentPopoverAnchor(null); setAgentSearchQuery(''); }}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          slotProps={{
            paper: { sx: getDropdownPopoverPaperSx(agentPopoverAnchor) },
          }}
        >
          {/* Строка поиска */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              px: 1.5,
              py: 0.9,
              gap: 1,
              borderBottom: '1px solid rgba(255,255,255,0.07)',
            }}
          >
            <SearchIcon sx={{ color: 'rgba(255,255,255,0.35)', fontSize: 16, flexShrink: 0 }} />
            <Box
              component="input"
              autoFocus
              placeholder="Поиск агентов по имени"
              value={agentSearchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAgentSearchQuery(e.target.value)}
              sx={{
                flex: 1,
                bgcolor: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'white',
                fontSize: '0.82rem',
                '&::placeholder': { color: 'rgba(255,255,255,0.3)' },
              }}
            />
          </Box>

          {/* Список */}
          <Box
            sx={{
              maxHeight: 220,
              overflowY: 'auto',
              py: 0.5,
              '&::-webkit-scrollbar': { width: 3 },
              '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.12)', borderRadius: 2 },
            }}
          >
            {/* «+ Новый агент» */}
            <Box
              onClick={() => { setSelectedAgentId('new'); setAgentPopoverAnchor(null); setAgentSearchQuery(''); }}
              sx={{
                ...DROPDOWN_ITEM_SX,
                color: selectedAgentId === 'new' ? 'white' : 'rgba(255,255,255,0.5)',
                fontStyle: 'italic',
                bgcolor: selectedAgentId === 'new' ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
              }}
            >
              + Новый агент
            </Box>

            {/* Существующие агенты */}
            {(agents || [])
              .filter(a => !agentSearchQuery.trim() || a.name.toLowerCase().includes(agentSearchQuery.toLowerCase()))
              .map(a => (
                <Box
                  key={a.id}
                  onClick={() => { setSelectedAgentId(a.id); setAgentPopoverAnchor(null); setAgentSearchQuery(''); }}
                  sx={{
                    ...DROPDOWN_ITEM_SX,
                    color: 'rgba(255,255,255,0.9)',
                    fontWeight: selectedAgentId === a.id ? 600 : 400,
                    bgcolor: selectedAgentId === a.id ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                  }}
                >
                  {a.name}
                </Box>
              ))}

            {/* Ничего не найдено */}
            {agentSearchQuery.trim() && (agents || []).filter(a => a.name.toLowerCase().includes(agentSearchQuery.toLowerCase())).length === 0 && (
              <Box sx={{ px: 1.5, py: 1.5, fontSize: '0.78rem', color: 'rgba(255,255,255,0.3)', textAlign: 'center' }}>
                Не найдено
              </Box>
            )}
          </Box>
        </Popover>
      </Box>

      {/* ── Scrollable form ─────────────────────────────────────────────────── */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5,
        '&::-webkit-scrollbar': { width: 4 },
        '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.15)', borderRadius: 2 },
      }}>

        {/* Кнопка добавления аватара — по центру, как на скриншоте */}
        <Box sx={{ display: 'flex', justifyContent: 'center', width: '100%', mb: 1.5 }}>
          <Avatar
            sx={{
              width: 64,
              height: 64,
              bgcolor: 'rgba(33,150,243,0.25)',
              border: '1px dashed rgba(255,255,255,0.25)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              '&:hover': { bgcolor: 'rgba(33,150,243,0.35)' },
            }}
          >
            <AddIcon sx={{ fontSize: 32, color: 'rgba(255,255,255,0.5)' }} />
          </Avatar>
        </Box>

        {/* Имя и Описание — такие же по размеру, как поля «Имя» и «Электронная почта» в контактах поддержки */}
        <Box>
          <FieldLabel text="Имя" required />
          <TextField
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Необязательно: имя агента"
            size="small"
            fullWidth
            sx={FORM_FIELD_INPUT_SX}
            inputProps={{ maxLength: 255 }}
          />
          {agentIdStr && (
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.68rem', display: 'block', mt: 0.25 }}>
              {agentIdStr}
            </Typography>
          )}
        </Box>

        <Box>
          <FieldLabel text="Описание" />
          <TextField
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Необязательно: описание вашего агента"
            size="small"
            fullWidth
            sx={FORM_FIELD_INPUT_SX}
          />
        </Box>

        {/* Category — стиль из constants/menuStyles */}
        <Box>
          <FieldLabel text="Категория" required />
          <Box
            onClick={e => setCategoryPopoverAnchor(e.currentTarget)}
            sx={FORM_FIELD_TRIGGER_SX}
          >
            <Typography sx={FORM_FIELD_TRIGGER_VALUE_TYPOGRAPHY_SX}>
              {category}
            </Typography>
            <ExpandMoreIcon
              sx={{ ...DROPDOWN_CHEVRON_SX, transform: Boolean(categoryPopoverAnchor) ? 'rotate(180deg)' : 'none' }}
            />
          </Box>
          <Popover
            open={Boolean(categoryPopoverAnchor)}
            anchorEl={categoryPopoverAnchor}
            onClose={() => setCategoryPopoverAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
            transformOrigin={{ vertical: 'top', horizontal: 'left' }}
            slotProps={{
              paper: { sx: getDropdownPopoverPaperSx(categoryPopoverAnchor) },
            }}
          >
            <Box sx={{ py: 0.5 }}>
              {CATEGORIES.map(c => (
                <Box
                  key={c}
                  onClick={() => { setCategory(c); setCategoryPopoverAnchor(null); }}
                  sx={{
                    ...DROPDOWN_ITEM_SX,
                    color: category === c ? 'white' : 'rgba(255,255,255,0.9)',
                    fontWeight: category === c ? 600 : 400,
                    bgcolor: category === c ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                  }}
                >
                  {c}
                </Box>
              ))}
            </Box>
          </Popover>
        </Box>

        {/* Instructions */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
            <FieldLabel text="Инструкции" />
            <Button
              size="small"
              startIcon={<SparkleIcon sx={{ fontSize: '0.8rem !important' }} />}
              sx={{
                fontSize: '0.7rem',
                textTransform: 'none',
                color: 'rgba(255,255,255,0.5)',
                py: 0,
                minWidth: 0,
                '&:hover': { color: 'rgba(255,255,255,0.8)', bgcolor: 'transparent' },
              }}
            >
              Переменные
            </Button>
          </Box>
          <TextField
            value={instructions}
            onChange={e => setInstructions(e.target.value)}
            placeholder="Системные инструкции, используемые агентом"
            size="small"
            fullWidth
            multiline
            minRows={3}
            maxRows={8}
            sx={FORM_FIELD_INPUT_SX}
          />
        </Box>

        {/* Model — по клику открывается окно параметров модели */}
        <Box>
          <FieldLabel text="Модель" required />
          <Box
            onClick={() => setShowModelParamsPanel(true)}
            sx={{
              ...FORM_FIELD_TRIGGER_SX,
              color: model ? FIELD_TEXT : FIELD_PLACEHOLDER,
            }}
          >
            {model ? (model.replace('llm-svc://', '').split('/').pop() || model) : 'Выберите модель'}
          </Box>
        </Box>

        {/* ── Capabilities ─────────────────────────────────────────────────── */}
        <Box>
          <SectionHeader>Возможности</SectionHeader>

          {/* Code interpreter */}
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.72rem', display: 'block', mb: 0.5 }}>
              API Интерпретатора кода
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={codeInterpreter}
                  onChange={e => setCodeInterpreter(e.target.checked)}
                  size="small"
                  sx={{ color: 'rgba(255,255,255,0.4)', '&.Mui-checked': { color: '#2196f3' }, p: 0.5 }}
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.75)', fontSize: '0.78rem' }}>Выполнить код</Typography>
                  <Tooltip title="Выполнять Python-код в изолированной среде" arrow>
                    <HelpIcon sx={{ fontSize: 12, color: 'rgba(255,255,255,0.25)' }} />
                  </Tooltip>
                </Box>
              }
              sx={{ ml: 0, '& .MuiFormControlLabel-label': { ml: 0.5 } }}
            />

            {codeInterpreter && (
              <Button
                size="small"
                startIcon={<UploadIcon sx={{ fontSize: '0.85rem !important' }} />}
                fullWidth
                sx={{
                  mt: 0.5,
                  fontSize: '0.72rem',
                  textTransform: 'none',
                  color: 'rgba(255,255,255,0.6)',
                  border: '1px dashed rgba(255,255,255,0.2)',
                  py: 0.75,
                  justifyContent: 'flex-start',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.35)' },
                }}
              >
                Загрузить для Интерпретатора кода
              </Button>
            )}
          </Box>

          {/* Web search */}
          <Box>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.72rem', display: 'block', mb: 0.5 }}>
              Веб-поиск
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={webSearch}
                  onChange={e => setWebSearch(e.target.checked)}
                  size="small"
                  sx={{ color: 'rgba(255,255,255,0.4)', '&.Mui-checked': { color: '#2196f3' }, p: 0.5 }}
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.75)', fontSize: '0.78rem' }}>Веб-поиск</Typography>
                  <Tooltip title="Поиск актуальной информации в интернете" arrow>
                    <HelpIcon sx={{ fontSize: 12, color: 'rgba(255,255,255,0.25)' }} />
                  </Tooltip>
                </Box>
              }
              sx={{ ml: 0, '& .MuiFormControlLabel-label': { ml: 0.5 } }}
            />
          </Box>

          {/* File context */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75 }}>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.72rem' }}>
                Контекст файла
              </Typography>
              <Tooltip title="Файл, доступный агенту как постоянный контекст" arrow>
                <HelpIcon sx={{ fontSize: 12, color: 'rgba(255,255,255,0.25)' }} />
              </Tooltip>
            </Box>
            <Button
              size="small"
              startIcon={<AttachIcon sx={{ fontSize: '0.85rem !important' }} />}
              fullWidth
              sx={{
                fontSize: '0.72rem',
                textTransform: 'none',
                color: 'rgba(255,255,255,0.6)',
                border: '1px dashed rgba(255,255,255,0.2)',
                py: 0.75,
                justifyContent: 'flex-start',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.35)' },
              }}
            >
              Загрузить файл контекста
            </Button>
          </Box>
        </Box>

        {/* ── Artifacts ────────────────────────────────────────────────────── */}
        <Box>
          <SectionHeader>Артефакты</SectionHeader>
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            {[
              { label: 'Включить артефакты', help: 'Артефакты — отдельно отображаемый контент (код, таблицы)', val: artifactsEnabled, set: setArtifactsEnabled },
              { label: 'Включить компоненты shadcn/ui', help: 'Разрешить использование shadcn/ui компонентов', val: shadcnEnabled, set: setShadcnEnabled },
              { label: 'Режим пользовательского промта', help: 'Расширенный пользовательский режим', val: userPromptMode, set: setUserPromptMode },
            ].map(({ label, help, val, set }) => (
              <Box key={label} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.78rem' }}>{label}</Typography>
                  <Tooltip title={help} arrow>
                    <HelpIcon sx={{ fontSize: 12, color: 'rgba(255,255,255,0.25)' }} />
                  </Tooltip>
                </Box>
                <Switch
                  checked={val}
                  onChange={e => set(e.target.checked)}
                  size="small"
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': { color: '#2196f3' },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: 'rgba(33,150,243,0.5)' },
                    '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.2)' },
                  }}
                />
              </Box>
            ))}
          </Box>
        </Box>

        {/* ── File Search (KB) ─────────────────────────────────────────────── */}
        <Box sx={{ minWidth: 0 }}>
          <SectionHeader>Поиск файлов</SectionHeader>

          <Box sx={{ mt: 1, minWidth: 0 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={fileSearchEnabled}
                  onChange={e => setFileSearchEnabled(e.target.checked)}
                  size="small"
                  sx={{ color: 'rgba(255,255,255,0.4)', '&.Mui-checked': { color: '#2196f3' }, p: 0.5 }}
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.75)', fontSize: '0.78rem' }}>Включить поиск файлов</Typography>
                  <Tooltip title="Поиск по загруженным документам Базы Знаний" arrow>
                    <HelpIcon sx={{ fontSize: 12, color: 'rgba(255,255,255,0.25)' }} />
                  </Tooltip>
                </Box>
              }
              sx={{ ml: 0, '& .MuiFormControlLabel-label': { ml: 0.5 } }}
            />

            {/* KB files list — сетка по 2 карточки в ряд, цвет по типу файла */}
            {isLoadingKb ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                <CircularProgress size={16} sx={{ color: 'rgba(255,255,255,0.4)' }} />
              </Box>
            ) : kbDocuments.length > 0 ? (
              <Box
                sx={{
                  mt: 0.5,
                  mb: 1,
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 0.75,
                  minWidth: 0,
                  width: '100%',
                }}
              >
                {kbDocuments.map(doc => (
                  <Box
                    key={doc.id}
                    sx={{
                      position: 'relative',
                      borderRadius: 1,
                      bgcolor: '#2a2d3a',
                      border: '1px solid rgba(255,255,255,0.08)',
                      p: 0.5,
                      minWidth: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                    }}
                  >
                    {/* Крестик удаления */}
                    <IconButton
                      size="small"
                      onClick={() => handleKbDelete(doc.id)}
                      sx={{
                        position: 'absolute',
                        top: 3,
                        right: 3,
                        p: 0.2,
                        color: 'rgba(255,255,255,0.45)',
                        '&:hover': { color: '#ef5350', bgcolor: 'rgba(239,83,80,0.12)' },
                      }}
                    >
                      <CloseIcon sx={{ fontSize: 11 }} />
                    </IconButton>

                    {/* Иконка + имя в строку */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0, pr: 2 }}>
                      {/* Цветной квадратик с иконкой */}
                      <Box
                        sx={{
                          width: 32,
                          height: 32,
                          borderRadius: 1,
                          bgcolor: getFileIconBg(doc.filename),
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        {getFileIcon(doc.filename)}
                      </Box>

                      {/* Имя + тип */}
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Tooltip
                          title={doc.filename}
                          placement="top"
                          slotProps={{
                            tooltip: {
                              sx: {
                                bgcolor: 'rgba(42, 45, 58, 0.98)',
                                color: '#fff',
                                borderRadius: 3,
                                border: '1px solid rgba(255,255,255,0.12)',
                                fontSize: '0.75rem',
                                fontWeight: 500,
                                py: 0.75,
                                px: 1.25,
                                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                              },
                            },
                          }}
                        >
                          <Typography
                            variant="caption"
                            noWrap
                            component="span"
                            sx={{ color: 'white', fontSize: '0.68rem', display: 'block', fontWeight: 500, lineHeight: 1.3 }}
                          >
                            {shortFileName(doc.filename, 16)}
                          </Typography>
                        </Tooltip>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.62rem', lineHeight: 1.2 }}>
                          {getFileTypeLabel(doc.filename)}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                ))}
              </Box>
            ) : null}

            {/* Upload button */}
            <input
              ref={kbFileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.csv"
              style={{ display: 'none' }}
              onChange={e => { if (e.target.files) handleKbUpload(e.target.files); e.target.value = ''; }}
            />
            <Button
              size="small"
              startIcon={isUploadingKb ? <CircularProgress size={13} sx={{ color: 'inherit' }} /> : <UploadIcon sx={{ fontSize: '0.85rem !important' }} />}
              fullWidth
              disabled={isUploadingKb}
              onClick={() => kbFileInputRef.current?.click()}
              sx={{
                mt: 0.5,
                fontSize: '0.72rem',
                textTransform: 'none',
                color: 'rgba(255,255,255,0.6)',
                border: '1px dashed rgba(255,255,255,0.2)',
                py: 0.75,
                justifyContent: 'flex-start',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.35)' },
                '&:disabled': { color: 'rgba(255,255,255,0.3)', borderColor: 'rgba(255,255,255,0.1)' },
              }}
            >
              {isUploadingKb ? 'Загрузка...' : 'Загрузить для поиска по файлам'}
            </Button>
          </Box>
        </Box>

        {/* ── Tools and Actions ────────────────────────────────────────────── */}
        <Box>
          <SectionHeader>Tools and Actions</SectionHeader>
          <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
            <Button
              size="small"
              startIcon={<ToolsIcon sx={{ fontSize: '0.85rem !important' }} />}
              sx={{
                flex: 1,
                fontSize: '0.72rem',
                textTransform: 'none',
                color: 'rgba(255,255,255,0.6)',
                border: '1px solid rgba(255,255,255,0.15)',
                py: 0.75,
                '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.3)' },
              }}
            >
              Добавить инструменты
            </Button>
            <Button
              size="small"
              startIcon={<SparkleIcon sx={{ fontSize: '0.85rem !important' }} />}
              sx={{
                flex: 1,
                fontSize: '0.72rem',
                textTransform: 'none',
                color: 'rgba(255,255,255,0.6)',
                border: '1px solid rgba(255,255,255,0.15)',
                py: 0.75,
                '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.3)' },
              }}
            >
              Добавить действия
            </Button>
          </Box>
        </Box>

        {/* ── Support Contacts ─────────────────────────────────────────────── */}
        <Box>
          <SectionHeader>Контакты службы поддержки</SectionHeader>
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Box>
              <FieldLabel text="Имя" />
              <TextField
                value={supportName}
                onChange={e => setSupportName(e.target.value)}
                placeholder="Имя контактного лица"
                size="small"
                fullWidth
                sx={FORM_FIELD_INPUT_SX}
              />
            </Box>
            <Box>
              <FieldLabel text="Электронная почта" />
              <TextField
                value={supportEmail}
                onChange={e => setSupportEmail(e.target.value)}
                placeholder="support@example.com"
                size="small"
                fullWidth
                type="email"
                sx={FORM_FIELD_INPUT_SX}
              />
            </Box>
          </Box>
        </Box>

        {/* Spacer */}
        <Box sx={{ pb: 1 }} />
      </Box>

      {/* ── Footer buttons ──────────────────────────────────────────────────── */}
      <Box sx={{ px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>

        {/* Errors / Success */}
        {saveError && (
          <Typography variant="caption" sx={{ color: '#ef5350', fontSize: '0.72rem', textAlign: 'center' }}>
            {saveError}
          </Typography>
        )}
        {saveSuccess && (
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" sx={{ color: '#66bb6a', fontSize: '0.72rem', display: 'block' }}>
              Агент успешно сохранён
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.65rem', display: 'block', mt: 0.25 }}>
              Данные сохранены в базу приложения (PostgreSQL, таблица agents). Агент отображается в блоке «Агенты» выше — выберите его для редактирования или нажмите «Использовать в чате».
            </Typography>
          </Box>
        )}

        {/* Advanced + Version */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            size="small"
            startIcon={<SettingsIcon sx={{ fontSize: '0.85rem !important' }} />}
            fullWidth
            sx={{
              fontSize: '0.72rem',
              textTransform: 'none',
              color: 'rgba(255,255,255,0.5)',
              border: '1px solid rgba(255,255,255,0.12)',
              py: 0.6,
              '&:hover': { bgcolor: 'rgba(255,255,255,0.06)' },
            }}
          >
            Расширенные
          </Button>
          <Button
            size="small"
            startIcon={<VersionIcon sx={{ fontSize: '0.85rem !important' }} />}
            fullWidth
            sx={{
              fontSize: '0.72rem',
              textTransform: 'none',
              color: 'rgba(255,255,255,0.5)',
              border: '1px solid rgba(255,255,255,0.12)',
              py: 0.6,
              '&:hover': { bgcolor: 'rgba(255,255,255,0.06)' },
            }}
          >
            Версия
          </Button>
        </Box>

        {/* Delete + Save */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          {selectedAgentId !== 'new' && (
            <Tooltip title="Удалить агента">
              <IconButton
                size="small"
                onClick={handleDelete}
                sx={{
                  color: 'rgba(255,255,255,0.4)',
                  border: '1px solid rgba(255,255,255,0.12)',
                  borderRadius: 1,
                  p: 0.75,
                  '&:hover': { color: '#ef5350', borderColor: 'rgba(239,83,80,0.4)', bgcolor: 'rgba(239,83,80,0.08)' },
                }}
              >
                <DeleteIcon sx={{ fontSize: '1rem' }} />
              </IconButton>
            </Tooltip>
          )}
          <Button
            fullWidth
            variant="contained"
            startIcon={isSaving ? <CircularProgress size={14} sx={{ color: 'white' }} /> : <SaveIcon sx={{ fontSize: '0.9rem !important' }} />}
            onClick={handleSave}
            disabled={isSaving}
            sx={{
              bgcolor: '#2e7d32',
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.82rem',
              py: 0.9,
              '&:hover': { bgcolor: '#388e3c' },
              '&:disabled': { bgcolor: 'rgba(46,125,50,0.4)', color: 'rgba(255,255,255,0.5)' },
            }}
          >
            {isSaving ? 'Сохраняю...' : 'Сохранить'}
          </Button>
        </Box>
      </Box>
        </>
      )}
    </Box>
  );
}
