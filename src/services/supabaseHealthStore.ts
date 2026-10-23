import { supabase } from '../lib/supabase';
import type { ECGAnalysisRecord, MonitoringCheckIn } from '../types';

// Real Supabase-backed implementation of the health store. Persists ECG
// analyses and monitoring check-ins in RLS-protected tables (ecg_analyses,
// monitoring_checkins) so each user only ever reads/writes their own rows.
// This is the default implementation (see ./healthStore).

// ---------- ECG analyses ----------
interface EcgRow {
  id: string;
  user_id: string;
  created_at: string;
  file_name: string | null;
  prediction: string;
  confidence: number;
  signal_preview: number[] | null;
}

const toEcgRecord = (row: EcgRow): ECGAnalysisRecord => ({
  id: row.id,
  userId: row.user_id,
  createdAt: row.created_at,
  fileName: row.file_name ?? '',
  prediction: row.prediction,
  confidence: row.confidence,
  signalPreview: row.signal_preview ?? [],
});

export const getEcgHistory = async (userId: string): Promise<ECGAnalysisRecord[]> => {
  const { data, error } = await supabase
    .from('ecg_analyses')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(50);

  if (error) {
    console.error('Error loading ECG history:', error);
    return [];
  }

  return ((data ?? []) as EcgRow[]).map(toEcgRecord);
};

export const addEcgAnalysis = async (record: ECGAnalysisRecord): Promise<ECGAnalysisRecord> => {
  const { data, error } = await supabase
    .from('ecg_analyses')
    .insert({
      user_id: record.userId,
      file_name: record.fileName,
      prediction: record.prediction,
      confidence: record.confidence,
      signal_preview: record.signalPreview,
      created_at: record.createdAt,
    })
    .select()
    .single();

  if (error || !data) {
    console.error('Error saving ECG analysis:', error);
    return record;
  }

  return toEcgRecord(data as EcgRow);
};

// ---------- Monitoring check-ins ----------
interface MonitoringRow {
  id: string;
  user_id: string;
  recorded_at: string;
  resting_heart_rate: number;
  breathlessness: number;
  fatigue: number;
  stress_level: number;
  activity_minutes: number;
  sleep_hours: number;
  note: string | null;
}

const toCheckIn = (row: MonitoringRow): MonitoringCheckIn => ({
  id: row.id,
  userId: row.user_id,
  recordedAt: row.recorded_at,
  restingHeartRate: row.resting_heart_rate,
  breathlessness: row.breathlessness,
  fatigue: row.fatigue,
  stressLevel: row.stress_level,
  activityMinutes: row.activity_minutes,
  sleepHours: row.sleep_hours,
  note: row.note ?? '',
});

export const getMonitoringCheckIns = async (userId: string): Promise<MonitoringCheckIn[]> => {
  const { data, error } = await supabase
    .from('monitoring_checkins')
    .select('*')
    .eq('user_id', userId)
    .order('recorded_at', { ascending: false })
    .limit(100);

  if (error) {
    console.error('Error loading monitoring check-ins:', error);
    return [];
  }

  return ((data ?? []) as MonitoringRow[]).map(toCheckIn);
};

export const addMonitoringCheckIn = async (checkIn: MonitoringCheckIn): Promise<MonitoringCheckIn> => {
  const { data, error } = await supabase
    .from('monitoring_checkins')
    .insert({
      user_id: checkIn.userId,
      recorded_at: checkIn.recordedAt,
      resting_heart_rate: checkIn.restingHeartRate,
      breathlessness: checkIn.breathlessness,
      fatigue: checkIn.fatigue,
      stress_level: checkIn.stressLevel,
      activity_minutes: checkIn.activityMinutes,
      sleep_hours: checkIn.sleepHours,
      note: checkIn.note,
    })
    .select()
    .single();

  if (error || !data) {
    console.error('Error saving monitoring check-in:', error);
    return checkIn;
  }

  return toCheckIn(data as MonitoringRow);
};
