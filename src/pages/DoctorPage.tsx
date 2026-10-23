import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BellRing,
  HeartPulse,
  MonitorDot,
  Stethoscope,
  UsersRound,
} from 'lucide-react';
import Card from '../components/ui/Card';
import { useAuthStore } from '../stores/authStore';
import { getDoctorPatientOverviews } from '../services/doctorCare';
import type { AlertSeverity, DoctorPatientOverview, PatientReviewStatus } from '../types';

const statusStyles: Record<PatientReviewStatus, string> = {
  urgent: 'border-red-200 bg-red-50 text-red-700',
  needs_review: 'border-amber-200 bg-amber-50 text-amber-800',
  stable: 'border-emerald-200 bg-emerald-50 text-emerald-800',
};

const statusLabels: Record<PatientReviewStatus, string> = {
  urgent: 'Urgent review',
  needs_review: 'Needs review',
  stable: 'Stable watch',
};

const severityLabels: Record<AlertSeverity, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

const formatDate = (value: string | null | undefined): string => {
  if (!value) return 'No data';
  return new Date(value).toLocaleString();
};

const DoctorPage: React.FC = () => {
  const { user } = useAuthStore();
  const [patients, setPatients] = useState<DoctorPatientOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.id) return;
    let active = true;
    setLoading(true);
    setError('');

    void getDoctorPatientOverviews(user.id)
      .then((items) => {
        if (!active) return;
        setPatients(items);
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(caughtError instanceof Error ? caughtError.message : 'Could not load doctor dashboard.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [user?.id]);

  const summary = useMemo(() => {
    const urgent = patients.filter((patient) => patient.reviewStatus === 'urgent').length;
    const needsReview = patients.filter((patient) => patient.reviewStatus === 'needs_review').length;
    const unreadAlerts = patients.reduce((total, patient) => total + patient.unreadAlerts, 0);
    const onlineDevices = patients.filter((patient) => patient.assignedDevice?.connected).length;

    return { urgent, needsReview, unreadAlerts, onlineDevices };
  }, [patients]);

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="animate-pulse space-y-5">
          <div className="h-48 rounded-[32px] bg-emerald-100/70" />
          <div className="grid gap-4 md:grid-cols-4">
            {[...Array(4)].map((_, index) => (
              <div key={index} className="h-28 rounded-[28px] bg-emerald-100/70" />
            ))}
          </div>
          <div className="h-96 rounded-[32px] bg-emerald-100/70" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="rounded-[32px] bg-[#08251a] px-6 py-8 text-white sm:px-8">
        <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">
              Doctor workspace
            </p>
            <h1 className="mt-4 font-sora text-3xl font-semibold sm:text-4xl">
              Assigned patient review queue
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-emerald-50/80">
              Review care-team patients by screening status, latest ECG, risk assessment,
              monitoring check-in, device state, and unread review alerts.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/doctor/devices"
              className="inline-flex min-h-11 items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-200"
            >
              <MonitorDot className="h-4 w-4" />
              Manage devices
            </Link>
            <div className="rounded-2xl border border-white/10 bg-white/10 p-4">
              <Stethoscope className="h-8 w-8 text-emerald-100" />
            </div>
          </div>
        </div>
      </section>

      {error ? (
        <div className="mt-5 rounded-[24px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Assigned patients"
          value={`${patients.length}`}
          detail="Active and pending care-team links"
          icon={<UsersRound className="h-5 w-5" />}
        />
        <MetricCard
          label="Urgent review"
          value={`${summary.urgent}`}
          detail="High-priority screening patterns"
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="urgent"
        />
        <MetricCard
          label="Unread alerts"
          value={`${summary.unreadAlerts}`}
          detail={`${summary.needsReview} patients need follow-up`}
          icon={<BellRing className="h-5 w-5" />}
          tone={summary.unreadAlerts ? 'warn' : 'ok'}
        />
        <MetricCard
          label="Online devices"
          value={`${summary.onlineDevices}`}
          detail="Assigned ECG devices seen recently"
          icon={<MonitorDot className="h-5 w-5" />}
        />
      </div>

      <Card className="mt-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
              Patient queue
            </p>
            <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
              Care-team monitoring overview
            </h2>
          </div>
          <p className="text-sm text-slate-500">
            Screening support only. Review alerts are not diagnoses.
          </p>
        </div>

        {patients.length === 0 ? (
          <div className="mt-6 rounded-[24px] border border-dashed border-emerald-200 bg-emerald-50/50 px-5 py-8 text-center">
            <UsersRound className="mx-auto h-8 w-8 text-emerald-700" />
            <h3 className="mt-4 font-sora text-xl font-semibold text-slate-950">
              No assigned patients yet
            </h3>
            <p className="mx-auto mt-2 max-w-2xl text-sm leading-7 text-slate-600">
              Once an admin or doctor creates active care-team links in doctor_patients, patients
              will appear here with their latest ECG, risk, monitoring, alerts, and device state.
            </p>
          </div>
        ) : (
          <div className="mt-6 space-y-4">
            {patients.map((patient) => (
              <PatientQueueItem key={patient.patientId} patient={patient} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

const MetricCard = ({
  label,
  value,
  detail,
  icon,
  tone = 'default',
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
  tone?: 'default' | 'ok' | 'warn' | 'urgent';
}) => {
  const toneClass =
    tone === 'urgent'
      ? 'bg-red-50 text-red-700'
      : tone === 'warn'
        ? 'bg-amber-50 text-amber-700'
        : tone === 'ok'
          ? 'bg-emerald-50 text-emerald-700'
          : 'bg-slate-50 text-slate-700';

  return (
    <Card className="rounded-2xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
          <p className="mt-3 font-sora text-3xl font-semibold text-slate-950">{value}</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
        </div>
        <div className={`rounded-2xl p-3 ${toneClass}`}>{icon}</div>
      </div>
    </Card>
  );
};

const PatientQueueItem = ({ patient }: { patient: DoctorPatientOverview }) => (
  <article className="rounded-[24px] border border-slate-100 bg-white p-4 shadow-sm">
    <div className="grid gap-4 xl:grid-cols-[1.1fr_1.5fr_0.9fr] xl:items-center">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-sora text-xl font-semibold text-slate-950">{patient.patientName}</h3>
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusStyles[patient.reviewStatus]}`}>
            {statusLabels[patient.reviewStatus]}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-500">{patient.email}</p>
        <p className="mt-3 text-sm leading-6 text-slate-600">{patient.aiSummary}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4">
        <SignalTile
          label="Latest ECG"
          value={patient.latestEcg?.prediction ?? 'No ECG'}
          detail={
            patient.latestEcg
              ? `${patient.latestEcg.confidence.toFixed(1)}% | ${formatDate(patient.latestEcg.createdAt)}`
              : 'No saved ECG analysis'
          }
          icon={<HeartPulse className="h-4 w-4" />}
        />
        <SignalTile
          label="Risk"
          value={patient.latestRisk ? `${patient.latestRisk.score}/100` : 'No risk'}
          detail={patient.latestRisk?.result ?? 'No AI assessment'}
          icon={<Stethoscope className="h-4 w-4" />}
        />
        <SignalTile
          label="Check-in"
          value={patient.latestCheckIn ? `${patient.latestCheckIn.restingHeartRate} bpm` : 'No check-in'}
          detail={
            patient.latestCheckIn
              ? `Fatigue ${patient.latestCheckIn.fatigue}/10 | ${formatDate(patient.latestCheckIn.recordedAt)}`
              : 'No monitoring entry'
          }
          icon={<UsersRound className="h-4 w-4" />}
        />
        <SignalTile
          label="Device"
          value={patient.assignedDevice?.displayName ?? 'No device'}
          detail={
            patient.assignedDevice
              ? `${patient.assignedDevice.connected ? 'Online' : 'Offline'} | ${patient.assignedDevice.deviceId}`
              : 'No assigned ECG device'
          }
          icon={<MonitorDot className="h-4 w-4" />}
        />
      </div>

      <div className="flex flex-col gap-3 xl:items-end">
        <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-700 xl:w-full">
          <p className="font-semibold text-slate-950">{patient.unreadAlerts} unread alerts</p>
          <p className="mt-1 text-xs text-slate-500">
            Highest: {patient.highestAlertSeverity ? severityLabels[patient.highestAlertSeverity] : 'None'}
          </p>
        </div>
        <Link
          to={`/doctor/patients/${patient.patientId}`}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:ring-offset-2 xl:w-full"
        >
          Review patient
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  </article>
);

const SignalTile = ({
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
  <div className="min-w-0 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
      {icon}
      {label}
    </div>
    <p className="mt-2 truncate text-sm font-semibold text-slate-950">{value}</p>
    <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{detail}</p>
  </div>
);

export default DoctorPage;
