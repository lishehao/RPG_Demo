/**
 * Mock authority + typed client + chat controller, end to end in-process (no network).
 * These prove the client-side guarantees against the mock; they are NOT real-service E2E.
 */
import {beforeAll, describe, expect, it} from 'vitest'
import {api} from '../src/api/adapter'
import {db, resetDB} from '../src/mock/db'
import {WORK_COVERS} from '../src/art/generated'
import type {StorySessionJSON} from '../src/api/types'
import {scenarios} from '../src/mock/scenarios'
import {createChatController} from '../src/chat/stream-controller'
import type {ChatController, ChatTransport} from '../src/chat/stream-controller'
import type {CompanionFriend} from '../src/contracts/companion'
import type {PrivateSnapshot} from '../src/contracts/private-chat-client'

let accountId = ''
const until = async (pred: () => boolean, ms = 15000) => {
  const t0 = Date.now()
  while (!pred()) { if (Date.now() - t0 > ms) throw new Error('timeout'); await new Promise(r => setTimeout(r, 40)) }
}
function controllerFor(friend: CompanionFriend, snapshot: PrivateSnapshot): ChatController {
  const conversationId = snapshot.conversation.id
  const transport: ChatTransport = {
    send: (cmd, signal) => api.chat.send(conversationId, cmd, accountId, friend.epoch, signal),
    stream: (adm, signal) => api.chat.stream(adm, signal),
    cancel: id => api.chat.cancel(id, accountId, friend.epoch),
    receipt: id => api.chat.receipt(id),
    retry: id => api.chat.retry(id, accountId, friend.epoch),
    lookup: key => api.chat.lookup(conversationId, key),
    read: () => api.chat.read(conversationId, friend.id, friend.epoch),
  }
  return createChatController(snapshot, {account_id: accountId, friend_id: friend.id, friend_epoch: friend.epoch, session_id: conversationId, allow_fictional_thought: false}, transport)
}
const playerTurns = (s: PrivateSnapshot, text: string) => s.history.turns.filter(t => t.player_expression === text).length

beforeAll(async () => {
  resetDB(); scenarios.clear()
  const account = await api.account.register('unit@example.com', 'password123')
  accountId = account.account!.id
})

describe('friends', () => {
  it('add is idempotent per key; a different intent under the same key is rejected; same source makes separate people', async () => {
    const input = {key: 'fk-1', source_id: 'official-lena', source_version: '1', name: 'Lena A', expected_account_id: accountId}
    const a = await api.friends.add(input)
    const again = await api.friends.add(input)
    expect(again.id).toBe(a.id)
    await expect(api.friends.add({...input, name: 'Someone else'})).rejects.toMatchObject({code: 'idempotency_conflict'})
    const b = await api.friends.add({...input, key: 'fk-2', name: 'Lena B'})
    expect(b.id).not.toBe(a.id)
    expect(b.display_number).toBe(2)
    const list = await api.friends.list(accountId)
    expect(list.items.filter(f => f.source_id === 'official-lena').map(f => f.name).sort()).toEqual(['Lena A', 'Lena B'])
  })
  it('reset starts a new epoch and makes the old conversation read-only', async () => {
    const f = await api.friends.add({key: 'fk-reset', source_id: 'official-marcus', source_version: '1', name: 'Marcus R', expected_account_id: accountId})
    const before = await api.chat.open(f.id, f.epoch, accountId, 'open-r1', 'zh')
    const reset = await api.friends.reset(f.id, f.epoch, accountId)
    expect(reset.epoch).toBe(f.epoch + 1)
    const old = await api.chat.read(before.conversation.id, f.id, f.epoch)
    expect(old.conversation.status).toBe('read_only')
    await expect(api.friends.rename(f.id, f.epoch, 'stale', accountId)).rejects.toMatchObject({code: 'friend_epoch_changed'})
  })
})

