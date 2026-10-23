import React from 'react';
import AuthForm from '../components/auth/AuthForm';

const AuthPage: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
      <AuthForm />
    </div>
  );
};

export default AuthPage;
