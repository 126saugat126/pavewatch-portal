import { Button, Center, Group, Stack, Text, Title } from '@mantine/core';
import { IconAlertCircle, IconArrowLeft, IconRefresh } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link, isRouteErrorResponse, useRouteError } from 'react-router-dom';
import { ApiError } from '../api/client';

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const notFound = error instanceof ApiError && error.status === 404;
  const message = error instanceof Error ? error.message : 'Something went wrong.';
  return (
    <div className="pw-tile pw-banner" role="alert" style={{ borderLeftColor: notFound ? 'var(--pw-ink-2)' : 'var(--pw-sev-high)' }}>
      <IconAlertCircle size={22} color={notFound ? 'var(--pw-ink-2)' : 'var(--pw-sev-high)'} aria-hidden />
      <h2 className="pw-tile__title">{notFound ? 'Not found' : 'Could not load this page'}</h2>
      <Stack gap="lg" align="flex-start">
        <Text className="pw-dim">{message}</Text>
        <Group gap="sm">
          {!notFound && onRetry && (
            <button type="button" className="pw-cta pw-caps" onClick={onRetry}>
              <IconRefresh size={16} /> Try again
            </button>
          )}
          <Link to="/" className="pw-cta pw-cta--ghost pw-caps">
            <IconArrowLeft size={16} /> All companies
          </Link>
        </Group>
      </Stack>
    </div>
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
    <div className="pw-tile" style={{ minHeight: 240, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <span className="pw-dim" aria-hidden>
        {icon}
      </span>
      <h2 className="pw-tile__title">{title}</h2>
      {children && <p className="pw-tile__blurb">{children}</p>}
      {action && <div style={{ marginTop: 'auto' }}>{action}</div>}
    </div>
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
