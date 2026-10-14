import {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react'
import {ArrowDown, ArrowLeft, BookOpenText, Clock, Eye, FastForward, Image as ImageIcon, ListChecks, MessageCircle, PanelRightClose, PanelRightOpen, RotateCcw, Search, Type, UserPlus, Users} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href} from '../../app/router'
import {toast, useApp} from '../../app/store'
import {api} from '../../api/adapter'
import type {StoryCastJSON, StorySegmentJSON, StorySessionJSON, StoryTurnJSON} from '../../api/types'
import {CompanionRequestError} from '../../contracts/companion'
import {ConfirmDialog} from '../../components/Dialog'
import {Portrait, useAssetUrl} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {errorArt} from '../../art/generated'
import {LiveStage} from '../../live2d/LiveStage'
import {characterFor} from '../../live2d/characters'
import {Composer} from '../../chat/Composer'
import {CharacterLine, NarrationLine, PlayerLine, RichText} from '../../chat/RichText'
import {expressionForText} from '../../chat/presentation'
import {useAddFriend} from '../friends/AddFriendFlow'
import {classNames, pick, randomId, readJSON, removeKey, writeJSON} from '../../lib/util'

type Notice = null | {kind: 'unknown'; key: string; turnKind: 'input' | 'continue'; text: string | null} | {kind: 'failed'} | {kind: 'conflict'}
const draftKey = (account: string, session: string) => `everwith.story.draft.v1:${JSON.stringify([account, session])}`

/**
 * Story run. Input is always the primary entry; “Continue story” advances without
 * speaking for the player. A turn's text and its state change commit together on the
 * (mock) server; while it is validating only the player's own receipt is shown.
 */
