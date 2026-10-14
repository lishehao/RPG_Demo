import {gameById, storyById} from '../catalog'
import {db, now, save} from '../db'
import {fail, ok} from '../http'
import type {MockRequest, MockResult} from '../http'
import {actor} from './context'

/** Concrete story/game records: one row per session, never merged by work name. */
export function handleRecords(req: MockRequest): MockResult | null {
  const d = db()
  if (req.path === '/records' && req.method === 'GET') {
    const archived = req.query.get('archived') === '1'
    const stories = Object.values(d.stories).filter(s => s.owner === actor() && !s.deleted && s.archived === archived).map(s => {
      const def = storyById(s.story_id, s.version)!
      return {kind: 'story', id: s.id, work_id: s.story_id, version: s.version, title: def.title, image: def.cover, status: s.status === 'read_only' ? 'read_only' : s.pending ? 'in_progress' : 'active',
        lineup: s.cast.map(c => ({role: def.roles.find(r => r.id === c.role_id)!.title, name: c.name, friend: c.kind === 'friend'})),
        turns: s.turns.length, created_at: s.created_at, updated_at: s.updated_at, archived: s.archived}
    })
    const games = Object.values(d.games).filter(g => g.owner === actor() && !g.deleted && g.archived === archived).map(g => {
      const def = gameById(g.game_id)!
      return {kind: 'game', id: g.id, work_id: g.game_id, version: g.profile, title: {zh: def.name, en: def.name}, image: def.poster, status: g.lifecycle,
        lineup: g.seats.map(s => ({role: null, name: s.name, friend: s.kind === 'friend', temporary: s.kind === 'temporary'})),
        revision: g.revision, created_at: g.created_at, updated_at: g.updated_at, archived: g.archived, rematch_of: g.rematch_of,
        result: g.settlement ? {scores: g.settlement.scores, winners: g.settlement.winners} : null}
    })
    return ok({items: [...stories, ...games].sort((a, b) => b.updated_at.localeCompare(a.updated_at))})
  }
  const m = /^\/records\/(story|game)\/([^/]+)\/(archive|restore|delete)$/.exec(req.path)
  if (m && req.method === 'POST') {
    const table = m[1] === 'story' ? d.stories : d.games
    const row = table[decodeURIComponent(m[2])] as {owner: string; archived: boolean; deleted: boolean; updated_at: string} | undefined
    if (!row || row.owner !== actor() || row.deleted) fail(404, 'not_found')
    if (m[3] === 'archive') row!.archived = true
    else if (m[3] === 'restore') row!.archived = false
    else {
      // Delete removes this record's text and state; other records and friends are untouched.
      row!.deleted = true
      if (m[1] === 'story') { const s = d.stories[decodeURIComponent(m[2])]; s.turns = []; s.pending = null }
      else { const g = d.games[decodeURIComponent(m[2])]; g.chat = []; g.public_log = []; g.state = null }
    }
    row!.updated_at = now(); save()
    return ok({ok: true})
  }
  return null
}
