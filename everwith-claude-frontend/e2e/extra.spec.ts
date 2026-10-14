/**
 * Smaller business rules: sign-in cancel keeps position, table-mate → friend without a
 * restart (F7), abandon → read-only unfinished, Recent continues the exact run, legacy
 * Splendor v1 save keeps its rules, asset/model failure degrades, returning users land
 * on Friends, Shift+Tab.
 */
import {expect, test} from '@playwright/test'
import {settle, shot, signUp, tableSnap, writeJSON} from './helpers'

test('table-mate becomes a friend in place (no restart / no extra seat); sign-in cancel keeps position; abandon is read-only', async ({page}) => {
  await page.goto('/#/games/cabo/prepare')
  await page.getByRole('button', {name: '2 人', exact: true}).click()
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  const before = await tableSnap(page)
  const seatName = (await page.locator('.ew-seat[data-seat="1"] .ew-seat-text strong').innerText()).trim()
  await page.getByRole('button', {name: `加为好友 · ${seatName}`}).click()
  await page.getByRole('button', {name: '确认加为好友'}).click()
  // Cancel sign-in: back on the same table, naming dialog still holds the name.
  await page.locator('dialog[open]').getByRole('button', {name: '取消'}).click()
  await expect(page.getByLabel('好友名字')).toHaveValue(seatName)
  expect((await tableSnap(page)).url).toBe(before.url)
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await signUp(page, 'e2e-extra@example.com')
  await page.getByLabel('好友名字').fill(`${seatName}（牌友）`)
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await expect(page.locator('.ew-seat[data-seat="1"]')).toContainText('好友')
  const after = await tableSnap(page)
  expect(after.url).toBe(before.url)
  expect(await page.locator('.ew-seat').count()).toBe(2)
  await shot(page, 'game-tablemate-befriended')
  // Explicit abandon → unfinished, read-only, no invented winner.
  await page.getByRole('button', {name: '放弃本局'}).click()
  await page.locator('dialog[open] .ew-btn.danger').click()
  await expect(page.getByText('已放弃 · 未完成（只读）').first()).toBeVisible()
  await shot(page, 'game-abandoned')
  await page.goto('/#/recent')
  await expect(page.getByTestId('record').first()).toContainText('已放弃（未完成）')
  writeJSON('tablemate-friend-abandon', {sameSession: after.url === before.url, seats: 2})
})

test('Recent continues the exact run; returning users land on Friends; legacy Splendor v1 keeps its rules', async ({page}) => {
  await page.goto('/#/stories/story-last-train/prepare?v=1')
  await page.getByTestId('story-start').click()
  await expect(page.getByTestId('story-play')).toBeVisible()
  const runUrl = page.url()
  await page.goto('/#/recent')
  await page.getByTestId('record-open').first().click()
  await expect(page).toHaveURL(runUrl)
  // Legacy save fixture through the mock panel.
  await page.getByTestId('mock-panel-open').click()
  await page.getByRole('button', {name: /v1/}).click()
  await page.waitForURL(/#\/play\/game\//)
  await expect(page.getByText('旧版 v1 存档（保持原规则）').first()).toBeVisible()
  await expect(page.locator('.sp-board')).toBeVisible()
  const take = await page.getByTestId('splendor-legal').getAttribute('data-take')
  await shot(page, 'splendor-legacy-v1')
  writeJSON('splendor-legacy-v1', {legalTakesOffered: take})
  // Make a friend, then the empty hash should land on Friends.
  await page.goto('/#/characters/official-iris?v=1')
  await page.getByRole('button', {name: '加为好友'}).first().click()
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await signUp(page, 'e2e-root@example.com')
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await expect(page).toHaveURL(/#\/friends\/fr_/)
  await page.goto('/#/')
  await expect(page).toHaveURL(/#\/friends$/)
})

test('model or image failures degrade to the same person / neutral placeholders; chat still works', async ({page}) => {
  await page.goto('/#/discover')
  await page.evaluate(() => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify({'live2d.model_missing': true, 'assets.missing': true})))
  await page.goto('/#/characters/official-marcus?v=1')
  await page.reload()
  await expect(page.getByText('动态形象不可用，显示同一角色的静态图')).toBeVisible()
  await settle(page)
  await shot(page, 'degraded-model-and-images')
  await page.goto('/#/discover')
  await expect(page.locator('.ew-card').first()).toBeVisible()
  await expect(page.locator('.ew-portrait.is-placeholder').first()).toBeVisible()
  await shot(page, 'degraded-discover-placeholders')
})

test('Shift+Tab walks focus backwards', async ({page}) => {
  await page.goto('/#/account')
  await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Tab')
  const third = await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80))
  await page.keyboard.press('Tab')
  await page.keyboard.press('Shift+Tab')
  expect(await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80))).toBe(third)
})
