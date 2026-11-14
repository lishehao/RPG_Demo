/**
 * Game sessions (LOCAL MOCK AUTHORITY). Full engine state stays here; responses carry
 * only seat 0's allowlisted projection. NPC seats are fixed-strategy “规则模拟陪玩”.
 * AI steps are requested one at a time by the open table, so leaving the page lets
 * the in-flight step finish and pauses the rest (G133).
 */
import {characterById, gameById, OFFICIAL_CHARACTERS} from '../catalog'
import {db, now, save} from '../db'
import type {GameRow, GameSeatRow} from '../db'
import {fail, fingerprint, int, ok, str} from '../http'
import type {MockRequest, MockResult} from '../http'
import {scenarios} from '../scenarios'
import {actor, expectAccount} from './context'
import {onFriendCreated, registerOrigin} from './friends'
import {GAME_MODULES} from '../games/modules'
import type {GameId} from '../games/modules'
import {hash32, randomId} from '../../lib/util'
import type {L10n, Lang} from '../../lib/util'

const TEMP_ROTATION = ['official-lena', 'official-arthur', 'official-marcus', 'official-nora', 'official-iris']

function seatJSON(s: GameSeatRow) {
  const ch = s.source_id ? characterById(s.source_id) : null
  return {seat: s.seat, kind: s.kind, identity: s.identity, friend_epoch: s.friend_epoch, name: s.name, source_id: s.source_id, source_version: s.source_version,
    avatar: ch?.avatar ?? null, live2d: ch && s.source_version === '1' ? ch.live2d : null}
}
function expressionFor(g: GameRow): Record<number, 'neutral' | 'happy' | 'surprised'> {
  const out: Record<number, 'neutral' | 'happy' | 'surprised'> = {}
  const last = g.public_log[g.public_log.length - 1]
  if (!last) return out
  if (last.kind === 'gain') out[last.seat] = 'happy'
  if (last.kind === 'surprise') for (const s of g.seats) if (s.seat !== last.seat) out[s.seat] = 'surprised'
  if (g.settlement) for (const w of g.settlement.winners) out[w] = 'happy'
  return out
}
export function gameViewJSON(g: GameRow) {
  const m = GAME_MODULES[g.game_id]
  const a = m.actor(g.state)
  return {
    schema_version: 'everwith-game-view-v1', mode: 'rule_simulated_companions', id: g.id, game_id: g.game_id, profile: g.profile,
    seats: g.seats.map(seatJSON), lifecycle: g.lifecycle, revision: g.revision, ai_hold: g.ai_hold,
    actor_seat: a, phase: m.phase(g.state), player_view: m.view(g.state, 0), settlement: g.settlement,
    origin: g.origin, created_at: g.created_at, updated_at: g.updated_at, rematch_of: g.rematch_of, archived: g.archived,
    log: g.public_log.slice(-60), expressions: expressionFor(g), chat_count: g.chat.length,
  }
}
function owned(id: string) {
  const g = db().games[id]
  if (!g || g.owner !== actor() || g.deleted) fail(404, 'not_found')
  return g
}
function logKind(gameId: GameId, action: Record<string, unknown>, before: unknown, after: unknown, seat: number): string {
  if (gameId === 'vegas' && action.type === 'payout') return 'payout'
  if (gameId === 'gems' && (action.type === 'buy' || action.type === 'noble')) {
    const b = (before as {players: {cards: string[]; nobles: string[]}[]}).players[seat], c = (after as {players: {cards: string[]; nobles: string[]}[]}).players[seat]
    return c.cards.length + c.nobles.length > b.cards.length + b.nobles.length ? 'gain' : 'move'
  }
  if (gameId === 'cabo' && (action.type === 'call' || action.type === 'swap')) return 'surprise'
  return 'move'
}
const seatName = (g: GameRow) => (seat: number) => g.seats[seat]?.name ?? `#${seat}`

function applyMove(g: GameRow, seat: number, action: Record<string, unknown>) {
  const m = GAME_MODULES[g.game_id]
  const before = g.state
  let next: unknown
  try { next = m.apply(before, seat, action) } catch (e) { return fail(422, 'game_action_rejected', {reason: e instanceof Error ? e.message : 'illegal'}) }
  g.state = next; g.revision++; g.updated_at = now()
  const summary = m.summary(before, next, seat, action, seatName(g))
  let kind = logKind(g.game_id, action, before, next, seat)
  if (g.game_id === 'vegas' && action.type === 'payout') {
    const r = (next as {events: {type: string; result?: {awards: {owner: number | 'neutral'}[]}}[]}).events.find(e => e.type === 'payout')?.result
    const winner = r?.awards[0]?.owner
    if (typeof winner === 'number') { kind = 'gain'; seat = winner }
  }
  if (summary) g.public_log.push({revision: g.revision, seat, summary, kind})
  if (g.public_log.length > 400) g.public_log.splice(0, g.public_log.length - 400)
  if (m.ended(next)) {
    g.lifecycle = 'ended'
    const settle = m.settle(next)
    g.settlement = {id: randomId('settle', 6), committed_revision: g.revision, ...settle}
  }
}

