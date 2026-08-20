import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';

/**
 * Reusable in-app confirmation dialog, styled to match the GitOnboard modal
 * system. Intended for destructive/irreversible actions (repository
 * deletion, etc.) in place of the browser's native window.confirm().
 *
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {function} props.onClose - Called on Cancel, Escape, backdrop click, or the header close button. No-op while isLoading.
 * @param {function} props.onConfirm
 * @param {string} props.title
 * @param {React.ReactNode} props.message - Primary confirmation question, e.g. `Are you sure you want to delete "${repoName}"?`
 * @param {React.ReactNode} [props.description] - Secondary explanatory text.
 * @param {string} [props.confirmLabel]
 * @param {string} [props.cancelLabel]
 * @param {string} [props.loadingLabel]
 * @param {boolean} [props.isLoading]
 * @param {string} [props.error]
 * @param {'danger'|'default'} [props.variant]
 */
export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  loadingLabel,
  isLoading = false,
  error,
  variant = 'danger',
}) {
  // Deletion is destructive: while it's in flight, Escape/backdrop/header-X
  // must not silently abandon the modal mid-request.
  const handleClose = () => {
    if (!isLoading) onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      hideCloseButton={isLoading}
      title={title}
      titleIcon={
        <AlertTriangle
          className={`w-5 h-5 flex-shrink-0 ${variant === 'danger' ? 'text-red-500 dark:text-red-400' : 'text-amber-500 dark:text-amber-400'}`}
          aria-hidden="true"
        />
      }
    >
      <div className="space-y-4">
        {message && <p className="text-slate-700 dark:text-slate-200 break-words">{message}</p>}
        {description && (
          <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
        )}

        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 rounded-lg border border-red-100 dark:border-red-900 text-sm flex items-start gap-2">
            <span className="font-bold mt-0.5">!</span>
            <p className="break-words">{error}</p>
          </div>
        )}

        <div className="pt-2 flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
            data-autofocus
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" aria-hidden="true" />
                {loadingLabel || `${confirmLabel}...`}
              </span>
            ) : (
              confirmLabel
            )}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
