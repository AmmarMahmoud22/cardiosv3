import type { ECGAnalysisRecord, MonitoringCheckIn } from '../types';
import * as supabaseStore from './supabaseHealthStore';
import * as localStore from './localHealthStore';

// Health-store facade.
//
// Default: the real Supabase-backed store (RLS-protected per-user tables).
// The browser localStorage implementation (./localHealthStore) is kept as a
// separate OFFLINE/MOCK fallback and is DISABLED by default. Enable it only by
// setting `VITE_USE_LOCAL_HEALTH_STORE=true` (e.g. for offline demos without a
// Supabase connection). All functions are async so callers are agnostic to the
// active backend.
const useLocalStore = import.meta.env.VITE_USE_LOCAL_HEALTH_STORE === 'true';

export const getEcgHistory = (userId: string): Promise<ECGAnalysisRecord[]> =>
  useLocalStore ? Promise.resolve(localStore.getEcgHistory(userId)) : supabaseStore.getEcgHistory(userId);

export const addEcgAnalysis = (record: ECGAnalysisRecord): Promise<ECGAnalysisRecord> =>
  useLocalStore ? Promise.resolve(localStore.addEcgAnalysis(record)) : supabaseStore.addEcgAnalysis(record);

export const getMonitoringCheckIns = (userId: string): Promise<MonitoringCheckIn[]> =>
  useLocalStore
    ? Promise.resolve(localStore.getMonitoringCheckIns(userId))
    : supabaseStore.getMonitoringCheckIns(userId);

export const addMonitoringCheckIn = (checkIn: MonitoringCheckIn): Promise<MonitoringCheckIn> =>
  useLocalStore
    ? Promise.resolve(localStore.addMonitoringCheckIn(checkIn))
    : supabaseStore.addMonitoringCheckIn(checkIn);
