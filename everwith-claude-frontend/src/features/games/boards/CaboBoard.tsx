import {useEffect, useState} from 'react'
import type {CSSProperties, ReactNode} from 'react'
import {Check, Eye, Hand, Layers, Megaphone, RotateCcw, Shuffle, Trash2, X} from 'lucide-react'
import * as cabo from '../../../games/engines/cabo/engine'
import type {CaboAbility, CaboCardView, CaboObservation, CaboScoreRow} from '../../../games/engines/cabo/engine'
import {useI18n} from '../../../app/i18n'
import {classNames} from '../../../lib/util'
import type {Lang} from '../../../lib/util'
import {ActionBar, GAME_ASSETS, seatColor, useBoardAsset, useBoardText, useRevisionState} from './shared'
import type {BoardProps} from './shared'

/**
 * CABO (Shareful procedures + PROVISIONAL component slice). Values are shown only when the
 * projection says so: public face-up cards, the seat's own drawn card, or an authorised
 * private reveal until it is acknowledged. Remembered cards carry a “known” badge WITHOUT
 * a number. Card numerals, 6/9 marks and ability text are drawn by code over the art.
 */
type Sel = {own: string[]; other: string | null; call: boolean}
const EMPTY: Sel = {own: [], other: null, call: false}
const ART_DIR = `${GAME_ASSETS}/cabo/card-rank-art`

