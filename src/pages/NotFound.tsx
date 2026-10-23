import React from 'react';
import { Link } from 'react-router-dom';
import { HeartPulse } from 'lucide-react';
import Button from '../components/ui/Button';

const NotFound: React.FC = () => (
  <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 px-4 text-center">
    <HeartPulse className="h-12 w-12 text-emerald-500" />
    <h1 className="text-3xl font-bold text-slate-900">Page not found</h1>
    <p className="max-w-md text-slate-600">
      The page you are looking for does not exist or has been moved.
    </p>
    <Link to="/">
      <Button>Back to Cardios home</Button>
    </Link>
  </div>
);

export default NotFound;