const AUTO_LINES: Record<string, L10n[]> = {
  gain: [{zh: '这一手不错。', en: 'Not a bad move.'}, {zh: '收下了，谢谢。', en: 'I\'ll take that, thanks.'}],
  surprise: [{zh: '……来真的？', en: '…Seriously?'}, {zh: '好，那就看看谁的牌更小。', en: 'Alright, let\'s see whose hand is lower.'}],
  end: [{zh: '这一局结束了。比分以台面为准。', en: 'That\'s the game. The table score stands.'}],
}
function autoLine(g: GameRow, seat: number, kind: string, lang: Lang) {
  if (seat === 0 || !AUTO_LINES[kind] || g.seats[seat]?.kind === 'player') return
  const pick = AUTO_LINES[kind][hash32(`${g.id}|${g.revision}`) % AUTO_LINES[kind].length]
  g.chat.push({id: `tc_${g.id}_${g.revision}_${seat}`, seat, text: pick[lang], audience: 'table', mode: 'simulated_rule_reply', kind: 'narration', language: lang, revision: g.revision})
}

registerOrigin('game', (origin, owner, sourceId, version) => {
  const g = db().games[String(origin.session_id)]
  if (!g || g.owner !== owner || g.deleted) fail(404, 'not_found')
  const seat = g!.seats[Number(origin.seat)]
  if (!seat || seat.kind !== 'temporary' || seat.source_id !== sourceId || version !== '1') fail(422, 'origin_mismatch')
  const def = gameById(g!.game_id)!
  return {kind: 'game', session_id: g!.id, label: {zh: `来自 ${def.name} 同桌`, en: `From a ${def.name} table`}}
})
onFriendCreated((friend, origin) => {
  if (origin.kind !== 'game') return
  const g = db().games[String(origin.session_id)]
  const seat = g?.seats[Number(origin.seat)]
  // F7: the temporary table-mate becomes this friend in place — no added seat, no restart.
  if (g && seat && seat.kind === 'temporary') {
    const previous = seat.identity
    seat.kind = 'friend'; seat.identity = friend.id; seat.friend_epoch = friend.epoch; seat.name = friend.name
    for (const other of Object.values(db().games)) if (other.rematch_of === g.id || g.rematch_of === other.id) {
      const s = other.seats.find(x => x.identity === previous); if (s) { s.kind = 'friend'; s.identity = friend.id; s.friend_epoch = friend.epoch; s.name = friend.name }
    }
  }
})

