import {useRef, useState} from 'react'
import type {FormEvent} from 'react'
import {Dialog} from '../../components/Dialog'
import {useI18n} from '../../app/i18n'
import {appStore, refreshFriends, requireSignIn, toast} from '../../app/store'
import {api} from '../../api/adapter'
import {CompanionRequestError} from '../../contracts/companion'
import type {CompanionFriend} from '../../contracts/companion'
import {randomId} from '../../lib/util'

export type FriendSource = {sourceId: string; version: string; sourceName: string; origin?: Record<string, unknown>}

/**
 * Explicit add-friend + naming (F1–F5, F7). One idempotency key per intent, kept across
 * sign-in and retries, so a timeout followed by “confirm” again never creates two.
 * Sign-in happens between naming and creation; the typed name is restored afterwards
 * and the user confirms again (signing in is not consent to create).
 */
export function useAddFriend(onCreated: (friend: CompanionFriend) => void) {
  const [source, setSource] = useState<FriendSource | null>(null)
  const [name, setName] = useState('')
  const [phase, setPhase] = useState<'naming' | 'creating'>('naming')
  const [error, setError] = useState<string | null>(null)
  const key = useRef<string>('')
  const open = (s: FriendSource) => { key.current = randomId('addfr', 10); setSource(s); setName(s.sourceName); setError(null); setPhase('naming') }
  const close = () => { setSource(null); setError(null) }
  const {t} = useI18n()
  const confirm = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!source || phase === 'creating') return
    if (!name.trim()) { setError(t('name.required')); return }
    const pending = source
    if (!appStore.get().account?.authenticated) {
      setSource(null) // one modal layer at a time
      const ok = await requireSignIn('auth.action.friend')
      setSource(pending)
      if (!ok) return
      return // back on the naming step with the same name and key; user confirms again
    }
    setPhase('creating'); setError(null)
    try {
      const account = appStore.get().account!.account!.id
      const friend = await api.friends.add({key: key.current, source_id: pending.sourceId, source_version: pending.version, name: name.trim(), expected_account_id: account, ...(pending.origin ? {origin: pending.origin} : {})})
      await refreshFriends()
      setSource(null)
      toast(`${friend.name} · ${t('character.add')}`, 'success')
      onCreated(friend)
    } catch (err) {
      setPhase('naming')
      const code = err instanceof CompanionRequestError ? err.code : 'network_error'
      setError(code === 'network_error' ? t('error.network') : code === 'auth_session_required' ? t('error.auth') : code === 'role_already_bound' ? t('error.conflict') : t('error.generic'))
    }
  }
  const dialog = source ? (
    <Dialog title={t('name.title')} onClose={close} initialFocus="input">
      <form className="ew-form" onSubmit={confirm}>
        <p className="ew-muted">{t('name.desc', {source: source.sourceName})}</p>
        <label className="ew-field"><span>{t('name.label')}</span>
          <input className="ew-input" value={name} maxLength={40} onChange={e => setName(e.target.value)} aria-invalid={!!error} required /></label>
        {error && <p className="ew-error-text" role="alert">{error}</p>}
        <div className="ew-form-actions">
          <span className="ew-grow" />
          <button type="button" className="ew-btn ghost" onClick={close}>{t('common.cancel')}</button>
          <button type="submit" className="ew-btn primary" disabled={phase === 'creating'}>{phase === 'creating' && <span className="ew-spinner" />}{phase === 'creating' ? t('name.creating') : t('name.confirm')}</button>
        </div>
      </form>
    </Dialog>
  ) : null
  return {open, dialog}
}
