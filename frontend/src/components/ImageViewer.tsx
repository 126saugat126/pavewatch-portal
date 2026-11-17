import { ActionIcon, Anchor, Group, Kbd, Modal, Paper, Skeleton, Switch, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { IconExternalLink, IconFileDownload, IconMaximize } from '@tabler/icons-react';
import { useState } from 'react';
import type { BoundingBox, Evidence } from '../api/types';
import { evidenceKindLabel } from '../lib/defects';
import { fmtBytes, fmtPercent } from '../lib/format';

/**
 * Bounding boxes are stored in ORIGINAL image pixels. The overlay is an SVG
 * whose viewBox is the original size laid exactly over the displayed image,
 * so boxes line up for the preview, the full-size view and any screen size.
 */
function BoxOverlay({ boxes, w, h }: { boxes: BoundingBox[]; w: number; h: number }) {
  const fs = Math.max(12, Math.round(Math.max(w, h) * 0.016));
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
      aria-hidden
    >
      {boxes.map((b, i) => {
        const [x0, y0, x1, y1] = b.bbox;
        const label = b.confidence != null ? `${b.label} ${fmtPercent(b.confidence)}` : b.label;
        const tw = label.length * fs * 0.58 + fs * 0.8;
        const ty = y0 - fs * 1.5 >= 0 ? y0 - fs * 1.5 : y1;
        return (
          <g key={i}>
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke="var(--pw-box-halo)" strokeWidth={5} vectorEffect="non-scaling-stroke" />
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke="var(--pw-box)" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
            <rect x={x0} y={ty} width={tw} height={fs * 1.5} fill="var(--pw-box)" rx={fs * 0.2} />
            <text x={x0 + fs * 0.4} y={ty + fs * 1.1} fontSize={fs} fontWeight={650} fill="#0b0b0b" fontFamily="system-ui, sans-serif">
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Picture({ ev, src, showBoxes, maxHeight }: { ev: Evidence; src: string; showBoxes: boolean; maxHeight?: string }) {
  const [loaded, setLoaded] = useState(false);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const w = ev.width_px ?? natural?.w ?? 16;
  const h = ev.height_px ?? natural?.h ?? 9;
  return (
    <div
      style={{
        position: 'relative',
        aspectRatio: `${w} / ${h}`,
        width: maxHeight ? `min(100%, calc(${maxHeight} * ${w / h}))` : '100%',
        margin: '0 auto',
        background: 'var(--mantine-color-default-border)',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      {!loaded && <Skeleton pos="absolute" inset={0} radius={0} />}
      <img
        src={src}
        alt={ev.caption ?? evidenceKindLabel(ev.kind)}
        decoding="async"
        onLoad={(e) => {
          setLoaded(true);
          setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
        }}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill', opacity: loaded ? 1 : 0, transition: 'opacity 150ms' }}
      />
      {showBoxes && loaded && ev.bounding_boxes.length > 0 && <BoxOverlay boxes={ev.bounding_boxes} w={w} h={h} />}
    </div>
  );
}

export function ImageViewer({
  evidence,
  showBoxes,
  onToggleBoxes,
}: {
  evidence: Evidence;
  showBoxes: boolean;
  onToggleBoxes: () => void;
}) {
  const [full, setFull] = useState(false);
  const hasBoxes = evidence.bounding_boxes.length > 0;
  return (
    <Paper withBorder radius="md" p="sm">
      <Picture key={evidence.url} ev={evidence} src={evidence.preview_url ?? evidence.url} showBoxes={showBoxes} />
      <Group justify="space-between" mt="sm" gap="xs" wrap="wrap">
        <div style={{ minWidth: 0 }}>
          <Text fz="sm" fw={600}>
            {evidenceKindLabel(evidence.kind)}
          </Text>
          <Text fz="xs" c="dimmed" truncate maw={420}>
            {[evidence.caption, evidence.width_px && `${evidence.width_px}×${evidence.height_px}px`].filter(Boolean).join(' · ')}
          </Text>
        </div>
        <Group gap="sm" wrap="nowrap">
          {hasBoxes && (
            <Switch
              size="sm"
              checked={showBoxes}
              onChange={onToggleBoxes}
              label={
                <Group gap={6} wrap="nowrap">
                  <span>Bounding boxes</span>
                  <Kbd size="xs" visibleFrom="sm">
                    B
                  </Kbd>
                </Group>
              }
            />
          )}
          <Tooltip label="View larger" withArrow>
            <ActionIcon variant="default" onClick={() => setFull(true)} aria-label="View larger">
              <IconMaximize size={16} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Open original file" withArrow>
            <ActionIcon variant="default" component="a" href={evidence.url} target="_blank" aria-label="Open original file">
              <IconExternalLink size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
      <Modal
        opened={full}
        onClose={() => setFull(false)}
        size="100%"
        centered
        title={`${evidenceKindLabel(evidence.kind)} · ${evidence.file}`}
        styles={{ body: { paddingBottom: 'var(--mantine-spacing-md)' } }}
      >
        {full && <Picture ev={evidence} src={evidence.url} showBoxes={showBoxes} maxHeight="78vh" />}
      </Modal>
    </Paper>
  );
}

export function EvidenceStrip({
  evidence,
  selected,
  onSelect,
}: {
  evidence: Evidence[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  return (
    <Group gap="xs" mt="sm" wrap="wrap" role="tablist" aria-label="Evidence">
      {evidence.map((ev, i) =>
        ev.is_image ? (
          <UnstyledButton
            key={ev.file}
            role="tab"
            aria-selected={i === selected}
            onClick={() => onSelect(i)}
            style={{
              borderRadius: 8,
              padding: 3,
              border: `2px solid ${i === selected ? 'var(--mantine-color-blue-filled)' : 'transparent'}`,
            }}
          >
            <img src={ev.thumb_url ?? ev.url} alt="" className="pw-thumb" style={{ width: 96, height: 60 }} loading="lazy" />
            <Text fz={11} ta="center" c={i === selected ? undefined : 'dimmed'} fw={i === selected ? 600 : 400}>
              {evidenceKindLabel(ev.kind)}
            </Text>
          </UnstyledButton>
        ) : (
          <Anchor key={ev.file} href={ev.url} target="_blank" fz="sm">
            <Group gap={6} wrap="nowrap">
              <IconFileDownload size={18} />
              <span>
                {evidenceKindLabel(ev.kind)} ({fmtBytes(ev.size_bytes)})
              </span>
            </Group>
          </Anchor>
        ),
      )}
    </Group>
  );
}
