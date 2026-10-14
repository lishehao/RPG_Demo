/**
 * One typed client over a fetch-compatible transport. The mock adapter passes an
 * in-process fetch; a real adapter would pass `window.fetch` with a base URL. All
 * responses go through the ported contract parsers either way.
 */
import {CompanionRequestError, parseAccount, parseCharacter, parseCharacters, parseFriend, parseFriends} from '../contracts/companion'
import {parsePrivateOperation, parsePrivateSnapshot} from '../contracts/private-chat-client'
import type {PrivateSnapshot} from '../contracts/private-chat-client'
import {parsePublicAdmission} from '../contracts/public-events'
import type {PublicAdmission} from '../contracts/public-events'
import type {Lang} from '../lib/util'
import type {DiscoverPage, GameJSON, GameViewJSON, PreviewJSON, RecordJSON, StoryJSON, StorySessionJSON, TableMessageJSON, WorkJSON} from './types'

export type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

function assertGameView(value: unknown): GameViewJSON {
  const v = value as GameViewJSON
  if (!v || v.schema_version !== 'everwith-game-view-v1' || !Array.isArray(v.seats) || typeof v.revision !== 'number') throw new CompanionRequestError('game_response_invalid')
  const pv = v.player_view as Record<string, unknown>
  // Defence in depth: a player projection must never carry authority-only fields.
  for (const key of ['truth', 'rng', 'up', 'seed', 'lastAction']) if (pv && key in pv) throw new CompanionRequestError('game_private_view_invalid')
  if (v.game_id === 'cabo' && (pv.observer !== 0 || (pv.deck as unknown[]).some(x => x !== null))) throw new CompanionRequestError('game_private_view_invalid')
  if (v.game_id === 'gems' && Object.values(pv.decks as Record<string, unknown>).some(x => typeof x !== 'number')) throw new CompanionRequestError('game_private_view_invalid')
  if (v.game_id === 'vegas' && 'deck' in pv) throw new CompanionRequestError('game_private_view_invalid')
  if (v.seats[0]?.kind !== 'player' || v.seats.slice(1).some(s => s.kind === 'player') || new Set(v.seats.map(s => s.identity)).size !== v.seats.length) throw new CompanionRequestError('game_identity_invalid')
  return v
}
function assertStory(value: unknown): StorySessionJSON {
  const v = value as StorySessionJSON
  if (!v || v.schema_version !== 'everwith-story-session-v1' || !Array.isArray(v.turns) || !Array.isArray(v.cast)) throw new CompanionRequestError('invalid_response')
  if (v.cast.filter(c => c.friend_id).length !== new Set(v.cast.filter(c => c.friend_id).map(c => c.friend_id)).size) throw new CompanionRequestError('invalid_response')
  return v
}

