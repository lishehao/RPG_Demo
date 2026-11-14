/**
 * LOCAL MOCK AUTHORITY: the only place that holds full engine state (truth, rng,
 * other seats' hidden cards). The UI receives `view(state, 0)` projections only.
 * NPC seats decide from their OWN projection (fixed-strategy “规则模拟陪玩”), never
 * from truth. JEV is not connected; nothing here claims chat changes a move.
 */
import * as royale from '../../games/engines/royale/engine'
import * as splendor from '../../games/engines/splendor/splendor/rules'
import {chooseBotAction} from '../../games/engines/splendor/splendor/npc'
import * as cabo from '../../games/engines/cabo/engine'
import type {L10n} from '../../lib/util'

export type GameId = 'vegas' | 'gems' | 'cabo'
export type SeatName = (seat: number) => string
export type Settlement = {scores: number[]; winners: number[]; labels: L10n[]}
export type GameModule = {
  id: GameId
  create(players: number, seed: number, profile?: string): unknown
  current(state: unknown): number
  phase(state: unknown): string
  ended(state: unknown): boolean
  /** Seat that must act next, or `any` when any seat may (CABO round end). */
  actor(state: unknown): number | 'any'
  apply(state: unknown, seat: number, action: unknown): unknown
  ai(state: unknown, seat: number, seed: number): unknown
  view(state: unknown, seat: number): unknown
  summary(prev: unknown, next: unknown, seat: number, action: unknown, name: SeatName): L10n | null
  settle(state: unknown): Settlement
  check(state: unknown): void
}

const CASINO_NAMES: L10n[] = [
  {zh: '奇迹', en: 'Miracle'}, {zh: '帝王', en: 'Kings'}, {zh: '海滨', en: 'Marina'},
  {zh: '广场', en: 'Plaza'}, {zh: '埃及艳后', en: 'Cleopatra'}, {zh: '日落', en: 'Sunset'},
]
export const casinoName = (i: number) => CASINO_NAMES[i]
const money = (n: number) => `${(n / 1000).toLocaleString('en-US')}K`

const royaleModule: GameModule = {
  id: 'vegas',
  create: (players, seed) => royale.create({players, seed, starter: 0, session: `royale-${seed}`}),
  current: s => (s as royale.State).current,
  phase: s => (s as royale.State).phase,
  ended: s => (s as royale.State).phase === 'ended',
  actor: s => (s as royale.State).current,
  apply(state, seat, action) {
    const s = state as royale.State
    const next = royale.act(s, seat, action as royale.Action, {expectedRevision: s.revision, requestId: `${s.session}:${s.revision}:${seat}`})
    royale.assertState(next); return next
  },
  ai(state, seat) {
    const s = state as royale.State
    if (s.current !== seat) throw Error('turn')
    // The heuristic receives this seat's allowlisted observation (no rng / bank order / hidden earnings).
    const own = royale.observe(s, seat) as unknown as royale.State
    return royale.decide(own)
  },
  view: (s, seat) => royale.observe(s as royale.State, seat),
  summary(prev, next, seat, action, name) {
    const a = action as royale.Action, n = next as royale.State, p = prev as royale.State
    if (a.type === 'roll') return {zh: `${name(seat)} 掷出 ${royale.remaining(p, seat).length} 颗骰子`, en: `${name(seat)} rolls ${royale.remaining(p, seat).length} dice`}
    if (a.type === 'place') {
      const ev = n.events.find(e => e.type === 'place'), count = ev?.dice?.reduce((x, d) => x + royale.weight(d), 0) ?? 0
      return {zh: `${name(seat)} 把 ${a.face} 点（影响力 ${count}）放进 ${CASINO_NAMES[a.face - 1].zh}`, en: `${name(seat)} places ${a.face}s (influence ${count}) in ${CASINO_NAMES[a.face - 1].en}`}
    }
    if (a.type === 'pass') return {zh: `${name(seat)} 付 1 筹码跳过本次放置`, en: `${name(seat)} pays 1 chip to skip`}
    if (a.type === 'payout') {
      const r = n.events.find(e => e.type === 'payout')?.result
      if (!r) return null
      const awards = r.awards.map(w => `${w.owner === 'neutral' ? '中立' : name(w.owner as number)} ${money(w.value)}`).join('，')
      const awardsEn = r.awards.map(w => `${w.owner === 'neutral' ? 'Neutral' : name(w.owner as number)} ${money(w.value)}`).join(', ')
      return {zh: `${CASINO_NAMES[r.casino].zh} 派彩：${awards || '无人获奖'}${r.excluded.length ? `（并列排除 ${r.excluded.length} 方）` : ''}`, en: `${CASINO_NAMES[r.casino].en} pays: ${awardsEn || 'no winner'}${r.excluded.length ? ` (${r.excluded.length} tied & excluded)` : ''}`}
    }
    if (a.type === 'nextRound') return {zh: `第 ${n.round} 轮开始`, en: `Round ${n.round} begins`}
    return null
  },
  settle(state) {
    const s = state as royale.State
    return {scores: s.players.map(royale.wealth), winners: [...s.winners], labels: s.players.map(p => ({zh: `现金 ${money(royale.cash(p))} + 筹码 ${p.chips}×10K`, en: `cash ${money(royale.cash(p))} + ${p.chips} chips ×10K`}))}
  },
  check: s => { royale.assertState(s as royale.State) },
}

