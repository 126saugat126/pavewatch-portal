import { Anchor, Group, Paper, Skeleton, Stack, Table, Text, UnstyledButton } from '@mantine/core';
import { useDocumentTitle } from '@mantine/hooks';
import { IconAlertTriangle, IconChevronDown, IconChevronUp, IconDrone, IconSelector } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { orgQuery, prefetchRun, runsQuery } from '../api/queries';
import type { RunSummary } from '../api/types';
import { RunStatus } from '../components/Badges';
import { SeverityBar } from '../components/Charts';
import { PageHeader } from '../components/PageHeader';
import { EmptyBlock, ErrorState } from '../components/States';
import { DEFECT_TYPES, defectMeta } from '../lib/defects';
import { fmtDate, fmtTime } from '../lib/format';

type SortKey = 'date' | 'findings' | 'high';

function SortTh({
  label,
  k,
  sort,
  onSort,
  align,
}: {
  label: string;
  k: SortKey;
  sort: { key: SortKey; desc: boolean };
  onSort: (k: SortKey) => void;
  align?: 'right';
}) {
  const active = sort.key === k;
  const Icon = active ? (sort.desc ? IconChevronDown : IconChevronUp) : IconSelector;
  return (
    <Table.Th aria-sort={active ? (sort.desc ? 'descending' : 'ascending') : 'none'} style={{ textAlign: align }}>
      <UnstyledButton onClick={() => onSort(k)} fw={600} fz="sm">
        <Group gap={4} wrap="nowrap" justify={align === 'right' ? 'flex-end' : undefined}>
          <span>{label}</span>
          <Icon size={14} />
        </Group>
      </UnstyledButton>
    </Table.Th>
  );
}

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
  if (r.findings_with_warnings) parts.push(`${r.findings_with_warnings} finding${r.findings_with_warnings === 1 ? '' : 's'}`);
  return parts.join(' · ');
}

export default function RunsPage() {
  const { orgId = '' } = useParams();
  const navigate = useNavigate();
  const org = useQuery(orgQuery(orgId));
  const runs = useQuery(runsQuery(orgId));
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'date', desc: true });
  useDocumentTitle(`${org.data?.name ?? 'Surveys'} · PaveWatch`);

  const sorted = useMemo(() => {
    const val = (r: RunSummary) =>
      sort.key === 'date' ? r.started_at : sort.key === 'findings' ? r.finding_count : (r.counts_by_severity.high ?? 0);
    return [...(runs.data ?? [])].sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      const c = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.desc ? -c : c;
    });
  }, [runs.data, sort]);

  const onSort = (key: SortKey) => setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: true }));
  const runPath = (r: RunSummary) => `/orgs/${encodeURIComponent(orgId)}/runs/${encodeURIComponent(r.run_id)}`;
  const error = org.error ?? runs.error;
  const totalFindings = runs.data?.reduce((a, r) => a + r.finding_count, 0) ?? 0;

  return (
    <>
      <PageHeader
        loading={org.isPending}
        crumbs={[{ label: 'Companies', to: '/' }, { label: org.data?.name ?? '…' }]}
        title={org.data?.name}
        subtitle={
          runs.data &&
          `${runs.data.length} survey${runs.data.length === 1 ? '' : 's'} · ${totalFindings} finding${totalFindings === 1 ? '' : 's'}`
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
        <Stack gap="xs">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} h={52} radius="sm" />
          ))}
        </Stack>
      ) : sorted.length === 0 ? (
        <EmptyBlock icon={<IconDrone size={22} />} title="No surveys yet">
          Surveys for this company will appear here after the first upload.
        </EmptyBlock>
      ) : (
        <Paper withBorder radius="md">
          <Table.ScrollContainer minWidth={860}>
            <Table verticalSpacing="sm" horizontalSpacing="md" highlightOnHover={false} stickyHeader>
              <Table.Thead>
                <Table.Tr>
                  <SortTh label="Date" k="date" sort={sort} onSort={onSort} />
                  <Table.Th>Site</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <SortTh label="Findings" k="findings" sort={sort} onSort={onSort} align="right" />
                  <SortTh label="Severity" k="high" sort={sort} onSort={onSort} />
                  <Table.Th>Defect types</Table.Th>
                  <Table.Th>Warnings</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sorted.map((r) => (
                  <Table.Tr
                    key={r.run_id}
                    className="pw-row pw-clickable"
                    tabIndex={0}
                    onClick={() => navigate(runPath(r))}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(runPath(r))}
                    onMouseEnter={() => prefetchRun(orgId, r.run_id)}
                    onFocus={() => prefetchRun(orgId, r.run_id)}
                  >
                    <Table.Td>
                      <Text fz="sm" fw={600}>
                        {fmtDate(r.started_at)}
                      </Text>
                      <Text fz="xs" c="dimmed">
                        {fmtTime(r.started_at)}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Anchor component={Link} to={runPath(r)} fz="sm" fw={500} onClick={(e) => e.stopPropagation()}>
                        {r.site_name}
                      </Anchor>
                      <Text fz="xs" c="dimmed" ff="monospace">
                        {r.run_id}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <RunStatus status={r.status} />
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text fz="sm" fw={600} className="pw-tabular">
                        {r.finding_count}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs" wrap="nowrap">
                        <SeverityBar counts={r.counts_by_severity} />
                        {(r.counts_by_severity.high ?? 0) > 0 && (
                          <Text fz="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                            {r.counts_by_severity.high} high
                          </Text>
                        )}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text fz="sm" c={r.finding_count ? undefined : 'dimmed'}>
                        {r.finding_count ? typeSummary(r.counts_by_type) : 'None detected'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {warningSummary(r) ? (
                        <Group gap={6} wrap="nowrap">
                          <IconAlertTriangle size={15} color="var(--pw-status-warning)" aria-hidden />
                          <Text fz="sm">{warningSummary(r)}</Text>
                        </Group>
                      ) : (
                        <Text fz="sm" c="dimmed">
                          None
                        </Text>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Paper>
      )}
    </>
  );
}
