import { Tooltip, useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import {
  IconAlertOctagon,
  IconArrowLeft,
  IconArrowRight,
  IconBuildingCommunity,
  IconChevronRight,
  IconMapPin,
  IconMoon,
  IconRoute,
  IconSun,
} from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Outlet, ScrollRestoration, useLocation, useMatches, useNavigate, useNavigation, useNavigationType } from 'react-router-dom';
import { orgQuery, orgsQuery, runQuery } from '../api/queries';
import { fmtDate } from '../lib/format';
import { MOTION } from '../lib/motion';
import { toast } from '../lib/toast';
import { CountUp, PageTransition } from './Motion';

const MAX_IDX_KEY = 'pw-max-history-idx';

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme('light', { getInitialValueInEffect: true });
  const next = computed === 'dark' ? 'light' : 'dark';
  return (
    <Tooltip label={`Switch to ${next} mode`}>
      <button type="button" className="pw-iconbtn" aria-label={`Switch to ${next} mode`} onClick={() => setColorScheme(next)}>
        <motion.span
          key={computed}
          initial={{ rotate: -90, opacity: 0 }}
          animate={{ rotate: 0, opacity: 1 }}
          transition={{ duration: MOTION.s.base, ease: MOTION.ease }}
          style={{ display: 'grid' }}
        >
          {computed === 'dark' ? <IconSun size={19} stroke={1.6} /> : <IconMoon size={19} stroke={1.6} />}
        </motion.span>
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
      <rect x="2.75" y="2.75" width="18.5" height="18.5" rx="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <line x1="2.75" y1="13.5" x2="21.25" y2="13.5" stroke="var(--pw-geo)" strokeWidth="2" />
      <line x1="8" y1="7.5" x2="16" y2="7.5" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
    </svg>
  );
}

/** The ids in the current URL (the deepest match carries all of them). */
function useRouteIds() {
  const matches = useMatches();
  return useMemo(() => {
    const p = (matches[matches.length - 1]?.params ?? {}) as Record<string, string | undefined>;
    return { orgId: p.orgId, runId: p.runId, findingId: p.findingId };
  }, [matches]);
}

/**
 * Browser-style back / forward. Back falls back to "up one level" when the page was opened directly
 * (no history to go back to). Forward is only enabled when there is a page ahead in this tab's history.
 */
function useHistoryNav(parentPath: string | null) {
  const navigate = useNavigate();
  const location = useLocation();
  const type = useNavigationType();
  const [state, setState] = useState({ idx: 0, max: 0 });

  useEffect(() => {
    const idx = Number((window.history.state as { idx?: number } | null)?.idx ?? 0);
    let max = idx;
    try {
      max = type === 'PUSH' ? idx : Math.max(idx, Number(sessionStorage.getItem(MAX_IDX_KEY) ?? 0));
      sessionStorage.setItem(MAX_IDX_KEY, String(max));
    } catch {
      /* storage unavailable: forward simply stays disabled after a reload */
    }
    setState({ idx, max });
  }, [location.key, type]);

  const canBack = state.idx > 0;
  const canUp = !canBack && !!parentPath;
  return {
    canBack: canBack || canUp,
    canForward: state.idx < state.max,
    back: () => (canBack ? navigate(-1) : parentPath && navigate(parentPath)),
    forward: () => navigate(1),
    backLabel: canBack ? 'Go back' : canUp ? 'Go up one level' : 'Nothing to go back to',
  };
}

interface Step {
  key: string;
  kind: string;
  name: string;
  to: string;
}

