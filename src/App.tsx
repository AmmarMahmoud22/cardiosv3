import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { supabase } from './lib/supabase';
import { client as appwriteClient } from './lib/appwrite';
import { useAuthStore } from './stores/authStore';
import Layout from './components/layout/Layout';
import RequireAuth from './components/auth/RequireAuth';
import RequireRole from './components/auth/RequireRole';
import RoleRedirect from './components/auth/RoleRedirect';

const Home = lazy(() => import('./pages/Home'));
const About = lazy(() => import('./pages/About'));
const Contact = lazy(() => import('./pages/Contact'));
const PredictionForm = lazy(() => import('./components/PredictionForm'));
const AuthPage = lazy(() => import('./pages/AuthPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const DoctorPage = lazy(() => import('./pages/DoctorPage'));
const DoctorDevicesPage = lazy(() => import('./pages/DoctorDevicesPage'));
const DoctorPatientPage = lazy(() => import('./pages/DoctorPatientPage'));
const ECGPrediction = lazy(() => import('./pages/ECGPrediction'));

const EvidenceAdvisor = lazy(() => import('./pages/EvidenceAdvisor'));
const NotFound = lazy(() => import('./pages/NotFound'));

const RouteFallback: React.FC = () => (
  <div className="min-h-[50vh] flex items-center justify-center text-slate-600">
    Loading...
  </div>
);

const App: React.FC = () => {
  const { setUser } = useAuthStore();

  useEffect(() => {
    // Ping Appwrite backend server to verify SDK setup (fail-safe)
    appwriteClient.ping().catch(() => {
      // Quiet failover if Appwrite is temporarily unreachable
    });

    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
    }).catch(() => {
      setUser(null);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, [setUser]);

  return (
    <Router>
      <Layout>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/app" element={<RoleRedirect />} />
            <Route
              path="/admin"
              element={
                <RequireAuth>
                  <AdminPage />
                </RequireAuth>
              }
            />
            <Route
              path="/doctor"
              element={
                <RequireRole allowed={['doctor']}>
                  <DoctorPage />
                </RequireRole>
              }
            />
            <Route
              path="/doctor/patients/:patientId"
              element={
                <RequireRole allowed={['doctor']}>
                  <DoctorPatientPage />
                </RequireRole>
              }
            />
            <Route
              path="/doctor/devices"
              element={
                <RequireRole allowed={['doctor']}>
                  <DoctorDevicesPage />
                </RequireRole>
              }
            />
            <Route
              path="/predict"
              element={
                <RequireAuth>
                  <PredictionForm />
                </RequireAuth>
              }
            />
            <Route
              path="/predict-ecg"
              element={
                <RequireAuth>
                  <ECGPrediction />
                </RequireAuth>
              }
            />

            {/*
              Deliberately public. The Evidence Advisor reads only published
              clinical guideline text — it touches no patient record and no PHI,
              so there is nothing here to protect behind a login. Gating it also
              made the guideline layer fail whenever Supabase was unavailable,
              which is a dependency it does not otherwise have.
            */}
            <Route path="/evidence" element={<EvidenceAdvisor />} />
            <Route
              path="/profile"
              element={
                <RequireAuth>
                  <ProfilePage />
                </RequireAuth>
              }
            />
            <Route path="/about" element={<About />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Layout>
    </Router>
  );
};

export default App;
