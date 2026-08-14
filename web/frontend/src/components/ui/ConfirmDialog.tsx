import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect } from 'react'

export type ConfirmTone = 'danger' | 'primary'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  /** Body copy. Keep it specific about what is about to happen. */
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** `danger` for destructive actions, `primary` for ordinary ones. */
  tone?: ConfirmTone
  /** Shows a spinner and blocks input while the action runs. */
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

const TONES: Record<ConfirmTone, { confirm: string; icon: string }> = {
  danger: {
    confirm:
      'bg-red-600 text-white hover:bg-red-700 shadow-lg shadow-red-500/25 focus-visible:outline-red-600',
    icon: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
  },
  primary: {
    confirm:
      'bg-primary-600 text-white hover:bg-primary-700 shadow-lg shadow-primary-500/25 focus-visible:outline-primary-600',
    icon: 'bg-primary-50 text-primary-600 dark:bg-primary-500/10 dark:text-primary-400',
  },
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'primary',
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, busy, onCancel])

  const toneStyles = TONES[tone]

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-end justify-center bg-black/70 backdrop-blur-sm sm:items-center sm:p-4"
          onClick={() => { if (!busy) onCancel() }}
          role="presentation"
        >
          <motion.div
            initial={{ y: 40, opacity: 0, scale: 0.98 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 40, opacity: 0, scale: 0.98 }}
            transition={{ type: 'spring', damping: 26, stiffness: 320 }}
            onClick={e => e.stopPropagation()}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-message"
            className="w-full max-w-md overflow-hidden rounded-t-2xl bg-white shadow-2xl dark:bg-[#0F172A] sm:rounded-2xl"
          >
            <div className="flex items-start gap-4 p-5 sm:p-6">
              <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${toneStyles.icon}`}>
                <AlertTriangle size={20} />
              </div>
              <div className="min-w-0 flex-1">
                <h2
                  id="confirm-dialog-title"
                  className="text-base font-bold text-neutral-900 dark:text-white"
                >
                  {title}
                </h2>
                <div
                  id="confirm-dialog-message"
                  className="mt-1.5 text-[13px] leading-relaxed text-neutral-600 dark:text-neutral-400"
                >
                  {message}
                </div>
              </div>
              <button
                onClick={onCancel}
                disabled={busy}
                aria-label="Close"
                className="-mr-1 -mt-1 shrink-0 rounded-lg p-1.5 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 disabled:opacity-50 dark:hover:bg-white/10 dark:hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-neutral-200 bg-neutral-50 px-5 py-4 dark:border-white/10 dark:bg-white/5 sm:flex-row sm:justify-end sm:px-6">
              <button
                onClick={onCancel}
                disabled={busy}
                className="rounded-xl px-4 py-2.5 text-sm font-bold text-neutral-600 transition-colors hover:bg-neutral-200 disabled:opacity-50 dark:text-neutral-300 dark:hover:bg-white/10"
              >
                {cancelLabel}
              </button>
              <button
                onClick={onConfirm}
                disabled={busy}
                autoFocus
                className={`flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${toneStyles.confirm}`}
              >
                {busy && (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                )}
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