const TEXT = {
  zh: {
    round: '第 {n} 轮', deck: '牌堆 {n}', discardPile: '弃牌堆 {n}', drawn: '抽到的牌', provisional: '组件与能力为临时假设（未核实）',
    legend: '临时组件：0 与 13 各 2 张、1–12 各 4 张；7/8 偷看自己 · 9/10 窥探他人 · 11/12 与他人盲换。', total: '累计 {n}', resetUsed: '已用过 100→50',
    caller: '{name} 叫了 CABO：还剩 {n} 人行动', called: '叫了 CABO', you: '你', known: '已知', knownLabel: '你看过这张（不显示数字，凭记忆）',
    cardFaceDown: '{owner} 的牌 · 位置 {slot} · 盖着', cardFaceUp: '{owner} 的牌 · 位置 {slot} · {value}', cardDiscard: '弃牌堆顶：{value}', cardDrawnHidden: '{name} 抽到的牌（盖着）', cardDrawn: '抽到的牌：{value}',
    peek: '偷看', peekDetail: '看自己的一张', spy: '窥探', spyDetail: '看别人的一张', swap: '交换', swapDetail: '与别人盲换一张',
    setupPrompt: '开局私看：选择你自己的两张牌（只有你能看到）。', setupConfirm: '私看这两张', revealPrompt: '只有你看得到这些牌。记住后点“记住了”，牌会立刻盖回。', ack: '记住了，盖回',
    turnPrompt: '轮到你：从牌堆抽一张、拿弃牌堆顶的牌（必须换入），或叫 CABO。', drawDeck: '从牌堆抽', drawDiscard: '拿弃牌顶 {value}（必须换入）', call: '叫 CABO',
    callPrompt: '叫 CABO 代替本回合抽牌；其余每人再走一次后计分。叫错（不是最低）要多加 5 分。', confirmCall: '确认叫 CABO',
    drawnPrompt: '你抽到了 {value}。选你的牌换入，或者弃掉{ability}。', drawnAbility: '（弃掉时可使用能力：{name}）', exchangePrompt: '从弃牌堆拿了 {value}：必须换入。选择要换掉的牌。',
    exchangeSel: '用 {value} 换掉选中的 {n} 张', exchangeMulti: '选 2–4 张时：同值则一起换成这一张；不同值则全部公开后盖回，抽到的牌被弃掉。', exchange: '换入',
    discard: '弃掉', discardAbility: '弃掉并{name}', abilityPeek: '偷看：选你自己一张盖着的牌。', abilitySpy: '窥探：选别人一张盖着的牌。', abilitySwap: '交换：选你的一张和别人的一张（盲换，不看）。',
    abilityConfirm: '确认', abilityCancel: '放弃能力', cancel: '取消选择', otherTurn: '{name}：{phase}', paused: '暂停中：可以先聊聊，再点“继续”。',
    phase_setup: '开局私看', phase_reveal: '私看中', phase_turn: '考虑中', phase_drawn: '抽到一张牌', phase_exchange: '换入弃牌', phase_ability: '使用能力', phase_roundEnd: '本轮结束', phase_ended: '已结束',
    roundEnd: '第 {n} 轮计分', nextRound: '开始下一轮', ended: '有人累计超过 100：本局结束，结果已锁定。', abandoned: '本局已放弃（只读）',
    col_player: '玩家', col_cards: '手牌', col_sum: '合计', col_gain: '本轮加分', col_total: '累计', reason_shootingTheMoon: '射月（12/12/13/13）', reason_lowest: '最低：不加分', reason_caboFailed: '叫 CABO 失败 +5', reason_cardSum: '加牌面和',
    resetNote: '恰好 100 → 回到 50', recent: '最新：', empty: '空位', hand: '{name} 的手牌', selectedN: '已选 {n}',
  },
  en: {
    round: 'Round {n}', deck: 'Deck {n}', discardPile: 'Discard {n}', drawn: 'Drawn card', provisional: 'Components & abilities are provisional (unverified)',
    legend: 'Provisional components: two each of 0 and 13, four each of 1–12; 7/8 peek own · 9/10 spy another · 11/12 blind-swap.', total: 'Total {n}', resetUsed: '100→50 used',
    caller: '{name} called CABO: {n} player(s) left to act', called: 'Called CABO', you: 'You', known: 'Known', knownLabel: 'You have seen this card (number not shown — remember it)',
    cardFaceDown: '{owner}\'s card · slot {slot} · face down', cardFaceUp: '{owner}\'s card · slot {slot} · {value}', cardDiscard: 'Discard top: {value}', cardDrawnHidden: 'Card drawn by {name} (face down)', cardDrawn: 'Drawn card: {value}',
    peek: 'Peek', peekDetail: 'look at one of yours', spy: 'Spy', spyDetail: 'look at another\'s', swap: 'Swap', swapDetail: 'blind-swap with another',
    setupPrompt: 'Opening peek: choose two of your own cards (only you see them).', setupConfirm: 'Peek at these two', revealPrompt: 'Only you can see these. Press “Got it” and they turn face down at once.', ack: 'Got it, turn down',
    turnPrompt: 'Your turn: draw from the deck, take the discard (must exchange), or call CABO.', drawDeck: 'Draw from deck', drawDiscard: 'Take discard {value} (must exchange)', call: 'Call CABO',
    callPrompt: 'Calling CABO replaces your draw; everyone else gets one more turn, then scoring. A wrong call (not lowest) adds 5.', confirmCall: 'Confirm CABO',
    drawnPrompt: 'You drew {value}. Choose cards to exchange, or discard it{ability}.', drawnAbility: ' (discarding can use: {name})', exchangePrompt: 'You took {value} from the discard: you must exchange. Choose the card(s) to replace.',
    exchangeSel: 'Exchange {n} selected card(s) for {value}', exchangeMulti: 'With 2–4 cards: if all match they become this one card; otherwise they are revealed, turned back down, and the drawn card is discarded.', exchange: 'Exchange',
    discard: 'Discard', discardAbility: 'Discard & {name}', abilityPeek: 'Peek: choose one of your face-down cards.', abilitySpy: 'Spy: choose another player\'s face-down card.', abilitySwap: 'Swap: choose one of yours and one of another player\'s (blind).',
    abilityConfirm: 'Confirm', abilityCancel: 'Skip ability', cancel: 'Clear selection', otherTurn: '{name}: {phase}', paused: 'Paused: chat first, then press Continue.',
    phase_setup: 'opening peek', phase_reveal: 'peeking', phase_turn: 'thinking', phase_drawn: 'holding a drawn card', phase_exchange: 'exchanging the discard', phase_ability: 'using an ability', phase_roundEnd: 'round over', phase_ended: 'finished',
    roundEnd: 'Round {n} scoring', nextRound: 'Start next round', ended: 'Someone passed 100: the game is over and the result is locked.', abandoned: 'Game abandoned (read-only)',
    col_player: 'Player', col_cards: 'Hand', col_sum: 'Sum', col_gain: 'Added', col_total: 'Total', reason_shootingTheMoon: 'Shooting the moon (12/12/13/13)', reason_lowest: 'Lowest: adds 0', reason_caboFailed: 'Failed CABO +5', reason_cardSum: 'Adds card sum',
    resetNote: 'Exactly 100 → back to 50', recent: 'Latest: ', empty: 'empty slot', hand: '{name}\'s hand', selectedN: '{n} selected',
  },
}

