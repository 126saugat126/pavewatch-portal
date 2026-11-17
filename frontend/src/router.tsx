import { createBrowserRouter } from 'react-router-dom';
import { loadFindingPage, loadRunPage } from './api/queries';
import { AppLayout } from './components/AppLayout';
import { RouteError } from './components/States';
import CompaniesPage from './pages/CompaniesPage';
import NotFoundPage from './pages/NotFoundPage';
import RunsPage from './pages/RunsPage';

// The map-heavy pages are split into their own chunks (MapLibre is large) and
// are prefetched when the user hovers a link that leads to them.
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <CompaniesPage /> },
      { path: 'orgs/:orgId', element: <RunsPage /> },
      { path: 'orgs/:orgId/runs/:runId', lazy: () => loadRunPage().then((m) => ({ Component: m.default })) },
      {
        path: 'orgs/:orgId/runs/:runId/findings/:findingId',
        lazy: () => loadFindingPage().then((m) => ({ Component: m.default })),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
