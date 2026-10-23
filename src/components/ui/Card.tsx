import React from 'react';

type CardProps = {
  children: React.ReactNode;
  className?: string;
};

const Card: React.FC<CardProps> = ({ children, className = '' }) => {
  return <div className={`cardios-shell rounded-[28px] p-6 ${className}`}>{children}</div>;
};

export default Card;