type ArtState = {ranks: (string | null)[]; back: string | null} | null
let artLoad: Promise<ArtState> | null = null
/** Loads and validates the public rank-art manifest once; any mismatch falls back to code-drawn cards. */
function loadArt(): Promise<ArtState> {
  artLoad ??= fetch(`${ART_DIR}/manifest.json`, {credentials: 'same-origin'}).then(r => r.ok ? r.json() : null).then((m: {schema?: string; template?: string; ranks?: {key: string; asset: {path: string; sha256: string; noBakedText: boolean} | null}[]; back?: {key: string; asset: {path: string; sha256: string; noBakedText: boolean} | null}} | null) => {
    if (!m || m.schema !== 'cabo-rank-art/1' || m.template !== 'illustration-print/1' || !Array.isArray(m.ranks) || m.ranks.length !== 14) return null
    const url = (entry: {key: string; asset: {path: string; sha256: string; noBakedText: boolean} | null} | undefined, key: string) => {
      const a = entry?.asset
      if (!entry || entry.key !== key || !a || a.noBakedText !== true || !/^[a-f0-9]{64}$/.test(a.sha256)) return null
      const file = a.path.split('/').pop() ?? ''
      return file === `${key}-${a.sha256}.webp` ? `${ART_DIR}/${file}` : null
    }
    return {ranks: m.ranks.map((e, i) => url(e, `rank-${i}`)), back: url(m.back, 'back')}
  }).catch(() => null)
  return artLoad
}
function useCaboArt() {
  const [art, setArt] = useState<ArtState>(null)
  useEffect(() => { let live = true; void loadArt().then(a => { if (live) setArt(a) }); return () => { live = false } }, [])
  return art
}

export function CaboCard({value, art, back, size = 'md', known = false, selected = false, onClick, label, testId, className, lang, reveal = false}: {
  value: number | null; art: string | null; back: string | null; size?: 'lg' | 'md' | 'sm'; known?: boolean; selected?: boolean; onClick?: () => void; label: string; testId?: string; className?: string; lang: Lang; reveal?: boolean
}) {
  const ab = value === null ? null : cabo.ability(value)
  const words = TEXT[lang]
  const face = value === null
    ? <span className="cb-back" style={back ? {backgroundImage: `url("${back}")`} : undefined} aria-hidden="true"><span className="cb-brand">C A B O</span></span>
    : <span className={classNames('cb-front', !art && 'no-art')} aria-hidden="true">
      {art && <span className="cb-art" style={{backgroundImage: `url("${art}")`}} />}
      {!art && <span className="cb-center-digit">{value}{(value === 6 || value === 9) && <i className="cb-underline" />}</span>}
      <span className="cb-corner tl">{value}{(value === 6 || value === 9) && <i className="cb-underline" />}</span>
      <span className="cb-corner br">{value}{(value === 6 || value === 9) && <i className="cb-underline" />}</span>
      <span className="cb-footer">{ab ? <><b>{words[ab]}</b><small>{words[`${ab}Detail` as 'peekDetail']}</small></> : <span className="cb-brand-small">C A B O</span>}</span>
    </span>
  const cls = classNames('cb-card', `size-${size}`, value === null ? 'is-down' : 'is-up', selected && 'is-selected', onClick && 'is-clickable', reveal && 'is-reveal', className)
  // The printed footer shows the short ability name; the full rule text is in the label.
  const fullLabel = ab ? `${label} · ${words[ab]}（${words[`${ab}Detail` as 'peekDetail']}）` : label
  const badge = known && value === null ? <span className="cb-known" aria-hidden="true"><Eye />{words.known}</span> : null
  return onClick
    ? <button type="button" className={cls} aria-pressed={selected} aria-label={fullLabel} title={ab ? fullLabel : undefined} data-testid={testId} onClick={onClick}>{face}{badge}</button>
    : <span className={cls} role="img" aria-label={fullLabel} title={ab ? fullLabel : undefined} data-testid={testId}>{face}{badge}</span>
}

