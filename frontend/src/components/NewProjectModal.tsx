import React, { useState, useRef, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  TextField,
  Button,
  IconButton,
  Typography,
  Collapse,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Avatar,
  Tabs,
  Tab,
  Paper,
  Tooltip,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  Add as AddIcon,
  Info as InfoIcon,
  Folder as FolderIcon,
  AttachMoney as MoneyIcon,
  Assignment as AssignmentIcon,
  Edit as EditIcon,
  Favorite as FavoriteIcon,
  Luggage as LuggageIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  AttachFile as AttachFileIcon,
  Lightbulb as LightbulbIcon,
  Image as ImageIcon,
  PlayArrow as PlayArrowIcon,
  MusicNote as MusicNoteIcon,
  AutoAwesome as SparkleIcon,
  Work as BriefcaseIcon,
  Language as GlobeIcon,
  School as GraduationIcon,
  AccountBalanceWallet as WalletIcon,
  SportsBaseball as BaseballIcon,
  Restaurant as CutleryIcon,
  LocalCafe as CoffeeIcon,
  Code as CodeIcon,
  LocalFlorist as LeafIcon,
  Pets as CatIcon,
  DirectionsCar as CarIcon,
  MenuBook as BookIcon,
  Cloud as UmbrellaIcon,
  CalendarToday as CalendarIcon,
  Computer as DesktopIcon,
  VolumeUp as SpeakerIcon,
  Assessment as ChartIcon,
  Email as MailIcon,
} from '@mui/icons-material';

interface NewProjectModalProps {
  open: boolean;
  onClose: () => void;
  onCreateProject?: (projectData: ProjectData) => void;
}

export interface ProjectData {
  name: string;
  icon?: string;
  iconType?: 'icon' | 'emoji';
  iconColor?: string;
  category?: string;
  memory: 'default' | 'project-only';
  instructions: string;
  files?: File[];
}

const iconOptions = [
  { name: 'folder', icon: FolderIcon },
  { name: 'money', icon: MoneyIcon },
  { name: 'lightbulb', icon: LightbulbIcon },
  { name: 'gallery', icon: ImageIcon },
  { name: 'video', icon: PlayArrowIcon },
  { name: 'music', icon: MusicNoteIcon },
  { name: 'sparkle', icon: SparkleIcon },
  { name: 'edit', icon: EditIcon },
  { name: 'briefcase', icon: BriefcaseIcon },
  { name: 'globe', icon: GlobeIcon },
  { name: 'graduation', icon: GraduationIcon },
  { name: 'wallet', icon: WalletIcon },
  { name: 'heart', icon: FavoriteIcon },
  { name: 'baseball', icon: BaseballIcon },
  { name: 'cutlery', icon: CutleryIcon },
  { name: 'coffee', icon: CoffeeIcon },
  { name: 'code', icon: CodeIcon },
  { name: 'leaf', icon: LeafIcon },
  { name: 'cat', icon: CatIcon },
  { name: 'car', icon: CarIcon },
  { name: 'book', icon: BookIcon },
  { name: 'umbrella', icon: UmbrellaIcon },
  { name: 'calendar', icon: CalendarIcon },
  { name: 'desktop', icon: DesktopIcon },
  { name: 'speaker', icon: SpeakerIcon },
  { name: 'chart', icon: ChartIcon },
  { name: 'mail', icon: MailIcon },
  { name: 'assignment', icon: AssignmentIcon },
  { name: 'luggage', icon: LuggageIcon },
];

const colorOptions = [
  { name: 'white', value: '#ffffff' },
  { name: 'red', value: '#f44336' },
  { name: 'orange', value: '#ff9800' },
  { name: 'green', value: '#4caf50' },
  { name: 'blue', value: '#2196f3' },
  { name: 'purple', value: '#9c27b0' },
  { name: 'dark-purple', value: '#673ab7' },
];

