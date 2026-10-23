import { supabase } from '../lib/supabase';
import type { AlertSeverity, AlertSource } from '../types';

interface SendPatientReportInput {
  patientId: string;
  source: AlertSource;
  severity: AlertSeverity;
  title: string;
  message: string;
  reasonCodes: string[];
  relatedDeviceId?: string | null;
  relatedRecordId?: string | null;
  metadata?: Record<string, unknown>;
}

const latestAssignedDoctorId = async (patientId: string): Promise<string | null> => {
  const { data, error } = await supabase
    .from('doctor_patients')
    .select('doctor_id')
    .eq('patient_id', patientId)
    .eq('status', 'active')
    .order('updated_at', { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) {
    console.error('Error loading assigned doctor:', error);
    throw new Error('Could not find the assigned doctor for this patient.');
  }

  return typeof data?.doctor_id === 'string' ? data.doctor_id : null;
};

export const sendPatientReportToDoctor = async ({
  patientId,
  source,
  severity,
  title,
  message,
  reasonCodes,
  relatedDeviceId = null,
  relatedRecordId = null,
  metadata = {},
}: SendPatientReportInput): Promise<void> => {
  const doctorId = await latestAssignedDoctorId(patientId);

  if (!doctorId) {
    throw new Error('No active doctor is assigned to this patient yet.');
  }

  const { error } = await supabase.from('alerts').insert({
    patient_id: patientId,
    doctor_id: doctorId,
    source,
    severity,
    title,
    message,
    reason_codes: reasonCodes,
    related_device_id: relatedDeviceId,
    related_record_id: relatedRecordId,
    metadata,
    status: 'unread',
  });

  if (error) {
    console.error('Error sending report to doctor:', error);
    throw new Error('Could not send this report to the assigned doctor.');
  }
};