const gemNames: Record<string, L10n> = {diamond: {zh: '钻石', en: 'diamond'}, sapphire: {zh: '蓝宝石', en: 'sapphire'}, emerald: {zh: '祖母绿', en: 'emerald'}, ruby: {zh: '红宝石', en: 'ruby'}, onyx: {zh: '缟玛瑙', en: 'onyx'}, gold: {zh: '黄金', en: 'gold'}}
/** Public reserves are visible to everyone; blind reserves only show a tier back. */
export function splendorProjection(state: splendor.SplendorState, seat: number) {
  const view = splendor.playerView(state, seat)
  const openReserves = new Set(state.events.filter(e => e.type === 'reserve' && e.blind === false && typeof e.card === 'string').map(e => e.card as string))
  return {
    ...view,
    players: state.players.map((p, i) => ({
      ...view.players[i],
      reserved: i === seat ? p.reserved.map(id => ({card: id, tier: id ? splendor.cardById(id).tier : null, hidden: false}))
        : p.reserved.map(id => id && openReserves.has(id) ? {card: id, tier: splendor.cardById(id).tier, hidden: false} : {card: null, tier: id ? splendor.cardById(id).tier : null, hidden: true}),
    })),
  }
}
const splendorModule: GameModule = {
  id: 'gems',
  create: (players, seed, profile) => splendor.createGame({players, seed: `seed-${seed}`, rulesProfile: profile ?? splendor.NEW_RULES_PROFILE}),
  current: s => (s as splendor.SplendorState).current,
  phase: s => (s as splendor.SplendorState).phase,
  ended: s => (s as splendor.SplendorState).ended,
  actor: s => (s as splendor.SplendorState).current,
  apply(state, seat, action) {
    const next = splendor.applyAction(state as splendor.SplendorState, seat, action as splendor.SplendorAction)
    splendor.assertInvariants(next); return next
  },
  ai(state, seat, seed) {
    const view = splendor.playerView(state as splendor.SplendorState, seat)
    const action = chooseBotAction(view, seat, {seed})
    if (!action) throw Error('no_legal_action')
    return action
  },
  view: (s, seat) => splendorProjection(s as splendor.SplendorState, seat),
  summary(prev, next, seat, action, name) {
    const a = action as splendor.SplendorAction, n = next as splendor.SplendorState
    if (a.type === 'take') return {zh: `${name(seat)} 拿取 ${a.colors.map(c => gemNames[c].zh).join('、')}`, en: `${name(seat)} takes ${a.colors.map(c => gemNames[c].en).join(', ')}`}
    if (a.type === 'reserve') {
      if (a.card) { const c = splendor.cardById(a.card); return {zh: `${name(seat)} 预留了「${c.name}」${n.players[seat].tokens.gold > (prev as splendor.SplendorState).players[seat].tokens.gold ? '并获得 1 黄金' : ''}`, en: `${name(seat)} reserves a tier ${c.tier} card${n.players[seat].tokens.gold > (prev as splendor.SplendorState).players[seat].tokens.gold ? ' and takes 1 gold' : ''}`} }
      return {zh: `${name(seat)} 从 ${a.tier} 级牌堆盲预留了一张`, en: `${name(seat)} blind-reserves from the tier ${a.tier} deck`}
    }
    if (a.type === 'buy') { const c = splendor.cardById(a.card); return {zh: `${name(seat)} 购买「${c.name}」${c.points ? `（+${c.points} 分）` : ''}`, en: `${name(seat)} buys a tier ${c.tier} ${gemNames[c.bonus].en} card${c.points ? ` (+${c.points})` : ''}`} }
    if (a.type === 'return') return {zh: `${name(seat)} 归还 1 枚${gemNames[a.color].zh}`, en: `${name(seat)} returns 1 ${gemNames[a.color].en}`}
    if (a.type === 'noble') { const nb = splendor.nobleById(a.noble); return {zh: `${nb.name} 拜访了 ${name(seat)}（+3）`, en: `A noble visits ${name(seat)} (+3)`} }
    return null
  },
  settle(state) {
    const s = state as splendor.SplendorState
    return {scores: s.players.map(splendor.score), winners: [...s.winners], labels: s.players.map(p => ({zh: `${p.cards.length} 张卡 · ${p.nobles.length} 位贵族`, en: `${p.cards.length} cards · ${p.nobles.length} noble(s)`}))}
  },
  check: s => { splendor.assertInvariants(s as splendor.SplendorState) },
}

