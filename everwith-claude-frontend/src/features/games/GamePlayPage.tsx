import {useCallback, useEffect, useRef, useState} from 'react'
import {ArrowLeft, BookOpenText, FlaskConical, Maximize, Minimize, PanelRightClose, PanelRightOpen, Pause, Play, Flag, Eye, EyeOff, Trophy, MessageCircle, RotateCcw, UserPlus} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {appStore, toast, useApp} from '../../app/store'
import {api, ADAPTER_MODE} from '../../api/adapter'
import {OPEN_MOCK_PANEL} from '../mock/MockPanel'
import type {GameJSON, GameViewJSON, SeatJSON, TableMessageJSON} from '../../api/types'
import {CompanionRequestError} from '../../contracts/companion'
import {ConfirmDialog, Dialog} from '../../components/Dialog'
import {Portrait} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {errorArt, personaAvatarUrl} from '../../art/generated'
import {LiveStage} from '../../live2d/LiveStage'
import {characterFor} from '../../live2d/characters'
import {useAddFriend} from '../friends/AddFriendFlow'
import {Composer} from '../../chat/Composer'
import {RichText} from '../../chat/RichText'
import {RoyaleBoard} from './boards/RoyaleBoard'
import {SplendorBoard} from './boards/SplendorBoard'
import {CaboBoard} from './boards/CaboBoard'
import {seatColor} from './boards/shared'
import {pick, randomId, classNames} from '../../lib/util'


