import { supabase } from '../lib/supabase';
import { computeCardiacRiskScore } from './cardiacInsights';
import type {
  AlertSeverity,
  CareTeamStatus,
  ClinicalAlert,
  DeviceAssignmentStatus,
  DoctorNote,
  DoctorPatientDetail,
  DoctorPatientOverview,
  FormData,
  PatientReviewStatus,
} from '../types';
import { isAbnormalLabel } from '../utils/ecg';

type DoctorPatientRow = {
  doctor_id: string;
  patient_id: string;
  status: CareTeamStatus;
  created_at: string;
};

type ProfileRow = {
  id: string;
  email: string | null;
};

type ExtendedProfileRow = {
  id: string;
  full_name: string | null;
};

type PredictionRow = {
  id: string;
  user_id: string;
  prediction_data: FormData;
  prediction_result: string;
  created_at: string;
};

type EcgRow = {
  id: string;
  user_id: string;
  file_name?: string | null;
  prediction: string;
  confidence: number;
  signal_preview?: number[] | unknown;
  created_at: string;
};

type MonitoringRow = {
  id: string;
  user_id: string;
  recorded_at: string;
  resting_heart_rate: number;
  breathlessness: number;
  fatigue: number;
  stress_level?: number;
  activity_minutes?: number;
  sleep_hours?: number;
  note?: string;
};

type DeviceRow = {
  id: string;
  device_id: string;
  display_name: string;
  patient_id: string | null;
  status: DeviceAssignmentStatus;
  last_seen_at: string | null;
};

type AlertRow = {
  id: string;
  patient_id: string;
  doctor_id?: string | null;
  source?: ClinicalAlert['source'];
  severity: AlertSeverity;
  status: string;
  title?: string;
  message?: string;
  reason_codes?: string[];
  related_device_id?: string | null;
  related_record_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  acknowledged_at?: string | null;
};

type DoctorNoteRow = {
  id: string;
  doctor_id: string;
  patient_id: string;
  body: string;
  visible_to_patient: boolean;
  created_at: string;
  updated_at: string;
};

const SEVERITY_RANK: Record<AlertSeverity, number> = {
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};

const latestByUser = <T extends { user_id: string; created_at?: string; recorded_at?: string }>(
  rows: T[],
  userId: string
): T | null =>
  rows
    .filter((row) => row.user_id === userId)
    .sort((left, right) => {
      const leftDate = left.created_at ?? left.recorded_at ?? '';
      const rightDate = right.created_at ?? right.recorded_at ?? '';
      return new Date(rightDate).getTime() - new Date(leftDate).getTime();
    })[0] ?? null;

const isConnected = (lastSeenAt: string | null): boolean => {
  if (!lastSeenAt) return false;
  const ageMs = Date.now() - new Date(lastSeenAt).getTime();
  return ageMs >= 0 && ageMs <= 10 * 60 * 1000;
};

const getHighestSeverity = (alerts: AlertRow[]): AlertSeverity | null =>
  alerts.reduce<AlertSeverity | null>((highest, alert) => {
    if (!highest || SEVERITY_RANK[alert.severity] > SEVERITY_RANK[highest]) {
      return alert.severity;
    }
    return highest;
  }, null);

const getReviewStatus = ({
  unreadAlerts,
  highestAlertSeverity,
  latestRiskScore,
  latestRiskResult,
  latestEcgPrediction,
  deviceConnected,
  hasDevice,
}: {
  unreadAlerts: number;
  highestAlertSeverity: AlertSeverity | null;
  latestRiskScore: number | null;
  latestRiskResult: string | null;
  latestEcgPrediction: string | null;
  deviceConnected: boolean;
  hasDevice: boolean;
}): PatientReviewStatus => {
  if (
    highestAlertSeverity === 'critical' ||
    highestAlertSeverity === 'high' ||
    (latestEcgPrediction && isAbnormalLabel(latestEcgPrediction))
  ) {
    return 'urgent';
  }

  if (
    unreadAlerts > 0 ||
    highestAlertSeverity === 'medium' ||
    latestRiskResult?.includes('High') ||
    (latestRiskScore !== null && latestRiskScore >= 65) ||
    (hasDevice && !deviceConnected)
  ) {
    return 'needs_review';
  }

  return 'stable';
};

