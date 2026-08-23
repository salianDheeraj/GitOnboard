import React, { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';

/**
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {function} props.onClose
 * @param {string} props.title
 * @param {React.ReactNode} [props.titleIcon]
 * @param {boolean} [props.hideCloseButton]
 * @param {'light'|'dark'} [props.variant] - 'dark' renders the workspace (IDE) dark surface regardless of the app theme.
 * @param {React.ReactNode} [props.children]
 */
export function Modal({ isOpen, onClose, title, titleIcon, hideCloseButton = false, variant = 'light', children }) {
  const panelRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const [entered, setEntered] = useState(false);
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen);

  // Reset the enter transition when the dialog closes, so it replays next
  // time it opens (this component instance persists across isOpen toggles —
  // it doesn't unmount, it just renders null). Adjusting state during render
  // in response to a prop change, rather than in an effect body, avoids an
  // extra cascading render pass.
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (!isOpen) setEntered(false);
  }

  // Prevent scrolling when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = 'unset';
      };
    } else {
      document.body.style.overflow = 'unset';
    }
  }, [isOpen]);

  // Escape-to-close + focus management: move focus into the dialog when it
  // opens, restore it to whatever triggered the dialog when it closes.
  useEffect(() => {
    if (!isOpen) return;

    previouslyFocusedRef.current = document.activeElement;

    // If something inside the panel already claimed focus (e.g. a native
    // autoFocus input), leave it alone. Otherwise focus an explicit
    // [data-autofocus] target, falling back to the panel itself.
    const alreadyFocusedInside = panelRef.current?.contains(document.activeElement);
    if (!alreadyFocusedInside) {
      const target = panelRef.current?.querySelector('[data-autofocus]');
      (target || panelRef.current)?.focus();
    }

    const raf = requestAnimationFrame(() => setEntered(true));

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose?.();
      }
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', handleKeyDown);
      if (previouslyFocusedRef.current && typeof previouslyFocusedRef.current.focus === 'function') {
        previouslyFocusedRef.current.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isDark = variant === 'dark';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className={`fixed inset-0 bg-slate-900/40 dark:bg-slate-950/70 backdrop-blur-sm transition-opacity duration-150 ${entered ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gitonboard-modal-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={`rounded-xl shadow-xl w-[calc(100%-2rem)] max-w-md z-10 overflow-hidden m-4 flex flex-col transition-all duration-150 ease-out focus:outline-none ${
          isDark
            ? 'bg-workspace-surface text-workspace-text border border-workspace-border'
            : 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-slate-800'
        } ${entered ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}
      >
        <div
          className={`flex items-center justify-between px-6 py-4 border-b ${
            isDark
              ? 'border-workspace-border bg-workspace-surface-raised/50'
              : 'border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50'
          }`}
        >
          <h3
            id="gitonboard-modal-title"
            className={`font-semibold text-lg flex items-center gap-2 ${isDark ? 'text-workspace-text' : 'text-slate-800 dark:text-slate-100'}`}
          >
            {titleIcon}
            {title}
          </h3>
          {!hideCloseButton && (
            <button
              onClick={onClose}
              aria-label="Close dialog"
              className={`transition-colors p-1 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                isDark
                  ? 'text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface-raised'
                  : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-slate-700/50'
              }`}
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );
}
