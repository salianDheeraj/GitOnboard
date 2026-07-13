import React from 'react';

const sizeClasses = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
  icon: 'p-2'
};

const variantClasses = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 border border-transparent shadow-sm',
  secondary: 'bg-white text-slate-700 hover:bg-slate-50 border border-slate-300 shadow-sm',
  danger: 'bg-red-600 text-white hover:bg-red-700 border border-transparent shadow-sm',
  ghost: 'bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  soft: 'bg-blue-50 text-blue-700 hover:bg-blue-100 border border-transparent'
};

/**
 * @param {Object} props
 * @param {React.ReactNode} [props.children]
 * @param {string} [props.variant]
 * @param {string} [props.size]
 * @param {string} [props.className]
 * @param {React.ReactNode} [props.icon]
 * @param {React.ReactNode} [props.iconRight]
 * @param {boolean} [props.disabled]
 * @param {function} [props.onClick]
 * @param {string} [props.type]
 */
export function Button({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  className = '', 
  icon, 
  iconRight,
  disabled,
  onClick,
  type = 'button'
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`
        inline-flex items-center justify-center font-medium rounded-lg transition-colors
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        disabled:opacity-50 disabled:cursor-not-allowed
        ${sizeClasses[size]} 
        ${variantClasses[variant]} 
        ${className}
      `}
    >
      {icon && <span className={`${children ? 'mr-2' : ''}`}>{icon}</span>}
      {children}
      {iconRight && <span className="ml-2">{iconRight}</span>}
    </button>
  );
}
