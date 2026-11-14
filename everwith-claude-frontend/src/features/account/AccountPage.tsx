import {useEffect, useState} from 'react'
import {LogOut, ShieldAlert} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {openSignIn, setAccount, setLang, setReducedMotion, toast, useApp} from '../../app/store'
import {api, ADAPTER_MODE, REAL_ADAPTER_GAPS} from '../../api/adapter'
import {useAssetUrl} from '../../components/Portrait'
import {PERSONA_AVATARS, PERSONA_AVATAR_LABELS, personaAvatarUrl} from '../../art/generated'
import type {PersonaAvatarId} from '../../art/generated'
import {pick} from '../../lib/util'

export default function AccountPage() {
  const {t, lang} = useI18n()
  const account = useApp(s => s.account)
  const reducedMotion = useApp(s => s.reducedMotion)
  const [name, setName] = useState(account?.persona?.name ?? '')
  const [bio, setBio] = useState(account?.persona?.bio ?? '')
  const [avatar, setAvatar] = useState<string | null>(account?.persona?.avatar ?? null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setName(account?.persona?.name ?? ''); setBio(account?.persona?.bio ?? ''); setAvatar(account?.persona?.avatar ?? null) }, [account?.persona?.name, account?.persona?.bio, account?.persona?.avatar])
  return (
    <div className="ew-page ew-account">
      <header className="ew-page-head"><div><h1>{t('account.title')}</h1></div></header>
      <div className="ew-settings">
        <section className="ew-panel ew-settings-card" aria-labelledby="acc-who">
          <h2 id="acc-who" className="ew-card-title">{account?.authenticated ? t('account.signedIn', {email: account.account!.email}) : t('account.guest')}</h2>
          <p className="ew-muted ew-small">{account?.authenticated ? t('auth.mockNote') : t('account.guestNote')}</p>
          <div className="ew-row wrap">
            {account?.authenticated
              ? <button type="button" className="ew-btn" onClick={async () => setAccount(await api.account.logout())}><LogOut aria-hidden="true" />{t('account.logout')}</button>
              : <button type="button" className="ew-btn primary" onClick={() => openSignIn('auth.action.generic')}>{t('common.signin')}</button>}
          </div>
          <p className="ew-faint ew-small"><ShieldAlert aria-hidden="true" className="ew-inline-icon" /> {t('account.noRecovery')}</p>
        </section>
        <section className="ew-panel ew-settings-card" aria-labelledby="acc-persona">
          <h2 id="acc-persona" className="ew-card-title">{t('account.persona')}</h2>
          <label className="ew-field"><span>{t('account.personaName')}</span><input className="ew-input" value={name} maxLength={40} onChange={e => setName(e.target.value)} /></label>
          <label className="ew-field"><span>{t('account.personaBio')}</span><textarea className="ew-textarea" value={bio} maxLength={400} onChange={e => setBio(e.target.value)} /></label>
          <div className="ew-field">
            <span id="acc-avatar">{t('account.personaAvatar')}</span>
            <div className="ew-avatar-picker" role="group" aria-labelledby="acc-avatar" data-testid="persona-avatars">
              <button type="button" className="ew-avatar-choice is-none" aria-pressed={avatar === null} aria-label={t('account.avatarNone')} title={t('account.avatarNone')} onClick={() => setAvatar(null)}>
                <span aria-hidden="true">{[...(name.trim() || '·')][0]?.toUpperCase()}</span></button>
              {PERSONA_AVATARS.map(id => <AvatarChoice key={id} id={id} label={pick(PERSONA_AVATAR_LABELS[id], lang)} selected={avatar === id} onSelect={() => setAvatar(id)} />)}
            </div>
            <small>{t('account.avatarNote')}</small>
          </div>
          <div><button type="button" className="ew-btn primary" disabled={busy || !name.trim()} onClick={async () => {
            setBusy(true)
            try { setAccount(await api.account.persona(name.trim(), bio.trim(), avatar)); toast(t('account.personaSaved'), 'success') } catch { toast(t('error.generic'), 'error') } finally { setBusy(false) }
          }}>{t('account.personaSave')}</button></div>
        </section>
        <section className="ew-panel ew-settings-card" aria-labelledby="acc-lang">
          <h2 id="acc-lang" className="ew-card-title">{t('account.language')}</h2>
          <div className="ew-row wrap" role="group" aria-labelledby="acc-lang">
            <button type="button" className="ew-btn" aria-pressed={lang === 'zh'} onClick={() => setLang('zh')}>中文</button>
            <button type="button" className="ew-btn" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
          </div>
          <p className="ew-faint ew-small">{t('account.languageNote')}</p>
          <label className="ew-check"><input type="checkbox" checked={reducedMotion} onChange={e => setReducedMotion(e.target.checked)} />{t('account.motion')}</label>
          <p className="ew-faint ew-small">{t('account.motionNote')}</p>
        </section>
        <section className="ew-panel ew-settings-card" aria-labelledby="acc-assets">
          <h2 id="acc-assets" className="ew-card-title">{t('account.assets')}</h2>
          <ul className="ew-gap-list">
            <li>{t('account.assets.package')}</li>
            <li>{t('account.assets.generated')}</li>
          </ul>
        </section>
        <section className="ew-panel ew-settings-card" aria-labelledby="acc-services">
          <h2 id="acc-services" className="ew-card-title">{ADAPTER_MODE === 'mock' ? t('mock.badge.long') : 'Real adapter (not connected)'}</h2>
          <ul className="ew-gap-list">
            {REAL_ADAPTER_GAPS.map(g => <li key={g.area}><strong>{g.area}</strong> — <span className="ew-faint">{g.gap}</span></li>)}
          </ul>
        </section>
      </div>
    </div>
  )
}

function AvatarChoice({id, label, selected, onSelect}: {id: PersonaAvatarId; label: string; selected: boolean; onSelect: () => void}) {
  const url = useAssetUrl(personaAvatarUrl(id))
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  return (
    <button type="button" className="ew-avatar-choice" aria-pressed={selected} aria-label={label} title={label} onClick={onSelect} data-avatar={id}>
      {url && !failed ? <img src={url} alt="" decoding="async" draggable={false} onError={() => setFailed(true)} /> : <span aria-hidden="true">{[...label][0]}</span>}
    </button>
  )
}
