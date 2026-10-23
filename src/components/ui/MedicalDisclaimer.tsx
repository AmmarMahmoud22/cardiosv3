import { AlertTriangle } from 'lucide-react';

/**
 * Clinical-safety gate (frontend). Cardios is an educational / decision-support
 * tool, not a diagnostic device. This banner is rendered alongside every
 * prediction result so a user never sees a model output without it. The backend
 * also returns a `disclaimer` field; pass it via `text` to show the server copy,
 * otherwise this default is used.
 */
export const MEDICAL_DISCLAIMER =
  'This result is an automated, educational estimate from a machine-learning model — ' +
  'it is not a medical diagnosis and can be wrong. Do not use it to start, stop, or ' +
  'change any treatment. For chest pain, shortness of breath, fainting, or other ' +
  'emergency symptoms, seek immediate medical care. Always consult a qualified ' +
  'healthcare professional about your heart health.';

interface MedicalDisclaimerProps {
  text?: string;
  className?: string;
}

export default function MedicalDisclaimer({ text, className = '' }: MedicalDisclaimerProps) {
  return (
    <div
      role="note"
      className={`flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900 ${className}`}
    >
      <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" aria-hidden="true" />
      <p>
        <span className="font-semibold">Not a medical diagnosis. </span>
        {text ?? MEDICAL_DISCLAIMER}
      </p>
    </div>
  );
}
