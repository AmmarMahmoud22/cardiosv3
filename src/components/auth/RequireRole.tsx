import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import type { UserRole } from '../../types';
import { getDefaultRouteForRole } from '../../utils/roleUtils';

type RequireRoleProps = {
  allowed: UserRole[];
  children: React.ReactNode;
};

const RequireRole: React.FC<RequireRoleProps> = ({ allowed, children }) => {
  const { user, loading, role, roleLoading } = useAuthStore();
  const location = useLocation();

  if (loading || roleLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-slate-600">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  if (!role || !allowed.includes(role)) {
    return <Navigate to={getDefaultRouteForRole(role)} replace />;
  }

  return <>{children}</>;
};

export default RequireRole;
