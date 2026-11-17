import {
  ActionIcon,
  Alert,
  Anchor,
  Button,
  CopyButton,
  Grid,
  Group,
  Kbd,
  Paper,
  Progress,
  Skeleton,
  Stack,
  Table,
  Text,
  Title,
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

function Section({ title, children, extra }: { title: string; children: ReactNode; extra?: ReactNode }) {
  return (
    <Paper withBorder radius="md" p="md">
      <Group justify="space-between" mb="sm">
        <Title order={2} fz="md">
          {title}
        </Title>
        {extra}
      </Group>
      {children}
    </Paper>
  );
}

function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <Table fz="sm" verticalSpacing={6} withRowBorders={false}>
      <Table.Tbody>
        {rows.map(([k, v]) => (
          <Table.Tr key={k}>
            <Table.Td c="dimmed" w={150} pl={0} style={{ verticalAlign: 'top' }}>
              {k}
            </Table.Td>
            <Table.Td pr={0}>{v}</Table.Td>
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

  const position = useMemo(
    () => (f ? findingPosition(f, run.data?.local_frame_origin) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [f?.finding_id, f?.lat, f?.lon, run.data?.local_frame_origin],
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
            <Group gap="sm" wrap="wrap">
              <span>{defectTitle(f.defect_type, f.subtype)}</span>
              <Text component="span" ff="monospace" fz="lg" c="dimmed" fw={500}>
                {f.finding_id}
              </Text>
            </Group>
          )
        }
        subtitle={
          f && (
            <Group gap="sm" wrap="wrap">
              <SeverityBadge severity={f.severity} />
              <span>Detected {fmtDateTime(f.detected_at)}</span>
            </Group>
          )
        }
        right={f && <Pager f={f} pathFor={pathFor} />}
      />

      <Grid gap="md">
        <Grid.Col span={{ base: 12, lg: 7 }}>
          {!f ? (
            <Skeleton radius="md" style={{ aspectRatio: '16 / 10' }} />
          ) : current ? (
            <>
              <ImageViewer evidence={current} showBoxes={showBoxes} onToggleBoxes={() => setShowBoxes((s) => !s)} />
              {images.length > 1 && <EvidenceStrip evidence={images} selected={selectedIndex} onSelect={setSelected} />}
            </>
          ) : (
            <Paper withBorder p="lg" radius="md">
              <Text c="dimmed" fz="sm" mb="sm">
                This finding has no images.
              </Text>
              <EvidenceStrip evidence={images} selected={-1} onSelect={() => undefined} />
            </Paper>
          )}
          {f?.description && (
            <Paper withBorder radius="md" p="md" mt="md">
              <Title order={2} fz="md" mb={6}>
                Description
              </Title>
              <Text fz="sm">{f.description}</Text>
            </Paper>
          )}
          <Group gap={6} mt="sm" visibleFrom="sm" c="dimmed" fz="xs">
            <Kbd size="xs">←</Kbd>
            <Kbd size="xs">→</Kbd>
            <span>previous / next finding</span>
            <Kbd size="xs" ml="sm">
              B
            </Kbd>
            <span>toggle boxes</span>
          </Group>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 5 }}>
          {!f ? (
            <Stack>
              <Skeleton h={160} radius="md" />
              <Skeleton h={260} radius="md" />
            </Stack>
          ) : (
            <Stack gap="md">
              <Section title="Measurements">
                {Object.keys(f.measurements).length ? (
                  <>
                    <KV rows={sortedMeasurements(f.measurements).map(([k, m]) => [humanize(k), <Text fz="sm" fw={600} className="pw-tabular">{fmtMeasurement(m)}</Text>])} />
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
                            <Text fz="sm" ff="monospace">
                              {fmtCoord(position.lat, position.lon)}
                            </Text>
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
                          <Progress value={f.confidence * 100} size="sm" w={110} color="var(--pw-series)" aria-label="Detection confidence" />
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

              <Section title="Quality warnings">
                <QualityWarningsList warnings={f.quality_warnings} />
              </Section>

              <Button variant="default" component={Link} to={runPath} leftSection={<IconChevronLeft size={16} />}>
                Back to all findings in this survey
              </Button>
            </Stack>
          )}
        </Grid.Col>
      </Grid>
    </>
  );
}