export function CaboBoard({view, pending, act, seatName, readOnly}: BoardProps) {
  const {lang} = useI18n()
  const bt = useBoardText(TEXT)
  const asset = useBoardAsset()
  const art = useCaboArt()
  const v = view.player_view as CaboObservation
  const [sel, setSel] = useRevisionState<Sel>(EMPTY, view.revision)
  const active = view.lifecycle === 'active'
  const myTurn = active && !readOnly && (v.current === 0 || v.phase === 'roundEnd') && !v.ended
  const me = v.players[0]
  const artFor = (value: number) => art?.ranks[value] ? asset(art.ranks[value]!) : null
  const backUrl = art?.back ? asset(art.back) : null
  const reveal = v.privateReveal && v.privateReveal.player === 0 ? new Map(v.privateReveal.cards.map(c => [c.id, c.value])) : new Map<string, number>()
  const known = (id: string) => typeof v.knowledge[id] === 'number'
  const abilityName = (a: CaboAbility) => bt(a)
  const drawnValue = v.drawn?.value ?? null

  const toggleOwn = (id: string, max: number) => setSel(s => ({...s, call: false, own: s.own.includes(id) ? s.own.filter(x => x !== id) : max === 1 ? [id] : s.own.length >= max ? s.own : [...s.own, id]}))
  const toggleOther = (id: string) => setSel(s => ({...s, call: false, other: s.other === id ? null : id}))

  // Which cards are selectable right now (never offers an illegal target).
  const ownMode: null | {max: number; faceDownOnly: boolean} = !myTurn ? null
    : v.phase === 'setup' ? {max: 2, faceDownOnly: false}
    : v.phase === 'drawn' || v.phase === 'exchange' ? {max: 4, faceDownOnly: false}
    : v.phase === 'ability' && v.activeAbility === 'peek' ? {max: 1, faceDownOnly: true}
    : v.phase === 'ability' && v.activeAbility === 'swap' ? {max: 1, faceDownOnly: false} : null
  const otherMode = myTurn && v.phase === 'ability' && (v.activeAbility === 'spy' || v.activeAbility === 'swap') ? {faceDownOnly: v.activeAbility === 'spy'} : null

  const cardLabel = (owner: number, c: CaboCardView, shown: number | null) => {
    const base = shown === null ? bt('cardFaceDown', {owner: seatName(owner), slot: c.slot + 1}) : bt('cardFaceUp', {owner: seatName(owner), slot: c.slot + 1, value: shown})
    return known(c.id) && shown === null ? `${base} · ${bt('knownLabel')}` : base
  }
  const hand = (p: CaboObservation['players'][number], size: 'lg' | 'md' | 'sm') => {
    const bySlot = new Map(p.cards.map(c => [c.slot, c]))
    const slots = Math.max(4, ...p.cards.map(c => c.slot + 1))
    return (
      <div className={classNames('cb-hand', `size-${size}`)} aria-label={bt('hand', {name: seatName(p.id)})}>
        {Array.from({length: slots}, (_, slot) => {
          const c = bySlot.get(slot)
          if (!c) return <span key={`empty-${slot}`} className={classNames('cb-slot-empty', `size-${size}`)} aria-label={bt('empty')} role="img" />
          const shown = reveal.has(c.id) ? reveal.get(c.id)! : c.faceUp || c.value !== null ? c.value : null
          const isOwn = p.id === 0
          const selectable = isOwn ? !!ownMode && (!ownMode.faceDownOnly || !c.faceUp) : !!otherMode && (!otherMode.faceDownOnly || !c.faceUp)
          const selected = isOwn ? sel.own.includes(c.id) : sel.other === c.id
          return <CaboCard key={c.id} value={shown} art={shown === null ? null : artFor(shown)} back={backUrl} size={size} known={known(c.id)} selected={selected} lang={lang} reveal={reveal.has(c.id)}
            label={cardLabel(p.id, c, shown)} testId={isOwn ? `cabo-own-${slot}` : `cabo-seat${p.id}-${slot}`}
            onClick={selectable ? () => isOwn ? toggleOwn(c.id, ownMode!.max) : toggleOther(c.id) : undefined} />
        })}
      </div>
    )
  }

  // ----- action strip -----
  let bar: ReactNode
  const cancelBtn = (sel.own.length > 0 || sel.other || sel.call) && <button type="button" className="ew-btn ghost" data-testid="cabo-cancel" onClick={() => setSel(EMPTY)}><X aria-hidden="true" />{bt('cancel')}</button>
  if (view.lifecycle === 'abandoned') bar = <ActionBar prompt={bt('abandoned')} />
  else if (v.ended || view.lifecycle === 'ended') bar = <ActionBar prompt={bt('ended')} tone="turn" />
  else if (v.phase === 'roundEnd') bar = (
    <ActionBar tone="turn" testId="cabo-actions" prompt={bt('roundEnd', {n: v.round})}>
      <button type="button" className="ew-btn primary" data-testid="cabo-next-round" disabled={pending || !active} onClick={() => void act({type: 'nextRound'})}><RotateCcw aria-hidden="true" />{bt('nextRound')}</button>
    </ActionBar>
  )
  else if (!myTurn) bar = <ActionBar prompt={view.ai_hold ? bt('paused') : bt('otherTurn', {name: seatName(v.current), phase: bt(`phase_${v.phase}`)})} />
  else if (v.phase === 'setup') bar = (
    <ActionBar tone="turn" testId="cabo-actions" prompt={bt('setupPrompt')} detail={sel.own.length ? bt('selectedN', {n: sel.own.length}) : undefined}>
      {cancelBtn}
      <button type="button" className="ew-btn primary" data-testid="cabo-peek-confirm" disabled={pending || sel.own.length !== 2} onClick={() => void act({type: 'initialPeek', cards: sel.own})}><Eye aria-hidden="true" />{bt('setupConfirm')}</button>
    </ActionBar>
  )
  else if (v.phase === 'reveal') bar = (
    <ActionBar tone="warn" testId="cabo-actions" prompt={bt('revealPrompt')}>
      <button type="button" className="ew-btn primary" data-testid="cabo-ack" disabled={pending} onClick={() => void act({type: 'ack'})}><Check aria-hidden="true" />{bt('ack')}</button>
    </ActionBar>
  )
  else if (v.phase === 'turn' && sel.call) bar = (
    <ActionBar tone="select" testId="cabo-actions" prompt={bt('callPrompt')}>
      {cancelBtn}
      <button type="button" className="ew-btn primary" data-testid="cabo-call-confirm" disabled={pending} onClick={() => void act({type: 'call'})}><Megaphone aria-hidden="true" />{bt('confirmCall')}</button>
    </ActionBar>
  )
  else if (v.phase === 'turn') {
    const top = v.discard[v.discard.length - 1]
    bar = (
      <ActionBar tone="turn" testId="cabo-actions" prompt={bt('turnPrompt')}>
        <button type="button" className="ew-btn primary" data-testid="cabo-draw-deck" disabled={pending} onClick={() => void act({type: 'draw', source: 'deck'})}><Layers aria-hidden="true" />{bt('drawDeck')}</button>
        <button type="button" className="ew-btn" data-testid="cabo-draw-discard" disabled={pending || !top} onClick={() => void act({type: 'draw', source: 'discard'})}><Hand aria-hidden="true" />{bt('drawDiscard', {value: top?.value ?? '—'})}</button>
        {v.caller === null && <button type="button" className="ew-btn ghost" data-testid="cabo-call" onClick={() => setSel({...EMPTY, call: true})}><Megaphone aria-hidden="true" />{bt('call')}</button>}
      </ActionBar>
    )
  } else if (v.phase === 'drawn' || v.phase === 'exchange') {
    const ab = drawnValue === null ? null : cabo.ability(drawnValue)
    bar = (
      <ActionBar tone="select" testId="cabo-actions"
        prompt={v.phase === 'exchange' ? bt('exchangePrompt', {value: drawnValue ?? '?'}) : bt('drawnPrompt', {value: drawnValue ?? '?', ability: ab ? bt('drawnAbility', {name: abilityName(ab)}) : ''})}
        detail={<span>{sel.own.length ? bt('exchangeSel', {n: sel.own.length, value: drawnValue ?? '?'}) : ''} <span className="ew-faint">{bt('exchangeMulti')}</span></span>}>
        {cancelBtn}
        <button type="button" className="ew-btn primary" data-testid="cabo-exchange" disabled={pending || sel.own.length === 0} onClick={() => void act({type: 'exchange', cards: sel.own})}><Shuffle aria-hidden="true" />{bt('exchange')}</button>
        {v.phase === 'drawn' && <button type="button" className="ew-btn" data-testid="cabo-discard" disabled={pending} onClick={() => void act({type: 'discard', useAbility: false})}><Trash2 aria-hidden="true" />{bt('discard')}</button>}
        {v.phase === 'drawn' && ab && <button type="button" className="ew-btn" data-testid="cabo-discard-ability" disabled={pending} onClick={() => void act({type: 'discard', useAbility: true})}><Eye aria-hidden="true" />{bt('discardAbility', {name: abilityName(ab)})}</button>}
      </ActionBar>
    )
  } else if (v.phase === 'ability') {
    const a = v.activeAbility!
    const ready = a === 'peek' ? sel.own.length === 1 : a === 'spy' ? !!sel.other : sel.own.length === 1 && !!sel.other
    const action = a === 'peek' ? {type: 'peek', card: sel.own[0]} : a === 'spy' ? {type: 'peek', card: sel.other} : {type: 'swap', own: sel.own[0], other: sel.other}
    bar = (
      <ActionBar tone="select" testId="cabo-actions" prompt={a === 'peek' ? bt('abilityPeek') : a === 'spy' ? bt('abilitySpy') : bt('abilitySwap')}>
        {cancelBtn}
        <button type="button" className="ew-btn ghost" data-testid="cabo-ability-cancel" disabled={pending} onClick={() => void act({type: 'cancelAbility'})}>{bt('abilityCancel')}</button>
        <button type="button" className="ew-btn primary" data-testid="cabo-ability-confirm" disabled={pending || !ready} onClick={() => void act(action)}><Check aria-hidden="true" />{bt('abilityConfirm')}</button>
      </ActionBar>
    )
  }

  const top = v.discard[v.discard.length - 1]
  const drawer = v.drawn ? v.current : null
  const others = v.players.filter(p => p.id !== 0)
  return (
    <div className={classNames('gb-board cb-board', `players-${v.players.length}`)} data-phase={v.phase} data-current={v.current} data-round={v.round} style={{'--cb-surface': `url("${asset(`${GAME_ASSETS}/cabo/embedded-surface-1.webp`)}")`} as CSSProperties}>
      <div className="cb-top">
        <strong>{bt('round', {n: v.round})}</strong>
        <span className="ew-chip warn" title={bt('legend')}>{bt('provisional')}</span>
        {v.caller !== null && !['roundEnd', 'ended'].includes(v.phase) && <span className="ew-chip danger"><Megaphone aria-hidden="true" />{bt('caller', {name: seatName(v.caller), n: v.finalQueue.length})}</span>}
        {view.log.length > 0 && <span className="gb-recent"><span className="ew-faint">{bt('recent')}</span>{view.log[view.log.length - 1].summary[lang]}</span>}
      </div>
      {(v.phase === 'roundEnd' || v.phase === 'ended') && v.roundResults.length > 0 && <ScoreTable rows={v.roundResults} round={v.round} seatName={seatName} bt={bt} />}
      <div className="cb-opponents">
        {others.map(p => (
          <section key={p.id} className={classNames('cb-seat', p.id === v.current && active && !['roundEnd', 'ended'].includes(v.phase) && 'is-current')} data-seat={p.id} aria-label={seatName(p.id)}>
            <header><span className="ew-seat-dot" style={{background: seatColor(p.id)}} aria-hidden="true" /><strong>{seatName(p.id)}</strong>
              <span className="cb-total">{bt('total', {n: p.total})}</span>{v.caller === p.id && <span className="ew-chip danger small">{bt('called')}</span>}{p.resetUsed && <small className="ew-faint">{bt('resetUsed')}</small>}</header>
            {hand(p, 'sm')}
            {drawer === p.id && v.drawn && <div className="cb-seat-drawn"><small>{bt('drawn')}</small><CaboCard value={v.drawn.value} art={v.drawn.value === null ? null : artFor(v.drawn.value)} back={backUrl} size="sm" lang={lang}
              label={v.drawn.value === null ? bt('cardDrawnHidden', {name: seatName(p.id)}) : bt('cardDrawn', {value: v.drawn.value})} /></div>}
          </section>
        ))}
      </div>
      <div className="cb-center">
        <div className="cb-pile">
          <CaboCard value={null} art={null} back={backUrl} size="md" lang={lang} label={bt('deck', {n: v.deck.length})} testId="cabo-deck" />
          <span className="cb-pile-label">{bt('deck', {n: v.deck.length})}</span>
        </div>
        <div className="cb-pile">
          {top ? <CaboCard value={top.value} art={artFor(top.value)} back={backUrl} size="md" lang={lang} label={bt('cardDiscard', {value: top.value})} testId="cabo-discard-top" /> : <span className="cb-slot-empty size-md" />}
          <span className="cb-pile-label">{bt('discardPile', {n: v.discard.length})}</span>
        </div>
        {drawer === 0 && v.drawn && <div className="cb-pile is-drawn">
          <CaboCard value={v.drawn.value} art={v.drawn.value === null ? null : artFor(v.drawn.value)} back={backUrl} size="md" lang={lang} reveal label={v.drawn.value === null ? bt('drawn') : bt('cardDrawn', {value: v.drawn.value})} testId="cabo-drawn" />
          <span className="cb-pile-label">{bt('drawn')}</span>
        </div>}
        <p className="cb-legend ew-faint">{bt('legend')}</p>
      </div>
      <section className={classNames('cb-me', v.current === 0 && active && !['roundEnd', 'ended'].includes(v.phase) && 'is-current')} aria-label={seatName(0)} data-seat={0}>
        <header><span className="ew-seat-dot" style={{background: seatColor(0)}} aria-hidden="true" /><strong>{seatName(0)}</strong><span className="cb-total">{bt('total', {n: me.total})}</span>
          {v.caller === 0 && <span className="ew-chip danger small">{bt('called')}</span>}{me.resetUsed && <small className="ew-faint">{bt('resetUsed')}</small>}</header>
        {hand(me, 'lg')}
      </section>
      {bar}
      <span hidden data-testid="cabo-state" data-phase={v.phase} data-current={v.current} data-drawn={drawnValue ?? ''} data-ability={v.activeAbility ?? ''} data-totals={v.players.map(p => p.total).join(',')} data-caller={v.caller ?? ''} />
    </div>
  )
}

