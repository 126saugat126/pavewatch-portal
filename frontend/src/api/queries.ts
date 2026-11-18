import { QueryCache, QueryClient, queryOptions } from '@tanstack/react-query';
import { toast } from '../lib/toast';
import { ApiError, enc, getJson } from './client';
import type { FindingDetail, FindingListItem, OrganizationSummary, OrgRef, RunDetail, RunSummary } from './types';

/** List pages re-check the server this often, so new uploads appear without a reload. */
export const LIVE_REFRESH_MS = 60_000;

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    // First-load errors are shown in the page itself. A failed *background* refresh keeps the
    // data on screen, so tell the user with a toast instead (one at a time).
    onError: (err, query) => {
      if (query.state.data === undefined) return;
      toast.warning('Could not refresh', `Showing the last data received. ${err instanceof Error ? err.message : ''}`, 'refresh-failed');
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

export const orgsQuery = () =>
  queryOptions({
    queryKey: ['orgs'],
    queryFn: ({ signal }) => getJson<OrganizationSummary[]>('/orgs', signal),
    refetchInterval: LIVE_REFRESH_MS,
  });

export const orgQuery = (orgId: string) =>
  queryOptions({
    queryKey: ['org', orgId],
    queryFn: ({ signal }) => getJson<OrgRef>(`/orgs/${enc(orgId)}`, signal),
  });

export const runsQuery = (orgId: string) =>
  queryOptions({
    queryKey: ['runs', orgId],
    queryFn: ({ signal }) => getJson<RunSummary[]>(`/orgs/${enc(orgId)}/runs`, signal),
    refetchInterval: LIVE_REFRESH_MS,
  });

export const runQuery = (orgId: string, runId: string) =>
  queryOptions({
    queryKey: ['run', orgId, runId],
    queryFn: ({ signal }) => getJson<RunDetail>(`/orgs/${enc(orgId)}/runs/${enc(runId)}`, signal),
  });

export const findingsQuery = (orgId: string, runId: string) =>
  queryOptions({
    queryKey: ['findings', orgId, runId],
    queryFn: ({ signal }) => getJson<FindingListItem[]>(`/orgs/${enc(orgId)}/runs/${enc(runId)}/findings`, signal),
  });

export const findingQuery = (orgId: string, runId: string, findingId: string) =>
  queryOptions({
    queryKey: ['finding', orgId, runId, findingId],
    queryFn: ({ signal }) =>
      getJson<FindingDetail>(`/orgs/${enc(orgId)}/runs/${enc(runId)}/findings/${enc(findingId)}`, signal),
  });

// ---- warm-up helpers (hover / adjacent prefetching for instant navigation)

const preloaded = new Set<string>();

export function preloadImage(url: string | null | undefined) {
  if (!url || preloaded.has(url)) return;
  preloaded.add(url);
  const img = new Image();
  img.decoding = 'async';
  img.src = url;
}

export const loadRunPage = () => import('../pages/RunDetailPage');

export function prefetchRun(orgId: string, runId: string) {
  void loadRunPage();
  void queryClient.prefetchQuery(runQuery(orgId, runId));
  void queryClient.prefetchQuery(findingsQuery(orgId, runId));
}

export function prefetchFinding(orgId: string, runId: string, findingId: string, withImages = false) {
  void loadRunPage();
  const p = queryClient.prefetchQuery(findingQuery(orgId, runId, findingId));
  if (withImages) {
    void p.then(() => {
      const d = queryClient.getQueryData(findingQuery(orgId, runId, findingId).queryKey);
      const first = d?.evidence.find((e) => e.is_image);
      preloadImage(first?.preview_url ?? first?.url);
      d?.evidence.forEach((e) => preloadImage(e.thumb_url));
    });
  }
}
