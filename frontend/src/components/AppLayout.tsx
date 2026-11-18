import { Tooltip, useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import { IconMoon, IconSun } from '@tabler/icons-react';
import { Link, NavLink, Outlet, ScrollRestoration, useNavigation } from 'react-router-dom';

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme('dark', { getInitialValueInEffect: true });
  const next = computed === 'dark' ? 'light' : 'dark';
  return (
    <Tooltip label={`Switch to ${next} mode`}>
      <button type="button" className="pw-icon-btn" aria-label={`Switch to ${next} mode`} onClick={() => setColorScheme(next)}>
        {computed === 'dark' ? <IconSun size={18} stroke={1.6} /> : <IconMoon size={18} stroke={1.6} />}
      </button>
    </Tooltip>
  );
}

function NavigationProgress() {
  const nav = useNavigation();
  if (nav.state === 'idle') return null;
  return <div className="pw-nav-progress" role="progressbar" aria-label="Loading page" />;
}

/** Survey-frame mark: the scanned area with the LiDAR line crossing it. */
function Mark() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden>
      <rect x="2.75" y="2.75" width="18.5" height="18.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <line x1="2.75" y1="13.5" x2="21.25" y2="13.5" stroke="var(--pw-lime)" strokeWidth="2" />
      <line x1="8" y1="7.5" x2="16" y2="7.5" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
    </svg>
  );
}

export function AppLayout() {
  return (
    <>
      <header className="pw-header">
        <NavigationProgress />
        <div className="pw-header__inner">
          <Link to="/" className="pw-wordmark pw-caps" aria-label="PaveWatch home">
            <Mark />
            <span>PaveWatch</span>
          </Link>
          <nav className="pw-nav pw-caps" aria-label="Main">
            <NavLink to="/" end>
              Companies
            </NavLink>
            <a href="/docs" target="_blank" rel="noreferrer" className="pw-hide-sm">
              API docs
            </a>
            <ColorSchemeToggle />
          </nav>
        </div>
      </header>
      <main className="pw-main">
        <Outlet />
      </main>
      <ScrollRestoration />
    </>
  );
}
