import React from 'react';
import { AlertTriangle, Info, ShieldAlert } from 'lucide-react';

type NoticeVariant = 'info' | 'caution' | 'limitation' | 'error';

interface ClinicalNoticeProps {
  variant?: NoticeVariant;
  title?: string;
  children: React.ReactNode;
  className?: string;
  compact?: boolean;
}

const variantConfig: Record<NoticeVariant, { icon: typeof Info; border: string; bg: string; text: string; iconColor: string }> = {
  info: {
    icon: Info,
    border: 'border-slate-200',
    bg: 'bg-slate-50',
    text: 'text-slate-600',
    iconColor: 'text-slate-400',
  },
  caution: {
    icon: AlertTriangle,
    border: 'border-amber-200',
    bg: 'bg-amber-50',
    text: 'text-amber-900',
    iconColor: 'text-amber-500',
  },
  limitation: {
    icon: ShieldAlert,
    border: 'border-blue-200',
    bg: 'bg-blue-50',
    text: 'text-blue-900',
    iconColor: 'text-blue-400',
  },
  error: {
    icon: AlertTriangle,
    border: 'border-red-200',
    bg: 'bg-red-50',
    text: 'text-red-700',
    iconColor: 'text-red-500',
  },
};

export default function ClinicalNotice({
  variant = 'info',
  title,
  children,
  className = '',
  compact = false,
}: ClinicalNoticeProps) {
  const config = variantConfig[variant];
  const Icon = config.icon;

  return (
    <div
      role="note"
      className={`flex items-start gap-3 rounded-2xl border ${config.border} ${config.bg} ${compact ? 'px-3 py-2.5' : 'p-4'} text-sm leading-6 ${config.text} ${className}`}
    >
      <Icon className={`mt-0.5 h-4 w-4 flex-shrink-0 ${config.iconColor}`} aria-hidden="true" />
      <div>
        {title && <span className="font-semibold">{title} </span>}
        {children}
      </div>
    </div>
  );
}
