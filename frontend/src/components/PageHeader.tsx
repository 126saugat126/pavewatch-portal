import { Anchor, Breadcrumbs, Group, Skeleton, Stack, Text, Title } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export interface Crumb {
  label: ReactNode;
  to?: string;
}

export function PageHeader({
  crumbs,
  title,
  subtitle,
  right,
  loading,
}: {
  crumbs: Crumb[];
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  loading?: boolean;
}) {
  return (
    <Stack gap={6} mb="lg">
      {crumbs.length > 0 && (
        <Breadcrumbs separatorMargin={6} fz="sm" styles={{ root: { flexWrap: 'wrap', rowGap: 2 } }}>
          {crumbs.map((c, i) =>
            c.to ? (
              <Anchor key={i} component={Link} to={c.to} fz="sm">
                {c.label}
              </Anchor>
            ) : (
              <Text key={i} fz="sm" c="dimmed" truncate maw={260}>
                {c.label}
              </Text>
            ),
          )}
        </Breadcrumbs>
      )}
      <Group justify="space-between" align="flex-end" gap="md" wrap="wrap">
        <Stack gap={4} style={{ minWidth: 0, flex: '1 1 320px' }}>
          {loading ? (
            <Skeleton h={34} w={320} radius="sm" />
          ) : (
            <Title order={1} fz={{ base: 24, sm: 30 }} lh={1.2}>
              {title}
            </Title>
          )}
          {loading ? (
            <Skeleton h={16} w={240} radius="sm" mt={4} />
          ) : (
            subtitle && (
              <Text c="dimmed" fz="sm" component="div">
                {subtitle}
              </Text>
            )
          )}
        </Stack>
        {right}
      </Group>
    </Stack>
  );
}