const caboModule: GameModule = {
  id: 'cabo',
  create: (players, seed) => cabo.create({players, seed}),
  current: s => (s as cabo.CaboState).current,
  phase: s => (s as cabo.CaboState).phase,
  ended: s => (s as cabo.CaboState).ended,
  actor: s => (s as cabo.CaboState).phase === 'roundEnd' ? 'any' : (s as cabo.CaboState).current,
  apply(state, seat, action) {
    const next = cabo.act(state as cabo.CaboState, seat, action as cabo.CaboAction)
    cabo.assertState(next); return next
  },
  ai: (state, seat, seed) => cabo.decide(cabo.observe(state as cabo.CaboState, seat), 'medium', {seed}),
  view: (s, seat) => cabo.observe(s as cabo.CaboState, seat),
  summary(prev, next, seat, action, name) {
    const a = action as cabo.CaboAction, n = next as cabo.CaboState, p = prev as cabo.CaboState
    const ev = (t: string) => n.events.find(e => e.type === t)
    switch (a.type) {
      case 'initialPeek': return {zh: `${name(seat)} 私看了自己的两张牌`, en: `${name(seat)} privately peeks at two own cards`}
      case 'call': return {zh: `${name(seat)} 叫了 CABO！其余玩家各再走一次`, en: `${name(seat)} calls CABO! Everyone else gets one more turn`}
      case 'draw': return {zh: `${name(seat)} 从${a.source === 'deck' ? '牌堆' : '弃牌堆'}抽了一张`, en: `${name(seat)} draws from the ${a.source === 'deck' ? 'deck' : 'discard pile'}`}
      case 'exchange': {
        const failed = ev('matchFailed')
        if (failed) return {zh: `${name(seat)} 配对失败，公开了 ${(failed.values as number[]).join('、')} 并盖回`, en: `${name(seat)}'s match fails, revealing ${(failed.values as number[]).join(', ')}`}
        const count = (ev('exchange')?.removed as string[] | undefined)?.length ?? 1
        return {zh: `${name(seat)} 换入一张牌${count > 1 ? `（${count} 张同值换 1）` : ''}`, en: `${name(seat)} exchanges ${count > 1 ? `${count} matching cards for one` : 'a card'}`}
      }
      case 'discard': { const v = p.drawn ? p.truth[p.drawn] : null; return {zh: `${name(seat)} 弃掉 ${v}${n.phase === 'ability' ? '，使用能力' : ''}`, en: `${name(seat)} discards ${v}${n.phase === 'ability' ? ' and uses its ability' : ''}`} }
      case 'peek': {
        const target = p.players.find(q => q.cards.includes(a.card))?.id ?? seat
        return target === seat ? {zh: `${name(seat)} 偷看了自己的一张牌`, en: `${name(seat)} peeks at an own card`} : {zh: `${name(seat)} 窥探了 ${name(target)} 的一张牌`, en: `${name(seat)} spies on ${name(target)}'s card`}
      }
      case 'swap': { const other = p.players.find(q => q.cards.includes(a.other))?.id ?? 0; return {zh: `${name(seat)} 与 ${name(other)} 盲换了一张牌`, en: `${name(seat)} blind-swaps a card with ${name(other)}`} }
      case 'cancelAbility': return {zh: `${name(seat)} 放弃使用能力`, en: `${name(seat)} declines the ability`}
      case 'nextRound': return {zh: `第 ${n.round} 轮开始`, en: `Round ${n.round} begins`}
      default: return null
    }
  },
  settle(state) {
    const s = state as cabo.CaboState
    return {scores: s.players.map(p => p.total), winners: [...s.winners], labels: s.players.map(p => ({zh: `累计 ${p.total}${p.resetUsed ? '（已用 100→50）' : ''}`, en: `total ${p.total}${p.resetUsed ? ' (100→50 used)' : ''}`}))}
  },
  check: s => { cabo.assertState(s as cabo.CaboState) },
}

export const GAME_MODULES: Record<GameId, GameModule> = {vegas: royaleModule, gems: splendorModule, cabo: caboModule}
