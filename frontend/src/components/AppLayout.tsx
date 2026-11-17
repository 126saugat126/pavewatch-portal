import {
  ActionIcon,
  Anchor,
  AppShell,
  Container,
  Group,
  Text,
  ThemeIcon,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core';
import { IconMoon, IconRoad, IconSun } from '@tabler/icons-react';
import { Link, Outlet, ScrollRestoration, useNavigation } from 'react-router-dom';

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme('light', { getInitialValueInEffect: true });
  const next = computed === 'dark' ? 'light' : 'dark';
  return (
    <Tooltip label={`Switch to ${next} mode`}>
      <ActionIcon variant="default" size="lg" aria-label={`Switch to ${next} mode`} onClick={() => setColorScheme(next)}>
        {computed === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}

function NavigationProgress() {
  const nav = useNavigation();
  if (nav.state === 'idle') return null;
  return <div className="pw-nav-progress" role="progressbar" aria-label="Loading page" />;
}

export function AppLayout() {
  return (
    <AppShell header={{ height: 56 }} padding={0}>
      <AppShell.Header>
        <NavigationProgress />
        <Container size="xl" h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Anchor component={Link} to="/" underline="never" c="inherit" aria-label="PaveWatch home">
              <Group gap="xs" wrap="nowrap">
                <ThemeIcon size={30} radius="md" variant="filled">
                  <IconRoad size={18} />
                </ThemeIcon>
                <Text fw={700} fz="lg">
                  PaveWatch
                </Text>
                <Text c="dimmed" fz="sm" visibleFrom="sm">
                  Survey portal
                </Text>
              </Group>
            </Anchor>
            <Group gap="sm" wrap="nowrap">
              <Anchor href="/docs" target="_blank" fz="sm" c="dimmed" visibleFrom="sm">
                API docs
              </Anchor>
              <ColorSchemeToggle />
            </Group>
          </Group>
        </Container>
      </AppShell.Header>
      <AppShell.Main>
        <Container size="xl" py="lg" px={{ base: 'md', sm: 'lg' }}>
          <Outlet />
        </Container>
      </AppShell.Main>
      <ScrollRestoration />
    </AppShell>
  );
}
