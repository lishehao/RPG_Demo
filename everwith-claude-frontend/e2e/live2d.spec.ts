/**
 * Live2D evidence for the five official characters on the character page:
 * 1× large-face framing, ≥4 fps frame sampling for ~30 s (motion continuity), expression
 * cues (happy / surprised / back to neutral), channel inventory (no eyeball writes),
 * and lifecycle (switching characters releases runtimes; context loss recovers).
 * Software GL (SwiftShader) in CI: timings are slower than a real GPU.
 */
import {expect, test} from '@playwright/test'
import type {Page} from '@playwright/test'
import {writeFileSync} from 'node:fs'
import {evidencePath, writeJSON} from './helpers'

const KEYS = ['lena', 'arthur', 'marcus', 'nora', 'iris'] as const
const SAMPLE_SECONDS = Number(process.env.LIVE2D_SAMPLE_SECONDS ?? 30)

type Snapshot = {active: number; created: number; disposed: number; framesDrawn: number; frameErrors?: number; skippedHidden?: number; runtimes: {character: string; status: string; lastError?: string | null; frames: number; avgFrameMs: number; maxFrameMs: number; expression: string | null; channels: string[]; extras: string[]; contextLosses: number; restores: number}[]}
const snap = (page: Page) => page.evaluate(() => window.__everwithLive2D!.snapshot() as unknown as Snapshot)
const saveDataUrl = (url: string, path: string) => writeFileSync(path, Buffer.from(url.split(',')[1], 'base64'))

async function sample(page: Page, seconds: number) {
  return page.evaluate(async secs => {
    const canvas = document.querySelector<HTMLCanvasElement>('.ew-stage canvas:not([hidden])')!
    const small = document.createElement('canvas'); small.width = 96; small.height = 128
    const ctx = small.getContext('2d', {willReadFrequently: true})!
    const thumbs: {t: number; url: string}[] = []
    const diffs: {t: number; diff: number}[] = []
    let prev: Uint8ClampedArray | null = null
    const start = performance.now()
    const thumb = () => { const c = document.createElement('canvas'); c.width = 240; c.height = Math.round(240 * canvas.height / canvas.width); c.getContext('2d')!.drawImage(canvas, 0, 0, c.width, c.height); return c.toDataURL('image/jpeg', .82) }
    await new Promise<void>(resolve => {
      let n = 0
      const tick = () => {
        const t = (performance.now() - start) / 1000
        ctx.clearRect(0, 0, 96, 128); ctx.drawImage(canvas, 0, 0, 96, 128)
        const data = ctx.getImageData(0, 0, 96, 128).data
        if (prev) { let s = 0; for (let i = 0; i < data.length; i += 4) s += Math.abs(data[i] - prev[i]) + Math.abs(data[i + 1] - prev[i + 1]) + Math.abs(data[i + 2] - prev[i + 2]); diffs.push({t, diff: s / (96 * 128 * 3)}) }
        prev = data
        if (n % 20 === 0) thumbs.push({t, url: thumb()})
        n++
        if (t >= secs) { thumbs.push({t, url: thumb()}); resolve() } else setTimeout(tick, Math.max(0, start + n * 200 - performance.now())) // 5 Hz schedule, drift-compensated
      }
      tick()
    })
    return {samples: diffs.length + 1, fps: (diffs.length + 1) / secs, diffs, thumbs}
  }, seconds)
}

test.describe.configure({mode: 'serial'})