export function createClient(fetcher: Fetcher, base = '') {
  async function request<T = unknown>(path: string, body?: unknown, method?: string, signal?: AbortSignal): Promise<T> {
    let response: Response
    try {
      response = await fetcher(`${base}/api/companions${path}`, {
        method: method ?? (body === undefined ? 'GET' : 'POST'), credentials: 'include', cache: 'no-store', signal,
        headers: body === undefined ? {} : {'Content-Type': 'application/json', 'X-Tiny-Stories-Request': '1'},
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new CompanionRequestError('network_error')
    }
    const data: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const raw = data && typeof data === 'object' && 'error' in data ? (data as {error: {code?: unknown; detail?: unknown}}).error : null
      const code = raw && typeof raw.code === 'string' && /^[a-z_]{1,64}$/.test(raw.code) ? raw.code : 'unavailable'
      throw new CompanionRequestError(code, response.status, raw && raw.detail && typeof raw.detail === 'object' ? raw.detail as Record<string, unknown> : null)
    }
    return data as T
  }
  const q = (params: Record<string, string | number | undefined>) => {
    const s = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') s.set(k, String(v))
    const t = s.toString(); return t ? `?${t}` : ''
  }
  type Command = {key: string; text: string; language: Lang; presented_turn_id: string; expected_revision: number}
  const parseStart = (raw: unknown) => {
    const row = raw as {operation: unknown; admission: unknown}
    return {operation: parsePrivateOperation(row.operation), admission: parsePublicAdmission(row.admission)}
  }
  return {
    request,
    account: {
      get: async () => parseAccount(await request('/account')),
      login: async (email: string, password: string) => parseAccount(await request('/account/login', {email, password})),
      register: async (email: string, password: string) => parseAccount(await request('/account/register', {email, password})),
      logout: async () => parseAccount(await request('/account/logout', {})),
      /** avatar: undefined keeps the current picture, null removes it. */
      persona: async (name: string, bio: string, avatar?: string | null) => parseAccount(await request('/account/persona', avatar === undefined ? {name, bio} : {name, bio, avatar}, 'PUT')),
    },
    catalog: {
      discover: (params: {type: string; q: string; offset: number; limit?: number}, signal?: AbortSignal) => request<DiscoverPage>(`/discover${q({type: params.type, q: params.q, offset: params.offset, limit: params.limit ?? 8})}`, undefined, undefined, signal),
      characters: async () => parseCharacters(await request('/characters')),
      character: async (id: string, version: string) => parseCharacter(await request(`/characters/${encodeURIComponent(id)}${q({version})}`)),
      story: (id: string, version?: string) => request<StoryJSON>(`/stories/${encodeURIComponent(id)}${q({version})}`),
      stories: () => request<{items: StoryJSON[]}>('/stories'),
      games: () => request<{items: GameJSON[]}>('/games'),
    },
    friends: {
      list: async (accountId: string, query = '') => parseFriends(await request(`/friends${q({limit: 50, offset: 0, q: query, expected_account_id: accountId})}`), accountId),
      get: async (id: string) => parseFriend(await request(`/friends/${encodeURIComponent(id)}`)),
      add: async (input: {key: string; source_id: string; source_version: string; name: string; expected_account_id: string; origin?: Record<string, unknown>}) => parseFriend(await request('/friends', input)),
      rename: async (id: string, epoch: number, name: string, accountId: string) => request<{friend: unknown}>(`/friends/${encodeURIComponent(id)}/rename`, {expected_epoch: epoch, name, expected_account_id: accountId}).then(r => parseFriend(r.friend)),
      reset: async (id: string, epoch: number, accountId: string) => request<{friend: unknown}>(`/friends/${encodeURIComponent(id)}/reset`, {expected_epoch: epoch, expected_account_id: accountId}).then(r => parseFriend(r.friend)),
      remove: (id: string, epoch: number, accountId: string) => request(`/friends/${encodeURIComponent(id)}/remove`, {expected_epoch: epoch, expected_account_id: accountId}),
      conversations: (id: string) => request<{items: {id: string; friend_epoch: number; status: string; turns: number; updated_at: string}[]}>(`/friends/${encodeURIComponent(id)}/conversations`),
    },
    chat: {
      open: async (friendId: string, epoch: number, accountId: string, key: string, language: Lang) => parsePrivateSnapshot(await request(`/friends/${encodeURIComponent(friendId)}/conversation`, {key, expected_account_id: accountId, expected_friend_epoch: epoch, language}), friendId, epoch),
      read: async (conversationId: string, friendId: string, epoch: number): Promise<PrivateSnapshot> => {
        const snapshot = parsePrivateSnapshot(await request(`/conversations/${encodeURIComponent(conversationId)}`), friendId, epoch)
        if (snapshot.conversation.id !== conversationId) throw new CompanionRequestError('invalid_response')
        return snapshot
      },
      send: async (conversationId: string, command: Command, accountId: string, epoch: number, signal?: AbortSignal) =>
        parseStart(await request(`/conversations/${encodeURIComponent(conversationId)}/operations`, {...command, expected_account_id: accountId, expected_friend_epoch: epoch}, 'POST', signal)),
      stream: async (admission: PublicAdmission, signal: AbortSignal) => {
        try { return await fetcher(`${base}/api/companions/operations/${encodeURIComponent(admission.operation_id)}/public-stream?run_epoch=${admission.run_epoch}`, {credentials: 'include', cache: 'no-store', signal}) }
        catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw error; throw new CompanionRequestError('network_error') }
      },
      receipt: async (operationId: string) => {
        const row = await request<{owner_id: string; operation: unknown; snapshot: unknown; admission: unknown}>(`/operations/${encodeURIComponent(operationId)}/receipt`)
        return {owner_id: row.owner_id, operation: row.operation, snapshot: row.snapshot, admission: row.admission ? parsePublicAdmission(row.admission) : null}
      },
      lookup: async (conversationId: string, key: string) => {
        const row = await request<{operation: unknown; admission: unknown; text: string}>(`/conversations/${encodeURIComponent(conversationId)}/operations/lookup${q({key})}`)
        return {operation: parsePrivateOperation(row.operation), admission: row.admission ? parsePublicAdmission(row.admission) : null, text: row.text}
      },
      retry: async (operationId: string, accountId: string, epoch: number) => parseStart(await request(`/operations/${encodeURIComponent(operationId)}/retry`, {expected_account_id: accountId, expected_friend_epoch: epoch})),
      cancel: async (operationId: string, accountId: string, epoch: number) => parsePrivateOperation(await request(`/operations/${encodeURIComponent(operationId)}/cancel`, {expected_account_id: accountId, expected_friend_epoch: epoch})),
      rollback: async (conversationId: string, turnId: string, revision: number, friendId: string, epoch: number, language: Lang) => {
        const row = await request<{snapshot: unknown; restored_draft: string}>(`/conversations/${encodeURIComponent(conversationId)}/rollback`, {turn_id: turnId, expected_revision: revision, language})
        return {snapshot: parsePrivateSnapshot(row.snapshot, friendId, epoch), restored: row.restored_draft}
      },
      correction: async (conversationId: string, key: string, text: string, turnId: string | null, friendId: string, epoch: number, language: Lang) => {
        const row = await request<{snapshot: unknown}>(`/conversations/${encodeURIComponent(conversationId)}/corrections`, {key, text, turn_id: turnId, language})
        return parsePrivateSnapshot(row.snapshot, friendId, epoch)
      },
    },
    stories: {
      start: async (body: {key: string; story_id: string; version: string; cast: {role_id: string; friend_id: string; friend_epoch: number}[]; language: Lang; expected_account_id: string}) => assertStory(await request('/story-sessions', body)),
      get: async (id: string) => assertStory(await request(`/story-sessions/${encodeURIComponent(id)}`)),
      turn: async (id: string, body: {key: string; kind: 'input' | 'continue'; text?: string; language: Lang; expected_revision: number}) => {
        const row = await request<{operation: {operation_id: string; status: string}; session: unknown}>(`/story-sessions/${encodeURIComponent(id)}/turns`, body)
        return {operation: row.operation, session: assertStory(row.session)}
      },
      control: async (id: string, op: string, action: 'cancel' | 'retry') => {
        const row = await request<{operation: {operation_id: string; status: string}; session: unknown; restored_input?: string | null}>(`/story-sessions/${encodeURIComponent(id)}/operations/${encodeURIComponent(op)}/${action}`, {})
        return {operation: row.operation, session: assertStory(row.session), restored: row.restored_input ?? null}
      },
      rollback: async (id: string, turnId: string, revision: number) => {
        const row = await request<{session: unknown; restored_draft: string}>(`/story-sessions/${encodeURIComponent(id)}/rollback`, {turn_id: turnId, expected_revision: revision})
        return {session: assertStory(row.session), restored: row.restored_draft}
      },
    },
    games: {
      start: async (body: Record<string, unknown>) => assertGameView(await request('/game-sessions', body)),
      lookup: async (key: string) => assertGameView(await request(`/game-sessions/lookup${q({key})}`)),
      get: async (id: string) => assertGameView(await request(`/game-sessions/${encodeURIComponent(id)}`)),
      list: async () => (await request<{items: unknown[]}>('/game-sessions')).items.map(assertGameView),
      act: async (id: string, key: string, action: unknown, revision: number) => assertGameView(await request(`/game-sessions/${encodeURIComponent(id)}/act`, {key, action, expected_revision: revision})),
      advance: async (id: string, key: string, revision: number, language: Lang) => assertGameView(await request(`/game-sessions/${encodeURIComponent(id)}/advance`, {key, expected_revision: revision, language})),
      hold: async (id: string, hold: boolean) => assertGameView(await request(`/game-sessions/${encodeURIComponent(id)}/hold`, {hold})),
      abandon: async (id: string, revision: number) => assertGameView(await request(`/game-sessions/${encodeURIComponent(id)}/abandon`, {expected_revision: revision})),
      rematch: async (id: string, key: string) => assertGameView(await request(`/game-sessions/${encodeURIComponent(id)}/rematch`, {key})),
      messages: (id: string) => request<{items: TableMessageJSON[]}>(`/game-sessions/${encodeURIComponent(id)}/table-chat`),
      say: (id: string, key: string, text: string, language: Lang) => request<{items: TableMessageJSON[]; reply_failed: boolean}>(`/game-sessions/${encodeURIComponent(id)}/table-chat`, {key, text, language}),
    },
    records: {
      list: (archived: boolean) => request<{items: RecordJSON[]}>(`/records${q({archived: archived ? 1 : 0})}`),
      mutate: (kind: 'story' | 'game', id: string, action: 'archive' | 'restore' | 'delete') => request(`/records/${kind}/${encodeURIComponent(id)}/${action}`, {}),
    },
    works: {
      list: () => request<{items: WorkJSON[]}>('/works'),
      create: (key: string, type: 'story' | 'character', name: string) => request<WorkJSON>('/works', {key, type, name}),
      get: (id: string) => request<WorkJSON>(`/works/${encodeURIComponent(id)}`),
      putDraft: (id: string, draft: Record<string, unknown>, base: number) => request<WorkJSON>(`/works/${encodeURIComponent(id)}/draft`, {draft, base_revision: base}, 'PUT'),
      save: (id: string, draftRevision: number) => request<WorkJSON>(`/works/${encodeURIComponent(id)}/save`, {draft_revision: draftRevision}),
      share: (id: string, enabled: boolean, version: number | null) => request<WorkJSON>(`/works/${encodeURIComponent(id)}/share`, {enabled, version}),
      assist: (id: string, instruction: string, draft: Record<string, unknown>, language: Lang) => request<{draft: Record<string, unknown>; summary: string[]; mode: string}>(`/works/${encodeURIComponent(id)}/assist`, {instruction, draft, language}),
      preview: (workId: string, draftRevision: number, language: Lang) => request<PreviewJSON>('/previews', {work_id: workId, draft_revision: draftRevision, language}),
      previewTurn: (id: string, key: string, text: string, language: Lang) => request<PreviewJSON>(`/previews/${encodeURIComponent(id)}/turns`, {key, text, language}),
    },
  }
}
export type EverwithClient = ReturnType<typeof createClient>
