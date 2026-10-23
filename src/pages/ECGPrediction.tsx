import React, { useEffect, useMemo, useState } from 'react';
import { toast } from 'react-hot-toast';
import { Activity, AlertTriangle, CheckCircle2, HeartPulse, Info, Upload, Waves } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { addEcgAnalysis, getEcgHistory } from '../services/healthStore';
import type { ECGAnalysisRecord, SignalQuality } from '../types';
import { getApiBaseUrl, getAuthHeaders } from '../lib/api';
import { isAbnormalLabel } from '../utils/ecg';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import MedicalDisclaimer from '../components/ui/MedicalDisclaimer';
import EcgWaveform from '../components/ecg/EcgWaveform';
import { sendPatientReportToDoctor } from '../services/patientReports';

interface ECGPredictionResponse {
  prediction: string;
  confidence: number | null;
  ecgData: number[];
  heartRateBpm?: number | null;
  sampleRateHz?: number;
  signalQuality?: SignalQuality;
  qualityOk?: boolean;
}

const formatConfidence = (value: number | null | undefined): string =>
  typeof value === 'number' ? `${value.toFixed(1)}%` : 'Not reported';

interface ErrorResponse {
  error: string;
}

const ECGPrediction: React.FC = () => {
  const { user } = useAuthStore();
  const [file, setFile] = useState<File | null>(null);
  const [prediction, setPrediction] = useState('');
  const [confidence, setConfidence] = useState<number | null>(null);
  const [uploadQuality, setUploadQuality] = useState<SignalQuality | null>(null);
  const [ecgData, setEcgData] = useState<number[]>([]);
  const [uploadSampleRateHz, setUploadSampleRateHz] = useState(180);
  const [isLoading, setIsLoading] = useState(false);
  const [serverStatus, setServerStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [errorDetails, setErrorDetails] = useState<string | null>(null);
  const [history, setHistory] = useState<ECGAnalysisRecord[]>([]);
  const [sendingUploadReport, setSendingUploadReport] = useState(false);

  useEffect(() => {
    if (!user?.id) return;
    let active = true;
    void getEcgHistory(user.id).then((rows) => {
      if (active) setHistory(rows);
    });
    return () => {
      active = false;
    };
  }, [user?.id]);

  useEffect(() => {
    const checkServerStatus = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/health`, {
          method: 'GET',
          headers: { Accept: 'application/json' },
        });

        if (!response.ok) {
          throw new Error('Cardios ECG service is unavailable.');
        }

        setServerStatus('online');
      } catch (statusError) {
        console.error('Server connection error:', statusError);
        setServerStatus('offline');
      }
    };

    void checkServerStatus();
    const interval = window.setInterval(checkServerStatus, 15000);
    return () => window.clearInterval(interval);
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setErrorDetails(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!file) {
      toast.error('Choose a CSV trace before starting the ECG analysis.');
      return;
    }

    if (!user?.id) {
      toast.error('Please sign in to store ECG comparisons in Cardios.');
      return;
    }

    setIsLoading(true);
    setErrorDetails(null);

    const payload = new FormData();
    payload.append('file', file);

    try {
      const response = await fetch(`${getApiBaseUrl()}/predict-ecg`, {
        method: 'POST',
        headers: { ...(await getAuthHeaders()) },
        body: payload,
      });

      const rawText = await response.text();

      if (!response.ok) {
        try {
          const parsedError = JSON.parse(rawText) as ErrorResponse;
          throw new Error(parsedError.error || 'Cardios ECG analysis failed.');
        } catch {
          throw new Error(rawText || 'Cardios ECG analysis failed.');
        }
      }

      const data = JSON.parse(rawText) as ECGPredictionResponse;

      setPrediction(data.prediction);
      setConfidence(data.confidence);
      setUploadQuality(data.signalQuality ?? null);
      setEcgData(data.ecgData);
      setUploadSampleRateHz(data.sampleRateHz ?? 180);

      await addEcgAnalysis({
        id: crypto.randomUUID(),
        userId: user.id,
        createdAt: new Date().toISOString(),
        fileName: file.name,
        prediction: data.prediction,
        confidence: data.confidence ?? 0,
        signalPreview: data.ecgData.slice(0, 300),
      });

      setHistory(await getEcgHistory(user.id));
      toast.success('ECG analysis complete. Comparison history updated.');
    } catch (submitError) {
      console.error('ECG prediction error:', submitError);
      const message =
        submitError instanceof Error
          ? submitError.message
          : 'Cardios could not complete the ECG analysis.';
      setErrorDetails(message);
      toast.error('ECG analysis failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const previousUploadRecord = useMemo(() => {
    if (!history.length || !prediction) {
      return history[0];
    }

    return history.find(
      (item) => item.fileName !== file?.name || item.createdAt !== history[0]?.createdAt
    );
  }, [file?.name, history, prediction]);

  const uploadConfidenceDelta =
    previousUploadRecord && prediction && confidence !== null
      ? Number((confidence - previousUploadRecord.confidence).toFixed(1))
      : null;

  const uploadSummary = prediction
    ? buildComparisonSummary(prediction, previousUploadRecord, uploadConfidenceDelta)
    : 'Run an ECG upload analysis to compare this trace with prior saved Cardios ECG results.';

  const sendEcgReportToDoctor = async ({
    predictionLabel,
    confidenceLabel,
    setSending,
  }: {
    predictionLabel: string;
    confidenceLabel: string;
    setSending: React.Dispatch<React.SetStateAction<boolean>>;
  }) => {
    if (!user?.id) return;
    setSending(true);

    try {
      await sendPatientReportToDoctor({
        patientId: user.id,
        source: 'ecg',
        severity: isAbnormalLabel(predictionLabel) ? 'high' : 'medium',
        title: `Patient ECG report: ${predictionLabel}`,
        message: `Patient sent an ECG report from CSV upload mode. Screening label: ${predictionLabel}. Confidence: ${confidenceLabel}.`,
        reasonCodes: [
          'patient_sent_report',
          'ecg_report',
          'csv_upload',
          isAbnormalLabel(predictionLabel) ? 'abnormal_ecg' : 'routine_ecg',
        ],
        relatedDeviceId: null,
        metadata: {
          reportType: 'ecg',
          reportKind: 'csv_upload',
          prediction: predictionLabel,
          confidence: confidenceLabel,
          createdAt: new Date().toISOString(),
        },
      });
      toast.success('ECG report sent to your doctor.');
    } catch (sendError) {
      toast.error(sendError instanceof Error ? sendError.message : 'Could not send ECG report to doctor.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="rounded-[36px] bg-gradient-to-br from-[#092b20] via-[#0c5a3e] to-[#16b16d] px-6 py-8 text-white shadow-[0_28px_70px_rgba(6,52,37,0.2)] sm:px-8">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
          <div>
            <p className="cardios-kicker border border-white/15 bg-white/10 text-emerald-50">
              ECG Intelligence
            </p>
            <h1 className="mt-5 font-sora text-4xl font-semibold sm:text-5xl">
              ECG Lab
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-8 text-emerald-50/80">
              Analyse ECG recordings using the Cardios ECG classification pipeline.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <InfoPanel
              title="Backend status"
              value={
                serverStatus === 'checking'
                  ? 'Checking...'
                  : serverStatus === 'online'
                    ? 'Connected'
                    : 'Offline'
              }
              detail="Cardios ECG classification service."
            />
          </div>
        </div>
      </section>

      <div
        role="note"
        className="mt-6 flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600"
      >
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
        <p>
          Automated ECG analysis is decision-support only and is not a definitive clinical interpretation.
          Results may be affected by signal quality and should be reviewed by a qualified clinician.
        </p>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[0.72fr_0.28fr]">
        <div className="space-y-6">
          <Card>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                <Upload className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Upload workflow</p>
                <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                  Start a CSV-based ECG analysis
                </h2>
              </div>
            </div>

            {serverStatus === 'offline' ? (
              <div className="mt-5 rounded-[24px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
                Cardios cannot reach the ECG service. Make sure the backend is running on
                <code className="ml-1">{getApiBaseUrl()}</code>.
              </div>
            ) : null}

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div className="rounded-[28px] border border-dashed border-emerald-200 bg-emerald-50/60 p-5">
                <label className="block text-sm font-medium text-slate-800">
                  ECG CSV file
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleFileChange}
                    className="mt-3 block w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-emerald-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white"
                  />
                </label>
                <div className="mt-4 space-y-2 text-sm leading-7 text-slate-600">
                  <p>Upload a single-column CSV containing numeric ECG amplitude values. The signal will be validated for quality before classification.</p>
                  <p>
                    Cardios will save the prediction label, confidence score, and a short signal
                    preview for future comparison.
                  </p>
                </div>
                {file ? (
                  <p className="mt-3 text-sm font-medium text-emerald-700">
                    Selected file: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                  </p>
                ) : null}
              </div>

              <Button type="submit" disabled={isLoading || serverStatus !== 'online'}>
                {isLoading ? 'Analyzing ECG...' : 'Analyze in Cardios'}
                <Waves className="h-4 w-4" />
              </Button>
            </form>

            {errorDetails ? (
              <div className="mt-5 rounded-[24px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
                <p className="font-semibold">Analysis error</p>
                <p className="mt-2 whitespace-pre-wrap">{errorDetails}</p>
              </div>
            ) : null}
          </Card>

          {prediction ? (
            <Card>
              <MedicalDisclaimer className="mb-4" />
              <SignalQualityBanner quality={uploadQuality} />
              <ClinicianReviewNotice prediction={prediction} />
              <div className="grid gap-4 md:grid-cols-3">
                <MetricCard
                  title="Screening signal"
                  value={prediction}
                  detail="Automated beat-type estimate — monitoring support, not a diagnosis."
                />
                <MetricCard
                  title="Model confidence"
                  value={formatConfidence(confidence)}
                  detail="Withheld when signal quality is too poor to classify."
                />
                <MetricCard
                  title="Comparison insight"
                  value={
                    uploadConfidenceDelta === null
                      ? 'First local trace'
                      : uploadConfidenceDelta >= 0
                        ? `+${uploadConfidenceDelta}%`
                        : `${uploadConfidenceDelta}%`
                  }
                  detail="Change versus the most recent prior trace in local Cardios history."
                />
              </div>
              <div className="mt-5">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={sendingUploadReport}
                  onClick={() =>
                    void sendEcgReportToDoctor({
                      predictionLabel: prediction,
                      confidenceLabel: formatConfidence(confidence),
                      setSending: setSendingUploadReport,
                    })
                  }
                >
                  {sendingUploadReport ? 'Sending...' : 'Send ECG report to doctor'}
                  <HeartPulse className="h-4 w-4" />
                </Button>
              </div>

              <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="rounded-[28px] border border-emerald-100 bg-white p-5">
                  <div className="flex items-center gap-3">
                    <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                      <Activity className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Signal preview</p>
                      <h3 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                        Uploaded waveform
                      </h3>
                    </div>
                  </div>

                  <div className="mt-5">
                    <EcgWaveform
                      samples={ecgData}
                      sampleRateHz={uploadSampleRateHz}
                      ariaLabel="Uploaded ECG waveform"
                    />
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="rounded-[28px] bg-[#08251a] p-5 text-white">
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">
                      Comparison summary
                    </p>
                    <p className="mt-3 text-sm leading-7 text-emerald-50/85">{uploadSummary}</p>
                  </div>

                  <div className="rounded-[28px] border border-emerald-100 bg-white p-5">
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
                      Recommended follow-up
                    </p>
                    <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
                      <p>1. Compare this result with the latest Cardios risk-support summary and symptom check-in.</p>
                      <p>2. Repeat the screening after a new clinical event or meaningful symptom change.</p>
                      <p>3. Take any abnormal-looking trace to a clinician — only a physician with a clinical 12-lead ECG can diagnose.</p>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ) : null}
        </div>

        <div className="space-y-6">
          <Card>
            <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">History</p>
            <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
              Recent ECG traces
            </h2>

            <div className="mt-5 space-y-3">
              {history.length ? (
                history.slice(0, 5).map((item, index) => (
                  <div
                    key={item.id}
                    className="rounded-[22px] border border-slate-100 bg-white px-4 py-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-slate-900">{item.prediction}</p>
                      {index === 0 ? (
                        <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
                          Latest
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{item.fileName}</p>
                    <p className="mt-2 text-sm text-slate-500">
                      {new Date(item.createdAt).toLocaleString()} ·{' '}
                      {item.confidence > 0
                        ? `${item.confidence.toFixed(1)}% confidence`
                        : 'confidence withheld (signal quality)'}
                    </p>
                  </div>
                ))
              ) : (
                <p className="rounded-[22px] border border-dashed border-emerald-200 bg-white px-4 py-4 text-sm text-slate-600">
                  No ECG traces saved yet. Your first successful upload will appear here.
                </p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

const buildComparisonSummary = (
  latestPrediction: string,
  previousRecord: ECGAnalysisRecord | undefined,
  confidenceDelta: number | null
) => {
  if (!previousRecord) {
    return `This is the first ECG trace stored locally in Cardios. The current screening estimate is "${latestPrediction}", so future traces can be compared against it.`;
  }

  if (latestPrediction !== previousRecord.prediction) {
    return `The screening estimate changed from "${previousRecord.prediction}" to "${latestPrediction}". This shift is not a diagnosis — review it with a clinician alongside symptoms and the broader cardiac risk profile.`;
  }

  if (confidenceDelta !== null && Math.abs(confidenceDelta) >= 8) {
    return `The label stayed the same, but model confidence changed by ${confidenceDelta > 0 ? '+' : ''}${confidenceDelta}%. That may indicate a meaningful signal difference worth watching.`;
  }

  return 'The latest result is broadly consistent with the previous stored ECG trace, suggesting a similar pattern in the current Cardios history.';
};

const InfoPanel = ({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) => (
  <div className="rounded-[28px] border border-white/10 bg-white/10 p-5 backdrop-blur-sm">
    <p className="text-xs uppercase tracking-[0.18em] text-emerald-100/75">{title}</p>
    <p className="mt-3 font-sora text-2xl font-semibold text-white">{value}</p>
    <p className="mt-2 text-sm text-emerald-50/75">{detail}</p>
  </div>
);

const ClinicianReviewNotice = ({ prediction }: { prediction: string }) => {
  if (!isAbnormalLabel(prediction)) return null;
  return (
    <div className="mb-4 flex items-start gap-3 rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        <span className="font-semibold">Clinician review suggested. </span>
        The model flagged a pattern labelled &quot;{prediction}&quot;. A single-lead consumer trace
        cannot confirm this — share it with a healthcare professional, who can order a clinical
        12-lead ECG if needed.
      </p>
    </div>
  );
};

const SignalQualityBanner = ({
  quality,
  leadOff,
}: {
  quality?: SignalQuality | null;
  leadOff?: boolean;
}) => {
  if (!quality) {
    if (!leadOff) return null;
    return (
      <div className="mb-4 flex items-start gap-3 rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <p>Lead-off detected — an electrode is not in proper contact. Re-seat the leads before trusting any reading.</p>
      </div>
    );
  }

  const tone =
    quality.quality === 'good'
      ? { box: 'border-emerald-200 bg-emerald-50 text-emerald-800', Icon: CheckCircle2 }
      : quality.quality === 'acceptable'
        ? { box: 'border-amber-200 bg-amber-50 text-amber-800', Icon: AlertTriangle }
        : { box: 'border-red-200 bg-red-50 text-red-800', Icon: AlertTriangle };
  const { Icon } = tone;

  const label =
    quality.quality === 'poor'
      ? 'Poor signal quality — classification withheld'
      : quality.quality === 'acceptable'
        ? 'Acceptable signal quality — interpret with caution'
        : 'Good signal quality';

  return (
    <div className={`mb-4 rounded-[20px] border px-4 py-3 text-sm ${tone.box}`}>
      <div className="flex items-center gap-2 font-semibold">
        <Icon className="h-4 w-4 shrink-0" />
        <span>
          {label} · score {quality.qualityScore}/100
        </span>
      </div>
      {quality.reasons?.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-6 text-[13px] leading-6">
          {quality.reasons.map((reason, i) => (
            <li key={i}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
};

const MetricCard = ({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) => (
  <div className="rounded-[24px] border border-emerald-100 bg-white px-5 py-5">
    <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">{title}</p>
    <p className="mt-3 font-sora text-2xl font-semibold text-slate-950">{value}</p>
    <p className="mt-3 text-sm leading-7 text-slate-600">{detail}</p>
  </div>
);

export default ECGPrediction;
