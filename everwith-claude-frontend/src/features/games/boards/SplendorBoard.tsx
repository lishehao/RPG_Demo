import {useMemo, useState} from 'react'
import type {CSSProperties, ReactNode} from 'react'
import {BookmarkPlus, Check, Crown, ShoppingBag, Undo2, X} from 'lucide-react'
import * as rules from '../../../games/engines/splendor/splendor/rules'
import type {SplendorAction, SplendorColor, SplendorGem, SplendorPlayer, SplendorState} from '../../../games/engines/splendor/splendor/rules'
import {useI18n} from '../../../app/i18n'
import {classNames} from '../../../lib/util'
import {ActionBar, cropStyle, seatColor, useBoardAsset, useBoardText, useRevisionState} from './shared'
import type {BoardProps} from './shared'
import {GEM_IMAGES, GEM_TONES, TABLE_CLOTH, TIER_BACKS, cardArt, nobleArt} from './splendor-art'

/**
 * Splendor. The board renders the seat-0 projection; legality comes from the frozen
 * engine's own `legalActions` run on that projection (saved games keep their own rules
 * profile — a legacy v1 save is never upgraded). Unknown blind reserves of other seats
 * are tier backs only: no card id, no click target, no tooltip.
 */
type ProjReserve = {card: string | null; tier: 1 | 2 | 3 | null; hidden: boolean}
type ProjPlayer = Omit<SplendorPlayer, 'reserved'> & {reserved: ProjReserve[]}
type SplendorView = Omit<SplendorState, 'players' | 'decks'> & {decks: Record<1 | 2 | 3, number>; players: ProjPlayer[]}
type Sel = null
  | {kind: 'take'; colors: SplendorColor[]}
  | {kind: 'card'; id: string; from: 'market' | 'reserve'}
  | {kind: 'deck'; tier: 1 | 2 | 3}
  | {kind: 'return'; colors: SplendorGem[]}
  | {kind: 'noble'; id: string}

const COLORS = rules.COLORS as SplendorColor[]
const ALL = rules.ALL as SplendorGem[]
const POSITIONS: Record<number, string[]> = {2: ['bottom', 'top'], 3: ['bottom', 'left', 'right'], 4: ['bottom', 'left', 'top', 'right']}
const CARD_ASPECT = 63 / 88

