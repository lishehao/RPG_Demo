/**
 * Creation studio (LOCAL MOCK): works, drafts, immutable versions, explicit sharing
 * and isolated previews. “AI 改稿” here is a deterministic local template, labelled
 * as such — no model is called. Previews never touch friends, chats or memories.
 */
import {OFFICIAL_CHARACTERS} from '../catalog'
import {db, now, save} from '../db'
import type {WorkRow} from '../db'
import {fail, int, ok, str} from '../http'
import type {MockRequest, MockResult} from '../http'
import {previewReply} from '../replies'
import {actor, requireAccount} from './context'
import {hash32, randomId} from '../../lib/util'
import type {Lang} from '../../lib/util'
import {WORK_COVERS, isWorkCover} from '../../art/generated'

export const VOICES = ['preset-neutral', 'preset-warm', 'preset-bright', 'preset-low', 'preset-calm']
export function blankDraft(type: 'story' | 'character', name: string): Record<string, unknown> {
  if (type === 'character') return {name, tagline: '', intro: '', persona: '', habit: '', background: '', opening: '', voice: 'preset-neutral', portrait: 'placeholder'}
  return {title: name, intro: '', genre: '', content_note: '', setting: '', player_entry: '', opening: '', narrative: 'balanced', mode: 'open',
    roles: [{id: 'role-1', title: '', description: '', character: 'official-lena', replaceable: true, locked: false}],
    worldbook: [], items: [], stages: []}
}
export function validateDraft(type: 'story' | 'character', d: Record<string, unknown>): {field: string; code: string}[] {
  const errors: {field: string; code: string}[] = []
  const s = (k: string) => typeof d[k] === 'string' ? (d[k] as string).trim() : ''
  // Cover: optional; when present it must be one of the preset ids (never a URL).
  if (d.cover !== undefined && !isWorkCover(d.cover)) errors.push({field: 'cover', code: 'invalid'})
  if (type === 'character') {
    if (!s('name')) errors.push({field: 'name', code: 'required'})
    if ([...s('name')].length > 40) errors.push({field: 'name', code: 'too_long'})
    if (!s('intro')) errors.push({field: 'intro', code: 'required'})
    if (!s('persona')) errors.push({field: 'persona', code: 'required'})
    if (!VOICES.includes(String(d.voice))) errors.push({field: 'voice', code: 'invalid'})
  } else {
    if (!s('title')) errors.push({field: 'title', code: 'required'})
    if (!s('opening')) errors.push({field: 'opening', code: 'required'})
    const roles = Array.isArray(d.roles) ? d.roles as Record<string, unknown>[] : []
    if (!roles.length) errors.push({field: 'roles', code: 'required'})
    if (roles.length > 10) errors.push({field: 'roles', code: 'too_many'})
    roles.forEach((r, i) => {
      if (typeof r.title !== 'string' || !r.title.trim()) errors.push({field: `roles.${i}.title`, code: 'required'})
      if (!OFFICIAL_CHARACTERS.some(c => c.id === r.character)) errors.push({field: `roles.${i}.character`, code: 'invalid'})
    })
    if (!['open', 'ending'].includes(String(d.mode))) errors.push({field: 'mode', code: 'invalid'})
  }
  return errors
}
function workJSON(w: WorkRow) {
  const latest = w.versions[w.versions.length - 1] ?? null
  return {id: w.id, type: w.type, name: w.name, created_at: w.created_at, updated_at: w.updated_at, draft: w.draft, draft_revision: w.draft_revision,
    versions: w.versions.map(v => ({version: v.version, saved_at: v.saved_at})), latest_version: latest?.version ?? null,
    dirty: !latest || JSON.stringify(latest.draft) !== JSON.stringify(w.draft), errors: validateDraft(w.type, w.draft), share: w.share,
    owner_kind: actor().startsWith('acc_') ? 'account' : 'guest'}
}
function ownedWork(id: string) {
  const w = db().works[id]
  if (!w || w.owner !== actor() || w.deleted) fail(404, 'not_found')
  return w
}
function assist(type: 'story' | 'character', draft: Record<string, unknown>, instruction: string, lang: Lang): {draft: Record<string, unknown>; summary: string[]} {
  const next = structuredClone(draft), summary: string[] = []
  const set = (k: string, v: unknown, label: string) => { next[k] = v; summary.push(label) }
  const empty = (k: string) => typeof next[k] !== 'string' || !(next[k] as string).trim()
  const zh = lang === 'zh'
  if (instruction === 'fill') {
    if (type === 'character') {
      const n = String(next.name || (zh ? '无名角色' : 'Unnamed'))
      if (empty('tagline')) set('tagline', zh ? '安静的观察者' : 'A quiet observer', zh ? '补全一句话身份' : 'Filled tagline')
      if (empty('intro')) set('intro', zh ? `${n}习惯先听完再开口，说话不绕弯子。` : `${n} listens first and speaks plainly.`, zh ? '补全公开介绍' : 'Filled public intro')
      if (empty('persona')) set('persona', zh ? '重视约定；不喜欢被催促；对熟悉的人会开玩笑。' : 'Values promises; dislikes being rushed; jokes with people they trust.', zh ? '补全人物设定' : 'Filled persona')
      if (empty('habit')) set('habit', zh ? '说话前会停顿一下' : 'Pauses briefly before speaking', zh ? '补全表达习惯' : 'Filled speaking habit')
      if (empty('opening')) set('opening', zh ? '*抬起头。*\n你来了。' : '*Looks up.*\nThere you are.', zh ? '补全开场' : 'Filled opening')
    } else {
      if (empty('intro')) set('intro', zh ? '一个关于约定与误会的小故事。' : 'A small story about a promise and a misunderstanding.', zh ? '补全简介' : 'Filled summary')
      if (empty('setting')) set('setting', zh ? '雨夜，一座老剧院的后台。' : 'A rainy night backstage at an old theatre.', zh ? '补全世界设定' : 'Filled setting')
      if (empty('player_entry')) set('player_entry', zh ? '玩家以受邀客人的身份进入。' : 'The player enters as an invited guest.', zh ? '补全玩家入场' : 'Filled player entry')
      if (empty('opening')) set('opening', zh ? '雨声很大，后台的门半开着。' : 'The rain is loud; the backstage door stands ajar.', zh ? '补全开场' : 'Filled opening')
      const roles = next.roles as Record<string, unknown>[]
      roles.forEach((r, i) => { if (typeof r.title !== 'string' || !r.title.trim()) { r.title = zh ? `角色 ${i + 1}` : `Role ${i + 1}`; summary.push(zh ? `补全角色位 ${i + 1} 名称` : `Named role ${i + 1}`) } })
    }
  } else if (instruction === 'shorter') {
    const k = type === 'character' ? 'intro' : 'intro'
    if (!empty(k)) { const t = [...String(next[k])]; if (t.length > 24) set(k, t.slice(0, 24).join('') + '…', zh ? '缩短简介' : 'Shortened summary') }
  } else if (instruction === 'add_role' && type === 'story') {
    const roles = next.roles as Record<string, unknown>[]
    if (roles.length >= 10) summary.push(zh ? '已达到 10 个 AI 位，未添加' : 'Already 10 AI roles; nothing added')
    else { roles.push({id: `role-${roles.length + 1}`, title: zh ? '新角色位' : 'New role', description: '', character: 'official-nora', replaceable: true, locked: false}); summary.push(zh ? '新增一个角色位（默认 Nora，可替换）' : 'Added a role (Nora by default, replaceable)') }
  } else if (instruction === 'warmer' && type === 'character') {
    set('habit', `${String(next.habit || '')}${next.habit ? '；' : ''}${zh ? '会用对方的名字称呼对方' : 'uses your name when talking'}`, zh ? '表达更亲近' : 'Warmer speaking habit')
  }
  if (!summary.length) summary.push(zh ? '没有可修改的地方' : 'Nothing to change')
  return {draft: next, summary}
}

