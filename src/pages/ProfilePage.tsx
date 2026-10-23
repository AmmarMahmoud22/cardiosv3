import React from 'react';
import { LogOut, UserRound } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import ProfileForm from '../components/profile/ProfileForm';
import PredictionHistory from '../components/profile/PredictionHistory';

const ProfilePage: React.FC = () => {
  const { user, signOut } = useAuthStore();

  return (
    <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="cardios-kicker mb-4">Patient profile</div>
              <h1 className="font-sora text-3xl font-semibold text-slate-950">Your Cardios profile</h1>
            </div>
            <Button variant="secondary" onClick={() => void signOut()}>
              <LogOut className="h-4 w-4" />
              Sign Out
            </Button>
          </div>

          <div className="mt-6 rounded-[28px] bg-emerald-50/70 p-5">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-white p-3 text-emerald-700 shadow-sm">
                <UserRound className="h-5 w-5" />
              </div>
              <div>
                <p className="font-semibold text-slate-900">{user?.email}</p>
                <p className="text-sm text-slate-600">
                  Member since {new Date(user?.created_at || '').toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-6">
            <ProfileForm />
          </div>
        </Card>

        <Card>
          <PredictionHistory />
        </Card>
      </div>
    </div>
  );
};

export default ProfilePage;
