import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import AuthenticatedInlineImage from './AuthenticatedInlineImage';
import InlineDocAttachmentChip from './InlineDocAttachmentChip';
import { formatFileSize } from '../utils/inlineImage';

export interface InlineAttachmentDisplayItem {
  name: string;
  contentType: 'text' | 'image';
  /** Для изображений: data URL, blob URL или URL MinIO */
  imageSrc?: string;
  size?: number;
}

type InlineAttachmentsVariant = 'input' | 'message';

interface InlineAttachmentsListProps {
  files: InlineAttachmentDisplayItem[];
  isDarkMode?: boolean;
  variant?: InlineAttachmentsVariant;
  onRemove?: (index: number) => void;
  onImageExpand?: (resolvedSrc: string, name: string) => void;
  sx?: object;
}

export default function InlineAttachmentsList({
  files,
  isDarkMode = false,
  variant = 'input',
  onRemove,
  onImageExpand,
  sx,
}: InlineAttachmentsListProps) {
  if (files.length === 0) return null;

  const isMessage = variant === 'message';
  const isInput = variant === 'input';

  const inlineImageRemoveSx = {
    position: 'absolute',
    top: 4,
    right: 4,
    p: 0.25,
    minWidth: 0,
    width: 22,
    height: 22,
    bgcolor: 'rgba(0, 0, 0, 0.55)',
    color: 'white',
    '&:hover': { bgcolor: 'rgba(0, 0, 0, 0.75)', color: 'white' },
  };

  const imageBorder = isMessage
    ? '1px solid rgba(255,255,255,0.35)'
    : `1px solid ${isDarkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)'}`;

  const renderImageThumb = (file: InlineAttachmentDisplayItem, index: number) => {
    const src = file.imageSrc || '';
    const canExpand = Boolean(onImageExpand && src);

    const imageSx = isMessage
      ? {
          maxHeight: 200,
          maxWidth: 280,
          width: 'auto',
          height: 'auto',
          borderRadius: '8px',
          objectFit: 'cover' as const,
          border: '2px solid rgba(255,255,255,0.3)',
          display: 'block',
          cursor: canExpand ? 'zoom-in' : 'default',
          transition: 'transform 0.15s, box-shadow 0.15s',
          '&:hover': canExpand
            ? {
                transform: 'scale(1.03)',
                boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              }
            : undefined,
        }
      : {
          width: '100%',
          height: '100%',
          borderRadius: 1.5,
          objectFit: 'cover' as const,
          display: 'block',
          border: imageBorder,
          cursor: canExpand ? 'zoom-in' : 'default',
        };

    const thumb = src.startsWith('data:') || src.startsWith('blob:') ? (
      <Box
        component="img"
        src={src}
        alt={file.name}
        onClick={canExpand ? () => onImageExpand!(src, file.name) : undefined}
        sx={imageSx}
      />
    ) : (
      <AuthenticatedInlineImage
        src={src}
        alt={file.name}
        onExpand={canExpand ? (resolvedSrc) => onImageExpand!(resolvedSrc, file.name) : undefined}
        sx={imageSx}
      />
    );

    const content = isMessage ? (
      thumb
    ) : (
      <Box sx={{ position: 'relative', width: 72, height: 72, flexShrink: 0 }}>
        {thumb}
        {onRemove && (
          <IconButton size="small" onClick={() => onRemove(index)} sx={inlineImageRemoveSx}>
            <CloseIcon sx={{ fontSize: '0.85rem' }} />
          </IconButton>
        )}
      </Box>
    );

    if (canExpand) {
      return (
        <Tooltip key={`inline-img-${file.name}-${index}`} title="Нажмите, чтобы увеличить" placement="top" arrow>
          {content}
        </Tooltip>
      );
    }

    return <React.Fragment key={`inline-img-${file.name}-${index}`}>{content}</React.Fragment>;
  };

  const indexedFiles = files.map((file, index) => ({ file, index }));
  const imageItems = indexedFiles.filter(({ file }) => file.contentType === 'image' && file.imageSrc);
  const docItems = indexedFiles.filter(({ file }) => file.contentType !== 'image');

  return (
    <Box sx={sx}>
      {imageItems.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: docItems.length > 0 ? 1 : 0 }}>
          {imageItems.map(({ file, index }) => renderImageThumb(file, index))}
        </Box>
      )}

      {docItems.length > 0 && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: isInput
              ? { xs: 'minmax(0, 1fr)', sm: 'repeat(2, minmax(0, 1fr))' }
              : 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 1,
            width: '100%',
            maxWidth: isInput ? 560 : '100%',
          }}
        >
          {docItems.map(({ file, index }) => (
            <InlineDocAttachmentChip
              key={`inline-doc-${file.name}-${index}`}
              name={file.name}
              size={file.size}
              sizeLabel={typeof file.size === 'number' && file.size > 0 ? formatFileSize(file.size) : undefined}
              isDarkMode={isDarkMode}
              isMessage={isMessage}
              onRemove={onRemove ? () => onRemove(index) : undefined}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}
