import type {
  FormData,
  PredictionRecord,
  PredictionTrendPoint,
  RiskFactor,
} from '../types';

const ageWeights: Record<string, number> = {
  '18-24': 0,
  '25-29': 2,
  '30-34': 4,
  '35-39': 7,
  '40-44': 10,
  '45-49': 13,
  '50-54': 17,
  '55-59': 21,
  '60-64': 25,
  '65-69': 30,
  '70-74': 35,
  '75-79': 40,
  '80 or older': 46,
};

export const computeCardiacRiskScore = (data: FormData): number => {
  let score = 8;

  score += ageWeights[data.AgeCategory] ?? 0;
  score += Math.max(0, (data.BMI - 22) * 1.5);
  score += data.Smoking === 'Yes' ? 14 : 0;
  score += data.AlcoholDrinking === 'Yes' ? 5 : 0;
  score += data.Stroke === 'Yes' ? 18 : 0;
  score += data.DiffWalking === 'Yes' ? 11 : 0;
  score += data.PhysicalActivity === 'No' ? 10 : 0;
  score += data.Diabetic === 'Yes' ? 12 : data.Diabetic.includes('borderline') ? 5 : 0;
  score += data.KidneyDisease === 'Yes' ? 10 : 0;
  score += data.Asthma === 'Yes' ? 4 : 0;
  score += data.SkinCancer === 'Yes' ? 3 : 0;
  score += data.PhysicalHealth * 0.8;
  score += data.MentalHealth * 0.4;
  score += data.SleepTime < 6 ? 8 : data.SleepTime > 9 ? 4 : 0;
  score += data.GenHealth === 'Poor' ? 18 : data.GenHealth === 'Fair' ? 10 : 0;

  return Math.max(0, Math.min(100, Math.round(score)));
};

export const buildRiskFactors = (data: FormData): RiskFactor[] => {
  const factors: RiskFactor[] = [];

  if (data.BMI >= 30) {
    factors.push({
      factor: 'Body composition',
      status: `BMI ${data.BMI} indicates obesity-related strain.`,
      risk: 'high',
      impact: 18,
      recommendation: 'Prioritize nutrition support and weight-management follow-up.',
    });
  } else if (data.BMI >= 25) {
    factors.push({
      factor: 'Body composition',
      status: `BMI ${data.BMI} is in the overweight range.`,
      risk: 'medium',
      impact: 10,
      recommendation: 'Track weight trend and reinforce activity goals.',
    });
  }

  if (data.Smoking === 'Yes') {
    factors.push({
      factor: 'Smoking',
      status: 'Active smoking increases vascular and cardiac workload.',
      risk: 'high',
      impact: 16,
      recommendation: 'Discuss a smoking cessation plan and follow-up support.',
    });
  }

  if (data.Stroke === 'Yes') {
    factors.push({
      factor: 'Neurologic / vascular history',
      status: 'Prior stroke history raises concern for cardiovascular burden.',
      risk: 'high',
      impact: 18,
      recommendation: 'Escalate clinician review and risk-factor optimization.',
    });
  }

  if (data.PhysicalActivity === 'No') {
    factors.push({
      factor: 'Activity level',
      status: 'Sedentary routine may weaken cardiovascular resilience.',
      risk: 'high',
      impact: 13,
      recommendation: 'Introduce a gradual activity target and monitor tolerance.',
    });
  }

  if (data.DiffWalking === 'Yes') {
    factors.push({
      factor: 'Functional capacity',
      status: 'Difficulty walking suggests lower exercise tolerance.',
      risk: 'medium',
      impact: 12,
      recommendation: 'Use check-ins to watch for progression or reduced stamina.',
    });
  }

  if (data.Diabetic === 'Yes' || data.Diabetic.includes('borderline')) {
    factors.push({
      factor: 'Metabolic health',
      status: `Diabetic status reported as "${data.Diabetic}".`,
      risk: data.Diabetic === 'Yes' ? 'high' : 'medium',
      impact: data.Diabetic === 'Yes' ? 14 : 8,
      recommendation: 'Coordinate glucose control and cardiovascular monitoring.',
    });
  }

  if (data.KidneyDisease === 'Yes') {
    factors.push({
      factor: 'Renal health',
      status: 'Kidney disease increases long-term cardiac risk.',
      risk: 'high',
      impact: 12,
      recommendation: 'Flag for clinician review and medication reconciliation.',
    });
  }

  if (data.PhysicalHealth >= 15) {
    factors.push({
      factor: 'Physical symptoms',
      status: `${data.PhysicalHealth} days of poor physical health reported.`,
      risk: 'high',
      impact: 14,
      recommendation: 'Consider symptom trend monitoring and earlier follow-up.',
    });
  }

  if (data.MentalHealth >= 15) {
    factors.push({
      factor: 'Stress burden',
      status: `${data.MentalHealth} days of poor mental health may affect self-management.`,
      risk: 'medium',
      impact: 6,
      recommendation: 'Support adherence, sleep hygiene, and stress reduction.',
    });
  }

  if (data.SleepTime < 6 || data.SleepTime > 9) {
    factors.push({
      factor: 'Sleep pattern',
      status: `${data.SleepTime} hours of sleep may indicate recovery imbalance.`,
      risk: 'medium',
      impact: 6,
      recommendation: 'Track sleep consistency alongside symptoms and fatigue.',
    });
  }

  if (data.GenHealth === 'Poor' || data.GenHealth === 'Fair') {
    factors.push({
      factor: 'Self-rated health',
      status: `General health was reported as "${data.GenHealth}".`,
      risk: data.GenHealth === 'Poor' ? 'high' : 'medium',
      impact: data.GenHealth === 'Poor' ? 14 : 8,
      recommendation: 'Use closer monitoring to see if the overall picture improves.',
    });
  }

  return factors.sort((left, right) => right.impact - left.impact);
};