const TEXT = {
  zh: {
    diamond: '钻石', sapphire: '蓝宝石', emerald: '祖母绿', ruby: '红宝石', onyx: '缟玛瑙', gold: '黄金',
    round: '第 {n} 回合', ending: '已有人达到 15 分：补齐本轮后结算', v2: '2024 基础规则 v2', score: '{n} 分', tokens: '宝石 {n}/10', bonus: '永久折扣',
    reserved: '预留 {n}/3', nobles: '贵族', noblesN: '贵族 {n}', bank: '公共宝石池', deck: '{tier} 级牌堆 · 剩 {n} 张', deckShort: '剩 {n}', tier: '{tier} 级',
    you: '你', hiddenReserve: '暗预留（{tier} 级牌背，内容不公开）', publicReserve: '公开预留', emptySlot: '空预留位',
    card: '{tier} 级 · {gem}折扣 +1 · {points} 分 · 成本 {cost}', cardName: '「{name}」', noble: '贵族 · 3 分 · 需要 {cost}',
    affordable: '可购买', missing: '缺 {n}', price: '你的价格：{cost}', pay: '支付：{pay}', payNothing: '无需支付宝石', goldNote: '（含 {n} 枚黄金补差）',
    reserveGold: '预留后得到 1 枚黄金', reserveNoGold: '黄金已空：预留不得黄金', reserveFull: '预留已满 3 张',
    takePrompt: '拿取：{list}', takeHint3: '有三种以上颜色时，拿三种不同颜色各一枚；或在某色至少 4 枚时拿两枚同色。', takeMore: '再选 {n} 种不同颜色。', takeRule: '这个组合不合规则：{why}',
    takeDoubleNeed4: '拿两枚同色前，公共池里该色至少要有 4 枚', takeGeneric: '请按池中现有颜色选择', takeOk: '可以确认；也可以改选。',
    turnPrompt: '轮到你：点公共池宝石拿取，或点一张发展卡购买 / 预留，或点牌堆盲预留。', otherTurn: '{name} 正在行动…', paused: '暂停中：可以先聊聊，再点“继续”。',
    buy: '购买', reserve: '预留', blind: '盲预留 {tier} 级', confirmTake: '确认拿取', cancel: '取消', blindPrompt: '从 {tier} 级牌堆顶盲预留一张（只有你能看到）。',
    returnPrompt: '你有 {n} 枚宝石，需要归还 {k} 枚（点你的宝石选择）。', returnList: '归还：{list}', confirmReturn: '确认归还', clear: '清空',
    noblePrompt: '你同时满足多位贵族的条件：选择本回合来访的一位。', confirmNoble: '请这位贵族来访', ended: '本局已结束，结果已锁定。', abandoned: '本局已放弃（只读）',
    noLegal: '当前没有合法动作。', legacy: '旧版 v1 存档：保持原规则与布局，不自动升级。', recent: '最新：', cardsBought: '已购 {n} 张', total: '共 {n}',
  },
  en: {
    diamond: 'diamond', sapphire: 'sapphire', emerald: 'emerald', ruby: 'ruby', onyx: 'onyx', gold: 'gold',
    round: 'Round {n}', ending: 'Someone reached 15: the round finishes, then scoring', v2: '2024 base rules v2', score: '{n} pts', tokens: 'Gems {n}/10', bonus: 'Bonuses',
    reserved: 'Reserved {n}/3', nobles: 'Nobles', noblesN: 'Nobles {n}', bank: 'Gem supply', deck: 'Tier {tier} deck · {n} left', deckShort: '{n} left', tier: 'Tier {tier}',
    you: 'You', hiddenReserve: 'Blind reserve (tier {tier} back, contents hidden)', publicReserve: 'Public reserve', emptySlot: 'Empty reserve slot',
    card: 'Tier {tier} · {gem} bonus +1 · {points} pts · cost {cost}', cardName: '', noble: 'Noble · 3 pts · needs {cost}',
    affordable: 'Affordable', missing: 'Short {n}', price: 'Your price: {cost}', pay: 'Pay: {pay}', payNothing: 'No gems needed', goldNote: ' (incl. {n} gold)',
    reserveGold: 'Reserving gives you 1 gold', reserveNoGold: 'No gold left: reserving gives no gold', reserveFull: 'You already reserve 3 cards',
    takePrompt: 'Take: {list}', takeHint3: 'With 3+ colours available take three different colours, or two of one colour that has at least 4.', takeMore: 'Pick {n} more different colour(s).', takeRule: 'Not allowed: {why}',
    takeDoubleNeed4: 'two of one colour needs at least 4 in the supply', takeGeneric: 'choose from the colours in the supply', takeOk: 'Ready to confirm, or change it.',
    turnPrompt: 'Your turn: pick gems from the supply, or a card to buy / reserve, or a deck to reserve blind.', otherTurn: '{name} is moving…', paused: 'Paused: chat first, then press Continue.',
    buy: 'Buy', reserve: 'Reserve', blind: 'Blind-reserve tier {tier}', confirmTake: 'Confirm take', cancel: 'Cancel', blindPrompt: 'Reserve the top card of the tier {tier} deck (only you will see it).',
    returnPrompt: 'You hold {n} gems and must return {k} (click your gems).', returnList: 'Return: {list}', confirmReturn: 'Confirm return', clear: 'Clear',
    noblePrompt: 'You meet several nobles: choose the one who visits this turn.', confirmNoble: 'Receive this noble', ended: 'Game over; the result is locked.', abandoned: 'Game abandoned (read-only)',
    noLegal: 'No legal action right now.', legacy: 'Legacy v1 save: original rules and layout kept, never upgraded.', recent: 'Latest: ', cardsBought: '{n} cards bought', total: '{n} total',
  },
}

const toEngine = (v: SplendorView) => ({...v, players: v.players.map(p => ({...p, reserved: p.reserved.map(r => r.card)}))}) as unknown as SplendorState
const sortedKey = (cs: string[]) => [...cs].sort().join('+')
const subMultiset = (a: string[], b: string[]) => { const rest = [...b]; for (const x of a) { const i = rest.indexOf(x); if (i < 0) return false; rest.splice(i, 1) } return true }

