import { createBrowserRouter } from 'react-router-dom';
import { loadRunPage } from './api/queries';
import { AppLayout } from './components/AppLayout';
import { RouteError } from './components/States';
import CompaniesPage from './pages/CompaniesPage';
import NotFoundPage from './pages/NotFoundPage';
import RunsPage from './pages/RunsPage';

// The map-heavy survey page is split into its own chunk (MapLibre is large) and
// is prefetched when the user hovers a link that leads to it.
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <CompaniesPage /> },
      { path: 'orgs/:orgId', element: <RunsPage /> },
      {
        path: 'orgs/:orgId/runs/:runId',
        lazy: () => loadRunPage().then((m) => ({ Component: m.default })),
        // A finding opens inside the survey page, so this child renders nothing of its own:
        // the survey page reads :findingId from the URL and shows the detail panel.
        children: [{ path: 'findings/:findingId', element: null }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
