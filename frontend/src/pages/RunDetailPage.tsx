import {
  Badge,
  Button,
  Chip,
  Group,
  ScrollArea,
  SegmentedControl,
  Skeleton,
  Stack,
  Switch,
  Table,
  Text,
  Tooltip,
} from '@mantine/core';
import { useDocumentTitle, useMediaQuery } from '@mantine/hooks';
import {
  IconAlertOctagon,
  IconAlertTriangle,
  IconFilterOff,
  IconGps,
  IconMoodEmpty,
  IconPhotoOff,
} from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { findingsQuery, prefetchFinding, runQuery } from '../api/queries';
import type { FindingListItem, RunDetail } from '../api/types';
import { DefectLabel, RunStatus, SeverityInline } from '../components/Badges';
import { StatTile, TypeBarList } from '../components/Charts';
import { MapLegend, SurveyMap } from '../components/map/SurveyMap';
import { PageHeader } from '../components/PageHeader';
import { EmptyBlock, ErrorState } from '../components/States';
import { DataWarningsList } from '../components/Warnings';
import { DEFECT_TYPES, SEVERITIES, defectMeta, severityMeta, warningMeta } from '../lib/defects';
import { fmtDate, fmtDateTime, fmtDuration, fmtTime, measurementSummary } from '../lib/format';
import { findingPosition } from '../lib/geo';

// ------------------------------------------------------------------ filters (kept in the URL)

function useFilters() {
  const [params, setParams] = useSearchParams();
  const list = (k: string) => (params.get(k) ?? '').split(',').filter(Boolean);
  const types = list('type');
  const sevs = list('sev');
  const warnOnly = params.get('warn') === '1';
  const sort = params.get('sort') === 'severity' ? 'severity' : 'id';
  const set = useCallback(
    (k: string, v: string[] | string | null) =>
      setParams(
        (p) => {
          const n = new URLSearchParams(p);
          const val = Array.isArray(v) ? v.join(',') : v;
          if (val) n.set(k, val);
          else n.delete(k);
          return n;
        },
        { replace: true, preventScrollReset: true },
      ),
    [setParams],
  );
  const clear = () => setParams({}, { replace: true, preventScrollReset: true });
  return { types, sevs, warnOnly, sort, set, clear, active: types.length > 0 || sevs.length > 0 || warnOnly };
}

// ------------------------------------------------------------------ list row

function FindingRow({
  f,
  to,
  active,
  approx,
  onHover,
  rowRef,
  prefetch,
}: {
  f: FindingListItem;
  to: string;
  active: boolean;
  approx: boolean | null;
  onHover: (id: string | null) => void;
  rowRef: (el: HTMLAnchorElement | null) => void;
  prefetch: () => void;
}) {
  const summary = measurementSummary(f.measurements);
  return (
    <Link
      ref={rowRef}
      to={to}
      className="pw-ledger-row pw-findrow"
      data-active={active}
      onMouseEnter={() => {
        onHover(f.finding_id);
        prefetch();
      }}
      onMouseLeave={() => onHover(null)}
      onFocus={() => {
        onHover(f.finding_id);
        prefetch();
      }}
      onBlur={() => onHover(null)}
    >
      {f.thumb_url ? (
        <img src={f.thumb_url} alt="" className="pw-thumb" loading="lazy" />
      ) : (
        <div className="pw-thumb" style={{ display: 'grid', placeItems: 'center' }}>
          <IconPhotoOff size={18} color="var(--mantine-color-dimmed)" />
        </div>
      )}
      <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
        <Group gap={8} wrap="nowrap" justify="space-between">
          <DefectLabel type={f.defect_type} subtype={f.subtype} />
          <Text c="dimmed" className="pw-mono" style={{ flex: 'none', fontSize: 12 }}>
            {f.finding_id}
          </Text>
        </Group>
        <Group gap={10} wrap="nowrap" justify="space-between">
          <Text fz="xs" c="dimmed" truncate>
            {summary || fmtTime(f.detected_at)}
          </Text>
          <Group gap={8} wrap="nowrap" style={{ flex: 'none' }}>
            {approx !== false && (
              <Tooltip label={approx ? 'No GPS fix: position estimated from the start point' : 'No location available'} withArrow>
                <Badge size="xs" variant="outline" color="gray" radius="sm" leftSection={<IconGps size={10} />}>
                  {approx ? 'approx.' : 'no location'}
                </Badge>
              </Tooltip>
            )}
            {f.warning_codes.length > 0 && (
              <Tooltip label={f.warning_codes.map((c) => warningMeta(c).label).join(', ')} withArrow>
                <Group gap={2} wrap="nowrap" aria-label={`${f.warning_codes.length} quality warnings`}>
                  <IconAlertTriangle size={14} color="var(--pw-status-warning)" />
                  <Text fz="xs">{f.warning_codes.length}</Text>
                </Group>
              </Tooltip>
            )}
            <SeverityInline severity={f.severity} />
          </Group>
        </Group>
      </Stack>
    </Link>
  );
}

