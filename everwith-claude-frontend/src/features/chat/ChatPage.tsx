import {Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore} from 'react'
import {ArrowDown, ArrowLeft, Gamepad2, Info, MoreHorizontal, PanelRightClose, PanelRightOpen, PencilLine, RotateCcw, Search, Undo2, UserX, Volume2, VolumeX, AlertTriangle, Pencil} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import type {I18nKey} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {appStore, openSignIn, refreshFriends, toast, useApp} from '../../app/store'
import {api} from '../../api/adapter'
import {CompanionRequestError} from '../../contracts/companion'
import type {CompanionFriend} from '../../contracts/companion'
import type {PrivateSnapshot, PrivateTurn} from '../../contracts/private-chat-client'
import {createChatController} from '../../chat/stream-controller'
import type {ChatController, ChatTransport, ChatView} from '../../chat/stream-controller'
import {Composer} from '../../chat/Composer'
import {CharacterLine, NarrationLine, PlayerLine, RichText} from '../../chat/RichText'
import {expressionForText, readDraft, readReading, writeDraft, writeReading} from '../../chat/presentation'
import type {DraftScope} from '../../chat/presentation'
import {LiveStage} from '../../live2d/LiveStage'
import {characterFor} from '../../live2d/characters'
import {demoVoice} from '../../live2d/audio'
import {Portrait} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {errorArt} from '../../art/generated'
import {ConfirmDialog, Dialog} from '../../components/Dialog'
import {PlayTogetherDialog} from '../friends/PlayTogether'
import {formatTime, pick, randomId} from '../../lib/util'

type Loaded = {friend: CompanionFriend; snapshot: PrivateSnapshot; accountId: string}

export default function ChatPage({friendId}: {friendId: string}) {
  const {t, lang} = useI18n()
  const account = useApp(s => s.account)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadSeq, setReloadSeq] = useState(0)
  const accountId = account?.authenticated ? account.account!.id : null

  useEffect(() => {
    if (!accountId) return
    let live = true
    setLoaded(null); setError(null)
    ;(async () => {
      try {
        const friend = await api.friends.get(friendId)
        const snapshot = await api.chat.open(friend.id, friend.epoch, accountId, randomId('open', 8), appStore.get().lang)
        if (live) setLoaded({friend, snapshot, accountId})
      } catch (e) { if (live) setError(e instanceof CompanionRequestError ? e.code : 'network_error') }
    })()
    return () => { live = false }
  }, [friendId, accountId, reloadSeq])

  if (account && !account.authenticated) return (
    <div className="ew-page"><div className="ew-empty"><SpotArt kind="signin" /><h2>{t('auth.why', {action: t('auth.action.chat')})}</h2>
      <button type="button" className="ew-btn primary" onClick={() => openSignIn('auth.action.chat')}>{t('common.signin')}</button></div></div>
  )
  if (error) return (
    <div className="ew-page"><a className="ew-back ew-btn ghost" href={href.friends()}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : error === 'auth_session_required' ? t('error.auth') : t('error.generic')}</h2>
        <button type="button" className="ew-btn" onClick={() => setReloadSeq(n => n + 1)}>{t('common.retry')}</button></div></div>
  )
  if (!loaded) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>
  return <ChatRoom key={`${loaded.friend.id}:${loaded.friend.epoch}:${loaded.snapshot.conversation.id}`} {...loaded} lang={lang} onReload={() => { void refreshFriends(); setReloadSeq(n => n + 1) }} />
}