const emojiOptions = [
  '📁', '💰', '📝', '❤️', '✈️', '🎯', '🚀', '💡', '📊', '🎨', '🏠', '🎓', '💼', '🏥', '🍕', '☕',
  '💻', '🌱', '🐱', '🐶', '🚗', '📚', '☂️', '📅', '🖥️', '🔊', '📈', '✉️', '🎮', '🎬', '🎵', '🎤',
  '🏀', '⚽', '🎾', '🏊', '🚴', '🎸', '🎹', '🎺', '🎻', '🎲', '🃏', '🎴', '🖼️', '🎭', '🎪', '🎡',
  '🌍', '🌎', '🌏', '🗺️', '🏔️', '⛰️', '🌋', '🏕️', '🏖️', '🏝️', '🏜️', '🌅', '🌄', '🌆', '🌇', '🌃',
];

export default function NewProjectModal({ open, onClose, onCreateProject }: NewProjectModalProps) {
  const theme = useTheme();
  const [projectName, setProjectName] = useState('');
  const [selectedIcon, setSelectedIcon] = useState<string | null>(null);
  const [selectedEmoji, setSelectedEmoji] = useState<string | null>(null);
  const [iconType, setIconType] = useState<'icon' | 'emoji'>('icon');
  const [selectedColor, setSelectedColor] = useState('#ffffff');
  const [memory, setMemory] = useState<'default' | 'project-only'>('default');
  const [instructions, setInstructions] = useState('');
  const [showIconPicker, setShowIconPicker] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [iconTab, setIconTab] = useState(0);
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const iconPickerRef = useRef<HTMLDivElement>(null);

  // Закрываем попап при клике вне его
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (iconPickerRef.current && !iconPickerRef.current.contains(event.target as Node)) {
        setShowIconPicker(false);
      }
    };

    if (showIconPicker) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showIconPicker]);

  const handleClose = () => {
    setProjectName('');
    setSelectedIcon(null);
    setSelectedEmoji(null);
    setIconType('icon');
    setSelectedColor('#ffffff');
    setMemory('default');
    setInstructions('');
    setShowIconPicker(false);
    setShowAdvanced(false);
    setIconTab(0);
    setFiles([]);
    onClose();
  };

  const handleCreate = () => {
    if (!projectName.trim()) return;

    const projectData: ProjectData = {
      name: projectName.trim(),
      icon: iconType === 'icon' ? selectedIcon || undefined : selectedEmoji || undefined,
      iconType,
      iconColor: selectedColor,
      category: undefined,
      memory,
      instructions: instructions.trim(),
      files: files.length > 0 ? files : undefined,
    };

    onCreateProject?.(projectData);
    handleClose();
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const newFiles = Array.from(event.target.files);
      setFiles([...files, ...newFiles]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const renderIcon = () => {
    if (iconType === 'emoji' && selectedEmoji) {
      return (
        <Avatar
          sx={{
            width: 48,
            height: 48,
            bgcolor: selectedColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : selectedColor,
            fontSize: 24,
          }}
        >
          {selectedEmoji}
        </Avatar>
      );
    }
    if (iconType === 'icon' && selectedIcon) {
      const IconComponent = iconOptions.find(opt => opt.name === selectedIcon)?.icon || FolderIcon;
      return (
        <Avatar
          sx={{
            width: 48,
            height: 48,
            bgcolor: selectedColor === '#ffffff' ? 'rgba(255,255,255,0.1)' : selectedColor,
            color: selectedColor === '#ffffff' ? 'white' : 'white',
          }}
        >
          <IconComponent />
        </Avatar>
      );
    }
    return (
      <Avatar
        sx={{
          width: 48,
          height: 48,
          bgcolor: 'rgba(255,255,255,0.1)',
          color: 'white',
        }}
      >
        <AddIcon />
      </Avatar>
    );
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: theme.palette.mode === 'dark' ? '#1e1e1e' : '#ffffff',
          borderRadius: 2,
          minHeight: '500px',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 2,
        }}
      >
        <Typography variant="h6" fontWeight="600">
          Новый проект
        </Typography>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <Box
            sx={{
              position: 'relative',
            }}
          >
            <IconButton
              onClick={() => setShowIconPicker(!showIconPicker)}
              sx={{
                width: 56,
                height: 56,
                p: 0,
                '&:hover': {
                  opacity: 0.8,
                },
              }}
            >
              {renderIcon()}
            </IconButton>

            {/* Попап выбора иконки/эмодзи */}
            {showIconPicker && (
              <Paper
                ref={iconPickerRef}
                sx={{
                  position: 'absolute',
                  top: 64,
                  left: 0,
                  zIndex: 1000,
                  p: 2,
                  minWidth: 400,
                  bgcolor: theme.palette.mode === 'dark' ? '#2d2d2d' : '#ffffff',
                  boxShadow: 4,
                  borderRadius: 2,
                }}
              >
                <Tabs value={iconTab} onChange={(_, v) => setIconTab(v)}>
                  <Tab label="Икона" />
                  <Tab label="Эмодзи" />
                </Tabs>

                {iconTab === 0 && (
                  <Box>
                    <Box
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(6, 1fr)',
                        gap: 1,
                        mt: 2,
                        mb: 2,
                        maxHeight: 300,
                        overflowY: 'auto',
                      }}
                    >
                      {iconOptions.map((option) => {
                        const IconComponent = option.icon;
                        return (
                          <IconButton
                            key={option.name}
                            onClick={() => {
                              setSelectedIcon(option.name);
                              setSelectedEmoji(null);
                              setIconType('icon');
                              setShowIconPicker(false);
                            }}
                            sx={{
                              width: 48,
                              height: 48,
                              border: selectedIcon === option.name ? '2px solid' : '1px solid',
                              borderColor: selectedIcon === option.name ? 'primary.main' : 'divider',
                              '&:hover': {
                                bgcolor: 'action.hover',
                              },
                            }}
                          >
                            <IconComponent sx={{ fontSize: 24 }} />
                          </IconButton>
                        );
                      })}
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                      {colorOptions.map((color) => (
                        <Box
                          key={color.name}
                          onClick={() => setSelectedColor(color.value)}
                          sx={{
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            bgcolor: color.value,
                            border: selectedColor === color.value ? '2px solid' : '1px solid',
                            borderColor: selectedColor === color.value ? 'primary.main' : 'divider',
                            cursor: 'pointer',
                            '&:hover': {
                              transform: 'scale(1.1)',
                            },
                            transition: 'transform 0.2s',
                          }}
                        />
                      ))}
                    </Box>
                  </Box>
                )}

                {iconTab === 1 && (
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(6, 1fr)',
                      gap: 1,
                      mt: 2,
                      mb: 2,
                      maxHeight: 300,
                      overflowY: 'auto',
                    }}
                  >
                    {emojiOptions.map((emoji) => (
                      <IconButton
                        key={emoji}
                        onClick={() => {
                          setSelectedEmoji(emoji);
                          setSelectedIcon(null);
                          setIconType('emoji');
                          setShowIconPicker(false);
                        }}
                        sx={{
                          width: 48,
                          height: 48,
                          border: selectedEmoji === emoji ? '2px solid' : '1px solid',
                          borderColor: selectedEmoji === emoji ? 'primary.main' : 'divider',
                          fontSize: 24,
                          '&:hover': {
                            bgcolor: 'action.hover',
                          },
                        }}
                      >
                        {emoji}
                      </IconButton>
                    ))}
                  </Box>
                )}
              </Paper>
            )}
          </Box>

          <TextField
            fullWidth
            placeholder="Название проекта"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            sx={{
              '& .MuiOutlinedInput-root': {
                color: theme.palette.mode === 'dark' ? 'white' : 'text.primary',
              },
            }}
          />
        </Box>

        {/* Расширенные настройки */}
        <Box sx={{ mb: 2 }}>
          <Button
            fullWidth
            onClick={() => setShowAdvanced(!showAdvanced)}
            endIcon={showAdvanced ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            sx={{
              justifyContent: 'space-between',
              textTransform: 'none',
              color: 'text.primary',
            }}
          >
            Расширенные настройки
          </Button>

          <Collapse in={showAdvanced}>
            <Box sx={{ mt: 2, pl: 2 }}>
              {/* Память */}
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" fontWeight="500">
                      Память
                    </Typography>
                    <Tooltip title="Выберите, имеет ли этот проект собственную изолированную память или использует общую память.">
                      <InfoIcon sx={{ fontSize: 16, opacity: 0.7 }} />
                    </Tooltip>
                  </Box>
                  <FormControl size="small" sx={{ minWidth: 200 }}>
                    <Select
                      value={memory}
                      onChange={(e) => setMemory(e.target.value as 'default' | 'project-only')}
                      sx={{
                        '& .MuiSelect-select': {
                          color: theme.palette.mode === 'dark' ? 'white' : 'text.primary',
                        },
                      }}
                    >
                      <MenuItem value="default">По умолчанию</MenuItem>
                      <MenuItem value="project-only">Только для проекта</MenuItem>
                    </Select>
                  </FormControl>
                </Box>
                <Typography variant="caption" sx={{ mt: 0.5, display: 'block', opacity: 0.7 }}>
                  {memory === 'default'
                    ? 'Чаты будут получать доступ к вашим общим воспоминаниям'
                    : 'Воспоминания изолированы в рамках этого проекта'}
                </Typography>
              </Box>

              {/* Инструкции */}
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Typography variant="body2" fontWeight="500">
                    Инструкции
                  </Typography>
                  <Tooltip title="Определите конкретную роль, тон и формат ответа, которые вы ожидаете от AstraChat в рамках этого проекта.">
                    <InfoIcon sx={{ fontSize: 16, opacity: 0.7 }} />
                  </Tooltip>
                </Box>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  placeholder="Что ИИ должен знать об этом проекте? (например, конкретные правила, тон или форматирование)"
                  value={instructions}
                  onChange={(e) => {
                    if (e.target.value.length <= 1000) {
                      setInstructions(e.target.value);
                    }
                  }}
                  helperText={`${instructions.length}/1000`}
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      color: theme.palette.mode === 'dark' ? 'white' : 'text.primary',
                    },
                  }}
                />
              </Box>

              {/* Файлы */}
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Typography variant="body2" fontWeight="500">
                    Файлы
                  </Typography>
                  <Tooltip title="Загрузите документы, изображения или код, чтобы использовать их в качестве базы знаний для AstraChat в рамках этого проекта.">
                    <InfoIcon sx={{ fontSize: 16, opacity: 0.7 }} />
                  </Tooltip>
                </Box>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                />
                <Button
                  variant="outlined"
                  startIcon={<AttachFileIcon />}
                  onClick={() => fileInputRef.current?.click()}
                  sx={{ mb: 1 }}
                >
                  Добавить файлы
                </Button>
                {files.length > 0 && (
                  <Box sx={{ mt: 1 }}>
                    {files.map((file, index) => (
                      <Chip
                        key={index}
                        label={file.name}
                        onDelete={() => handleRemoveFile(index)}
                        sx={{ mr: 1, mb: 1 }}
                      />
                    ))}
                  </Box>
                )}
              </Box>
            </Box>
          </Collapse>
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={handleClose} sx={{ textTransform: 'none' }}>
          Отменить
        </Button>
        <Button
          onClick={handleCreate}
          variant="contained"
          disabled={!projectName.trim()}
          sx={{
            textTransform: 'none',
            bgcolor: !projectName.trim() ? 'rgba(255,255,255,0.1)' : 'primary.main',
            color: !projectName.trim() ? 'rgba(255,255,255,0.5)' : 'white',
            '&:hover': {
              bgcolor: !projectName.trim() ? 'rgba(255,255,255,0.1)' : 'primary.dark',
            },
          }}
        >
          Создать проект
        </Button>
      </DialogActions>
    </Dialog>
  );
}

