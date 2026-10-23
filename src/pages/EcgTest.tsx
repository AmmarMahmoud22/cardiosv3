import React, { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'react-hot-toast';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ArrowLeft, CheckCircle2, HeartPulse, Play, Radio, Square, Wifi } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { addEcgAnalysis } from '../services/healthStore';
import type { DeviceECGReading, DeviceECGSummary } from '../types';
import { isAbnormalLabel } from '../utils/ecg';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import MedicalDisclaimer from '../components/ui/MedicalDisclaimer';
import EcgWaveform from '../components/ecg/EcgWaveform';
import { getLatestDeviceReading, getVisibleDevicesForUser } from '../services/deviceEcg';
import { sendPatientReportToDoctor } from '../services/patientReports';

// Recording window for one live ECG test. One minute, as requested.
const TEST_DURATION_SECONDS = 60;
// How often we pull the latest device batch while recording.
const POLL_INTERVAL_MS = 2500;
const LIVE_PACKET_MAX_AGE_MS = 15000;

type TestStatus = 'idle' | 'recording' | 'done';

interface TestSummary {
  batches: number;
  goodBatches: number;
  avgHeartRate: number | null;
  // Mean of the per-batch model confidences (0 when none were usable). Stored on
  // the saved record so history's "% confidence" label stays truthful.
  avgConfidence: number;
  dominantPrediction: string;
  abnormal: boolean;
  qualitySharePercent: number;
  predictionCounts: Record<string, number>;
}

const mean = (values: number[]): number =>
  values.reduce((sum, n) => sum + n, 0) / values.length;

// Readings carry heartRateBpm / confidence as `number | null`; keep only the
// batches that actually reported a value.
const reportedNumbers = (values: Array<number | null>): number[] =>
  values.filter((v): v is number => typeof v === 'number');

const isLiveReading = (reading: DeviceECGReading | null, deviceId: string): boolean => {
  if (!reading || reading.deviceId !== deviceId) return false;
  const packetAge = Date.now() - new Date(reading.receivedAt).getTime();
  return packetAge >= 0 && packetAge <= LIVE_PACKET_MAX_AGE_MS;
};

const tallyPredictions = (readings: DeviceECGReading[]): Record<string, number> => {
  const counts: Record<string, number> = {};
  for (const reading of readings) {
    counts[reading.prediction] = (counts[reading.prediction] || 0) + 1;
  }
  return counts;
};

