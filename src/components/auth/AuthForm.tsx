import React, { useState } from 'react';
import { ActivitySquare, HeartPulse, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { supabase } from '../../lib/supabase';
import Button from '../ui/Button';

type AuthMode = 'signin' | 'signup';

const inputClasses =
  'mt-2 block w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200';

const AuthForm: React.FC = () => {
  const [mode, setMode] = useState<AuthMode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [gender, setGender] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();
  const { signIn, signUp } = useAuthStore();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'signup') {
        await signUp(email, password);

        const { error: profileError } = await supabase.from('extended_profiles').insert({
          id: (await supabase.auth.getUser()).data.user?.id,
          full_name: fullName,
          date_of_birth: dateOfBirth,
          gender,
          phone_number: phoneNumber,
        });

        if (profileError) {
          throw new Error(profileError.message);
        }
      } else {
        await signIn(email, password);
      }

      navigate('/app');
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Cardios could not complete the authentication request.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
      <div className="rounded-[32px] bg-[#08251a] p-8 text-white">
        <div className="inline-flex rounded-2xl bg-emerald-500/20 p-3 text-emerald-100">
          <ActivitySquare className="h-6 w-6" />
        </div>
        <h2 className="mt-6 font-sora text-3xl font-semibold">Welcome to Cardios</h2>
        <p className="mt-4 text-sm leading-7 text-emerald-50/80">
          Sign in to access your cardiac dashboard, monitor trends, compare ECG studies, and
          generate clinician-ready reports.
        </p>
        <div className="mt-8 space-y-4 text-sm text-emerald-50/80">
          <div className="flex items-start gap-3 rounded-3xl bg-white/8 p-4">
            <HeartPulse className="mt-0.5 h-5 w-5 text-emerald-200" />
            <span>Track repeated risk assessments over time instead of relying on one isolated result.</span>
          </div>
          <div className="flex items-start gap-3 rounded-3xl bg-white/8 p-4">
            <ShieldCheck className="mt-0.5 h-5 w-5 text-emerald-200" />
            <span>Keep profile, ECG, and check-in context together inside one cardiac workspace.</span>
          </div>
        </div>
      </div>

      <div className="cardios-shell rounded-[32px] p-8">
        <h2 className="font-sora text-3xl font-semibold text-slate-950">
          {mode === 'signin' ? 'Sign in to Cardios' : 'Create your Cardios account'}
        </h2>
        <p className="mt-2 text-sm leading-7 text-slate-600">
          {mode === 'signin'
            ? 'Return to your cardiac monitoring workspace.'
            : 'Start a secure cardiac profile for AI assessments and monitoring.'}
        </p>

        {error && <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClasses}
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClasses}
              minLength={6}
              required
            />
          </div>

          {mode === 'signup' && (
            <>
              <div>
                <label className="text-sm font-medium text-slate-700">Full name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  className={inputClasses}
                  required
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-slate-700">Date of birth</label>
                  <input
                    type="date"
                    value={dateOfBirth}
                    onChange={(event) => setDateOfBirth(event.target.value)}
                    className={inputClasses}
                    required
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-slate-700">Gender</label>
                  <select
                    value={gender}
                    onChange={(event) => setGender(event.target.value)}
                    className={inputClasses}
                    required
                  >
                    <option value="">Select</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-slate-700">Phone number</label>
                <input
                  type="tel"
                  value={phoneNumber}
                  onChange={(event) => setPhoneNumber(event.target.value)}
                  className={inputClasses}
                />
              </div>
            </>
          )}

          <Button type="submit" className="mt-2 w-full" disabled={loading}>
            {loading
              ? mode === 'signin'
                ? 'Signing in...'
                : 'Creating account...'
              : mode === 'signin'
              ? 'Sign In'
              : 'Create Account'}
          </Button>

          <button
            type="button"
            onClick={() => {
              setMode(mode === 'signin' ? 'signup' : 'signin');
              setError('');
            }}
            className="w-full text-sm font-semibold text-emerald-700 hover:text-emerald-800"
          >
            {mode === 'signin' ? "Don't have an account? Create one" : 'Already have an account? Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default AuthForm;
