import { Skeleton, TextInput } from '@mantine/core';
import { useDocumentTitle } from '@mantine/hooks';
import { IconAlertOctagon, IconArrowUpRight, IconBuildingCommunity, IconSearch, IconX } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { orgsQuery, queryClient, runsQuery } from '../api/queries';
import type { OrganizationSummary } from '../api/types';
import { Figure } from '../components/Charts';
import { PageHeader } from '../components/PageHeader';
import { EmptyBlock, ErrorState } from '../components/States';
import { fmtDate, fmtRelative } from '../lib/format';

function CompanyTile({ org }: { org: OrganizationSummary }) {
  const prefetch = () => void queryClient.prefetchQuery(runsQuery(org.org_id));
  return (
    <Link
      to={`/orgs/${encodeURIComponent(org.org_id)}`}
      className={`pw-tile${org.cover_url ? ' pw-tile--photo' : ''}`}
      onMouseEnter={prefetch}
      onFocus={prefetch}
    >
      {org.cover_url && (
        <>
          <img className="pw-tile__img" src={org.cover_url} alt="" loading="lazy" />
          <div className="pw-tile__scrim" />
        </>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <h2 className="pw-tile__title">{org.name}</h2>
          <p className="pw-tile__blurb">
            {org.last_survey_at
              ? `Latest survey: ${org.last_site_name}, ${fmtDate(org.last_survey_at)} (${fmtRelative(org.last_survey_at)}).`
              : 'No surveys uploaded yet.'}
          </p>
        </div>
        <IconArrowUpRight size={22} stroke={1.5} style={{ flex: 'none', opacity: 0.7 }} aria-hidden />
      </div>
      <div className="pw-tile__foot pw-figures">
        <Figure label={org.run_count === 1 ? 'Survey' : 'Surveys'} value={org.run_count} />
        <Figure label={org.finding_count === 1 ? 'Finding' : 'Findings'} value={org.finding_count} />
        <Figure
          label="High severity"
          value={org.high_severity_count}
          icon={org.high_severity_count > 0 ? <IconAlertOctagon size={14} color="var(--pw-sev-high)" aria-hidden /> : undefined}
        />
      </div>
    </Link>
  );
}

export default function CompaniesPage() {
  useDocumentTitle('Companies · PaveWatch');
  const { data, isPending, error, refetch } = useQuery(orgsQuery());
  const [q, setQ] = useState('');
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? []).filter((o) => !needle || o.name.toLowerCase().includes(needle) || o.org_id.includes(needle));
  }, [data, q]);

  const totals = useMemo(
    () =>
      (data ?? []).reduce(
        (a, o) => ({ runs: a.runs + o.run_count, findings: a.findings + o.finding_count, high: a.high + o.high_severity_count }),
        { runs: 0, findings: 0, high: 0 },
      ),
    [data],
  );

  return (
    <>
      <PageHeader
        eyebrow="Survey clients"
        title="Pavement findings, by client."
        subtitle="Each company below commissions supervised drone surveys of its paved areas. Open one to see its survey runs, the defects found in each, and where the data was too weak to be sure."
        right={
          data &&
          data.length > 0 && (
            <>
              <div className="pw-figures" style={{ color: 'var(--pw-ink)' }}>
                <Figure label={data.length === 1 ? 'Company' : 'Companies'} value={data.length} />
                <Figure label="Surveys" value={totals.runs} />
                <Figure label="Findings" value={totals.findings} />
              </div>
              {data.length > 3 && (
                <TextInput
                  className="pw-field"
                  placeholder="Search companies"
                  leftSection={<IconSearch size={18} />}
                  rightSection={
                    q ? <IconX size={16} style={{ cursor: 'pointer' }} onClick={() => setQ('')} aria-label="Clear search" /> : null
                  }
                  value={q}
                  onChange={(e) => setQ(e.currentTarget.value)}
                  aria-label="Search companies"
                />
              )}
            </>
          )
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : isPending ? (
        <div className="pw-stagger">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} />
          ))}
        </div>
      ) : data.length === 0 ? (
        <EmptyBlock icon={<IconBuildingCommunity size={22} />} title="No companies yet">
          Companies appear here as soon as the processing pipeline uploads their first survey. For test data, run
          tools/synthetic/generate.py.
        </EmptyBlock>
      ) : shown.length === 0 ? (
        <EmptyBlock icon={<IconSearch size={22} />} title={`No company matches "${q}"`} />
      ) : (
        <div className="pw-stagger">
          {shown.map((o) => (
            <CompanyTile key={o.org_id} org={o} />
          ))}
        </div>
      )}
    </>
  );
}
