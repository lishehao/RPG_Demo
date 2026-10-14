/**
 * Generated art (user-provided GPT batch v2-batch-01 — rights unverified, see
 * docs/GENERATED_ASSETS.json): every picture used from it really loads where it is shown,
 * story scenes follow the committed beats, the persona picture and work cover choices
 * persist and show up elsewhere, and with the “assets missing” scenario every one of
 * them disappears cleanly (no broken image, no other character's face).
 */
import {expect, test} from '@playwright/test'
import type {Page} from '@playwright/test'
import {settle, shot, writeJSON} from './helpers'

type Seen = Map<string, boolean>
/** Generated images inside the viewport (lazy images further down are not expected to have loaded). */
const generatedImages = (page: Page) => page.evaluate(() => [...document.images]
  .filter(i => (i.currentSrc || i.src).includes('/generated/'))
  .filter(i => { const r = i.getBoundingClientRect(); return r.width > 0 && r.bottom > 0 && r.top < innerHeight })
  .map(i => ({src: new URL(i.currentSrc || i.src).pathname, ok: i.complete && i.naturalWidth > 0})))
const scrollMain = (page: Page, to: 'end' | 'top') => page.locator('#main').evaluate((m, where) => m.scrollTo(0, where === 'end' ? m.scrollHeight : 0), to)
async function collect(page: Page, seen: Seen) {
  await settle(page)
  for (const r of await generatedImages(page)) seen.set(r.src, (seen.get(r.src) ?? true) && r.ok)
}
/** Images that finished loading with nothing to show (a broken-image icon). */
const brokenImages = (page: Page) => page.evaluate(() => [...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src')))

test('generated art loads where it is used; story scenes follow the beats', async ({page}) => {
  const seen: Seen = new Map()
  await page.goto('/#/discover')
  await expect(page.locator('.ew-card').first()).toBeVisible()
  await collect(page, seen)
  await shot(page, 'art-discover')
  await scrollMain(page, 'end')
  await collect(page, seen)
  await scrollMain(page, 'top')
  await page.goto('/#/discover?tab=games')
  await expect(page.locator('.ew-card.is-game')).toHaveCount(3)
  await collect(page, seen)
  for (const id of ['official-arthur', 'official-iris']) {
    await page.goto(`/#/characters/${id}?v=1`)
    await expect(page.locator('.ew-character-stage .ew-backdrop img')).toHaveAttribute('src', `/generated/batch-01/backdrop-${id.slice(9)}.webp`)
    await collect(page, seen)
  }
  for (const id of ['story-promise-rain', 'story-last-train']) {
    await page.goto(`/#/stories/${id}?v=1`)
    await expect(page.locator('.ew-story-cover img')).toHaveAttribute('src', `/generated/batch-01/${id}-cover-wide.webp`)
    await collect(page, seen)
  }
  await shot(page, 'art-story-detail')

  // Scenes: opening → beat 1 → beat 2 → beat 3 → a free turn in open mode (ending place).
  await page.goto('/#/stories/story-last-train/prepare?v=1')
  await expect(page.locator('.ew-prepare-poster img')).toHaveAttribute('src', '/generated/batch-01/story-last-train-cover-tall.webp')
  await page.getByTestId('story-start').click()
  await expect(page.getByTestId('story-play')).toBeVisible()
  const scene = page.locator('.ew-story-scene')
  await expect(scene).toHaveAttribute('data-scene', 'waiting-room')
  await expect(scene.locator('.ew-story-scene-label')).toHaveText('候车室 · 深夜')
  await collect(page, seen)
  const order: string[] = []
  for (const expected of ['waiting-room', 'corner', 'duty-room', 'platform-dawn']) {
    await page.getByTestId('story-continue-btn').click()
    await expect(page.getByTestId('story-pending')).toBeHidden({timeout: 15_000})
    await expect(scene).toHaveAttribute('data-scene', expected)
    await expect(scene.locator('img')).toHaveAttribute('src', new RegExp(`scene-${expected}\\.webp$`))
    order.push(expected)
    await collect(page, seen)
  }
  await shot(page, 'art-story-scene-dawn')

  await page.goto('/#/recent')
  await expect(page.getByTestId('record').first().locator('.ew-record-icon img')).toHaveAttribute('src', '/generated/batch-01/story-last-train-cover-tall.webp')
  await collect(page, seen)
  for (const [path, art] of [['/#/friends', 'signin'], ['/#/create', 'create'], ['/#/no-such-page', 'not-found']] as const) {
    await page.goto(path)
    await expect(page.locator(`.ew-empty .ew-spot[data-art="${art}"]`)).toBeVisible()
    await collect(page, seen)
  }
  await page.goto('/#/create')
  await page.getByTestId('create-new').click()
  await expect(page.locator('dialog[open] .ew-type-art')).toHaveCount(2)
  await collect(page, seen)
  await shot(page, 'art-create-types')

  const icon = await page.request.get('/generated/batch-01/favicon-64.png')
  expect(icon.status()).toBe(200)
  expect(await page.locator('link[rel="icon"]').getAttribute('href')).toBe('/generated/batch-01/favicon-64.png')
  const bad = [...seen].filter(([, ok]) => !ok).map(([src]) => src)
  writeJSON('generated-art', {seen: [...seen.keys()].sort(), count: seen.size, notLoaded: bad, sceneOrder: order})
  expect(bad).toEqual([])
  expect(seen.size).toBeGreaterThanOrEqual(20)
  for (const must of ['brand-emblem.png', 'backdrop-arthur.webp', 'game-splendor-cover.webp', 'story-promise-rain-cover-wide.webp', 'story-last-train-scene-platform-dawn.webp', 'state-not-found.webp', 'create-type-story.webp'])
    expect([...seen.keys()].some(src => src.endsWith(must)), must).toBe(true)
})

test('persona picture and work cover: chosen, kept after reload, shown elsewhere', async ({page}) => {
  await page.goto('/#/account')
  await page.getByLabel('称呼').fill('小雨')
  await page.locator('[data-avatar="persona-avatar-06"]').click()
  await page.getByRole('button', {name: '保存 Persona'}).click()
  await expect(page.locator('.ew-nav-avatar img')).toHaveAttribute('src', '/generated/batch-01/persona-avatar-06.webp')
  await page.reload()
  await expect(page.locator('[data-avatar="persona-avatar-06"]')).toHaveAttribute('aria-pressed', 'true')
  await shot(page, 'art-persona-avatar')
  await page.goto('/#/games/cabo/prepare')
  await expect(page.locator('.ew-seat-row').first().locator('img')).toHaveAttribute('src', '/generated/batch-01/persona-avatar-06.webp')
  await expect(page.locator('.ew-prepare-poster img')).toHaveAttribute('src', '/generated/batch-01/game-cabo-cover.webp')

  await page.goto('/#/create')
  await page.getByTestId('create-new').click()
  await page.getByTestId('type-character').click()
  await page.getByTestId('work-name').fill('雨夜来信')
  await page.getByTestId('work-create').click()
  await expect(page.getByTestId('work-editor')).toBeVisible()
  await expect(page.locator('[data-testid="cover-picker"] [aria-pressed="true"]')).toHaveCount(1) // a preset cover from the start
  await page.locator('[data-cover="work-cover-05"]').click()
  await expect(page.getByTestId('sync-status')).toHaveText('草稿已同步', {timeout: 10_000})
  await shot(page, 'art-work-cover-picker')
  await page.goto('/#/create')
  await expect(page.getByTestId('work-card').first().locator('.ew-work-cover img')).toHaveAttribute('src', '/generated/batch-01/work-cover-05.webp')
  await shot(page, 'art-work-cards')
})

test('assets missing: generated art drops out cleanly — no broken image, no substitute face', async ({page}) => {
  await page.goto('/#/discover')
  await page.evaluate(() => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify({'assets.missing': true})))
  const pages = ['/#/discover', '/#/discover?tab=games', '/#/characters/official-nora?v=1', '/#/stories/story-promise-rain?v=1', '/#/friends', '/#/create', '/#/account']
  const report: Record<string, unknown> = {}
  for (const path of pages) {
    await page.goto(path)
    await page.reload()
    await settle(page)
    const broken = await brokenImages(page)
    const generated = await generatedImages(page)
    report[path] = {broken, generatedShown: generated.filter(g => g.ok).length}
    expect(broken, path).toEqual([])
    expect(generated.filter(g => g.ok), path).toEqual([])
  }
  await expect(page.locator('.ew-backdrop')).toHaveCount(0)
  await expect(page.locator('.ew-brand-mark')).toHaveText('e') // lettermark fallback
  await page.goto('/#/characters/official-nora?v=1')
  await page.reload()
  await settle(page)
  await expect(page.locator('.ew-character-stage .ew-backdrop')).toHaveCount(0)
  await shot(page, 'art-missing-character')
  writeJSON('generated-art-missing', report)
})