describe('private chat controller against the mock authority', () => {
  let friend: CompanionFriend
  let c: ChatController
  beforeAll(async () => {
    friend = await api.friends.add({key: 'fk-chat', source_id: 'official-nora', source_version: '1', name: 'Nora C', expected_account_id: accountId})
    c = controllerFor(friend, await api.chat.open(friend.id, friend.epoch, accountId, 'open-c1', 'zh'))
  })
  it('send → public frames → verified receipt commits exactly once; a second send while active is refused', async () => {
    const first = c.start('你好', 'zh', 'key-hello')
    const second = await c.start('又一条', 'zh')
    expect(second).toBe(false)
    await first
    await until(() => ['committed', 'idle'].includes(c.getSnapshot().phase))
    const v = c.getSnapshot()
    expect(playerTurns(v.history, '你好')).toBe(1)
    expect(v.provisional).toEqual([])
  })
  it('retryable failure keeps the input and an explicit Retry reuses the same operation', async () => {
    scenarios.set('chat.retryable_failure', true)
    await c.start('第二句', 'zh')
    await until(() => c.getSnapshot().history.pending_operation?.status === 'retryable_failed' || c.getSnapshot().notice?.kind === 'retryable', 20000)
    const opId = c.getSnapshot().history.pending_operation?.operation_id
    expect(playerTurns(c.getSnapshot().history, '第二句')).toBe(0)
    await c.retry()
    await until(() => ['committed', 'idle'].includes(c.getSnapshot().phase), 20000)
    expect(playerTurns(c.getSnapshot().history, '第二句')).toBe(1)
    expect(opId).toBeTruthy()
  })
  it('unknown result: looks up the ORIGINAL key and never creates a second turn', async () => {
    scenarios.set('chat.unknown_result', true)
    await c.start('结果未知', 'zh', 'key-unknown')
    expect(c.getSnapshot().phase).toBe('unknown')
    await c.lookup()
    await until(() => ['committed', 'idle'].includes(c.getSnapshot().phase) || c.getSnapshot().notice?.kind === 'lookup_missing', 20000)
    if (c.getSnapshot().notice?.kind === 'lookup_missing') await c.resendSameKey()
    await until(() => ['committed', 'idle'].includes(c.getSnapshot().phase), 20000)
    expect(playerTurns(c.getSnapshot().history, '结果未知')).toBe(1)
  })
  it('Stop that loses to a commit reports “already completed” and keeps the result', async () => {
    scenarios.set('chat.commit_before_cancel', true)
    const run = c.start('停止竞争', 'zh')
    await until(() => ['generating', 'awaiting_commit', 'starting'].includes(c.getSnapshot().phase))
    await c.cancel()
    await run
    await until(() => !['sending', 'starting', 'generating', 'awaiting_commit', 'cancelling'].includes(c.getSnapshot().phase), 20000)
    expect(c.getSnapshot().notice?.kind).toBe('commit_won')
    expect(playerTurns(c.getSnapshot().history, '停止竞争')).toBe(1)
  })
  it('late frames from the old run are ignored after an explicit retry (run_epoch check)', async () => {
    scenarios.set('chat.late_old_stream', true)
    await c.start('晚到的旧流', 'zh')
    await until(() => c.getSnapshot().history.pending_operation?.status === 'retryable_failed' || c.getSnapshot().notice?.kind === 'retryable', 20000)
    await c.retry()
    await until(() => ['committed', 'idle'].includes(c.getSnapshot().phase), 20000)
    expect(c.getSnapshot().ignoredFrames).toBeGreaterThan(0)
    expect(playerTurns(c.getSnapshot().history, '晚到的旧流')).toBe(1)
  })
  it('a real cancel leaves history unchanged and hands the text back', async () => {
    const before = c.getSnapshot().history.history.turns.length
    const run = c.start('取消我', 'zh')
    await until(() => ['starting', 'generating'].includes(c.getSnapshot().phase))
    await c.cancel()
    await run
    await until(() => !['sending', 'starting', 'generating', 'awaiting_commit', 'cancelling'].includes(c.getSnapshot().phase), 20000)
    const v = c.getSnapshot()
    expect(v.history.history.turns.length).toBe(before)
    expect(v.restore?.text ?? v.input).toBe('取消我')
  })
})