export function handleGames(req: MockRequest): MockResult | null {
  const d = db()
  if (req.path === '/game-sessions' && req.method === 'GET') {
    return ok({items: Object.values(d.games).filter(g => g.owner === actor() && !g.deleted).sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(gameViewJSON)})
  }
  if (req.path === '/game-sessions/lookup' && req.method === 'GET') {
    const key = req.query.get('key') ?? ''
    const g = Object.values(d.games).find(x => x.owner === actor() && x.key === key)
    if (!g) fail(404, 'not_found')
    return ok(gameViewJSON(g!))
  }
  if (req.path === '/game-sessions' && req.method === 'POST') {
    expectAccount(req.body)
    const key = str(req.body, 'key', 128), gameId = str(req.body, 'game_id', 10) as GameId
    const def = gameById(gameId)
    if (!def || !GAME_MODULES[gameId]) fail(404, 'not_found')
    const players = int(req.body, 'players')
    if (!def!.players.includes(players)) fail(422, 'player_count_invalid')
    const profile = typeof req.body?.profile === 'string' ? req.body.profile : def!.profile
    if (profile !== def!.profile && !(gameId === 'gems' && profile === 'splendor-legacy-v1' && req.body?.legacy_fixture === true)) fail(422, 'profile_invalid')
    const seatsIn = Array.isArray(req.body?.seats) ? req.body!.seats as {seat: number; kind: string; friend_id?: string; friend_epoch?: number; character_id?: string}[] : []
    const origin = (req.body?.origin ?? {kind: 'discover', return_hash: '#/discover?tab=games'}) as GameRow['origin']
    const fp = fingerprint({gameId, players, profile, seatsIn})
    const existing = Object.values(d.games).find(g => g.owner === actor() && g.key === key)
    if (existing) { if (existing.fingerprint !== fp) fail(409, 'idempotency_conflict'); return ok(gameViewJSON(existing)) }
    if (seatsIn.length !== players - 1) fail(422, 'seats_invalid')
    const used = new Set<string>()
    const seats: GameSeatRow[] = [{seat: 0, kind: 'player', identity: actor(), friend_epoch: null, name: d.accounts[actor()]?.persona?.name || (d.guest_personas[actor()]?.name ?? '你'), source_id: null, source_version: null}]
    seatsIn.forEach((s, i) => {
      if (s.seat !== i + 1) fail(422, 'seats_invalid')
      if (s.kind === 'friend') {
        const f = d.friends[s.friend_id ?? '']
        if (!f || f.owner !== actor() || f.status !== 'active') fail(422, 'friend_unavailable', {seat: s.seat})
        if (f!.epoch !== s.friend_epoch) fail(409, 'friend_epoch_changed', {seat: s.seat})
        if (used.has(f!.id)) fail(422, 'friend_already_seated', {seat: s.seat})
        used.add(f!.id)
        seats.push({seat: s.seat, kind: 'friend', identity: f!.id, friend_epoch: f!.epoch, name: f!.name, source_id: f!.source_id, source_version: f!.source_version})
      } else {
        const ch = characterById(s.character_id ?? '') ?? characterById(TEMP_ROTATION[i % TEMP_ROTATION.length])!
        seats.push({seat: s.seat, kind: 'temporary', identity: randomId('tmp', 6), friend_epoch: null, name: ch.name, source_id: ch.id, source_version: ch.version})
      }
    })
    const seed = hash32(`${key}|${gameId}|${players}`) % 1000000 + 1
    const m = GAME_MODULES[gameId]
    const g: GameRow = {id: randomId('gs', 8), owner: actor(), game_id: gameId, profile, key, fingerprint: fp, seats, lifecycle: 'active', revision: 1, ai_hold: false,
      state: m.create(players, seed, profile), seed, origin, chat: [], settlement: null, actions: {}, created_at: now(), updated_at: now(), rematch_of: null,
      archived: false, deleted: false, public_log: [{revision: 1, seat: 0, summary: {zh: '牌局开始', en: 'Game started'}, kind: 'move'}]}
    d.games[g.id] = g; save()
    if (scenarios.consume('game.unknown_start')) return {drop: true}
    return ok(gameViewJSON(g), 201)
  }
  const one = /^\/game-sessions\/([^/]+)$/.exec(req.path)
  if (one && req.method === 'GET') return ok(gameViewJSON(owned(decodeURIComponent(one[1]))))
  const cmd = /^\/game-sessions\/([^/]+)\/(act|advance|hold|abandon|rematch)$/.exec(req.path)
  if (cmd && req.method === 'POST') {
    const g = owned(decodeURIComponent(cmd[1]))
    const m = GAME_MODULES[g.game_id]
    if (cmd[2] === 'hold') {
      if (g.lifecycle === 'active') { g.ai_hold = req.body?.hold === true; save() }
      return ok(gameViewJSON(g))
    }
    if (cmd[2] === 'rematch') {
      if (g.lifecycle !== 'ended' && g.lifecycle !== 'abandoned') fail(409, 'game_not_finished')
      const key = str(req.body, 'key', 128)
      const prior = Object.values(d.games).find(x => x.owner === actor() && x.key === key)
      if (prior) return ok(gameViewJSON(prior))
      // Same table, same people (temporary identities kept); a fresh deal and new record.
      const seed = hash32(`${key}|rematch|${g.id}`) % 1000000 + 1
      const fresh: GameRow = {...structuredClone(g), id: randomId('gs', 8), key, fingerprint: fingerprint({rematch: g.id}), lifecycle: 'active', revision: 1, ai_hold: false,
        state: m.create(g.seats.length, seed, g.profile), seed, chat: [], settlement: null, actions: {}, created_at: now(), updated_at: now(), rematch_of: g.id, archived: false,
        public_log: [{revision: 1, seat: 0, summary: {zh: '原桌再开一局', en: 'Rematch at the same table'}, kind: 'move'}]}
      d.games[fresh.id] = fresh; save()
      return ok(gameViewJSON(fresh), 201)
    }
    if (cmd[2] === 'abandon') {
      if (g.lifecycle === 'ended' || g.lifecycle === 'abandoned') return ok(gameViewJSON(g))
      if (int(req.body, 'expected_revision') !== g.revision) fail(409, 'game_revision_changed')
      // Explicit abandon: read-only, unfinished, no invented winner.
      g.lifecycle = 'abandoned'; g.updated_at = now()
      g.public_log.push({revision: g.revision, seat: 0, summary: {zh: '你明确放弃了本局（未完成，不计胜负）', en: 'You abandoned this game (unfinished, no result)'}, kind: 'move'}); save()
      return ok(gameViewJSON(g))
    }
    if (g.lifecycle !== 'active') fail(409, 'game_not_active')
    const key = str(req.body, 'key', 128)
    const expected = int(req.body, 'expected_revision')
    const prior = g.actions[key]
    const action = (cmd[2] === 'act' ? req.body?.action : {advance: true}) as Record<string, unknown>
    const fp = fingerprint(action)
    if (prior) { if (prior.fingerprint !== fp) fail(409, 'idempotency_conflict'); return ok(gameViewJSON(g)) }
    if (expected !== g.revision) fail(409, 'game_revision_changed')
    const who = m.actor(g.state)
    if (cmd[2] === 'act') {
      if (!(who === 0 || who === 'any')) fail(409, 'game_seat_not_authorized')
      if (!action || typeof action.type !== 'string') fail(400, 'invalid_request')
      applyMove(g, 0, action)
      g.ai_hold = false
    } else {
      if (g.ai_hold) fail(409, 'game_ai_on_hold')
      if (who === 0 || who === 'any') fail(409, 'waiting_for_player')
      const seat = who as number
      const decided = m.ai(g.state, seat, hash32(`${g.id}|${g.revision}`) % 100000 + 1) as Record<string, unknown>
      applyMove(g, seat, decided)
      const last = g.public_log[g.public_log.length - 1]
      const lang: Lang = req.body?.language === 'en' ? 'en' : 'zh'
      if (last && last.revision === g.revision && (last.kind === 'gain' || last.kind === 'surprise') && hash32(`${g.id}|${g.revision}|talk`) % 3 === 0) autoLine(g, last.seat, last.kind, lang)
      if (g.lifecycle === 'ended') autoLine(g, g.settlement!.winners.find(w => w !== 0) ?? 1, 'end', lang)
    }
    g.actions[key] = {fingerprint: fp, revision: g.revision}
    save()
    return ok(gameViewJSON(g))
  }
  const chat = /^\/game-sessions\/([^/]+)\/table-chat$/.exec(req.path)
  if (chat) {
    const g = owned(decodeURIComponent(chat[1]))
    const items = () => g.chat.slice(-60).map(({revision: _r, ...m}) => m)
    if (req.method === 'GET') return ok({items: items()})
    if (req.method === 'POST') {
      if (g.lifecycle === 'abandoned') fail(409, 'table_chat_read_only')
      const key = str(req.body, 'key', 128), text = str(req.body, 'text', 2000).trim(), lang: Lang = req.body?.language === 'en' ? 'en' : 'zh'
      if (!text) fail(422, 'empty_input')
      if (g.chat.some(m => m.id === `tc_${key}`)) return ok({items: items(), reply_failed: false})
      g.chat.push({id: `tc_${key}`, seat: 0, text, audience: 'table', mode: 'player', kind: 'dialogue', language: lang, revision: g.revision})
      const others = g.seats.filter(s => s.seat !== 0)
      const speaker = others[hash32(key) % others.length]
      if (scenarios.consume('game.text_failed')) { save(); return ok({items: items(), reply_failed: true}) }
      const last = g.public_log[g.public_log.length - 1]
      // Replies read only public table facts; they never move pieces or change scores.
      const lines: L10n[] = g.lifecycle === 'ended'
        ? [{zh: '结果已经锁定啦，不过还可以聊聊刚才那几手。', en: 'The result is locked, but we can still talk about those moves.'}]
        : [{zh: `我看到了：${last?.summary.zh ?? '刚开局'}。聊天不会替谁出牌，轮到谁还是谁来。`, en: `I saw it: ${last?.summary.en ?? 'just started'}. Chat doesn't play for anyone — turns stay as they are.`},
          {zh: '嗯，我听到了。不过我的下一步还是按规则来。', en: 'Heard you. My next move still follows the rules, though.'}]
      const line = lines[hash32(`${key}|r`) % lines.length]
      g.chat.push({id: `tc_${key}_r`, seat: speaker.seat, text: line[lang], audience: 'table', mode: 'simulated_rule_reply', kind: 'narration', language: lang, revision: g.revision})
      save()
      return ok({items: items(), reply_failed: false})
    }
  }
  return null
}
export function _tempRotation() { return OFFICIAL_CHARACTERS.map(c => c.id) }