const summariseReadings = (readings: DeviceECGReading[]): TestSummary => {
  const good = readings.filter((r) => r.qualityOk);
  const heartRates = reportedNumbers(readings.map((r) => r.heartRateBpm));
  const confidences = reportedNumbers(readings.map((r) => r.confidence));
  // Classifications are tallied over usable batches only.
  const predictionCounts = tallyPredictions(good);
  const dominantPrediction =
    Object.entries(predictionCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ??
    (readings.length ? 'Inconclusive (poor signal quality)' : 'No data captured');

  return {
    batches: readings.length,
    goodBatches: good.length,
    avgHeartRate: heartRates.length ? Math.round(mean(heartRates)) : null,
    avgConfidence: confidences.length ? Math.round(mean(confidences) * 10) / 10 : 0,
    dominantPrediction,
    abnormal: good.some((r) => isAbnormalLabel(r.prediction)),
    qualitySharePercent: readings.length ? Math.round((good.length / readings.length) * 100) : 0,
    predictionCounts,
  };
};

// Persist one history record summarising the whole test run.
const persistTestSummary = async (
  userId: string,
  summary: TestSummary,
  readings: DeviceECGReading[]
): Promise<void> => {
  const preview =
    readings.find((r) => r.qualityOk)?.ecgData ??
    readings[readings.length - 1]?.ecgData ??
    [];
  await addEcgAnalysis({
    id: crypto.randomUUID(),
    userId,
    createdAt: new Date().toISOString(),
    fileName: `live-test-${TEST_DURATION_SECONDS}s`,
    prediction: summary.dominantPrediction,
    confidence: summary.avgConfidence,
    signalPreview: preview.slice(0, 300),
  });
};

const EcgTest: React.FC = () => {
  const { user, role } = useAuthStore();
  const [status, setStatus] = useState<TestStatus>('idle');
  const [secondsLeft, setSecondsLeft] = useState(TEST_DURATION_SECONDS);
  const [devices, setDevices] = useState<DeviceECGSummary[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const [latest, setLatest] = useState<DeviceECGReading | null>(null);
  const [capturedBatches, setCapturedBatches] = useState(0);
  const [summary, setSummary] = useState<TestSummary | null>(null);
  const [sendingReport, setSendingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const readingsRef = useRef<DeviceECGReading[]>([]);
  const lastTimestampRef = useRef<string | null>(null);

  const finishTest = useCallback(async () => {
    setStatus('done');
    const testSummary = summariseReadings(readingsRef.current);
    setSummary(testSummary);

    if (testSummary.batches === 0) {
      toast.error('No device data was received. Is the ESP32 sending and on the same Wi-Fi?');
      return;
    }

    if (!user?.id) return;
    try {
      await persistTestSummary(user.id, testSummary, readingsRef.current);
      toast.success('ECG test saved to your history.');
    } catch (saveError) {
      console.error('Saving ECG test failed:', saveError);
    }
  }, [user?.id]);

  const refreshDevices = useCallback(async () => {
    try {
      const availableDevices = await getVisibleDevicesForUser(user?.id, role);
      setDevices(availableDevices);
      setSelectedDeviceId((currentDeviceId) =>
        availableDevices.some(({ deviceId }) => deviceId === currentDeviceId)
          ? currentDeviceId
          : availableDevices[0]?.deviceId || ''
      );
      setError(null);
    } catch (deviceError) {
      setError(deviceError instanceof Error ? deviceError.message : 'Device discovery failed.');
    }
  }, [role, user?.id]);

  const pollOnce = useCallback(async () => {
    if (!selectedDeviceId) return;
    try {
      const deviceReading = await getLatestDeviceReading(selectedDeviceId);
      setLatest(deviceReading);
      setError(null);
      // Dedupe by receivedAt so we only count each batch once.
      if (status === 'recording' && deviceReading.receivedAt !== lastTimestampRef.current) {
        lastTimestampRef.current = deviceReading.receivedAt;
        readingsRef.current = [...readingsRef.current, deviceReading];
        setCapturedBatches(readingsRef.current.length);
      }
    } catch (pollError) {
      setError(pollError instanceof Error ? pollError.message : 'Device polling failed.');
    }
  }, [selectedDeviceId, status]);

  const startTest = useCallback(() => {
    if (!user?.id) {
      toast.error('Please sign in before running an ECG test.');
      return;
    }
    if (!isLiveReading(latest, selectedDeviceId)) {
      toast.error('Choose an online ESP32 and wait for a fresh ECG packet before starting.');
      return;
    }
    if (latest?.leadOff) {
      toast.error('Re-seat the electrodes and wait for the lead-off warning to clear.');
      return;
    }
    readingsRef.current = [];
    lastTimestampRef.current = latest?.receivedAt ?? null;
    setCapturedBatches(0);
    setSummary(null);
    setError(null);
    setSecondsLeft(TEST_DURATION_SECONDS);
    setStatus('recording');
  }, [latest, selectedDeviceId, user?.id]);

  const stopTest = useCallback(() => {
    void finishTest();
  }, [finishTest]);

  const sendGuidedTestReportToDoctor = async () => {
    if (!user?.id || !summary) return;
    setSendingReport(true);

    try {
      await sendPatientReportToDoctor({
        patientId: user.id,
        source: 'ecg',
        severity: summary.abnormal ? 'high' : summary.qualitySharePercent === 0 ? 'medium' : 'low',
        title: `Guided ECG test report: ${summary.dominantPrediction}`,
        message: `Patient sent a guided ${TEST_DURATION_SECONDS}s ECG test report. Dominant rhythm: ${summary.dominantPrediction}. Batches: ${summary.batches}. Usable quality: ${summary.qualitySharePercent}%. Average heart rate: ${summary.avgHeartRate ?? 'not reported'}.`,
        reasonCodes: [
          'patient_sent_report',
          'guided_ecg_test',
          summary.abnormal ? 'abnormal_ecg' : 'routine_ecg',
        ],
        relatedDeviceId: selectedDeviceId || null,
        metadata: {
          reportType: 'guided_ecg_test',
          durationSeconds: TEST_DURATION_SECONDS,
          batches: summary.batches,
          goodBatches: summary.goodBatches,
          qualitySharePercent: summary.qualitySharePercent,
          avgHeartRate: summary.avgHeartRate,
          dominantPrediction: summary.dominantPrediction,
        },
      });
      toast.success('ECG test report sent to your doctor.');
    } catch (sendError) {
      toast.error(sendError instanceof Error ? sendError.message : 'Could not send ECG report to doctor.');
    } finally {
      setSendingReport(false);
    }
  };

  useEffect(() => {
    void refreshDevices();
    const refreshInterval = window.setInterval(() => void refreshDevices(), 5000);
    return () => window.clearInterval(refreshInterval);
  }, [refreshDevices]);

  useEffect(() => {
    if (status === 'recording' || !selectedDeviceId) return;
    void pollOnce();
    const previewInterval = window.setInterval(() => void pollOnce(), POLL_INTERVAL_MS);
    return () => window.clearInterval(previewInterval);
  }, [pollOnce, selectedDeviceId, status]);

  useEffect(() => {
    if (status !== 'recording') return;
    void pollOnce();
    const pollInterval = window.setInterval(() => void pollOnce(), POLL_INTERVAL_MS);
    const countdownInterval = window.setInterval(() => {
      setSecondsLeft((remainingSeconds) => {
        if (remainingSeconds <= 1) {
          void finishTest();
          return 0;
        }
        return remainingSeconds - 1;
      });
    }, 1000);
    return () => {
      window.clearInterval(pollInterval);
      window.clearInterval(countdownInterval);
    };
  }, [finishTest, pollOnce, status]);

  const progressPercent = Math.round(
    ((TEST_DURATION_SECONDS - secondsLeft) / TEST_DURATION_SECONDS) * 100
  );
  const mmss = `${String(Math.floor(secondsLeft / 60)).padStart(2, '0')}:${String(
    secondsLeft % 60
  ).padStart(2, '0')}`;
  const deviceLive = isLiveReading(latest, selectedDeviceId);
  const testReady = deviceLive && latest?.leadOff === false;

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      <Link
        to="/predict-ecg"
        className="inline-flex min-h-11 items-center gap-2 rounded-full px-3 text-sm font-semibold text-emerald-800 transition-colors hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-300"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to ECG Lab
      </Link>
      <header className="rounded-[32px] bg-gradient-to-br from-[#08251a] via-[#0c5a3e] to-[#16a66a] p-6 text-white shadow-[0_24px_60px_rgba(6,52,37,0.2)] sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-200">Guided ECG test</p>
            <h1 className="mt-3 font-sora text-3xl font-semibold sm:text-4xl">One minute. One clear screening summary.</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-emerald-50/80 sm:text-base">
              Cardios captures fresh ESP32 batches, checks signal quality, and summarises heart rate
              and beat classifications without presenting the result as a diagnosis.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm">
            <span className={`h-2.5 w-2.5 rounded-full ${testReady ? 'bg-emerald-300' : 'bg-amber-300'}`} />
            {testReady ? 'Ready to record' : deviceLive ? 'Check electrodes' : 'Waiting for device'}
          </div>
        </div>
      </header>

      <Card className="space-y-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">Pre-test check</p>
          <h2 className="mt-2 font-sora text-xl font-semibold text-slate-950">Make the signal trustworthy before recording</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <label className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm font-medium text-slate-700">
            {role === 'doctor' || role === 'admin' ? 'ESP32 device' : 'Your assigned ECG device'}
            <select
              value={selectedDeviceId}
              disabled={status === 'recording' || (role !== 'doctor' && role !== 'admin' && devices.length <= 1)}
              onChange={(event) => {
                setSelectedDeviceId(event.target.value);
                setLatest(null);
              }}
              className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {!devices.length ? <option value="">No devices found</option> : null}
              {devices.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.displayName ?? device.deviceId} - {device.connected ? 'online' : 'offline'}
                </option>
              ))}
            </select>
            {!devices.length ? (
              <p className="mt-3 text-xs leading-5 text-amber-700">
                {role === 'doctor' || role === 'admin'
                  ? 'No ESP32 devices are currently visible to the backend.'
                  : 'No ECG device is assigned to your patient profile yet.'}
              </p>
            ) : null}
          </label>
          <ReadinessItem
            icon={<Wifi className="h-5 w-5" />}
            title="Fresh connection"
            detail={deviceLive ? 'A packet arrived within 15 seconds.' : 'Power the ESP32 and wait for a fresh packet.'}
            ready={deviceLive}
          />
          <ReadinessItem
            icon={<HeartPulse className="h-5 w-5" />}
            title="Electrode contact"
            detail={latest?.leadOff ? 'Lead-off detected. Re-seat the electrodes.' : 'No lead-off detected in the latest packet.'}
            ready={deviceLive && latest?.leadOff === false}
          />
        </div>
      </Card>

      {/* --- Control + countdown --- */}
      <Card className="space-y-5">
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50">
              <HeartPulse className="h-8 w-8 text-emerald-600" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Test duration</p>
              <p className="text-4xl font-bold tabular-nums text-slate-900">{mmss}</p>
            </div>
          </div>

          {status === 'recording' ? (
            <Button variant="secondary" onClick={stopTest}>
              <Square className="h-4 w-4" /> Stop early
            </Button>
          ) : (
            <Button onClick={startTest} disabled={!testReady}>
              <Play className="h-4 w-4" /> {status === 'done' ? 'Run again' : 'Start test'}
            </Button>
          )}
        </div>

        <div
          role="progressbar"
          aria-label="ECG test progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={status === 'idle' ? 0 : progressPercent}
          className="h-2 w-full overflow-hidden rounded-full bg-slate-100"
        >
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-500"
            style={{ width: `${status === 'idle' ? 0 : progressPercent}%` }}
          />
        </div>

        {status === 'recording' && (
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Batches" value={`${capturedBatches}`} />
            <Stat
              label="Heart rate"
              value={latest?.heartRateBpm ? `${latest.heartRateBpm} bpm` : '—'}
            />
            <Stat
              label="Signal"
              value={latest?.leadOff ? 'Lead-off' : latest?.qualityOk ? 'Good' : 'Poor'}
              tone={latest?.leadOff || latest?.qualityOk === false ? 'warn' : 'ok'}
            />
          </div>
        )}
      </Card>

      {(latest || status === 'recording') && (
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 text-slate-700">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-emerald-600" />
              <h2 className="font-semibold">Latest 3-second ECG capture</h2>
            </div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-700">
              <Radio className="h-4 w-4" />
              {status === 'recording' ? 'Recording' : 'Live preview'}
            </div>
          </div>
          {latest?.leadOff && (
            <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" />
              Electrode lead-off detected. Press the pads firmly to bare, clean skin for a usable
              reading.
            </div>
          )}
          <EcgWaveform
            samples={latest?.ecgData || []}
            sampleRateHz={latest?.sampleRateHz || 250}
            ariaLabel={`Latest ECG waveform from ${selectedDeviceId || 'the selected device'}`}
          />
        </Card>
      )}

      {/* --- Summary when done --- */}
      {status === 'done' && summary && summary.batches > 0 && (
        <Card className="space-y-5">
          <div className="flex items-center gap-2 text-slate-700">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <h2 className="font-semibold">Test summary</h2>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Batches captured" value={`${summary.batches}`} />
            <Stat
              label="Avg heart rate"
              value={summary.avgHeartRate ? `${summary.avgHeartRate} bpm` : '—'}
            />
            <Stat label="Usable quality" value={`${summary.qualitySharePercent}%`} />
            <Stat
              label="Dominant rhythm"
              value={summary.dominantPrediction.replace(/ \(.*\)$/, '')}
            />
          </div>

          <Button type="button" variant="secondary" onClick={sendGuidedTestReportToDoctor} disabled={sendingReport}>
            {sendingReport ? 'Sending...' : 'Send test report to doctor'}
            <HeartPulse className="h-4 w-4" />
          </Button>

          {summary.abnormal ? (
            <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
              <p>
                <span className="font-semibold">Clinician review suggested. </span>
                One or more beats were classified as abnormal (ectopic) during this test. This is a
                screening signal only — please share this with a qualified clinician and confirm
                with a clinical 12-lead ECG.
              </p>
            </div>
          ) : summary.qualitySharePercent === 0 ? (
            <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
              <p>
                <span className="font-semibold">Signal too poor to classify. </span>
                Every batch was flagged for poor signal quality (often lead-off or noise). Re-seat
                the electrodes and run the test again.
              </p>
            </div>
          ) : (
            <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
              <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" />
              <p>
                No abnormal beats were flagged in the usable portion of this test. This does not
                rule out heart disease — single-lead screening cannot detect ischemia or structural
                problems.
              </p>
            </div>
          )}

          {/* per-class breakdown */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-600">Classification breakdown (usable batches)</p>
            {Object.entries(summary.predictionCounts).length === 0 ? (
              <p className="text-sm text-slate-500">No usable batches to classify.</p>
            ) : (
              Object.entries(summary.predictionCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([label, count]) => (
                  <div key={label} className="flex items-center justify-between text-sm">
                    <span className={isAbnormalLabel(label) ? 'text-red-700' : 'text-slate-700'}>
                      {label}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-900">{count}</span>
                  </div>
                ))
            )}
          </div>

          <MedicalDisclaimer />
        </Card>
      )}

      {error && status !== 'recording' && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {status === 'idle' && (
        <p className="text-sm text-slate-500">
          Connect the ESP32, place the electrodes, then press <strong>Start test</strong>. No
          hardware? Run <code>scripts/simulate_device.py</code> and the test will record from the
          simulator exactly as from a real device.
        </p>
      )}
    </div>
  );
};

interface StatProps {
  label: string;
  value: string;
  tone?: 'ok' | 'warn';
}

const Stat: React.FC<StatProps> = ({ label, value, tone }) => (
  <div className="rounded-2xl border border-slate-100 bg-white p-3 text-center">
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p
      className={`mt-1 text-lg font-semibold ${
        tone === 'warn' ? 'text-amber-600' : tone === 'ok' ? 'text-emerald-600' : 'text-slate-900'
      }`}
    >
      {value}
    </p>
  </div>
);

interface ReadinessItemProps {
  icon: React.ReactNode;
  title: string;
  detail: string;
  ready: boolean;
}

const ReadinessItem: React.FC<ReadinessItemProps> = ({ icon, title, detail, ready }) => (
  <div
    className={`rounded-2xl border p-4 text-sm transition-colors ${
      ready ? 'border-emerald-200 bg-emerald-50 text-slate-700' : 'border-amber-200 bg-amber-50 text-slate-700'
    }`}
  >
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 rounded-xl p-2 ${ready ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-slate-900">{title}</p>
        <p className="mt-1 leading-6">{detail}</p>
      </div>
    </div>
  </div>
);

export default EcgTest;