export default function GamePlayPage({sessionId}: {sessionId: string}) {
  const {t, lang} = useI18n()
  const reducedMotion = useApp(s => s.reducedMotion)
  const [view, setView] = useState<GameViewJSON | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [autoplay, setAutoplay] = useState(true)
  const [leftPaused, setLeftPaused] = useState(false)
  // Narrow desktops fold the people/chat rail into a drawer instead of shrinking the board.
  const [rail, setRail] = useState(() => typeof window === 'undefined' || window.innerWidth >= 1100)
  const [immersive, setImmersive] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [dialog, setDialog] = useState<null | 'rules' | 'abandon'>(null)
  const [messages, setMessages] = useState<TableMessageJSON[]>([])
  const [replyFailed, setReplyFailed] = useState(false)
  const [game, setGame] = useState<GameJSON | null>(null)
  const shell = useRef<HTMLDivElement>(null)
  const viewRef = useRef<GameViewJSON | null>(null)
  viewRef.current = view
  const {open: openAddFriend, dialog: addFriendDialog} = useAddFriend(() => { void reload() })

  // Rail performer: follows the acting table-mate, but switches at most every few seconds
  // so fast AI turns do not reload a model per step.
  const desiredSeat = !view ? 1 : view.lifecycle === 'active' && typeof view.actor_seat === 'number' && view.actor_seat !== 0 ? view.actor_seat
    : (view.log.slice().reverse().find(l => l.seat !== 0)?.seat ?? 1)
  const shownSeat = useDwell(desiredSeat, 4000)

  const reload = useCallback(async () => {
    try { const v = await api.games.get(sessionId); setView(v); return v } catch (e) { setError(e instanceof CompanionRequestError ? e.code : 'network_error'); return null }
  }, [sessionId])
  useEffect(() => {
    void reload().then(v => {
      // Returning to a table where an AI seat is next: the rest stays paused until “Continue”.
      // A brand-new table (revision 1) simply starts.
      if (v && v.lifecycle === 'active' && v.revision > 1 && v.actor_seat !== 0 && v.actor_seat !== 'any') { setLeftPaused(true); setAutoplay(false) }
    })
    api.catalog.games().then(r => setGame(r.items.find(g => g.id === viewRef.current?.game_id) ?? null)).catch(() => {})
  }, [reload])
  useEffect(() => { if (view && !game) api.catalog.games().then(r => setGame(r.items.find(g => g.id === view.game_id) ?? null)).catch(() => {}) }, [view, game])
  const chatCount = view?.chat_count ?? 0
  useEffect(() => { api.games.messages(sessionId).then(r => setMessages(r.items)).catch(() => {}) }, [sessionId, chatCount])

  // Leaving (hidden tab / unmount): the in-flight step finishes server-side; later steps pause.
  useEffect(() => {
    const onVis = () => { if (document.visibilityState === 'hidden') { setAutoplay(false); const v = viewRef.current; if (v?.lifecycle === 'active' && v.actor_seat !== 0) setLeftPaused(true) } }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  // AI seats act one step at a time while this table is open, visible and not paused.
  useEffect(() => {
    if (!view || view.lifecycle !== 'active' || view.ai_hold || !autoplay || pending) return
    if (view.actor_seat === 0 || view.actor_seat === 'any') return
    const timer = setTimeout(async () => {
      if (document.visibilityState === 'hidden') return
      setPending(true)
      try { setView(await api.games.advance(view.id, randomId('adv', 8), view.revision, appStore.get().lang)) }
      catch (e) {
        const code = e instanceof CompanionRequestError ? e.code : 'network_error'
        if (code === 'game_revision_changed' || code === 'waiting_for_player') await reload()
        else { setAutoplay(false); toast(code === 'network_error' ? t('error.network') : t('error.generic'), 'error') }
      } finally { setPending(false) }
    }, reducedMotion ? 380 : 820)
    return () => clearTimeout(timer)
  }, [view, autoplay, pending, reducedMotion, reload, t])

  const act = useCallback(async (action: Record<string, unknown>) => {
    const v = viewRef.current
    if (!v || pending) return false
    setPending(true)
    try {
      const next = await api.games.act(v.id, randomId('act', 8), action, v.revision)
      viewRef.current = next
      setView(next); setAutoplay(true); setLeftPaused(false)
      return true
    } catch (e) {
      const code = e instanceof CompanionRequestError ? e.code : 'network_error'
      const reason = e instanceof CompanionRequestError && typeof e.detail?.reason === 'string' ? `（${e.detail.reason}）` : ''
      if (code === 'game_revision_changed') { await reload(); toast(t('error.conflict')) }
      else toast(code === 'network_error' ? t('error.network') : `${t('error.generic')}${reason}`, 'error')
      return false
    } finally { setPending(false) }
  }, [pending, reload, t])

  useEffect(() => {
    const onFs = () => setFullscreen(document.fullscreenElement === shell.current && !!shell.current)
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])
  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await shell.current?.requestFullscreen()
    } catch { toast(t('game.fullscreenDenied'), 'error') }
  }

  if (error) return (
    <div className="ew-page"><a className="ew-back ew-btn ghost" href={href.recent()}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : t('error.generic')}</h2><p>{t('game.leaveNote')}</p>
        <div className="ew-row center"><button type="button" className="ew-btn" onClick={() => { setError(null); void reload() }}>{t('common.retry')}</button><a className="ew-btn" href={href.recent()}>{t('nav.recent')}</a></div></div></div>
  )
  if (!view) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>

  const seatName = (seat: number) => seat === 0 ? t('common.you') : view.seats[seat]?.name ?? `#${seat}`
  const readOnly = view.lifecycle === 'abandoned' || view.lifecycle === 'ended'
  const yourTurn = view.lifecycle === 'active' && (view.actor_seat === 0 || view.actor_seat === 'any')
  const back = view.origin.return_hash || href.recent()
  const Board = view.game_id === 'vegas' ? RoyaleBoard : view.game_id === 'gems' ? SplendorBoard : CaboBoard
  const focusSeat = shownSeat
  const status = view.lifecycle === 'ended' ? t('game.ended') : view.lifecycle === 'abandoned' ? t('game.abandoned')
    : yourTurn ? t('game.yourTurn') : view.ai_hold || !autoplay ? t('game.paused') : t('game.aiThinking', {name: seatName(view.actor_seat as number)})

  return (
    <div ref={shell} className={classNames('ew-table-shell', `game-${view.game_id}`, !rail && 'rail-closed', immersive && 'is-immersive', fullscreen && 'is-fullscreen')} data-game={view.game_id} data-revision={view.revision} data-lifecycle={view.lifecycle}>
      <header className="ew-table-top">
        <a className="ew-back ew-btn ghost small" href={back} title={t('game.leaveNote')}><ArrowLeft aria-hidden="true" />{t('game.leave')}</a>
        <div className="ew-table-title">
          <strong>{game?.name ?? view.game_id}</strong>
          <span className="ew-chip">{view.profile === 'splendor-legacy-v1' ? t('game.v1') : pick(game?.profile_label ?? {zh: view.profile, en: view.profile}, lang)}</span>
          <span className="ew-chip mock" title={t('game.ruleSimulatedNote')}>{t('game.ruleSimulated')}</span>
          <span className="ew-faint ew-small" data-testid="revision">{t('game.revision', {n: view.revision})}</span>
        </div>
        <p className="ew-table-status" role="status" aria-live="polite" data-testid="table-status">{status}</p>
        <div className="ew-table-tools">
          {view.lifecycle === 'active' && (autoplay && !view.ai_hold
            ? <button type="button" className="ew-btn small" onClick={async () => { setAutoplay(false); setView(await api.games.hold(view.id, true)) }}><Pause aria-hidden="true" />{t('game.pause')}</button>
            : <button type="button" className="ew-btn small primary" data-testid="continue-ai" onClick={async () => { setLeftPaused(false); setView(await api.games.hold(view.id, false)); setAutoplay(true) }}><Play aria-hidden="true" />{t('game.resume')}</button>)}
          {ADAPTER_MODE === 'mock' && <button type="button" className="ew-icon-btn ew-mock-tool" onClick={() => window.dispatchEvent(new Event(OPEN_MOCK_PANEL))} aria-label={t('mock.panel')} title={t('mock.panel.title')}><FlaskConical aria-hidden="true" /></button>}
          <button type="button" className="ew-icon-btn" onClick={() => setDialog('rules')} aria-label={t('game.rules')} title={t('game.rules')}><BookOpenText aria-hidden="true" /></button>
          <button type="button" className="ew-icon-btn" aria-pressed={immersive} onClick={() => setImmersive(v => !v)} aria-label={immersive ? t('game.exitImmersive') : t('game.immersive')} title={immersive ? t('game.exitImmersive') : t('game.immersive')}>{immersive ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}</button>
          <button type="button" className="ew-icon-btn" aria-pressed={fullscreen} onClick={() => void toggleFullscreen()} aria-label={fullscreen ? t('game.exitFullscreen') : t('game.fullscreen')} title={fullscreen ? t('game.exitFullscreen') : t('game.fullscreen')}>{fullscreen ? <Minimize aria-hidden="true" /> : <Maximize aria-hidden="true" />}</button>
          <button type="button" className="ew-icon-btn" aria-pressed={rail} aria-expanded={rail} onClick={() => setRail(v => !v)} aria-label={t('game.sidebar')} title={t('game.sidebar')}>{rail ? <PanelRightClose aria-hidden="true" /> : <PanelRightOpen aria-hidden="true" />}</button>
          {view.lifecycle === 'active' && <button type="button" className="ew-btn small ghost danger-text" onClick={() => setDialog('abandon')}><Flag aria-hidden="true" />{t('game.abandon')}</button>}
        </div>
      </header>
      {leftPaused && view.lifecycle === 'active' && <div className="ew-notice warn ew-table-notice" role="status"><Pause aria-hidden="true" /><span>{t('game.leftPaused')}</span></div>}
      <div className="ew-table-body">
        <main className="ew-board-area" aria-label={game?.name ?? 'board'}>
          {view.lifecycle === 'ended' && view.settlement && <ResultPanel view={view} seatName={seatName} onRematch={async () => { try { const v = await api.games.rematch(view.id, randomId('rematch', 8)); navigate(href.gamePlay(v.id)) } catch { toast(t('error.generic'), 'error') } }} back={back} />}
          {view.lifecycle === 'abandoned' && <div className="ew-notice warn ew-result" role="status"><Flag aria-hidden="true" /><div><strong>{t('game.abandoned')}</strong><div className="ew-notice-actions"><a className="ew-btn small" href={back}>{t('game.backSource')}</a>
            <button type="button" className="ew-btn small" onClick={async () => { try { const v = await api.games.rematch(view.id, randomId('rematch', 8)); navigate(href.gamePlay(v.id)) } catch { toast(t('error.generic'), 'error') } }}><RotateCcw aria-hidden="true" />{t('game.rematch')}</button></div></div></div>}
          <Board view={view} pending={pending} act={act} seatName={seatName} readOnly={readOnly || !yourTurn} />
        </main>
        <aside className="ew-rail" aria-label={t('game.sidebar')} hidden={!rail || immersive}>
          <div className="ew-rail-stage">
            <LiveStage character={characterFor(view.seats[focusSeat]?.source_id, view.seats[focusSeat]?.source_version)} name={view.seats[focusSeat]?.name ?? ''} fallbackImage={view.seats[focusSeat]?.avatar} expression={view.expressions[focusSeat] ?? 'neutral'} preset="rail" />
            <span className="ew-rail-stage-name">{view.seats[focusSeat]?.name}</span>
          </div>
          <ul className="ew-rail-seats">
            {view.seats.map(s => <SeatRow key={s.seat} seat={s} view={view} active={view.actor_seat === s.seat} onBefriend={() => openAddFriend({sourceId: s.source_id!, version: s.source_version!, sourceName: s.name, origin: {kind: 'game', session_id: view.id, seat: s.seat}})} />)}
          </ul>
          <TableChat view={view} messages={messages} replyFailed={replyFailed} onSend={async text => {
            try { const r = await api.games.say(view.id, randomId('say', 8), text, appStore.get().lang); setMessages(r.items); setReplyFailed(r.reply_failed); return true }
            catch (e) { toast(e instanceof CompanionRequestError && e.code === 'table_chat_read_only' ? t('error.forbidden') : t('error.generic'), 'error'); return false }
          }} seatName={seatName} />
        </aside>
      </div>
      {dialog === 'rules' && <Dialog title={`${t('game.rules')} · ${game?.name ?? ''}`} onClose={() => setDialog(null)} wide>
        <p><code className="ew-code">{view.profile}</code></p>
        <ul className="ew-rules">{(game?.rule_notes ?? []).map((n, i) => <li key={i}>{pick(n, lang)}</li>)}</ul>
        <p className="ew-faint ew-small">{t('game.ruleSimulatedNote')}</p>
      </Dialog>}
      {dialog === 'abandon' && <ConfirmDialog title={t('game.abandon')} body={<p>{t('game.abandonConfirm')}</p>} confirmLabel={t('game.abandon')} danger onCancel={() => setDialog(null)}
        onConfirm={async () => { setDialog(null); try { setView(await api.games.abandon(view.id, view.revision)) } catch { await reload() } }} />}
      {addFriendDialog}
    </div>
  )
}

