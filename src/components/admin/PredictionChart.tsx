import React from 'react';
import { ResponsiveContainer, BarChart, Bar, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts';
import type { PredictionStats } from '../../types/admin';
import { supabase } from '../../lib/supabase';

const PredictionChart: React.FC = () => {
  const [stats, setStats] = React.useState<PredictionStats[]>([]);

  React.useEffect(() => {
    const fetchStats = async () => {
      const since = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString();
      const { data, error } = await supabase
        .from('predictions')
        .select('created_at, prediction_result')
        .gte('created_at', since)
        .order('created_at', { ascending: true });

      if (error || !data) {
        console.error('Error fetching prediction chart data:', error);
        return;
      }

      const grouped = data.reduce((accumulator: Record<string, PredictionStats>, current) => {
        const date = new Date(current.created_at).toLocaleDateString(undefined, {
          month: 'short',
          day: 'numeric',
        });

        if (!accumulator[date]) {
          accumulator[date] = { date, count: 0, accuracy: 0 };
        }

        accumulator[date].count += 1;
        accumulator[date].accuracy += current.prediction_result.includes('High') ? 1 : 0;
        return accumulator;
      }, {});

      const nextStats = Object.values(grouped).map((item) => ({
        ...item,
        accuracy: item.count ? Number(((item.accuracy / item.count) * 100).toFixed(1)) : 0,
      }));

      setStats(nextStats);
    };

    void fetchStats();
  }, []);

  if (!stats.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-[24px] border border-dashed border-emerald-200 bg-emerald-50/60 text-sm text-slate-600">
        Recent prediction activity will appear here.
      </div>
    );
  }

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={stats}>
          <CartesianGrid strokeDasharray="3 3" stroke="#d7efe4" />
          <XAxis dataKey="date" tick={{ fill: '#486558', fontSize: 12 }} />
          <YAxis tick={{ fill: '#486558', fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="count" fill="#10b981" radius={[10, 10, 0, 0]} name="Predictions" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PredictionChart;
