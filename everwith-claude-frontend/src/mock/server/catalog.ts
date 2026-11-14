import {GAMES, OFFICIAL_CHARACTERS, STORIES} from '../catalog'
import {db} from '../db'
import {fail, ok} from '../http'
import type {MockRequest, MockResult} from '../http'
import {scenarios} from '../scenarios'
import {actor} from './context'

export function characterJSON(c: (typeof OFFICIAL_CHARACTERS)[number]) {
  return {id: c.id, version: c.version, name: c.name, avatar: c.avatar, feed: c.feed, description: c.description, tagline: c.tagline,
    traits: c.traits, origin: 'official', voice: c.voice, live2d: c.live2d}
}
/** A saved character work owned by the caller, exposed as a character source (F5). */
export function workCharacterJSON(workId: string, version: number) {
  const w = db().works[workId]
  if (!w || w.deleted || w.type !== 'character' || w.owner !== actor()) fail(404, 'not_found')
  const v = w.versions.find(x => x.version === version)
  if (!v) fail(404, 'not_found')
  const d = v!.draft as Record<string, string>
  const text = (s: unknown) => typeof s === 'string' && s.trim() ? s : '—'
  return {id: `work-${w.id}`, version: String(version), name: text(d.name), avatar: null, feed: null,
    description: {zh: text(d.intro), en: text(d.intro)}, tagline: {zh: text(d.tagline), en: text(d.tagline)},
    traits: [], origin: 'mine', voice: typeof d.voice === 'string' && d.voice ? d.voice : 'preset-neutral', live2d: null}
}
export function storyJSON(s: (typeof STORIES)[number]) {
  const byId = (id: string) => OFFICIAL_CHARACTERS.find(c => c.id === id)!
  return {id: s.id, version: s.version, title: s.title, description: s.description, genre: s.genre, content_note: s.contentNote,
    image: s.cover, image_wide: s.coverWide, player_role: s.playerRole, player_entry: 'script', objectives: s.objectives,
    roles: s.roles.map(r => ({id: r.id, title: r.title, description: r.description, replaceable: r.replaceable, locked: !!r.locked, default_character: characterJSON(byId(r.defaultCharacter))}))}
}
export function gameJSON(g: (typeof GAMES)[number]) {
  return {id: g.id, slug: g.slug, name: g.name, description: g.description, players: g.players, default_players: g.defaultPlayers,
    profile: g.profile, profile_label: g.profileLabel, poster: g.poster, preview: g.preview, rule_notes: g.ruleNotes}
}
const matches = (q: string, ...texts: (string | {zh: string; en: string})[]) => !q || texts.some(t => (typeof t === 'string' ? t : `${t.zh} ${t.en}`).toLowerCase().includes(q))

export function handleCatalog(req: MockRequest): MockResult | null {
  if (req.method !== 'GET') return null
  if (req.path === '/characters') return ok({items: OFFICIAL_CHARACTERS.map(characterJSON)})
  const ch = /^\/characters\/([^/]+)$/.exec(req.path)
  if (ch) {
    const id = decodeURIComponent(ch[1]), version = req.query.get('version') ?? '1'
    const official = OFFICIAL_CHARACTERS.find(c => c.id === id && c.version === version)
    if (official) return ok(characterJSON(official))
    const work = /^work-(.+)$/.exec(id)
    if (work) return ok(workCharacterJSON(work[1], Number(version)))
    fail(404, 'not_found')
  }
  if (req.path === '/stories') return ok({items: STORIES.map(storyJSON)})
  const st = /^\/stories\/([^/]+)$/.exec(req.path)
  if (st) {
    const s = STORIES.find(x => x.id === decodeURIComponent(st[1]) && x.version === (req.query.get('version') ?? x.version))
    if (!s) fail(404, 'not_found')
    return ok(storyJSON(s!))
  }
  if (req.path === '/games') return ok({items: GAMES.map(gameJSON)})
  if (req.path === '/discover') {
    const type = req.query.get('type') ?? 'all', q = (req.query.get('q') ?? '').trim().toLowerCase()
    const offset = Number(req.query.get('offset') ?? 0), limit = Math.min(24, Number(req.query.get('limit') ?? 8))
    if (scenarios.isOn('discover.error') && offset === 0) fail(503, 'discover_unavailable')
    if (scenarios.isOn('discover.append_error') && offset > 0) fail(503, 'discover_unavailable')
    const items = [
      ...(type === 'all' || type === 'characters' ? OFFICIAL_CHARACTERS.filter(c => matches(q, c.name, c.tagline, c.description)).map(c => ({kind: 'character', ...characterJSON(c)})) : []),
      ...(type === 'all' || type === 'stories' ? STORIES.filter(s => matches(q, s.title, s.description, s.genre)).map(s => ({kind: 'story', ...storyJSON(s)})) : []),
      ...(type === 'all' || type === 'games' ? GAMES.filter(g => matches(q, g.name, g.description)).map(g => ({kind: 'game', ...gameJSON(g)})) : []),
    ]
    const page = items.slice(offset, offset + limit)
    return ok({items: page, total: items.length, next_offset: offset + page.length < items.length ? offset + page.length : null})
  }
  return null
}
