import { Alert, Button, Center, Group, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core';
import { IconAlertCircle, IconArrowLeft, IconRefresh } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link, isRouteErrorResponse, useRouteError } from 'react-router-dom';
import { ApiError } from '../api/client';

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const notFound = error instanceof ApiError && error.status === 404;
  const message = error instanceof Error ? error.message : 'Something went wrong.';
  return (
    <Alert
      color={notFound ? 'gray' : 'red'}
      variant="light"
      icon={<IconAlertCircle />}
      title={notFound ? 'Not found' : 'Could not load this page'}
      my="md"
    >
      <Stack gap="sm" align="flex-start">
        <Text size="sm">{message}</Text>
        <Group gap="xs">
          {!notFound && onRetry && (
            <Button size="xs" variant="default" leftSection={<IconRefresh size={14} />} onClick={onRetry}>
              Try again
            </Button>
          )}
          <Button size="xs" variant="subtle" component={Link} to="/" leftSection={<IconArrowLeft size={14} />}>
            All companies
          </Button>
        </Group>
      </Stack>
    </Alert>
  );
}

export function EmptyBlock({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Paper withBorder p="xl" radius="md">
      <Center>
        <Stack align="center" gap="xs" maw={460} ta="center">
          <ThemeIcon size={44} radius="xl" variant="light" color="gray">
            {icon}
          </ThemeIcon>
          <Text fw={600}>{title}</Text>
          {children && (
            <Text size="sm" c="dimmed">
              {children}
            </Text>
          )}
          {action}
        </Stack>
      </Center>
    </Paper>
  );
}

export function RouteError() {
  const err = useRouteError();
  const msg = isRouteErrorResponse(err) ? `${err.status} ${err.statusText}` : (err as Error)?.message;
  return (
    <Center mih="60vh" p="lg">
      <Stack align="center" gap="sm">
        <Title order={3}>Something went wrong</Title>
        <Text c="dimmed">{msg || 'Unexpected error'}</Text>
        <Button component="a" href="/" variant="default">
          Back to start
        </Button>
      </Stack>
    </Center>
  );
}