for (const key of KEYS) {
  test(`${key}: big face, continuous idle motion, expressions, channel inventory @long`, async ({page}) => {
    test.setTimeout((SAMPLE_SECONDS + 90) * 1000)
    await page.goto(`/#/characters/official-${key}?v=1`)
    await expect(page.locator('.ew-stage[data-live2d-status="ready"]')).toBeVisible({timeout: 30_000})
    await page.getByRole('button', {name: '放大'}).or(page.locator('.ew-stage-zoom')).first().click()
    await page.waitForTimeout(1500)
    const stage = page.locator('.ew-character-stage')
    await stage.screenshot({path: evidencePath('live2d', key, '1x-large-face.png')})
    const s = await sample(page, SAMPLE_SECONDS)
    s.thumbs.forEach((th, i) => saveDataUrl(th.url, evidencePath('live2d', key, `frame-${String(i).padStart(2, '0')}-t${th.t.toFixed(1)}s.jpg`)))
    const diffs = s.diffs.map(d => d.diff)
    const moving = diffs.filter(d => d > 0.05).length / diffs.length
    const maxJump = Math.max(...diffs)
    const mean = diffs.reduce((a, b) => a + b, 0) / diffs.length
    // Expressions are driven exactly like a committed cue would drive them.
    const faces: Record<string, string | null> = {}
    for (const e of ['happy', 'surprised', 'neutral'] as const) {
      await page.evaluate(([k, x]) => window.__everwithLive2D!.debugSetExpression(k, x), [key, e] as const)
      await page.waitForTimeout(1200)
      await stage.screenshot({path: evidencePath('live2d', key, `expression-${e}.png`)})
      faces[e] = (await snap(page)).runtimes.find(r => r.character === key)?.expression ?? null
    }
    const rt = (await snap(page)).runtimes.find(r => r.character === key)!
    const eyeball = rt.channels.filter(c => /EyeBall/i.test(c))
    const report = {character: key, sampleSeconds: SAMPLE_SECONDS, samples: s.samples, fps: Number(s.fps.toFixed(2)),
      motion: {fractionOfSamplesWithChange: Number(moving.toFixed(3)), meanAbsDiff: Number(mean.toFixed(3)), maxAbsDiff: Number(maxJump.toFixed(3))},
      expressionsReported: faces, channels: rt.channels, extras: rt.extras, eyeballChannels: eyeball,
      frameStats: {frames: rt.frames, avgFrameMs: rt.avgFrameMs, maxFrameMs: rt.maxFrameMs}, environment: 'headless Chromium + SwiftShader (software GL)'}
    writeJSON(`live2d-${key}`, report)
    writeFileSync(evidencePath('live2d', key, 'diffs.json'), JSON.stringify(s.diffs))
    expect(s.fps).toBeGreaterThanOrEqual(3.5)
    expect(moving).toBeGreaterThan(0.5) // keeps moving (idle never freezes)
    expect(faces.happy).toBe('happy')
    expect(faces.surprised).toBe('surprised')
    expect(faces.neutral).toBe('neutral')
    expect(eyeball).toEqual([]) // no eyeball/gaze writes (Nora gaze OFF; others not driven)
  })
}

