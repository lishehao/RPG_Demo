/**
 * Account / character / friend wire parsers.
 * Ported from reference/contracts/companion-client.ts (frozen 677b1b4b). Changes:
 *  - avatar allowlist rebased to this project's hash-verified asset copy (/handoff/assets/...)
 *    plus `null` for works without an approved image (UI shows a neutral placeholder);
 *  - friends carry display-only fields (source_name, created_at, origin) used to tell
 *    same-name / same-source friends apart; identity is still id + epoch + source/version.
 */
export class CompanionRequestError extends Error {
  constructor(public code: string, public status = 0, public detail: Record<string, unknown> | null = null) { super('Companion request failed') }
}
const invalid = (): never => { throw new CompanionRequestError('invalid_response') }
export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid()
  return value as Record<string, unknown>
}
export function string(value: unknown, max = 512): string {
  if (typeof value !== 'string' || !value || value.length > max) return invalid()
  return value
}
function integer(value: unknown): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) return invalid()
  return Number(value)
}
function localized(value: unknown, max = 2000) {
  const row = object(value)
  return {zh: string(row.zh, max), en: string(row.en, max)}
}

const APPROVED_PORTRAIT = /^\/handoff\/assets\/companions\/(?:portraits\/(?:arthur-r7|lena-soft-anime-v2|marcus-r3|nora-r4|iris-local|arthur-local|lena-local|marcus-local|nora-local)-neutral\.png|feed\/(?:arthur|lena|marcus|nora|iris)\.webp)$/
export function parseAvatar(value: unknown): string | null {
  if (value === null) return null
  const path = string(value)
  if (!APPROVED_PORTRAIT.test(path)) return invalid()
  return path
}

export type AccountSession = {
  authenticated: boolean
  account: {id: string; email: string} | null
  guest_id: string
  /** avatar: id of a preset persona picture (an object, never a person), or null. */
  persona: {name: string; bio: string; avatar: string | null} | null
  mode: 'local_mock'
}
const PERSONA_AVATAR = /^persona-avatar-0[1-8]$/
export function parseAccount(value: unknown): AccountSession {
  const data = object(value)
  const guest = string(data.guest_id, 80)
  if (!guest.startsWith('guest_')) return invalid()
  if (data.mode !== 'local_mock') return invalid()
  const persona = data.persona === null || data.persona === undefined ? null : (() => {
    const p = object(data.persona)
    return {name: typeof p.name === 'string' ? p.name.slice(0, 40) : '', bio: typeof p.bio === 'string' ? p.bio.slice(0, 400) : '',
      avatar: typeof p.avatar === 'string' && PERSONA_AVATAR.test(p.avatar) ? p.avatar : null}
  })()
  if (data.authenticated === false && data.account === null) return {authenticated: false, account: null, guest_id: guest, persona, mode: 'local_mock'}
  if (data.authenticated !== true) return invalid()
  const account = object(data.account)
  const id = string(account.id, 80)
  if (!id.startsWith('acc_')) return invalid()
  return {authenticated: true, account: {id, email: string(account.email, 254)}, guest_id: guest, persona, mode: 'local_mock'}
}

export type CharacterWork = {
  id: string; version: string; name: string; avatar: string | null; feed: string | null
  description: {zh: string; en: string}; tagline: {zh: string; en: string}
  traits: {zh: string; en: string}[]; origin: 'official' | 'mine'; voice: string
  live2d: 'arthur' | 'lena' | 'marcus' | 'nora' | 'iris' | null
}
const LIVE2D = ['arthur', 'lena', 'marcus', 'nora', 'iris'] as const
export function parseCharacter(item: unknown): CharacterWork {
  const row = object(item)
  const live2d = row.live2d === null ? null : String(row.live2d)
  if (live2d !== null && !(LIVE2D as readonly string[]).includes(live2d)) return invalid()
  // A Live2D binding is only accepted for the official v1 source it was pinned to.
  if (live2d && (row.id !== `official-${live2d}` || row.version !== '1')) return invalid()
  if (row.origin !== 'official' && row.origin !== 'mine') return invalid()
  if (!Array.isArray(row.traits) || row.traits.length > 8) return invalid()
  return {
    id: string(row.id, 80), version: string(row.version, 80), name: string(row.name, 160),
    avatar: parseAvatar(row.avatar), feed: row.feed === null ? null : parseAvatar(row.feed),
    description: localized(row.description), tagline: localized(row.tagline, 400),
    traits: row.traits.map(t => localized(t, 120)), origin: row.origin, voice: string(row.voice, 80),
    live2d: live2d as CharacterWork['live2d'],
  }
}
export function parseCharacters(value: unknown): CharacterWork[] {
  const data = object(value)
  if (!Array.isArray(data.items) || data.items.length > 100) return invalid()
  return data.items.map(parseCharacter)
}

export type CompanionFriend = {
  id: string; source_id: string; source_version: string; name: string; avatar: string | null
  epoch: number; revision: number; display_number: number; status: 'active'
  source_name: string; created_at: string; origin: {kind: 'character' | 'story' | 'game' | 'creation'; label: {zh: string; en: string}}
  live2d: CharacterWork['live2d']
}
export function parseFriend(value: unknown): CompanionFriend {
  const data = object(value)
  if (data.status !== 'active') return invalid()
  const origin = object(data.origin)
  if (!['character', 'story', 'game', 'creation'].includes(String(origin.kind))) return invalid()
  const live2d = data.live2d === null ? null : String(data.live2d)
  if (live2d !== null && (!(LIVE2D as readonly string[]).includes(live2d) || data.source_id !== `official-${live2d}` || data.source_version !== '1')) return invalid()
  return {
    id: string(data.id, 80), source_id: string(data.source_id, 80), source_version: string(data.source_version, 80),
    name: string(data.name, 160), avatar: parseAvatar(data.avatar), epoch: integer(data.epoch), revision: integer(data.revision),
    display_number: integer(data.display_number), status: 'active', source_name: string(data.source_name, 160),
    created_at: string(data.created_at, 40), origin: {kind: origin.kind as CompanionFriend['origin']['kind'], label: localized(origin.label, 200)},
    live2d: live2d as CompanionFriend['live2d'],
  }
}
export function parseFriends(value: unknown, expectedAccountId?: string): {items: CompanionFriend[]; total: number} {
  const data = object(value)
  if (expectedAccountId && data.owner_id !== expectedAccountId) throw new CompanionRequestError('account_changed')
  if (!Array.isArray(data.items) || data.items.length > 100) return invalid()
  return {items: data.items.map(parseFriend), total: integer(data.total)}
}
