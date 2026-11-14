import {characterById} from '../catalog'
import {db, now, save} from '../db'
import type {FriendRow} from '../db'
import {fail, fingerprint, int, ok, str} from '../http'
import type {MockRequest, MockResult} from '../http'
import {expectAccount, requireAccount} from './context'
import {workCharacterJSON} from './catalog'
import {randomId} from '../../lib/util'
import type {L10n} from '../../lib/util'

export function friendJSON(f: FriendRow) {
  const official = characterById(f.source_id)
  const live2d = official && f.source_version === '1' ? official.live2d : null
  return {id: f.id, source_id: f.source_id, source_version: f.source_version, name: f.name, avatar: official?.avatar ?? null,
    epoch: f.epoch, revision: f.revision, display_number: f.display_number, status: 'active', source_name: f.source_name,
    created_at: f.created_at, origin: {kind: f.origin.kind, label: f.origin.label}, live2d}
}
export function activeFriend(id: string, owner: string): FriendRow {
  const f = db().friends[id]
  if (!f || f.owner !== owner || f.status !== 'active') fail(404, 'not_found')
  return f
}
function sourceName(sourceId: string, version: string): string {
  const official = characterById(sourceId)
  if (official && version === official.version) return official.name
  const work = /^work-(.+)$/.exec(sourceId)
  if (work) return (workCharacterJSON(work[1], Number(version)) as {name: string}).name
  return fail(404, 'source_not_found')
}

export type FriendCreateHook = (friend: FriendRow, origin: Record<string, unknown>) => void
const hooks: FriendCreateHook[] = []
/** Story/game modules bind “this exact person” (F2/F7) in the same commit as the friend. */
export function onFriendCreated(hook: FriendCreateHook) { hooks.push(hook) }
export type FriendOriginValidator = (origin: Record<string, unknown>, owner: string, sourceId: string, version: string) => {label: L10n; kind: FriendRow['origin']['kind']; session_id?: string}
const validators: Record<string, FriendOriginValidator> = {}
export function registerOrigin(kind: string, v: FriendOriginValidator) { validators[kind] = v }

export function handleFriends(req: MockRequest): MockResult | null {
  const d = db()
  if (req.path === '/friends' && req.method === 'GET') {
    const me = requireAccount()
    if (req.query.get('expected_account_id') && req.query.get('expected_account_id') !== me.id) fail(409, 'account_changed')
    const q = (req.query.get('q') ?? '').trim().toLowerCase()
    const items = Object.values(d.friends).filter(f => f.owner === me.id && f.status === 'active' && (!q || `${f.name} ${f.source_name}`.toLowerCase().includes(q)))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
    return ok({owner_id: me.id, items: items.slice(0, 100).map(friendJSON), total: items.length})
  }
  if (req.path === '/friends' && req.method === 'POST') {
    const me = requireAccount(); expectAccount(req.body)
    const key = str(req.body, 'key', 128), sourceId = str(req.body, 'source_id', 80), version = str(req.body, 'source_version', 80)
    const name = str(req.body, 'name', 40).trim()
    if (!name) fail(422, 'name_required')
    const origin = (req.body?.origin ?? {kind: 'character'}) as Record<string, unknown>
    const fp = fingerprint({sourceId, version, name, origin})
    const existing = Object.values(d.friends).find(f => f.owner === me.id && f.key === key)
    if (existing) {
      // Same key replays the original result; a different intent under that key is rejected.
      if (existing.fingerprint !== fp) fail(409, 'idempotency_conflict')
      return ok(friendJSON(existing))
    }
    const src = sourceName(sourceId, version)
    const kind = String(origin.kind ?? 'character')
    const v = kind === 'character' ? null : validators[kind]
    if (kind !== 'character' && !v) fail(400, 'invalid_origin')
    const resolved = v ? v(origin, me.id, sourceId, version) : {kind: (sourceId.startsWith('work-') ? 'creation' : 'character') as FriendRow['origin']['kind'], label: sourceId.startsWith('work-') ? {zh: '来自我保存的角色作品', en: 'From my saved character work'} : {zh: '来自公开角色介绍', en: 'From the public character page'}}
    const sameSource = Object.values(d.friends).filter(f => f.owner === me.id && f.source_id === sourceId)
    const row: FriendRow = {id: randomId('fr', 8), owner: me.id, source_id: sourceId, source_version: version, source_name: src, name,
      epoch: 1, revision: 1, display_number: sameSource.length + 1, status: 'active', created_at: now(),
      origin: {kind: resolved.kind, label: resolved.label, session_id: resolved.session_id}, key, fingerprint: fp}
    d.friends[row.id] = row
    for (const hook of hooks) hook(row, origin)
    save()
    return ok(friendJSON(row), 201)
  }
  const one = /^\/friends\/([^/]+)$/.exec(req.path)
  if (one && req.method === 'GET') {
    const me = requireAccount()
    return ok(friendJSON(activeFriend(decodeURIComponent(one[1]), me.id)))
  }
  const action = /^\/friends\/([^/]+)\/(rename|reset|remove)$/.exec(req.path)
  if (action && req.method === 'POST') {
    const me = requireAccount(); expectAccount(req.body)
    const f = activeFriend(decodeURIComponent(action[1]), me.id)
    if (int(req.body, 'expected_epoch') !== f.epoch) fail(409, 'friend_epoch_changed')
    if (action[2] === 'rename') {
      const name = str(req.body, 'name', 40).trim(); if (!name) fail(422, 'name_required')
      f.name = name; f.revision++
    } else if (action[2] === 'reset') {
      // New generation: old chats and affected activities become read-only, never deleted.
      f.epoch++; f.revision++
      for (const c of Object.values(d.conversations)) if (c.friend_id === f.id && c.friend_epoch < f.epoch) c.status = 'read_only'
      for (const s of Object.values(d.stories)) if (s.cast.some(r => r.friend_id === f.id)) s.status = 'read_only'
    } else {
      f.status = 'removed'; f.revision++
      for (const c of Object.values(d.conversations)) if (c.friend_id === f.id) c.status = 'read_only'
    }
    save()
    return ok({friend: action[2] === 'remove' ? null : friendJSON(f), removed: action[2] === 'remove'})
  }
  return null
}
