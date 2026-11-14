/**
 * Desktop layout matrix (1024 / 1280 / 1440 / 1920 × 中文 / English), 200 % zoom
 * (emulated as half-size CSS viewport at deviceScaleFactor 2), keyboard focus order,
 * Esc + focus return, reduced motion, and a synthetic CDP IME composition.
 */
import {expect, test} from '@playwright/test'
import type {Page} from '@playwright/test'
import {evidencePath, settle, shot, writeJSON} from './helpers'

const VIEWPORTS: [number, number][] = [[1024, 768], [1280, 800], [1440, 900], [1920, 1080]]
const overflow = (page: Page) => page.evaluate(() => {
  const doc = document.documentElement, main = document.querySelector<HTMLElement>('.ew-main')
  return {docOverflowX: doc.scrollWidth - window.innerWidth, mainOverflowX: main ? main.scrollWidth - main.clientWidth : 0}
})
async function setLang(page: Page, lang: 'zh' | 'en') {
  await page.goto('/#/discover')
  await page.evaluate(l => localStorage.setItem('everwith.ui.lang', JSON.stringify(l)), lang)
}
async function startSplendor(page: Page) {
  await page.goto('/#/games/gems/prepare')
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  await expect(page.locator('.sp-board')).toBeVisible()
}

test('desktop matrix: four widths × two languages, no horizontal overflow @long', async ({browser}) => {
  test.setTimeout(10 * 60_000)
  const results: Record<string, unknown>[] = []
  for (const [w, h] of VIEWPORTS) for (const lang of ['zh', 'en'] as const) {
    const ctx = await browser.newContext({viewport: {width: w, height: h}, locale: lang === 'zh' ? 'zh-CN' : 'en-US'})
    const page = await ctx.newPage()
    await setLang(page, lang)
    const pages: [string, () => Promise<void>][] = [
      ['discover', async () => { await page.goto('/#/discover'); await expect(page.locator('.ew-card').first()).toBeVisible() }],
      ['character', async () => { await page.goto('/#/characters/official-nora?v=1'); await expect(page.locator('.ew-stage')).toBeVisible(); await page.waitForTimeout(1200) }],
      ['story', async () => { await page.goto('/#/stories/story-promise-rain/prepare?v=1'); await page.getByTestId('story-start').click(); await expect(page.getByTestId('story-play')).toBeVisible(); await page.waitForTimeout(800) }],
      ['splendor-table', async () => { await startSplendor(page); await page.waitForTimeout(800) }],
      ['cabo-prepare', async () => { await page.goto('/#/games/cabo/prepare'); await expect(page.locator('.ew-start-btn')).toBeVisible() }],
    ]
    for (const [name, go] of pages) {
      await go()
      await settle(page)
      const o = await overflow(page)
      await page.screenshot({path: evidencePath('screenshots', 'matrix', `${name}-${w}x${h}-${lang}.png`)})
      results.push({page: name, viewport: `${w}x${h}`, lang, ...o})
      expect(o.docOverflowX, `${name} ${w} ${lang}`).toBeLessThanOrEqual(1)
    }
    await ctx.close()
  }
  writeJSON('layout-matrix', results)
})

test('200 % zoom (CSS 640×400 and 720×450 at 2×): content reflows, actions reachable', async ({browser}) => {
  const results: Record<string, unknown>[] = []
  for (const [w, h] of [[640, 400], [720, 450]] as [number, number][]) {
    const ctx = await browser.newContext({viewport: {width: w, height: h}, deviceScaleFactor: 2, locale: 'zh-CN'})
    const page = await ctx.newPage()
    await page.goto('/#/discover')
    await expect(page.locator('.ew-card').first()).toBeVisible()
    await settle(page)
    await page.screenshot({path: evidencePath('screenshots', 'zoom200', `discover-${w}x${h}.png`)})
    results.push({page: 'discover', viewport: `${w}x${h}@2x`, ...(await overflow(page))})
    await startSplendor(page)
    const bar = page.locator('.gb-actionbar')
    await expect(bar).toBeVisible()
    await settle(page)
    await page.screenshot({path: evidencePath('screenshots', 'zoom200', `splendor-${w}x${h}.png`)})
    await page.locator('[data-testid^="splendor-bank-"]').first().scrollIntoViewIfNeeded()
    await page.locator('[data-testid^="splendor-bank-"]').first().click()
    await expect(page.getByTestId('splendor-cancel')).toBeVisible()
    results.push({page: 'splendor-table', viewport: `${w}x${h}@2x`, ...(await overflow(page)), bankReachable: true})
    await ctx.close()
  }
  writeJSON('layout-zoom200', results)
})

