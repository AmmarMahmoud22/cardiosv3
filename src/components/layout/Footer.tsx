import React from 'react';
import { ActivitySquare, Mail, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

const Footer: React.FC = () => {
  return (
    <footer className="border-t border-emerald-100 bg-[#071c15] text-white">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.3fr_0.7fr_0.7fr] lg:px-8">
        <div>
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500 text-white">
              <ActivitySquare className="h-5 w-5" />
            </div>
            <div>
              <p className="font-sora text-xl font-semibold">Cardios</p>
              <p className="text-xs uppercase tracking-[0.24em] text-emerald-200">Cardiac Intelligence</p>
            </div>
          </div>
          <p className="max-w-xl text-sm leading-7 text-emerald-50/80">
            Cardios brings risk assessment, ECG review, monitoring check-ins, and clinician-ready
            reporting into one calm cardiac intelligence workspace.
          </p>
          <div className="mt-5 flex flex-wrap gap-3 text-xs text-emerald-100/80">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-900 px-3 py-2">
              <Sparkles className="h-3.5 w-3.5" />
              AI-assisted assessments
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-900 px-3 py-2">
              <ShieldCheck className="h-3.5 w-3.5" />
              Patient-centered monitoring
            </span>
          </div>
        </div>

        <div>
          <h3 className="mb-4 font-sora text-lg font-semibold">Navigate</h3>
          <div className="space-y-3 text-sm text-emerald-50/80">
            <Link className="block hover:text-white" to="/">
              Home
            </Link>
            <Link className="block hover:text-white" to="/predict">
              Heart Risk
            </Link>
            <Link className="block hover:text-white" to="/predict-ecg">
              ECG Lab
            </Link>
            <Link className="block hover:text-white" to="/evidence">
              Evidence Advisor
            </Link>
            <Link className="block hover:text-white" to="/profile">
              Profile
            </Link>
          </div>
        </div>

        <div>
          <h3 className="mb-4 font-sora text-lg font-semibold">Support</h3>
          <div className="space-y-3 text-sm text-emerald-50/80">
            <Link className="block hover:text-white" to="/about">
              About
            </Link>
            <Link className="block hover:text-white" to="/contact">
              Contact
            </Link>
            <p className="inline-flex items-center gap-2">
              <Mail className="h-4 w-4 text-emerald-300" />
              hello@cardios.health
            </p>
          </div>
        </div>
      </div>
      <div className="border-t border-emerald-950/80 px-4 py-5 text-center text-sm text-emerald-100/70">
        © {new Date().getFullYear()} Cardios. Built for better cardiac decisions.
      </div>
    </footer>
  );
};

export default Footer;
