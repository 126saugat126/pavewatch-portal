import { SegmentedControl, Skeleton, Text, Tooltip } from '@mantine/core';
import { useDocumentTitle } from '@mantine/hooks';
import { IconAlertOctagon, IconAlertTriangle, IconChevronRight, IconDrone, IconPhotoOff } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { orgQuery, prefetchRun, runsQuery } from '../api/queries';
import type { RunSummary } from '../api/types';
import { RunStatus } from '../components/Badges';
import { Figure, SeverityBar } from '../components/Charts';
import { PageHeader } from '../components/PageHeader';
import { EmptyBlock, ErrorState } from '../components/States';
import { fmtDate, fmtDuration, fmtTime } from '../lib/format';

type SortKey = 'date' | 'findings' | 'high';

function warningSummary(r: RunSummary) {
  const parts: string[] = [];
  if (r.data_warning_count) parts.push(`${r.data_warning_count} survey note${r.data_warning_count === 1 ? '' : 's'}`);
  if (r.findings_with_warnings) parts.push(`${r.findings_with_warnings} finding${r.findings_with_warnings === 1 ? '' : 's'} flagged`);
  return parts.join(' · ');
}

function RunRow({ r, to, orgId }: { r: RunSummary; to: string; orgId: string }) {
  const high = r.counts_by_severity.high ?? 0;
  const warn = warningSummary(r);
  const duration = fmtDuration(r.started_at, r.ended_at);
  return (
    <Link
      to={to}
      className="pw-ledger-row pw-runrow"
      onMouseEnter={() => prefetchRun(orgId, r.run_id)}
      onFocus={() => prefetchRun(orgId, r.run_id)}
    >
      {r.cover_url ? (
        <img src={r.cover_url} alt="" className="pw-runrow__thumb" loading="lazy" />
      ) : (
        <span className="pw-runrow__thumb" style={{ display: 'grid', placeItems: 'center' }} aria-hidden>
          <IconPhotoOff size={18} color="var(--pw-muted)" />
        </span>
      )}
      <span className="pw-mono pw-dim pw-runrow__when">
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
          {duration && ` · ${duration} flight`}
          {r.aircraft_id && ` · ${r.aircraft_id}`}
          {warn && ` · ${warn}`}
        </Text>
      </span>
      <span className="pw-runrow__status">
        <RunStatus status={r.status} />
      </span>
      <span className="pw-runrow__sev">
        <SeverityBar counts={r.counts_by_severity} />
        <Text fz="xs" className="pw-dim" mt={6}>
          {high ? `${high} high` : r.finding_count ? 'none high' : 'no findings'}
        </Text>
      </span>
      <span className="pw-stat-num pw-runrow__count" aria-label={`${r.finding_count} findings`}>
        {r.finding_count}
      </span>
      <IconChevronRight size={18} className="pw-runrow__go" aria-hidden />
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
  const totalFindings = list.reduce((a, r) => a + r.finding_count, 0);
  const totalHigh = list.reduce((a, r) => a + (r.counts_by_severity.high ?? 0), 0);
  const sites = new Set(list.map((r) => r.site_name)).size;

  return (
    <>
      <PageHeader
        loading={org.isPending}
        title={org.data?.name}
        subtitle={
          runs.data &&
          (list.length
            ? `${list.length} survey run${list.length === 1 ? '' : 's'} across ${sites} site${sites === 1 ? '' : 's'}. Open one for its map, findings and data-quality notes.`
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
        <Skeleton h={420} />
      ) : list.length === 0 ? (
        <EmptyBlock icon={<IconDrone size={22} />} title="No surveys yet">
          Surveys for this company will appear here after the first upload.
        </EmptyBlock>
      ) : (
        <section className="pw-tile pw-tile--flush" aria-label="All surveys">
          <div className="pw-tile__head pw-runs-head">
            <div>
              <h2 className="pw-tile__title">All surveys</h2>
              <p className="pw-tile__blurb">Newest first. The bar shows the severity mix; the number on the right is the findings count.</p>
            </div>
            <SegmentedControl
              size="xs"
              value={sort}
              onChange={(v) => setSort(v as SortKey)}
              data={[
                { label: 'Newest', value: 'date' },
                { label: 'Most findings', value: 'findings' },
                { label: 'Most high severity', value: 'high' },
              ]}
              aria-label="Sort surveys"
            />
          </div>
          <div className="pw-ledger pw-runs">
            <div className="pw-ledger-head pw-runrow pw-eyebrow" aria-hidden>
              <span />
              <span>Flown</span>
              <span>Survey</span>
              <span className="pw-runrow__status">Status</span>
              <span className="pw-runrow__sev">Severity mix</span>
              <span style={{ textAlign: 'right' }}>Findings</span>
              <span />
            </div>
            {sorted.map((r) => (
              <RunRow key={r.run_id} r={r} to={runPath(r)} orgId={orgId} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