export default function StoryPlayPage({sessionId}: {sessionId: string}) {
  const {t, lang} = useI18n()
  const accountId = useApp(s => s.account?.account?.id ?? s.account?.guest_id ?? 'anon')
  const [session, setSession] = useState<StorySessionJSON | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraftState] = useState(() => readJSON<string>(draftKey(accountId, sessionId), ''))
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const [mode, setMode] = useState<'text' | 'scene'>(() => readJSON<'text' | 'scene'>(`everwith.story.mode.v1:${sessionId}`, 'scene', 'session'))
  const [panel, setPanel] = useState(() => typeof window === 'undefined' || window.innerWidth >= 1200)
  const [rollbackTurn, setRollbackTurn] = useState<StoryTurnJSON | null>(null)
  const sessionRef = useRef<StorySessionJSON | null>(null)
  sessionRef.current = session
  const setDraft = useCallback((text: string) => { setDraftState(text); if (text) writeJSON(draftKey(accountId, sessionId), text); else removeKey(draftKey(accountId, sessionId)) }, [accountId, sessionId])
  const {open: openAddFriend, dialog: addFriendDialog} = useAddFriend(() => { void reload() })
  // The account may finish loading after the first render (reload): pick up its saved draft then.
  useEffect(() => {
    const saved = readJSON<string>(draftKey(accountId, sessionId), '')
    if (saved) setDraftState(current => current || saved)
  }, [accountId, sessionId])

  const reload = useCallback(async () => {
    try { const s = await api.stories.get(sessionId); setSession(s); setError(null); return s } catch (e) { setError(e instanceof CompanionRequestError ? e.code : 'network_error'); return null }
  }, [sessionId])
  useEffect(() => { void reload() }, [reload])
  useEffect(() => { writeJSON(`everwith.story.mode.v1:${sessionId}`, mode, 'session') }, [mode, sessionId])

  // While the world is responding, poll the authoritative session (no partial text is shown).
  const pendingStatus = session?.pending?.status
  useEffect(() => {
    if (!pendingStatus || !['validating', 'accepted'].includes(pendingStatus)) return
    const timer = setInterval(() => { void reload() }, 600)
    return () => clearInterval(timer)
  }, [pendingStatus, reload])
  useEffect(() => { if (pendingStatus === 'retryable_failed') setNotice({kind: 'failed'}) }, [pendingStatus])

  const send = async (turnKind: 'input' | 'continue', text: string | null, key = randomId('sturn', 10)) => {
    const s = sessionRef.current
    if (!s || busy) return
    setBusy(true); setNotice(null)
    try {
      const r = await api.stories.turn(s.id, {key, kind: turnKind, ...(text ? {text} : {}), language: lang, expected_revision: s.revision})
      setSession(r.session)
      if (turnKind === 'input') setDraft('')
    } catch (e) {
      const code = e instanceof CompanionRequestError ? e.code : 'network_error'
      // Unknown result: never invent a second turn — retry with the SAME key.
      if (code === 'network_error') setNotice({kind: 'unknown', key, turnKind, text})
      else if (code === 'stale_revision' || code === 'operation_pending') { await reload(); setNotice({kind: 'conflict'}) }
      else toast(code === 'session_read_only' ? t('story.readOnly') : t('error.generic'), 'error')
    } finally { setBusy(false) }
  }
  const control = async (action: 'cancel' | 'retry') => {
    const s = sessionRef.current
    if (!s?.pending) return
    setBusy(true)
    try {
      const r = await api.stories.control(s.id, s.pending.operation_id, action)
      setSession(r.session); setNotice(null)
      if (action === 'cancel' && r.restored && !draft.trim()) setDraft(r.restored)
    } catch { await reload() } finally { setBusy(false) }
  }

  if (error) return (
    <div className="ew-page"><a className="ew-back ew-btn ghost" href={href.recent()}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : t('error.generic')}</h2>
        {error !== 'not_found' && <button type="button" className="ew-btn" onClick={() => void reload()}>{t('common.retry')}</button>}</div></div>
  )
  if (!session) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>

  const readOnly = session.status !== 'active'
  const pending = session.pending
  const working = !!pending && ['validating', 'accepted'].includes(pending.status)
  const castByRole = new Map(session.cast.map(c => [c.role_id, c]))
  const lastSpeaker = (() => {
    for (let i = session.turns.length - 1; i >= 0; i--) {
      const seg = [...session.turns[i].segments].reverse().find(g => g.role_id && g.kind !== 'narration')
      if (seg) return {cast: castByRole.get(seg.role_id!) ?? null, text: seg.text}
    }
    return {cast: session.cast[0] ?? null, text: ''}
  })()
  const focus = lastSpeaker.cast

  return (
    <div className={classNames('ew-story', panel && 'panel-open')} data-revision={session.revision} data-testid="story-play">
      <aside className="ew-story-cast" aria-label={t('story.present')}>
        <div className="ew-chat-stage-top">
          <a className="ew-back ew-btn ghost small" href={href.story(session.story_id, session.version)}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
          <div className="ew-chat-who"><strong>{pick(session.title, lang)}</strong><small>{t('story.youAre', {role: pick(session.player_role, lang)})}</small></div>
        </div>
        <div className="ew-story-stage">
          {focus && <LiveStage key={focus.character_id} character={characterFor(focus.character_id, '1')} name={focus.name} fallbackImage={focus.avatar} expression={expressionForText(lastSpeaker.text)} preset="stage" />}
          {focus && <span className="ew-rail-stage-name">{focus.name} · {pick(focus.role_title, lang)}</span>}
        </div>
        <ul className="ew-story-cast-list">
          {session.cast.map(c => <CastRow key={c.role_id} c={c} readOnly={readOnly} onBefriend={separate => openAddFriend({sourceId: c.character_id, version: '1', sourceName: c.character_name, origin: {kind: 'story', session_id: session.id, role_id: c.role_id, ...(separate ? {separate: true} : {})}})} />)}
        </ul>
        <p className="ew-chip mock ew-story-mode-chip">{t('story.narrationMode')}</p>
      </aside>

      <section className="ew-chat-main ew-story-main" aria-label={pick(session.title, lang)}>
        <div className="ew-story-toolbar">
          <div className="ew-row" role="group" aria-label={t('story.view')}>
            <button type="button" className="ew-btn small" aria-pressed={mode === 'scene'} onClick={() => setMode('scene')}><ImageIcon aria-hidden="true" />{t('story.mode.scene')}</button>
            <button type="button" className="ew-btn small" aria-pressed={mode === 'text'} onClick={() => setMode('text')}><Type aria-hidden="true" />{t('story.mode.text')}</button>
          </div>
          <button type="button" className="ew-icon-btn" aria-pressed={panel} aria-expanded={panel} onClick={() => setPanel(p => !p)} aria-label={t('story.known')} title={t('story.known')}>{panel ? <PanelRightClose aria-hidden="true" /> : <PanelRightOpen aria-hidden="true" />}</button>
        </div>
        {mode === 'scene' && <SceneBanner state={session.state} lang={lang} />}
        {readOnly && <div className="ew-notice warn" role="status">{t('story.readOnly')}</div>}
        {session.state.open_mode && !readOnly && <div className="ew-notice ok" role="status">{t('story.openMode')}</div>}
        <Transcript session={session} castByRole={castByRole} working={working} onRollback={readOnly || !!pending ? null : setRollbackTurn} />
        {notice?.kind === 'unknown' && <div className="ew-notice warn" role="alert"><span>{t('story.unknownResult')}<span className="ew-notice-actions">
          <button type="button" className="ew-btn small" disabled={busy} onClick={() => void send(notice.turnKind, notice.text, notice.key)}>{t('story.retrySame')}</button></span></span></div>}
        {notice?.kind === 'failed' && pending?.status === 'retryable_failed' && <div className="ew-notice danger" role="alert"><span>{t('story.failed')}<span className="ew-notice-actions">
          <button type="button" className="ew-btn small" disabled={busy} onClick={() => void control('retry')} data-testid="story-retry">{t('common.retry')}</button>
          <button type="button" className="ew-btn small ghost" disabled={busy} onClick={() => void control('cancel')}>{t('story.giveUp')}</button></span></span></div>}
        {notice?.kind === 'conflict' && <div className="ew-notice" role="status"><span>{t('story.conflict')}</span></div>}
        <div className="ew-composer-wrap ew-story-composer">
          <div className="ew-story-actions">
            <button type="button" className="ew-btn small" data-testid="story-continue-btn" disabled={readOnly || busy || !!pending} onClick={() => void send('continue', null)} title={t('story.continueNote')}><FastForward aria-hidden="true" />{t('story.continueStory')}</button>
            <span className="ew-faint ew-small">{t('story.continueNote')}</span>
          </div>
          <Composer value={draft} onChange={setDraft} busy={working || busy} disabled={readOnly} label={t('story.input')} placeholder={readOnly ? t('story.readOnly') : t('story.input')}
            onSubmit={text => void send('input', text.trim())} onStop={working ? () => void control('cancel') : undefined} />
        </div>
      </section>

      <aside className="ew-story-state" aria-label={t('story.known')} hidden={!panel}>
        <h2 className="ew-card-title"><Eye aria-hidden="true" className="ew-inline-icon" /> {t('story.known')}</h2>
        <section><h3><ListChecks aria-hidden="true" />{t('story.objectives')}</h3>
          <ol className="ew-objectives">{session.state.objectives.map((o, i) => <li key={i} className={classNames(o.done && 'is-done', o.current && 'is-current')}>{pick(o.text, lang)}{o.done && <span className="ew-sr"> ✓</span>}</li>)}</ol></section>
        <section><h3><Search aria-hidden="true" />{t('story.clues')}</h3>
          {session.state.clues.length ? <ul className="ew-clues">{session.state.clues.map(c => <li key={c.id}>{pick(c.label, lang)}</li>)}</ul> : <p className="ew-faint ew-small">{t('story.noClues')}</p>}</section>
        <section><h3><Clock aria-hidden="true" />{t('story.time', {m: session.state.minutes})}</h3></section>
        <section><h3><Users aria-hidden="true" />{t('story.present')}</h3>
          <p className="ew-small">{session.cast.filter(c => session.state.present.includes(c.role_id)).map(c => `${c.name}（${pick(c.role_title, lang)}）`).join(lang === 'zh' ? '、' : ', ')}</p></section>
        {session.state.hint && !readOnly && <section className="ew-story-hint"><h3><BookOpenText aria-hidden="true" />{t('story.hint')}</h3><p className="ew-small"><RichText text={pick(session.state.hint, lang)} /></p></section>}
        <p className="ew-faint ew-small">{t('story.stateNote', {rev: session.revision})}</p>
      </aside>

      {rollbackTurn && <ConfirmDialog title={t('story.rollback')} body={<><p>{t('story.rollbackConfirm')}</p><blockquote className="ew-quote">{rollbackTurn.input}</blockquote></>} confirmLabel={t('story.rollback')} danger
        onCancel={() => setRollbackTurn(null)} onConfirm={async () => {
          const target = rollbackTurn; setRollbackTurn(null)
          try { const r = await api.stories.rollback(session.id, target.turn_id, session.revision); setSession(r.session); setDraft(r.restored) }
          catch { toast(t('error.conflict'), 'error'); await reload() }
        }} />}
      {addFriendDialog}
    </div>
  )
}

