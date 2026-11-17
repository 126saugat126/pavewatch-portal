import { Card, Group, SimpleGrid, Skeleton, Stack, Text, TextInput, ThemeIcon, Title } from '@mantine/core';
import { useDocumentTitle } from '@mantine/hooks';
import { IconAlertOctagon, IconBuildingCommunity, IconSearch, IconX } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { orgsQuery, queryClient, runsQuery } from '../api/queries';
import type { OrganizationSummary } from '../api/types';
import { PageHeader } from '../components/PageHeader';
import { EmptyBlock, ErrorState } from '../components/States';
import { fmtDate, fmtRelative } from '../lib/format';

function Stat({ label, value, icon }: { label: string; value: number; icon?: ReactNode }) {
  return (
    <Stack gap={0}>
      <Group gap={4} wrap="nowrap">
        {icon}
        <Text fz="xl" fw={650} lh={1.2}>
          {value}
        </Text>
      </Group>
      <Text fz="xs" c="dimmed">
        {label}
      </Text>
    </Stack>
  );
}

function CompanyCard({ org }: { org: OrganizationSummary }) {
  return (
    <Card
      component={Link}
      to={`/orgs/${encodeURIComponent(org.org_id)}`}
      withBorder
      padding="lg"
      radius="md"
      className="pw-clickable pw-card-link"
      onMouseEnter={() => void queryClient.prefetchQuery(runsQuery(org.org_id))}
      onFocus={() => void queryClient.prefetchQuery(runsQuery(org.org_id))}
    >
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <ThemeIcon size={40} radius="md" variant="light">
          <IconBuildingCommunity size={22} />
        </ThemeIcon>
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Title order={3} fz="lg" lh={1.3}>
            {org.name}
          </Title>
          <Text fz="sm" c="dimmed" lineClamp={1}>
            {org.last_survey_at
              ? `Last survey ${fmtDate(org.last_survey_at)} (${fmtRelative(org.last_survey_at)}) · ${org.last_site_name}`
              : 'No surveys yet'}
          </Text>
        </Stack>
      </Group>
      <SimpleGrid cols={3} mt="lg" spacing="xs">
        <Stat label={org.run_count === 1 ? 'Survey' : 'Surveys'} value={org.run_count} />
        <Stat label={org.finding_count === 1 ? 'Finding' : 'Findings'} value={org.finding_count} />
        <Stat
          label="High severity"
          value={org.high_severity_count}
          icon={org.high_severity_count > 0 ? <IconAlertOctagon size={16} color="var(--pw-sev-high)" aria-hidden /> : undefined}
        />
      </SimpleGrid>
    </Card>
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

  return (
    <>
      <PageHeader
        crumbs={[]}
        title="Companies"
        subtitle="Choose a company to see its pavement surveys and findings."
        right={
          (data?.length ?? 0) > 3 && (
            <TextInput
              placeholder="Search companies"
              leftSection={<IconSearch size={16} />}
              rightSection={
                q ? (
                  <IconX size={16} style={{ cursor: 'pointer' }} onClick={() => setQ('')} aria-label="Clear search" />
                ) : null
              }
              value={q}
              onChange={(e) => setQ(e.currentTarget.value)}
              w={{ base: '100%', sm: 280 }}
              aria-label="Search companies"
            />
          )
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : isPending ? (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} h={190} radius="md" />
          ))}
        </SimpleGrid>
      ) : data.length === 0 ? (
        <EmptyBlock icon={<IconBuildingCommunity size={22} />} title="No companies yet">
          Companies appear here as soon as the processing pipeline uploads their first survey. For test data, run
          tools/synthetic/generate.py.
        </EmptyBlock>
      ) : shown.length === 0 ? (
        <EmptyBlock icon={<IconSearch size={22} />} title={`No company matches "${q}"`} />
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {shown.map((o) => (
            <CompanyCard key={o.org_id} org={o} />
          ))}
        </SimpleGrid>
      )}
    </>
  );
}
