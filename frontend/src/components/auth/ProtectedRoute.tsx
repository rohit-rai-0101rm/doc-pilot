import { Navigate, Outlet } from 'react-router-dom';

import { useAuth } from '@/lib/auth';

export function ProtectedRoute() {
  const { session, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
