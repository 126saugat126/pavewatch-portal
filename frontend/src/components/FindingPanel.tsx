import { ActionIcon, Alert, Anchor, Button, Group, Kbd, Progress, Skeleton, Stack, Table, Text, Tooltip } from '@mantine/core';
import { useHotkeys } from '@mantine/hooks';
import { IconArrowLeft, IconChevronLeft, IconChevronRight, IconCopy, IconExternalLink, IconGps, IconRefresh } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { findingQuery, prefetchFinding } from '../api/queries';
import type { FindingDetail, RunDetail } from '../api/types';
import { Glyph, SeverityBadge } from './Badges';
import { EvidenceStrip, ImageViewer } from './ImageViewer';
import { MiniMap } from './map/MiniMap';
import { QualityWarningsList } from './Warnings';
import { SOURCE_LABEL, defectTitle, humanize } from '../lib/defects';
import { fmtCoord, fmtDateTime, fmtMeasurement, fmtNumber, sortedMeasurements } from '../lib/format';
import { findingPosition, osmLink } from '../lib/geo';
import { MOTION } from '../lib/motion';
import { copyText } from '../lib/toast';

function Section({ title, children, warn }: { title: string; children: ReactNode; warn?: boolean }) {
  return (
    <section className={`pw-panel__sec${warn ? ' pw-panel__sec--warn' : ''}`}>
      <h3 className="pw-panel__h">{title}</h3>
      {children}
    </section>
  );
}