function useDwell<T>(desired: T, ms: number): T {
  const [shown, setShown] = useState(desired)
  const since = useRef(0)
  useEffect(() => {
    if (Object.is(desired, shown)) return
    const wait = Math.max(0, since.current + ms - Date.now())
    const timer = setTimeout(() => { since.current = Date.now(); setShown(desired) }, wait)
    return () => clearTimeout(timer)
  }, [desired, shown, ms])
  return shown
}

function SeatRow({seat, view, active, onBefriend}: {seat: SeatJSON; view: GameViewJSON; active: boolean; onBefriend: () => void}) {
  const {t} = useI18n()
  const myAvatar = useApp(s => s.account?.persona?.avatar ?? null)
  const score = view.settlement?.scores[seat.seat]
  return (
    <li className={classNames('ew-seat', active && 'is-active')} data-seat={seat.seat}>
      <span className="ew-seat-dot" style={{background: seatColor(seat.seat)}} aria-hidden="true" />
      <span className="ew-avatar small"><Portrait src={seat.kind === 'player' ? personaAvatarUrl(myAvatar) : seat.avatar} name={seat.name} position={seat.kind === 'player' ? undefined : '50% 14%'} /></span>
      <span className="ew-seat-text"><strong>{seat.seat === 0 ? t('common.you') : seat.name}</strong>
        <small>{seat.kind === 'player' ? t('game.you') : seat.kind === 'friend' ? t('common.friend') : t('common.temporary')}{score !== undefined ? ` · ${score.toLocaleString()}` : ''}</small></span>
      {seat.kind === 'friend' && <a className="ew-icon-btn" href={href.chat(seat.identity)} aria-label={`${t('game.toChat')} · ${seat.name}`} title={t('game.toChat')}><MessageCircle aria-hidden="true" /></a>}
      {seat.kind === 'temporary' && seat.source_id && <button type="button" className="ew-icon-btn" onClick={onBefriend} aria-label={`${t('game.befriend')} · ${seat.name}`} title={`${t('game.befriend')} — ${t('game.befriendNote')}`}><UserPlus aria-hidden="true" /></button>}
    </li>
  )
}

