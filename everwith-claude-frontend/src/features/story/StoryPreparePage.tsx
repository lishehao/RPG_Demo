import {useEffect, useMemo, useRef, useState} from 'react'
import {ArrowLeft, Lock, Play, Users} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {refreshFriends, useApp} from '../../app/store'
import {api} from '../../api/adapter'
import type {StoryJSON} from '../../api/types'
import {CompanionRequestError} from '../../contracts/companion'
import {Portrait} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {errorArt} from '../../art/generated'
import {pick, randomId} from '../../lib/util'

const MAX_AI = 10
type Choice = {role_id: string; friend_id: string; friend_epoch: number}

/**
 * Story setup: player identity, original cast, optional friend casting. Nothing is created
 * until “Start this run”; one idempotency key per preparation (double click / retry safe).
 * The server re-checks seats, locks, the 10-AI limit, one-role-per-friend and epochs.
 */
export default function StoryPreparePage({storyId, version, withFriend, from}: {storyId: string; version: string; withFriend: string | null; from: string | null}) {
  const {t, lang} = useI18n()
  const friends = useApp(s => s.friends) ?? []
  const account = useApp(s => s.account)
  const [story, setStory] = useState<StoryJSON | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cast, setCast] = useState<Choice[]>([])
  const [busy, setBusy] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const key = useRef(randomId('sstart', 10))
  const seededFriend = useRef(false)
  const back = from ?? href.story(storyId, version)

  useEffect(() => { void refreshFriends() }, [])
  useEffect(() => {
    api.catalog.story(storyId, version).then(setStory).catch(e => setError(e instanceof CompanionRequestError ? e.code : 'network_error'))
  }, [storyId, version])
  // “一起玩” from a friend: put them in the first open, replaceable role (still editable).
  useEffect(() => {
    if (!story || !withFriend || seededFriend.current) return
    const f = friends.find(x => x.id === withFriend)
    const role = story.roles.find(r => r.replaceable && !r.locked)
    if (f && role) { seededFriend.current = true; setCast([{role_id: role.id, friend_id: f.id, friend_epoch: f.epoch}]) }
  }, [story, withFriend, friends])

  const used = useMemo(() => new Map(cast.map(c => [c.friend_id, c.role_id])), [cast])
  if (error) return <div className="ew-page"><a className="ew-back ew-btn ghost" href={back}><ArrowLeft aria-hidden="true" />{t('common.back')}</a><div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : t('error.generic')}</h2></div></div>
  if (!story) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>
  const aiCount = story.roles.length
  const invalid = aiCount > MAX_AI || cast.some(c => story.roles.find(r => r.id === c.role_id)?.locked) || new Set(cast.map(c => c.friend_id)).size !== cast.length

  const start = async () => {
    if (busy || invalid) return
    setBusy(true); setStartError(null)
    try {
      const session = await api.stories.start({key: key.current, story_id: story.id, version: story.version, cast, language: lang, expected_account_id: account?.account?.id ?? account?.guest_id ?? ''})
      navigate(href.storyPlay(session.id), {replace: true})
    } catch (e) {
      const code = e instanceof CompanionRequestError ? e.code : 'network_error'
      // Same key on retry: the server returns the run it may already have created.
      setStartError(code === 'network_error' ? t('story.startUnknown') : code === 'friend_epoch_changed' || code === 'friend_unavailable' ? t('error.conflict') : t('error.generic'))
      if (code === 'friend_epoch_changed' || code === 'friend_unavailable') { await refreshFriends(); setCast([]); key.current = randomId('sstart', 10) }
    } finally { setBusy(false) }
  }

  return (
    <div className="ew-page ew-prepare ew-story-prepare">
      <a className="ew-back ew-btn ghost" href={back}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className="ew-prepare-layout">
        <section className="ew-prepare-main" aria-labelledby="sprep-title">
          <p className="ew-eyebrow">{t('story.prepare')} · v{story.version}</p>
          <h1 id="sprep-title" className="ew-title-xl">{pick(story.title, lang)}</h1>
          <div className="ew-prepare-block">
            <h2 className="ew-section-title">{t('story.playerRole')}</h2>
            <p className="ew-player-role"><strong>{pick(story.player_role, lang)}</strong> <span className="ew-faint">· {t('story.playedBy', {name: account?.persona?.name || t('common.you')})}</span></p>
          </div>
          <div className="ew-prepare-block">
            <h2 className="ew-section-title">{t('story.cast')} <span className="ew-chip">{t('story.aiCount', {n: aiCount})}</span></h2>
            <ol className="ew-seat-list">
              {story.roles.map(r => {
                const chosen = cast.find(c => c.role_id === r.id)
                const f = chosen ? friends.find(x => x.id === chosen.friend_id) : null
                const locked = r.locked || !r.replaceable
                return (
                  <li key={r.id} className="ew-seat-row ew-cast-row" data-role={r.id}>
                    <span className="ew-avatar large"><Portrait src={f?.avatar ?? r.default_character.avatar} name={f?.name ?? r.default_character.name} position="50% 14%" /></span>
                    <span className="ew-seat-name ew-cast-text">
                      <strong>{pick(r.title, lang)}</strong>
                      <span className="ew-faint ew-small">{pick(r.description, lang)}</span>
                      <span className="ew-row wrap">
                        <span>{f ? f.name : r.default_character.name}</span>
                        {f ? <span className="ew-chip friend">{t('common.friend')} · {f.source_name} #{f.display_number}</span> : <span className="ew-chip temp">{t('common.npc')}</span>}
                        {locked && <span className="ew-chip"><Lock aria-hidden="true" />{t('story.locked')}</span>}
                      </span>
                    </span>
                    {locked ? <span className="ew-faint ew-small ew-seat-select">{t('story.lockedNote')}</span> : (
                      <label className="ew-seat-select">
                        <span className="ew-sr">{pick(r.title, lang)}</span>
                        <select className="ew-select" data-testid={`cast-${r.id}`} value={chosen ? `f:${chosen.friend_id}` : 'npc'} onChange={e => {
                          const value = e.target.value
                          setCast(prev => {
                            const rest = prev.filter(c => c.role_id !== r.id)
                            if (value === 'npc') return rest
                            const fr = friends.find(x => x.id === value.slice(2))!
                            return [...rest, {role_id: r.id, friend_id: fr.id, friend_epoch: fr.epoch}]
                          })
                        }}>
                          <option value="npc">{t('story.uninvite')} · {r.default_character.name}</option>
                          {friends.length > 0 && <optgroup label={t('story.invite')}>
                            {friends.map(fr => {
                              const elsewhere = used.has(fr.id) && used.get(fr.id) !== r.id
                              return <option key={fr.id} value={`f:${fr.id}`} disabled={elsewhere}>{fr.name} · {fr.source_name} #{fr.display_number}{elsewhere ? ` (${t('story.friendUsed')})` : ''}</option>
                            })}
                          </optgroup>}
                        </select>
                      </label>
                    )}
                  </li>
                )
              })}
            </ol>
            {friends.length === 0 && <p className="ew-faint ew-small"><Users aria-hidden="true" className="ew-inline-icon" /> {account?.authenticated ? t('story.noFriends') : t('friends.guest')}</p>}
          </div>
          <div className="ew-notice"><span>{t('story.adapt')}</span></div>
        </section>
        <aside className="ew-prepare-side">
          <div className="ew-prepare-poster">{story.image ? <Portrait src={story.image} name={pick(story.title, lang)} /> : <span className="ew-story-cover-fallback" aria-hidden="true" />}</div>
          <div className="ew-notice mock"><span>{t('story.narrationMode')}</span></div>
          <p className="ew-faint ew-small">{t('story.noRecord')}</p>
          {startError && <div className="ew-notice danger" role="alert">{startError}</div>}
          <button type="button" className="ew-btn primary wide ew-start-btn" data-testid="story-start" disabled={busy || invalid} onClick={() => void start()}>
            {busy ? <span className="ew-spinner" /> : <Play aria-hidden="true" />}{busy ? t('game.starting') : startError ? t('story.startRetry') : t('story.startConfirm')}</button>
        </aside>
      </div>
    </div>
  )
}
