import type { ECGAnalysisRecord, MonitoringCheckIn } from '../types';

const checkInKey = 'cardios-monitoring-checkins';
const ecgHistoryKey = 'cardios-ecg-history';

const canUseStorage = () => typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';

const readFromStorage = <T>(key: string): T[] => {
  if (!canUseStorage()) {
    return [];
  }

  const rawValue = window.localStorage.getItem(key);
  if (!rawValue) {
    return [];
  }

  try {
    const parsed = JSON.parse(rawValue) as T[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const writeToStorage = <T>(key: string, value: T[]) => {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.setItem(key, JSON.stringify(value));
};

export const getMonitoringCheckIns = (userId: string) =>
  readFromStorage<MonitoringCheckIn>(checkInKey)
    .filter((item) => item.userId === userId)
    .sort((left, right) => new Date(right.recordedAt).getTime() - new Date(left.recordedAt).getTime());

export const addMonitoringCheckIn = (checkIn: MonitoringCheckIn) => {
  const allCheckIns = readFromStorage<MonitoringCheckIn>(checkInKey);
  const nextValue = [checkIn, ...allCheckIns].slice(0, 100);
  writeToStorage(checkInKey, nextValue);
  return checkIn;
};

export const getEcgHistory = (userId: string) =>
  readFromStorage<ECGAnalysisRecord>(ecgHistoryKey)
    .filter((item) => item.userId === userId)
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime());

export const addEcgAnalysis = (record: ECGAnalysisRecord) => {
  const allRecords = readFromStorage<ECGAnalysisRecord>(ecgHistoryKey);
  const nextValue = [record, ...allRecords].slice(0, 50);
  writeToStorage(ecgHistoryKey, nextValue);
  return record;
};
