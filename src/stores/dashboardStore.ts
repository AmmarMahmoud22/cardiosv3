import { create } from 'zustand';
import { supabase } from '../lib/supabase';
import type { PredictionRecord } from '../types';

interface DashboardStats {
  totalUsers: number;
  totalPredictions: number;
  recentPredictions: PredictionRecord[];
  allPredictions: PredictionRecord[];
  latestPrediction: PredictionRecord | null;
}

interface DashboardState extends DashboardStats {
  loading: boolean;
  error: string | null;
  fetchStats: (userId: string) => Promise<void>;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  totalUsers: 0,
  totalPredictions: 0,
  recentPredictions: [],
  allPredictions: [],
  latestPrediction: null,
  loading: false,
  error: null,

  fetchStats: async (userId: string) => {
    if (!userId) {
      set({
        loading: false,
        error: 'A signed-in profile is required to load the Cardios dashboard.',
      });
      return;
    }

    set({ loading: true, error: null });

    try {
      const [
        { count: usersCount, error: usersError },
        { count: predictionsCount, error: predictionsError },
        { data: userPredictions, error: userPredictionsError },
      ] = await Promise.all([
        supabase.from('profiles').select('id', { count: 'exact', head: true }),
        supabase.from('predictions').select('id', { count: 'exact', head: true }),
        supabase
          .from('predictions')
          .select('*')
          .eq('user_id', userId)
          .order('created_at', { ascending: false })
          .limit(24),
      ]);

      if (usersError) throw usersError;
      if (predictionsError) throw predictionsError;
      if (userPredictionsError) throw userPredictionsError;

      const totalUsers = usersCount || 0;
      const totalPredictions = predictionsCount || 0;
      const allPredictions = userPredictions || [];
      const recentPredictions = allPredictions.slice(0, 5);
      const latestPrediction = recentPredictions[0] || null;

      set({
        totalUsers,
        totalPredictions,
        allPredictions,
        recentPredictions,
        latestPrediction,
        loading: false,
        error: null,
      });
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
      set({
        loading: false,
        error: 'Cardios could not load the latest cardiac dashboard data.',
      });
    }
  },
}));
