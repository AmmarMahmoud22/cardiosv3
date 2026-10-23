import React, { useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Download,
  HeartPulse,
  Info,
  Moon,
  ShieldCheck,
  UserRound,
  Waves,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuthStore } from '../stores/authStore';
import type { FormData } from '../types';
import {
  AGE_CATEGORIES,
  DIABETIC_OPTIONS,
  GEN_HEALTH_OPTIONS,
  RACE_CATEGORIES,
} from '../types';
import { savePrediction } from '../services/predictionService';
import { sendPatientReportToDoctor } from '../services/patientReports';
import {
  buildNextSteps,
  buildResultHeadline,
  buildRiskFactors,
  computeCardiacRiskScore,
  getRiskBand,
  getRiskBandLabel,
} from '../services/cardiacInsights';
import SelectField from './form/SelectField';
import NumberField from './form/NumberField';
import Card from './ui/Card';
import Button from './ui/Button';
import MedicalDisclaimer from './ui/MedicalDisclaimer';
import { getApiBaseUrl, getAuthHeaders } from '../lib/api';

// Labelled, ordered view of every model input — rendered into the report so a
// clinician can see exactly what the estimate was based on.
const REPORT_INPUT_LABELS: Array<[keyof FormData, string]> = [
  ['Sex', 'Sex'],
  ['AgeCategory', 'Age category'],
  ['Race', 'Race'],
  ['GenHealth', 'General health'],
  ['BMI', 'BMI'],
  ['SleepTime', 'Sleep (hours)'],
  ['Smoking', 'Smoking'],
  ['AlcoholDrinking', 'Alcohol drinking'],
  ['PhysicalActivity', 'Physical activity'],
  ['PhysicalHealth', 'Poor physical health days'],
  ['MentalHealth', 'Poor mental health days'],
  ['DiffWalking', 'Difficulty walking'],
  ['Stroke', 'Stroke history'],
  ['Diabetic', 'Diabetic'],
  ['Asthma', 'Asthma'],
  ['KidneyDisease', 'Kidney disease'],
  ['SkinCancer', 'Skin cancer'],
];

const INITIAL_FORM_DATA: FormData = {
  BMI: 25,
  Smoking: 'No',
  AlcoholDrinking: 'No',
  Stroke: 'No',
  PhysicalHealth: 0,
  MentalHealth: 0,
  DiffWalking: 'No',
  Sex: 'Male',
  AgeCategory: '18-24',
  Race: 'White',
  Diabetic: 'No',
  PhysicalActivity: 'Yes',
  GenHealth: 'Very good',
  SleepTime: 7,
  Asthma: 'No',
  KidneyDisease: 'No',
  SkinCancer: 'No',
};

