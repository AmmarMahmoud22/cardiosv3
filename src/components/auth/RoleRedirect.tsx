import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { getDefaultRouteForRole } from '../../utils/roleUtils';

const RoleRedirect: React.FC = () => {
  const { user, loading, role, roleLoading } = useAuthStore();

  if (loading || roleLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-slate-600">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" replace />;
  }

  return <Navigate to={getDefaultRouteForRole(role)} replace />;
};

export default RoleRedirect;
