import React from 'react';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: 'emerald' | 'teal' | 'slate' | 'amber';
}

const colorClasses = {
  emerald: 'bg-emerald-100 text-emerald-700',
  teal: 'bg-teal-100 text-teal-700',
  slate: 'bg-slate-100 text-slate-700',
  amber: 'bg-amber-100 text-amber-700',
};

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color }) => (
  <div className="cardios-shell rounded-[28px] p-6">
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{title}</p>
        <p className="mt-3 font-sora text-3xl font-semibold text-slate-950">{value}</p>
      </div>
      <div className={`rounded-2xl p-3 ${colorClasses[color]}`}>{icon}</div>
    </div>
  </div>
);

export default StatCard;