const PredictionForm: React.FC = () => {
  const { user } = useAuthStore();
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState<FormData>(INITIAL_FORM_DATA);
  const [prediction, setPrediction] = useState<string | null>(null);
  // Snapshot of the inputs that produced the current prediction, so the report
  // stays consistent even if the form is edited after submission.
  const [submittedData, setSubmittedData] = useState<FormData | null>(null);
  const [assessedAt, setAssessedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(false);
  const [sendingReport, setSendingReport] = useState(false);
  const resultsRef = useRef<HTMLDivElement>(null);

  // Live values drive the sidebar preview while the user fills the form.
  const riskScore = useMemo(() => computeCardiacRiskScore(formData), [formData]);
  const riskFactors = useMemo(() => buildRiskFactors(formData), [formData]);

  // Report values are pinned to the submitted snapshot.
  const reportData = submittedData ?? formData;
  const reportScore = useMemo(() => computeCardiacRiskScore(reportData), [reportData]);
  const reportFactors = useMemo(() => buildRiskFactors(reportData), [reportData]);
  const riskBand = useMemo(
    () => getRiskBand(reportScore, prediction ?? undefined),
    [prediction, reportScore]
  );
  const nextSteps = useMemo(
    () => (prediction ? buildNextSteps(reportData, prediction) : []),
    [reportData, prediction]
  );
  const resultHeadline = useMemo(
    () => (prediction ? buildResultHeadline(prediction, reportScore) : ''),
    [prediction, reportScore]
  );

  const handleInputChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = event.target;
    setFormData((previous) => ({
      ...previous,
      [name]: event.target.type === 'number' ? Number(value) : value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!user) {
      toast.error('Please sign in to run a Cardios assessment.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${getApiBaseUrl()}/predict`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(await getAuthHeaders()),
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Cardios could not complete the assessment.');
      }

      const predictionResult = data.HeartFailureRisk;
      setPrediction(predictionResult);
      setSubmittedData({ ...formData });
      setAssessedAt(new Date());
      setShowResults(true);

      const savedPrediction = await savePrediction(user.id, formData, predictionResult);

      if (savedPrediction) {
        toast.success('Assessment complete. Your Cardios report has been saved.');
      } else {
        toast.error('Assessment completed, but the report could not be saved.');
      }

      window.setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (submitError) {
      const message =
        submitError instanceof Error
          ? submitError.message
          : 'Network error: Cardios could not reach the prediction service.';
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const downloadAsPDF = async () => {
    if (!resultsRef.current) {
      return;
    }

    try {
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ]);

      // html2canvas's bundled types omit backgroundColor/scale, but both are
      // valid runtime options — cast to satisfy tsc without changing behaviour.
      const canvas = await html2canvas(resultsRef.current, {
        backgroundColor: '#f4fbf7',
        scale: 2,
      } as Parameters<typeof html2canvas>[1]);

      const image = canvas.toDataURL('image/png');
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'px',
        format: [canvas.width, canvas.height],
      });

      pdf.addImage(image, 'PNG', 0, 0, canvas.width, canvas.height);
      const stamp = (assessedAt ?? new Date()).toISOString().slice(0, 16).replace(/[:T]/g, '-');
      pdf.save(`cardios-assessment-report-${stamp}.pdf`);
      toast.success('Cardios report downloaded successfully.');
    } catch (pdfError) {
      console.error('PDF generation error:', pdfError);
      toast.error('Cardios could not export the report.');
    }
  };

  const sendRiskReportToDoctor = async () => {
    if (!user?.id || !prediction) return;
    setSendingReport(true);

    try {
      await sendPatientReportToDoctor({
        patientId: user.id,
        source: 'risk_prediction',
        severity: riskBand === 'high' ? 'high' : riskBand === 'elevated' ? 'medium' : 'low',
        title: `Patient risk report: ${getRiskBandLabel(riskBand)}`,
        message: `${resultHeadline} Result: ${prediction}. Cardios score: ${reportScore}/100. Top drivers: ${
          reportFactors.slice(0, 3).map((factor) => factor.factor).join(', ') || 'none'
        }.`,
        reasonCodes: [
          'patient_sent_report',
          `risk_band_${riskBand}`,
          ...(reportFactors.slice(0, 3).map((factor) => factor.factor.toLowerCase().replace(/\s+/g, '_'))),
        ],
        metadata: {
          reportType: 'risk_prediction',
          riskScore: reportScore,
          riskBand,
          prediction,
          assessedAt: (assessedAt ?? new Date()).toISOString(),
        },
      });
      toast.success('Report sent to your doctor.');
    } catch (sendError) {
      toast.error(sendError instanceof Error ? sendError.message : 'Could not send report to doctor.');
    } finally {
      setSendingReport(false);
    }
  };

  const assessmentSteps = [
    {
      title: 'Profile',
      description: 'Demographics and baseline patient context.',
      icon: <UserRound className="h-5 w-5" />,
      content: (
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField
            label="Sex"
            name="Sex"
            value={formData.Sex}
            onChange={handleInputChange}
            options={[
              { value: 'Male', label: 'Male' },
              { value: 'Female', label: 'Female' },
            ]}
          />
          <SelectField
            label="Age category"
            name="AgeCategory"
            value={formData.AgeCategory}
            onChange={handleInputChange}
            options={AGE_CATEGORIES.map((age) => ({ value: age, label: age }))}
          />
          <SelectField
            label="Race"
            name="Race"
            value={formData.Race}
            onChange={handleInputChange}
            options={RACE_CATEGORIES.map((race) => ({ value: race, label: race }))}
          />
          <SelectField
            label="General health"
            name="GenHealth"
            value={formData.GenHealth}
            onChange={handleInputChange}
            options={GEN_HEALTH_OPTIONS.map((value) => ({ value, label: value }))}
          />
        </div>
      ),
    },
    {
      title: 'Lifestyle',
      description: 'Habits that influence long-term cardiovascular resilience.',
      icon: <Activity className="h-5 w-5" />,
      content: (
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField
            label="Smoking"
            name="Smoking"
            value={formData.Smoking}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
          <SelectField
            label="Alcohol drinking"
            name="AlcoholDrinking"
            value={formData.AlcoholDrinking}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
          <SelectField
            label="Physical activity"
            name="PhysicalActivity"
            value={formData.PhysicalActivity}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
          <NumberField
            label={
              <div className="flex items-center gap-2">
                <Moon className="h-4 w-4 text-emerald-700" />
                Sleep time (hours)
              </div>
            }
            name="SleepTime"
            value={formData.SleepTime}
            onChange={handleInputChange}
            min={0}
            max={24}
          />
        </div>
      ),
    },
    {
      title: 'Symptoms',
      description: 'Physical and mental health burden over the last month.',
      icon: <HeartPulse className="h-5 w-5" />,
      content: (
        <div className="grid gap-4 md:grid-cols-2">
          <NumberField
            label={
              <LabelWithHint
                title="BMI"
                hint="Body Mass Index. Cardios uses it as one contributor, not a diagnosis."
              />
            }
            name="BMI"
            value={formData.BMI}
            onChange={handleInputChange}
            min={10}
            max={60}
            step={0.1}
          />
          <NumberField
            label={
              <LabelWithHint
                title="Poor physical health days"
                hint="How many days in the past 30 days your physical health felt not good."
              />
            }
            name="PhysicalHealth"
            value={formData.PhysicalHealth}
            onChange={handleInputChange}
            min={0}
            max={30}
          />
          <NumberField
            label={
              <LabelWithHint
                title="Poor mental health days"
                hint="How many days in the past 30 days your mental health felt not good."
              />
            }
            name="MentalHealth"
            value={formData.MentalHealth}
            onChange={handleInputChange}
            min={0}
            max={30}
          />
          <SelectField
            label="Difficulty walking"
            name="DiffWalking"
            value={formData.DiffWalking}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
        </div>
      ),
    },
    {
      title: 'Conditions',
      description: 'Comorbidities and clinical history relevant to cardiac risk.',
      icon: <ShieldCheck className="h-5 w-5" />,
      content: (
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField
            label="Stroke history"
            name="Stroke"
            value={formData.Stroke}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
          <SelectField
            label="Diabetic"
            name="Diabetic"
            value={formData.Diabetic}
            onChange={handleInputChange}
            options={DIABETIC_OPTIONS.map((value) => ({ value, label: value }))}
          />
          <SelectField
            label="Asthma"
            name="Asthma"
            value={formData.Asthma}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
          <SelectField
            label="Kidney disease"
            name="KidneyDisease"
            value={formData.KidneyDisease}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
          <SelectField
            label="Skin cancer"
            name="SkinCancer"
            value={formData.SkinCancer}
            onChange={handleInputChange}
            options={[
              { value: 'Yes', label: 'Yes' },
              { value: 'No', label: 'No' },
            ]}
          />
        </div>
      ),
    },
  ];

  const currentStepData = assessmentSteps[currentStep];

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="grid gap-6 lg:grid-cols-[0.72fr_0.28fr]">
        <div className="space-y-6">
          <section className="rounded-[36px] bg-gradient-to-br from-[#0d392a] via-[#0c5a3e] to-[#18b36e] px-6 py-8 text-white shadow-[0_32px_70px_rgba(9,63,44,0.18)] sm:px-8">
            <div className="max-w-3xl">
              <p className="cardios-kicker border border-white/15 bg-white/10 text-emerald-50">
                Heart Risk Intelligence
              </p>
              <h1 className="mt-5 font-sora text-4xl font-semibold sm:text-5xl">
                AI Assessment
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-8 text-emerald-50/80">
                Evaluate cardiac risk indicators using the patient&apos;s provided health profile.
              </p>
            </div>
          </section>

          <div role="note" className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden="true" />
            <p>
              <span className="font-semibold text-slate-700">Not a medical diagnosis. </span>
              This assessment estimates a cardiac risk profile from the information provided and
              is intended for decision support only. It does not replace clinical evaluation by
              a qualified healthcare professional.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error ? (
              <div className="rounded-[24px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <Card className="overflow-hidden p-0">
              <div className="border-b border-emerald-100 px-6 py-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Assessment flow</p>
                    <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                      {currentStepData.title}
                    </h2>
                    <p className="mt-2 text-sm text-slate-600">{currentStepData.description}</p>
                  </div>
                  <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                    {currentStepData.icon}
                  </div>
                </div>
              </div>

              <div className="px-6 pt-6">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {assessmentSteps.map((step, index) => (
                    <button
                      key={step.title}
                      type="button"
                      onClick={() => setCurrentStep(index)}
                      className={`rounded-[22px] border px-4 py-4 text-left transition ${
                        index === currentStep
                          ? 'border-emerald-400 bg-emerald-50 shadow-sm'
                          : 'border-slate-200 bg-white hover:border-emerald-200 hover:bg-emerald-50/50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`rounded-2xl p-2 ${
                            index === currentStep
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {step.icon}
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                            Step {index + 1}
                          </p>
                          <p className="mt-1 font-medium text-slate-900">{step.title}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="mt-6 h-2 rounded-full bg-emerald-100">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-emerald-500 to-[#0c7f58] transition-all duration-300"
                    style={{ width: `${((currentStep + 1) / assessmentSteps.length) * 100}%` }}
                  />
                </div>
              </div>

              <div className="px-6 py-6">{currentStepData.content}</div>

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-emerald-100 px-6 py-5">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={currentStep === 0}
                  onClick={() => setCurrentStep((previous) => Math.max(previous - 1, 0))}
                >
                  Previous step
                </Button>

                <div className="flex flex-wrap gap-3">
                  {currentStep < assessmentSteps.length - 1 ? (
                    <Button
                      type="button"
                      onClick={() =>
                        setCurrentStep((previous) =>
                          Math.min(previous + 1, assessmentSteps.length - 1)
                        )
                      }
                    >
                      Next step
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button type="submit" disabled={loading}>
                      {loading ? 'Running Cardios AI...' : 'Run Cardios assessment'}
                      <HeartPulse className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          </form>

          {showResults && prediction ? (
            <Card className="space-y-6 bg-[#f7fcf9]">
              <div ref={resultsRef} className="space-y-6">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-emerald-100 pb-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
                      Cardios assessment report
                    </p>
                    <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                      Cardiac risk-support summary
                    </h2>
                  </div>
                  <div className="text-right text-sm text-slate-600">
                    <p>Generated: {(assessedAt ?? new Date()).toLocaleString()}</p>
                    <p className="mt-1 font-medium text-amber-700">
                      Screening estimate — requires clinician review
                    </p>
                  </div>
                </div>

                <MedicalDisclaimer />

                {riskBand === 'high' ? (
                  <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-800">
                    <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" aria-hidden="true" />
                    <p>
                      <span className="font-semibold">Clinician review recommended. </span>
                      This profile matched the model&apos;s higher-risk pattern. Share this report with a
                      healthcare professional — do not start, stop, or change any treatment based on it.
                    </p>
                  </div>
                ) : null}

                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
                      Assessment result
                    </p>
                    <h2 className="mt-2 font-sora text-3xl font-semibold text-slate-950">
                      {resultHeadline}
                    </h2>
                    <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">{prediction}</p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button type="button" variant="secondary" onClick={sendRiskReportToDoctor} disabled={sendingReport}>
                      {sendingReport ? 'Sending...' : 'Send to doctor'}
                      <HeartPulse className="h-4 w-4" />
                    </Button>
                    <Button type="button" variant="secondary" onClick={downloadAsPDF}>
                      Download report
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <MetricCard
                    title="Cardios risk score"
                    value={`${reportScore}/100`}
                    detail="Explanatory composite from the entered profile — not a validated clinical risk calculator."
                  />
                  <MetricCard
                    title="Risk band"
                    value={getRiskBandLabel(riskBand)}
                    detail="A simplified watch level to help interpret the model output."
                  />
                  <MetricCard
                    title="Top concern"
                    value={reportFactors[0]?.factor || 'No major driver'}
                    detail={reportFactors[0]?.status || 'No single dominant driver identified from the form.'}
                  />
                </div>

                <div className="rounded-[28px] border border-emerald-100 bg-white p-5">
                  <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
                    Inputs used for this assessment
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    {REPORT_INPUT_LABELS.map(([key, label]) => (
                      <div key={key} className="rounded-2xl bg-slate-50 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
                        <p className="mt-1 text-sm font-medium text-slate-900">{String(reportData[key])}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
                  <div className="space-y-4 rounded-[28px] border border-emerald-100 bg-white p-5">
                    <div className="flex items-center gap-3">
                      <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                        <AlertCircle className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
                          Risk drivers
                        </p>
                        <h3 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                          Why Cardios reached this result
                        </h3>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {reportFactors.length ? (
                        reportFactors.slice(0, 6).map((factor) => (
                          <div
                            key={`${factor.factor}-${factor.status}`}
                            className="rounded-[22px] border border-slate-100 bg-slate-50 px-4 py-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <p className="font-medium text-slate-900">{factor.factor}</p>
                              <span
                                className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                                  factor.risk === 'high'
                                    ? 'bg-red-100 text-red-700'
                                    : factor.risk === 'medium'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-emerald-100 text-emerald-700'
                                }`}
                              >
                                {factor.risk} impact
                              </span>
                            </div>
                            <p className="mt-2 text-sm leading-7 text-slate-600">{factor.status}</p>
                            <p className="mt-2 text-sm text-emerald-700">{factor.recommendation}</p>
                          </div>
                        ))
                      ) : (
                        <p className="rounded-[22px] bg-emerald-50 px-4 py-4 text-sm text-slate-600">
                          No prominent risk factors were triggered by the current data entry.
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-[28px] bg-[#0b2b20] p-5 text-white">
                      <p className="text-xs uppercase tracking-[0.2em] text-emerald-200">
                        Summary for clinician review
                      </p>
                      <p className="mt-3 text-sm leading-7 text-emerald-50/85">
                        Cardios combines patient-reported context with the ML model to flag a
                        {` ${getRiskBandLabel(riskBand).toLowerCase()} `}
                        profile. The strongest contributors came from {reportFactors
                          .slice(0, 3)
                          .map((item) => item.factor.toLowerCase())
                          .join(', ') || 'the general intake profile'}. This is screening
                        support based on self-reported data, not a clinical finding.
                      </p>
                    </div>

                    <div className="rounded-[28px] border border-emerald-100 bg-white p-5">
                      <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                          <Waves className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">
                            Next steps
                          </p>
                          <h3 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
                            Suggested follow-up
                          </h3>
                        </div>
                      </div>

                      <div className="mt-4 space-y-3">
                        {nextSteps.map((step) => (
                          <div
                            key={step}
                            className="rounded-[20px] border border-slate-100 bg-slate-50 px-4 py-4 text-sm leading-7 text-slate-600"
                          >
                            {step}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5 text-sm leading-7 text-slate-600">
                  <p className="font-semibold text-slate-800">Limitations of this report</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    <li>
                      The model is a statistical screening tool trained on self-reported population
                      survey data; it has not been clinically validated for individual diagnosis.
                    </li>
                    <li>
                      The result reflects a single point in time and depends entirely on the accuracy
                      of the entered information.
                    </li>
                    <li>
                      The Cardios risk score and risk band are explanatory aids derived from the form
                      inputs — they are not a validated clinical risk calculator.
                    </li>
                    <li>
                      Only a qualified clinician, with examination and appropriate diagnostics, can
                      assess actual cardiac status.
                    </li>
                  </ul>
                </div>
              </div>
            </Card>
          ) : null}
        </div>

        <div className="space-y-6">
          <Card>
            <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Live preview</p>
            <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
              Assessment posture before submission
            </h2>
            <div className="mt-5 rounded-[24px] bg-emerald-50 p-5">
              <p className="text-sm text-slate-600">Estimated Cardios score</p>
              <p className="mt-3 font-sora text-4xl font-semibold text-slate-950">{riskScore}</p>
              <p className="mt-2 text-sm text-slate-600">
                {getRiskBandLabel(getRiskBand(riskScore))} based on the current form state.
              </p>
            </div>

            <div className="mt-5 space-y-3">
              {riskFactors.slice(0, 3).map((factor) => (
                <div
                  key={factor.factor}
                  className="rounded-[22px] border border-slate-100 bg-white px-4 py-4"
                >
                  <p className="font-medium text-slate-900">{factor.factor}</p>
                  <p className="mt-2 text-sm leading-7 text-slate-600">{factor.status}</p>
                </div>
              ))}

              {riskFactors.length === 0 ? (
                <p className="rounded-[22px] border border-dashed border-emerald-200 bg-white px-4 py-4 text-sm text-slate-600">
                  Your current inputs do not yet trigger prominent risk drivers.
                </p>
              ) : null}
            </div>
          </Card>

          <Card>
            <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">How to use</p>
            <h2 className="mt-2 font-sora text-2xl font-semibold text-slate-950">
              Best-practice workflow
            </h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
              <p>1. Capture stable baseline information rather than a rushed estimate.</p>
              <p>2. Repeat after meaningful symptom or lifestyle changes to build a trend.</p>
              <p>3. Pair this result with the ECG Lab and Monitoring panels for stronger context.</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

const LabelWithHint = ({ title, hint }: { title: string; hint: string }) => (
  <div className="flex items-center gap-2">
    <span>{title}</span>
    <div className="group relative">
      <Info className="h-4 w-4 cursor-help text-emerald-700" />
      <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-56 -translate-x-1/2 rounded-2xl bg-slate-950 px-3 py-2 text-xs leading-5 text-white opacity-0 shadow-lg transition group-hover:opacity-100">
        {hint}
      </div>
    </div>
  </div>
);

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
    <p className="mt-3 font-sora text-3xl font-semibold text-slate-950">{value}</p>
    <p className="mt-3 text-sm leading-7 text-slate-600">{detail}</p>
  </div>
);

export default PredictionForm;