describe('games', () => {
  it('start is idempotent per key, lookup finds the original, and stale revisions are refused', async () => {
    const body = {key: 'g-key-1', game_id: 'cabo', players: 3, profile: 'cabo-shareful-2025-en-slice-provisional', expected_account_id: accountId,
      seats: [{seat: 1, kind: 'temporary', character_id: 'official-lena'}, {seat: 2, kind: 'temporary', character_id: 'official-iris'}], origin: {kind: 'discover', return_hash: '#/discover?tab=games'}}
    const a = await api.games.start(body)
    const b = await api.games.start(body)
    expect(b.id).toBe(a.id)
    expect((await api.games.lookup('g-key-1')).id).toBe(a.id)
    await expect(api.games.start({...body, players: 2, seats: body.seats.slice(0, 1)})).rejects.toMatchObject({code: 'idempotency_conflict'})
    await expect(api.games.act(a.id, 'act-stale', {type: 'ack'}, a.revision + 5)).rejects.toMatchObject({code: 'game_revision_changed'})
    // The projection never carries authority-only fields.
    const pv = a.player_view as Record<string, unknown>
    for (const k of ['truth', 'rng', 'up', 'seed']) expect(k in pv).toBe(false)
  })
  it('a friend can only take one seat', async () => {
    const f = await api.friends.add({key: 'fk-seat', source_id: 'official-arthur', source_version: '1', name: 'Arthur S', expected_account_id: accountId})
    await expect(api.games.start({key: 'g-key-2', game_id: 'vegas', players: 3, expected_account_id: accountId,
      seats: [{seat: 1, kind: 'friend', friend_id: f.id, friend_epoch: f.epoch}, {seat: 2, kind: 'friend', friend_id: f.id, friend_epoch: f.epoch}]})).rejects.toMatchObject({code: 'friend_already_seated'})
  })
})

describe('stories', () => {
  it('rejects casting one friend twice or replacing a locked role; accepts the original cast', async () => {
    const f = await api.friends.add({key: 'fk-story', source_id: 'official-lena', source_version: '1', name: 'Lena S', expected_account_id: accountId})
    const base = {story_id: 'story-promise-rain', version: '1', language: 'zh' as const, expected_account_id: accountId}
    await expect(api.stories.start({...base, key: 's-1', cast: [{role_id: 'investigator', friend_id: f.id, friend_epoch: f.epoch}, {role_id: 'stage', friend_id: f.id, friend_epoch: f.epoch}]})).rejects.toMatchObject({code: 'friend_already_cast'})
    await expect(api.stories.start({...base, key: 's-2', cast: [{role_id: 'manager', friend_id: f.id, friend_epoch: f.epoch}]})).rejects.toMatchObject({code: 'role_locked'})
    const s = await api.stories.start({...base, key: 's-3', cast: [{role_id: 'investigator', friend_id: f.id, friend_epoch: f.epoch}]})
    expect(s.cast.find(c => c.role_id === 'investigator')?.friend_id).toBe(f.id)
    expect(s.turns).toHaveLength(1)
  })
  it('a cast friend brings no private chat history; resetting that friend makes the run read-only', async () => {
    const f = await api.friends.add({key: 'fk-story-2', source_id: 'official-iris', source_version: '1', name: 'Iris S', expected_account_id: accountId})
    const chat = controllerFor(f, await api.chat.open(f.id, f.epoch, accountId, 'open-s2', 'zh'))
    await chat.start('只属于私聊的秘密：蓝色雨伞', 'zh')
    await until(() => ['committed', 'idle'].includes(chat.getSnapshot().phase), 20000)
    const s = await api.stories.start({story_id: 'story-promise-rain', version: '1', language: 'zh', expected_account_id: accountId, key: 's-4', cast: [{role_id: 'investigator', friend_id: f.id, friend_epoch: f.epoch}]})
    expect(JSON.stringify(s)).not.toContain('蓝色雨伞')
    await api.friends.reset(f.id, f.epoch, accountId)
    expect((await api.stories.get(s.id)).status).toBe('read_only')
    await expect(api.stories.turn(s.id, {key: 'st-ro', kind: 'continue', language: 'zh', expected_revision: s.revision})).rejects.toMatchObject({code: 'session_read_only'})
  })
})

describe('creation', () => {
  it('draft sync needs the base revision; versions are explicit; sharing needs a valid saved version', async () => {
    const w = await api.works.create('w-1', 'character', '测试角色')
    const next = await api.works.putDraft(w.id, {...w.draft, intro: '介绍'}, w.draft_revision)
    expect(next.draft_revision).toBe(w.draft_revision + 1)
    await expect(api.works.putDraft(w.id, {...w.draft, intro: '旧'}, w.draft_revision)).rejects.toMatchObject({code: 'draft_revision_changed'})
    const saved = await api.works.save(w.id, next.draft_revision)
    expect(saved.saved_version).toBe(1)
    await expect(api.works.share(w.id, true, 1)).rejects.toMatchObject({code: 'share_check_failed'}) // persona still empty
    expect((await api.works.get(w.id)).share.enabled).toBe(false)
  })
})

