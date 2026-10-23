import React from 'react';
import { ActivitySquare } from 'lucide-react';
import type { PredictionRecord } from '../../types';
import { computeCardiacRiskScore, getRiskBandLabel } from '../../services/cardiacInsights';

const RecentPredictions: React.FC<{ predictions: PredictionRecord[] }> = ({ predictions }) => {
  return (
    <div className="cardios-shell rounded-[32px] p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Assessment history</p>
          <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">Recent AI assessments</h2>
          <p className="mt-1 text-xs text-slate-500">Automated screening estimates — not diagnoses.</p>
        </div>
        <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
          <ActivitySquare className="h-5 w-5" />
        </div>
      </div>

      <div className="space-y-4">
        {predictions.map((prediction) => {
          const score = computeCardiacRiskScore(prediction.prediction_data);
          const riskTone = prediction.prediction_result.includes('High')
            ? 'bg-red-50 text-red-700'
            : 'bg-emerald-50 text-emerald-700';

          return (
            <div
              key={prediction.id}
              className="rounded-[26px] border border-emerald-100 bg-white px-5 py-4 shadow-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${riskTone}`}>
                    {prediction.prediction_result.includes('High') ? 'High attention' : 'Stable watch'}
                  </div>
                  <p className="mt-3 font-sora text-lg font-semibold text-slate-950">{prediction.prediction_result}</p>
                  <p className="mt-1 text-sm text-slate-500">{new Date(prediction.created_at).toLocaleString()}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Metric label="Risk score" value={score.toString()} />
                  <Metric label="Risk band" value={getRiskBandLabel(prediction.prediction_result.includes('High') ? 'high' : score >= 38 ? 'elevated' : 'stable')} />
                  <Metric label="BMI" value={prediction.prediction_data.BMI.toString()} />
                  <Metric label="Sleep" value={`${prediction.prediction_data.SleepTime} hrs`} />
                </div>
              </div>
            </div>
          );
        })}

        {predictions.length === 0 && (
          <div className="rounded-[26px] border border-dashed border-emerald-200 bg-emerald-50/70 px-5 py-8 text-center text-sm text-slate-600">
            No saved assessments yet. Run your first Cardios AI assessment to start a personal risk record.
          </div>
        )}
      </div>
    </div>
  );
};

const Metric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-2xl bg-emerald-50/60 px-3 py-2">
    <p className="text-[11px] uppercase tracking-[0.16em] text-emerald-700">{label}</p>
    <p className="mt-1 font-medium text-slate-900">{value}</p>
  </div>
);

export default RecentPredictions;
