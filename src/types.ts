export interface FormData {
  BMI: number;
  Smoking: string;
  AlcoholDrinking: string;
  Stroke: string;
  PhysicalHealth: number;
  MentalHealth: number;
  DiffWalking: string;
  Sex: string;
  AgeCategory: string;
  Race: string;
  Diabetic: string;
  PhysicalActivity: string;
  GenHealth: string;
  SleepTime: number;
  Asthma: string;
  KidneyDisease: string;
  SkinCancer: string;
}

export interface PredictionRecord {
  id: string;
  user_id: string;
  prediction_data: FormData;
  prediction_result: string;
  created_at: string;
}

export interface ExtendedProfile {
  id: string;
  full_name: string | null;
  date_of_birth: string | null;
  gender: 'Male' | 'Female' | 'Other' | null;
  phone_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserStats {
  total_predictions: number;
  high_risk_predictions: number;
  low_risk_predictions: number;
  last_prediction_date: string | null;
}

export interface SystemStats {
  total_users: number;
  total_predictions: number;
  accuracy_rate: number;
  lives_impacted: number;
}

export interface RiskFactor {
  factor: string;
  status: string;
  risk: 'high' | 'medium' | 'low';
  impact: number;
  recommendation: string;
}

export interface PredictionTrendPoint {
  id: string;
  date: string;
  label: string;
  riskScore: number;
  riskBand: 'stable' | 'elevated' | 'high';
  predictionResult: string;
}

export interface MonitoringCheckIn {
  id: string;
  userId: string;
  recordedAt: string;
  restingHeartRate: number;
  breathlessness: number;
  fatigue: number;
  stressLevel: number;
  activityMinutes: number;
  sleepHours: number;
  note: string;
}

export interface ECGAnalysisRecord {
  id: string;
  userId: string;
  createdAt: string;
  fileName: string;
  prediction: string;
  confidence: number;
  signalPreview: number[];
}

export interface SignalQuality {
  leadOff: boolean;
  flatline: boolean;
  clipping: boolean;
  noisy: boolean;
  weakSignal: boolean;
  tooShort?: boolean;
  quality: 'good' | 'acceptable' | 'poor';
  qualityScore: number;
  usableForClassification: boolean;
  reasons: string[];
  metrics?: Record<string, number>;
}

export interface DeviceECGReading {
  connected: boolean;
  deviceId: string;
  receivedAt: string;
  prediction: string;
  // null when the signal quality is too poor for a confident classification
  confidence: number | null;
  ecgData: number[];
  sampleRateHz: number;
  heartRateBpm: number | null;
  leadOff: boolean;
  modelSampleCount: number;
  signalQuality?: SignalQuality;
  qualityOk?: boolean;
}

export interface DeviceECGSummary {
  connected: boolean;
  deviceId: string;
  receivedAt: string;
  displayName?: string;
}

export type UserRole = 'patient' | 'doctor' | 'admin';
export type CareTeamStatus = 'pending' | 'active' | 'archived';
export type DeviceAssignmentStatus = 'active' | 'inactive' | 'retired';
export type AlertSource =
  | 'ecg'
  | 'risk_prediction'
  | 'monitoring_checkin'
  | 'device_offline'
  | 'poor_signal';
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'unread' | 'acknowledged' | 'resolved' | 'dismissed';

export interface DoctorPatientLink {
  id: string;
  doctorId: string;
  patientId: string;
  status: CareTeamStatus;
  createdAt: string;
  updatedAt: string;
}

export interface PatientDevice {
  id: string;
  deviceId: string;
  displayName: string;
  patientId: string | null;
  assignedBy: string | null;
  status: DeviceAssignmentStatus;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ClinicalAlert {
  id: string;
  patientId: string;
  doctorId: string | null;
  source: AlertSource;
  severity: AlertSeverity;
  title: string;
  message: string;
  reasonCodes: string[];
  status: AlertStatus;
  relatedDeviceId: string | null;
  relatedRecordId: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  acknowledgedAt: string | null;
}

export interface DoctorNote {
  id: string;
  doctorId: string;
  patientId: string;
  body: string;
  visibleToPatient: boolean;
  createdAt: string;
  updatedAt: string;
}

export type PatientReviewStatus = 'stable' | 'needs_review' | 'urgent';

export interface DoctorPatientOverview {
  patientId: string;
  patientName: string;
  email: string;
  relationshipStatus: CareTeamStatus;
  assignedAt: string;
  reviewStatus: PatientReviewStatus;
  latestRisk: {
    id: string;
    result: string;
    score: number;
    createdAt: string;
  } | null;
  latestEcg: {
    id: string;
    prediction: string;
    confidence: number;
    createdAt: string;
  } | null;
  latestCheckIn: {
    id: string;
    recordedAt: string;
    restingHeartRate: number;
    breathlessness: number;
    fatigue: number;
  } | null;
  assignedDevice: {
    id: string;
    deviceId: string;
    displayName: string;
    status: DeviceAssignmentStatus;
    lastSeenAt: string | null;
    connected: boolean;
  } | null;
  unreadAlerts: number;
  highestAlertSeverity: AlertSeverity | null;
  aiSummary: string;
}

export interface DoctorPatientDetail extends DoctorPatientOverview {
  riskHistory: Array<{
    id: string;
    result: string;
    score: number;
    createdAt: string;
  }>;
  ecgHistory: Array<{
    id: string;
    fileName: string | null;
    prediction: string;
    confidence: number;
    signalPreview: number[];
    createdAt: string;
  }>;
  checkIns: Array<{
    id: string;
    recordedAt: string;
    restingHeartRate: number;
    breathlessness: number;
    fatigue: number;
    stressLevel: number;
    activityMinutes: number;
    sleepHours: number;
    note: string;
  }>;
  alerts: ClinicalAlert[];
  notes: DoctorNote[];
}

export interface DoctorPatientOption {
  patientId: string;
  patientName: string;
  email: string;
}

export interface ManagedDevice {
  id: string;
  deviceId: string;
  displayName: string;
  patientId: string | null;
  patientName: string | null;
  assignedBy: string | null;
  status: DeviceAssignmentStatus;
  lastSeenAt: string | null;
  connected: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SaveDeviceAssignmentInput {
  id?: string;
  deviceId: string;
  displayName: string;
  patientId: string | null;
  status: DeviceAssignmentStatus;
}

export const AGE_CATEGORIES = [
  '18-24',
  '25-29',
  '30-34',
  '35-39',
  '40-44',
  '45-49',
  '50-54',
  '55-59',
  '60-64',
  '65-69',
  '70-74',
  '75-79',
  '80 or older',
];

export const RACE_CATEGORIES = [
  'White',
  'Black',
  'Asian',
  'American Indian/Alaskan Native',
  'Other',
  'Hispanic',
];

export const DIABETIC_OPTIONS = [
  'No',
  'Yes',
  'No, borderline diabetes',
  'Yes (during pregnancy)',
];

export const GEN_HEALTH_OPTIONS = [
  'Very good',
  'Fair',
  'Good',
  'Poor',
  'Excellent',
];
