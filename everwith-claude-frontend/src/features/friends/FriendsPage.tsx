import {useState} from 'react'
import {MessageCircle, Gamepad2, Search, Compass, PenLine} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href} from '../../app/router'
import {openSignIn, refreshFriends, useApp} from '../../app/store'
import {Portrait} from '../../components/Portrait'
import {SpotArt, StageBackdrop} from '../../components/Art'
import {backdropFor} from '../../art/generated'
import {characterFor} from '../../live2d/characters'
import {PlayTogetherDialog} from './PlayTogether'
import type {CompanionFriend} from '../../contracts/companion'
import {formatTime, pick} from '../../lib/util'

export default function FriendsPage() {
  const {t, lang} = useI18n()
  const account = useApp(s => s.account)
  const friends = useApp(s => s.friends)
  const error = useApp(s => s.friendsError)
  const [query, setQuery] = useState('')
  const [playWith, setPlayWith] = useState<CompanionFriend | null>(null)
  const list = (friends ?? []).filter(f => !query.trim() || `${f.name} ${f.source_name}`.toLowerCase().includes(query.trim().toLowerCase()))
  return (
    <div className="ew-page ew-friends">
      <header className="ew-page-head">
        <div><h1>{t('friends.title')}</h1><p className="ew-muted">{t('friends.subtitle')}</p></div>
        {!!friends?.length && <label className="ew-search"><Search aria-hidden="true" /><input className="ew-input" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={t('friends.search')} aria-label={t('friends.search')} /></label>}
      </header>
      {account && !account.authenticated && (
        <div className="ew-empty">
          <SpotArt kind="signin" />
          <h2>{t('friends.guest')}</h2>
          <p>{t('account.guestNote')}</p>
          <div className="ew-row wrap center">
            <button type="button" className="ew-btn primary" onClick={() => openSignIn('auth.action.friend')}>{t('common.signin')}</button>
            <a className="ew-btn" href={href.discover()}><Compass aria-hidden="true" />{t('nav.discover')}</a>
          </div>
        </div>
      )}
      {account?.authenticated && error && <div className="ew-notice danger" role="alert"><span>{t('error.generic')}</span><button className="ew-btn small" type="button" onClick={() => void refreshFriends()}>{t('common.retry')}</button></div>}
      {account?.authenticated && friends === null && !error && <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>}
      {account?.authenticated && friends && friends.length === 0 && (
        <div className="ew-empty">
          <SpotArt kind="friends" />
          <h2>{t('friends.empty')}</h2><p>{t('friends.emptyHint')}</p>
          <div className="ew-row wrap center">
            <a className="ew-btn primary" href={href.discover()}><Compass aria-hidden="true" />{t('nav.discover')}</a>
            <a className="ew-btn" href={href.create()}><PenLine aria-hidden="true" />{t('nav.create')}</a>
          </div>
        </div>
      )}
      {list.length > 0 && (
        <ul className="ew-friend-grid" aria-label={t('friends.title')}>
          {list.map(f => (
            <li key={f.id} className="ew-friend-card">
              <a className="ew-friend-main" href={href.chat(f.id)}>
                <span className="ew-friend-face"><StageBackdrop src={backdropFor(characterFor(f.source_id, f.source_version)?.key)} /><Portrait src={f.avatar} name={f.name} position="50% 14%" /></span>
                <span className="ew-friend-text">
                  <strong className="ew-friend-name">{f.name}</strong>
                  <small>{t('friends.source', {name: f.source_name})} · {t('friends.number', {n: f.display_number})}</small>
                  <small className="ew-faint">{t('friends.since', {date: formatTime(f.created_at, lang)})} · {pick(f.origin.label, lang)}</small>
                </span>
              </a>
              <div className="ew-friend-actions">
                <a className="ew-btn small primary" href={href.chat(f.id)}><MessageCircle aria-hidden="true" />{t('friends.chat')}</a>
                <button type="button" className="ew-btn small" onClick={() => setPlayWith(f)}><Gamepad2 aria-hidden="true" />{t('friends.play')}</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {playWith && <PlayTogetherDialog friend={playWith} from={href.friends()} onClose={() => setPlayWith(null)} />}
    </div>
  )
}
