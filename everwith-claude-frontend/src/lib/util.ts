/** Small shared helpers. No network, no storage of secrets. */
export type Lang = 'zh' | 'en'
export type L10n = {zh: string; en: string}

export const pick = (text: L10n | string, lang: Lang): string => typeof text === 'string' ? text : text[lang] || text.zh

export function randomId(prefix: string, bytes = 8): string {
  const raw = new Uint8Array(bytes)
  crypto.getRandomValues(raw)
  return `${prefix}_${Array.from(raw, b => b.toString(16).padStart(2, '0')).join('')}`
}

/** Deterministic 32-bit hash for presentation-only variation (never for game randomness). */
export function hash32(text: string): number {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619)
  return h >>> 0
}

export function seededRandom(seed: number): () => number {
  let x = seed >>> 0
  return () => {
    x = (Math.imul(x, 1664525) + 1013904223) >>> 0
    return x / 4294967296
  }
}

export const sleep = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal?.aborted) { reject(signal.reason ?? new DOMException('Aborted', 'AbortError')); return }
  const timer = setTimeout(() => { signal?.removeEventListener('abort', onAbort); resolve() }, ms)
  const onAbort = () => { clearTimeout(timer); reject(signal?.reason ?? new DOMException('Aborted', 'AbortError')) }
  signal?.addEventListener('abort', onAbort, {once: true})
})

export function clamp(value: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, value)) }

export function formatTime(iso: string, lang: Lang): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})
}

export function classNames(...parts: (string | false | null | undefined)[]) { return parts.filter(Boolean).join(' ') }

export function safeStorage(kind: 'local' | 'session' = 'local'): Storage | null {
  try {
    const s = kind === 'local' ? window.localStorage : window.sessionStorage
    const probe = '__everwith_probe__'
    s.setItem(probe, '1'); s.removeItem(probe)
    return s
  } catch { return null }
}

export function readJSON<T>(key: string, fallback: T, kind: 'local' | 'session' = 'local'): T {
  const s = safeStorage(kind)
  if (!s) return fallback
  try {
    const raw = s.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch { return fallback }
}

export function writeJSON(key: string, value: unknown, kind: 'local' | 'session' = 'local') {
  const s = safeStorage(kind)
  if (!s) return
  try { s.setItem(key, JSON.stringify(value)) } catch { /* Quota or privacy mode: keep in memory only. */ }
}

export function removeKey(key: string, kind: 'local' | 'session' = 'local') {
  const s = safeStorage(kind)
  try { s?.removeItem(key) } catch { /* ignore */ }
}