function TableChat({view, messages, replyFailed, onSend, seatName}: {view: GameViewJSON; messages: TableMessageJSON[]; replyFailed: boolean; onSend: (text: string) => Promise<boolean>; seatName: (s: number) => string}) {
  const {t} = useI18n()
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const atEnd = useRef(true)
  useEffect(() => { const b = box.current; if (b && atEnd.current) b.scrollTop = b.scrollHeight }, [messages.length])
  return (
    <section className="ew-table-chat" aria-label={t('game.tableChat')}>
      <header><strong>{t('game.tableChat')}</strong><small className="ew-faint">{t('game.tableChatNote')}</small></header>
      <div ref={box} className="ew-table-log" role="log" onScroll={e => { const b = e.currentTarget; atEnd.current = b.scrollHeight - b.scrollTop - b.clientHeight < 30 }}>
        {view.log.slice(-6).map(l => <p key={`log-${l.revision}-${l.seat}`} className="ew-log-line"><span className="ew-seat-dot" style={{background: seatColor(l.seat)}} aria-hidden="true" />{pickSummary(l.summary)}</p>)}
        {messages.map(m => <p key={m.id} className={`ew-chat-line ${m.seat === 0 ? 'is-me' : ''}`}><strong>{seatName(m.seat)}</strong>{m.mode === 'simulated_rule_reply' && <span className="ew-chip mock small">{t('common.simulated')}</span>}<span className="ew-chat-text"><RichText text={m.text} /></span></p>)}
        {replyFailed && <p className="ew-faint ew-small">{t('game.replyFailed')}</p>}
      </div>
      <Composer value={draft} onChange={setDraft} busy={busy} disabled={view.lifecycle === 'abandoned'} label={t('game.tableChat')} placeholder={t('game.say')}
        onSubmit={async text => { setBusy(true); const ok = await onSend(text); setBusy(false); if (ok) setDraft('') }} />
    </section>
  )
}
function pickSummary(s: {zh: string; en: string}) { return appStore.get().lang === 'zh' ? s.zh : s.en }

