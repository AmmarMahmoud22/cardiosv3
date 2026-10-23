import React, { useState } from 'react';
import Button from '../ui/Button';

const inputClasses =
  'mt-2 block w-full rounded-2xl border border-emerald-100 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200';

const ContactForm: React.FC = () => {
  const [isSent, setIsSent] = useState(false);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setIsSent(true);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="text-sm font-medium text-slate-700">Name</label>
        <input type="text" className={inputClasses} required />
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700">Email</label>
        <input type="email" className={inputClasses} required />
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700">What do you want to improve?</label>
        <textarea rows={5} className={inputClasses} required />
      </div>

      <Button type="submit" className="w-full">
        Send to Cardios
      </Button>

      {isSent && (
        <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          Thanks. This demo form is now capturing your intent for presentation purposes.
        </p>
      )}
    </form>
  );
};

export default ContactForm;
