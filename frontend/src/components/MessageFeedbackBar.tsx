import React, { useCallback, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  ThumbUpAltOutlined as ThumbUpOutlinedIcon,
  ThumbUp as ThumbUpIcon,
  ThumbDownAltOutlined as ThumbDownOutlinedIcon,
  ThumbDown as ThumbDownIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import type { MessageFeedback } from '../constants/messageFeedback';
import { DISLIKE_FEEDBACK_TAGS } from '../constants/messageFeedback';

export interface MessageFeedbackBarProps {
  feedback?: MessageFeedback | null;
  disabled?: boolean;
  isDarkMode?: boolean;
  onLike: () => void | Promise<void>;
  onDislikeSubmit: (payload: { tags: string[]; comment: string }) => void | Promise<void>;
  onClear: () => void | Promise<void>;
  /** Компактный стиль для multi-LLM колонок */
  compact?: boolean;
}

const MessageFeedbackBar: React.FC<MessageFeedbackBarProps> = ({
  feedback,
  disabled = false,
  isDarkMode = false,
  onLike,
  onDislikeSubmit,
  onClear,
  compact = false,
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const rating = feedback?.rating ?? null;

  const iconSx = useMemo(
    () => ({
      opacity: 0.7,
      p: 0.5,
      borderRadius: '6px',
      minWidth: compact ? '26px' : '28px',
      width: compact ? '26px' : '28px',
      height: compact ? '26px' : '28px',
      '&:hover:not(:disabled)': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
      '&:disabled': { opacity: 0.4 },
      '& .MuiSvgIcon-root': {
        fontSize: compact ? '16px !important' : '18px !important',
        width: compact ? '16px !important' : '18px !important',
        height: compact ? '16px !important' : '18px !important',
      },
    }),
    [compact],
  );

  const openDislikeDialog = useCallback(() => {
    setSelectedTags(feedback?.rating === 'dislike' ? [...(feedback.tags || [])] : []);
    setComment(feedback?.rating === 'dislike' ? feedback.comment || '' : '');
    setDialogOpen(true);
  }, [feedback]);

  const handleLikeClick = useCallback(async () => {
    if (disabled || submitting) return;
    setSubmitting(true);
    try {
      if (rating === 'like') {
        await onClear();
      } else {
        await onLike();
      }
    } finally {
      setSubmitting(false);
    }
  }, [disabled, submitting, rating, onClear, onLike]);

  const handleDislikeClick = useCallback(() => {
    if (disabled || submitting) return;
    if (rating === 'dislike') {
      void (async () => {
        setSubmitting(true);
        try {
          await onClear();
        } finally {
          setSubmitting(false);
        }
      })();
      return;
    }
    openDislikeDialog();
  }, [disabled, submitting, rating, onClear, openDislikeDialog]);

  const canSubmitDislike = selectedTags.length > 0 || comment.trim().length > 0;

  const handleSubmitDislike = useCallback(async () => {
    if (!canSubmitDislike || submitting) return;
    setSubmitting(true);
    try {
      await onDislikeSubmit({ tags: selectedTags, comment: comment.trim() });
      setDialogOpen(false);
    } finally {
      setSubmitting(false);
    }
  }, [canSubmitDislike, submitting, onDislikeSubmit, selectedTags, comment]);

  const toggleTag = (tagId: string) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((t) => t !== tagId) : [...prev, tagId],
    );
  };

  return (
    <>
      <Tooltip title={rating === 'like' ? 'Убрать оценку' : 'Хороший ответ'}>
        <span>
          <IconButton
            size="small"
            onClick={() => void handleLikeClick()}
            disabled={disabled || submitting}
            className="message-like-button"
            data-theme={isDarkMode ? 'dark' : 'light'}
            sx={{
              ...iconSx,
              color: rating === 'like' ? 'success.main' : undefined,
              opacity: rating === 'like' ? 1 : iconSx.opacity,
            }}
            aria-label="Хороший ответ"
          >
            {rating === 'like' ? <ThumbUpIcon /> : <ThumbUpOutlinedIcon />}
          </IconButton>
        </span>
      </Tooltip>

      <Tooltip title={rating === 'dislike' ? 'Убрать оценку' : 'Плохой ответ'}>
        <span>
          <IconButton
            size="small"
            onClick={handleDislikeClick}
            disabled={disabled || submitting}
            className="message-dislike-button"
            data-theme={isDarkMode ? 'dark' : 'light'}
            sx={{
              ...iconSx,
              color: rating === 'dislike' ? 'error.main' : undefined,
              opacity: rating === 'dislike' ? 1 : iconSx.opacity,
            }}
            aria-label="Плохой ответ"
          >
            {rating === 'dislike' ? <ThumbDownIcon /> : <ThumbDownOutlinedIcon />}
          </IconButton>
        </span>
      </Tooltip>

      <Dialog
        open={dialogOpen}
        onClose={() => !submitting && setDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 3,
            bgcolor: isDarkMode ? 'grey.900' : 'background.paper',
          },
        }}
      >
        <DialogTitle
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            pr: 1,
            pb: 1,
          }}
        >
          <Typography component="span" variant="h6" sx={{ fontWeight: 600 }}>
            Поделиться отзывом
          </Typography>
          <IconButton
            size="small"
            onClick={() => setDialogOpen(false)}
            disabled={submitting}
            aria-label="Закрыть"
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>

        <DialogContent sx={{ pt: 1 }}>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              mb: 2,
            }}
          >
            {DISLIKE_FEEDBACK_TAGS.map((tag) => {
              const selected = selectedTags.includes(tag.id);
              return (
                <Chip
                  key={tag.id}
                  label={tag.label}
                  clickable
                  onClick={() => toggleTag(tag.id)}
                  variant={selected ? 'filled' : 'outlined'}
                  color={selected ? 'primary' : 'default'}
                  sx={{
                    borderRadius: '999px',
                    fontSize: '0.8125rem',
                    height: 'auto',
                    py: 0.75,
                    '& .MuiChip-label': { whiteSpace: 'normal' },
                  }}
                />
              );
            })}
          </Box>

          <TextField
            multiline
            minRows={3}
            fullWidth
            placeholder="Поделитесь подробностями (необязательно)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={submitting}
            inputProps={{ maxLength: 2000 }}
            sx={{
              '& .MuiOutlinedInput-root': { borderRadius: 2 },
            }}
          />

          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mt: 1.5,
              px: 1.5,
              py: 1,
              borderRadius: 2,
              bgcolor: isDarkMode ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
              lineHeight: 1.45,
            }}
          >
            Отправка отзыва поможет улучшить ответы ассистента в этом и следующих диалогах.
            Предпочтения учитываются моделью при генерации.
          </Typography>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button
            variant="contained"
            onClick={() => void handleSubmitDislike()}
            disabled={!canSubmitDislike || submitting}
            sx={{ borderRadius: 999, px: 3, textTransform: 'none' }}
          >
            Отправить
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default MessageFeedbackBar;