const buildAiSummary = (overview: {
  reviewStatus: PatientReviewStatus;
  unreadAlerts: number;
  highestAlertSeverity: AlertSeverity | null;
  latestRiskScore: number | null;
  latestEcgPrediction: string | null;
  deviceConnected: boolean;
  hasDevice: boolean;
}): string => {
  if (overview.reviewStatus === 'urgent') {
    return 'AI review support sees a high-priority screening pattern. Clinician review is recommended.';
  }

  if (overview.unreadAlerts > 0) {
    return `AI review support found ${overview.unreadAlerts} unread review alert${overview.unreadAlerts === 1 ? '' : 's'} for follow-up.`;
  }

  if (overview.latestRiskScore !== null && overview.latestRiskScore >= 65) {
    return 'AI review support sees elevated risk inputs that should remain on the care-team watchlist.';
  }

  if (overview.hasDevice && !overview.deviceConnected) {
    return 'The assigned ECG device has not checked in recently. Confirm device power and patient setup.';
  }

  if (overview.latestEcgPrediction) {
    return 'Recent screening data is available for routine clinician review.';
  }

  return 'No recent high-priority screening signals are available yet.';
};

const emptyByPatient = <T extends { patient_id?: string | null }>(rows: T[], patientId: string): T[] =>
  rows.filter((row) => row.patient_id === patientId);

const toClinicalAlert = (row: AlertRow): ClinicalAlert => ({
  id: row.id,
  patientId: row.patient_id,
  doctorId: row.doctor_id ?? null,
  source: row.source ?? 'monitoring_checkin',
  severity: row.severity,
  title: row.title ?? 'Clinical review alert',
  message: row.message ?? 'Review this patient signal.',
  reasonCodes: row.reason_codes ?? [],
  status: row.status as ClinicalAlert['status'],
  relatedDeviceId: row.related_device_id ?? null,
  relatedRecordId: row.related_record_id ?? null,
  metadata: row.metadata ?? {},
  createdAt: row.created_at,
  acknowledgedAt: row.acknowledged_at ?? null,
});

