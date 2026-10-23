import React from 'react';
import { Mail, MapPin, Phone } from 'lucide-react';

const ContactItem = ({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) => (
  <div className="flex items-start gap-4 rounded-3xl bg-emerald-50/80 p-4">
    <div className="rounded-2xl bg-white p-3 text-emerald-700 shadow-sm">{icon}</div>
    <div>
      <p className="font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
    </div>
  </div>
);

const ContactInfo: React.FC = () => {
  return (
    <div className="space-y-4">
      <ContactItem icon={<Mail className="h-5 w-5" />} title="Email" text="hello@cardios.health" />
      <ContactItem icon={<Phone className="h-5 w-5" />} title="Phone" text="+20 155 000 1200" />
      <ContactItem
        icon={<MapPin className="h-5 w-5" />}
        title="Location"
        text="Cairo cardiac innovation lab, remote-ready for clinics and care teams."
      />
    </div>
  );
};

export default ContactInfo;
