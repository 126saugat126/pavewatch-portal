import { SegmentedControl, Skeleton, Text, Tooltip } from '@mantine/core';
import { useDocumentTitle } from '@mantine/hooks';
import { IconAlertOctagon, IconAlertTriangle, IconArrowRight, IconDrone } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { orgQuery, prefetchRun, runsQuery } from '../api/queries';
import type { RunSummary } from '../api/types';
import { RunStatus } from '../components/Badges';
import { Figure, SeverityBar } from '../components/Charts';
import { PageHeader } from '../components/PageHeader';
import { EmptyBlock, ErrorState } from '../components/States';
import { DEFECT_TYPES, defectMeta } from '../lib/defects';
import { fmtDate, fmtDuration, fmtRelative, fmtTime } from '../lib/format';

type SortKey = 'date' | 'findings' | 'high';

function typeSummary(counts: Record<string, number>) {
  const items = [...DEFECT_TYPES, ...Object.keys(counts).filter((t) => !(DEFECT_TYPES as readonly string[]).includes(t))]
    .filter((t) => counts[t])
    .sort((a, b) => counts[b] - counts[a])
    .map((t) => `${counts[t]} ${defectMeta(t).label.toLowerCase()}`);
  if (items.length <= 3) return items.join(' · ');
  return `${items.slice(0, 3).join(' · ')} · +${items.length - 3} more`;
}

function warningSummary(r: RunSummary) {
  const parts: string[] = [];
  if (r.data_warning_count) parts.push(`${r.data_warning_count} survey note${r.data_warning_count === 1 ? '' : 's'}`);
  if (r.findings_with_warnings) parts.push(`${r.findings_with_warnings} finding${r.findings_with_warnings === 1 ? '' : 's'} flagged`);
  return parts.join(' · ');
}

/** Tall photo tile for the most recent survey. */
function LatestRunTile({ r, to, orgId }: { r: RunSummary; to: string; orgId: string }) {
  const high = r.counts_by_severity.high ?? 0;
  const warn = r.data_warning_count + r.findings_with_warnings;
  const duration = fmtDuration(r.started_at, r.ended_at);
  return (
    <Link
      to={to}
      className={`pw-tile${r.cover_url ? ' pw-tile--photo' : ''}`}
      style={{ minHeight: 'min(640px, 80vh)' }}
      onMouseEnter={() => prefetchRun(orgId, r.run_id)}
      onFocus={() => prefetchRun(orgId, r.run_id)}
    >
      {r.cover_url && (
        <>
          <img className="pw-tile__img" src={r.cover_url} alt="" />
          <div className="pw-tile__scrim" />
        </>
      )}
      <span className="pw-eyebrow pw-dim">Latest survey · {fmtRelative(r.started_at)}</span>
      <h2 className="pw-tile__title" style={{ marginTop: 16 }}>
        {r.site_name}
      </h2>
      <p className="pw-tile__blurb">
        {fmtDate(r.started_at)}, {fmtTime(r.started_at)}
        {duration && ` · ${duration} flight`}
        {r.aircraft_id && ` · Aircraft ${r.aircraft_id}`}
        <br />
        <span className="pw-mono">{r.run_id}</span>
      </p>
      <div style={{ marginTop: 16 }}>
        <RunStatus status={r.status} />
      </div>

      <div className="pw-tile__foot" style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
        <div className="pw-figures">
          <Figure label={r.finding_count === 1 ? 'Finding' : 'Findings'} value={r.finding_count} />
          <Figure
            label="High severity"
            value={high}
            icon={high > 0 ? <IconAlertOctagon size={14} color="var(--pw-sev-high)" aria-hidden /> : undefined}
          />
          <Figure
            label="Warnings"
            value={warn}
            icon={warn > 0 ? <IconAlertTriangle size={14} color="var(--pw-status-warning)" aria-hidden /> : undefined}
          />
        </div>
        <Text fz="sm" className="pw-dim">
          {r.finding_count ? typeSummary(r.counts_by_type) : 'No defects detected.'}
          {warningSummary(r) && ` — ${warningSummary(r)}.`}
        </Text>
        <span className="pw-caps" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          Open survey <IconArrowRight size={16} />
        </span>
      </div>
    </Link>
  );
}