test('lifecycle: switching, zoom, hidden tab, off-screen and the table rail release or pause runtimes; a lost WebGL context recovers', async ({page}) => {
  test.setTimeout(240_000)
  const frames = async (key: string) => (await snap(page)).runtimes.find(r => r.character === key)?.frames ?? 0
  for (const key of [...KEYS, ...KEYS]) {
    await page.goto(`/#/characters/official-${key}?v=1`)
    await expect(page.locator('.ew-stage[data-live2d-status="ready"]')).toBeVisible({timeout: 30_000})
  }
  const a = await snap(page)
  // Zoom in / out four times on the same character: one live runtime at a time.
  for (let i = 0; i < 4; i++) {
    await page.locator('.ew-stage-zoom').click()
    await expect(page.locator('.ew-stage[data-live2d-status="ready"]')).toBeVisible({timeout: 30_000})
  }
  const z = await snap(page)
  // Hidden tab: no draws while hidden, drawing resumes when visible again.
  await page.evaluate(() => { Object.defineProperty(document, 'visibilityState', {configurable: true, get: () => 'hidden'}); document.dispatchEvent(new Event('visibilitychange')) })
  const h0 = await frames('iris'); await page.waitForTimeout(1500); const h1 = await frames('iris')
  await page.evaluate(() => { Object.defineProperty(document, 'visibilityState', {configurable: true, get: () => 'visible'}); document.dispatchEvent(new Event('visibilitychange')) })
  await page.waitForTimeout(1500); const h2 = await frames('iris')
  // Off-screen stage: the observer pauses it; back on screen it resumes.
  await page.evaluate(() => { document.querySelector<HTMLElement>('.ew-stage')!.style.transform = 'translateY(-6000px)' })
  await page.waitForTimeout(700); const o0 = await frames('iris'); await page.waitForTimeout(1500); const o1 = await frames('iris')
  await page.evaluate(() => { document.querySelector<HTMLElement>('.ew-stage')!.style.transform = '' })
  await page.waitForTimeout(1500); const o2 = await frames('iris')
  await page.goto('/#/discover')
  await page.waitForTimeout(800)
  const b = await snap(page)
  // Table rail: open/close the people rail three times on a game table.
  await page.goto('/#/games/cabo/prepare')
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  for (let i = 0; i < 6; i++) { await page.getByRole('button', {name: '人物与桌聊'}).click(); await page.waitForTimeout(700) }
  await page.waitForTimeout(1500)
  const r = await snap(page)
  await page.goto('/#/discover')
  await page.waitForTimeout(800)
  const r2 = await snap(page)
  // Context loss on a fresh stage.
  await page.goto('/#/characters/official-lena?v=1')
  await expect(page.locator('.ew-stage[data-live2d-status="ready"]')).toBeVisible({timeout: 30_000})
  const lost = await page.evaluate(async () => {
    const c = document.querySelector<HTMLCanvasElement>('.ew-stage canvas:not([hidden])')!
    const gl = c.getContext('webgl')!
    const ext = gl.getExtension('WEBGL_lose_context')!
    ext.loseContext()
    await new Promise(r => setTimeout(r, 600))
    ext.restoreContext()
    await new Promise(r => setTimeout(r, 2500))
    return true
  })
  const c = await snap(page)
  const lena = c.runtimes.find(r => r.character === 'lena')
  const framesBefore = lena?.frames ?? 0
  await page.waitForTimeout(1500)
  const framesAfter = await frames('lena')
  const memory = await page.evaluate(() => (performance as unknown as {memory?: {usedJSHeapSize: number}}).memory?.usedJSHeapSize ?? null)
  writeJSON('live2d-lifecycle', {afterTenSwitches: {active: a.active, created: a.created, disposed: a.disposed},
    afterFourZoomToggles: {active: z.active, created: z.created, disposed: z.disposed},
    hiddenTab: {framesAtHide: h0, after1500msHidden: h1, after1500msVisible: h2, skippedHidden: (await snap(page)).skippedHidden},
    offscreen: {framesAtOffscreen: o0, after1500msOffscreen: o1, after1500msBack: o2},
    afterLeaving: {active: b.active, created: b.created, disposed: b.disposed},
    tableRailSixToggles: {activeOnTable: r.active, createdMinusDisposedOnTable: r.created - r.disposed, afterLeavingTable: {active: r2.active, created: r2.created, disposed: r2.disposed}},
    contextLoss: {simulated: lost, contextLosses: lena?.contextLosses, restores: lena?.restores, status: lena?.status, lastError: lena?.lastError ?? null, frameErrors: c.frameErrors ?? 0, framesBefore, framesAfter, framesAdvancingAfterRestore: framesAfter > framesBefore},
    usedJSHeapBytesAtEnd: memory, environment: 'headless Chromium + SwiftShader (software GL)'})
  expect(a.active).toBe(1)
  expect(z.active).toBe(1)
  expect(z.created - z.disposed).toBe(1)
  expect(h1 - h0).toBeLessThanOrEqual(1)
  expect(h2).toBeGreaterThan(h1)
  expect(o1 - o0).toBeLessThanOrEqual(1)
  expect(o2).toBeGreaterThan(o1)
  expect(b.active).toBe(0)
  expect(b.created - b.disposed).toBe(0)
  expect(r.created - r.disposed).toBe(r.active)
  expect(r.active).toBeLessThanOrEqual(1)
  expect(r2.active).toBe(0)
  expect(r2.created - r2.disposed).toBe(0)
  expect(lena?.contextLosses).toBeGreaterThanOrEqual(1)
  expect(framesAfter).toBeGreaterThan(framesBefore)
})
