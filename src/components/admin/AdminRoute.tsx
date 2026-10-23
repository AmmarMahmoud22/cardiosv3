import React from 'react';
import RequireRole from '../auth/RequireRole';

interface AdminRouteProps {
  children: React.ReactNode;
}

const AdminRoute: React.FC<AdminRouteProps> = ({ children }) => {
  return <RequireRole allowed={['admin']}>{children}</RequireRole>;
};

export default AdminRoute;
