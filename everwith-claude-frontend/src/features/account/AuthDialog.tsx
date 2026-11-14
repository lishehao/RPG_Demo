import {useState} from 'react'
import type {FormEvent} from 'react'
import {Dialog} from '../../components/Dialog'
import {SpotArt} from '../../components/Art'
import {useI18n} from '../../app/i18n'
import type {I18nKey} from '../../app/i18n'
import {resolveAuth, setAccount, useApp} from '../../app/store'
import {api} from '../../api/adapter'
import {CompanionRequestError} from '../../contracts/companion'

/**
 * Sign-in gate. Cancel resolves `false` and leaves the caller exactly where it was
 * (inputs and trial play untouched). Success resolves `true`; the caller then asks
 * for any remaining confirmation — signing in never auto-runs the protected action.
 */
export function AuthDialog() {
  const prompt = useApp(s => s.authPrompt)
  if (!prompt) return null
  return <AuthForm key={prompt.id} action={prompt.action} />
}
function AuthForm({action}: {action: I18nKey}) {
  const {t} = useI18n()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try {
      const session = mode === 'login' ? await api.account.login(email, password) : await api.account.register(email, password)
      setAccount(session)
      resolveAuth(true)
    } catch (err) {
      const code = err instanceof CompanionRequestError ? err.code : 'network_error'
      const key = `auth.error.${code}` as I18nKey
      setError(t(key) !== key ? t(key) : t('error.generic'))
    } finally { setBusy(false) }
  }
  return (
    <Dialog title={t(mode === 'login' ? 'auth.title.login' : 'auth.title.register')} onClose={() => resolveAuth(false)} initialFocus="input[type=email]">
      <form className="ew-form" onSubmit={submit} noValidate>
        <div className="ew-auth-why"><SpotArt kind="signin" className="small" /><p className="ew-muted">{t('auth.why', {action: t(action)})}</p></div>
        <label className="ew-field"><span>{t('auth.email')}</span>
          <input className="ew-input" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required aria-invalid={!!error} /></label>
        <label className="ew-field"><span>{t('auth.password')}</span>
          <input className="ew-input" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} required minLength={8} aria-invalid={!!error} aria-describedby="auth-pw-hint" />
          <small id="auth-pw-hint">{t('auth.passwordHint')}</small></label>
        {error && <p className="ew-error-text" role="alert">{error}</p>}
        <div className="ew-notice mock"><span>{t('auth.mockNote')}</span></div>
        <div className="ew-form-actions">
          <button type="button" className="ew-link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>{t(mode === 'login' ? 'auth.switchRegister' : 'auth.switchLogin')}</button>
          <span className="ew-grow" />
          <button type="button" className="ew-btn ghost" onClick={() => resolveAuth(false)}>{t('common.cancel')}</button>
          <button type="submit" className="ew-btn primary" disabled={busy || !email || !password}>{busy && <span className="ew-spinner" />}{t(mode === 'login' ? 'auth.submit.login' : 'auth.submit.register')}</button>
        </div>
      </form>
    </Dialog>
  )
}
