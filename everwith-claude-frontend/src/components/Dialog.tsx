import {useEffect, useId, useRef} from 'react'
import type {ReactNode} from 'react'
import {X} from 'lucide-react'
import {useModalFocusReturn} from './use-modal-focus-return'
import {useI18n} from '../app/i18n'

let lastFullscreenExit = 0
if (typeof document !== 'undefined') document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) lastFullscreenExit = performance.now() })

/**
 * One modal layer at a time. Esc order: while the page is fullscreen, the first Esc
 * belongs to the browser (exit fullscreen); only a later Esc closes this dialog.
 * Focus returns to the opener (or the nearest sensible control) on close.
 */
export function Dialog({title, children, onClose, footer, wide = false, initialFocus, dismissible = true, className = ''}: {
  title: string; children: ReactNode; onClose: () => void; footer?: ReactNode; wide?: boolean; initialFocus?: string; dismissible?: boolean; className?: string
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  const {t} = useI18n()
  useModalFocusReturn(ref, {initialFocusSelector: initialFocus})
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    const cancel = (event: Event) => {
      event.preventDefault()
      if (!dismissible) return
      if (document.fullscreenElement || performance.now() - lastFullscreenExit < 300) return
      onClose()
    }
    dialog.addEventListener('cancel', cancel)
    return () => dialog.removeEventListener('cancel', cancel)
  }, [onClose, dismissible])
  return (
    <dialog ref={ref} className={`ew-dialog ${wide ? 'is-wide' : ''} ${className}`} aria-labelledby={`${id}-title`}
      onMouseDown={e => { if (dismissible && e.target === ref.current) onClose() }}>
      <div className="ew-dialog-panel">
        <header className="ew-dialog-head">
          <h2 id={`${id}-title`}>{title}</h2>
          {dismissible && <button type="button" className="ew-icon-btn" aria-label={t('common.close')} title={t('common.close')} onClick={onClose}><X size={20} aria-hidden="true" /></button>}
        </header>
        <div className="ew-dialog-body">{children}</div>
        {footer && <footer className="ew-dialog-foot">{footer}</footer>}
      </div>
    </dialog>
  )
}

export function ConfirmDialog({title, body, confirmLabel, danger = false, onConfirm, onCancel, busy = false}: {
  title: string; body: ReactNode; confirmLabel: string; danger?: boolean; onConfirm: () => void; onCancel: () => void; busy?: boolean
}) {
  const {t} = useI18n()
  return (
    <Dialog title={title} onClose={onCancel} initialFocus="[data-autofocus]" footer={<>
      <button type="button" className="ew-btn ghost" onClick={onCancel} data-autofocus>{t('common.cancel')}</button>
      <button type="button" className={`ew-btn ${danger ? 'danger' : 'primary'}`} disabled={busy} onClick={onConfirm}>{confirmLabel}</button>
    </>}>
      <div className="ew-prose">{body}</div>
    </Dialog>
  )
}
