/** Presentation-only helpers: drafts, reading anchors, expression cues. No server state. */
import {readJSON, writeJSON, removeKey} from '../lib/util'
import type {Expression} from '../live2d/performer'

export type DraftScope = {accountId: string; friendId: string; epoch: number; conversationId: string}
const draftKey = (s: DraftScope) => `everwith.draft.v1:${JSON.stringify([s.accountId, s.friendId, s.epoch, s.conversationId])}`
export type Draft = {text: string; start: number; end: number}
export function readDraft(s: DraftScope): Draft | null { return readJSON<Draft | null>(draftKey(s), null) }
export function writeDraft(s: DraftScope, d: Draft) { if (d.text) writeJSON(draftKey(s), d); else removeKey(draftKey(s)) }

/** Reading position (anchor message + offset), per account/friend/epoch/conversation. */
export type ReadingPosition = {anchorId: string | null; offset: number; atEnd: boolean}
const readingKey = (s: DraftScope) => `everwith.reading.v1:${JSON.stringify([s.accountId, s.friendId, s.epoch, s.conversationId])}`
export function readReading(s: DraftScope): ReadingPosition | null { return readJSON<ReadingPosition | null>(readingKey(s), null, 'session') }
export function writeReading(s: DraftScope, p: ReadingPosition) { writeJSON(readingKey(s), p, 'session') }

/**
 * Local deterministic cue from VISIBLE public text only (provider_mode
 * local_deterministic). Only the three supported faces; anything else stays neutral.
 */
export function expressionForText(text: string): Expression {
  const t = text.replace(/\*[^*]*\*/g, ' ')
  if (/[!！]{1}.*[?？]|[?？][!！]|真的|竟然|居然|不会吧|等等|really|wait|seriously|no way/i.test(t)) return 'surprised'
  if (/笑|开心|谢谢|好啊|不错|太好了|高兴|glad|smile|great|sure|thanks|happy|nice/i.test(text)) return 'happy'
  return 'neutral'
}
