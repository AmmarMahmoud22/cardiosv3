import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

type RequireAuthProps = {
  children: React.ReactNode;
};

const RequireAuth: React.FC<RequireAuthProps> = ({ children }) => {
  const { user, loading } = useAuthStore();
  const location = useLocation();

  // On a hard refresh the Supabase session is restored asynchronously. Until
  // that first getSession() resolves (loading === true) we must NOT redirect,
  // otherwise a logged-in user is bounced to /auth before their session loads.
  if (loading) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center text-slate-600">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default RequireAuth;