// ------------------------------------------------------------------ details card

function RunDetails({ run }: { run: RunDetail }) {
  const rows: [string, string][] = [
    ['Run ID', run.run_id],
    ['Started', fmtDateTime(run.started_at)],
    ['Ended', fmtDateTime(run.ended_at)],
    ['Aircraft', run.aircraft_id ?? '—'],
    ['Operator', run.operator ?? '—'],
    ['Processing software', run.software_version],
    ['Uploaded', fmtDateTime(run.ingested_at)],
  ];
  return (
    <Table fz="sm" verticalSpacing={6} withRowBorders={false}>
      <Table.Tbody>
        {rows.map(([k, v]) => (
          <Table.Tr key={k}>
            <Table.Td c="dimmed" w={160} pl={0}>
              {k}
            </Table.Td>
            <Table.Td pr={0} className="pw-mono" style={{ wordBreak: 'break-word' }}>
              {v}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

// ------------------------------------------------------------------ page

export default function RunDetailPage() {
  const { orgId = '', runId = '' } = useParams();
  const navigate = useNavigate();
  const run = useQuery(runQuery(orgId, runId));
  const findings = useQuery(findingsQuery(orgId, runId));
  const filters = useFilters();
  const [hover, setHover] = useState<{ id: string; fromMap: boolean } | null>(null);
  const rowRefs = useRef(new Map<string, HTMLAnchorElement>());
  const wide = useMediaQuery('(min-width: 75em)');
  const panelHeight = wide ? 560 : 420;

  const r = run.data;
  useDocumentTitle(r ? `${r.site_name} · ${fmtDate(r.started_at)} · PaveWatch` : 'Survey · PaveWatch');

  const all = useMemo(() => findings.data ?? [], [findings.data]);
  // Filter arrays are re-parsed from the URL on every render, so memoise on their
  // string form. A stable `shown` array keeps the map from rebuilding its markers.
  const typesKey = filters.types.join(',');
  const sevsKey = filters.sevs.join(',');
  const { warnOnly, sort } = filters;
  const shown = useMemo(() => {
    const types = typesKey ? typesKey.split(',') : [];
    const sevs = sevsKey ? sevsKey.split(',') : [];
    const out = all.filter(
      (f) =>
        (!types.length || types.includes(f.defect_type)) &&
        (!sevs.length || sevs.includes(f.severity ?? 'none')) &&
        (!warnOnly || f.warning_codes.length > 0),
    );
    if (sort === 'severity') {
      out.sort((a, b) => severityMeta(b.severity).rank - severityMeta(a.severity).rank || a.finding_id.localeCompare(b.finding_id));
    }
    return out;
  }, [all, typesKey, sevsKey, warnOnly, sort]);

  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    all.forEach((f) => (c[f.defect_type] = (c[f.defect_type] ?? 0) + 1));
    return c;
  }, [all]);
  const sevCounts = useMemo(() => {
    const c: Record<string, number> = {};
    all.forEach((f) => (c[f.severity ?? 'none'] = (c[f.severity ?? 'none'] ?? 0) + 1));
    return c;
  }, [all]);

  const findingPath = useCallback(
    (fid: string) => `/orgs/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(runId)}/findings/${encodeURIComponent(fid)}`,
    [orgId, runId],
  );
  const onMapHover = useCallback((id: string | null, fromMap: boolean) => setHover(id ? { id, fromMap } : null), []);
  const onOpen = useCallback((id: string) => navigate(findingPath(id)), [navigate, findingPath]);

  // When a marker is hovered, bring its row into view.
  useEffect(() => {
    if (hover?.fromMap) rowRefs.current.get(hover.id)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [hover]);

  const toggleType = (t: string) =>
    filters.set('type', filters.types.includes(t) ? filters.types.filter((x) => x !== t) : [...filters.types, t]);

  const error = run.error ?? findings.error;
  if (error) {
    return (
      <ErrorState
        error={error}
        onRetry={() => {
          void run.refetch();
          void findings.refetch();
        }}
      />
    );
  }

  const orgPath = `/orgs/${encodeURIComponent(orgId)}`;
  const anyApprox = all.some((f) => findingPosition(f, r?.local_frame_origin)?.approx);
  const high = sevCounts.high ?? 0;
  const presentTypes = [...DEFECT_TYPES.filter((t) => typeCounts[t]), ...Object.keys(typeCounts).filter((t) => !(DEFECT_TYPES as readonly string[]).includes(t))];

  return (
    <>
      <PageHeader
        loading={!r}
        crumbs={[
          { label: 'Companies', to: '/' },
          { label: r?.organization.name ?? '…', to: orgPath },
          { label: r ? `${r.site_name} · ${fmtDate(r.started_at)}` : '…' },
        ]}
        title={r?.site_name}
        subtitle={
          r && (
            <Group gap="xs" wrap="wrap">
              <span>
                {fmtDateTime(r.started_at)}
                {fmtDuration(r.started_at, r.ended_at) && ` · ${fmtDuration(r.started_at, r.ended_at)} flight`}
              </span>
              {r.aircraft_id && <span>· Aircraft {r.aircraft_id}</span>}
              <RunStatus status={r.status} />
            </Group>
          )
        }
      />

      {r?.status === 'incomplete' && (
        <div className="pw-tile pw-banner" role="note" style={{ marginBottom: 'var(--pw-gutter)' }}>
          <IconAlertTriangle size={22} color="var(--pw-status-warning)" aria-hidden />
          <h2 className="pw-tile__title" style={{ fontSize: 17 }}>
            Incomplete survey
          </h2>
          <Text className="pw-dim" maw="80ch">
            This flight did not cover the whole planned area. Findings are shown for the scanned part only. Unscanned
            areas are outlined on the map and listed under Survey data quality.
          </Text>
        </div>
      )}

      <div className="pw-grid pw-statstrip" style={{ marginBottom: 'calc(var(--pw-gutter) * 1.25)' }}>
        {r && findings.data ? (
          <>
            <StatTile label="Findings" value={all.length} hint={`${presentTypes.length} defect type${presentTypes.length === 1 ? '' : 's'}`} />
            <StatTile
              label="High severity"
              value={high}
              icon={<IconAlertOctagon size={16} color="var(--pw-sev-high)" aria-hidden />}
              hint={all.length ? `${Math.round((high / all.length) * 100)}% of findings` : undefined}
            />
            <StatTile
              label="Findings with warnings"
              value={r.findings_with_warnings}
              icon={<IconAlertTriangle size={16} color="var(--pw-status-warning)" aria-hidden />}
              hint="position or data quality"
            />
            <StatTile label="Survey data notes" value={r.data_warning_count} hint="e.g. areas not scanned" />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} h={168} />)
        )}
      </div>

      {/* Filters: one row above the map and list, applied to both */}
      {all.length > 0 && (
        <div className="pw-filterbar" role="group" aria-label="Filter findings">
            <div className="pw-filterbar__group">
              <span className="pw-eyebrow">Type</span>
              <Chip.Group multiple value={filters.types} onChange={(v) => filters.set('type', v)}>
                <Group gap={6} wrap="wrap">
                  {presentTypes.map((t) => (
                    <Chip key={t} value={t} size="xs" variant="outline">
                      {defectMeta(t).label} ({typeCounts[t]})
                    </Chip>
                  ))}
                </Group>
              </Chip.Group>
            </div>
            <div className="pw-filterbar__group">
              <span className="pw-eyebrow">Severity</span>
              <Chip.Group multiple value={filters.sevs} onChange={(v) => filters.set('sev', v)}>
                <Group gap={6} wrap="wrap">
                  {[...SEVERITIES, 'none' as const]
                    .filter((s) => sevCounts[s])
                    .map((s) => (
                      <Chip key={s} value={s} size="xs" variant="outline">
                        {severityMeta(s).label} ({sevCounts[s]})
                      </Chip>
                    ))}
                </Group>
              </Chip.Group>
            </div>
            <Switch
              size="sm"
              label="Only with warnings"
              checked={filters.warnOnly}
              onChange={(e) => filters.set('warn', e.currentTarget.checked ? '1' : null)}
            />
            {filters.active && (
              <Button size="compact-sm" variant="subtle" leftSection={<IconFilterOff size={14} />} onClick={filters.clear}>
                Clear filters
              </Button>
            )}
            <Text c="dimmed" ml="auto" className="pw-mono">
              {shown.length} / {all.length} shown
            </Text>
        </div>
      )}

      <div className="pw-grid pw-split-7-5">
        <div style={{ minWidth: 0 }}>
          {r && findings.data ? (
            <>
              <SurveyMap
                run={r}
                findings={shown}
                allFindings={all}
                hoveredId={hover?.id ?? null}
                onHover={onMapHover}
                onOpen={onOpen}
                height={panelHeight}
              />
              <MapLegend showApprox={anyApprox} />
            </>
          ) : (
            <Skeleton h={panelHeight} />
          )}
        </div>
        <div style={{ minWidth: 0 }}>
          {!findings.data ? (
            <Skeleton h={panelHeight} />
          ) : all.length === 0 ? (
            <EmptyBlock icon={<IconMoodEmpty size={22} />} title="No defects detected in this survey">
              Check the survey data notes below: areas that were not scanned, or scanned with poor data, can still
              contain defects.
            </EmptyBlock>
          ) : (
            <section className="pw-tile pw-tile--flush" aria-label="Findings">
              <Group justify="space-between" px="var(--pw-tile-pad)" py={20} wrap="nowrap">
                <h2 className="pw-tile__title">Findings</h2>
                <SegmentedControl
                  size="xs"
                  value={filters.sort}
                  onChange={(v) => filters.set('sort', v === 'severity' ? 'severity' : null)}
                  data={[
                    { label: 'By ID', value: 'id' },
                    { label: 'By severity', value: 'severity' },
                  ]}
                  aria-label="Sort findings"
                />
              </Group>
              <ScrollArea h={panelHeight - 76} type="auto" offsetScrollbars={false}>
                {shown.length === 0 ? (
                  <Stack align="center" p="xl" gap="xs">
                    <Text fz="sm" c="dimmed">
                      No findings match these filters.
                    </Text>
                    <Button size="xs" variant="default" onClick={filters.clear}>
                      Clear filters
                    </Button>
                  </Stack>
                ) : (
                  shown.map((f) => {
                    const pos = findingPosition(f, r?.local_frame_origin);
                    return (
                      <FindingRow
                        key={f.finding_id}
                        f={f}
                        to={findingPath(f.finding_id)}
                        active={hover?.id === f.finding_id}
                        approx={pos ? pos.approx : null}
                        onHover={(id) => setHover(id ? { id, fromMap: false } : null)}
                        prefetch={() => prefetchFinding(orgId, runId, f.finding_id, true)}
                        rowRef={(el) => {
                          if (el) rowRefs.current.set(f.finding_id, el);
                          else rowRefs.current.delete(f.finding_id);
                        }}
                      />
                    );
                  })
                )}
              </ScrollArea>
            </section>
          )}
        </div>
      </div>

      {r && findings.data && (
        <div className="pw-grid pw-split-5-7" style={{ marginTop: 'calc(var(--pw-gutter) * 1.5)' }}>
          <section className="pw-tile" style={{ alignSelf: 'start' }}>
            <div className="pw-tile__head">
              <div>
                <h2 className="pw-tile__title">Defect types</h2>
                <p className="pw-tile__blurb">Click a row to filter the map and list.</p>
              </div>
            </div>
            <TypeBarList counts={typeCounts} selected={filters.types} onToggle={toggleType} />
          </section>
          <div className="pw-stack">
            <section className="pw-tile pw-tile--raised">
              <div className="pw-tile__head">
                <div>
                  <h2 className="pw-tile__title">Survey data quality</h2>
                  <p className="pw-tile__blurb">
                    Where the data was too weak to be sure, &ldquo;no findings&rdquo; does not mean &ldquo;no defects&rdquo;.
                  </p>
                </div>
              </div>
              <DataWarningsList warnings={r.data_warnings} />
            </section>
            <section className="pw-tile">
              <div className="pw-tile__head">
                <h2 className="pw-tile__title">Survey details</h2>
              </div>
              <RunDetails run={r} />
            </section>
          </div>
        </div>
      )}
    </>
  );
}
