import React from 'react';
import AdminRoute from '../components/admin/AdminRoute';
import Dashboard from '../components/admin/Dashboard';

const AdminPage: React.FC = () => {
  return (
    <AdminRoute>
      <Dashboard />
    </AdminRoute>
  );
};

export default AdminPage;