import {useEffect, useMemo, useRef, useState} from 'react'
import {ArrowLeft, Play, Users, BookOpenText} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {useApp} from '../../app/store'
import {api} from '../../api/adapter'
import type {GameJSON} from '../../api/types'
import {CompanionRequestError} from '../../contracts/companion'
import {Portrait} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {personaAvatarUrl} from '../../art/generated'
import {OFFICIAL_CHARACTERS} from '../../mock/catalog'
import {pick, randomId} from '../../lib/util'

type SeatChoice = {kind: 'temporary'; character_id: string} | {kind: 'friend'; friend_id: string; friend_epoch: number}
const ROTATION = ['official-lena', 'official-arthur', 'official-marcus', 'official-nora']

export default function GamePreparePage({gameId, withFriend, from}: {gameId: string; withFriend: string | null; from: string | null}) {
  const {t, lang} = useI18n()
  const friends = useApp(s => s.friends) ?? []
  const account = useApp(s => s.account)
  const [game, setGame] = useState<GameJSON | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [players, setPlayers] = useState(4)
  const [seats, setSeats] = useState<SeatChoice[]>([])
  const [busy, setBusy] = useState<false | 'starting' | 'lookup'>(false)
  const [startError, setStartError] = useState<string | null>(null)
  // One key per preparation intent: double clicks, retries and timeouts reuse it.
  const key = useRef(randomId('gstart', 10))
  const back = from ?? href.discover('games')

  useEffect(() => {
    api.catalog.games().then(r => {
      const g = r.items.find(x => x.id === gameId || x.slug === gameId)
      if (!g) { setError('not_found'); return }
      setGame(g); setPlayers(g.default_players)
    }).catch(() => setError('network_error'))
  }, [gameId])
  useEffect(() => {
    if (!game) return
    setSeats(prev => Array.from({length: players - 1}, (_, i) => {
      if (prev[i]) return prev[i]
      if (i === 0 && withFriend) {
        const f = friends.find(x => x.id === withFriend)
        if (f) return {kind: 'friend', friend_id: f.id, friend_epoch: f.epoch}
      }
      return {kind: 'temporary', character_id: ROTATION[i % ROTATION.length]}
    }))
  }, [game, players, withFriend, friends])

  const seated = useMemo(() => new Set(seats.filter(s => s.kind === 'friend').map(s => (s as {friend_id: string}).friend_id)), [seats])
  const invalid = seats.length !== players - 1 || seats.some((s, i) => s.kind === 'friend' && seats.findIndex(o => o.kind === 'friend' && o.friend_id === s.friend_id) !== i)
  const start = async () => {
    if (!game || busy || invalid) return
    setBusy('starting'); setStartError(null)
    const friend = withFriend ? friends.find(f => f.id === withFriend) : null
    const body = {key: key.current, game_id: game.id, players, profile: game.profile, expected_account_id: account?.account?.id ?? account?.guest_id,
      seats: seats.map((s, i) => ({seat: i + 1, ...s})),
      origin: friend ? {kind: 'friend', friend_id: friend.id, return_hash: back} : {kind: 'discover', return_hash: back}}
    try {
      const view = await api.games.start(body)
      navigate(href.gamePlay(view.id))
    } catch (e) {
      const code = e instanceof CompanionRequestError ? e.code : 'network_error'
      if (code === 'network_error') {
        // Unknown result: look up the original key before anything else.
        setBusy('lookup')
        try { const view = await api.games.lookup(key.current); navigate(href.gamePlay(view.id)); return }
        catch { setStartError(t('error.network')) }
      } else setStartError(code === 'friend_epoch_changed' || code === 'friend_unavailable' ? t('error.conflict') : t('error.generic'))
      setBusy(false)
    }
  }
  if (error) return <div className="ew-page"><a className="ew-back ew-btn ghost" href={back}><ArrowLeft aria-hidden="true" />{t('common.back')}</a><div className="ew-empty"><SpotArt kind="not-found" /><h2>{t('error.notFound')}</h2></div></div>
  if (!game) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>
  return (
    <div className="ew-page ew-prepare">
      <a className="ew-back ew-btn ghost" href={back}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className="ew-prepare-layout">
        <section className="ew-prepare-main" aria-labelledby="prep-title">
          <p className="ew-eyebrow">{t('game.prepare')}</p>
          <h1 id="prep-title" className="ew-title-xl">{game.name}</h1>
          <p className="ew-lead">{pick(game.description, lang)}</p>
          <div className="ew-prepare-block">
            <h2 className="ew-section-title">{t('game.profile')}</h2>
            <p><span className="ew-chip">{pick(game.profile_label, lang)}</span> <code className="ew-code">{game.profile}</code></p>
            <ul className="ew-rules">{game.rule_notes.map((n, i) => <li key={i}>{pick(n, lang)}</li>)}</ul>
          </div>
          <div className="ew-prepare-block">
            <h2 className="ew-section-title" id="players-label">{t('game.players')}</h2>
            <div className="ew-row wrap" role="group" aria-labelledby="players-label">
              {game.players.map(n => <button key={n} type="button" className="ew-btn small" aria-pressed={players === n} onClick={() => setPlayers(n)}>{n} {t('common.players')}</button>)}
            </div>
          </div>
          <div className="ew-prepare-block">
            <h2 className="ew-section-title">{t('game.seats')}</h2>
            <ol className="ew-seat-list">
              <li className="ew-seat-row"><span className="ew-seat-no">0</span><span className="ew-avatar"><Portrait src={personaAvatarUrl(account?.persona?.avatar)} name={account?.persona?.name || t('common.you')} /></span><strong>{t('game.you')}</strong></li>
              {seats.map((s, i) => {
                const f = s.kind === 'friend' ? friends.find(x => x.id === s.friend_id) : null
                const ch = s.kind === 'temporary' ? OFFICIAL_CHARACTERS.find(c => c.id === s.character_id)! : null
                return (
                  <li key={i} className="ew-seat-row">
                    <span className="ew-seat-no">{i + 1}</span>
                    <span className="ew-avatar"><Portrait src={f?.avatar ?? ch?.avatar} name={f?.name ?? ch?.name ?? '?'} position="50% 14%" /></span>
                    <span className="ew-seat-name"><strong>{f?.name ?? ch?.name}</strong>
                      <span className={`ew-chip ${s.kind === 'friend' ? 'friend' : 'temp'}`}>{s.kind === 'friend' ? t('common.friend') : t('common.temporary')}</span></span>
                    <label className="ew-seat-select">
                      <span className="ew-sr">{t('game.seat', {n: i + 1})}</span>
                      <select className="ew-select" value={s.kind === 'friend' ? `f:${s.friend_id}` : `t:${s.character_id}`} onChange={e => {
                        const v = e.target.value
                        setSeats(prev => prev.map((x, j) => j !== i ? x : v.startsWith('f:') ? (() => { const fr = friends.find(q => q.id === v.slice(2))!; return {kind: 'friend' as const, friend_id: fr.id, friend_epoch: fr.epoch} })() : {kind: 'temporary' as const, character_id: v.slice(2)}))
                      }}>
                        <optgroup label={t('game.defaultLineup')}>
                          {OFFICIAL_CHARACTERS.map(c => <option key={c.id} value={`t:${c.id}`}>{c.name} · {t('common.temporary')}</option>)}
                        </optgroup>
                        {friends.length > 0 && <optgroup label={t('game.useFriend')}>
                          {friends.map(fr => <option key={fr.id} value={`f:${fr.id}`} disabled={seated.has(fr.id) && !(s.kind === 'friend' && s.friend_id === fr.id)}>{fr.name} · {fr.source_name} #{fr.display_number}{seated.has(fr.id) && !(s.kind === 'friend' && s.friend_id === fr.id) ? ` (${t('game.friendSeated')})` : ''}</option>)}
                        </optgroup>}
                      </select>
                    </label>
                  </li>
                )
              })}
            </ol>
            {!account?.authenticated && <p className="ew-faint ew-small"><Users aria-hidden="true" className="ew-inline-icon" /> {t('friends.guest')}</p>}
          </div>
        </section>
        <aside className="ew-prepare-side">
          <div className="ew-prepare-poster"><Portrait src={game.poster} name={game.name} /></div>
          <div className="ew-notice mock"><BookOpenText aria-hidden="true" /><span>{t('game.ruleSimulatedNote')}</span></div>
          <p className="ew-faint ew-small">{t('game.noRecord')}</p>
          {startError && <div className="ew-notice danger" role="alert">{startError}</div>}
          <button type="button" className="ew-btn primary wide ew-start-btn" disabled={!!busy || invalid} onClick={() => void start()}>
            {busy ? <span className="ew-spinner" /> : <Play aria-hidden="true" />}{busy === 'lookup' ? t('game.lookup') : busy ? t('game.starting') : t('game.start')}</button>
        </aside>
      </div>
    </div>
  )
}