function CastRow({c, readOnly, onBefriend}: {c: StoryCastJSON; readOnly: boolean; onBefriend: (separate: boolean) => void}) {
  const {t, lang} = useI18n()
  const official = c.character_id.startsWith('official-')
  return (
    <li className="ew-story-cast-row" data-role={c.role_id}>
      <span className="ew-avatar"><Portrait src={c.avatar} name={c.name} position="50% 14%" /></span>
      <span className="ew-seat-text"><strong>{c.name}</strong><small>{pick(c.role_title, lang)} · {c.kind === 'friend' ? t('common.friend') : t('common.npc')}</small></span>
      {c.kind === 'friend' && c.friend_id && <a className="ew-icon-btn" href={href.chat(c.friend_id)} aria-label={`${t('game.toChat')} · ${c.name}`} title={t('game.toChat')}><MessageCircle aria-hidden="true" /></a>}
      {official && !readOnly && c.kind === 'npc' && <button type="button" className="ew-icon-btn" data-testid={`story-befriend-${c.role_id}`} onClick={() => onBefriend(false)} aria-label={t('story.addFriend', {name: c.name})} title={`${t('story.addFriend', {name: c.name})} — ${t('story.addFriendNote')}`}><UserPlus aria-hidden="true" /></button>}
      {official && !readOnly && c.kind === 'friend' && <button type="button" className="ew-icon-btn" onClick={() => onBefriend(true)} aria-label={`${t('story.anotherFriend')} · ${c.character_name}`} title={t('story.anotherFriend')}><UserPlus aria-hidden="true" /></button>}
    </li>
  )
}

