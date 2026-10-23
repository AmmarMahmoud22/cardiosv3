import React, { useState } from 'react';
import { ActivitySquare, Menu, ShieldCheck, Stethoscope, UserRound, X } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

const Header: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const location = useLocation();
  const { user, role } = useAuthStore();

  const isActive = (path: string) =>
    location.pathname === path
      ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
      : 'text-slate-600 hover:text-emerald-700 hover:bg-emerald-50/70 border-transparent';

  const navLinks = [
    { to: '/', label: 'Home' },
    ...(user ? (
      role === 'doctor'
        ? [
            { to: '/doctor', label: 'Doctor Portal' },
            { to: '/doctor/devices', label: 'Devices' },
          ]
        : [
            { to: '/predict', label: 'Heart Risk' },
            { to: '/predict-ecg', label: 'ECG Lab' },
          ]
    ) : []),
    { to: '/evidence', label: 'Evidence' },
    ...(role === 'admin' ? [{ to: '/admin', label: 'Admin' }] : []),
    { to: '/about', label: 'About' },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-emerald-100/70 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-[0_14px_30px_rgba(23,201,121,0.28)]">
            <ActivitySquare className="h-5 w-5" />
          </div>
          <div>
            <p className="font-sora text-xl font-semibold text-slate-950">Cardios</p>
            <p className="text-xs uppercase tracking-[0.28em] text-emerald-700">Cardiac Intelligence</p>
          </div>
        </Link>

        <button
          onClick={() => setIsMenuOpen((open) => !open)}
          className="inline-flex rounded-2xl border border-emerald-100 p-3 text-slate-700 md:hidden"
          aria-expanded={isMenuOpen}
        >
          {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

        <nav className="hidden items-center gap-2 md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${isActive(link.to)}`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          {user ? (
            <>
              {role === 'doctor' ? (
                <Link
                  to="/doctor"
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${isActive(
                    '/doctor'
                  )}`}
                >
                  <Stethoscope className="h-4 w-4" />
                  Doctor
                </Link>
              ) : null}
              {role === 'admin' ? (
                <Link
                  to="/admin"
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${isActive(
                    '/admin'
                  )}`}
                >
                  <ShieldCheck className="h-4 w-4" />
                  Admin
                </Link>
              ) : null}
              <Link
                to="/profile"
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${isActive(
                  '/profile'
                )}`}
              >
                <UserRound className="h-4 w-4" />
                Profile
              </Link>
            </>
          ) : (
            <Link
              to="/auth"
              className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${isActive(
                '/auth'
              )}`}
            >
              <Stethoscope className="h-4 w-4" />
              Sign In
            </Link>
          )}
        </div>
      </div>

      {isMenuOpen && (
        <div className="border-t border-emerald-100 bg-white px-4 py-4 md:hidden">
          <div className="space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`block rounded-2xl border px-4 py-3 text-sm font-medium transition-colors ${isActive(link.to)}`}
                onClick={() => setIsMenuOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            <Link
              to={user ? (role === 'doctor' ? '/doctor' : role === 'admin' ? '/admin' : '/profile') : '/auth'}
              className={`block rounded-2xl border px-4 py-3 text-sm font-medium transition-colors ${isActive(
                user ? (role === 'doctor' ? '/doctor' : role === 'admin' ? '/admin' : '/profile') : '/auth'
              )}`}
              onClick={() => setIsMenuOpen(false)}
            >
              {user ? (role === 'doctor' ? 'Doctor Portal' : role === 'admin' ? 'Admin' : 'Profile') : 'Sign In'}
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
