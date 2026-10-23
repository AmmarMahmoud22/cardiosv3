import { useEffect, useState } from 'react';
import { supabase } from '../../../lib/supabase';
import type { AdminStats } from '../../../types/admin';

export const useAdminStats = () => {
  const [stats, setStats] = useState<AdminStats>({
    totalUsers: 0,
    totalPredictions: 0,
    activeUsers: 0,
    highRiskShare: 0,
  });

  useEffect(() => {
    const fetchStats = async () => {
      const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

      const [
        { count: userCount, error: usersError },
        { data: predictions, count: predictionCount, error: predictionsError },
      ] = await Promise.all([
        supabase.from('profiles').select('id', { count: 'exact', head: true }),
        supabase
          .from('predictions')
          .select('user_id, prediction_result, created_at', { count: 'exact' })
          .gte('created_at', thirtyDaysAgo),
      ]);

      if (usersError || predictionsError) {
        console.error('Error fetching admin stats:', usersError || predictionsError);
        return;
      }

      const recentPredictions = predictions || [];
      const activeUsers = new Set(recentPredictions.map((item) => item.user_id)).size;
      const highRiskShare = recentPredictions.length
        ? (recentPredictions.filter((item) => item.prediction_result.includes('High')).length /
            recentPredictions.length) *
          100
        : 0;

      setStats({
        totalUsers: userCount || 0,
        totalPredictions: predictionCount || 0,
        activeUsers,
        highRiskShare: Number(highRiskShare.toFixed(1)),
      });
    };

    void fetchStats();
  }, []);

  return stats;
};