export function handleWorks(req: MockRequest): MockResult | null {
  const d = db()
  if (req.path === '/works' && req.method === 'GET') return ok({items: Object.values(d.works).filter(w => w.owner === actor() && !w.deleted).sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(workJSON)})
  if (req.path === '/works' && req.method === 'POST') {
    const key = str(req.body, 'key', 128), type = req.body?.type === 'character' ? 'character' as const : req.body?.type === 'story' ? 'story' as const : fail(422, 'type_required')
    const name = str(req.body, 'name', 60).trim()
    if (!name) fail(422, 'name_required')
    const existing = Object.values(d.works).find(w => w.owner === actor() && w.key === key)
    if (existing) return ok(workJSON(existing))
    const id = randomId('work', 6)
    // A new work starts with one of the preset covers (stable per work); the editor can change it.
    const w: WorkRow = {id, owner: actor(), type: type as 'story' | 'character', name, created_at: now(), updated_at: now(), key,
      draft: {...blankDraft(type as 'story' | 'character', name), cover: WORK_COVERS[hash32(id) % WORK_COVERS.length]}, draft_revision: 1, versions: [], share: {enabled: false, version: null}, deleted: false}
    d.works[w.id] = w; save()
    return ok(workJSON(w), 201)
  }
  const one = /^\/works\/([^/]+)$/.exec(req.path)
  if (one && req.method === 'GET') return ok(workJSON(ownedWork(decodeURIComponent(one[1]))))
  const sub = /^\/works\/([^/]+)\/(draft|save|share|assist)$/.exec(req.path)
  if (sub) {
    const w = ownedWork(decodeURIComponent(sub[1]))
    if (sub[2] === 'draft' && req.method === 'PUT') {
      if (int(req.body, 'base_revision') !== w.draft_revision) fail(409, 'draft_revision_changed', {current: w.draft_revision})
      const draft = req.body?.draft
      if (!draft || typeof draft !== 'object' || Array.isArray(draft)) fail(400, 'invalid_request')
      if (JSON.stringify(draft).length > 60000) fail(413, 'draft_too_large')
      w.draft = draft as Record<string, unknown>; w.draft_revision++; w.updated_at = now()
      if (w.type === 'character' && typeof w.draft.name === 'string' && w.draft.name.trim()) w.name = w.draft.name.trim()
      if (w.type === 'story' && typeof w.draft.title === 'string' && w.draft.title.trim()) w.name = w.draft.title.trim()
      save(); return ok(workJSON(w))
    }
    if (sub[2] === 'save' && req.method === 'POST') {
      requireAccount()
      if (int(req.body, 'draft_revision') !== w.draft_revision) fail(409, 'draft_revision_changed', {current: w.draft_revision})
      const errors = validateDraft(w.type, w.draft)
      const latest = w.versions[w.versions.length - 1]
      if (latest && JSON.stringify(latest.draft) === JSON.stringify(w.draft)) return ok({...workJSON(w), saved_version: latest.version, unchanged: true})
      // Incomplete drafts may be saved; they simply cannot be previewed or shared.
      w.versions.push({version: (latest?.version ?? 0) + 1, draft: structuredClone(w.draft), saved_at: now()}); w.updated_at = now(); save()
      return ok({...workJSON(w), saved_version: w.versions[w.versions.length - 1].version, unchanged: false, errors})
    }
    if (sub[2] === 'share' && req.method === 'POST') {
      requireAccount()
      const enabled = req.body?.enabled === true
      if (enabled) {
        const version = int(req.body, 'version')
        const v = w.versions.find(x => x.version === version)
        if (!v) fail(422, 'version_not_saved')
        if (validateDraft(w.type, v!.draft).length) fail(422, 'share_check_failed')
        w.share = {enabled: true, version}
      } else w.share = {enabled: false, version: w.share.version}
      w.updated_at = now(); save(); return ok(workJSON(w))
    }
    if (sub[2] === 'assist' && req.method === 'POST') {
      const instruction = str(req.body, 'instruction', 40)
      const lang: Lang = req.body?.language === 'en' ? 'en' : 'zh'
      const draft = (req.body?.draft ?? w.draft) as Record<string, unknown>
      return ok({...assist(w.type, draft, instruction, lang), mode: 'local_template_mock'})
    }
  }
  if (req.path === '/previews' && req.method === 'POST') {
    const w = ownedWork(str(req.body, 'work_id', 80))
    const rev = int(req.body, 'draft_revision')
    if (rev !== w.draft_revision) fail(409, 'draft_revision_changed', {current: w.draft_revision})
    if (validateDraft(w.type, w.draft).length) fail(422, 'preview_check_failed')
    const p = {id: randomId('pv', 6), owner: actor(), work_id: w.id, draft_revision: rev, snapshot: structuredClone(w.draft), turns: [] as {id: string; role: 'player' | 'character'; text: string; language: Lang}[], created_at: now()}
    const lang: Lang = req.body?.language === 'en' ? 'en' : 'zh'
    const opening = String(w.type === 'character' ? w.draft.opening || '' : w.draft.opening || '')
    if (opening) p.turns.push({id: randomId('pt', 6), role: 'character', text: opening, language: lang})
    d.previews[p.id] = p; save()
    return ok(p, 201)
  }
  const pv = /^\/previews\/([^/]+)(\/turns)?$/.exec(req.path)
  if (pv) {
    const p = d.previews[decodeURIComponent(pv[1])]
    if (!p || p.owner !== actor()) fail(404, 'not_found')
    if (!pv[2] && req.method === 'GET') return ok(p)
    if (pv[2] && req.method === 'POST') {
      const text = str(req.body, 'text', 2000).trim(), key = str(req.body, 'key', 128)
      if (!text) fail(422, 'empty_input')
      if (p!.turns.some(t => t.id === key)) return ok(p)
      const lang: Lang = req.body?.language === 'en' ? 'en' : 'zh'
      p!.turns.push({id: key, role: 'player', text, language: lang})
      p!.turns.push({id: `${key}_r`, role: 'character', text: previewReply(p!.snapshot, text, lang, p!.turns.length), language: lang})
      save(); return ok(p)
    }
  }
  return null
}
