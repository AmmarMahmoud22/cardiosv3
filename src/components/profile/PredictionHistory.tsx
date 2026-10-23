import React, { useCallback, useEffect, useState } from 'react';
import { supabase } from '../../lib/supabase';
import { useAuthStore } from '../../stores/authStore';
import { computeCardiacRiskScore } from '../../services/cardiacInsights';
import type { PredictionRecord } from '../../types';

const PredictionHistory: React.FC = () => {
  const { user } = useAuthStore();
  const [predictions, setPredictions] = useState<PredictionRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const loadPredictions = useCallback(async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('predictions')
        .select('*')
        .eq('user_id', user?.id)
        .order('created_at', { ascending: false })
        .limit(20);

      if (error) throw error;
      setPredictions(data || []);
    } catch (error) {
      console.error('Error loading predictions:', error);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      void loadPredictions();
    }
  }, [user, loadPredictions]);

  if (loading) {
    return <div className="text-sm text-slate-500">Loading Cardios assessment history...</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="font-sora text-xl font-semibold text-slate-950">Assessment history</h2>
      <p className="text-xs text-slate-500">Automated screening estimates — not diagnoses.</p>
      {predictions.length === 0 ? (
        <p className="text-sm text-slate-600">No saved assessments yet.</p>
      ) : (
        predictions.map((prediction) => {
          const riskScore = computeCardiacRiskScore(prediction.prediction_data);
          const riskClass = prediction.prediction_result.includes('High')
            ? 'bg-red-50 text-red-700'
            : 'bg-emerald-50 text-emerald-700';

          return (
            <div key={prediction.id} className="rounded-[24px] border border-emerald-100 bg-white px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${riskClass}`}>
                    {prediction.prediction_result.includes('High') ? 'High attention' : 'Stable watch'}
                  </span>
                  <p className="mt-3 font-semibold text-slate-950">{prediction.prediction_result}</p>
                  <p className="mt-1 text-sm text-slate-500">{new Date(prediction.created_at).toLocaleString()}</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <HistoryMetric label="Risk score" value={riskScore.toString()} />
                  <HistoryMetric label="BMI" value={prediction.prediction_data.BMI.toString()} />
                  <HistoryMetric label="Sleep" value={`${prediction.prediction_data.SleepTime} hrs`} />
                  <HistoryMetric label="Activity" value={prediction.prediction_data.PhysicalActivity} />
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
};

const HistoryMetric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-2xl bg-emerald-50/60 px-3 py-2">
    <p className="text-[11px] uppercase tracking-[0.14em] text-emerald-700">{label}</p>
    <p className="mt-1 font-medium text-slate-900">{value}</p>
  </div>
);

export default PredictionHistory;
