/**
 * Adapter seam. Default: in-process LOCAL MOCK (no network). `VITE_EVERWITH_ADAPTER=real`
 * selects network transport, and even then nothing is requested unless
 * `VITE_EVERWITH_ALLOW_NETWORK=1` is also set — there is no silent real→mock fallback.
 */
import {createClient} from './client'
import type {Fetcher} from './client'
import {mockFetch} from '../mock/server'
import {CompanionRequestError} from '../contracts/companion'

export const ADAPTER_MODE: 'mock' | 'real' = import.meta.env.VITE_EVERWITH_ADAPTER === 'real' ? 'real' : 'mock'

/** Concrete gaps before a real adapter can be enabled (also listed in README). */
export const REAL_ADAPTER_GAPS: {area: string; gap: string}[] = [
  {area: 'account', gap: 'Real /account shape has no `guest_id`/`mode`; guest-merge endpoint and CSRF bootstrap (/request-protection) must be confirmed against the Pydantic contract.'},
  {area: 'catalog', gap: '/discover (paged, typed search), /stories, /games and /characters/{id}?version are candidates; only /characters is in ENDPOINTS.json.'},
  {area: 'friends', gap: 'rename/reset/remove commands and `origin` (story F2 / game F7 binding) are candidates; server must bind source version + epoch atomically.'},
  {area: 'private chat', gap: 'POST …/operations must return {operation, admission}; GET …/operations/{id}/receipt and …/public-stream?run_epoch are candidates from the stream design, not verified endpoints.'},
  {area: 'stories', gap: 'All /story-sessions endpoints are new candidates; real narrator (Luna) and atomic turn validation are not connected.'},
  {area: 'games', gap: '/game-sessions act/advance/hold/abandon/rematch shapes are candidates; JEV decision seam is not connected (fixed-strategy NPC only).'},
  {area: 'creation', gap: '/works, /previews and assist endpoints are candidates; no AI model is called.'},
  {area: 'voice', gap: 'No TTS/viseme service; lip-sync only follows the local demo audio track.'},
]

const blockedFetch: Fetcher = async () => { throw new CompanionRequestError('real_adapter_not_enabled') }
const networkAllowed = import.meta.env.VITE_EVERWITH_ALLOW_NETWORK === '1'
export const api = ADAPTER_MODE === 'real'
  ? createClient(networkAllowed ? window.fetch.bind(window) : blockedFetch, import.meta.env.VITE_EVERWITH_API_BASE ?? '')
  : createClient(mockFetch)
