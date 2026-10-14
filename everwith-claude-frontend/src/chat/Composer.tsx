import {useEffect, useId, useLayoutEffect, useRef, useState} from 'react'
import type {FormEvent, RefObject} from 'react'
import {ArrowUp, Asterisk, Square, Zap} from 'lucide-react'
import {RichText} from './RichText'
import {useI18n} from '../app/i18n'

/**
 * Free input is always the primary entry. Enter sends, Shift+Enter breaks lines.
 * IME safety: no send while composing (compositionstart/end, KeyboardEvent.isComposing,
 * keyCode 229) and none for the trailing Enter some platforms deliver right after
 * compositionend. NOTE: verified with synthetic events only; a real macOS Chinese IME
 * pass still has to be done by a person (see ACCEPTANCE.md A04).
 */
export function Composer({value, onChange, onSubmit, onStop, busy = false, disabled = false, canSend = true, maxLength = 2000, label, placeholder, hints, inputRef, describedBy, selection, onSelection, extra}: {
  value: string; onChange: (text: string) => void; onSubmit: (text: string) => void; onStop?: () => void
  busy?: boolean; disabled?: boolean; canSend?: boolean; maxLength?: number; label: string; placeholder: string
  hints?: {title: string; items: string[]; note: string} | null; inputRef?: RefObject<HTMLTextAreaElement | null>; describedBy?: string
  selection?: {start: number; end: number} | null; onSelection?: (s: {start: number; end: number}) => void; extra?: React.ReactNode
}) {
  const {t} = useI18n()
  const own = useRef<HTMLTextAreaElement>(null), ref = inputRef ?? own
  const composing = useRef(false), compositionEnded = useRef(-Infinity)
  const pendingFocus = useRef<(() => void) | null>(null)
  const [hintsOpen, setHintsOpen] = useState(false)
  const [hintChoice, setHintChoice] = useState<string | null>(null)
  const hintId = useId()
  useLayoutEffect(() => () => pendingFocus.current?.(), [])
  // Auto-grow up to a limit, then scroll inside the box.
  useLayoutEffect(() => { const e = ref.current; if (e) { e.style.height = '46px'; e.style.height = `${Math.min(196, Math.max(46, e.scrollHeight))}px` } }, [value, ref])
  // Restore the saved caret/selection once (per mount) without stealing focus.
  const restored = useRef(false)
  useEffect(() => {
    const e = ref.current
    if (!e || restored.current || !selection) return
    restored.current = true
    try { e.setSelectionRange(Math.min(selection.start, value.length), Math.min(selection.end, value.length)) } catch { /* ignore */ }
  }, [selection, value.length, ref])
  const report = () => { const e = ref.current; if (e && onSelection) onSelection({start: e.selectionStart, end: e.selectionEnd}) }
  const submit = (e?: FormEvent) => { e?.preventDefault(); if (!busy && !disabled && canSend && value.trim()) onSubmit(value) }
  const insertStar = () => {
    const e = ref.current; if (!e || disabled) return
    const start = e.selectionStart, end = e.selectionEnd, selected = start !== end
    if (value.length + (selected ? 2 : 1) > maxLength) return
    pendingFocus.current?.()
    const doc = e.ownerDocument, owner = doc.activeElement
    const next = value.slice(0, start) + '*' + value.slice(start, end) + (selected ? '*' : '') + value.slice(end)
    let retired = false, frame: number | undefined
    // Never steal a newer focus choice, never write into an unmounted/hidden box.
    const retire = () => {
      if (retired) return; retired = true; if (frame !== undefined) cancelAnimationFrame(frame)
      doc.removeEventListener('focusin', focus, true); doc.removeEventListener('pointerdown', retire, true)
      doc.removeEventListener('keydown', retire, true); doc.removeEventListener('visibilitychange', visibility)
      if (pendingFocus.current === retire) pendingFocus.current = null
    }
    const focus = (event: FocusEvent) => { if (event.target !== owner && event.target !== doc.body && event.target !== doc.documentElement) retire() }
    const visibility = () => { if (doc.visibilityState === 'hidden') retire() }
    pendingFocus.current = retire
    doc.addEventListener('focusin', focus, true); doc.addEventListener('pointerdown', retire, true)
    doc.addEventListener('keydown', retire, true); doc.addEventListener('visibilitychange', visibility)
    onChange(next)
    frame = requestAnimationFrame(() => {
      if (retired) return
      const current = doc.activeElement
      const valid = ref.current === e && e.isConnected && !e.disabled && e.value === next && doc.visibilityState !== 'hidden'
        && !e.closest('[hidden],[inert],[aria-hidden="true"],dialog:not([open])') && (current === owner || current === doc.body || current === doc.documentElement)
      retire()
      if (valid) { e.focus({preventScroll: true}); e.setSelectionRange(start + 1, selected ? end + 1 : start + 1); report() }
    })
  }
  const applyHint = (hint: string, mode: 'use' | 'keep') => {
    setHintChoice(null); setHintsOpen(false)
    if (mode === 'use') onChange(hint.slice(0, maxLength))
    requestAnimationFrame(() => ref.current?.focus())
  }
  return (
    <div className="ew-composer-wrap">
      {hints && hintsOpen && (
        <section className="ew-hints" id={hintId} aria-label={hints.title}>
          <header><span>{hints.title}</span><button type="button" className="ew-btn ghost small" onClick={() => { setHintsOpen(false); setHintChoice(null) }}>{t('common.close')}</button></header>
          {hintChoice ? (
            <div className="ew-hint-confirm" role="group" aria-label={t('chat.draftExists')}>
              <p>{t('chat.draftExists')}</p>
              <div className="ew-row wrap">
                <button type="button" className="ew-btn small" onClick={() => applyHint(hintChoice, 'keep')}>{t('chat.keepDraft')}</button>
                <button type="button" className="ew-btn small primary" onClick={() => applyHint(hintChoice, 'use')}>{t('chat.useHint')}</button>
              </div>
            </div>
          ) : hints.items.map(h => (
            <button type="button" className="ew-hint" key={h} disabled={disabled} onClick={() => value.trim() ? setHintChoice(h) : applyHint(h, 'use')}><RichText text={h} /></button>
          ))}
          <small>{hints.note}</small>
        </section>
      )}
      <form className="ew-composer" onSubmit={submit}>
        {hints && <button type="button" className="ew-icon-btn ew-hints-toggle" aria-expanded={hintsOpen} aria-controls={hintId} aria-label={t('chat.hints')} title={t('chat.hints')} disabled={disabled} onPointerDown={e => e.preventDefault()} onClick={() => setHintsOpen(v => !v)}><Zap aria-hidden="true" /></button>}
        <div className="ew-input-pill">
          <textarea ref={ref} rows={1} value={value} maxLength={maxLength} disabled={disabled} aria-label={label} aria-describedby={describedBy} placeholder={placeholder}
            onChange={e => { onChange(e.target.value); report() }} onSelect={report} onKeyUp={report} onBlur={report}
            onCompositionStart={() => { composing.current = true }}
            onCompositionEnd={() => { composing.current = false; compositionEnded.current = performance.now() }}
            onKeyDown={e => {
              if (e.key !== 'Enter' || e.shiftKey) return
              const native = e.nativeEvent
              // Selection Enter inside an IME, or its trailing echo, must never send.
              if (composing.current || native.isComposing || native.keyCode === 229 || performance.now() - compositionEnded.current < 40) return
              e.preventDefault(); submit()
            }} />
          <button type="button" className="ew-icon-btn ew-star" disabled={disabled || value.length >= maxLength} title={t('chat.asterisk')} aria-label={t('chat.asterisk')} onPointerDown={e => e.preventDefault()} onClick={insertStar}><Asterisk aria-hidden="true" /></button>
        </div>
        {extra}
        {/* Send turns into Stop in the same spot: the second click of a double-click
            (event.detail 2) must not stop the message that the first click just sent. */}
        {busy && onStop
          ? <button type="button" className="ew-send is-stop" onClick={e => { if (e.detail > 1) return; onStop() }} aria-label={t('common.stop')} title={t('common.stop')}><Square aria-hidden="true" /></button>
          : <button type="submit" className="ew-send" aria-label={t('common.send')} title={t('common.send')} disabled={disabled || busy || !canSend || !value.trim()}><ArrowUp aria-hidden="true" /></button>}
      </form>
      <div className="ew-composer-count" aria-hidden="true">{value.length > maxLength * .8 ? `${value.length} / ${maxLength}` : ''}</div>
    </div>
  )
}
