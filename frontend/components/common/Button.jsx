import React from 'react';

const sizeClasses = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
  icon: 'p-2'
};

const variantClasses = {
  primary: 'bg-blue-600 dark:bg-blue-600 workspace:bg-workspace-accent text-white hover:bg-blue-700 dark:hover:bg-blue-500 workspace:hover:bg-workspace-accent/80 border border-transparent shadow-sm',
  secondary: 'bg-white dark:bg-slate-800 workspace:bg-workspace-surface text-slate-700 dark:text-slate-200 workspace:text-workspace-text hover:bg-slate-50 dark:hover:bg-slate-700 workspace:hover:bg-workspace-surface-raised border border-slate-300 dark:border-slate-700 workspace:border-workspace-border shadow-sm',
  danger: 'bg-red-600 dark:bg-red-600 text-white hover:bg-red-700 dark:hover:bg-red-500 border border-transparent shadow-sm',
  ghost: 'bg-transparent text-slate-600 dark:text-slate-400 workspace:text-workspace-text-muted hover:bg-slate-100 dark:hover:bg-slate-800 workspace:hover:bg-workspace-surface-raised hover:text-slate-900 dark:hover:text-slate-100 workspace:hover:text-workspace-text',
  soft: 'bg-blue-50 dark:bg-blue-950/60 workspace:bg-workspace-accent/10 text-blue-700 dark:text-blue-400 workspace:text-workspace-accent hover:bg-blue-100 dark:hover:bg-blue-900/60 workspace:hover:bg-workspace-accent/20 border border-transparent'
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
 * @param {string} [props.title]
 * @param {string} [props['aria-label']]
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
  type = 'button',
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`
        inline-flex items-center justify-center font-medium rounded-lg transition-colors
        focus:outline-none focus:ring-2 focus:ring-blue-500 workspace:focus:ring-workspace-accent focus:ring-offset-2 dark:focus:ring-offset-slate-900 workspace:focus:ring-offset-workspace-bg
        disabled:opacity-50 disabled:cursor-not-allowed
        ${sizeClasses[size]}
        ${variantClasses[variant]}
        ${className}
      `}
      {...rest}
    >
      {icon && <span className={`${children ? 'mr-2' : ''}`}>{icon}</span>}
      {children}
      {iconRight && <span className="ml-2">{iconRight}</span>}
    </button>
  );
}
