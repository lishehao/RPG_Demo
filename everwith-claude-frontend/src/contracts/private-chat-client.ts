import {deduplicateChatRead} from "./chat-poll"
import {startChatTiming,receivedChatTiming,observeChatOperation,failedChatTiming} from "./chat-timing"
import type {DialogueCheckpoint} from "./dialogue-expression-client"
import { CompanionRequestError } from "./companion"

export type PrivateSegment = { segment_id: string; kind: "dialogue" | "narration" | "action"; speaker_id: string | null; text: string; availability?: "available" | "withdrawn" }
export type PrivateTurn = { turn_id: string; player_actor_id: string; player_expression: string | null; visible_segments: PrivateSegment[]; revision?: number; language: "zh" | "en"; input_availability?: "available" | "withdrawn" }
export type PrivateOperation = { operation_id: string; status: "accepted" | "running" | "validating" | "retryable_failed" | "committed" | "cancelled" | "failed_final" | "stale"; availability: string; turn_id?: string | null }
export type PrivateCommand = { key: string; session_id: string; text: string; language: "zh" | "en"; presented_turn_id: string; expected_revision: number; recall_session_id?: string }
export type PrivateRecallOption = { session_id: string; title: { zh: string; en: string } }
export type PrivateSnapshot = {
  publicStreamVersion?: "private-public-segments.v1"
  replyMode?: "simulated_fixed_reply" | "real_siwc_gpt6_luna" | "other_live"
  conversation: { id: string; friend_id: string; friend_epoch: number; binding_version: number; status: "active" | "read_only" }
  history: { session_id: string; position: { revision: number; head_turn_id: string | null }; turns: PrivateTurn[] }
  pending_operation: PrivateOperation | null; pending_expression: string | null
  expressionCheckpoint?:DialogueCheckpoint;source?: "memory"; recall_options?: PrivateRecallOption[]
}
type Transport = (path: string, body?: unknown) => Promise<unknown>
function invalid(): never { throw new CompanionRequestError("invalid_response") }
function record(value: unknown): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) return invalid(); return value as Record<string, unknown> }
function text(value: unknown, max = 128): string { if (typeof value !== "string" || !value.trim() || value.length > max) return invalid(); return value }
function count(value: unknown): number { if (!Number.isSafeInteger(value) || Number(value) < 1) return invalid(); return Number(value) }
function optionalText(value: unknown, max = 8000) { return value === null ? null : text(value, max) }
function items(value: unknown, max: number): unknown[] { if (!Array.isArray(value) || value.length > max) return invalid(); return value }
function visibleText(value: unknown, max = 12000): string {
  const body = text(value, max)
  for (let i = 0; i < body.length; i++) {
    const c = body.charCodeAt(i)
    if (c < 32 && c !== 9 && c !== 10 || c === 127) return invalid()
    if (c >= 0xd800 && c <= 0xdbff) { const next = body.charCodeAt(++i); if (!(next >= 0xdc00 && next <= 0xdfff)) return invalid() }
    else if (c >= 0xdc00 && c <= 0xdfff) return invalid()
  }
  return body
}
function visibleSpeaker(segment: Record<string, unknown>): string | null {
  const speaker = optionalText(segment.speaker_id, 128)
  if (segment.kind === "dialogue" && speaker === null) return invalid()
  return speaker
}
export function parsePrivateOperation(value: unknown): PrivateOperation {
  const row = record(value), schema = row.schema_version, status = row.status
  if (schema !== undefined && schema !== "companion-memory-private-operation-v1") return invalid()
  if (typeof status !== "string" || !["accepted", "running", "validating", "retryable_failed", "committed", "cancelled", "failed_final", "stale"].includes(status)) return invalid()
  if (typeof row.availability !== "string" || !["pending", "absent", "available", "withdrawn", "forbidden"].includes(row.availability)) return invalid()
  const allowed = status === "committed" ? ["available", "withdrawn"] : ["cancelled", "failed_final", "stale"].includes(status) ? ["absent"] : ["pending"]
  if (!allowed.includes(row.availability)) return invalid()
  const turnId = schema === "companion-memory-private-operation-v1" ? optionalText(row.turn_id, 128) : undefined
  if (schema === "companion-memory-private-operation-v1" && status === "committed" !== Boolean(turnId)) return invalid()
  observeChatOperation("private", text(row.operation_id), status, turnId)
  return { operation_id: text(row.operation_id), status: status as PrivateOperation["status"], availability: row.availability, ...(schema ? { turn_id: turnId } : {}) }
}
export function parsePrivateCommand(value: unknown): PrivateCommand {
  const row = record(value)
  if (row.language !== "zh" && row.language !== "en") return invalid()
  const recall = row.recall_session_id === undefined ? undefined : text(row.recall_session_id)
  return { key: text(row.key), session_id: text(row.session_id), text: text(row.text, 8000), language: row.language, presented_turn_id: text(row.presented_turn_id), expected_revision: count(row.expected_revision), ...(recall ? { recall_session_id: recall } : {}) }
}
export function parsePrivateSnapshot(value: unknown, friendId: string, epoch: number): PrivateSnapshot {
  const data = record(value), conversation = record(data.conversation), history = record(data.history), position = record(history.position)
  if (data.schema_version !== undefined) {
    if (data.schema_version !== "companion-memory-private-display-v1") return invalid()
    return parseMemoryPrivateSnapshot(data, conversation, history, position, friendId, epoch)
  }
  const currentRevision = count(position.revision)
  if (conversation.friend_id !== friendId || conversation.friend_epoch !== epoch || history.session_id !== conversation.id) return invalid()
  if (conversation.status !== "active" && conversation.status !== "read_only") return invalid()
  const turns = items(history.turns, 10000).map((value): PrivateTurn => {
    const turn = record(value)
    if (turn.language !== "zh" && turn.language !== "en") return invalid()
    const revision = count(turn.revision)
    const visible_segments = items(turn.visible_segments, 100).map((value): PrivateSegment => {
      const segment = record(value)
      if (segment.kind !== "dialogue" && segment.kind !== "narration" && segment.kind !== "action") return invalid()
      return { segment_id: text(segment.segment_id), kind: segment.kind, speaker_id: visibleSpeaker(segment), text: visibleText(segment.text) }
    })
    return { turn_id: text(turn.turn_id), player_actor_id: text(turn.player_actor_id), player_expression: optionalText(turn.player_expression), visible_segments, revision, language: turn.language }
  })
  const legacyRevisions = turns.map((turn) => turn.revision as number)
  if (legacyRevisions.some((revision, index) => index > 0 && revision <= legacyRevisions[index - 1])) return invalid()
  if (!turns.length || new Set(turns.map((turn) => turn.turn_id)).size !== turns.length || turns.at(-1)?.turn_id !== position.head_turn_id || legacyRevisions.at(-1)! > currentRevision) return invalid()
  const pending = data.pending_operation === null ? null : parsePrivateOperation(data.pending_operation)
  const expression = optionalText(data.pending_expression)
  if (pending && !["accepted", "running", "validating", "retryable_failed"].includes(pending.status) || Boolean(pending) !== Boolean(expression)) return invalid()
  return {
    conversation: { id: text(conversation.id), friend_id: friendId, friend_epoch: epoch, binding_version: count(conversation.binding_version), status: conversation.status },
    history: { session_id: text(history.session_id), position: { revision: currentRevision, head_turn_id: optionalText(position.head_turn_id, 128) }, turns },
    pending_operation: pending, pending_expression: expression,
  }
}
function parseMemoryPrivateSnapshot(data: Record<string, unknown>, conversation: Record<string, unknown>, history: Record<string, unknown>, position: Record<string, unknown>, friendId: string, epoch: number): PrivateSnapshot {
  if (data.reply_mode !== undefined && !["simulated_fixed_reply", "real_siwc_gpt6_luna", "other_live"].includes(String(data.reply_mode))) return invalid()
  if (data.public_stream_version != null && data.public_stream_version !== "private-public-segments.v1") return invalid()
  const currentRevision = count(position.revision), player = text(history.player_actor_id)
  if (conversation.friend_id !== friendId || conversation.friend_epoch !== epoch || history.session_id !== conversation.id) return invalid()
  if (conversation.status !== "active" && conversation.status !== "read_only") return invalid()
  const turns = items(history.turns, 10000).map((value): PrivateTurn => {
    const turn = record(value)
    if (turn.language !== "zh" && turn.language !== "en" || turn.input_availability !== "available" && turn.input_availability !== "withdrawn") return invalid()
    const playerExpression = optionalText(turn.player_expression, 2000)
    if (turn.input_availability === "withdrawn" && playerExpression !== null) return invalid()
    const visible_segments = items(turn.segments, 100).map((value): PrivateSegment => {
      const segment = record(value)
      if (segment.kind !== "dialogue" && segment.kind !== "narration" && segment.kind !== "action") return invalid()
      if (segment.availability !== "available" && segment.availability !== "withdrawn") return invalid()
      const body = segment.body === null ? null : visibleText(segment.body)
      if (segment.availability === "withdrawn" && body !== null || segment.availability === "available" && body === null) return invalid()
      return { segment_id: text(segment.segment_id), kind: segment.kind, speaker_id: visibleSpeaker(segment), text: body ?? "", availability: segment.availability }
    })
    return { turn_id: text(turn.turn_id), player_actor_id: player, player_expression: playerExpression, visible_segments, language: turn.language, input_availability: turn.input_availability }
  })
  if (!turns.length || new Set(turns.map(turn => turn.turn_id)).size !== turns.length || turns.at(-1)?.turn_id !== position.head_turn_id) return invalid()
  const pending = data.pending_operation === null ? null : parsePrivateOperation(data.pending_operation)
  const expression = optionalText(data.pending_expression, 2000)
  if (pending && !["accepted", "running", "validating", "retryable_failed"].includes(pending.status) || Boolean(pending) !== Boolean(expression)) return invalid()
  const recall_options = items(data.recall_options, 10).map((value): PrivateRecallOption => {
    const option = record(value), title = record(option.title)
    return { session_id: text(option.session_id), title: { zh: text(title.zh, 1000), en: text(title.en, 1000) } }
  })
  if (new Set(recall_options.map(option => option.session_id)).size !== recall_options.length) return invalid()
  return {
    conversation: { id: text(conversation.id), friend_id: friendId, friend_epoch: epoch, binding_version: count(conversation.binding_version), status: conversation.status },
    history: { session_id: text(history.session_id), position: { revision: currentRevision, head_turn_id: optionalText(position.head_turn_id, 128) }, turns },
    pending_operation: pending, pending_expression: expression, source: "memory", recall_options,
    ...(data.public_stream_version ? {publicStreamVersion: "private-public-segments.v1" as const} : {}),
    ...(data.reply_mode ? { replyMode: data.reply_mode as PrivateSnapshot["replyMode"] } : {}),
    ...(typeof position.branch_id==="string"&&[history.content_revision,history.invalidation_epoch,history.access_epoch].every(v=>Number.isSafeInteger(v)&&Number(v)>=0)?{expressionCheckpoint:{session_id:text(history.session_id),branch_id:text(position.branch_id),revision:currentRevision,head_turn_id:text(position.head_turn_id),content_revision:Number(history.content_revision),invalidation_epoch:Number(history.invalidation_epoch),access_epoch:Number(history.access_epoch)}}:{}),
  }
}
export function createPrivateChatClient(request: Transport, accountId: string, friendId: string, epoch: number) {
  const authority = { expected_account_id: accountId, expected_friend_epoch: epoch }
  let replyMode = "unconfirmed"
  const parse = (value: unknown) => { const snapshot = parsePrivateSnapshot(value, friendId, epoch); replyMode = snapshot.replyMode ?? "unconfirmed"; return snapshot }
  const replay = async (command: PrivateCommand) => {
    const { session_id, ...body } = parsePrivateCommand(command)
    const trace = startChatTiming("private", replyMode)
    try {
      const operation = parsePrivateOperation(await request(`/conversations/${encodeURIComponent(session_id)}/operations`, { ...body, ...authority }))
      receivedChatTiming(trace, operation.operation_id, operation.status, operation.turn_id)
      return operation
    } catch (error) { failedChatTiming(trace); throw error }
  }
  return {
    open: async (key: string, language: "zh" | "en") => parse(await request(`/friends/${encodeURIComponent(friendId)}/conversation`, { key, ...authority, language })),
    read: async (id: string) => {
      const snapshot = parse(await request(`/conversations/${encodeURIComponent(id)}`))
      if (snapshot.conversation.id !== id) return invalid()
      return snapshot
    },
    replay,
    send: async (snapshot: PrivateSnapshot, key: string, message: string, language: "zh" | "en", recallSessionId?: string) => replay({ session_id: snapshot.conversation.id, key, presented_turn_id: snapshot.history.position.head_turn_id!, expected_revision: snapshot.history.position.revision, text: message, language, ...(recallSessionId ? { recall_session_id: recallSessionId } : {}) }),
    result: async (id: string) => {
      const operation = parsePrivateOperation(await deduplicateChatRead(request, JSON.stringify(["private-operation", accountId, friendId, epoch, id]), () => request(`/operations/${encodeURIComponent(id)}`)))
      if (operation.operation_id !== id) return invalid()
      observeChatOperation("private", operation.operation_id, operation.status, operation.turn_id, true)
      return operation
    },
    lookup: async (id: string, key: string) => parsePrivateOperation(await request(`/conversations/${encodeURIComponent(id)}/operations/lookup?key=${encodeURIComponent(key)}`)),
    retry: async (id: string) => parsePrivateOperation(await request(`/operations/${encodeURIComponent(id)}/retry`, authority)),
    cancel: async (id: string) => parsePrivateOperation(await request(`/operations/${encodeURIComponent(id)}/cancel`, authority)),
  }
}
