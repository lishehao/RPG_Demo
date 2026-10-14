/**
 * Story sessions (LOCAL MOCK). Fixed scripted beats stand in for a narrator model:
 * “本地模拟叙事”. Each accepted turn commits text + state together (atomic); nothing
 * uncommitted is streamed to the player. Hidden beats/clues are never serialised.
 */
import {characterById, storyById} from '../catalog'
import type {StoryDef} from '../catalog'
import {db, now, save} from '../db'
import type {StorySessionRow, StoryTurnRow} from '../db'
import {fail, fingerprint, int, ok, str} from '../http'
import type {MockRequest, MockResult} from '../http'
import {scenarios} from '../scenarios'
import {actor, expectAccount} from './context'
import {onFriendCreated, registerOrigin} from './friends'
import {randomId, hash32} from '../../lib/util'
import type {Lang} from '../../lib/util'

const MAX_AI = 10
const initialState = (def: StoryDef): StorySessionRow['state'] => ({beat: 0, objective: 0, clues: [], minutes: 0, scene: def.beats[0]?.scene ?? '', present: def.roles.map(r => r.id)})

function stateFrom(def: StoryDef, turns: StoryTurnRow[]): StorySessionRow['state'] {
  const s = initialState(def)
  for (const t of turns) {
    if (t.availability !== 'available') continue
    s.minutes += t.delta.minutes
    if (t.delta.clue && !s.clues.includes(t.delta.clue)) s.clues.push(t.delta.clue)
    if (typeof t.delta.objective === 'number') s.objective = Math.max(s.objective, t.delta.objective + 1)
    if (t.delta.beat !== undefined) { s.beat = t.delta.beat + 1; s.scene = def.beats[t.delta.beat]?.scene ?? s.scene }
    // A free turn after the last beat moves to the story's ending place (if it has one).
    else if (t.kind !== 'opening' && s.beat >= def.beats.length && def.endingScene) s.scene = def.endingScene
  }
  return s
}
/** Rows written before scenes had their own keys are re-derived from their turns. */
const sceneKey = (def: StoryDef, s: StorySessionRow) => Object.prototype.hasOwnProperty.call(def.scenes, s.state.scene) ? s.state.scene : stateFrom(def, s.turns).scene

function sessionJSON(s: StorySessionRow) {
  const def = storyById(s.story_id, s.version)!
  const nextBeat = def.beats[s.state.beat]
  const lastBeat = def.beats[Math.max(0, s.state.beat - 1)]
  const hint = (s.state.beat > 0 ? lastBeat : nextBeat)?.hint ?? null
  const scene = sceneKey(def, s), place = def.scenes[scene] ?? null
  return {
    schema_version: 'everwith-story-session-v1', narration_mode: 'local_scripted_mock', id: s.id, story_id: s.story_id, version: s.version,
    title: def.title, player_role: def.playerRole, status: s.status, archived: s.archived, revision: s.revision,
    head_turn_id: s.turns[s.turns.length - 1]?.turn_id ?? null, created_at: s.created_at, updated_at: s.updated_at, language: s.language,
    cast: s.cast.map(c => {
      const role = def.roles.find(r => r.id === c.role_id)!
      const ch = characterById(c.character_id)
      return {role_id: c.role_id, role_title: role.title, kind: c.kind, character_id: c.character_id, character_name: ch?.name ?? c.name,
        friend_id: c.friend_id, friend_epoch: c.friend_epoch, name: c.name, avatar: ch?.avatar ?? null, live2d: ch?.live2d ?? null, replaceable: role.replaceable}
    }),
    turns: s.turns.map(t => ({turn_id: t.turn_id, kind: t.kind, input: t.input_availability === 'withdrawn' ? null : t.input, input_availability: t.input_availability,
      language: t.language, created_at: t.created_at, delta: {minutes: t.delta.minutes, clue: t.delta.clue ? def.beats.find(b => b.clue?.id === t.delta.clue)?.clue?.label ?? null : null, objective: t.delta.objective ?? null},
      segments: t.segments.map(g => ({segment_id: g.segment_id, kind: g.kind, role_id: g.role_id, text: g.text}))})),
    state: {
      objectives: def.objectives.map((o, i) => ({text: o, done: i < s.state.objective, current: i === s.state.objective})),
      clues: s.state.clues.map(id => ({id, label: def.beats.find(b => b.clue?.id === id)!.clue!.label})),
      minutes: s.state.minutes, scene, scene_image: place?.image ?? null, scene_position: place?.position ?? null, scene_label: place?.label ?? null, present: s.state.present, hint,
      open_mode: s.state.beat >= def.beats.length,
    },
    pending: s.pending ? {operation_id: s.pending.op_id, kind: s.pending.kind, text: s.pending.text, status: s.pending.status} : null,
  }
}

