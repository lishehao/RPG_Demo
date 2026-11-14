import {useSyncExternalStore} from 'react'

export type DiscoverTab = 'all' | 'characters' | 'stories' | 'games'
export type Route =
  | {name: 'root'}
  | {name: 'discover'; tab: DiscoverTab; q: string}
  | {name: 'friends'}
  | {name: 'chat'; friendId: string}
  | {name: 'character'; id: string; version: string}
  | {name: 'story'; id: string; version: string}
  | {name: 'storyPrepare'; id: string; version: string; withFriend: string | null; from: string | null}
  | {name: 'storyPlay'; sessionId: string}
  | {name: 'gamePrepare'; gameId: string; withFriend: string | null; from: string | null}
  | {name: 'gamePlay'; sessionId: string}
  | {name: 'recent'; archived: boolean}
  | {name: 'create'}
  | {name: 'work'; workId: string}
  | {name: 'account'}
  | {name: 'notFound'; hash: string}

const TABS: DiscoverTab[] = ['all', 'characters', 'stories', 'games']

/**
 * Old deep links (`#/companions?view=…&friend=…&storySession=…&gameSession=…`) map to the
 * object they named, never to the default home (01_BUSINESS_AND_PAGE_MAP.md).
 */
export function mapLegacy(hash: string): string | null {
  if (!hash.startsWith('#/companions')) return null
  const params = new URLSearchParams(hash.split('?')[1] ?? '')
  const game = params.get('gameSession'), story = params.get('storySession'), friend = params.get('friend')
  if (game) return `#/play/game/${encodeURIComponent(game)}`
  if (story) return `#/play/story/${encodeURIComponent(story)}`
  if (friend) return `#/friends/${encodeURIComponent(friend)}`
  const storyId = params.get('story')
  if (storyId) return `#/stories/${encodeURIComponent(storyId)}?v=${encodeURIComponent(params.get('version') ?? '1')}`
  const view = params.get('view')
  if (view === 'friends') return '#/friends'
  if (view === 'recent') return '#/recent'
  if (view === 'create') return '#/create'
  return '#/discover'
}

export function parseHash(hash: string): Route {
  if (!hash || hash === '#' || hash === '#/') return {name: 'root'}
  const [rawPath, rawQuery = ''] = hash.replace(/^#/, '').split('?')
  const parts = rawPath.split('/').filter(Boolean).map(p => { try { return decodeURIComponent(p) } catch { return p } })
  const q = new URLSearchParams(rawQuery)
  const [a, b, c] = parts
  if (a === 'discover' && !b) { const tab = q.get('tab') as DiscoverTab; return {name: 'discover', tab: TABS.includes(tab) ? tab : 'all', q: q.get('q') ?? ''} }
  if (a === 'friends' && !b) return {name: 'friends'}
  if (a === 'friends' && b && !c) return {name: 'chat', friendId: b}
  if (a === 'characters' && b && !c) return {name: 'character', id: b, version: q.get('v') ?? '1'}
  if (a === 'stories' && b && !c) return {name: 'story', id: b, version: q.get('v') ?? '1'}
  if (a === 'stories' && b && c === 'prepare') return {name: 'storyPrepare', id: b, version: q.get('v') ?? '1', withFriend: q.get('with'), from: q.get('from')}
  if (a === 'play' && b === 'story' && c) return {name: 'storyPlay', sessionId: c}
  if (a === 'games' && b && c === 'prepare') return {name: 'gamePrepare', gameId: b, withFriend: q.get('with'), from: q.get('from')}
  if (a === 'play' && b === 'game' && c) return {name: 'gamePlay', sessionId: c}
  if (a === 'recent' && !b) return {name: 'recent', archived: q.get('archived') === '1'}
  if (a === 'create' && !b) return {name: 'create'}
  if (a === 'create' && b && !c) return {name: 'work', workId: b}
  if (a === 'account' && !b) return {name: 'account'}
  return {name: 'notFound', hash}
}

export const href = {
  discover: (tab: DiscoverTab = 'all', q = '') => `#/discover${tab !== 'all' || q ? `?${new URLSearchParams({...(tab !== 'all' ? {tab} : {}), ...(q ? {q} : {})})}` : ''}`,
  friends: () => '#/friends',
  chat: (friendId: string) => `#/friends/${encodeURIComponent(friendId)}`,
  character: (id: string, version = '1') => `#/characters/${encodeURIComponent(id)}?v=${encodeURIComponent(version)}`,
  story: (id: string, version = '1') => `#/stories/${encodeURIComponent(id)}?v=${encodeURIComponent(version)}`,
  storyPrepare: (id: string, version = '1', withFriend?: string | null, from?: string | null) => `#/stories/${encodeURIComponent(id)}/prepare?${new URLSearchParams({v: version, ...(withFriend ? {with: withFriend} : {}), ...(from ? {from} : {})})}`,
  storyPlay: (id: string) => `#/play/story/${encodeURIComponent(id)}`,
  gamePrepare: (gameId: string, withFriend?: string | null, from?: string | null) => `#/games/${encodeURIComponent(gameId)}/prepare${withFriend || from ? `?${new URLSearchParams({...(withFriend ? {with: withFriend} : {}), ...(from ? {from} : {})})}` : ''}`,
  gamePlay: (id: string) => `#/play/game/${encodeURIComponent(id)}`,
  recent: (archived = false) => `#/recent${archived ? '?archived=1' : ''}`,
  create: () => '#/create',
  work: (id: string) => `#/create/${encodeURIComponent(id)}`,
  account: () => '#/account',
}

const listeners = new Set<() => void>()
let currentHash = typeof window !== 'undefined' ? window.location.hash : ''
function sync() {
  const legacy = mapLegacy(window.location.hash)
  if (legacy) { history.replaceState(history.state, '', legacy); }
  if (window.location.hash !== currentHash) { currentHash = window.location.hash; listeners.forEach(fn => fn()) }
}
if (typeof window !== 'undefined') {
  const legacy = mapLegacy(window.location.hash)
  if (legacy) { history.replaceState(history.state, '', legacy); currentHash = legacy }
  window.addEventListener('hashchange', sync)
  window.addEventListener('popstate', sync)
}
export function navigate(hash: string, options: {replace?: boolean} = {}) {
  if (hash === window.location.hash) return
  if (options.replace) history.replaceState(history.state, '', hash)
  else history.pushState(null, '', hash)
  sync()
}
export function useRoute(): Route {
  const hash = useSyncExternalStore(fn => { listeners.add(fn); return () => { listeners.delete(fn) } }, () => currentHash, () => '')
  return parseHash(hash)
}
export const currentRouteHash = () => currentHash