function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <Table fz="sm" verticalSpacing={8} withRowBorders={false}>
      <Table.Tbody>
        {rows.map(([k, v]) => (
          <Table.Tr key={k}>
            <Table.Td c="dimmed" w={130} pl={0} style={{ verticalAlign: 'top' }}>
              {k}
            </Table.Td>
            <Table.Td pr={0} className="pw-mono">
              {v}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function Details({ f, run, showBoxes, onToggleBoxes }: { f: FindingDetail; run: RunDetail | undefined; showBoxes: boolean; onToggleBoxes: () => void }) {
  const [selected, setSelected] = useState(0);
  const images = f.evidence;
  const current = images[selected]?.is_image ? images[selected] : images.find((e) => e.is_image);
  const selectedIndex = current ? images.indexOf(current) : -1;

  // Keep `position` referentially stable for the mini map (a new object would make it
  // re-fit and discard the user's zoom), so depend on the values, not the objects.
  const { lat, lon, local_x_m: lx, local_y_m: ly } = f;
  const origin = run?.local_frame_origin;
  const position = useMemo(() => findingPosition({ lat, lon, local_x_m: lx, local_y_m: ly }, origin), [lat, lon, lx, ly, origin]);

  return (
    <>
      <section className="pw-panel__sec">
        <Group gap={10} wrap="wrap" align="center">
          <h2 className="pw-panel__title">{defectTitle(f.defect_type, f.subtype)}</h2>
          <span className="pw-mono pw-dim">{f.finding_id}</span>
        </Group>
        <Group gap="sm" wrap="wrap" mt={10}>
          <SeverityBadge severity={f.severity} />
          <span className="pw-mono pw-dim" style={{ fontSize: 12.5 }}>
            Detected {fmtDateTime(f.detected_at)}
          </span>
        </Group>
        {f.description && (
          <Text fz="sm" mt="sm">
            {f.description}
          </Text>
        )}
      </section>

      <Section title="Evidence">
        {current ? (
          <>
            <ImageViewer evidence={current} showBoxes={showBoxes} onToggleBoxes={onToggleBoxes} />
            {images.length > 1 && <EvidenceStrip evidence={images} selected={selectedIndex} onSelect={setSelected} />}
          </>
        ) : (
          <>
            <Text c="dimmed" fz="sm" mb="sm">
              This finding has no images.
            </Text>
            <EvidenceStrip evidence={images} selected={-1} onSelect={() => undefined} />
          </>
        )}
      </Section>

      <Section title="Measurements">
        {Object.keys(f.measurements).length ? (
          <>
            <KV rows={sortedMeasurements(f.measurements).map(([k, m]) => [humanize(k), <span className="pw-stat-num" style={{ fontSize: 26 }}>{fmtMeasurement(m)}</span>])} />
            <Text fz="xs" c="dimmed" mt={4}>
              Estimated by the processing pipeline; verify on site before repair planning.
            </Text>
          </>
        ) : (
          <Text fz="sm" c="dimmed">
            No measurements were provided.
          </Text>
        )}
      </Section>

      <Section title="Location">
        {position ? (
          <Stack gap="sm">
            <MiniMap
              position={position}
              accuracyM={f.gps_accuracy_m}
              defectType={f.defect_type}
              severity={f.severity}
              flightPath={run?.flight_path}
            />
            {position.approx && (
              <Alert color="gray" variant="light" icon={<IconGps size={18} />} p="xs">
                <Text fz="xs">
                  No GPS fix for this finding. The position is estimated from the drone's start point and may be off by a few
                  metres.
                </Text>
              </Alert>
            )}
            <KV
              rows={[
                [
                  position.approx ? 'Approx. coordinates' : 'Coordinates',
                  <Group gap={4} wrap="nowrap">
                    <span>{fmtCoord(position.lat, position.lon)}</span>
                    <Tooltip label="Copy coordinates" withArrow>
                      <ActionIcon
                        variant="subtle"
                        size="sm"
                        aria-label="Copy coordinates"
                        onClick={() => copyText(`${position.lat.toFixed(6)}, ${position.lon.toFixed(6)}`, 'Coordinates copied')}
                      >
                        <IconCopy size={14} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>,
                ],
                ...(f.gps_accuracy_m != null
                  ? ([['GPS accuracy', `± ${fmtNumber(f.gps_accuracy_m, 1)} m (dashed circle)`]] as [string, ReactNode][])
                  : []),
                ...(f.local_x_m != null && f.local_y_m != null
                  ? ([['From start point', `${fmtNumber(f.local_x_m, 1)} m forward, ${fmtNumber(f.local_y_m, 1)} m right`]] as [string, ReactNode][])
                  : []),
              ]}
            />
            <Anchor href={osmLink(position.lat, position.lon)} target="_blank" fz="sm">
              <Group gap={4} wrap="nowrap">
                <span>Open in OpenStreetMap</span>
                <IconExternalLink size={14} />
              </Group>
            </Anchor>
          </Stack>
        ) : (
          <Text fz="sm" c="dimmed">
            No location is available for this finding.
          </Text>
        )}
      </Section>

      <Section title="Detection">
        <KV
          rows={[
            [
              'Defect type',
              <Group gap={6} wrap="nowrap">
                <Glyph type={f.defect_type} />
                <span>{defectTitle(f.defect_type, f.subtype)}</span>
              </Group>,
            ],
            ['Detected by', f.detection_source ? (SOURCE_LABEL[f.detection_source] ?? f.detection_source) : '—'],
            [
              'Confidence',
              f.confidence != null ? (
                <Group gap="xs" wrap="nowrap">
                  <Text fz="sm" fw={600} w={40} className="pw-tabular">
                    {Math.round(f.confidence * 100)}%
                  </Text>
                  <Progress value={f.confidence * 100} size="sm" w={110} radius={0} color="var(--pw-series)" aria-label="Detection confidence" />
                </Group>
              ) : (
                '—'
              ),
            ],
            ['Detected at', fmtDateTime(f.detected_at)],
            ['Software', run?.software_version ?? '—'],
          ]}
        />
      </Section>

      <Section title="Quality warnings" warn={f.quality_warnings.length > 0}>
        <QualityWarningsList warnings={f.quality_warnings} />
      </Section>
    </>
  );
}

/**
 * One finding, shown inside the survey page. The finding id lives in the URL, so a link opens straight to it,
 * Back closes it, and the map, list and this panel all follow the same selection.
 */
export function FindingPanel({
  orgId,
  runId,
  findingId,
  run,
  order,
  onSelect,
  onClose,
}: {
  orgId: string;
  runId: string;
  findingId: string;
  run: RunDetail | undefined;
  /** Finding ids in the order the list shows them (filters and sort applied). */
  order: string[];
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const q = useQuery(findingQuery(orgId, runId, findingId));
  const f = q.data;
  const [showBoxes, setShowBoxes] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);
  const root = useRef<HTMLElement>(null);

  // Previous / next follow what the list shows. A finding hidden by the filters falls back to run order.
  const at = order.indexOf(findingId);
  const prevId = at >= 0 ? (order[at - 1] ?? null) : (f?.prev_finding_id ?? null);
  const nextId = at >= 0 ? (order[at + 1] ?? null) : (f?.next_finding_id ?? null);
  const pos = at >= 0 ? { n: at + 1, of: order.length } : f ? { n: f.position_in_run, of: f.findings_in_run } : null;

  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [findingId]);

  // Move focus into the panel when it opens (keyboard and screen-reader users land on it).
  useEffect(() => {
    root.current?.focus({ preventScroll: true });
  }, []);

  // Warm up the neighbours (data + first image) so previous / next feel instant.
  useEffect(() => {
    if (prevId) prefetchFinding(orgId, runId, prevId, true);
    if (nextId) prefetchFinding(orgId, runId, nextId, true);
  }, [orgId, runId, prevId, nextId]);

  useHotkeys([
    ['ArrowLeft', () => prevId && onSelect(prevId)],
    ['ArrowRight', () => nextId && onSelect(nextId)],
    [
      'Escape',
      () => {
        // A full-size image dialog handles its own Escape.
        if (!document.querySelector('[role="dialog"][aria-modal="true"]')) onClose();
      },
    ],
    ['b', () => setShowBoxes((s) => !s)],
  ]);

  const step = (id: string | null, label: string, icon: ReactNode) =>
    id ? (
      <Tooltip label={`${label}: ${id}`} withArrow>
        <ActionIcon variant="default" size="lg" onClick={() => onSelect(id)} aria-label={`${label}: ${id}`}>
          {icon}
        </ActionIcon>
      </Tooltip>
    ) : (
      <ActionIcon variant="default" size="lg" disabled aria-label={label}>
        {icon}
      </ActionIcon>
    );

  return (
    <section ref={root} tabIndex={-1} className="pw-tile pw-tile--flush pw-panel" aria-label="Finding details">
      <div className="pw-panel__bar">
        <Button variant="default" size="sm" leftSection={<IconArrowLeft size={16} />} onClick={onClose}>
          All findings
        </Button>
        <Group gap="xs" wrap="nowrap">
          {step(prevId, 'Previous finding', <IconChevronLeft size={18} />)}
          <Text fz="sm" c="dimmed" className="pw-tabular" style={{ whiteSpace: 'nowrap', minWidth: 64, textAlign: 'center' }} aria-live="polite">
            {pos ? `${pos.n} of ${pos.of}` : '…'}
          </Text>
          {step(nextId, 'Next finding', <IconChevronRight size={18} />)}
        </Group>
      </div>

      <div ref={scroller} className="pw-panel__scroll">
        <motion.div
          key={findingId}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: MOTION.s.base, ease: MOTION.ease }}
        >
          {q.error ? (
            <Stack align="center" gap="sm" p="xl">
              <Text fz="sm" ta="center">
                {q.error instanceof Error ? q.error.message : 'This finding could not be loaded.'}
              </Text>
              <Button size="xs" variant="default" leftSection={<IconRefresh size={14} />} onClick={() => void q.refetch()}>
                Try again
              </Button>
            </Stack>
          ) : !f ? (
            <Stack gap="md" p="lg">
              <Skeleton h={28} w="60%" />
              <Skeleton style={{ aspectRatio: '16 / 10' }} />
              <Skeleton h={120} />
            </Stack>
          ) : (
            <>
              <Details f={f} run={run} showBoxes={showBoxes} onToggleBoxes={() => setShowBoxes((s) => !s)} />
              <Group gap={6} px="lg" py="md" visibleFrom="sm" c="dimmed" fz="xs">
                <Kbd size="xs">←</Kbd>
                <Kbd size="xs">→</Kbd>
                <span>previous / next</span>
                <Kbd size="xs" ml="sm">
                  B
                </Kbd>
                <span>boxes</span>
                <Kbd size="xs" ml="sm">
                  Esc
                </Kbd>
                <span>close</span>
              </Group>
            </>
          )}
        </motion.div>
      </div>
    </section>
  );
}