function GemImg({gem, className}: {gem: SplendorGem; className?: string}) {
  const asset = useBoardAsset()
  return <img className={classNames('sp-gem-img', className)} src={asset(GEM_IMAGES[gem])} alt="" aria-hidden="true" draggable={false} />
}
function Pips({cost, className}: {cost: Partial<Record<SplendorColor, number>>; className?: string}) {
  return <span className={classNames('sp-pips', className)} aria-hidden="true">{COLORS.filter(c => (cost[c] ?? 0) > 0).map(c => <span key={c} className="sp-pip" style={{'--pip-bg': GEM_TONES[c].bg, '--pip-ink': GEM_TONES[c].ink} as CSSProperties}>{cost[c]}</span>)}</span>
}

export function SplendorBoard({view, pending, act, seatName, readOnly}: BoardProps) {
  const {lang} = useI18n()
  const bt = useBoardText(TEXT)
  const asset = useBoardAsset()
  const v = view.player_view as SplendorView
  const legacy = view.profile === 'splendor-legacy-v1'
  const ev = useMemo(() => toEngine(v), [v])
  const active = view.lifecycle === 'active'
  const myTurn = active && !readOnly && v.current === 0 && !v.ended
  const me = ev.players[0]
  const legal: SplendorAction[] = useMemo(() => myTurn ? rules.legalActions(ev, 0) : [], [myTurn, ev])
  const [sel, setSel] = useRevisionState<Sel>(null, view.revision)
  const [returning, setReturning] = useState(false)

  const takeOptions = legal.filter((a): a is Extract<SplendorAction, {type: 'take'}> => a.type === 'take').map(a => a.colors)
  const takeKeys = new Set(takeOptions.map(sortedKey))
  const buyable = new Set(legal.filter(a => a.type === 'buy').map(a => (a as {card: string}).card))
  const reservable = new Set(legal.filter(a => a.type === 'reserve' && a.card).map(a => (a as {card: string}).card))
  const blindTiers = new Set(legal.filter(a => a.type === 'reserve' && !a.card).map(a => (a as {tier: number}).tier))
  const gem = (c: string) => bt(c)
  const costText = (cost: Partial<Record<string, number>>) => Object.entries(cost).filter(([, n]) => (n ?? 0) > 0).map(([c, n]) => `${n} ${gem(c)}`).join(lang === 'zh' ? '、' : ', ') || '0'
  const cardLabel = (id: string) => { const c = rules.cardById(id); return `${lang === 'zh' ? bt('cardName', {name: c.name}) + ' ' : ''}${bt('card', {tier: c.tier, gem: gem(c.bonus), points: c.points, cost: costText(c.cost)})}` }
  const lastEvent = v.events[v.events.length - 1] as undefined | {id: number; type: string; player: number; colors?: string[]; card?: string | null; noble?: string; bonus?: string}

  const clickBank = (c: SplendorGem) => {
    if (!myTurn || v.phase !== 'action' || c === 'gold') return
    setSel(prev => {
      const colors = prev?.kind === 'take' ? prev.colors : []
      const n = colors.filter(x => x === c).length
      let next: SplendorColor[]
      if (n === 2) next = colors.filter(x => x !== c)
      else if (n === 1) next = colors.length === 1 && v.bank[c] >= 4 ? [c, c] : colors.filter(x => x !== c)
      else if (colors.length === 2 && colors[0] === colors[1]) next = [c]
      else if (colors.length >= 3) next = colors
      else next = [...colors, c as SplendorColor]
      return next.length ? {kind: 'take', colors: next} : null
    })
  }
  const clickOwnToken = (c: SplendorGem) => {
    if (!myTurn || v.phase !== 'return') return
    const excess = rules.total(me.tokens) - 10
    setSel(prev => {
      const colors = prev?.kind === 'return' ? prev.colors : []
      const have = colors.filter(x => x === c).length
      if (have < me.tokens[c] && colors.length < excess) return {kind: 'return', colors: [...colors, c]}
      const next = colors.filter(x => x !== c)
      return next.length ? {kind: 'return', colors: next} : null
    })
  }
  // Each returned gem is its own engine action; the sequence locks the controls until it ends.
  const submitReturn = async (colors: SplendorGem[]) => {
    setReturning(true)
    try { for (const color of colors) { if (!(await act({type: 'return', color}))) break } } finally { setReturning(false) }
  }

  // ----- action strip -----
  let bar: ReactNode
  if (view.lifecycle === 'abandoned') bar = <ActionBar prompt={bt('abandoned')} />
  else if (v.ended || view.lifecycle === 'ended') bar = <ActionBar prompt={bt('ended')} tone="turn" />
  else if (!myTurn) bar = <ActionBar prompt={view.ai_hold ? bt('paused') : bt('otherTurn', {name: seatName(v.current)})} />
  else if (v.phase === 'return') {
    const excess = rules.total(me.tokens) - 10
    const colors = sel?.kind === 'return' ? sel.colors : []
    bar = (
      <ActionBar tone="warn" testId="splendor-actions" prompt={bt('returnPrompt', {n: rules.total(me.tokens), k: excess})} detail={colors.length ? bt('returnList', {list: colors.map(gem).join(lang === 'zh' ? '、' : ', ')}) : undefined}>
        {colors.length > 0 && <button type="button" className="ew-btn ghost" disabled={returning} onClick={() => setSel(null)}><Undo2 aria-hidden="true" />{bt('clear')}</button>}
        <button type="button" className="ew-btn primary" data-testid="splendor-confirm" disabled={pending || returning || colors.length !== excess} onClick={() => void submitReturn(colors)}><Check aria-hidden="true" />{bt('confirmReturn')}</button>
      </ActionBar>
    )
  } else if (v.phase === 'noble') bar = (
    <ActionBar tone="select" testId="splendor-actions" prompt={bt('noblePrompt')}>
      <button type="button" className="ew-btn primary" data-testid="splendor-confirm" disabled={pending || sel?.kind !== 'noble'} onClick={() => sel?.kind === 'noble' && void act({type: 'noble', noble: sel.id})}><Crown aria-hidden="true" />{bt('confirmNoble')}</button>
    </ActionBar>
  )
  else if (sel?.kind === 'take') {
    const valid = takeKeys.has(sortedKey(sel.colors))
    const grow = takeOptions.filter(o => o.length > sel.colors.length && subMultiset(sel.colors, o))
    const doubleShort = sel.colors.length === 2 && sel.colors[0] === sel.colors[1] && v.bank[sel.colors[0]] < 4
    const hint = valid ? (grow.length ? `${bt('takeOk')} ${bt('takeMore', {n: Math.min(...grow.map(o => o.length - sel.colors.length))})}` : bt('takeOk'))
      : grow.length ? bt('takeMore', {n: Math.min(...grow.map(o => o.length - sel.colors.length))}) : bt('takeRule', {why: doubleShort ? bt('takeDoubleNeed4') : bt('takeGeneric')})
    bar = (
      <ActionBar tone="select" testId="splendor-actions" prompt={bt('takePrompt', {list: sel.colors.map(gem).join(lang === 'zh' ? '、' : ', ')})} detail={<span className={valid ? '' : 'ew-error-text'}>{hint}</span>}>
        <button type="button" className="ew-btn ghost" data-testid="splendor-cancel" onClick={() => setSel(null)}><X aria-hidden="true" />{bt('cancel')}</button>
        <button type="button" className="ew-btn primary" data-testid="splendor-confirm" disabled={pending || !valid} onClick={() => void act({type: 'take', colors: sel.colors})}><Check aria-hidden="true" />{bt('confirmTake')}</button>
      </ActionBar>
    )
  } else if (sel?.kind === 'card') {
    const card = rules.cardById(sel.id)
    const price = rules.priceFor(me, card)
    const pay = rules.paymentFor(me, card)
    const canBuy = buyable.has(card.id)
    const canReserve = sel.from === 'market' && reservable.has(card.id)
    bar = (
      <ActionBar tone="select" testId="splendor-actions" prompt={cardLabel(card.id)}
        detail={<span className="sp-detail">
          <span>{bt('price', {cost: costText(price)})}</span>
          <span>{pay ? (rules.total(pay) ? `${bt('pay', {pay: costText(pay)})}${pay.gold ? bt('goldNote', {n: pay.gold}) : ''}` : bt('payNothing')) : bt('missing', {n: rules.missingFor(me, card)})}</span>
          {sel.from === 'market' && <span className="ew-faint">{me.reserved.length >= 3 ? bt('reserveFull') : v.bank.gold > 0 ? bt('reserveGold') : bt('reserveNoGold')}</span>}
        </span>}>
        <button type="button" className="ew-btn ghost" data-testid="splendor-cancel" onClick={() => setSel(null)}><X aria-hidden="true" />{bt('cancel')}</button>
        {sel.from === 'market' && <button type="button" className="ew-btn" data-testid="splendor-reserve" disabled={pending || !canReserve} onClick={() => void act({type: 'reserve', card: card.id})}><BookmarkPlus aria-hidden="true" />{bt('reserve')}</button>}
        <button type="button" className="ew-btn primary" data-testid="splendor-buy" disabled={pending || !canBuy} onClick={() => void act({type: 'buy', card: card.id})}><ShoppingBag aria-hidden="true" />{bt('buy')}</button>
      </ActionBar>
    )
  } else if (sel?.kind === 'deck') bar = (
    <ActionBar tone="select" testId="splendor-actions" prompt={bt('blindPrompt', {tier: sel.tier})} detail={<span className="ew-faint">{v.bank.gold > 0 ? bt('reserveGold') : bt('reserveNoGold')}</span>}>
      <button type="button" className="ew-btn ghost" data-testid="splendor-cancel" onClick={() => setSel(null)}><X aria-hidden="true" />{bt('cancel')}</button>
      <button type="button" className="ew-btn primary" data-testid="splendor-confirm" disabled={pending || !blindTiers.has(sel.tier)} onClick={() => void act({type: 'reserve', tier: sel.tier})}><BookmarkPlus aria-hidden="true" />{bt('blind', {tier: sel.tier})}</button>
    </ActionBar>
  )
  else bar = <ActionBar tone="turn" testId="splendor-actions" prompt={legal.length ? bt('turnPrompt') : bt('noLegal')} detail={<span className="ew-faint">{bt('takeHint3')}</span>} />

  const positions = POSITIONS[v.players.length] ?? POSITIONS[4]
  const myBonus = rules.bonuses(me)
  const flash = (player: number, key: string) => lastEvent && lastEvent.player === player && (
    (lastEvent.type === 'take' && lastEvent.colors?.includes(key)) || (lastEvent.type === 'buy' && lastEvent.bonus === key) || (lastEvent.type === 'return' && key === 'return') ||
    (lastEvent.type === 'reserve' && key === 'reserve') || (lastEvent.type === 'noble' && key === 'noble'))

  const devCard = (id: string, size: 'md' | 'sm' = 'md', from?: 'market' | 'reserve') => {
    const c = rules.cardById(id)
    const art = cardArt(c)
    const afford = !!rules.paymentFor(me, c)
    const missing = afford ? 0 : rules.missingFor(me, c)
    const clickable = !!from && myTurn && v.phase === 'action'
    const selected = sel?.kind === 'card' && sel.id === id
    const inner = <>
      <span className="sp-card-art" style={cropStyle(asset(art.src), art.w, art.h, art.rect, CARD_ASPECT)} aria-hidden="true" />
      <span className="sp-card-head" aria-hidden="true"><b className="sp-points">{c.points || ''}</b><GemImg gem={c.bonus} className="sp-bonus" /></span>
      <Pips cost={c.cost} className="sp-card-cost" />
      {from && size === 'md' && <span className={classNames('sp-afford', afford ? 'is-ok' : 'is-short')} aria-hidden="true">{afford ? bt('affordable') : bt('missing', {n: missing})}</span>}
    </>
    const cls = classNames('sp-card', `size-${size}`, `tier-${c.tier}`, selected && 'is-selected', clickable && 'is-clickable', afford && 'is-affordable')
    return clickable
      ? <button key={id} type="button" className={cls} data-card={id} data-testid={`splendor-card-${id}`} aria-pressed={selected} aria-label={`${cardLabel(id)} · ${afford ? bt('affordable') : bt('missing', {n: missing})}`} onClick={() => setSel(selected ? null : {kind: 'card', id, from: from!})}>{inner}</button>
      : <span key={id} className={cls} data-card={id} role="img" aria-label={cardLabel(id)}>{inner}</span>
  }
  const tierBack = (key: string, tier: 1 | 2 | 3, label: string) => <span key={key} className="sp-card is-back size-sm" role="img" aria-label={label} style={{backgroundImage: `url("${asset(TIER_BACKS[tier])}")`}} />
  const noble = (id: string, size: 'md' | 'sm' = 'md', choosable = false) => {
    const n = rules.nobleById(id), art = nobleArt(id)
    const selected = sel?.kind === 'noble' && sel.id === id
    const inner = <>
      <span className="sp-noble-art" style={cropStyle(asset(art.src), art.w, art.h, art.rect, 1)} aria-hidden="true" />
      <b className="sp-points" aria-hidden="true">3</b>
      <Pips cost={n.cost} className="sp-noble-cost" />
    </>
    const label = `${lang === 'zh' ? `「${n.name}」` : ''}${bt('noble', {cost: costText(n.cost)})}`
    return choosable
      ? <button key={id} type="button" className={classNames('sp-noble', `size-${size}`, 'is-clickable', selected && 'is-selected')} aria-pressed={selected} aria-label={label} data-testid={`splendor-noble-${id}`} onClick={() => setSel({kind: 'noble', id})}>{inner}</button>
      : <span key={id} className={classNames('sp-noble', `size-${size}`)} role="img" aria-label={label}>{inner}</span>
  }

  const playerPanel = (p: ProjPlayer, pos: string) => {
    const eng = ev.players[p.id]
    const bonus = rules.bonuses(eng)
    const isMe = p.id === 0
    const canReturn = isMe && myTurn && v.phase === 'return' && !returning
    const returnSel = isMe && sel?.kind === 'return' ? sel.colors : []
    return (
      <section key={p.id} className={classNames('sp-seat', `pos-${pos}`, isMe && 'is-me', p.id === v.current && active && 'is-current')} data-seat={p.id} aria-label={seatName(p.id)}>
        <header className="sp-seat-head">
          <span className="ew-seat-dot" style={{background: seatColor(p.id)}} aria-hidden="true" />
          <strong>{seatName(p.id)}</strong>
          <b className="sp-seat-score">{bt('score', {n: rules.score(eng)})}</b>
          <small className="ew-faint">{bt('cardsBought', {n: eng.cards.length})}</small>
        </header>
        <div className="sp-seat-row" aria-label={bt('tokens', {n: rules.total(eng.tokens)})}>
          {ALL.map(c => {
            const chosen = returnSel.filter(x => x === c).length
            const content = <><GemImg gem={c} /><b>{eng.tokens[c]}</b>{chosen > 0 && <em className="sp-chosen">−{chosen}</em>}</>
            const label = `${gem(c)} ${eng.tokens[c]}`
            return canReturn && eng.tokens[c] > 0
              ? <button key={c} type="button" className={classNames('sp-token-mini', 'is-clickable', chosen > 0 && 'is-selected')} aria-label={label} data-testid={`splendor-return-${c}`} onClick={() => clickOwnToken(c)}>{content}</button>
              : <span key={flash(p.id, c) ? `${c}-${view.revision}` : c} className={classNames('sp-token-mini', eng.tokens[c] === 0 && 'is-zero', flash(p.id, c) && 'is-flash')} role="img" aria-label={label}>{content}</span>
          })}
          <small className="sp-token-total">{rules.total(eng.tokens)}/10</small>
        </div>
        <div className="sp-seat-row sp-bonus-row" aria-label={bt('bonus')}>
          <span className="sp-row-label">{bt('bonus')}</span>
          {COLORS.map(c => <span key={flash(p.id, c) && lastEvent?.type === 'buy' ? `${c}-${view.revision}` : c} className={classNames('sp-bonus-chip', flash(p.id, c) && lastEvent?.type === 'buy' && 'is-flash')} style={{'--pip-bg': GEM_TONES[c].bg, '--pip-ink': GEM_TONES[c].ink} as CSSProperties} role="img" aria-label={`${bt('bonus')} ${gem(c)} ${bonus[c]}`}>{bonus[c]}</span>)}
        </div>
        <div className={classNames('sp-seat-reserved', flash(p.id, 'reserve') && 'is-flash')} aria-label={bt('reserved', {n: p.reserved.length})}>
          <span className="sp-row-label">{bt('reserved', {n: p.reserved.length})}</span>
          {p.reserved.map((r, i) => r.hidden || !r.card
            ? tierBack(`hidden-${i}`, (r.tier ?? 1) as 1 | 2 | 3, bt('hiddenReserve', {tier: r.tier ?? '?'}))
            : devCard(r.card, isMe ? 'md' : 'sm', isMe ? 'reserve' : undefined))}
        </div>
        {eng.nobles.length > 0 && <div className="sp-seat-nobles" aria-label={bt('noblesN', {n: eng.nobles.length})}>{eng.nobles.map(id => noble(id, 'sm'))}</div>}
      </section>
    )
  }

  return (
    <div className={classNames('gb-board sp-board', `players-${v.players.length}`)} data-phase={v.phase} data-current={v.current} style={{'--sp-cloth': `url("${asset(TABLE_CLOTH)}")`} as CSSProperties}>
      <div className="sp-top">
        <strong>{bt('round', {n: v.round})}</strong>
        <span className="ew-chip">{legacy ? bt('legacy') : bt('v2')}</span>
        {v.ending && !v.ended && <span className="ew-chip warn">{bt('ending')}</span>}
        {view.log.length > 0 && <span className="gb-recent"><span className="ew-faint">{bt('recent')}</span>{view.log[view.log.length - 1].summary[lang]}</span>}
      </div>
      <div className="sp-table">
        {v.players.slice(1).map(p => playerPanel(p, positions[p.id]))}
        <div className="sp-center">
          <div className="sp-nobles" aria-label={bt('nobles')}>
            {(v.phase === 'noble' && myTurn ? v.pendingNobles : v.nobles).map(id => noble(id, 'md', v.phase === 'noble' && myTurn))}
            {v.phase === 'noble' && myTurn && v.nobles.filter(id => !v.pendingNobles.includes(id)).map(id => noble(id))}
          </div>
          <div className="sp-market">
            {([3, 2, 1] as const).map(tier => (
              <div key={tier} className="sp-market-row" aria-label={bt('tier', {tier})}>
                {myTurn && v.phase === 'action' && blindTiers.has(tier)
                  ? <button type="button" className={classNames('sp-deck', sel?.kind === 'deck' && sel.tier === tier && 'is-selected')} data-testid={`splendor-deck-${tier}`} aria-pressed={sel?.kind === 'deck' && sel.tier === tier} aria-label={bt('deck', {tier, n: v.decks[tier]})} onClick={() => setSel(sel?.kind === 'deck' && sel.tier === tier ? null : {kind: 'deck', tier})} style={{backgroundImage: `url("${asset(TIER_BACKS[tier])}")`}}><b>{bt('deckShort', {n: v.decks[tier]})}</b></button>
                  : <span className="sp-deck" role="img" aria-label={bt('deck', {tier, n: v.decks[tier]})} style={{backgroundImage: v.decks[tier] ? `url("${asset(TIER_BACKS[tier])}")` : undefined}}><b>{bt('deckShort', {n: v.decks[tier]})}</b></span>}
                {v.market[tier].map((id, i) => id ? devCard(id, 'md', 'market') : <span key={`empty-${i}`} className="sp-card is-empty" aria-hidden="true" />)}
              </div>
            ))}
          </div>
          <div className="sp-bank" aria-label={bt('bank')}>
            {ALL.map(c => {
              const picked = sel?.kind === 'take' ? sel.colors.filter(x => x === c).length : 0
              const clickable = myTurn && v.phase === 'action' && c !== 'gold' && v.bank[c] > 0
              const content = <><GemImg gem={c} className="sp-bank-gem" /><b>{v.bank[c]}</b>{picked > 0 && <em className="sp-chosen">+{picked}</em>}</>
              return clickable
                ? <button key={c} type="button" className={classNames('sp-token', picked > 0 && 'is-selected')} data-testid={`splendor-bank-${c}`} aria-pressed={picked > 0} aria-label={`${gem(c)} ${v.bank[c]}${picked ? ` · +${picked}` : ''}`} onClick={() => clickBank(c)}>{content}</button>
                : <span key={c} className={classNames('sp-token', c === 'gold' && 'is-gold', v.bank[c] === 0 && 'is-zero')} role="img" aria-label={`${gem(c)} ${v.bank[c]}`}>{content}</span>
            })}
          </div>
        </div>
      </div>
      {playerPanel(v.players[0], 'bottom')}
      {bar}
      <span hidden data-testid="splendor-legal" data-take={takeOptions.map(sortedKey).join(' ')} data-buy={[...buyable].join(' ')} data-reserve={[...reservable].join(' ')} data-blind={[...blindTiers].join(' ')} data-my-bonus={COLORS.map(c => myBonus[c]).join(',')} />
    </div>
  )
}

