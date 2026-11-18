import {
  ActionIcon,
  Alert,
  Anchor,
  CopyButton,
  Group,
  Kbd,
  Progress,
  Skeleton,
  Stack,
  Table,
  Text,
  Tooltip,
} from '@mantine/core';
import { useDocumentTitle, useHotkeys } from '@mantine/hooks';
import { IconCheck, IconChevronLeft, IconChevronRight, IconCopy, IconExternalLink, IconGps } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { findingQuery, prefetchFinding, runQuery } from '../api/queries';
import type { FindingDetail } from '../api/types';
import { Glyph, SeverityBadge } from '../components/Badges';
import { EvidenceStrip, ImageViewer } from '../components/ImageViewer';
import { MiniMap } from '../components/map/MiniMap';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/States';
import { QualityWarningsList } from '../components/Warnings';
import { SOURCE_LABEL, defectMeta, defectTitle, humanize } from '../lib/defects';
import { fmtCoord, fmtDate, fmtDateTime, fmtMeasurement, fmtNumber, sortedMeasurements } from '../lib/format';
import { findingPosition, osmLink } from '../lib/geo';

function Section({
  title,
  children,
  extra,
  raised,
}: {
  title: string;
  children: ReactNode;
  extra?: ReactNode;
  raised?: boolean;
}) {
  return (
    <section className={`pw-tile${raised ? ' pw-tile--raised' : ''}`}>
      <div className="pw-tile__head">
        <h2 className="pw-tile__title">{title}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}

function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <Table fz="sm" verticalSpacing={10}>
      <Table.Tbody>
        {rows.map(([k, v]) => (
          <Table.Tr key={k}>
            <Table.Td c="dimmed" w={150} pl={0} style={{ verticalAlign: 'top' }}>
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

function PagerButton({ id, label, pathFor, children }: { id: string | null; label: string; pathFor: (id: string) => string; children: ReactNode }) {
  if (!id) {
    return (
      <ActionIcon variant="default" size="lg" disabled aria-label={label}>
        {children}
      </ActionIcon>
    );
  }
  return (
    <Tooltip label={`${label}: ${id}`} withArrow>
      <ActionIcon variant="default" size="lg" component={Link} to={pathFor(id)} aria-label={`${label}: ${id}`}>
        {children}
      </ActionIcon>
    </Tooltip>
  );
}

function Pager({ f, pathFor }: { f: FindingDetail; pathFor: (id: string) => string }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <PagerButton id={f.prev_finding_id} label="Previous finding" pathFor={pathFor}>
        <IconChevronLeft size={18} />
      </PagerButton>
      <Text fz="sm" c="dimmed" className="pw-tabular" style={{ whiteSpace: 'nowrap' }}>
        {f.position_in_run} of {f.findings_in_run}
      </Text>
      <PagerButton id={f.next_finding_id} label="Next finding" pathFor={pathFor}>
        <IconChevronRight size={18} />
      </PagerButton>
    </Group>
  );
}

export default function FindingDetailPage() {
  const { orgId = '', runId = '', findingId = '' } = useParams();
  const navigate = useNavigate();
  const q = useQuery(findingQuery(orgId, runId, findingId));
  const run = useQuery(runQuery(orgId, runId));
  const [showBoxes, setShowBoxes] = useState(true);
  const [selected, setSelected] = useState(0);
  const f = q.data;

  useDocumentTitle(f ? `${f.finding_id} ${defectMeta(f.defect_type).label} · PaveWatch` : 'Finding · PaveWatch');

  const pathFor = (id: string) =>
    `/orgs/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(runId)}/findings/${encodeURIComponent(id)}`;
  const runPath = `/orgs/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(runId)}`;

  // New finding -> show its first image again.
  useEffect(() => setSelected(0), [findingId]);

  // Warm up neighbours (data + images) so previous/next feel instant.
  useEffect(() => {
    if (!f) return;
    if (f.next_finding_id) prefetchFinding(orgId, runId, f.next_finding_id, true);
    if (f.prev_finding_id) prefetchFinding(orgId, runId, f.prev_finding_id, true);
  }, [f, orgId, runId]);

  useHotkeys([
    ['ArrowLeft', () => f?.prev_finding_id && navigate(pathFor(f.prev_finding_id))],
    ['ArrowRight', () => f?.next_finding_id && navigate(pathFor(f.next_finding_id))],
    ['b', () => setShowBoxes((s) => !s)],
  ]);

  // Keep `position` referentially stable for the mini map (a new object would make it
  // re-fit and discard the user's zoom), so depend on the values, not the objects.
  const lat = f?.lat ?? null;
  const lon = f?.lon ?? null;
  const lx = f?.local_x_m ?? null;
  const ly = f?.local_y_m ?? null;
  const origin = run.data?.local_frame_origin;
  const hasFinding = !!f;
  const position = useMemo(
    () => (hasFinding ? findingPosition({ lat, lon, local_x_m: lx, local_y_m: ly }, origin) : null),
    [hasFinding, lat, lon, lx, ly, origin],
  );

  if (q.error) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;

  const images = f?.evidence ?? [];
  const current = images[selected] && images[selected].is_image ? images[selected] : images.find((e) => e.is_image);
  const selectedIndex = current ? images.indexOf(current) : -1;

  return (
    <>
      <PageHeader
        loading={!f}
        crumbs={[
          { label: 'Companies', to: '/' },
          { label: f?.organization.name ?? run.data?.organization.name ?? '…', to: `/orgs/${encodeURIComponent(orgId)}` },
          {
            label: run.data ? `${run.data.site_name} · ${fmtDate(run.data.started_at)}` : (f?.site_name ?? '…'),
            to: runPath,
          },
          { label: findingId },
        ]}
        title={
          f && (
            <>
              {defectTitle(f.defect_type, f.subtype)}
              <span className="pw-display__id">{f.finding_id}</span>
            </>
          )
        }
        subtitle={
          f && (
            <Stack gap="sm">
              <Group gap="sm" wrap="wrap">
                <SeverityBadge severity={f.severity} />
                <span className="pw-mono">Detected {fmtDateTime(f.detected_at)}</span>
              </Group>
              {f.description && <span>{f.description}</span>}
            </Stack>
          )
        }
        right={f && <Pager f={f} pathFor={pathFor} />}
      />

      <div className="pw-grid pw-split-7-5">
        <div style={{ minWidth: 0 }}>
          <section className="pw-tile pw-tile--flush" style={{ padding: 'calc(var(--pw-tile-pad) / 2)' }}>
          {!f ? (
            <Skeleton style={{ aspectRatio: '16 / 10' }} />
          ) : current ? (
            <>
              <ImageViewer evidence={current} showBoxes={showBoxes} onToggleBoxes={() => setShowBoxes((s) => !s)} />
              {images.length > 1 && <EvidenceStrip evidence={images} selected={selectedIndex} onSelect={setSelected} />}
            </>
          ) : (
            <div style={{ padding: 'calc(var(--pw-tile-pad) / 2)' }}>
              <Text c="dimmed" fz="sm" mb="sm">
                This finding has no images.
              </Text>
              <EvidenceStrip evidence={images} selected={-1} onSelect={() => undefined} />
            </div>
          )}
          </section>
          <Group gap={6} mt="md" visibleFrom="sm" c="dimmed" fz="xs">
            <Kbd size="xs">←</Kbd>
            <Kbd size="xs">→</Kbd>
            <span>previous / next finding</span>
            <Kbd size="xs" ml="sm">
              B
            </Kbd>
            <span>toggle boxes</span>
          </Group>
        </div>

        <div style={{ minWidth: 0 }}>
          {!f ? (
            <div className="pw-stack">
              <Skeleton h={200} />
              <Skeleton h={320} />
            </div>
          ) : (
            <div className="pw-stack">
              <Section title="Measurements">
                {Object.keys(f.measurements).length ? (
                  <>
                    <KV rows={sortedMeasurements(f.measurements).map(([k, m]) => [humanize(k), <span className="pw-stat-num" style={{ fontSize: 28 }}>{fmtMeasurement(m)}</span>])} />
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
                      flightPath={run.data?.flight_path}
                    />
                    {position.approx && (
                      <Alert color="gray" variant="light" icon={<IconGps size={18} />} p="xs">
                        <Text fz="xs">
                          No GPS fix for this finding. The position is estimated from the drone's start point and may be
                          off by a few metres.
                        </Text>
                      </Alert>
                    )}
                    <KV
                      rows={[
                        [
                          position.approx ? 'Approx. coordinates' : 'Coordinates',
                          <Group gap={4} wrap="nowrap">
                            <span>{fmtCoord(position.lat, position.lon)}</span>
                            <CopyButton value={`${position.lat.toFixed(6)}, ${position.lon.toFixed(6)}`}>
                              {({ copied, copy }) => (
                                <Tooltip label={copied ? 'Copied' : 'Copy coordinates'} withArrow>
                                  <ActionIcon variant="subtle" size="sm" onClick={copy} aria-label="Copy coordinates">
                                    {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                                  </ActionIcon>
                                </Tooltip>
                              )}
                            </CopyButton>
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
                    ['Software', run.data?.software_version ?? '—'],
                  ]}
                />
              </Section>

              <Section title="Quality warnings" raised>
                <QualityWarningsList warnings={f.quality_warnings} />
              </Section>

              <Link to={runPath} className="pw-cta pw-cta--ghost pw-caps" style={{ alignSelf: 'flex-start' }}>
                <IconChevronLeft size={16} /> All findings in this survey
              </Link>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
