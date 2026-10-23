import React from 'react';
import { Activity, BarChart3, HeartPulse, Users } from 'lucide-react';
import StatCard from './StatCard';
import UserList from './UserList';
import PredictionChart from './PredictionChart';
import { useAdminStats } from './hooks/useAdminStats';

const Dashboard: React.FC = () => {
  const stats = useAdminStats();

  return (
    <div className="space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-[36px] bg-gradient-to-br from-[#08261c] via-[#0b4f37] to-[#12a767] px-6 py-8 text-white shadow-[0_30px_70px_rgba(9,49,36,0.2)]">
        <p className="cardios-kicker border border-white/15 bg-white/10 text-emerald-50">
          Cardios operations
        </p>
        <h1 className="mt-5 font-sora text-4xl font-semibold sm:text-5xl">
          Admin intelligence for the cardiac AI platform
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-8 text-emerald-50/80">
          Track adoption, prediction volume, and recent platform activity from one operations view.
        </p>
      </section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Total users"
          value={stats.totalUsers}
          icon={<Users className="h-6 w-6" />}
          color="emerald"
        />
        <StatCard
          title="Total predictions"
          value={stats.totalPredictions}
          icon={<Activity className="h-6 w-6" />}
          color="teal"
        />
        <StatCard
          title="Active users (30d)"
          value={stats.activeUsers}
          icon={<HeartPulse className="h-6 w-6" />}
          color="slate"
        />
        <StatCard
          title="High-risk share (30d)"
          value={`${stats.highRiskShare.toFixed(1)}%`}
          icon={<BarChart3 className="h-6 w-6" />}
          color="amber"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="cardios-shell rounded-[30px] p-6">
          <h2 className="font-sora text-2xl font-semibold text-slate-950">Recent users</h2>
          <p className="mt-2 text-sm text-slate-600">
            Latest profiles from the restored Supabase project.
          </p>
          <div className="mt-5">
            <UserList />
          </div>
        </div>

        <div className="cardios-shell rounded-[30px] p-6">
          <h2 className="font-sora text-2xl font-semibold text-slate-950">Prediction activity</h2>
          <p className="mt-2 text-sm text-slate-600">
            Daily prediction volume over the recent week.
          </p>
          <div className="mt-5">
            <PredictionChart />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
