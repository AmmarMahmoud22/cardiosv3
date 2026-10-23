import React from 'react';
import { ArrowRight, BrainCircuit, HeartPulse, ShieldCheck, Stethoscope, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';

const pillars = [
  {
    title: 'AI that stays interpretable',
    body: 'Cardios turns tabular risk prediction into a readable story with score trends, risk drivers, and follow-up cues.',
    icon: BrainCircuit,
  },
  {
    title: 'ECG analysis that keeps context',
    body: 'Uploaded ECG traces are paired with confidence and side-by-side comparison so each new reading means more than a label.',
    icon: Waves,
  },
  {
    title: 'Monitoring between visits',
    body: 'Patients can track fatigue, stress, breathlessness, sleep, and activity to support safer ongoing review.',
    icon: HeartPulse,
  },
];

const About: React.FC = () => {
  return (
    <div className="min-h-screen px-4 py-14 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-12">
        <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <div className="cardios-kicker mb-5">About Cardios</div>
            <h1 className="cardios-section-title max-w-4xl">
              Cardios was designed to feel like a cardiac command center, not just a prediction screen.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
              We built Cardios to combine structured risk assessment, ECG review, continuous monitoring,
              and clinician-facing reporting inside one experience. The goal is earlier recognition,
              clearer follow-up, and better continuity between cardiac touchpoints.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link to="/predict">
                <ButtonLink label="Start an AI assessment" />
              </Link>
              <Link to="/predict-ecg">
                <ButtonLink label="Open ECG Lab" secondary />
              </Link>
            </div>
          </div>

          <Card className="overflow-hidden p-0">
            <div className="h-full bg-gradient-to-br from-emerald-500 via-emerald-600 to-[#08251a] p-8 text-white">
              <p className="text-xs uppercase tracking-[0.24em] text-emerald-100">Core product promise</p>
              <div className="mt-6 space-y-4">
                <InsightRow
                  icon={<ShieldCheck className="h-5 w-5" />}
                  title="Detect earlier"
                  body="Flag cardiac risk signals before they are buried in fragmented data."
                />
                <InsightRow
                  icon={<Stethoscope className="h-5 w-5" />}
                  title="Guide next steps"
                  body="Translate AI output into immediate follow-up recommendations."
                />
                <InsightRow
                  icon={<HeartPulse className="h-5 w-5" />}
                  title="Monitor continuously"
                  body="Keep symptoms and recovery visible between clinic visits."
                />
              </div>
            </div>
          </Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          {pillars.map(({ title, body, icon: Icon }) => (
            <Card key={title}>
              <div className="mb-5 inline-flex rounded-2xl bg-emerald-50 p-3 text-emerald-700">
                <Icon className="h-6 w-6" />
              </div>
              <h2 className="font-sora text-2xl font-semibold text-slate-950">{title}</h2>
              <p className="mt-4 text-sm leading-7 text-slate-600">{body}</p>
            </Card>
          ))}
        </section>

        <section>
          <Card className="border-amber-200 bg-amber-50/60">
            <h2 className="font-sora text-2xl font-semibold text-slate-950">Scope &amp; limitations</h2>
            <p className="mt-3 text-sm leading-7 text-slate-700">
              Cardios is a <strong>monitoring and risk-support tool, not a diagnostic device</strong>. Its
              outputs are automated screening estimates and can be wrong.
            </p>
            <ul className="mt-4 list-disc space-y-2 pl-6 text-sm leading-7 text-slate-700">
              <li>
                ECG capture uses a low-cost <strong>single-lead</strong> sensor (AD8232). It can support
                heart-rate, rhythm-regularity, and ectopic-beat screening, but <strong>cannot</strong> detect
                ischemia or a heart attack, or localize conduction disease — that needs a clinical 12-lead ECG.
              </li>
              <li>Poor-quality traces (lead-off, flatline, clipping, noise) are flagged and not classified.</li>
              <li>The risk model estimates statistical risk from self-reported data; it does not confirm any condition.</li>
              <li>Always consult a qualified clinician. For chest pain, fainting, or breathlessness, seek emergency care.</li>
            </ul>
          </Card>
        </section>
      </div>
    </div>
  );
};

const InsightRow = ({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) => (
  <div className="rounded-[28px] bg-white/10 p-5 backdrop-blur-sm">
    <div className="mb-3 inline-flex rounded-2xl bg-white/15 p-2.5 text-emerald-100">{icon}</div>
    <h3 className="font-sora text-xl">{title}</h3>
    <p className="mt-2 text-sm leading-7 text-emerald-50/80">{body}</p>
  </div>
);

const ButtonLink = ({ label, secondary = false }: { label: string; secondary?: boolean }) => (
  <span
    className={`inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition-all ${
      secondary
        ? 'border border-emerald-200 bg-white text-slate-900 hover:bg-emerald-50'
        : 'bg-emerald-500 text-white hover:bg-emerald-600'
    }`}
  >
    {label}
    <ArrowRight className="h-4 w-4" />
  </span>
);

export default About;