test('keyboard: skip link, visible focus, Esc closes one dialog layer and returns focus', async ({page}) => {
  await page.goto('/#/characters/official-arthur?v=1')
  const add = page.getByRole('button', {name: '加为好友'}).first()
  await expect(add).toBeVisible() // content loaded before walking the tab order
  await page.keyboard.press('Tab')
  await expect(page.locator('.ew-skip')).toBeFocused()
  // Skip link → main content first.
  await page.keyboard.press('Enter')
  const afterSkip = await page.evaluate(() => document.activeElement?.id || document.activeElement?.className || '')
  const order: string[] = []
  for (let i = 0; i < 16; i++) { await page.keyboard.press('Tab'); order.push(await page.evaluate(() => { const e = document.activeElement as HTMLElement; return `${e.tagName.toLowerCase()}:${(e.getAttribute('aria-label') ?? e.textContent ?? '').trim().slice(0, 24)}` })) }
  expect(order.some(o => o.includes('加为好友')), order.join(' | ')).toBe(true)
  await add.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('dialog[open]')).toBeVisible()
  await expect(page.getByLabel('好友名字')).toBeFocused()
  await shot(page, 'keyboard-dialog-focus')
  await page.keyboard.press('Escape')
  await expect(page.locator('dialog[open]')).toHaveCount(0)
  await expect(add).toBeFocused()
  // Game table: rules dialog via keyboard; Esc returns focus to the trigger.
  await page.goto('/#/games/cabo/prepare')
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  const rules = page.getByRole('button', {name: '规则', exact: true})
  await rules.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('dialog[open]')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(rules).toBeFocused()
  const focusRing = await rules.evaluate(e => getComputedStyle(e).boxShadow)
  writeJSON('keyboard', {skipTarget: afterSkip, tabOrderAfterSkip: order, rulesFocusRing: focusRing})
  expect(focusRing).not.toBe('none')
})

test('reduced motion: OS preference collapses animations; the board stays operable', async ({browser}) => {
  const ctx = await browser.newContext({reducedMotion: 'reduce', viewport: {width: 1280, height: 800}, locale: 'zh-CN'})
  const page = await ctx.newPage()
  await page.goto('/#/games/vegas/prepare')
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  await page.getByTestId('royale-roll').click()
  const dur = await page.locator('.rb-arena .rb-die').first().evaluate(e => getComputedStyle(e).animationDuration)
  await expect(page.locator('[data-testid^="royale-face-"]').first()).toBeVisible()
  await page.screenshot({path: evidencePath('screenshots', 'reduced-motion-royale.png')})
  writeJSON('reduced-motion', {animationDuration: dur})
  expect(parseFloat(dur)).toBeLessThan(0.01)
  await ctx.close()
})

test('IME (synthetic, CDP composition): Enter during composition does not send', async ({page}) => {
  await page.goto('/#/games/cabo/prepare')
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  const box = page.locator('.ew-table-chat textarea')
  await box.click()
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Input.imeSetComposition', {selectionStart: 2, selectionEnd: 2, text: 'ni'})
  await page.keyboard.press('Enter')
  const during = await page.locator('.ew-chat-line.is-me').count()
  await cdp.send('Input.insertText', {text: '你好'})
  await page.waitForTimeout(100)
  await page.keyboard.press('Enter')
  await expect(page.locator('.ew-chat-line.is-me')).toHaveCount(1)
  writeJSON('ime-synthetic', {sentDuringComposition: during, sentAfterCommit: 1, note: 'CDP Input.imeSetComposition — not a real OS IME; a manual macOS/Windows pass is still required.'})
  expect(during).toBe(0)
})
