/**
 * Private chat authority (LOCAL MOCK). One command = one key = one operation.
 * Replies are pre-decided simulated text (replies.ts); only public segments are
 * framed as `private-public-segments.v1` NDJSON. Commit happens server-side on its
 * own schedule, independent of whether a browser is still reading the stream.
 */
import {characterById} from '../catalog'
import {db, now, save} from '../db'
import type {ConversationRow, OperationRow, TurnRow} from '../db'
import {fail, int, ok, str} from '../http'
import type {MockRequest, MockResult} from '../http'
import {planReply} from '../replies'
import {scenarios} from '../scenarios'
import {actor, requireAccount} from './context'
import {activeFriend} from './friends'
import {randomId} from '../../lib/util'
import type {Lang} from '../../lib/util'

const VERSION = 'private-public-segments.v1'
// Run timeline (ms after run start). Slow enough that Stop can genuinely race commit.
const T = {start: 0, firstSegment: 520, segmentGap: 620, completeAfter: 380, commitAfter: 520}

function snapshotJSON(c: ConversationRow) {
  const d = db()
  const pending = Object.values(d.operations).find(o => o.conversation_id === c.id && ['accepted', 'running', 'validating', 'retryable_failed'].includes(o.status)) ?? null
  const head = c.turns[c.turns.length - 1]
  return {
    schema_version: 'companion-memory-private-display-v1', reply_mode: 'simulated_fixed_reply', public_stream_version: VERSION,
    conversation: {id: c.id, friend_id: c.friend_id, friend_epoch: c.friend_epoch, binding_version: c.binding_version, status: c.status},
    history: {session_id: c.id, player_actor_id: c.player_actor_id, position: {revision: c.revision, head_turn_id: head.turn_id, branch_id: 'main'},
      content_revision: c.content_revision, invalidation_epoch: c.invalidation_epoch, access_epoch: c.access_epoch,
      turns: c.turns.map(t => ({turn_id: t.turn_id, language: t.language, input_availability: t.input_availability,
        player_expression: t.input_availability === 'withdrawn' ? null : t.player_expression,
        segments: t.segments.map(s => ({segment_id: s.segment_id, kind: s.kind, speaker_id: s.speaker_id, availability: s.availability, body: s.availability === 'withdrawn' ? null : s.body})),
        expression: t.expression, kind: t.kind}))},
    pending_operation: pending ? operationJSON(pending) : null,
    pending_expression: pending ? pending.text : null,
    recall_options: [],
  }
}
function operationJSON(o: OperationRow) {
  const availability = o.status === 'committed' ? 'available' : ['cancelled', 'failed_final', 'stale'].includes(o.status) ? 'absent' : 'pending'
  return {schema_version: 'companion-memory-private-operation-v1', operation_id: o.id, status: o.status, availability, turn_id: o.status === 'committed' ? o.turn_id : null}
}
function bindingOf(o: OperationRow) {
  return {account_id: o.owner, friend_id: o.friend_id, friend_epoch: o.friend_epoch, session_id: o.conversation_id, revision: o.baseline_revision, head_turn_id: o.baseline_head, allow_fictional_thought: false}
}
const admissionJSON = (o: OperationRow) => ({version: VERSION, operation_id: o.id, run_epoch: o.run_epoch, binding: bindingOf(o)})

function greetingTurn(c: ConversationRow, sourceId: string, language: Lang): TurnRow {
  const ch = characterById(sourceId)
  const text = ch ? ch.greeting[language] : (language === 'zh' ? '*点点头。*\n你好。' : '*Nods.*\nHello.')
  const [action, spoken] = text.startsWith('*') ? [text.slice(1, text.indexOf('*', 1)), text.slice(text.indexOf('\n') + 1)] : ['', text]
  const segs = [...(action ? [{kind: 'action' as const, body: action}] : []), {kind: 'dialogue' as const, body: spoken}]
  return {turn_id: randomId('turn', 6), player_expression: null, input_availability: 'available', language, expression: 'neutral', created_at: now(), kind: 'greeting',
    segments: segs.map(s => ({segment_id: randomId('seg', 6), kind: s.kind, speaker_id: c.friend_id, body: s.body, availability: 'available'}))}
}

