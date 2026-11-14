import {useApp} from '../app/store'

export function Toasts() {
  const toasts = useApp(s => s.toasts)
  return (
    <div className="ew-toasts" role="status" aria-live="polite">
      {toasts.map(t => <div key={t.id} className={`ew-toast ${t.kind}`}>{t.text}</div>)}
    </div>
  )
}
