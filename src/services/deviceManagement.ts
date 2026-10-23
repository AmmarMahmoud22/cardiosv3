import { supabase } from '../lib/supabase';
import type {
  DeviceAssignmentStatus,
  DoctorPatientOption,
  ManagedDevice,
  SaveDeviceAssignmentInput,
} from '../types';

type DoctorPatientRow = {
  patient_id: string;
  status: string;
};

type ProfileRow = {
  id: string;
  email: string | null;
};

type ExtendedProfileRow = {
  id: string;
  full_name: string | null;
};

type DeviceRow = {
  id: string;
  device_id: string;
  display_name: string;
  patient_id: string | null;
  assigned_by: string | null;
  status: DeviceAssignmentStatus;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
};

export interface DeviceManagementData {
  patients: DoctorPatientOption[];
  devices: ManagedDevice[];
}

const isConnected = (lastSeenAt: string | null): boolean => {
  if (!lastSeenAt) return false;
  const ageMs = Date.now() - new Date(lastSeenAt).getTime();
  return ageMs >= 0 && ageMs <= 10 * 60 * 1000;
};

const normalizeDeviceId = (deviceId: string): string => deviceId.trim();

const toPatientOptions = (
  patientIds: string[],
  profiles: ProfileRow[],
  extendedProfiles: ExtendedProfileRow[]
): DoctorPatientOption[] => {
  const profileMap = new Map(profiles.map((profile) => [profile.id, profile]));
  const extendedMap = new Map(extendedProfiles.map((profile) => [profile.id, profile]));

  return patientIds.map((patientId) => {
    const profile = profileMap.get(patientId);
    const extended = extendedMap.get(patientId);
    return {
      patientId,
      patientName: extended?.full_name || profile?.email?.split('@')[0] || 'Unnamed patient',
      email: profile?.email ?? 'No email',
    };
  });
};

const toManagedDevice = (
  row: DeviceRow,
  patientMap: Map<string, DoctorPatientOption>
): ManagedDevice => ({
  id: row.id,
  deviceId: row.device_id,
  displayName: row.display_name,
  patientId: row.patient_id,
  patientName: row.patient_id ? patientMap.get(row.patient_id)?.patientName ?? null : null,
  assignedBy: row.assigned_by,
  status: row.status,
  lastSeenAt: row.last_seen_at,
  connected: isConnected(row.last_seen_at),
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export const getDeviceManagementData = async (
  doctorId: string
): Promise<DeviceManagementData> => {
  const { data: links, error: linksError } = await supabase
    .from('doctor_patients')
    .select('patient_id, status')
    .eq('doctor_id', doctorId)
    .neq('status', 'archived');

  if (linksError) {
    console.error('Error loading assigned patients for devices:', linksError);
    throw new Error('Could not load assigned patients.');
  }

  const patientIds = [
    ...new Set(((links ?? []) as DoctorPatientRow[]).map((link) => link.patient_id)),
  ];

  const [profilesResult, extendedResult, assignedDevicesResult, ownDevicesResult] = await Promise.all([
    patientIds.length
      ? supabase.from('profiles').select('id, email').in('id', patientIds)
      : Promise.resolve({ data: [], error: null }),
    patientIds.length
      ? supabase.from('extended_profiles').select('id, full_name').in('id', patientIds)
      : Promise.resolve({ data: [], error: null }),
    patientIds.length
      ? supabase
          .from('devices')
          .select('id, device_id, display_name, patient_id, assigned_by, status, last_seen_at, created_at, updated_at')
          .in('patient_id', patientIds)
          .order('updated_at', { ascending: false })
      : Promise.resolve({ data: [], error: null }),
    supabase
      .from('devices')
      .select('id, device_id, display_name, patient_id, assigned_by, status, last_seen_at, created_at, updated_at')
      .eq('assigned_by', doctorId)
      .order('updated_at', { ascending: false }),
  ]);

  const failed = [
    profilesResult.error,
    extendedResult.error,
    assignedDevicesResult.error,
    ownDevicesResult.error,
  ].find(Boolean);

  if (failed) {
    console.error('Error loading device management data:', failed);
    throw new Error('Could not load device assignments.');
  }

  const patients = toPatientOptions(
    patientIds,
    (profilesResult.data ?? []) as ProfileRow[],
    (extendedResult.data ?? []) as ExtendedProfileRow[]
  );
  const patientMap = new Map(patients.map((patient) => [patient.patientId, patient]));
  const devicesById = new Map<string, DeviceRow>();

  for (const row of [
    ...((assignedDevicesResult.data ?? []) as DeviceRow[]),
    ...((ownDevicesResult.data ?? []) as DeviceRow[]),
  ]) {
    devicesById.set(row.id, row);
  }

  const devices = [...devicesById.values()]
    .map((row) => toManagedDevice(row, patientMap))
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime());

  return { patients, devices };
};

export const saveDeviceAssignment = async (
  doctorId: string,
  input: SaveDeviceAssignmentInput
): Promise<ManagedDevice> => {
  const deviceId = normalizeDeviceId(input.deviceId);
  const displayName = input.displayName.trim() || deviceId;

  if (!deviceId) {
    throw new Error('Device ID is required.');
  }

  const payload = {
    device_id: deviceId,
    display_name: displayName,
    patient_id: input.patientId,
    assigned_by: doctorId,
    status: input.status,
    updated_at: new Date().toISOString(),
  };

  const query = input.id
    ? supabase.from('devices').update(payload).eq('id', input.id).select().single()
    : supabase
        .from('devices')
        .upsert(payload, { onConflict: 'device_id' })
        .select()
        .single();

  const { data, error } = await query;

  if (error || !data) {
    console.error('Error saving device assignment:', error);
    throw new Error(error?.message || 'Could not save device assignment.');
  }

  return toManagedDevice(data as DeviceRow, new Map());
};

export const retireDevice = async (deviceId: string): Promise<void> => {
  const { error } = await supabase
    .from('devices')
    .update({ status: 'retired', patient_id: null, updated_at: new Date().toISOString() })
    .eq('id', deviceId);

  if (error) {
    console.error('Error retiring device:', error);
    throw new Error(error.message);
  }
};
