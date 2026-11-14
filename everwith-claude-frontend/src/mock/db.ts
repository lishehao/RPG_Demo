/**
 * LOCAL MOCK persistence. Everything lives in this browser's localStorage under one
 * key, so refresh/restore can be exercised. This is NOT an authentication system and
 * NOT multi-user secret storage: a browser demo that holds game truth cannot claim
 * secret safety (06_API_AND_MOCK.md). Production must use a real server.
 */
import {randomId, readJSON, writeJSON} from '../lib/util'
import type {L10n, Lang} from '../lib/util'

export const DB_KEY = 'everwith.mock.db.v1'

export type PersonaRow = {name: string; bio: string; avatar?: string | null}
export type AccountRow = {id: string; email: string; salt: string; hash: string; created_at: string; persona: PersonaRow | null}
export type FriendRow = {
  id: string; owner: string; source_id: string; source_version: string; source_name: string; name: string
  epoch: number; revision: number; display_number: number; status: 'active' | 'removed'
  created_at: string; origin: {kind: 'character' | 'story' | 'game' | 'creation'; label: L10n; session_id?: string}
  key: string; fingerprint: string
}
export type SegmentRow = {segment_id: string; kind: 'dialogue' | 'narration' | 'action'; speaker_id: string | null; body: string | null; availability: 'available' | 'withdrawn'}
export type TurnRow = {turn_id: string; player_expression: string | null; input_availability: 'available' | 'withdrawn'; segments: SegmentRow[]; language: Lang; expression: 'neutral' | 'happy' | 'surprised'; created_at: string; kind: 'greeting' | 'reply' | 'note'}
export type ConversationRow = {
  id: string; owner: string; friend_id: string; friend_epoch: number; binding_version: number; status: 'active' | 'read_only'
  revision: number; turns: TurnRow[]; player_actor_id: string; created_at: string; updated_at: string
  content_revision: number; invalidation_epoch: number; access_epoch: number
}
export type OperationStatus = 'accepted' | 'running' | 'validating' | 'retryable_failed' | 'committed' | 'cancelled' | 'failed_final' | 'stale'
export type OperationRow = {
  id: string; conversation_id: string; owner: string; friend_id: string; friend_epoch: number; key: string
  text: string; language: Lang; baseline_revision: number; baseline_head: string
  status: OperationStatus; run_epoch: number; turn_id: string | null; created_at: string
  /** Pre-decided public reply (simulated, deterministic). Never streamed before its run starts. */
  plan: {segments: {segment_id: string; kind: 'spoken' | 'action' | 'narration'; text: string}[]; expression: 'neutral' | 'happy' | 'surprised'}
  scenario: string | null; late_on_retry: boolean; commit_at: number | null; run_started_at: number | null
}
export type StorySessionRow = {
  id: string; owner: string; story_id: string; version: string; key: string; fingerprint: string
  cast: {role_id: string; kind: 'npc' | 'friend'; character_id: string; friend_id: string | null; friend_epoch: number | null; name: string}[]
  turns: StoryTurnRow[]; revision: number; status: 'active' | 'read_only'; archived: boolean; deleted: boolean
  state: {beat: number; objective: number; clues: string[]; minutes: number; scene: string; present: string[]}
  created_at: string; updated_at: string; language: Lang
  pending: {op_id: string; key: string; kind: 'input' | 'continue'; text: string | null; status: OperationStatus; commit_at: number; language: Lang; fail?: boolean} | null
  ops: Record<string, {key: string; status: string; turn_id: string | null}>
}
export type StoryTurnRow = {
  turn_id: string; kind: 'opening' | 'input' | 'continue'; input: string | null; input_availability: 'available' | 'withdrawn'
  segments: {segment_id: string; kind: 'narration' | 'dialogue' | 'action'; role_id: string | null; text: string}[]
  delta: {clue?: string; objective?: number; minutes: number; beat?: number}; availability: 'available' | 'withdrawn'; language: Lang; created_at: string
}
export type GameSeatRow = {seat: number; kind: 'player' | 'friend' | 'temporary'; identity: string; friend_epoch: number | null; name: string; source_id: string | null; source_version: string | null}
export type GameRow = {
  id: string; owner: string; game_id: 'vegas' | 'gems' | 'cabo'; profile: string; key: string; fingerprint: string
  seats: GameSeatRow[]; lifecycle: 'active' | 'paused' | 'ended' | 'abandoned'; revision: number; ai_hold: boolean
  state: unknown; seed: number | string; origin: {kind: 'discover' | 'friend' | 'private'; friend_id?: string; conversation_id?: string; return_hash: string}
  chat: {id: string; seat: number; text: string; audience: 'table'; mode: 'player' | 'simulated_rule_reply'; kind: 'dialogue' | 'narration'; language: Lang; revision: number}[]
  settlement: null | {id: string; committed_revision: number; scores: number[]; winners: number[]; labels: L10n[]}
  actions: Record<string, {fingerprint: string; revision: number}>
  created_at: string; updated_at: string; rematch_of: string | null; archived: boolean; deleted: boolean
  public_log: {revision: number; seat: number; summary: L10n; kind: string}[]
}
export type WorkRow = {
  id: string; owner: string; type: 'story' | 'character'; name: string; created_at: string; updated_at: string; key: string
  draft: Record<string, unknown>; draft_revision: number; versions: {version: number; draft: Record<string, unknown>; saved_at: string}[]
  share: {enabled: boolean; version: number | null}; deleted: boolean
}
export type PreviewRow = {id: string; owner: string; work_id: string; draft_revision: number; snapshot: Record<string, unknown>; turns: {id: string; role: 'player' | 'character'; text: string; language: Lang}[]; created_at: string}

export type DB = {
  schema: 'everwith-mock-db-v1'
  guest_id: string
  session_account: string | null
  accounts: Record<string, AccountRow>
  guest_personas: Record<string, PersonaRow>
  merged_guests: Record<string, string>
  friends: Record<string, FriendRow>
  conversations: Record<string, ConversationRow>
  operations: Record<string, OperationRow>
  stories: Record<string, StorySessionRow>
  games: Record<string, GameRow>
  works: Record<string, WorkRow>
  previews: Record<string, PreviewRow>
  corrections: {id: string; conversation_id: string; turn_id: string | null; text: string; created_at: string}[]
}

export function emptyDB(): DB {
  return {schema: 'everwith-mock-db-v1', guest_id: randomId('guest'), session_account: null, accounts: {}, guest_personas: {}, merged_guests: {},
    friends: {}, conversations: {}, operations: {}, stories: {}, games: {}, works: {}, previews: {}, corrections: []}
}

let cache: DB | null = null
export function db(): DB {
  if (cache) return cache
  const stored = readJSON<DB | null>(DB_KEY, null)
  cache = stored && stored.schema === 'everwith-mock-db-v1' ? stored : emptyDB()
  if (!stored) save()
  return cache
}
export function save() { if (cache) writeJSON(DB_KEY, cache) }
export function resetDB() { cache = emptyDB(); save() }
/** Re-read from storage (another tab may have written). */
export function reloadDB() { cache = null; return db() }
export const now = () => new Date().toISOString()