/** Companies › Surveys › Findings (› one finding): the current step is filled, earlier steps are buttons. */
function Trail({ steps }: { steps: Step[] }) {
  return (
    <nav aria-label="You are here" className="pw-trail">
      <ol>
        <AnimatePresence initial={false} mode="popLayout">
          {steps.map((s, i) => {
            const current = i === steps.length - 1;
            const inner = (
              <>
                {current && (
                  <motion.span
                    layoutId="pw-step-active"
                    className="pw-step__bg"
                    transition={{ type: 'spring', stiffness: 520, damping: 40, mass: 0.8 }}
                  />
                )}
                <span className="pw-step__kind">{s.kind}</span>
                <span className="pw-step__name">{s.name}</span>
              </>
            );
            return (
              <motion.li
                key={s.key}
                layout="position"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: MOTION.s.base, ease: MOTION.ease }}
              >
                {i > 0 && <IconChevronRight size={16} className="pw-trail__sep" aria-hidden />}
                {current ? (
                  <span className="pw-step" aria-current="page">
                    {inner}
                  </span>
                ) : (
                  <Link className="pw-step" to={s.to} preventScrollReset={s.key === 'findings'}>
                    {inner}
                  </Link>
                )}
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
    </nav>
  );
}

/** Portfolio-wide figures in the top bar. Reuses the cached companies query (no extra request). */
function SummaryChips() {
  const { data, dataUpdatedAt, isFetching } = useQuery(orgsQuery());
  const totals = useMemo(
    () =>
      (data ?? []).reduce(
        (a, o) => ({ runs: a.runs + o.run_count, findings: a.findings + o.finding_count, high: a.high + o.high_severity_count }),
        { runs: 0, findings: 0, high: 0 },
      ),
    [data],
  );

  // Tell the user when a background refresh brings in new surveys.
  const prev = useRef<Map<string, number> | null>(null);
  useEffect(() => {
    if (!data) return;
    const now = new Map(data.map((o) => [o.org_id, o.run_count]));
    if (prev.current) {
      const grown = data.filter((o) => o.run_count > (prev.current!.get(o.org_id) ?? 0));
      if (grown.length) {
        toast.info(
          grown.length === 1 ? 'New survey received' : 'New surveys received',
          grown.map((o) => o.name).join(', '),
          'new-surveys',
        );
      }
    }
    prev.current = now;
  }, [data]);

  if (!data) return <div className="pw-chips" aria-hidden />;
  const chips = [
    { icon: <IconBuildingCommunity size={15} stroke={1.7} />, label: 'Clients', value: data.length },
    { icon: <IconRoute size={15} stroke={1.7} />, label: 'Surveys', value: totals.runs },
    { icon: <IconMapPin size={15} stroke={1.7} />, label: 'Findings', value: totals.findings },
    { icon: <IconAlertOctagon size={15} stroke={1.7} color="var(--pw-sev-high)" />, label: 'High severity', value: totals.high },
  ];
  return (
    <div className="pw-chips" aria-label="All clients">
      {chips.map((c) => (
        <span key={c.label} className="pw-chip">
          {c.icon}
          <span className="pw-chip__label">{c.label}</span>
          <b>
            <CountUp value={c.value} />
          </b>
        </span>
      ))}
      <Tooltip label={`Checks for new uploads every minute. Last checked ${new Date(dataUpdatedAt).toLocaleTimeString()}.`}>
        <span className="pw-live" data-fetching={isFetching || undefined}>
          <span className="pw-live__dot" aria-hidden />
          <span className="pw-hide-sm">Live</span>
        </span>
      </Tooltip>
    </div>
  );
}

export function AppLayout() {
  const location = useLocation();
  const { orgId, runId, findingId } = useRouteIds();
  // Same query keys as the pages, so these come from the cache (no extra requests).
  const org = useQuery({ ...orgQuery(orgId ?? ''), enabled: !!orgId });
  const run = useQuery({ ...runQuery(orgId ?? '', runId ?? ''), enabled: !!orgId && !!runId });

  const steps = useMemo<Step[]>(() => {
    const list: Step[] = [{ key: 'companies', kind: 'Companies', name: 'All clients', to: '/' }];
    if (!orgId) return list;
    const orgPath = `/orgs/${encodeURIComponent(orgId)}`;
    list.push({ key: 'surveys', kind: 'Surveys', name: org.data?.name ?? '…', to: orgPath });
    if (!runId) return list;
    const runPath = `${orgPath}/runs/${encodeURIComponent(runId)}`;
    list.push({
      key: 'findings',
      kind: 'Findings',
      name: run.data ? `${run.data.site_name} · ${fmtDate(run.data.started_at)}` : '…',
      // Closing a finding keeps the filters the user had set.
      to: findingId ? `${runPath}${location.search}` : runPath,
    });
    if (findingId) list.push({ key: 'finding', kind: 'Finding', name: findingId, to: location.pathname });
    return list;
  }, [orgId, runId, findingId, org.data?.name, run.data, location.search, location.pathname]);

  const parent = steps.length > 1 ? steps[steps.length - 2].to : null;
  const nav = useHistoryNav(parent);
  // The finding panel lives inside the survey page, so moving between findings is not a page change.
  const pageKey = location.pathname.replace(/\/findings\/[^/]+$/, '');

  return (
    <div className="pw-shell">
      <header className="pw-topbar">
        <NavigationProgress />
        <div className="pw-topbar__in">
          <Link to="/" className="pw-mark" aria-label="PaveWatch home">
            <Mark />
          </Link>

          <div className="pw-histgroup" role="group" aria-label="History">
            <Tooltip label={nav.backLabel}>
              <button type="button" className="pw-histbtn" onClick={nav.back} disabled={!nav.canBack} aria-label={nav.backLabel}>
                <IconArrowLeft size={17} stroke={1.8} />
                <span className="pw-histbtn__label">Back</span>
              </button>
            </Tooltip>
            <Tooltip label={nav.canForward ? 'Go forward' : 'Nothing to go forward to'}>
              <button
                type="button"
                className="pw-histbtn"
                onClick={nav.forward}
                disabled={!nav.canForward}
                aria-label={nav.canForward ? 'Go forward' : 'Nothing to go forward to'}
              >
                <span className="pw-histbtn__label">Forward</span>
                <IconArrowRight size={17} stroke={1.8} />
              </button>
            </Tooltip>
          </div>

          <Trail steps={steps} />
          <SummaryChips />
          <ColorSchemeToggle />
        </div>
      </header>
      <main className="pw-main">
        <PageTransition key={pageKey}>
          <Outlet />
        </PageTransition>
      </main>
      <ScrollRestoration />
    </div>
  );
}
