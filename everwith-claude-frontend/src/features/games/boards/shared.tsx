import {useCallback, useState} from 'react'
import type {ReactNode} from 'react'
import {useSyncExternalStore} from 'react'
import {useI18n} from '../../../app/i18n'
import {scenarios} from '../../../mock/scenarios'
import {classNames} from '../../../lib/util'
import type {GameViewJSON} from '../../../api/types'

export type BoardProps = {view: GameViewJSON; pending: boolean; act: (action: Record<string, unknown>) => Promise<boolean>; seatName: (seat: number) => string; readOnly: boolean}
const SEAT_COLORS = ['#e6bd5a', '#cb5367', '#4b94b5', '#f0e9d6', '#529e76']
/** One colour per real seat, shared by dice, tokens, dots and the result table. */
export const seatColor = (seat: number) => SEAT_COLORS[seat % SEAT_COLORS.length]

/** Board art lives in the byte-identical handoff copy (see scripts/sync-assets.mjs). */
export const GAME_ASSETS = '/handoff/assets/games'

export type BoardDict = Record<string, string>
/** Board-local strings: keeps the three boards self-contained and both languages complete. */
export function useBoardText(dicts: {zh: BoardDict; en: BoardDict}) {
  const {lang} = useI18n()
  return useCallback((key: string, vars?: Record<string, string | number>) => {
    let s = dicts[lang][key] ?? dicts.zh[key] ?? key
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v))
    return s
  }, [dicts, lang])
}

/** Same rewrite as portraits so the “assets missing” scenario also covers boards. */
export function useBoardAsset() {
  const missing = useSyncExternalStore(scenarios.subscribe, () => scenarios.isOn('assets.missing'), () => false)
  return useCallback((path: string) => missing ? path.replace('/handoff/', '/handoff/__missing__/') : path, [missing])
}

/**
 * CSS crop of a sub-rectangle of an image into a box of a known aspect ratio (cover, with
 * a slight upward bias like the reference `imageCrop`). Pure presentation; no game data.
 */
export function cropStyle(src: string, imageW: number, imageH: number, rect: [number, number, number, number], boxAspect: number, biasX = .5, biasY = .45) {
  const [nx, ny, nw, nh] = rect
  let sx = nx * imageW, sy = ny * imageH, sw = nw * imageW, sh = nh * imageH
  if (sw / sh > boxAspect) { const next = sh * boxAspect; sx += (sw - next) * biasX; sw = next } else { const next = sw / boxAspect; sy += (sh - next) * biasY; sh = next }
  const px = imageW - sw < .5 ? 0 : sx / (imageW - sw) * 100
  const py = imageH - sh < .5 ? 0 : sy / (imageH - sh) * 100
  return {backgroundImage: `url("${src}")`, backgroundSize: `${(imageW / sw * 100).toFixed(3)}% auto`, backgroundPosition: `${px.toFixed(3)}% ${py.toFixed(3)}%`, backgroundRepeat: 'no-repeat'}
}

/** Selection that silently resets whenever the authoritative revision changes. */
export function useRevisionState<T>(initial: T, revision: number): [T, (next: T | ((prev: T) => T)) => void] {
  const [box, setBox] = useState<{rev: number; value: T}>({rev: revision, value: initial})
  const value = box.rev === revision ? box.value : initial
  const set = useCallback((next: T | ((prev: T) => T)) => setBox(b => {
    const prev = b.rev === revision ? b.value : initial
    return {rev: revision, value: typeof next === 'function' ? (next as (p: T) => T)(prev) : next}
  }), [revision])
  return [value, set]
}

/** Bottom action strip: what is selected, what it will cost, Confirm / Cancel. */
export function ActionBar({prompt, detail, children, tone = 'idle', testId}: {prompt: ReactNode; detail?: ReactNode; children?: ReactNode; tone?: 'idle' | 'turn' | 'select' | 'warn'; testId?: string}) {
  return (
    <div className={classNames('gb-actionbar', `tone-${tone}`)} role="group" aria-label={typeof prompt === 'string' ? prompt : undefined} data-testid={testId}>
      <div className="gb-action-text">
        <p className="gb-prompt" aria-live="polite">{prompt}</p>
        {detail && <div className="gb-detail">{detail}</div>}
      </div>
      {children && <div className="gb-action-buttons">{children}</div>}
    </div>
  )
}

export const formatMoney = (n: number, lang: 'zh' | 'en') => n.toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US')
