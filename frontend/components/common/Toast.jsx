import React, { useEffect } from 'react';
import { AlertTriangle, CheckCircle2, X } from 'lucide-react';

const VARIANT_STYLE = {
  error: {
    bg: 'bg-red-50 dark:bg-red-950/80',
    border: 'border-red-200 dark:border-red-900',
    text: 'text-red-700 dark:text-red-300',
    Icon: AlertTriangle,
  },
  success: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/80',
    border: 'border-emerald-200 dark:border-emerald-900',
    text: 'text-emerald-700 dark:text-emerald-300',
    Icon: CheckCircle2,
  },
};

/**
 * Minimal, self-dismissing transient message — not a notification center.
 * Each page owns a single `message` string in its own state and renders one
 * of these; there's no shared queue or provider.
 *
 * @param {Object} props
 * @param {string|null} props.message
 * @param {'error'|'success'} [props.variant]
 * @param {function} props.onDismiss
 * @param {number} [props.duration] - ms before auto-dismiss
 */
export function Toast({ message, variant = 'error', onDismiss, duration = 6000 }) {
  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onDismiss]);

  if (!message) return null;

  const style = VARIANT_STYLE[variant] || VARIANT_STYLE.error;
  const Icon = style.Icon;

  return (
    <div className="fixed bottom-4 right-4 z-[100] max-w-sm w-full pointer-events-none">
      <div
        role="alert"
        className={`pointer-events-auto flex items-start gap-2.5 p-3.5 rounded-lg border shadow-lg ${style.bg} ${style.border} ${style.text}`}
      >
        <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <p className="text-sm flex-1 break-words">{message}</p>
        <button
          onClick={onDismiss}
          aria-label="Dismiss message"
          className="flex-shrink-0 p-0.5 rounded hover:bg-black/5 dark:hover:bg-white/10 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
