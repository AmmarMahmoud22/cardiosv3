import React, { Suspense, lazy } from 'react';
import {
  ArrowRight,
  BookOpen,
  HeartPulse,
  Waves,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import Button from '../components/ui/Button';

const Dashboard = lazy(() => import('../components/Dashboard'));

const intelligenceAreas = [
  {
    title: 'Heart Risk Intelligence',
    description:
      'Evaluate cardiac risk indicators using the patient\'s provided health profile.',
    route: '/predict',
    icon: HeartPulse,
    requiresAuth: true,
  },
  {
    title: 'ECG Intelligence',
    description:
      'Analyse ECG recordings using the Cardios ECG classification pipeline.',
    route: '/predict-ecg',
    icon: Waves,
    requiresAuth: true,
  },
  {
    title: 'Clinical Evidence Intelligence',
    description:
      'Search the ESC Heart Failure guideline and review traceable clinical evidence.',
    route: '/evidence',
    icon: BookOpen,
    requiresAuth: false,
  },
];

const LandingPage: React.FC = () => (
  <div className="pb-16">
    <section className="px-4 pt-16 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl text-center">
        <p className="cardios-kicker mb-6">Cardiac Clinical Decision Support</p>
        <h1 className="font-sora text-4xl font-semibold leading-tight text-slate-950 sm:text-5xl md:text-6xl">
          Cardios
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-600">
          A cardiac clinical AI platform combining risk assessment, ECG analysis, and
          evidence-based guideline retrieval in one integrated workspace.
        </p>
      </div>
    </section>

    <section className="mx-auto mt-14 max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="grid gap-6 md:grid-cols-3">
        {intelligenceAreas.map(({ title, description, route, icon: Icon, requiresAuth }) => (
          <Link
            key={route}
            to={requiresAuth ? '/auth' : route}
            className="group rounded-2xl border border-emerald-100 bg-white p-6 shadow-sm transition-all hover:border-emerald-200 hover:shadow-md"
          >
            <div className="mb-4 inline-flex rounded-xl bg-emerald-50 p-3 text-emerald-600 transition-colors group-hover:bg-emerald-100">
              <Icon className="h-5 w-5" />
            </div>
            <h3 className="font-sora text-lg font-semibold text-slate-900">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-emerald-600">
              {requiresAuth ? 'Sign in to access' : 'Open'}
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </Link>
        ))}
      </div>
    </section>

    <section className="mx-auto mt-14 max-w-3xl px-4 text-center sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
        <p className="text-sm leading-6 text-slate-600">
          Cardios is designed for decision support and education. It does not replace
          clinical evaluation by a qualified healthcare professional. Model outputs are
          screening estimates — not diagnoses.
        </p>
      </div>
    </section>

    <section className="mx-auto mt-12 max-w-4xl px-4 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-center justify-center gap-4">
        <Link to="/auth">
          <Button className="px-6 py-3">
            Sign in
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
        <Link to="/evidence">
          <Button variant="secondary" className="px-6 py-3">
            <BookOpen className="h-4 w-4" />
            Try Evidence Advisor
          </Button>
        </Link>
      </div>
    </section>
  </div>
);

const Home: React.FC = () => {
  const { user } = useAuthStore();

  return (
    <Suspense fallback={<LandingPage />}>
      {user ? <Dashboard /> : <LandingPage />}
    </Suspense>
  );
};

export default Home;
