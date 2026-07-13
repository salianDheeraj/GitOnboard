import React from 'react';

const variantClasses = {
  success: 'bg-green-50 text-green-700 border-green-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  error: 'bg-red-50 text-red-700 border-red-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
  neutral: 'bg-slate-50 text-slate-700 border-slate-200',
  outline: 'bg-transparent text-slate-600 border-slate-300'
};

/**
 * @param {Object} props
 * @param {React.ReactNode} [props.children]
 * @param {string} [props.variant]
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.icon]
 */
export function Badge({ children, variant = 'neutral', className = '', icon }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${variantClasses[variant]} ${className}`}>
      {icon && <span className="mr-1.5 flex-shrink-0">{icon}</span>}
      {children}
    </span>
  );
}