function respond(s: StorySessionRow, kind: 'input' | 'continue', text: string | null, lang: Lang): StoryTurnRow {
  const def = storyById(s.story_id, s.version)!
  const beatIndex = s.state.beat, beat = def.beats[beatIndex]
  const segs: StoryTurnRow['segments'] = []
  const seg = (k: StoryTurnRow['segments'][number]['kind'], textValue: string, role: string | null = null) => segs.push({segment_id: randomId('seg', 6), kind: k, role_id: role, text: textValue})
  const sinceBeat = (() => { let n = 0; for (let i = s.turns.length - 1; i >= 0; i--) { const t = s.turns[i]; if (t.delta.beat !== undefined) break; if (t.kind === 'input') n++ } return n })()
  const matches = !!beat && !!text && beat.keywords.some(k => text.toLowerCase().includes(k.toLowerCase()))
  if (beat && (kind === 'continue' || matches || sinceBeat >= 2)) {
    if (kind === 'input' && text) seg('narration', lang === 'zh' ? `你的行动被接受了。` : 'Your action goes ahead.')
    seg('narration', beat.narration[lang])
    for (const line of beat.lines) {
      const body = line.text[lang]
      if (body.startsWith('*')) {
        const end = body.indexOf('*', 1)
        seg('action', body.slice(1, end), line.role)
        seg('dialogue', body.slice(end + 1).trim(), line.role)
      } else seg('dialogue', body, line.role)
    }
    return {turn_id: randomId('turn', 6), kind, input: text, input_availability: 'available', segments: segs, availability: 'available', language: lang, created_at: now(),
      delta: {minutes: beat.minutes, clue: beat.clue?.id, objective: beat.objective, beat: beatIndex}}
  }
  // A smaller, local response: acknowledges the action without inventing progress.
  const present = def.roles[hash32(`${s.id}|${s.turns.length}`) % def.roles.length]
  if (kind === 'continue') seg('narration', lang === 'zh' ? '片刻过去，周围安静下来。没有新的事情发生——也许该由你来做点什么。' : 'A moment passes. Nothing new happens — perhaps it is your move.')
  else {
    seg('narration', lang === 'zh' ? '你照自己的想法行动。周围的人注意到了，但局面暂时没有变化。' : 'You act on your own idea. The others notice, but nothing changes yet.')
    seg('action', lang === 'zh' ? '看了你一眼。' : 'Glances at you.', present.id)
    seg('dialogue', lang === 'zh' ? '这样做也行。不过线索恐怕不在这里。' : 'Fair enough. Though I doubt the answer is here.', present.id)
  }
  return {turn_id: randomId('turn', 6), kind, input: text, input_availability: 'available', segments: segs, availability: 'available', language: lang, created_at: now(), delta: {minutes: kind === 'continue' ? 3 : 2}}
}

export function tickStories() {
  const d = db(), t = Date.now()
  let changed = false
  for (const s of Object.values(d.stories)) {
    const p = s.pending
    if (!p || !['accepted', 'validating'].includes(p.status) || t < p.commit_at) continue
    if (p.fail) { p.status = 'retryable_failed'; p.fail = false; changed = true; continue }
    const turn = respond(s, p.kind, p.text, p.language)
    s.turns.push(turn); s.revision++; s.updated_at = now()
    s.state = stateFrom(storyById(s.story_id, s.version)!, s.turns)
    s.ops = {...s.ops, [p.op_id]: {key: p.key, status: 'committed', turn_id: turn.turn_id}}
    s.pending = null; changed = true
  }
  if (changed) save()
}