/** Advance every operation per its timeline. Idempotent; safe to call often. */
export function tickOperations() {
  const d = db(), t = Date.now()
  let changed = false
  for (const o of Object.values(d.operations)) {
    if (!['accepted', 'running', 'validating'].includes(o.status) || o.run_started_at === null) continue
    const plan = o.plan.segments.length
    const failAt = o.scenario === 'retryable_failure' && o.run_epoch === 1 ? o.run_started_at + T.firstSegment + T.segmentGap * .6 : null
    if (failAt !== null && t >= failAt) { o.status = 'retryable_failed'; changed = true; continue }
    const completeAt = o.run_started_at + T.firstSegment + T.segmentGap * (plan - 1) + T.completeAfter
    const commitAt = o.commit_at ?? completeAt + T.commitAfter
    if (t >= commitAt) { commit(o); changed = true }
    else if (t >= completeAt && o.status !== 'validating') { o.status = 'validating'; changed = true }
    else if (t >= o.run_started_at && o.status === 'accepted') { o.status = 'running'; changed = true }
  }
  if (changed) save()
}
function commit(o: OperationRow) {
  const d = db(), c = d.conversations[o.conversation_id]
  if (!c || o.status === 'committed') return
  const turn: TurnRow = {turn_id: randomId('turn', 6), player_expression: o.text, input_availability: 'available', language: o.language, expression: o.plan.expression,
    created_at: now(), kind: 'reply', segments: o.plan.segments.map(s => ({segment_id: s.segment_id, kind: s.kind === 'spoken' ? 'dialogue' : s.kind, speaker_id: s.kind === 'narration' ? null : o.friend_id, body: s.text, availability: 'available'}))}
  c.turns.push(turn); c.revision++; c.content_revision++; c.updated_at = now()
  o.status = 'committed'; o.turn_id = turn.turn_id
}
let ticker: ReturnType<typeof setInterval> | null = null
export function startChatTicker() { if (!ticker) ticker = setInterval(tickOperations, 90) }

function encodeFrames(frames: unknown[]): Uint8Array[] {
  // Split each frame at a deterministic byte offset (often inside a multi-byte
  // UTF-8 character) so the strict streaming decoder is exercised for real.
  const enc = new TextEncoder(), out: Uint8Array[] = []
  for (const f of frames) {
    const bytes = enc.encode(JSON.stringify(f) + '\n')
    const cut = Math.max(1, Math.floor(bytes.length * .61))
    out.push(bytes.slice(0, cut), bytes.slice(cut))
  }
  return out
}
function streamFor(o: OperationRow, runEpoch: number, signal?: AbortSignal | null): ReadableStream<Uint8Array> {
  const binding = bindingOf(o)
  const env = (seq: number) => ({version: VERSION, operation_id: o.id, run_epoch: runEpoch, seq})
  const late = o.scenario === 'late_old_stream' && runEpoch > 1
  let seq = 0, closed = false
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const push = (frames: unknown[]) => { for (const chunk of encodeFrames(frames)) controller.enqueue(chunk) }
      const wait = (ms: number) => new Promise<void>(r => setTimeout(r, Math.max(0, ms)))
      signal?.addEventListener('abort', () => { closed = true }, {once: true})
      try {
        if (late) {
          // Stale frames from the retired run arrive first; the receiver must ignore them.
          push([{version: VERSION, operation_id: o.id, run_epoch: runEpoch - 1, seq: 0, type: 'start', binding},
            {version: VERSION, operation_id: o.id, run_epoch: runEpoch - 1, seq: 1, type: 'segment', segment: {segment_id: 'stale_segment_old_run', kind: 'spoken', text: '（这是旧 run 的晚到片段，不应显示）'}}])
        }
        push([{...env(seq++), type: 'start', binding}])
        for (let i = 0; i < o.plan.segments.length; i++) {
          const due = (o.run_started_at ?? Date.now()) + T.firstSegment + T.segmentGap * i
          await wait(due - Date.now())
          if (closed) return
          tickOperations()
          const live = db().operations[o.id]
          if (!live || live.run_epoch !== runEpoch) { closed = true; controller.close(); return }
          if (live.status === 'cancelled') { push([{...env(seq++), type: 'cancelled'}]); controller.close(); return }
          if (live.status === 'retryable_failed') { push([{...env(seq++), type: 'failed', reason: 'generation_failed'}]); controller.close(); return }
          const s = live.plan.segments[i]
          push([{...env(seq++), type: 'segment', segment: {segment_id: s.segment_id, kind: s.kind, text: s.text}}])
        }
        const completeAt = (o.run_started_at ?? Date.now()) + T.firstSegment + T.segmentGap * (o.plan.segments.length - 1) + T.completeAfter
        await wait(completeAt - Date.now())
        if (closed) return
        tickOperations()
        const live = db().operations[o.id]
        if (live?.status === 'cancelled') push([{...env(seq++), type: 'cancelled'}])
        else if (live?.status === 'retryable_failed') push([{...env(seq++), type: 'failed', reason: 'generation_failed'}])
        else push([{...env(seq++), type: 'complete'}])
        controller.close()
      } catch { if (!closed) controller.error(new Error('stream_failed')) }
    },
    cancel() { closed = true },
  })
}

