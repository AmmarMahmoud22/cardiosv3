import React, { useEffect, useMemo, useState } from 'react';
import { Moon, Plus, TimerReset, Waves, Wind } from 'lucide-react';
import { addMonitoringCheckIn, getMonitoringCheckIns } from '../../services/healthStore';
import type { MonitoringCheckIn } from '../../types';
import Button from '../ui/Button';
import Card from '../ui/Card';

const createEmptyCheckIn = (): Omit<MonitoringCheckIn, 'id' | 'userId' | 'recordedAt'> => ({
  restingHeartRate: 72,
  breathlessness: 1,
  fatigue: 1,
  stressLevel: 2,
  activityMinutes: 30,
  sleepHours: 7,
  note: '',
});

const MonitoringPanel: React.FC<{ userId: string }> = ({ userId }) => {
  const [checkIns, setCheckIns] = useState<MonitoringCheckIn[]>([]);
  const [draft, setDraft] = useState(createEmptyCheckIn());

  useEffect(() => {
    let active = true;
    void getMonitoringCheckIns(userId).then((rows) => {
      if (active) setCheckIns(rows);
    });
    return () => {
      active = false;
    };
  }, [userId]);

  const latestCheckIn = checkIns[0];
  const summary = useMemo(() => {
    if (!latestCheckIn) {
      return null;
    }

    const readinessScore = Math.max(
      0,
      100 -
        latestCheckIn.breathlessness * 14 -
        latestCheckIn.fatigue * 12 -
        latestCheckIn.stressLevel * 8 +
        Math.min(latestCheckIn.activityMinutes, 60) * 0.35
    );

    return {
      readinessScore: Math.round(readinessScore),
      label:
        readinessScore >= 72 ? 'Recovery looks steady' : readinessScore >= 50 ? 'Monitor symptoms closely' : 'Escalate follow-up attention',
    };
  }, [latestCheckIn]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    const savedCheckIn: MonitoringCheckIn = {
      id: crypto.randomUUID(),
      userId,
      recordedAt: new Date().toISOString(),
      ...draft,
    };

    await addMonitoringCheckIn(savedCheckIn);
    setCheckIns(await getMonitoringCheckIns(userId));
    setDraft(createEmptyCheckIn());
  };

  const summaryCards = [
    {
      title: 'Resting HR',
      value: latestCheckIn ? `${latestCheckIn.restingHeartRate} bpm` : 'Not set',
      icon: <Waves className="h-4 w-4" />,
    },
    {
      title: 'Sleep',
      value: latestCheckIn ? `${latestCheckIn.sleepHours} hrs` : 'Not set',
      icon: <Moon className="h-4 w-4" />,
    },
    {
      title: 'Breathlessness',
      value: latestCheckIn ? `${latestCheckIn.breathlessness}/3` : 'Not set',
      icon: <Wind className="h-4 w-4" />,
    },
  ];

  return (
    <Card>
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Continuous monitoring</p>
          <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">Daily cardiac check-ins</h2>
        </div>
        <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
          <TimerReset className="h-5 w-5" />
        </div>
      </div>

      {summary && (
        <div className="mb-6 rounded-[28px] bg-[#08251a] p-5 text-white">
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">Latest readiness</p>
          <div className="mt-3 flex items-end justify-between gap-6">
            <div>
              <p className="font-sora text-4xl font-semibold">{summary.readinessScore}</p>
              <p className="mt-2 text-sm text-emerald-50/80">{summary.label}</p>
              <p className="mt-2 text-xs text-emerald-50/60">
                Wellness heuristic from your check-in — not a medical score.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {summaryCards.map((item) => (
                <div key={item.title} className="rounded-3xl bg-white/8 px-4 py-3 text-center">
                  <div className="mb-2 inline-flex rounded-full bg-white/10 p-2 text-emerald-100">{item.icon}</div>
                  <p className="text-xs uppercase tracking-[0.14em] text-emerald-50/60">{item.title}</p>
                  <p className="mt-1 text-sm font-semibold text-white">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-2">
        <MetricInput
          label="Resting heart rate"
          value={draft.restingHeartRate}
          onChange={(value) => setDraft((current) => ({ ...current, restingHeartRate: value }))}
          min={40}
          max={160}
        />
        <MetricInput
          label="Sleep hours"
          value={draft.sleepHours}
          onChange={(value) => setDraft((current) => ({ ...current, sleepHours: value }))}
          min={0}
          max={14}
          step={0.5}
        />
        <MetricInput
          label="Activity minutes"
          value={draft.activityMinutes}
          onChange={(value) => setDraft((current) => ({ ...current, activityMinutes: value }))}
          min={0}
          max={180}
        />
        <MetricInput
          label="Breathlessness (0-3)"
          value={draft.breathlessness}
          onChange={(value) => setDraft((current) => ({ ...current, breathlessness: value }))}
          min={0}
          max={3}
        />
        <MetricInput
          label="Fatigue (0-3)"
          value={draft.fatigue}
          onChange={(value) => setDraft((current) => ({ ...current, fatigue: value }))}
          min={0}
          max={3}
        />
        <MetricInput
          label="Stress level (0-5)"
          value={draft.stressLevel}
          onChange={(value) => setDraft((current) => ({ ...current, stressLevel: value }))}
          min={0}
          max={5}
        />

        <div className="lg:col-span-2">
          <label className="text-sm font-medium text-slate-700">Clinician note or symptom note</label>
          <textarea
            rows={3}
            value={draft.note}
            onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))}
            className="mt-2 block w-full rounded-[24px] border border-emerald-100 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200"
            placeholder="Optional note about chest discomfort, recovery, or follow-up context."
          />
        </div>

        <div className="lg:col-span-2">
          <Button type="submit">
            <Plus className="h-4 w-4" />
            Save today&apos;s check-in
          </Button>
        </div>
      </form>

      <div className="mt-6 space-y-3">
        <h3 className="font-sora text-lg font-semibold text-slate-950">Recent check-ins</h3>
        {checkIns.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-emerald-200 bg-emerald-50/60 p-5 text-sm text-slate-600">
            No monitoring entries yet. Add your first check-in to start building a between-visits story.
          </div>
        ) : (
          checkIns.slice(0, 4).map((checkIn) => (
            <div key={checkIn.id} className="rounded-[24px] border border-emerald-100 bg-white px-4 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">
                    {new Date(checkIn.recordedAt).toLocaleDateString()} at{' '}
                    {new Date(checkIn.recordedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    HR {checkIn.restingHeartRate} bpm, sleep {checkIn.sleepHours} hrs, activity {checkIn.activityMinutes} mins
                  </p>
                </div>
                <div className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">
                  Breathlessness {checkIn.breathlessness}/3
                </div>
              </div>
              {checkIn.note && <p className="mt-3 text-sm leading-7 text-slate-600">{checkIn.note}</p>}
            </div>
          ))
        )}
      </div>
    </Card>
  );
};

const MetricInput = ({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
}) => (
  <div>
    <label className="text-sm font-medium text-slate-700">{label}</label>
    <input
      type="number"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(event) => onChange(Number(event.target.value))}
      className="mt-2 block w-full rounded-[24px] border border-emerald-100 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200"
    />
  </div>
);

export default MonitoringPanel;