function ScoreTable({rows, round, seatName, bt}: {rows: CaboScoreRow[]; round: number; seatName: (s: number) => string; bt: (k: string, vars?: Record<string, string | number>) => string}) {
  return (
    <section className="cb-scores" aria-labelledby="cabo-score-title" data-testid="cabo-scores">
      <h3 id="cabo-score-title">{bt('roundEnd', {n: round})}</h3>
      <table>
        <thead><tr><th scope="col">{bt('col_player')}</th><th scope="col">{bt('col_cards')}</th><th scope="col">{bt('col_sum')}</th><th scope="col">{bt('col_gain')}</th><th scope="col">{bt('col_total')}</th></tr></thead>
        <tbody>{rows.map(r => (
          <tr key={r.player}>
            <th scope="row"><span className="ew-seat-dot" style={{background: seatColor(r.player)}} aria-hidden="true" /> {seatName(r.player)}</th>
            <td className="cb-values">{r.values.map((x, i) => <span key={i} className="cb-mini-value">{x}{(x === 6 || x === 9) && <i className="cb-underline" />}</span>)}</td>
            <td>{r.sum}</td>
            <td>+{r.gain} <small className="ew-faint">{bt(`reason_${r.reason}`)}</small></td>
            <td>{r.before ?? '—'} → <strong>{r.after ?? '—'}</strong>{r.reset && <small className="ew-faint"> · {bt('resetNote')}</small>}</td>
          </tr>
        ))}</tbody>
      </table>
    </section>
  )
}