function ResultPanel({view, seatName, onRematch, back}: {view: GameViewJSON; seatName: (s: number) => string; onRematch: () => void; back: string}) {
  const {t} = useI18n()
  const ref = useRef<HTMLElement>(null)
  useEffect(() => { ref.current?.focus({preventScroll: false}) }, [])
  const s = view.settlement!
  const order = view.seats.map(x => x.seat).sort((a, b) => view.game_id === 'cabo' ? s.scores[a] - s.scores[b] : s.scores[b] - s.scores[a])
  return (
    <section ref={ref} tabIndex={-1} className="ew-result" aria-labelledby="result-title" data-testid="result">
      <h2 id="result-title"><Trophy aria-hidden="true" /> {t('game.result')} · {t('game.ended')}</h2>
      <table className="ew-result-table">
        <thead><tr><th scope="col">{t('game.seats')}</th><th scope="col">{t('game.score')}</th><th scope="col"></th></tr></thead>
        <tbody>{order.map(seat => <tr key={seat} className={s.winners.includes(seat) ? 'is-winner' : ''}>
          <th scope="row"><span className="ew-seat-dot" style={{background: seatColor(seat)}} aria-hidden="true" /> {seatName(seat)}</th>
          <td>{s.scores[seat].toLocaleString()}</td><td>{s.winners.includes(seat) ? t('game.winner') : ''} <small className="ew-faint">{s.labels[seat] ? pickSummary(s.labels[seat]) : ''}</small></td></tr>)}</tbody>
      </table>
      <div className="ew-row wrap">
        <button type="button" className="ew-btn primary" onClick={onRematch}><RotateCcw aria-hidden="true" />{t('game.rematch')}</button>
        {view.seats.filter(x => x.kind === 'friend').map(f => <a key={f.identity} className="ew-btn" href={href.chat(f.identity)}><MessageCircle aria-hidden="true" />{t('game.toChat')} · {f.name}</a>)}
        <a className="ew-btn ghost" href={back}>{t('game.backSource')}</a>
      </div>
    </section>
  )
}
