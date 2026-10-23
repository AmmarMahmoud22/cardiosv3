import React from 'react';
import Card from '../components/ui/Card';
import ContactForm from '../components/contact/ContactForm';
import ContactInfo from '../components/contact/ContactInfo';

const Contact: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
      <div className="mb-10 max-w-3xl">
        <div className="cardios-kicker mb-4">Talk to the Cardios team</div>
        <h1 className="cardios-section-title">Bring Cardios into your cardiac workflow.</h1>
        <p className="mt-4 text-lg leading-8 text-slate-600">
          Reach out for product walkthroughs, clinician feedback, partnership ideas, or deployment
          questions around cardiac risk screening and ECG-assisted monitoring.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <h2 className="font-sora text-2xl font-semibold text-slate-950">Start the conversation</h2>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            Tell us how you want to use Cardios, what kind of users you are supporting, and what
            cardiac workflow you need to improve.
          </p>
          <div className="mt-6">
            <ContactForm />
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="font-sora text-2xl font-semibold text-slate-950">Contact details</h2>
            <div className="mt-5">
              <ContactInfo />
            </div>
          </Card>

          <Card className="bg-[#08251a] text-white">
            <h2 className="font-sora text-2xl font-semibold">Who Cardios is built for</h2>
            <div className="mt-5 space-y-3 text-sm leading-7 text-emerald-50/80">
              <p>Clinics screening for earlier cardiac risk patterns.</p>
              <p>Remote care teams monitoring symptom change between visits.</p>
              <p>Students and researchers demonstrating end-to-end cardiac AI workflows.</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Contact;