function conversationFor(friendId: string, owner: string) {
  return Object.values(db().conversations).filter(c => c.friend_id === friendId && c.owner === owner).sort((a, b) => b.friend_epoch - a.friend_epoch)
}
function ownedConversation(id: string, owner: string) {
  const c = db().conversations[id]
  if (!c || c.owner !== owner) fail(404, 'not_found')
  return c
}

export function handleChat(req: MockRequest): MockResult | null {
  const d = db()
  tickOperations()
  const open = /^\/friends\/([^/]+)\/conversation$/.exec(req.path)
  if (open && req.method === 'POST') {
    const me = requireAccount()
    if (req.body?.expected_account_id !== me.id) fail(409, 'account_changed')
    const f = activeFriend(decodeURIComponent(open[1]), me.id)
    if (int(req.body, 'expected_friend_epoch') !== f.epoch) fail(409, 'friend_epoch_changed')
    const language = req.body?.language === 'en' ? 'en' : 'zh'
    let c = conversationFor(f.id, me.id).find(x => x.friend_epoch === f.epoch)
    if (!c) {
      c = {id: randomId('conv', 8), owner: me.id, friend_id: f.id, friend_epoch: f.epoch, binding_version: 1, status: 'active', revision: 1, turns: [],
        player_actor_id: `player_${me.id}`, created_at: now(), updated_at: now(), content_revision: 1, invalidation_epoch: 0, access_epoch: 1}
      c.turns.push(greetingTurn(c, f.source_id, language))
      d.conversations[c.id] = c; save()
    }
    return ok(snapshotJSON(c))
  }
  const archive = /^\/friends\/([^/]+)\/conversations$/.exec(req.path)
  if (archive && req.method === 'GET') {
    const me = requireAccount()
    const f = d.friends[decodeURIComponent(archive[1])]
    if (!f || f.owner !== me.id) fail(404, 'not_found')
    return ok({items: conversationFor(f.id, me.id).map(c => ({id: c.id, friend_epoch: c.friend_epoch, status: c.status, turns: c.turns.length, updated_at: c.updated_at}))})
  }
  const read = /^\/conversations\/([^/]+)$/.exec(req.path)
  if (read && req.method === 'GET') { const me = requireAccount(); return ok(snapshotJSON(ownedConversation(decodeURIComponent(read[1]), me.id))) }

  const send = /^\/conversations\/([^/]+)\/operations$/.exec(req.path)
  if (send && req.method === 'POST') {
    const me = requireAccount()
    if (req.body?.expected_account_id !== me.id) fail(409, 'account_changed')
    const c = ownedConversation(decodeURIComponent(send[1]), me.id)
    const f = activeFriend(c.friend_id, me.id)
    if (scenarios.consume('chat.friend_reset_elsewhere')) {
      f.epoch++; f.revision++
      for (const x of Object.values(d.conversations)) if (x.friend_id === f.id && x.friend_epoch < f.epoch) x.status = 'read_only'
      save(); fail(409, 'friend_epoch_changed')
    }
    if (int(req.body, 'expected_friend_epoch') !== f.epoch || c.friend_epoch !== f.epoch) fail(409, 'friend_epoch_changed')
    if (c.status !== 'active') fail(409, 'conversation_read_only')
    const key = str(req.body, 'key', 128), text = str(req.body, 'text', 2000), language = req.body?.language === 'en' ? 'en' as const : 'zh' as const
    if (!text.trim()) fail(422, 'empty_input')
    const prior = Object.values(d.operations).find(o => o.conversation_id === c.id && o.key === key)
    if (prior) {
      if (prior.text !== text || prior.language !== language) fail(409, 'idempotency_conflict')
      return ok({operation: operationJSON(prior), admission: admissionJSON(prior)})
    }
    if (scenarios.consume('chat.stale_head')) {
      // Another window committed first: the presented head is now stale.
      const other: TurnRow = {turn_id: randomId('turn', 6), player_expression: language === 'zh' ? '（另一窗口发送的消息）' : '(Message sent from another window)', input_availability: 'available', language, expression: 'neutral', created_at: now(), kind: 'reply',
        segments: [{segment_id: randomId('seg', 6), kind: 'dialogue', speaker_id: c.friend_id, body: language === 'zh' ? '嗯，这条是在另一个窗口里回复的。' : 'Mm, this reply happened in another window.', availability: 'available'}]}
      c.turns.push(other); c.revision++; c.content_revision++; save()
    }
    const head = c.turns[c.turns.length - 1]
    if (int(req.body, 'expected_revision') !== c.revision || req.body?.presented_turn_id !== head.turn_id) fail(409, 'stale_revision')
    if (Object.values(d.operations).some(o => o.conversation_id === c.id && ['accepted', 'running', 'validating', 'retryable_failed'].includes(o.status))) fail(409, 'operation_pending')
    let scenario: string | null = null, lateOnRetry = false
    if (scenarios.consume('chat.late_old_stream')) { scenario = 'retryable_failure'; lateOnRetry = true }
    else if (scenarios.consume('chat.retryable_failure')) scenario = 'retryable_failure'
    else if (scenarios.consume('chat.commit_before_cancel')) scenario = 'commit_before_cancel'
    const source = characterById(f.source_id)?.live2d ?? 'default'
    const plan = planReply(source, text, language, c.turns.length)
    const o: OperationRow = {id: randomId('op', 8), conversation_id: c.id, owner: me.id, friend_id: f.id, friend_epoch: f.epoch, key, text, language,
      baseline_revision: c.revision, baseline_head: head.turn_id, status: 'accepted', run_epoch: 1, turn_id: null, created_at: now(),
      plan: {segments: plan.segments.map(s => ({...s, segment_id: randomId('seg', 6)})), expression: plan.expression},
      scenario, late_on_retry: lateOnRetry, commit_at: null, run_started_at: Date.now() + 140}
    if (o.scenario === 'commit_before_cancel') o.commit_at = o.run_started_at! + T.firstSegment + 160
    d.operations[o.id] = o; save()
    const result = {operation: operationJSON(o), admission: admissionJSON(o)}
    if (scenarios.consume('chat.unknown_result')) return {drop: true}
    return ok(result, 202)
  }
  const stream = /^\/operations\/([^/]+)\/public-stream$/.exec(req.path)
  if (stream && req.method === 'GET') {
    const me = requireAccount()
    const o = d.operations[decodeURIComponent(stream[1])]
    if (!o || o.owner !== me.id) fail(404, 'not_found')
    const run = Number(req.query.get('run_epoch'))
    if (run !== o!.run_epoch) fail(409, 'run_epoch_changed')
    return {status: 200, stream: streamFor(o!, run, req.signal), contentType: 'application/x-ndjson'}
  }
  const opRead = /^\/operations\/([^/]+)(\/receipt)?$/.exec(req.path)
  if (opRead && req.method === 'GET') {
    const me = requireAccount()
    const o = d.operations[decodeURIComponent(opRead[1])]
    if (!o || o.owner !== me.id) fail(404, 'not_found')
    if (!opRead[2]) return ok(operationJSON(o!))
    const c = d.conversations[o!.conversation_id]
    return ok({owner_id: me.id, operation: operationJSON(o!), snapshot: snapshotJSON(c), admission: ['accepted', 'running', 'validating'].includes(o!.status) ? admissionJSON(o!) : null})
  }
  const lookup = /^\/conversations\/([^/]+)\/operations\/lookup$/.exec(req.path)
  if (lookup && req.method === 'GET') {
    const me = requireAccount()
    const c = ownedConversation(decodeURIComponent(lookup[1]), me.id)
    const key = req.query.get('key') ?? ''
    const o = Object.values(d.operations).find(x => x.conversation_id === c.id && x.key === key)
    if (!o) fail(404, 'operation_not_found')
    return ok({operation: operationJSON(o!), admission: ['accepted', 'running', 'validating'].includes(o!.status) ? admissionJSON(o!) : null, text: o!.text})
  }
  const control = /^\/operations\/([^/]+)\/(retry|cancel)$/.exec(req.path)
  if (control && req.method === 'POST') {
    const me = requireAccount()
    if (req.body?.expected_account_id !== me.id) fail(409, 'account_changed')
    const o = d.operations[decodeURIComponent(control[1])]
    if (!o || o.owner !== me.id) fail(404, 'not_found')
    const f = d.friends[o!.friend_id]
    if (!f || f.status !== 'active' || int(req.body, 'expected_friend_epoch') !== o!.friend_epoch || f.epoch !== o!.friend_epoch) fail(409, 'friend_epoch_changed')
    if (control[2] === 'cancel') {
      // Scenario “commit wins over Stop”: the authority committed just before Stop arrived.
      if (o!.scenario === 'commit_before_cancel' && ['accepted', 'running', 'validating'].includes(o!.status)) o!.commit_at = Math.min(o!.commit_at ?? Infinity, Date.now())
      tickOperations()
      if (['accepted', 'running', 'validating', 'retryable_failed'].includes(o!.status)) { o!.status = 'cancelled'; save() }
      return ok(operationJSON(o!))
    }
    if (o!.status !== 'retryable_failed') fail(409, 'operation_not_retryable')
    const c = d.conversations[o!.conversation_id]
    if (c.revision !== o!.baseline_revision || c.turns[c.turns.length - 1].turn_id !== o!.baseline_head) { o!.status = 'stale'; save(); fail(409, 'stale_revision') }
    // Same operation, same key, same input, same baseline; a new run epoch.
    o!.run_epoch++; o!.status = 'accepted'; o!.run_started_at = Date.now() + 140
    o!.scenario = o!.late_on_retry ? 'late_old_stream' : null
    save()
    return ok({operation: operationJSON(o!), admission: admissionJSON(o!)}, 202)
  }
  const rollback = /^\/conversations\/([^/]+)\/rollback$/.exec(req.path)
  if (rollback && req.method === 'POST') {
    const me = requireAccount()
    const c = ownedConversation(decodeURIComponent(rollback[1]), me.id)
    if (c.status !== 'active') fail(409, 'conversation_read_only')
    if (int(req.body, 'expected_revision') !== c.revision) fail(409, 'stale_revision')
    if (Object.values(d.operations).some(o => o.conversation_id === c.id && ['accepted', 'running', 'validating', 'retryable_failed'].includes(o.status))) fail(409, 'operation_pending')
    const turnId = str(req.body, 'turn_id', 128)
    const index = c.turns.findIndex(t => t.turn_id === turnId)
    if (index <= 0 || c.turns[index].player_expression === null || c.turns[index].input_availability === 'withdrawn') fail(422, 'rollback_target_invalid')
    const draft = c.turns[index].player_expression
    const withdrawn = c.turns.length - index
    // The target and everything after it leave the valid history at once: no body is
    // kept anywhere that a later read, search, preview or export could return.
    c.turns = c.turns.slice(0, index)
    const lang = req.body?.language === 'en' ? 'en' : 'zh'
    c.turns.push({turn_id: randomId('turn', 6), player_expression: null, input_availability: 'available', language: lang, expression: 'neutral', created_at: now(), kind: 'note',
      segments: [{segment_id: randomId('seg', 6), kind: 'narration', speaker_id: null, availability: 'available',
        body: lang === 'zh' ? `已回退到这里：之后的 ${withdrawn} 轮已撤回，原输入已放回输入框。` : `Rolled back here: ${withdrawn} later turn(s) withdrawn; your original input is back in the composer.`}]})
    c.revision++; c.invalidation_epoch++; c.content_revision++; c.updated_at = now(); save()
    return ok({snapshot: snapshotJSON(c), restored_draft: draft})
  }
  const correction = /^\/conversations\/([^/]+)\/corrections$/.exec(req.path)
  if (correction && req.method === 'POST') {
    const me = requireAccount()
    const c = ownedConversation(decodeURIComponent(correction[1]), me.id)
    if (c.status !== 'active') fail(409, 'conversation_read_only')
    const text = str(req.body, 'text', 400).trim(), target = typeof req.body?.turn_id === 'string' ? req.body.turn_id : null
    if (!text) fail(422, 'empty_input')
    const key = str(req.body, 'key', 128)
    if (d.corrections.some(x => x.id === key)) return ok({snapshot: snapshotJSON(c)})
    d.corrections.push({id: key, conversation_id: c.id, turn_id: target, text, created_at: now()})
    const lang = req.body?.language === 'en' ? 'en' : 'zh'
    c.turns.push({turn_id: randomId('turn', 6), player_expression: null, input_availability: 'available', language: lang, expression: 'neutral', created_at: now(), kind: 'note',
      segments: [{segment_id: randomId('seg', 6), kind: 'narration', speaker_id: null, availability: 'available',
        body: lang === 'zh' ? `已记录更正（玩家说明，不改写已发生的事）：${text}` : `Correction recorded (player's statement; past events are not rewritten): ${text}`}]})
    c.revision++; c.content_revision++; save()
    return ok({snapshot: snapshotJSON(c)})
  }
  return null
}
export const _internal = {actor}
