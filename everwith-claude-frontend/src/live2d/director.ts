/**
 * One requestAnimationFrame for every visible runtime. Hidden documents and
 * off-screen stages are skipped (no writes, no draws). Exposes counters so tests can
 * verify that switching characters / closing stages returns everything to zero.
 */
import type {ModelRuntime} from './runtime'

type Entry = {runtime: ModelRuntime; visible: boolean; lastDraw: number}
const entries = new Map<ModelRuntime, Entry>()
let raf = 0
export const live2dCounters = {created: 0, disposed: 0, framesDrawn: 0, skippedHidden: 0, throttled: 0, frameErrors: 0}

function loop(now: number) {
  raf = 0
  if (document.visibilityState === 'hidden') { live2dCounters.skippedHidden++; return }
  for (const e of entries.values()) {
    if (!e.visible) continue
    // Adaptive budget: a runtime whose frames cost > 12 ms (e.g. software GL) renders at
    // ~30 fps so it never starves input, timers and the chat/game UI on the same thread.
    if (e.runtime.stats.avgFrameMs > 12 && now - e.lastDraw < 30) { live2dCounters.throttled++; continue }
    // One failing frame (e.g. a draw racing a context loss) must not end the shared loop
    // for every stage: record it on that runtime and keep scheduling.
    try { if (e.runtime.frame(now)) { live2dCounters.framesDrawn++; e.lastDraw = now } }
    catch (error) { live2dCounters.frameErrors++; e.runtime.noteFrameError(error) }
  }
  if (entries.size) raf = requestAnimationFrame(loop)
}
function kick() { if (!raf && entries.size && document.visibilityState !== 'hidden') raf = requestAnimationFrame(loop) }
if (typeof document !== 'undefined') document.addEventListener('visibilitychange', kick)

export const director = {
  register(runtime: ModelRuntime) { entries.set(runtime, {runtime, visible: true, lastDraw: 0}); live2dCounters.created++; kick() },
  setVisible(runtime: ModelRuntime, visible: boolean) { const e = entries.get(runtime); if (e) { e.visible = visible; kick() } },
  unregister(runtime: ModelRuntime) { if (entries.delete(runtime)) live2dCounters.disposed++ },
  /** Evidence hook (tests / manual review): drive a visible runtime's expression like a committed cue would. */
  debugSetExpression(character: string, expression: 'neutral' | 'happy' | 'surprised') {
    let n = 0
    for (const e of entries.values()) if (e.runtime.cfg.key === character) { e.runtime.setExpression(expression); n++ }
    return n
  },
  snapshot() {
    return {
      active: entries.size, ...live2dCounters,
      runtimes: [...entries.values()].map(e => ({character: e.runtime.cfg.key, status: e.runtime.status, visible: e.visible, frames: e.runtime.stats.frames,
        avgFrameMs: Number(e.runtime.stats.avgFrameMs.toFixed(2)), maxFrameMs: Number(e.runtime.stats.maxFrameMs.toFixed(2)), contextLosses: e.runtime.stats.contextLosses,
        restores: e.runtime.stats.restores, expression: e.runtime.lastFrame?.state.expression ?? null, eye: e.runtime.lastFrame?.state.eye ?? null, mouth: e.runtime.lastFrame?.state.mouth ?? null,
        error: e.runtime.error, lastError: e.runtime.stats.lastError, canvas: [e.runtime.canvas.width, e.runtime.canvas.height],
        channels: Object.keys(e.runtime.lastFrame?.canonical ?? {}), extras: Object.keys(e.runtime.lastFrame?.extras ?? {}), swapping: e.runtime.lastFrame?.state.swapping ?? null})),
    }
  },
}
declare global { interface Window { __everwithLive2D?: typeof director } }
if (typeof window !== 'undefined') window.__everwithLive2D = director
