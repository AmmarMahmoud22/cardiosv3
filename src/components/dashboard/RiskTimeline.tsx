import React from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ActivitySquare } from 'lucide-react';
import Card from '../ui/Card';
import type { PredictionTrendPoint } from '../../types';

const RiskTimeline: React.FC<{
  timeline: PredictionTrendPoint[];
  narrative: string;
}> = ({ timeline, narrative }) => {
  return (
    <Card>
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Risk timeline</p>
          <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">Trend your cardiac risk over time</h2>
        </div>
        <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
          <ActivitySquare className="h-5 w-5" />
        </div>
      </div>

      {timeline.length === 0 ? (
        <div className="rounded-[28px] border border-dashed border-emerald-200 bg-emerald-50/60 p-8 text-sm leading-7 text-slate-600">
          Complete your first Cardios assessment to unlock the risk timeline.
        </div>
      ) : (
        <>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeline}>
                <defs>
                  <linearGradient id="riskFill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#17c979" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#17c979" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#d8f7e7" strokeDasharray="4 4" />
                <XAxis dataKey="label" tick={{ fill: '#4f6b62', fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#4f6b62', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    borderRadius: 20,
                    border: '1px solid #d8f7e7',
                    boxShadow: '0 20px 40px rgba(8,37,26,0.08)',
                  }}
                />
                <Area type="monotone" dataKey="riskScore" stroke="#17c979" fill="url(#riskFill)" strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-4 text-sm leading-7 text-slate-600">{narrative}</p>
        </>
      )}
    </Card>
  );
};

export default RiskTimeline;