const toDoctorNote = (row: DoctorNoteRow): DoctorNote => ({
  id: row.id,
  doctorId: row.doctor_id,
  patientId: row.patient_id,
  body: row.body,
  visibleToPatient: row.visible_to_patient,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export const getDoctorPatientOverviews = async (
  doctorId: string
): Promise<DoctorPatientOverview[]> => {
  const { data: links, error: linksError } = await supabase
    .from('doctor_patients')
    .select('doctor_id, patient_id, status, created_at')
    .eq('doctor_id', doctorId)
    .neq('status', 'archived')
    .order('created_at', { ascending: false });

  if (linksError) {
    console.error('Error loading doctor-patient links:', linksError);
    throw new Error('Could not load assigned patients.');
  }

  const relationshipRows = (links ?? []) as DoctorPatientRow[];
  const patientIds = [...new Set(relationshipRows.map((row) => row.patient_id))];

  if (!patientIds.length) return [];

  const [
    profilesResult,
    extendedProfilesResult,
    predictionsResult,
    ecgResult,
    monitoringResult,
    devicesResult,
    alertsResult,
  ] = await Promise.all([
    supabase.from('profiles').select('id, email').in('id', patientIds),
    supabase.from('extended_profiles').select('id, full_name').in('id', patientIds),
    supabase
      .from('predictions')
      .select('id, user_id, prediction_data, prediction_result, created_at')
      .in('user_id', patientIds)
      .order('created_at', { ascending: false })
      .limit(250),
    supabase
      .from('ecg_analyses')
      .select('id, user_id, prediction, confidence, created_at')
      .in('user_id', patientIds)
      .order('created_at', { ascending: false })
      .limit(250),
    supabase
      .from('monitoring_checkins')
      .select('id, user_id, recorded_at, resting_heart_rate, breathlessness, fatigue')
      .in('user_id', patientIds)
      .order('recorded_at', { ascending: false })
      .limit(250),
    supabase
      .from('devices')
      .select('id, device_id, display_name, patient_id, status, last_seen_at')
      .in('patient_id', patientIds)
      .order('last_seen_at', { ascending: false, nullsFirst: false }),
    supabase
      .from('alerts')
      .select('id, patient_id, severity, status, created_at')
      .in('patient_id', patientIds)
      .order('created_at', { ascending: false })
      .limit(250),
  ]);

  const failed = [
    profilesResult.error,
    extendedProfilesResult.error,
    predictionsResult.error,
    ecgResult.error,
    monitoringResult.error,
    devicesResult.error,
    alertsResult.error,
  ].find(Boolean);

  if (failed) {
    console.error('Error loading doctor dashboard data:', failed);
    throw new Error('Could not load patient monitoring data.');
  }

  const profiles = new Map((profilesResult.data ?? []).map((row) => [(row as ProfileRow).id, row as ProfileRow]));
  const extendedProfiles = new Map(
    (extendedProfilesResult.data ?? []).map((row) => [
      (row as ExtendedProfileRow).id,
      row as ExtendedProfileRow,
    ])
  );
  const predictions = (predictionsResult.data ?? []) as PredictionRow[];
  const ecgRows = (ecgResult.data ?? []) as EcgRow[];
  const monitoringRows = (monitoringResult.data ?? []) as MonitoringRow[];
  const deviceRows = (devicesResult.data ?? []) as DeviceRow[];
  const alertRows = (alertsResult.data ?? []) as AlertRow[];

  return relationshipRows.map((link) => {
    const profile = profiles.get(link.patient_id);
    const extendedProfile = extendedProfiles.get(link.patient_id);
    const latestRisk = latestByUser(predictions, link.patient_id);
    const latestEcg = latestByUser(ecgRows, link.patient_id);
    const latestCheckIn = latestByUser(monitoringRows, link.patient_id);
    const assignedDevice = emptyByPatient(deviceRows, link.patient_id)[0] ?? null;
    const patientAlerts = emptyByPatient(alertRows, link.patient_id);
    const unreadAlerts = patientAlerts.filter((alert) => alert.status === 'unread').length;
    const highestAlertSeverity = getHighestSeverity(patientAlerts.filter((alert) => alert.status === 'unread'));
    const riskScore = latestRisk ? computeCardiacRiskScore(latestRisk.prediction_data) : null;
    const deviceConnected = assignedDevice ? isConnected(assignedDevice.last_seen_at) : false;
    const reviewStatus = getReviewStatus({
      unreadAlerts,
      highestAlertSeverity,
      latestRiskScore: riskScore,
      latestRiskResult: latestRisk?.prediction_result ?? null,
      latestEcgPrediction: latestEcg?.prediction ?? null,
      deviceConnected,
      hasDevice: !!assignedDevice,
    });

    return {
      patientId: link.patient_id,
      patientName: extendedProfile?.full_name || profile?.email?.split('@')[0] || 'Unnamed patient',
      email: profile?.email ?? 'No email',
      relationshipStatus: link.status,
      assignedAt: link.created_at,
      reviewStatus,
      latestRisk: latestRisk
        ? {
            id: latestRisk.id,
            result: latestRisk.prediction_result,
            score: riskScore ?? 0,
            createdAt: latestRisk.created_at,
          }
        : null,
      latestEcg: latestEcg
        ? {
            id: latestEcg.id,
            prediction: latestEcg.prediction,
            confidence: latestEcg.confidence,
            createdAt: latestEcg.created_at,
          }
        : null,
      latestCheckIn: latestCheckIn
        ? {
            id: latestCheckIn.id,
            recordedAt: latestCheckIn.recorded_at,
            restingHeartRate: latestCheckIn.resting_heart_rate,
            breathlessness: latestCheckIn.breathlessness,
            fatigue: latestCheckIn.fatigue,
          }
        : null,
      assignedDevice: assignedDevice
        ? {
            id: assignedDevice.id,
            deviceId: assignedDevice.device_id,
            displayName: assignedDevice.display_name,
            status: assignedDevice.status,
            lastSeenAt: assignedDevice.last_seen_at,
            connected: deviceConnected,
          }
        : null,
      unreadAlerts,
      highestAlertSeverity,
      aiSummary: buildAiSummary({
        reviewStatus,
        unreadAlerts,
        highestAlertSeverity,
        latestRiskScore: riskScore,
        latestEcgPrediction: latestEcg?.prediction ?? null,
        deviceConnected,
        hasDevice: !!assignedDevice,
      }),
    };
  });
};

export const getDoctorPatientDetail = async (
  doctorId: string,
  patientId: string
): Promise<DoctorPatientDetail> => {
  const overviews = await getDoctorPatientOverviews(doctorId);
  const overview = overviews.find((item) => item.patientId === patientId);

  if (!overview) {
    throw new Error('This patient is not assigned to the current doctor.');
  }

  const [
    predictionsResult,
    ecgResult,
    monitoringResult,
    alertsResult,
    notesResult,
  ] = await Promise.all([
    supabase
      .from('predictions')
      .select('id, user_id, prediction_data, prediction_result, created_at')
      .eq('user_id', patientId)
      .order('created_at', { ascending: false })
      .limit(20),
    supabase
      .from('ecg_analyses')
      .select('id, user_id, file_name, prediction, confidence, signal_preview, created_at')
      .eq('user_id', patientId)
      .order('created_at', { ascending: false })
      .limit(20),
    supabase
      .from('monitoring_checkins')
      .select('id, user_id, recorded_at, resting_heart_rate, breathlessness, fatigue, stress_level, activity_minutes, sleep_hours, note')
      .eq('user_id', patientId)
      .order('recorded_at', { ascending: false })
      .limit(20),
    supabase
      .from('alerts')
      .select('id, patient_id, doctor_id, source, severity, title, message, reason_codes, status, related_device_id, related_record_id, metadata, created_at, acknowledged_at')
      .eq('patient_id', patientId)
      .order('created_at', { ascending: false })
      .limit(30),
    supabase
      .from('doctor_notes')
      .select('id, doctor_id, patient_id, body, visible_to_patient, created_at, updated_at')
      .eq('patient_id', patientId)
      .order('created_at', { ascending: false })
      .limit(20),
  ]);

  const failed = [
    predictionsResult.error,
    ecgResult.error,
    monitoringResult.error,
    alertsResult.error,
    notesResult.error,
  ].find(Boolean);

  if (failed) {
    console.error('Error loading patient detail:', failed);
    throw new Error('Could not load the patient timeline.');
  }

  const riskHistory = ((predictionsResult.data ?? []) as PredictionRow[]).map((row) => ({
    id: row.id,
    result: row.prediction_result,
    score: computeCardiacRiskScore(row.prediction_data),
    createdAt: row.created_at,
  }));

  const ecgHistory = ((ecgResult.data ?? []) as EcgRow[]).map((row) => ({
    id: row.id,
    fileName: row.file_name ?? null,
    prediction: row.prediction,
    confidence: row.confidence,
    signalPreview: Array.isArray(row.signal_preview) ? (row.signal_preview as number[]) : [],
    createdAt: row.created_at,
  }));

  const checkIns = ((monitoringResult.data ?? []) as MonitoringRow[]).map((row) => ({
    id: row.id,
    recordedAt: row.recorded_at,
    restingHeartRate: row.resting_heart_rate,
    breathlessness: row.breathlessness,
    fatigue: row.fatigue,
    stressLevel: row.stress_level ?? 0,
    activityMinutes: row.activity_minutes ?? 0,
    sleepHours: Number(row.sleep_hours ?? 0),
    note: row.note ?? '',
  }));

  return {
    ...overview,
    riskHistory,
    ecgHistory,
    checkIns,
    alerts: ((alertsResult.data ?? []) as AlertRow[]).map(toClinicalAlert),
    notes: ((notesResult.data ?? []) as DoctorNoteRow[]).map(toDoctorNote),
  };
};

export const acknowledgePatientAlert = async (alertId: string): Promise<void> => {
  const { error } = await supabase
    .from('alerts')
    .update({
      status: 'acknowledged',
      acknowledged_at: new Date().toISOString(),
    })
    .eq('id', alertId);

  if (error) {
    console.error('Error acknowledging alert:', error);
    throw new Error('Could not acknowledge this alert.');
  }
};

export const addDoctorNote = async ({
  doctorId,
  patientId,
  body,
  visibleToPatient,
}: {
  doctorId: string;
  patientId: string;
  body: string;
  visibleToPatient: boolean;
}): Promise<DoctorNote> => {
  const trimmedBody = body.trim();
  if (!trimmedBody) {
    throw new Error('Note body is required.');
  }

  const { data, error } = await supabase
    .from('doctor_notes')
    .insert({
      doctor_id: doctorId,
      patient_id: patientId,
      body: trimmedBody,
      visible_to_patient: visibleToPatient,
    })
    .select('id, doctor_id, patient_id, body, visible_to_patient, created_at, updated_at')
    .single();

  if (error || !data) {
    console.error('Error saving doctor note:', error);
    throw new Error(error?.message || 'Could not save the doctor note.');
  }

  return toDoctorNote(data as DoctorNoteRow);
};
