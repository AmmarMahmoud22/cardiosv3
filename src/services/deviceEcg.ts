import { getApiBaseUrl, getAuthHeaders } from '../lib/api';
import { supabase } from '../lib/supabase';
import type { DeviceECGReading, DeviceECGSummary, UserRole } from '../types';

interface DeviceListResponse {
  devices: DeviceECGSummary[];
}

export const getAvailableDevices = async (): Promise<DeviceECGSummary[]> => {
  const response = await fetch(`${getApiBaseUrl()}/device-ecg/devices`, {
    headers: { Accept: 'application/json', ...(await getAuthHeaders()) },
  });
  if (!response.ok) {
    throw new Error('Could not fetch the connected ESP32 devices.');
  }
  const deviceList = (await response.json()) as DeviceListResponse;
  return deviceList.devices;
};

export const getAssignedPatientDevices = async (patientId: string): Promise<DeviceECGSummary[]> => {
  const { data, error } = await supabase
    .from('devices')
    .select('device_id, display_name, last_seen_at, status')
    .eq('patient_id', patientId)
    .eq('status', 'active')
    .order('updated_at', { ascending: false });

  if (error) {
    console.error('Error loading patient ECG devices:', error);
    throw new Error('Could not load your assigned ECG device.');
  }

  return (data ?? []).map((device) => {
    const lastSeenAt = typeof device.last_seen_at === 'string' ? device.last_seen_at : '';
    const ageMs = lastSeenAt ? Date.now() - new Date(lastSeenAt).getTime() : Number.POSITIVE_INFINITY;

    return {
      connected: ageMs >= 0 && ageMs <= 15_000,
      deviceId: String(device.device_id),
      displayName: String(device.display_name || device.device_id),
      receivedAt: lastSeenAt,
    };
  });
};

export const getVisibleDevicesForUser = async (
  userId: string | undefined,
  role: UserRole | null
): Promise<DeviceECGSummary[]> => {
  if (role === 'doctor' || role === 'admin') {
    return getAvailableDevices();
  }

  if (!userId) return [];
  return getAssignedPatientDevices(userId);
};

export const getLatestDeviceReading = async (deviceId: string): Promise<DeviceECGReading> => {
  const readingUrl = `${getApiBaseUrl()}/device-ecg/latest?deviceId=${encodeURIComponent(deviceId)}`;
  const response = await fetch(readingUrl, {
    headers: { Accept: 'application/json', ...(await getAuthHeaders()) },
  });
  if (!response.ok) {
    throw new Error('Could not fetch the latest ESP32 ECG batch.');
  }
  return response.json() as Promise<DeviceECGReading>;
};
