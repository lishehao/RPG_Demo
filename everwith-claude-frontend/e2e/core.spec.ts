/**
 * Core journeys on the mock adapter: discover states, add-friend with sign-in in the
 * middle, private chat (send / stop / retry / unknown result), draft persistence, and
 * “play together” from a friend. Scenario switches are the documented mock scenarios.
 */
import {expect, test} from '@playwright/test'
import type {Page} from '@playwright/test'
import {shot, signUp, writeJSON} from './helpers'

const setScenarios = (page: Page, on: Record<string, true>) => page.evaluate(v => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify(v)), on)
const composer = (page: Page) => page.locator('.ew-chat-main textarea')
const playerBubbles = (page: Page, text: string) => page.locator('.ew-msg.is-player:not(.is-provisional) .ew-msg-bubble', {hasText: text})

test('discover: first visit, tabs, empty search vs load failure, deep link and Back', async ({page}) => {
  await page.goto('/')
  await expect(page).toHaveURL(/#\/discover$/)
  await expect(page.locator('.ew-card').first()).toBeVisible()
  await shot(page, 'discover-all-zh')
  await page.getByRole('link', {name: '游戏', exact: true}).click()
  await expect(page).toHaveURL(/tab=games/)
  await shot(page, 'discover-games-zh')
  await page.getByRole('searchbox').or(page.locator('.ew-search input')).first().fill('zzzz')
  await expect(page.getByText('没有找到与“zzzz”相关的内容。')).toBeVisible()
  await shot(page, 'discover-empty-search')
  await setScenarios(page, {'discover.error': true})
  await page.goto('/#/discover?tab=stories')
  await page.reload()
  await expect(page.getByText('内容加载失败（不是“没有内容”）。')).toBeVisible()
  await shot(page, 'discover-load-error')
  await setScenarios(page, {})
  await page.reload()
  await page.locator('.ew-card').first().click()
  await expect(page).toHaveURL(/#\/stories\//)
  await page.goBack()
  await expect(page).toHaveURL(/tab=stories/)
})

test('add friend: naming → sign-in in the middle → same name restored → confirm → private chat', async ({page}) => {
  await page.goto('/#/characters/official-lena?v=1')
  await page.getByRole('button', {name: '加为好友'}).first().click()
  const name = page.getByLabel('好友名字')
  await name.fill('雨夜的 Lena')
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await signUp(page, 'e2e-core@example.com')
  await expect(page.getByLabel('好友名字')).toHaveValue('雨夜的 Lena') // restored, not auto-created
  await shot(page, 'friend-naming-after-signin')
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await expect(page).toHaveURL(/#\/friends\/fr_/)
  await expect(composer(page)).toBeVisible()

  // Send with Enter, receive a committed reply.
  await composer(page).fill('你好，今天下雨了')
  await composer(page).press('Enter')
  await expect(playerBubbles(page, '你好，今天下雨了')).toHaveCount(1, {timeout: 20_000})
  await expect(page.locator('.ew-msg.is-character:not(.is-provisional)').last()).toBeVisible()
  await page.waitForTimeout(1500)
  await shot(page, 'chat-after-reply')

  // Draft survives a reload (per account/friend/epoch/conversation).
  await composer(page).fill('还没发出的草稿')
  await page.waitForTimeout(400)
  await page.reload()
  await expect(composer(page)).toHaveValue('还没发出的草稿')

  // Stop: the partial reply never enters history; the text comes back.
  await composer(page).fill('请讲一个很长的故事')
  await composer(page).press('Enter')
  await page.locator('.ew-send.is-stop').click()
  await expect(page.getByText('已停止。半段回复没有进入记录，原输入已放回输入框。')).toBeVisible({timeout: 15_000})
  await expect(playerBubbles(page, '请讲一个很长的故事')).toHaveCount(0)
  await shot(page, 'chat-stopped')

  // Retryable failure through the Mock panel UI → explicit Retry of the same operation.
  await page.getByTestId('mock-panel-open').click()
  await page.getByLabel(/下一次私聊：生成中途可重试失败/).check()
  await shot(page, 'mock-panel')
  await page.keyboard.press('Escape')
  await composer(page).fill('第二句话')
  await composer(page).press('Enter')
  await expect(page.getByText('这次生成中断了。原输入已保留，可以明确“重试”同一条（不会重复发送）。')).toBeVisible({timeout: 20_000})
  await shot(page, 'chat-retryable')
  await page.getByRole('button', {name: '重试同一条'}).click()
  await expect(playerBubbles(page, '第二句话')).toHaveCount(1, {timeout: 20_000})

  // Unknown result: look up the original key first; never a second turn.
  await setScenarios(page, {'chat.unknown_result': true})
  await page.reload()
  await composer(page).fill('结果未知的一句')
  await composer(page).press('Enter')
  await expect(page.getByText('尚未确认这条消息是否被接收。请先“查询原请求”，不要重新发送。')).toBeVisible({timeout: 15_000})
  await shot(page, 'chat-unknown-result')
  await page.getByRole('button', {name: '查询原请求'}).click()
  const resend = page.getByRole('button', {name: '用同一请求重新发送'})
  if (await resend.isVisible({timeout: 3000}).catch(() => false)) await resend.click()
  await expect(playerBubbles(page, '结果未知的一句')).toHaveCount(1, {timeout: 20_000})
  writeJSON('chat-core', {ok: true, checked: ['enter-send', 'draft-reload', 'stop', 'retry-same-op', 'unknown-lookup']})

  // Play together → game prepare keeps the friend in seat 1 → explicit Start.
  if (!(await page.getByRole('button', {name: '一起玩'}).isVisible())) await page.getByRole('button', {name: '工具'}).click()
  await page.getByRole('button', {name: '一起玩'}).click()
  await page.getByRole('button', {name: /Splendor/}).click()
  await expect(page).toHaveURL(/#\/games\/gems\/prepare\?with=/)
  await expect(page.locator('.ew-seat-row').nth(1)).toContainText('雨夜的 Lena')
  await shot(page, 'play-together-prepare')
  await page.locator('.ew-start-btn').click()
  await expect(page).toHaveURL(/#\/play\/game\//)
  await expect(page.locator('.ew-seat[data-seat="1"]')).toContainText('雨夜的 Lena')
  await shot(page, 'play-together-table')
  await page.getByRole('link', {name: /去私聊 · 雨夜的 Lena/}).click()
  await expect(page).toHaveURL(/#\/friends\/fr_/)
  await expect(composer(page)).toBeVisible()
})
