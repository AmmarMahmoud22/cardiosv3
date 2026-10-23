import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, HeartPulse, NotebookText, Waves } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useDashboardStore } from '../stores/dashboardStore';
import { buildNextSteps, buildPredictionTimeline, buildTrendNarrative, computeCardiacRiskScore, getRiskBandLabel } from '../services/cardiacInsights';
import { getEcgHistory, getMonitoringCheckIns } from '../services/healthStore';
import type { ECGAnalysisRecord, MonitoringCheckIn } from '../types';
import Button from './ui/Button';
import StatsOverview from './stats/StatsOverview';
import RecentPredictions from './predictions/RecentPredictions';
import RiskTimeline from './dashboard/RiskTimeline';
import MonitoringPanel from './dashboard/MonitoringPanel';

const Dashboard: React.FC = () => {
  const { user } = useAuthStore();
  const {
    totalUsers,
    totalPredictions,
    recentPredictions,
    allPredictions,
    latestPrediction,
    loading,
    error,
    fetchStats,
  } = useDashboardStore();

  useEffect(() => {
    if (user?.id) {
      void fetchStats(user.id);
    }
  }, [fetchStats, user?.id]);

  const timeline = useMemo(() => buildPredictionTimeline(allPredictions), [allPredictions]);
  const timelineNarrative = useMemo(() => buildTrendNarrative(timeline), [timeline]);
  const latestRiskScore = latestPrediction ? computeCardiacRiskScore(latestPrediction.prediction_data) : null;
  const carePlan = latestPrediction ? buildNextSteps(latestPrediction.prediction_data, latestPrediction.prediction_result) : [];

  const [checkIns, setCheckIns] = useState<MonitoringCheckIn[]>([]);
  const [latestEcg, setLatestEcg] = useState<ECGAnalysisRecord | undefined>(undefined);

  useEffect(() => {
    if (!user?.id) {
      setCheckIns([]);
      setLatestEcg(undefined);
      return;
    }
    let active = true;
    void Promise.all([getMonitoringCheckIns(user.id), getEcgHistory(user.id)]).then(
      ([monitoring, ecgHistory]) => {
        if (!active) return;
        setCheckIns(monitoring);
        setLatestEcg(ecgHistory[0]);
      }
    );
    return () => {
      active = false;
    };
  }, [user?.id]);

  if (!user) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-14 text-center">
        <p className="text-lg text-slate-600">Sign in to unlock your Cardios dashboard.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-5">
          <div className="h-48 rounded-[32px] bg-emerald-100/70" />
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {[...Array(4)].map((_, index) => (
              <div key={index} className="h-36 rounded-[28px] bg-emerald-100/70" />
            ))}
          </div>
          <div className="h-80 rounded-[32px] bg-emerald-100/70" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="rounded-[28px] border border-red-200 bg-red-50 px-6 py-5 text-red-700">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-16">
      <section className="bg-gradient-to-br from-[#0b3023] via-[#0c5a3e] to-[#13a868] px-4 py-14 text-white sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-8 grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
            <div>
              <div className="inline-flex rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-50">
                Cardios command center
              </div>
              <h1 className="mt-5 font-sora text-4xl font-semibold md:text-5xl">
                Welcome back, {user.email?.split('@')[0]}
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-8 text-emerald-50/80">
                Review your latest cardiac signals, compare AI assessments over time, and keep a
                between-visits monitoring trail in one place.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <Link to="/predict">
                  <Button className="bg-white text-slate-950 hover:bg-emerald-50">
                    New AI assessment
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
                <Link to="/predict-ecg">
                  <Button variant="secondary" className="border-white/20 bg-white/10 text-white hover:bg-white/15">
                    Open ECG Lab
                    <Waves className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <QuickInsight
                title="Latest assessment"
                value={latestPrediction ? getRiskBandLabel(latestPrediction.prediction_result.includes('High') ? 'high' : latestRiskScore && latestRiskScore >= 38 ? 'elevated' : 'stable') : 'No data'}
                detail={latestPrediction ? latestPrediction.prediction_result : 'Run your first AI cardiac assessment.'}
                icon={<HeartPulse className="h-5 w-5" />}
              />
              <QuickInsight
                title="Monitoring streak"
                value={checkIns.length ? `${checkIns.length} check-ins` : 'Start today'}
                detail={checkIns[0] ? `Last entry ${new Date(checkIns[0].recordedAt).toLocaleDateString()}` : 'Add fatigue, sleep, and symptom trends.'}
                icon={<NotebookText className="h-5 w-5" />}
              />
            </div>
          </div>

          <StatsOverview
            totalUsers={totalUsers}
            totalPredictions={totalPredictions}
            userAssessments={allPredictions.length}
            monitoringCheckIns={checkIns.length}
          />
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[1.2fr_0.8fr] lg:px-8">
        <div className="space-y-6">
          <RiskTimeline timeline={timeline} narrative={timelineNarrative} />
          <RecentPredictions predictions={recentPredictions} />
        </div>

        <div className="space-y-6">
          <MonitoringPanel userId={user.id} />
          <div className="cardios-shell rounded-[32px] p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                <HeartPulse className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Action plan</p>
                <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">What Cardios suggests next</h2>
              </div>
            </div>

            {carePlan.length === 0 ? (
              <p className="rounded-[24px] bg-emerald-50/60 px-4 py-4 text-sm text-slate-600">
                Complete an assessment to unlock guided next steps and follow-up cues.
              </p>
            ) : (
              <div className="space-y-3">
                {carePlan.map((step) => (
                  <div key={step} className="rounded-[24px] border border-emerald-100 bg-white px-4 py-4 text-sm leading-7 text-slate-600">
                    {step}
                  </div>
                ))}
              </div>
            )}

            <div className="mt-6 rounded-[24px] bg-[#08251a] p-5 text-white">
              <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">ECG comparison</p>
              <p className="mt-3 font-sora text-xl font-semibold">
                {latestEcg ? latestEcg.prediction : 'No ECG study saved yet'}
              </p>
              <p className="mt-2 text-sm text-emerald-50/80">
                {latestEcg
                  ? latestEcg.confidence > 0
                    ? `Latest ECG confidence ${latestEcg.confidence.toFixed(1)}%. Open ECG Lab to compare against previous traces.`
                    : 'Confidence was withheld for the latest trace because of poor signal quality. Open ECG Lab to review it.'
                  : 'Upload a CSV trace in ECG Lab to start comparison history.'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const QuickInsight = ({
  title,
  value,
  detail,
  icon,
}: {
  title: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) => (
  <div className="rounded-[30px] border border-white/10 bg-white/10 p-5 backdrop-blur-sm">
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[0.18em] text-emerald-100/70">{title}</p>
        <p className="mt-3 font-sora text-2xl font-semibold text-white">{value}</p>
        <p className="mt-2 text-sm text-emerald-50/75">{detail}</p>
      </div>
      <div className="rounded-2xl bg-white/10 p-3 text-emerald-100">{icon}</div>
    </div>
  </div>
);

export default Dashboard;