describe('generated art wiring in the mock data', () => {
  /** Commits the pending story turn now instead of waiting for the simulated 1.5 s. */
  const commit = async (s: StorySessionJSON, key: string) => {
    await api.stories.turn(s.id, {key, kind: 'continue', language: 'zh', expected_revision: s.revision})
    db().stories[s.id].pending!.commit_at = 0
    return api.stories.get(s.id)
  }
  it('stories carry a tall and a wide cover; each beat moves the scene; open mode moves to the ending place', async () => {
    const story = await api.catalog.story('story-last-train', '1')
    expect(story.image).toBe('/generated/batch-01/story-last-train-cover-tall.webp')
    expect(story.image_wide).toBe('/generated/batch-01/story-last-train-cover-wide.webp')
    let s = await api.stories.start({story_id: 'story-last-train', version: '1', language: 'zh', expected_account_id: accountId, key: 's-art', cast: []})
    expect(s.state).toMatchObject({scene: 'waiting-room', scene_image: '/generated/batch-01/story-last-train-scene-waiting-room.webp', scene_position: '52%', scene_label: {zh: '候车室 · 深夜'}})
    const seen = [s.state.scene]
    for (let i = 0; i < 4; i++) { s = await commit(s, `st-art-${i}`); seen.push(s.state.scene) }
    expect(seen).toEqual(['waiting-room', 'waiting-room', 'corner', 'duty-room', 'platform-dawn'])
    expect(s.state.open_mode).toBe(true)
    expect(s.state.scene_image).toBe('/generated/batch-01/story-last-train-scene-platform-dawn.webp')
  })
  it('a run stored with the earlier scene keys still resolves its place from its turns', async () => {
    let s = await api.stories.start({story_id: 'story-promise-rain', version: '1', language: 'zh', expected_account_id: accountId, key: 's-art-old', cast: []})
    s = await commit(s, 'st-old-1'); s = await commit(s, 'st-old-2')
    expect(s.state.scene).toBe('backstage')
    db().stories[s.id].state.scene = 'study'
    const reread = await api.stories.get(s.id)
    expect(reread.state.scene).toBe('backstage')
    expect(reread.state.scene_image).toBe('/generated/batch-01/story-promise-rain-scene-backstage.webp')
  })
  it('records carry the work picture (story cover / game poster)', async () => {
    await api.games.start({key: 'g-art', game_id: 'cabo', players: 2, profile: 'cabo-shareful-2025-en-slice-provisional', expected_account_id: accountId,
      seats: [{seat: 1, kind: 'temporary', character_id: 'official-nora'}], origin: {kind: 'discover', return_hash: '#/discover?tab=games'}})
    const items = (await api.records.list(false)).items
    expect(items.find(r => r.kind === 'story' && r.work_id === 'story-last-train')?.image).toBe('/generated/batch-01/story-last-train-cover-tall.webp')
    expect(items.find(r => r.kind === 'game' && r.work_id === 'cabo')?.image).toBe('/generated/batch-01/game-cabo-cover.webp')
  })
  it('persona avatar: preset ids only; omitted keeps it; null clears it', async () => {
    expect((await api.account.persona('我', '', 'persona-avatar-03')).persona?.avatar).toBe('persona-avatar-03')
    expect((await api.account.persona('我2', '简介')).persona).toMatchObject({name: '我2', avatar: 'persona-avatar-03'})
    await expect(api.account.persona('我', '', '/generated/batch-01/backdrop-lena.webp')).rejects.toMatchObject({code: 'invalid_avatar'})
    expect((await api.account.persona('我', '', null)).persona?.avatar).toBeNull()
  })
  it('a new work starts with a preset cover; anything else is reported as invalid', async () => {
    const w = await api.works.create('w-art', 'story', '封面测试')
    expect(WORK_COVERS as readonly unknown[]).toContain(w.draft.cover)
    expect(w.errors.some(e => e.field === 'cover')).toBe(false)
    const bad = await api.works.putDraft(w.id, {...w.draft, cover: 'https://example.com/cover.png'}, w.draft_revision)
    expect(bad.errors).toContainEqual({field: 'cover', code: 'invalid'})
  })
})
