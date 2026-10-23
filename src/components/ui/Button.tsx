import React from 'react';

type ButtonProps = {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  className = '',
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60';
  const variantStyles = {
    primary:
      'bg-emerald-500 text-white shadow-[0_16px_30px_rgba(23,201,121,0.22)] hover:-translate-y-0.5 hover:bg-emerald-600',
    secondary:
      'bg-white text-slate-900 border border-emerald-100 hover:border-emerald-300 hover:bg-emerald-50',
    ghost: 'bg-transparent text-emerald-700 hover:bg-emerald-50',
  };

  return (
    <button className={`${baseStyles} ${variantStyles[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
};

export default Button;