function ChatRoom({friend, snapshot, accountId, lang, onReload}: Loaded & {lang: 'zh' | 'en'; onReload: () => void}) {
  const conversationId = snapshot.conversation.id
  const scope: DraftScope = useMemo(() => ({accountId, friendId: friend.id, epoch: friend.epoch, conversationId}), [accountId, friend.id, friend.epoch, conversationId])
  // One controller per mount. Created in an effect so StrictMode's trial unmount
  // disposes its own instance instead of a shared one.
  const [controller, setController] = useState<ChatController | null>(null)
  useEffect(() => {
    const transport: ChatTransport = {
      send: (cmd, signal) => api.chat.send(conversationId, cmd, accountId, friend.epoch, signal),
      stream: (adm, signal) => api.chat.stream(adm, signal),
      cancel: id => api.chat.cancel(id, accountId, friend.epoch),
      receipt: id => api.chat.receipt(id),
      retry: id => api.chat.retry(id, accountId, friend.epoch),
      lookup: key => api.chat.lookup(conversationId, key),
      read: () => api.chat.read(conversationId, friend.id, friend.epoch),
    }
    const c = createChatController(snapshot, {account_id: accountId, friend_id: friend.id, friend_epoch: friend.epoch, session_id: conversationId, allow_fictional_thought: false}, transport)
    setController(c)
    if (snapshot.pending_operation) void c.resume()
    return () => c.dispose()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- keyed by friend/epoch/conversation
  if (!controller) return <div className="ew-page-loading" role="status"><span className="ew-spinner" /></div>
  return <ChatRoomBody controller={controller} friend={friend} snapshot={snapshot} accountId={accountId} lang={lang} onReload={onReload} scope={scope} conversationId={conversationId} />
}

function ChatRoomBody({controller, friend, accountId, lang, onReload, scope, conversationId}: Loaded & {controller: ChatController; lang: 'zh' | 'en'; onReload: () => void; scope: DraftScope; conversationId: string}) {
  const {t} = useI18n()
  const view = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot)
  // Draft (text + selection) per account/friend/epoch/conversation.
  const saved = useMemo(() => readDraft(scope), [scope])
  const [draft, setDraft] = useState(saved?.text ?? '')
  const [selection, setSelection] = useState<{start: number; end: number} | null>(saved ? {start: saved.start, end: saved.end} : null)
  const [stash, setStash] = useState<string | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const latestDraft = useRef({text: draft, start: draft.length, end: draft.length})
  latestDraft.current = {text: draft, start: selection?.start ?? draft.length, end: selection?.end ?? draft.length}
  useEffect(() => { const h = setTimeout(() => writeDraft(scope, latestDraft.current), 120); return () => clearTimeout(h) }, [draft, selection, scope])
  // Leaving within the debounce window must not resurrect an older draft: flush on unmount.
  useEffect(() => () => writeDraft(scope, latestDraft.current), [scope])
  // A cancelled / stale / failed command gives its text back — never auto-sent.
  useEffect(() => {
    if (!view.restore) return
    const r = controller.consumeRestore()
    if (!r) return
    if (!draft.trim()) setDraft(r.text); else setStash(r.text)
  }, [view.restore]) // eslint-disable-line react-hooks/exhaustive-deps

  const active = ['sending', 'starting', 'generating', 'awaiting_commit', 'cancelling'].includes(view.phase)
  const readOnly = view.history.conversation.status !== 'active'
  const cfg = characterFor(friend.source_id, friend.source_version)
  const [toolsOpen, setToolsOpen] = useState(() => window.innerWidth >= 1360)
  const [dialog, setDialog] = useState<null | 'play' | 'rename' | 'reset' | 'remove' | 'correct' | 'profile' | {rollback: string; count: number}>(null)
  const [speaking, setSpeaking] = useState(false)

  const send = (text: string) => {
    if (/^\s*\/(纠错|correct)\s*$/i.test(text)) { setDialog('correct'); return } // exact shortcut only
    setStash(null)
    void controller.start(text, appStore.get().lang)
    // Accepted for sending: the receipt now holds the text; failures hand it back.
    const v = controller.getSnapshot()
    if (v.phase === 'sending' && v.input === text) { setDraft(''); setSelection(null) }
  }

  // Expression: from visible public text only; neutral after a cancel/failure.
  const lastCharacterText = useMemo(() => {
    for (let i = view.history.history.turns.length - 1; i >= 0; i--) {
      const seg = [...view.history.history.turns[i].visible_segments].reverse().find(s => s.kind === 'dialogue' && s.availability !== 'withdrawn')
      if (seg) return seg.text
    }
    return ''
  }, [view.history])
  const provisionalSpoken = view.provisional.filter(s => s.kind === 'spoken').map(s => s.text).join(' ')
  const expression = view.phase === 'cancelled' || view.phase === 'failed' ? 'neutral' : expressionForText(provisionalSpoken || lastCharacterText)

  useEffect(() => () => { if (demoVoice.speaker === cfg?.key) demoVoice.stop() }, [cfg?.key])
  const toggleVoice = async () => {
    if (!cfg) return
    if (speaking) { demoVoice.stop(); setSpeaking(false); return }
    try { setSpeaking(true); await demoVoice.play(lastCharacterText || friend.name, cfg.key, () => setSpeaking(false)) } catch { setSpeaking(false); toast(t('chat.voiceOff'), 'error') }
  }

  return (
    <div className={`ew-chat ${toolsOpen ? 'tools-open' : ''}`}>
      <aside className="ew-chat-stage" aria-label={friend.name}>
        <div className="ew-chat-stage-top">
          <a className="ew-back ew-icon-btn" href={href.friends()} aria-label={t('common.back')} title={t('common.back')}><ArrowLeft aria-hidden="true" /></a>
          <div className="ew-chat-who">
            <strong>{friend.name}</strong>
            <small>{t('friends.source', {name: friend.source_name})} · {t('friends.number', {n: friend.display_number})}</small>
          </div>
        </div>
        <div className="ew-chat-portrait">
          <LiveStage character={cfg} name={friend.name} fallbackImage={friend.avatar} expression={expression} speaking={speaking} preset="stage" />
        </div>
        <div className="ew-chat-stage-meta">
          <span className="ew-chip">{t(`expr.${expression}`)}</span>
          <span className="ew-chip mock" title={t('chat.replyModeNote')}>{t('chat.replyMode')}</span>
        </div>
        <div className="ew-voice">
          <button type="button" className="ew-btn small" onClick={() => void toggleVoice()} disabled={!cfg} aria-pressed={speaking}>
            {speaking ? <VolumeX aria-hidden="true" /> : <Volume2 aria-hidden="true" />}{speaking ? t('chat.stopAudio') : t('chat.demoAudio')}</button>
          <small className="ew-faint">{t('chat.voiceOff')}</small>
        </div>
      </aside>

      <section className="ew-chat-main" aria-label={t('chat.label', {name: friend.name})}>
        {readOnly && <div className="ew-notice warn" role="status"><Info aria-hidden="true" /><div><strong>{t('chat.readOnly')}</strong><div>{t('chat.readOnlyNote')}</div></div></div>}
        <Transcript view={view} friend={friend} scope={scope} readOnly={readOnly || active} onRollback={(turnId, count) => setDialog({rollback: turnId, count})} />
        <Notices view={view} controller={controller} onReload={onReload} />
        {stash !== null && <div className="ew-notice" role="status"><Undo2 aria-hidden="true" /><div><span>{t('chat.notice.cancelled')}</span><div className="ew-stash">“{stash}”</div><div className="ew-notice-actions">
          <button type="button" className="ew-btn small" onClick={() => { setDraft(stash); setStash(null); inputRef.current?.focus() }}>{t('chat.useHint')}</button>
          <button type="button" className="ew-btn small ghost" onClick={() => setStash(null)}>{t('common.close')}</button></div></div></div>}
        <Composer value={draft} onChange={setDraft} onSubmit={send} onStop={() => void controller.cancel()} busy={active} disabled={readOnly || view.phase === 'unknown'}
          canSend={!view.history.pending_operation} label={t('chat.label', {name: friend.name})} placeholder={t('chat.placeholder', {name: friend.name})} inputRef={inputRef}
          selection={selection} onSelection={setSelection} describedBy="chat-status"
          hints={{title: t('chat.hintsTitle'), note: t('chat.hintsNote'), items: lang === 'zh' ? ['*想了想。*\n今天过得怎么样？', '*笑了笑。*\n下次一起玩一局吧。'] : ['*Thinks for a moment.*\nHow was your day?', '*Smiles.*\nLet\'s play a game together next time.']}} />
        <p id="chat-status" className="ew-sr" aria-live="polite">{view.phase === 'generating' ? t('chat.generating', {name: friend.name}) : view.phase === 'awaiting_commit' ? t('chat.awaiting') : ''}</p>
      </section>

      <aside className={`ew-chat-tools ${toolsOpen ? 'is-open' : ''}`} aria-label={t('chat.tools')}>
        <button type="button" className="ew-icon-btn ew-tools-toggle" aria-expanded={toolsOpen} onClick={() => setToolsOpen(v => !v)} aria-label={t('chat.tools')} title={t('chat.tools')}>
          {toolsOpen ? <PanelRightClose aria-hidden="true" /> : <PanelRightOpen aria-hidden="true" />}</button>
        {toolsOpen && <div className="ew-tools-body">
          <button type="button" className="ew-btn primary wide" onClick={() => setDialog('play')}><Gamepad2 aria-hidden="true" />{t('chat.playTogether')}</button>
          <button type="button" className="ew-btn wide" onClick={() => setDialog('profile')}><Info aria-hidden="true" />{t('chat.profile')}</button>
          <hr />
          <p className="ew-tools-caption"><MoreHorizontal aria-hidden="true" className="ew-inline-icon" /> {t('common.more')}</p>
          <button type="button" className="ew-btn ghost wide align-start" disabled={readOnly} onClick={() => setDialog('correct')}><Search aria-hidden="true" />{t('chat.correct')}</button>
          <button type="button" className="ew-btn ghost wide align-start" onClick={() => setDialog('rename')}><Pencil aria-hidden="true" />{t('chat.rename')}</button>
          <button type="button" className="ew-btn ghost wide align-start" onClick={() => setDialog('reset')}><RotateCcw aria-hidden="true" />{t('chat.reset')}</button>
          <button type="button" className="ew-btn ghost wide align-start danger-text" onClick={() => setDialog('remove')}><UserX aria-hidden="true" />{t('chat.remove')}</button>
          <OlderConversations friend={friend} currentId={conversationId} />
        </div>}
      </aside>

      {dialog === 'play' && <PlayTogetherDialog friend={friend} from={href.chat(friend.id)} onClose={() => setDialog(null)} />}
      {dialog === 'profile' && <Dialog title={friend.name} onClose={() => setDialog(null)}>
        <div className="ew-row"><span className="ew-avatar large"><Portrait src={friend.avatar} name={friend.name} /></span>
          <div><strong>{friend.name}</strong><div className="ew-muted">{t('friends.source', {name: friend.source_name})} · {t('friends.number', {n: friend.display_number})}</div>
            <div className="ew-faint ew-small">{t('friends.since', {date: formatTime(friend.created_at, lang)})} · {pick(friend.origin.label, lang)} · epoch {friend.epoch}</div></div></div>
        <a className="ew-btn" href={href.character(friend.source_id, friend.source_version)}>{t('character.public')}</a>
      </Dialog>}
      {dialog === 'rename' && <RenameDialog friend={friend} accountId={accountId} onClose={() => setDialog(null)} onDone={onReload} />}
      {dialog === 'reset' && <FriendCommandDialog kind="reset" friend={friend} accountId={accountId} onClose={() => setDialog(null)} onDone={onReload} />}
      {dialog === 'remove' && <FriendCommandDialog kind="remove" friend={friend} accountId={accountId} onClose={() => setDialog(null)} onDone={() => { void refreshFriends(); navigate(href.friends()) }} />}
      {dialog === 'correct' && <CorrectionDialog onClose={() => setDialog(null)} onSubmit={async text => {
        const next = await api.chat.correction(conversationId, randomId('corr', 8), text, null, friend.id, friend.epoch, appStore.get().lang)
        controller.replaceHistory(next); setDialog(null)
        if (/^\s*\/(纠错|correct)\s*$/i.test(draft)) setDraft('')
      }} />}
      {typeof dialog === 'object' && dialog && 'rollback' in dialog && <ConfirmDialog title={t('chat.rollback')} body={<p>{t('chat.rollbackConfirm', {n: dialog.count})}</p>} confirmLabel={t('chat.rollback')} danger
        onCancel={() => setDialog(null)} onConfirm={async () => {
          try {
            const r = await api.chat.rollback(conversationId, dialog.rollback, view.history.history.position.revision, friend.id, friend.epoch, appStore.get().lang)
            controller.replaceHistory(r.snapshot)
            if (draft.trim()) setStash(draft)
            setDraft(r.restored); setDialog(null); toast(t('chat.rollbackDone'), 'success')
            requestAnimationFrame(() => inputRef.current?.focus())
          } catch (e) { setDialog(null); toast(e instanceof CompanionRequestError && e.code === 'stale_revision' ? t('error.conflict') : t('error.generic'), 'error') }
        }} />}
    </div>
  )
}

function Transcript({view, friend, scope, readOnly, onRollback}: {view: ChatView; friend: CompanionFriend; scope: DraftScope; readOnly: boolean; onRollback: (turnId: string, count: number) => void}) {
  const {t} = useI18n()
  const ref = useRef<HTMLDivElement>(null)
  const atBottom = useRef(true)
  const [unseen, setUnseen] = useState(0)
  const turns = view.history.history.turns
  const showReceipt = !!view.input && ['sending', 'starting', 'generating', 'awaiting_commit', 'cancelling', 'unknown', 'interrupted'].includes(view.phase)
  const contentKey = `${turns.length}|${view.provisional.map(s => s.text.length).join(',')}|${showReceipt}`
  const prevTurns = useRef(turns.length)

  const saveAnchor = useCallback(() => {
    const box = ref.current; if (!box) return
    const end = box.scrollHeight - box.scrollTop - box.clientHeight < 40
    atBottom.current = end
    if (end) setUnseen(0)
    const items = Array.from(box.querySelectorAll<HTMLElement>('[data-anchor]'))
    const first = items.find(el => el.offsetTop + el.offsetHeight > box.scrollTop) ?? null
    writeReading(scope, {anchorId: first?.dataset.anchor ?? null, offset: first ? first.offsetTop - box.scrollTop : 0, atEnd: end})
  }, [scope])
  const restoreAnchor = useCallback(() => {
    const box = ref.current; if (!box) return
    const pos = readReading(scope)
    if (!pos || pos.atEnd || !pos.anchorId) { box.scrollTop = box.scrollHeight; atBottom.current = true; return }
    const el = box.querySelector<HTMLElement>(`[data-anchor="${CSS.escape(pos.anchorId)}"]`)
    if (el) { box.scrollTop = el.offsetTop - pos.offset; atBottom.current = false } else box.scrollTop = box.scrollHeight
  }, [scope])
  useLayoutEffect(() => { restoreAnchor() }, [restoreAnchor])
  // New content: follow only if the reader was already at the end.
  useLayoutEffect(() => {
    const box = ref.current; if (!box) return
    if (atBottom.current) box.scrollTop = box.scrollHeight
    else if (turns.length > prevTurns.current) setUnseen(n => n + (turns.length - prevTurns.current))
    prevTurns.current = turns.length
  }, [contentKey]) // eslint-disable-line react-hooks/exhaustive-deps
  // Width/height changes (side panels, zoom, fonts) keep the same anchor instead of jumping.
  useEffect(() => {
    const box = ref.current; if (!box) return
    const ro = new ResizeObserver(() => { if (atBottom.current) box.scrollTop = box.scrollHeight; else restoreAnchor() })
    ro.observe(box)
    return () => ro.disconnect()
  }, [restoreAnchor])

  const avatar = <span className="ew-avatar"><Portrait src={friend.avatar} name={friend.name} position="50% 14%" /></span>
  const later = (index: number) => turns.slice(index).length
  return (
    <div className="ew-transcript-wrap">
      <div ref={ref} className="ew-transcript" onScroll={saveAnchor} tabIndex={0} aria-label={t('chat.label', {name: friend.name})} role="log" aria-live="off">
        <p className="ew-transcript-start">{t('chat.empty', {name: friend.name})}</p>
        {turns.map((turn, index) => <TurnView key={turn.turn_id} turn={turn} friend={friend} avatar={avatar} canRollback={!readOnly && index > 0 && !!turn.player_expression} onRollback={() => onRollback(turn.turn_id, later(index) - 1)} />)}
        {showReceipt && (
          <div data-anchor="receipt">
            <PlayerLine provisional meta={<span className="ew-receipt">{view.phase === 'unknown' ? t('chat.notice.unknown').split('。')[0] : t('chat.receiptPending')}</span>}><RichText text={view.input} /></PlayerLine>
          </div>
        )}
        {view.provisional.length > 0 && (
          <div data-anchor="provisional">
            <CharacterLine name={friend.name} avatar={avatar} provisional meta={<span className="ew-chip mock small">{t('chat.provisional')}</span>}>
              {view.provisional.map(s => <p key={s.segment_id} className={s.kind === 'action' ? 'ew-line-action' : s.kind === 'narration' ? 'ew-line-narr' : ''}>{s.kind === 'action' ? <em className="ew-act">{s.text}</em> : <RichText text={s.text} />}</p>)}
            </CharacterLine>
          </div>
        )}
        {['sending', 'starting'].includes(view.phase) && view.provisional.length === 0 && <div className="ew-typing" role="status"><span className="ew-spinner" />{view.phase === 'sending' ? t('chat.sending') : t('chat.generating', {name: friend.name})}</div>}
        {view.phase === 'awaiting_commit' && <div className="ew-typing" role="status"><span className="ew-spinner" />{t('chat.awaiting')}</div>}
        {view.phase === 'cancelling' && <div className="ew-typing" role="status"><span className="ew-spinner" />{t('chat.cancelling')}</div>}
        {view.ignoredFrames > 0 && <p className="ew-faint ew-small ew-center">{t('chat.ignoredFrames', {n: view.ignoredFrames})}</p>}
      </div>
      {unseen > 0 && <button type="button" className="ew-new-pill" onClick={() => { const box = ref.current; if (box) { box.scrollTop = box.scrollHeight; atBottom.current = true; setUnseen(0) } }}>
        <ArrowDown aria-hidden="true" />{t('chat.newMessages', {n: unseen})}</button>}
    </div>
  )
}

function TurnView({turn, friend, avatar, canRollback, onRollback}: {turn: PrivateTurn; friend: CompanionFriend; avatar: React.ReactNode; canRollback: boolean; onRollback: () => void}) {
  const {t} = useI18n()
  const groups: {kind: 'character' | 'narration'; parts: {kind: string; text: string; id: string}[]}[] = []
  for (const s of turn.visible_segments) {
    if (s.availability === 'withdrawn') continue
    const kind = s.kind === 'narration' ? 'narration' : 'character'
    const last = groups[groups.length - 1]
    if (last && last.kind === kind && kind === 'character') last.parts.push({kind: s.kind, text: s.text, id: s.segment_id})
    else groups.push({kind, parts: [{kind: s.kind, text: s.text, id: s.segment_id}]})
  }
  return (
    <div className="ew-turn" data-anchor={turn.turn_id} data-turn={turn.turn_id}>
      {turn.player_expression && turn.input_availability !== 'withdrawn' && (
        <PlayerLine meta={canRollback ? <button type="button" className="ew-msg-tool" onClick={onRollback} title={t('chat.rollback')} aria-label={`${t('chat.rollback')}: ${turn.player_expression.slice(0, 20)}`}><Undo2 aria-hidden="true" /><span>{t('chat.rollback')}</span></button> : undefined}>
          <RichText text={turn.player_expression} />
        </PlayerLine>
      )}
      {groups.map((g, i) => g.kind === 'narration'
        ? <NarrationLine key={i}>{g.parts.map(p => <Fragment key={p.id}><RichText text={p.text} action /></Fragment>)}</NarrationLine>
        : <CharacterLine key={i} name={friend.name} avatar={avatar} actorKey={friend.id}>
            {g.parts.map(p => <p key={p.id} className={p.kind === 'action' ? 'ew-line-action' : ''}>{p.kind === 'action' ? <em className="ew-act">{p.text}</em> : <RichText text={p.text} />}</p>)}
          </CharacterLine>)}
    </div>
  )
}

function Notices({view, controller, onReload}: {view: ChatView; controller: ChatController; onReload: () => void}) {
  const {t} = useI18n()
  const n = view.notice
  const pending = view.history.pending_operation
  if (pending?.status === 'retryable_failed' || (n?.kind === 'retryable')) {
    return <div className="ew-notice warn" role="alert"><AlertTriangle aria-hidden="true" /><div><span>{t('chat.notice.retryable')}</span>
      <div className="ew-notice-actions"><button type="button" className="ew-btn small primary" onClick={() => void controller.retry()}>{t('chat.retry')}</button></div></div></div>
  }
  if (!n) return null
  const key = `chat.notice.${n.kind}` as I18nKey
  const actions = n.kind === 'unknown' ? <button type="button" className="ew-btn small primary" onClick={() => void controller.lookup()}>{t('chat.lookup')}</button>
    : n.kind === 'lookup_missing' ? <button type="button" className="ew-btn small primary" onClick={() => void controller.resendSameKey()}>{t('chat.resend')}</button>
    : n.kind === 'epoch_changed' || n.kind === 'read_only' ? <button type="button" className="ew-btn small" onClick={onReload}>{t('common.retry')}</button>
    : n.kind === 'auth' ? <button type="button" className="ew-btn small primary" onClick={() => openSignIn('auth.action.chat')}>{t('common.signin')}</button>
    : null
  const tone = n.kind === 'commit_won' ? 'ok' : n.kind === 'cancelled' || n.kind === 'stale' ? '' : 'warn'
  return (
    <div className={`ew-notice ${tone}`} role={tone === 'warn' ? 'alert' : 'status'} data-notice={n.kind}>
      <Info aria-hidden="true" />
      <div><span>{t(key)}</span><div className="ew-notice-actions">{actions}
        {n.kind !== 'unknown' && <button type="button" className="ew-btn small ghost" onClick={() => controller.dismissNotice()}>{t('common.close')}</button>}</div></div>
    </div>
  )
}

function RenameDialog({friend, accountId, onClose, onDone}: {friend: CompanionFriend; accountId: string; onClose: () => void; onDone: () => void}) {
  const {t} = useI18n()
  const [name, setName] = useState(friend.name)
  const [busy, setBusy] = useState(false)
  return (
    <Dialog title={t('chat.renameTitle')} onClose={onClose} initialFocus="input" footer={<>
      <button type="button" className="ew-btn ghost" onClick={onClose}>{t('common.cancel')}</button>
      <button type="button" className="ew-btn primary" disabled={busy || !name.trim()} onClick={async () => {
        setBusy(true)
        try { await api.friends.rename(friend.id, friend.epoch, name.trim(), accountId); onClose(); onDone() } catch { toast(t('error.generic'), 'error'); setBusy(false) }
      }}>{t('common.save')}</button></>}>
      <p className="ew-muted">{t('name.desc', {source: friend.source_name})}</p>
      <label className="ew-field"><span>{t('name.label')}</span><input className="ew-input" value={name} maxLength={40} onChange={e => setName(e.target.value)} /></label>
    </Dialog>
  )
}
function FriendCommandDialog({kind, friend, accountId, onClose, onDone}: {kind: 'reset' | 'remove'; friend: CompanionFriend; accountId: string; onClose: () => void; onDone: () => void}) {
  const {t} = useI18n()
  const [busy, setBusy] = useState(false)
  return <ConfirmDialog title={t(kind === 'reset' ? 'chat.resetTitle' : 'chat.removeTitle')} danger busy={busy}
    body={<><p>{t(kind === 'reset' ? 'chat.resetDesc' : 'chat.removeDesc', {name: friend.name})}</p><p className="ew-faint ew-small">{friend.name} · {t('friends.source', {name: friend.source_name})} · epoch {friend.epoch}</p></>}
    confirmLabel={t(kind === 'reset' ? 'chat.reset' : 'chat.remove')} onCancel={onClose}
    onConfirm={async () => {
      setBusy(true)
      try { if (kind === 'reset') await api.friends.reset(friend.id, friend.epoch, accountId); else await api.friends.remove(friend.id, friend.epoch, accountId); onClose(); onDone() }
      catch { setBusy(false); toast(t('error.generic'), 'error') }
    }} />
}
function CorrectionDialog({onClose, onSubmit}: {onClose: () => void; onSubmit: (text: string) => Promise<void>}) {
  const {t} = useI18n()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <Dialog title={t('chat.correctTitle')} onClose={onClose} initialFocus="textarea" footer={<>
      <button type="button" className="ew-btn ghost" onClick={onClose}>{t('common.cancel')}</button>
      <button type="button" className="ew-btn primary" disabled={busy || !text.trim()} onClick={async () => { setBusy(true); try { await onSubmit(text.trim()) } catch { setBusy(false); toast(t('error.generic'), 'error') } }}><PencilLine aria-hidden="true" />{t('common.confirm')}</button></>}>
      <p className="ew-muted">{t('chat.correctDesc')}</p>
      <label className="ew-field"><span>{t('chat.correctLabel')}</span><textarea className="ew-textarea" value={text} maxLength={400} onChange={e => setText(e.target.value)} /></label>
    </Dialog>
  )
}
function OlderConversations({friend, currentId}: {friend: CompanionFriend; currentId: string}) {
  const {t, lang} = useI18n()
  const [items, setItems] = useState<{id: string; friend_epoch: number; status: string; turns: number; updated_at: string}[]>([])
  const [viewing, setViewing] = useState<PrivateSnapshot | null>(null)
  useEffect(() => { api.friends.conversations(friend.id).then(r => setItems(r.items.filter(c => c.id !== currentId))).catch(() => setItems([])) }, [friend.id, currentId])
  if (!items.length) return null
  return (
    <section className="ew-older">
      <p className="ew-tools-caption">{t('chat.history')}</p>
      {items.map(c => <button key={c.id} type="button" className="ew-btn ghost wide align-start small" onClick={async () => setViewing(await api.chat.read(c.id, friend.id, c.friend_epoch))}>
        epoch {c.friend_epoch} · {c.turns} · {formatTime(c.updated_at, lang)} <span className="ew-chip">{t('chat.readOnly')}</span></button>)}
      {viewing && <Dialog title={`${t('chat.readOnly')} · epoch ${viewing.conversation.friend_epoch}`} onClose={() => setViewing(null)} wide>
        <div className="ew-readonly-log">
          {viewing.history.turns.map(turn => <div key={turn.turn_id} className="ew-turn">
            {turn.player_expression && <PlayerLine><RichText text={turn.player_expression} /></PlayerLine>}
            {turn.visible_segments.filter(s => s.availability !== 'withdrawn').map(s => s.kind === 'narration' ? <NarrationLine key={s.segment_id}><RichText text={s.text} action /></NarrationLine>
              : <p key={s.segment_id} className={`ew-plain-line ${s.kind === 'action' ? 'ew-line-action' : ''}`}>{s.kind === 'action' ? <em className="ew-act">{s.text}</em> : <RichText text={s.text} />}</p>)}
          </div>)}
        </div>
      </Dialog>}
    </section>
  )
}
