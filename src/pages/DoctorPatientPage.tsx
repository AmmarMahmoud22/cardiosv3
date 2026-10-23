import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  BellRing,
  ClipboardList,
  HeartPulse,
  MessageSquarePlus,
  MonitorDot,
  Save,
  Stethoscope,
} from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { useAuthStore } from '../stores/authStore';
import {
  acknowledgePatientAlert,
  addDoctorNote,
  getDoctorPatientDetail,
} from '../services/doctorCare';
import type { AlertSeverity, AlertStatus, DoctorPatientDetail } from '../types';

const severityStyles: Record<AlertSeverity, string> = {
  low: 'border-sky-200 bg-sky-50 text-sky-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-800',
  high: 'border-orange-200 bg-orange-50 text-orange-800',
  critical: 'border-red-200 bg-red-50 text-red-700',
};

const statusStyles: Record<AlertStatus, string> = {
  unread: 'bg-red-50 text-red-700',
  acknowledged: 'bg-amber-50 text-amber-800',
  resolved: 'bg-emerald-50 text-emerald-700',
  dismissed: 'bg-slate-100 text-slate-600',
};

const formatDate = (value: string | null | undefined): string => {
  if (!value) return 'No data';
  return new Date(value).toLocaleString();
};

const DoctorPatientPage: React.FC = () => {
  const { patientId } = useParams();
  const { user } = useAuthStore();
  const [detail, setDetail] = useState<DoctorPatientDetail | null>(null);
  const [note, setNote] = useState('');
  const [visibleToPatient, setVisibleToPatient] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadDetail = React.useCallback(async () => {
    if (!user?.id || !patientId) return;
    setLoading(true);
    setError('');

    try {
      const nextDetail = await getDoctorPatientDetail(user.id, patientId);
      setDetail(nextDetail);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Could not load patient details.');
    } finally {
      setLoading(false);
    }
  }, [patientId, user?.id]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleAcknowledge = async (alertId: string) => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await acknowledgePatientAlert(alertId);
      setSuccess('Alert acknowledged.');
      await loadDetail();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Could not acknowledge alert.');
    } finally {
      setSaving(false);
    }
  };

  const handleNoteSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user?.id || !patientId) return;

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await addDoctorNote({
        doctorId: user.id,
        patientId,
        body: note,
        visibleToPatient,
      });
      setNote('');
      setVisibleToPatient(false);
      setSuccess('Doctor note saved.');
      await loadDetail();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Could not save doctor note.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-5">
          <div className="h-44 rounded-[32px] bg-emerald-100/70" />
          <div className="grid gap-4 md:grid-cols-3">
            {[...Array(3)].map((_, index) => (
              <div key={index} className="h-32 rounded-[28px] bg-emerald-100/70" />
            ))}
          </div>
          <div className="h-96 rounded-[32px] bg-emerald-100/70" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <Link
        to="/doctor"
        className="inline-flex min-h-11 items-center gap-2 rounded-full px-3 text-sm font-semibold text-emerald-800 transition-colors hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to doctor dashboard
      </Link>

      {error ? (
        <div className="mt-5 rounded-[24px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="mt-5 rounded-[24px] border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-800">
          {success}
        </div>
      ) : null}

      {!detail ? (
        <Card className="mt-5 text-center">
          <ClipboardList className="mx-auto h-9 w-9 text-emerald-700" />
          <h1 className="mt-4 font-sora text-2xl font-semibold text-slate-950">
            Patient timeline unavailable
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Confirm that this patient is actively assigned to the current doctor.
          </p>
        </Card>
      ) : (
        <>
          <section className="mt-4 rounded-[32px] bg-[#08251a] px-6 py-8 text-white sm:px-8">
            <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
                  Patient detail
                </p>
                <h1 className="mt-4 font-sora text-3xl font-semibold sm:text-4xl">
                  {detail.patientName}
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-emerald-50/80">
                  {detail.email} | {detail.aiSummary}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/10 p-4">
                <ClipboardList className="h-8 w-8 text-emerald-100" />
              </div>
            </div>
          </section>

          <div className="mt-6 grid gap-4 md:grid-cols-4">
            <SummaryCard
              label="Latest ECG"
              value={detail.latestEcg?.prediction ?? 'No ECG'}
              detail={detail.latestEcg ? `${detail.latestEcg.confidence.toFixed(1)}% confidence` : 'No saved analysis'}
              icon={<HeartPulse className="h-5 w-5" />}
            />
            <SummaryCard
              label="Risk score"
              value={detail.latestRisk ? `${detail.latestRisk.score}/100` : 'No risk'}
              detail={detail.latestRisk?.result ?? 'No AI assessment'}
              icon={<Stethoscope className="h-5 w-5" />}
            />
            <SummaryCard
              label="Unread alerts"
              value={`${detail.unreadAlerts}`}
              detail={detail.highestAlertSeverity ? `Highest: ${detail.highestAlertSeverity}` : 'No unread alerts'}
              icon={<BellRing className="h-5 w-5" />}
            />
            <SummaryCard
              label="Device"
              value={detail.assignedDevice?.displayName ?? 'No device'}
              detail={
                detail.assignedDevice
                  ? `${detail.assignedDevice.connected ? 'Online' : 'Offline'} | ${detail.assignedDevice.deviceId}`
                  : 'No device assigned'
              }
              icon={<MonitorDot className="h-5 w-5" />}
            />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-6">
              <TimelineSection
                title="Clinical alerts"
                empty="No alerts for this patient."
                icon={<AlertTriangle className="h-5 w-5" />}
              >
                {detail.alerts.map((alert) => (
                  <article key={alert.id} className="rounded-[24px] border border-slate-100 bg-white p-4 shadow-sm">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${severityStyles[alert.severity]}`}>
                            {alert.severity}
                          </span>
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[alert.status]}`}>
                            {alert.status}
                          </span>
                        </div>
                        <h3 className="mt-3 font-sora text-lg font-semibold text-slate-950">{alert.title}</h3>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{alert.message}</p>
                        <p className="mt-2 text-xs text-slate-500">{formatDate(alert.createdAt)}</p>
                      </div>
                      {alert.status === 'unread' ? (
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => void handleAcknowledge(alert.id)}
                          className="inline-flex min-h-11 items-center justify-center rounded-full border border-emerald-200 px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Acknowledge
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </TimelineSection>

              <TimelineSection
                title="Risk history"
                empty="No risk assessments yet."
                icon={<Stethoscope className="h-5 w-5" />}
              >
                {detail.riskHistory.map((risk) => (
                  <CompactRow
                    key={risk.id}
                    title={`${risk.score}/100 | ${risk.result}`}
                    detail={formatDate(risk.createdAt)}
                  />
                ))}
              </TimelineSection>

              <TimelineSection
                title="ECG history"
                empty="No ECG analyses yet."
                icon={<HeartPulse className="h-5 w-5" />}
              >
                {detail.ecgHistory.map((ecg) => (
                  <CompactRow
                    key={ecg.id}
                    title={`${ecg.prediction} | ${ecg.confidence.toFixed(1)}%`}
                    detail={`${ecg.fileName ?? 'ECG file'} | ${formatDate(ecg.createdAt)}`}
                  />
                ))}
              </TimelineSection>
            </div>

            <div className="space-y-6">
              <Card>
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                    <MessageSquarePlus className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
                      Doctor notes
                    </p>
                    <h2 className="font-sora text-2xl font-semibold text-slate-950">
                      Follow-up notes
                    </h2>
                  </div>
                </div>

                <form onSubmit={handleNoteSubmit} className="mt-5 space-y-4">
                  <textarea
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    rows={5}
                    placeholder="Write a concise clinical follow-up note..."
                    className="w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100"
                    required
                  />
                  <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                    <input
                      type="checkbox"
                      checked={visibleToPatient}
                      onChange={(event) => setVisibleToPatient(event.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    Visible to patient
                  </label>
                  <Button type="submit" className="w-full" disabled={saving}>
                    <Save className="h-4 w-4" />
                    {saving ? 'Saving...' : 'Save note'}
                  </Button>
                </form>

                <div className="mt-6 space-y-3">
                  {detail.notes.length === 0 ? (
                    <p className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/50 px-4 py-5 text-center text-sm text-slate-600">
                      No doctor notes yet.
                    </p>
                  ) : (
                    detail.notes.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                        <p className="text-sm leading-6 text-slate-700">{item.body}</p>
                        <p className="mt-2 text-xs text-slate-500">
                          {formatDate(item.createdAt)} | {item.visibleToPatient ? 'Patient-visible' : 'Doctor-only'}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </Card>

              <TimelineSection
                title="Monitoring check-ins"
                empty="No monitoring check-ins yet."
                icon={<ClipboardList className="h-5 w-5" />}
              >
                {detail.checkIns.map((checkIn) => (
                  <CompactRow
                    key={checkIn.id}
                    title={`${checkIn.restingHeartRate} bpm | fatigue ${checkIn.fatigue}/10`}
                    detail={`Breathlessness ${checkIn.breathlessness}/10 | Sleep ${checkIn.sleepHours}h | ${formatDate(checkIn.recordedAt)}`}
                  />
                ))}
              </TimelineSection>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

const SummaryCard = ({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) => (
  <Card className="rounded-2xl">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
        <p className="mt-3 truncate font-sora text-xl font-semibold text-slate-950">{value}</p>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{detail}</p>
      </div>
      <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">{icon}</div>
    </div>
  </Card>
);

const TimelineSection = ({
  title,
  empty,
  icon,
  children,
}: {
  title: string;
  empty: string;
  icon: React.ReactNode;
  children: React.ReactNode[];
}) => (
  <Card>
    <div className="flex items-center gap-3">
      <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">{icon}</div>
      <h2 className="font-sora text-2xl font-semibold text-slate-950">{title}</h2>
    </div>
    <div className="mt-5 space-y-3">
      {children.length ? (
        children
      ) : (
        <p className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/50 px-4 py-5 text-center text-sm text-slate-600">
          {empty}
        </p>
      )}
    </div>
  </Card>
);

const CompactRow = ({ title, detail }: { title: string; detail: string }) => (
  <article className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
    <h3 className="font-semibold text-slate-950">{title}</h3>
    <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
  </article>
);

export default DoctorPatientPage;
