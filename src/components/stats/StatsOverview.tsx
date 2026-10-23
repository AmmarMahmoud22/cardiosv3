import React from 'react';
import { Activity, BrainCircuit, HeartPulse, Users } from 'lucide-react';

const StatCard = ({
  title,
  value,
  description,
  icon,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: React.ReactNode;
}) => (
  <div className="rounded-[28px] border border-white/10 bg-white/10 p-5 backdrop-blur-sm">
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-emerald-50/70">{title}</p>
        <p className="mt-2 font-sora text-3xl font-semibold text-white">{value}</p>
        <p className="mt-2 text-sm text-emerald-50/70">{description}</p>
      </div>
      <div className="rounded-2xl bg-white/10 p-3 text-emerald-100">{icon}</div>
    </div>
  </div>
);

const StatsOverview: React.FC<{
  totalUsers: number;
  totalPredictions: number;
  userAssessments: number;
  monitoringCheckIns: number;
}> = ({ totalUsers, totalPredictions, userAssessments, monitoringCheckIns }) => {
  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="Care profiles"
        value={totalUsers.toLocaleString()}
        description="Total people with Cardios data in the workspace."
        icon={<Users className="h-6 w-6" />}
      />
      <StatCard
        title="AI assessments"
        value={totalPredictions.toLocaleString()}
        description="Screening assessments recorded across the platform."
        icon={<BrainCircuit className="h-6 w-6" />}
      />
      <StatCard
        title="Your assessments"
        value={userAssessments.toLocaleString()}
        description="Risk-support assessments saved to your own record."
        icon={<Activity className="h-6 w-6" />}
      />
      <StatCard
        title="Monitoring check-ins"
        value={monitoringCheckIns.toLocaleString()}
        description="Symptom and wellness entries in your monitoring trail."
        icon={<HeartPulse className="h-6 w-6" />}
      />
    </div>
  );
};

export default StatsOverview;