function ownedStory(id: string) {
  const s = db().stories[id]
  if (!s || s.owner !== actor() || s.deleted) fail(404, 'not_found')
  return s
}

registerOrigin('story', (origin, owner, sourceId, version) => {
  const s = db().stories[String(origin.session_id)]
  if (!s || s.owner !== owner || s.deleted) fail(404, 'not_found')
  const role = s!.cast.find(c => c.role_id === origin.role_id)
  if (!role || role.character_id !== sourceId || version !== '1') fail(422, 'origin_mismatch')
  if (!origin.separate && role!.kind === 'friend') fail(409, 'role_already_bound')
  const def = storyById(s!.story_id, s!.version)!
  return {kind: 'story', session_id: s!.id, label: {zh: `来自故事《${def.title.zh}》`, en: `From the story “${def.title.en}”`}}
})
onFriendCreated((friend, origin) => {
  if (origin.kind !== 'story' || origin.separate) return
  const s = db().stories[String(origin.session_id)]
  const role = s?.cast.find(c => c.role_id === origin.role_id)
  // F2: the current person becomes this friend in the same commit (no re-cast, no restart).
  if (role && role.kind === 'npc') { role.kind = 'friend'; role.friend_id = friend.id; role.friend_epoch = friend.epoch; role.name = friend.name; s!.revision++ }
})

