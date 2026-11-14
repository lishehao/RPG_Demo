/**
 * Story run (prepare → play → continue → rollback → befriend the current person) and the
 * creation studio (type → name → edit → AI-template assist + undo → isolated preview →
 * stale preview → sign-in → save → explicit share → befriend v1 → chat).
 */
import {expect, test} from '@playwright/test'
import {shot, signUp, writeJSON} from './helpers'

test('story: explicit start, committed turns only, continue, rollback restores the draft, befriend the person in this run', async ({page}) => {
  await page.goto('/#/stories/story-promise-rain?v=1')
  await shot(page, 'story-detail')
  await page.getByTestId('story-prepare').click()
  await expect(page.getByText('确认前不会创建任何记录。').first()).toBeVisible()
  await shot(page, 'story-prepare')
  await page.getByTestId('story-start').click()
  await expect(page.getByTestId('story-play')).toBeVisible()
  const scene = page.locator('.ew-story-scene')
  await expect(scene).toHaveAttribute('data-scene', 'entrance-rain')
  const input = page.locator('.ew-story-main textarea')
  await input.fill('我凑近看看那份名单上的墨迹')
  await input.press('Enter')
  await expect(page.getByTestId('story-pending')).toBeVisible()
  await shot(page, 'story-validating')
  await expect(page.getByTestId('story-pending')).toBeHidden({timeout: 15_000})
  await expect(page.getByText('新线索：未干的划线墨迹')).toBeVisible()
  const playerLines = page.locator('.ew-story-main .ew-msg.is-player:not(.is-provisional)')
  await expect(playerLines).toHaveCount(1)
  await page.getByTestId('story-continue-btn').click()
  await expect(page.getByTestId('story-pending')).toBeHidden({timeout: 15_000})
  await expect(page.locator('.ew-objectives li.is-done')).toHaveCount(2)
  await expect(playerLines).toHaveCount(1) // “Continue” never invents a player line
  await expect(scene).toHaveAttribute('data-scene', 'backstage') // the committed beat moved the scene
  await shot(page, 'story-after-continue')
  const revBefore = Number(await page.getByTestId('story-play').getAttribute('data-revision'))

  // Roll back to the first action: text + state withdraw together, the action returns as a draft.
  await page.locator('.ew-turn').nth(1).hover()
  await page.getByRole('button', {name: '回退到这里'}).first().click()
  await shot(page, 'story-rollback-confirm')
  await page.locator('dialog[open] .ew-btn.danger').click()
  await expect(input).toHaveValue('我凑近看看那份名单上的墨迹')
  await expect(page.locator('.ew-objectives li.is-done')).toHaveCount(0)
  await expect(scene).toHaveAttribute('data-scene', 'entrance-rain') // scene withdrawn with the text
  const revAfter = Number(await page.getByTestId('story-play').getAttribute('data-revision'))
  expect(revAfter).toBeGreaterThan(revBefore)

  // Retryable validation failure: no half turn; explicit retry of the same turn.
  await page.evaluate(() => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify({'story.retryable_failure': true})))
  await page.reload()
  await input.press('Enter')
  await expect(page.getByText('这一轮没有完成（可重试，未写入任何内容）。')).toBeVisible({timeout: 15_000})
  await shot(page, 'story-retryable')
  await page.getByTestId('story-retry').click()
  await expect(page.getByText('新线索：未干的划线墨迹')).toBeVisible({timeout: 15_000})

  // F2: befriend THIS person (Marcus as stage manager) — sign-in in the middle, same run continues.
  await page.getByTestId('story-befriend-stage').click()
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await signUp(page, 'e2e-story@example.com')
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await expect(page.locator('.ew-story-cast-row[data-role="stage"]')).toContainText('好友')
  await shot(page, 'story-befriended-in-run')
  writeJSON('story-run', {ok: true, revBefore, revAfter})
})

test('creation studio: type → name → edit → assist/undo → isolated preview → stale → save → share → befriend v1', async ({page}) => {
  await page.goto('/#/create')
  await expect(page.getByText('你还没有作品。')).toBeVisible()
  await page.getByTestId('create-new').click()
  await expect(page.getByTestId('work-create')).toBeDisabled()
  await page.getByTestId('type-character').click()
  await page.getByTestId('work-name').fill('晚风')
  await shot(page, 'create-type-and-name')
  await page.getByTestId('work-create').click()
  await expect(page.getByTestId('work-editor')).toBeVisible()
  await expect(page.getByTestId('preview-start')).toBeDisabled() // required fields missing
  await page.getByTestId('assist-fill').click()
  await expect(page.getByTestId('field-persona')).not.toHaveValue('')
  await page.getByTestId('assist-undo').click()
  await expect(page.getByTestId('field-persona')).toHaveValue('')
  await page.getByTestId('assist-fill').click()
  await expect(page.getByTestId('sync-status')).toHaveText('草稿已同步', {timeout: 10_000})
  await page.getByTestId('preview-start').click()
  const say = page.locator('.ew-preview textarea')
  await say.fill('你好，你平时喜欢做什么？')
  await say.press('Enter')
  await expect(page.locator('.ew-preview .ew-msg.is-player')).toHaveCount(1)
  await page.getByTestId('field-habit').fill('说话很慢，喜欢停顿')
  await expect(page.getByTestId('preview-stale')).toBeVisible({timeout: 10_000})
  await shot(page, 'create-preview-stale')
  await page.getByTestId('work-save').click()
  await signUp(page, 'e2e-create@example.com')
  await page.getByTestId('work-save').click()
  await expect(page.getByText('已保存 v1').first()).toBeVisible()
  await page.getByTestId('share-on').click()
  await expect(page.getByText('已分享 v1').first()).toBeVisible()
  await shot(page, 'create-saved-shared')
  await page.getByTestId('work-befriend').click()
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await expect(page).toHaveURL(/#\/friends\/fr_/)
  // A self-made character has no room of its own: the generic generated backdrop, never an official one.
  await expect(page.locator('.ew-chat-portrait .ew-backdrop img')).toHaveAttribute('src', '/generated/batch-01/backdrop-generic.webp')
  // The isolated preview never leaks into the friend's real conversation (no test lines as memory).
  await expect(page.locator('.ew-chat-main')).not.toContainText('你好，你平时喜欢做什么？')
  const box = page.locator('.ew-chat-main textarea')
  await box.fill('你好呀')
  await box.press('Enter')
  await expect(page.locator('.ew-msg.is-character:not(.is-provisional)').last()).toBeVisible({timeout: 20_000})
  await shot(page, 'create-friend-chat')
})
