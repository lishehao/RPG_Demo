import { Navigate, Outlet, createBrowserRouter } from 'react-router-dom';
import { DashboardPage } from '@/pages/DashboardPage';
import { LoginPage } from '@/pages/LoginPage';
import { SessionPage } from '@/pages/SessionPage';
import { AppShell } from '@/shared/ui/AppShell';
import { useAuthStore } from '@/shared/store/authStore';

function ProtectedLayout() {
  const token = useAuthStore((state) => state.token);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function GuestOnlyRoute() {
  const token = useAuthStore((state) => state.token);

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  return <LoginPage />;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/dashboard" replace />,
  },
  {
    path: '/login',
    element: <GuestOnlyRoute />,
  },
  {
    element: <ProtectedLayout />,
    children: [
      {
        path: '/dashboard',
        element: <DashboardPage />,
      },
      {
        path: '/sessions/:sessionId',
        element: <SessionPage />,
      },
    ],
  },
]);