export const getRiskBand = (
  score: number,
  predictionResult?: string
): 'stable' | 'elevated' | 'high' => {
  if (predictionResult?.includes('High') || score >= 65) {
    return 'high';
  }

  if (score >= 38) {
    return 'elevated';
  }

  return 'stable';
};

export const getRiskBandLabel = (band: 'stable' | 'elevated' | 'high') => {
  if (band === 'high') return 'High attention';
  if (band === 'elevated') return 'Elevated watch';
  return 'Stable watch';
};

export const buildNextSteps = (data: FormData, predictionResult: string) => {
  const steps = [
    'Repeat the assessment after major symptom or lifestyle changes to track trend direction.',
    'Use the monitoring check-ins to document fatigue, sleep, stress, and daily activity.',
  ];

  if (predictionResult.includes('High')) {
    steps.unshift('Schedule a clinician review soon to validate risk factors and discuss next diagnostics.');
  }

  if (data.Stroke === 'Yes' || data.KidneyDisease === 'Yes') {
    steps.push('Prioritize medication review and chronic condition follow-up with a healthcare professional.');
  }

  if (data.PhysicalActivity === 'No' || data.DiffWalking === 'Yes') {
    steps.push('Set a low-intensity movement goal and monitor tolerance over the next 2 weeks.');
  }

  if (data.Smoking === 'Yes') {
    steps.push('Add smoking cessation support to the care plan because it materially shifts cardiac risk.');
  }

  return [...new Set(steps)];
};

export const buildPredictionTimeline = (
  predictions: PredictionRecord[]
): PredictionTrendPoint[] =>
  predictions
    .slice()
    .sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime())
    .map((prediction) => {
      const riskScore = computeCardiacRiskScore(prediction.prediction_data);
      const riskBand = getRiskBand(riskScore, prediction.prediction_result);

      return {
        id: prediction.id,
        date: prediction.created_at,
        label: new Date(prediction.created_at).toLocaleDateString(),
        riskScore,
        riskBand,
        predictionResult: prediction.prediction_result,
      };
    });

export const buildTrendNarrative = (timeline: PredictionTrendPoint[]) => {
  if (timeline.length < 2) {
    return 'You need at least two completed assessments to unlock a meaningful risk trajectory.';
  }

  const latest = timeline[timeline.length - 1];
  const previous = timeline[timeline.length - 2];
  const delta = latest.riskScore - previous.riskScore;

  if (delta >= 8) {
    return 'Risk indicators have moved upward since the last assessment and should be reviewed closely.';
  }

  if (delta <= -8) {
    return 'The latest assessment shows a healthier trajectory compared with the previous reading.';
  }

  return 'The latest assessment is broadly consistent with recent cardiac risk patterns.';
};

export const buildResultHeadline = (predictionResult: string, score: number) => {
  const band = getRiskBand(score, predictionResult);

  if (band === 'high') {
    return 'Cardios sees a high-priority cardiac risk profile.';
  }

  if (band === 'elevated') {
    return 'Cardios sees an elevated-risk pattern that deserves continued monitoring.';
  }

  return 'Cardios sees a comparatively stable risk profile right now.';
};