export function handleStories(req: MockRequest): MockResult | null {
  const d = db()
  tickStories()
  if (req.path === '/story-sessions' && req.method === 'POST') {
    expectAccount(req.body)
    const key = str(req.body, 'key', 128), storyId = str(req.body, 'story_id', 80), version = str(req.body, 'version', 20)
    const def = storyById(storyId, version)
    if (!def) fail(404, 'not_found')
    const castInput = Array.isArray(req.body?.cast) ? req.body!.cast as {role_id: string; friend_id: string; friend_epoch: number}[] : []
    const language = req.body?.language === 'en' ? 'en' : 'zh'
    const fp = fingerprint({storyId, version, castInput})
    const existing = Object.values(d.stories).find(s => s.owner === actor() && s.key === key)
    if (existing) { if (existing.fingerprint !== fp) fail(409, 'idempotency_conflict'); return ok(sessionJSON(existing)) }
    // Strong checks: open seats only, one seat per friend, AI seats ≤ 10, locked roles stay.
    const seen = new Set<string>()
    for (const c of castInput) {
      const role = def!.roles.find(r => r.id === c.role_id)
      if (!role) fail(422, 'unknown_role')
      if (!role!.replaceable) fail(422, 'role_locked', {role: c.role_id})
      if (seen.has(c.friend_id)) fail(422, 'friend_already_cast', {friend: c.friend_id})
      seen.add(c.friend_id)
      const f = d.friends[c.friend_id]
      if (!f || f.owner !== actor() || f.status !== 'active') fail(422, 'friend_unavailable', {friend: c.friend_id})
      if (f!.epoch !== c.friend_epoch) fail(409, 'friend_epoch_changed', {friend: c.friend_id})
    }
    if (new Set(castInput.map(c => c.role_id)).size !== castInput.length) fail(422, 'role_cast_twice')
    if (def!.roles.length > MAX_AI) fail(422, 'too_many_ai')
    const cast = def!.roles.map(r => {
      const chosen = castInput.find(c => c.role_id === r.id)
      if (chosen) { const f = d.friends[chosen.friend_id]; return {role_id: r.id, kind: 'friend' as const, character_id: f.source_id, friend_id: f.id, friend_epoch: f.epoch, name: f.name} }
      const ch = characterById(r.defaultCharacter)!
      return {role_id: r.id, kind: 'npc' as const, character_id: ch.id, friend_id: null, friend_epoch: null, name: ch.name}
    })
    const opening: StoryTurnRow = {turn_id: randomId('turn', 6), kind: 'opening', input: null, input_availability: 'available', availability: 'available', language, created_at: now(), delta: {minutes: 0},
      segments: [{segment_id: randomId('seg', 6), kind: 'narration', role_id: null, text: def!.opening[language]}]}
    const s: StorySessionRow = {id: randomId('ss', 8), owner: actor(), story_id: def!.id, version: def!.version, key, fingerprint: fp, cast, turns: [opening], revision: 1,
      status: 'active', archived: false, deleted: false, state: initialState(def!), created_at: now(), updated_at: now(), language, pending: null, ops: {}}
    d.stories[s.id] = s; save()
    return ok(sessionJSON(s), 201)
  }
  const one = /^\/story-sessions\/([^/]+)$/.exec(req.path)
  if (one && req.method === 'GET') return ok(sessionJSON(ownedStory(decodeURIComponent(one[1]))))
  const turns = /^\/story-sessions\/([^/]+)\/turns$/.exec(req.path)
  if (turns && req.method === 'POST') {
    const s = ownedStory(decodeURIComponent(turns[1]))
    if (s.status !== 'active') fail(409, 'session_read_only')
    const key = str(req.body, 'key', 128), kind = req.body?.kind === 'continue' ? 'continue' as const : 'input' as const
    const text = kind === 'input' ? str(req.body, 'text', 2000).trim() : null
    if (kind === 'input' && !text) fail(422, 'empty_input')
    const ops = s.ops ?? {}
    const done = Object.entries(ops).find(([, v]) => v.key === key)
    if (done) return ok({operation: {operation_id: done[0], status: done[1].status}, session: sessionJSON(s)})
    if (s.pending) {
      if (s.pending.key === key) return ok({operation: {operation_id: s.pending.op_id, status: s.pending.status}, session: sessionJSON(s)})
      fail(409, 'operation_pending')
    }
    if (int(req.body, 'expected_revision') !== s.revision) fail(409, 'stale_revision')
    const language = req.body?.language === 'en' ? 'en' as const : 'zh' as const
    s.pending = {op_id: randomId('sop', 8), key, kind, text, status: 'validating', commit_at: Date.now() + 1500, language}
    if (scenarios.consume('story.retryable_failure')) s.pending.fail = true
    save()
    return ok({operation: {operation_id: s.pending.op_id, status: 'validating'}, session: sessionJSON(s)}, 202)
  }
  const control = /^\/story-sessions\/([^/]+)\/operations\/([^/]+)\/(cancel|retry)$/.exec(req.path)
  if (control && req.method === 'POST') {
    const s = ownedStory(decodeURIComponent(control[1]))
    const opId = decodeURIComponent(control[2])
    if (!s.pending || s.pending.op_id !== opId) {
      const ops = s.ops ?? {}
      if (ops[opId]) return ok({operation: {operation_id: opId, status: ops[opId].status}, session: sessionJSON(s)})
      fail(404, 'not_found')
    }
    if (control[3] === 'cancel') {
      const op = s.pending!; s.pending = null; s.ops = {...s.ops, [op.op_id]: {key: op.key, status: 'cancelled', turn_id: null}}; save()
      return ok({operation: {operation_id: op.op_id, status: 'cancelled'}, session: sessionJSON(s), restored_input: op.text})
    }
    if (s.pending!.status !== 'retryable_failed') fail(409, 'operation_not_retryable')
    s.pending!.status = 'validating'; s.pending!.commit_at = Date.now() + 1500; save()
    return ok({operation: {operation_id: s.pending!.op_id, status: 'validating'}, session: sessionJSON(s)})
  }
  const rollback = /^\/story-sessions\/([^/]+)\/rollback$/.exec(req.path)
  if (rollback && req.method === 'POST') {
    const s = ownedStory(decodeURIComponent(rollback[1]))
    if (s.status !== 'active') fail(409, 'session_read_only')
    if (s.pending) fail(409, 'operation_pending')
    if (int(req.body, 'expected_revision') !== s.revision) fail(409, 'stale_revision')
    const idx = s.turns.findIndex(t => t.turn_id === req.body?.turn_id)
    if (idx <= 0 || s.turns[idx].kind !== 'input') fail(422, 'rollback_target_invalid')
    const draft = s.turns[idx].input
    s.turns = s.turns.slice(0, idx); s.revision++; s.updated_at = now()
    s.state = stateFrom(storyById(s.story_id, s.version)!, s.turns); save()
    return ok({session: sessionJSON(s), restored_draft: draft})
  }
  return null
}
export {sessionJSON as storySessionJSON}