function Transcript({session, castByRole, working, onRollback}: {session: StorySessionJSON; castByRole: Map<string, StoryCastJSON>; working: boolean; onRollback: ((turn: StoryTurnJSON) => void) | null}) {
  const {t, lang} = useI18n()
  const box = useRef<HTMLDivElement>(null)
  const atEnd = useRef(true)
  const [unseen, setUnseen] = useState(false)
  const count = `${session.turns.length}|${session.pending?.operation_id ?? ''}|${session.pending?.status ?? ''}|${session.revision}`
  // New text never drags a reader who scrolled up; a pill offers the jump instead.
  useLayoutEffect(() => {
    const b = box.current
    if (!b) return
    if (atEnd.current) { b.scrollTop = b.scrollHeight; setUnseen(false) } else setUnseen(true)
  }, [count])
  const segment = (g: StorySegmentJSON) => {
    if (g.kind === 'narration' || !g.role_id) return <NarrationLine key={g.segment_id}><RichText text={g.text} /></NarrationLine>
    const c = castByRole.get(g.role_id)
    const name = c ? `${c.name} · ${pick(c.role_title, lang)}` : g.role_id
    return <CharacterLine key={g.segment_id} name={name} actorKey={c?.character_id} tone={g.kind === 'action' ? 'ew-line-action' : undefined}
      avatar={<span className="ew-avatar small"><Portrait src={c?.avatar} name={c?.name ?? '?'} position="50% 14%" /></span>}
      meta={c?.kind === 'friend' ? <span className="ew-chip friend small">{t('common.friend')}</span> : null}>
      <p><RichText text={g.text} action={g.kind === 'action'} /></p>
    </CharacterLine>
  }
  return (
    <div className="ew-transcript-wrap">
      <div ref={box} className="ew-transcript" role="log" aria-live="off" tabIndex={0} aria-label={pick(session.title, lang)}
        onScroll={e => { const b = e.currentTarget; atEnd.current = b.scrollHeight - b.scrollTop - b.clientHeight < 40; if (atEnd.current) setUnseen(false) }}>
        {session.turns.map(turn => (
          <div key={turn.turn_id} className="ew-turn" data-turn={turn.turn_id}>
            {turn.kind === 'input' && (turn.input_availability === 'available' && turn.input
              ? <PlayerLine meta={<span className="ew-receipt">{t('story.receipt')}{onRollback && <button type="button" className="ew-msg-tool" onClick={() => onRollback(turn)}><RotateCcw aria-hidden="true" />{t('story.rollback')}</button>}</span>}><RichText text={turn.input} /></PlayerLine>
              : <p className="ew-faint ew-small ew-center">{t('story.withdrawn')}</p>)}
            {turn.kind === 'continue' && <p className="ew-story-divider"><FastForward aria-hidden="true" />{t('story.continueStory')}</p>}
            {turn.segments.map(segment)}
            {(turn.delta.clue || turn.delta.minutes > 0) && turn.kind !== 'opening' && <p className="ew-story-delta">{turn.delta.clue && <span className="ew-chip ok">{t('story.newClue', {clue: pick(turn.delta.clue, lang)})}</span>} <span className="ew-faint">+{turn.delta.minutes} min</span></p>}
          </div>
        ))}
        {session.pending && (
          <div className="ew-turn is-pending" data-testid="story-pending">
            {session.pending.kind === 'input' && session.pending.text && <PlayerLine provisional meta={<span className="ew-receipt">{t('story.receipt')}</span>}><RichText text={session.pending.text} /></PlayerLine>}
            {session.pending.kind === 'continue' && <p className="ew-story-divider"><FastForward aria-hidden="true" />{t('story.continueStory')}</p>}
            {working && <p className="ew-typing" role="status"><span className="ew-spinner" />{t('story.validating')}</p>}
          </div>
        )}
      </div>
      {unseen && <button type="button" className="ew-new-pill" onClick={() => { const b = box.current; if (b) { b.scrollTop = b.scrollHeight; atEnd.current = true; setUnseen(false) } }}><ArrowDown aria-hidden="true" />{t('chat.toBottom')}</button>}
    </div>
  )
}

/** Where the story is now (generated scene art, cropped to its reviewed band) and its name. */
function SceneBanner({state, lang}: {state: StorySessionJSON['state']; lang: 'zh' | 'en'}) {
  const url = useAssetUrl(state.scene_image)
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  return (
    <div className="ew-story-scene" data-scene={state.scene}>
      {url && !failed && <img src={url} alt="" decoding="async" draggable={false} style={{objectPosition: `50% ${state.scene_position ?? '50%'}`}} onError={() => setFailed(true)} />}
      {state.scene_label && <span className="ew-story-scene-label">{pick(state.scene_label, lang)}</span>}
    </div>
  )
}
