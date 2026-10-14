/** App-level session state: account, language, friends cache, sign-in gate, toasts. */
import {useSyncExternalStore} from 'react'
import {api} from '../api/adapter'
import {CompanionRequestError} from '../contracts/companion'
import type {AccountSession, CompanionFriend} from '../contracts/companion'
import type {I18nKey} from './i18n'
import {readJSON, writeJSON} from '../lib/util'
import type {Lang} from '../lib/util'

export type Toast = {id: number; text: string; kind: 'info' | 'error' | 'success'}
export type AppState = {
  lang: Lang
  account: AccountSession | null
  accountError: string | null
  friends: CompanionFriend[] | null
  friendsError: string | null
  authPrompt: {action: I18nKey; id: number} | null
  toasts: Toast[]
  navCollapsed: boolean
  reducedMotion: boolean
}
const LANG_KEY = 'everwith.ui.lang', NAV_KEY = 'everwith.ui.navCollapsed', MOTION_KEY = 'everwith.ui.reducedMotion'
const systemMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
let state: AppState = {
  lang: readJSON<Lang>(LANG_KEY, (typeof navigator !== 'undefined' && navigator.language.startsWith('en') ? 'en' : 'zh')),
  account: null, accountError: null, friends: null, friendsError: null, authPrompt: null, toasts: [],
  navCollapsed: readJSON<boolean>(NAV_KEY, false), reducedMotion: readJSON<boolean | null>(MOTION_KEY, null) ?? systemMotion,
}
const listeners = new Set<() => void>()
const set = (patch: Partial<AppState>) => { state = {...state, ...patch}; listeners.forEach(fn => fn()) }
export const appStore = {
  subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
  get: () => state,
}
export function useApp<T>(select: (s: AppState) => T): T {
  return useSyncExternalStore(appStore.subscribe, () => select(state), () => select(state))
}

let toastSeq = 0
export function toast(text: string, kind: Toast['kind'] = 'info') {
  const id = ++toastSeq
  set({toasts: [...state.toasts, {id, text, kind}].slice(-4)})
  setTimeout(() => set({toasts: state.toasts.filter(t => t.id !== id)}), 5200)
}
export function setLang(lang: Lang) { writeJSON(LANG_KEY, lang); document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'; set({lang}) }
export function setNavCollapsed(v: boolean) { writeJSON(NAV_KEY, v); set({navCollapsed: v}) }
export function setReducedMotion(v: boolean) { writeJSON(MOTION_KEY, v); set({reducedMotion: v}) }

export async function loadAccount() {
  try { const account = await api.account.get(); set({account, accountError: null}); if (account.authenticated) void refreshFriends() ; else set({friends: []}) }
  catch (e) { set({accountError: e instanceof CompanionRequestError ? e.code : 'network_error'}) }
}
export function setAccount(account: AccountSession) {
  const changed = state.account?.account?.id !== account.account?.id
  set({account, ...(changed ? {friends: null} : {})})
  if (account.authenticated) void refreshFriends(); else set({friends: []})
}
let friendsFlight = 0
export async function refreshFriends() {
  const acc = state.account
  if (!acc?.authenticated || !acc.account) { set({friends: []}); return }
  const flight = ++friendsFlight
  try {
    const {items} = await api.friends.list(acc.account.id)
    // A late answer for a previous account must never overwrite the current one.
    if (flight === friendsFlight && state.account?.account?.id === acc.account.id) set({friends: items, friendsError: null})
  } catch (e) {
    if (flight !== friendsFlight) return
    if (e instanceof CompanionRequestError && e.code === 'auth_session_required') { void loadAccount(); return }
    set({friendsError: e instanceof CompanionRequestError ? e.code : 'network_error'})
  }
}

/** Sign-in gate for protected actions. Resolves true once signed in, false if cancelled. */
let pendingAuth: ((ok: boolean) => void) | null = null, authSeq = 0
export function requireSignIn(action: I18nKey): Promise<boolean> {
  if (state.account?.authenticated) return Promise.resolve(true)
  pendingAuth?.(false)
  return new Promise(resolve => { pendingAuth = resolve; set({authPrompt: {action, id: ++authSeq}}) })
}
export function resolveAuth(ok: boolean) { const r = pendingAuth; pendingAuth = null; set({authPrompt: null}); r?.(ok) }
export function openSignIn(action: I18nKey = 'auth.action.generic') { void requireSignIn(action) }