function RunRow({ r, to, orgId }: { r: RunSummary; to: string; orgId: string }) {
  const high = r.counts_by_severity.high ?? 0;
  const warn = warningSummary(r);
  return (
    <Link
      to={to}
      className="pw-ledger-row pw-runrow"
      onMouseEnter={() => prefetchRun(orgId, r.run_id)}
      onFocus={() => prefetchRun(orgId, r.run_id)}
    >
      <span className="pw-mono pw-dim">
        {fmtDate(r.started_at)}
        <br />
        {fmtTime(r.started_at)}
      </span>
      <span style={{ minWidth: 0 }}>
        <Text fw={500} truncate>
          {r.site_name}
          {r.status !== 'complete' && (
            <Tooltip label="Incomplete: the flight did not cover the whole planned area" withArrow>
              <IconAlertTriangle size={14} color="var(--pw-status-warning)" style={{ marginLeft: 6, verticalAlign: -2 }} aria-label="Incomplete" />
            </Tooltip>
          )}
        </Text>
        <Text fz="xs" className="pw-dim" truncate>
          <span className="pw-mono" style={{ fontSize: 12 }}>
            {r.run_id}
          </span>
          {warn && ` · ${warn}`}
        </Text>
      </span>
      <span className="pw-runrow__sev">
        <SeverityBar counts={r.counts_by_severity} />
        <Text fz="xs" className="pw-dim" mt={6}>
          {high ? `${high} high` : r.finding_count ? 'none high' : 'no findings'}
        </Text>
      </span>
      <span className="pw-stat-num" style={{ fontSize: 28, textAlign: 'right' }} aria-label={`${r.finding_count} findings`}>
        {r.finding_count}
      </span>
    </Link>
  );
}

export default function RunsPage() {
  const { orgId = '' } = useParams();
  const org = useQuery(orgQuery(orgId));
  const runs = useQuery(runsQuery(orgId));
  const [sort, setSort] = useState<SortKey>('date');
  useDocumentTitle(`${org.data?.name ?? 'Surveys'} · PaveWatch`);

  const sorted = useMemo(() => {
    const val = (r: RunSummary) =>
      sort === 'date' ? r.started_at : sort === 'findings' ? r.finding_count : (r.counts_by_severity.high ?? 0);
    return [...(runs.data ?? [])].sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      return va < vb ? 1 : va > vb ? -1 : b.started_at.localeCompare(a.started_at);
    });
  }, [runs.data, sort]);

  const runPath = (r: RunSummary) => `/orgs/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(r.run_id)}`;
  const error = org.error ?? runs.error;
  const list = runs.data ?? [];
  const latest = list[0]; // API returns newest first
  const totalFindings = list.reduce((a, r) => a + r.finding_count, 0);
  const totalHigh = list.reduce((a, r) => a + (r.counts_by_severity.high ?? 0), 0);
  const sites = new Set(list.map((r) => r.site_name)).size;

  return (
    <>
      <PageHeader
        loading={org.isPending}
        crumbs={[{ label: 'Companies', to: '/' }, { label: org.data?.name ?? '…' }]}
        title={org.data?.name}
        subtitle={
          runs.data &&
          (list.length
            ? `${list.length} survey run${list.length === 1 ? '' : 's'} across ${sites} site${sites === 1 ? '' : 's'}. Runs are listed by flight date; open one for its map, findings and data-quality notes.`
            : 'No survey runs uploaded yet.')
        }
        right={
          list.length > 0 && (
            <div className="pw-figures" style={{ color: 'var(--pw-ink)' }}>
              <Figure label="Surveys" value={list.length} />
              <Figure label="Findings" value={totalFindings} />
              <Figure
                label="High severity"
                value={totalHigh}
                icon={totalHigh > 0 ? <IconAlertOctagon size={14} color="var(--pw-sev-high)" aria-hidden /> : undefined}
              />
            </div>
          )
        }
      />
      {error ? (
        <ErrorState
          error={error}
          onRetry={() => {
            void org.refetch();
            void runs.refetch();
          }}
        />
      ) : runs.isPending ? (
        <div className="pw-grid pw-split-7-5">
          <Skeleton h={600} />
          <Skeleton h={600} />
        </div>
      ) : !latest ? (
        <EmptyBlock icon={<IconDrone size={22} />} title="No surveys yet">
          Surveys for this company will appear here after the first upload.
        </EmptyBlock>
      ) : (
        <div className="pw-grid pw-split-7-5">
          <LatestRunTile r={latest} to={runPath(latest)} orgId={orgId} />
          <section className="pw-tile pw-tile--flush" aria-label="All surveys" style={{ alignSelf: 'start' }}>
            <div className="pw-tile__head">
              <div>
                <h2 className="pw-tile__title">All surveys</h2>
                <p className="pw-tile__blurb">Findings count on the right; bar shows the severity mix.</p>
              </div>
            </div>
            <div style={{ padding: '0 var(--pw-tile-pad) 20px' }}>
              <SegmentedControl
                size="xs"
                value={sort}
                onChange={(v) => setSort(v as SortKey)}
                data={[
                  { label: 'Newest', value: 'date' },
                  { label: 'Findings', value: 'findings' },
                  { label: 'High', value: 'high' },
                ]}
                aria-label="Sort surveys"
              />
            </div>
            <div className="pw-ledger">
              {sorted.map((r) => (
                <RunRow key={r.run_id} r={r} to={runPath(r)} orgId={orgId} />
              ))}
            </div>
          </section>
        </div>
      )}
    </>
  );
}
