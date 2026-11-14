/**
 * Edge cases for A05 / A06 / A07 / A11 / A16 on the mock adapter:
 * double-click send, Stop losing to a commit, late frames from a retired run, a stale head,
 * a friend reset elsewhere, leaving mid-stream, expired sign-in; reading position / draft /
 * selection across side panel, profile dialog and reload; game start receipt lost, a missing
 * game, and a failed table-chat line.
 */
import {expect, test} from '@playwright/test'
import type {Page} from '@playwright/test'
import {shot, signUp, writeJSON} from './helpers'

const composer = (page: Page) => page.locator('.ew-chat-main textarea')
const committed = (page: Page, text: string) => page.locator('.ew-msg.is-player:not(.is-provisional) .ew-msg-bubble', {hasText: text})
const idle = (page: Page) => expect(page.locator('.ew-chat-main .ew-send.is-stop')).toHaveCount(0, {timeout: 20_000})
async function scenario(page: Page, on: Record<string, true>) {
  await page.evaluate(v => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify(v)), on)
  await page.reload()
  await expect(composer(page)).toBeVisible()
}
async function befriend(page: Page, id: string, email: string) {
  await page.goto(`/#/characters/${id}?v=1`)
  await page.getByRole('button', {name: '加为好友'}).first().click()
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await signUp(page, email)
  await page.getByRole('button', {name: '确认加为好友'}).click()
  await expect(page).toHaveURL(/#\/friends\/fr_/)
  await expect(composer(page)).toBeVisible()
}
async function say(page: Page, text: string) {
  await composer(page).fill(text)
  await composer(page).press('Enter')
  await expect(committed(page, text)).toHaveCount(1, {timeout: 20_000})
  await idle(page)
}
const dbGames = (page: Page) => page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('everwith.mock.db.v1') ?? '{}').games ?? {}).length)

test('chat races: double-click once, Stop that loses to the commit, late old-run frames, stale head, reset elsewhere, leaving mid-stream, expired sign-in', async ({page}) => {
  test.setTimeout(180_000)
  const report: Record<string, unknown> = {}
  await befriend(page, 'official-arthur', 'e2e-edge@example.com')
  const chatUrl = page.url()

  // A05 double-click: one operation; the second click does not hit the Stop that replaced Send.
  await composer(page).fill('只发一次')
  await page.locator('.ew-chat-main .ew-send').dblclick()
  await expect(committed(page, '只发一次')).toHaveCount(1, {timeout: 20_000})
  await idle(page)
  await page.waitForTimeout(800)
  expect(await committed(page, '只发一次').count()).toBe(1)
  await expect(page.getByText('已停止。半段回复没有进入记录')).toHaveCount(0)
  report.doubleClick = {committedTurns: 1, stopped: false}

  // A18 Cancel → neutral: a real Stop drops the provisional reply and the face returns to neutral.
  await composer(page).fill('给我讲个开心的故事吧！')
  await composer(page).press('Enter')
  await expect(page.locator('.ew-chat-main .ew-msg.is-character.is-provisional').last()).toBeVisible({timeout: 10_000})
  await page.locator('.ew-chat-main .ew-send.is-stop').click()
  await expect(page.getByText('已停止。半段回复没有进入记录，原输入已放回输入框。')).toBeVisible({timeout: 15_000})
  await expect(page.locator('.ew-chat-stage-meta .ew-chip').first()).toHaveText('平静')
  await page.waitForTimeout(600)
  report.cancelNeutral = {chip: '平静', runtimeExpressions: await page.evaluate(() => (window as unknown as {__everwithLive2D?: {snapshot(): {runtimes: {expression: string | null}[]}}}).__everwithLive2D?.snapshot().runtimes.map(r => r.expression) ?? null)}
  await shot(page, 'chat-stop-neutral')

  // A05 Stop vs commit: the commit wins and is reported as such.
  await scenario(page, {'chat.commit_before_cancel': true})
  await composer(page).fill('停止和提交赛跑')
  await composer(page).press('Enter')
  await page.locator('.ew-chat-main .ew-send.is-stop').click()
  await expect(page.getByText('这条回复在停止前已经完成，结果已保留（没有被停止）。')).toBeVisible({timeout: 15_000})
  await expect(committed(page, '停止和提交赛跑')).toHaveCount(1)
  await shot(page, 'chat-commit-won')
  report.commitBeforeCancel = 'commit_won notice, reply kept'

  // A06 late frames from the retired run are rejected (run_epoch / seq check).
  await scenario(page, {'chat.late_old_stream': true})
  await composer(page).fill('旧帧晚到')
  await composer(page).press('Enter')
  await page.getByRole('button', {name: '重试同一条'}).click({timeout: 20_000})
  await expect(committed(page, '旧帧晚到')).toHaveCount(1, {timeout: 20_000})
  await expect(page.getByText(/已拒绝 \d+ 个旧 run 的晚到帧/)).toBeVisible()
  await expect(page.getByText('（这是旧 run 的晚到片段，不应显示）')).toHaveCount(0)
  await shot(page, 'chat-late-frames-rejected')
  report.lateOldRun = await page.getByText(/已拒绝 \d+ 个旧 run 的晚到帧/).innerText()

  // A06 stale head (another window committed first): latest loaded, draft kept, nothing resent.
  await scenario(page, {'chat.stale_head': true})
  await composer(page).fill('我以为我是最新的')
  await composer(page).press('Enter')
  await expect(page.getByText('会话在别处有了新内容。已读取最新版本，你的草稿保留在输入框，没有自动重发。')).toBeVisible({timeout: 15_000})
  await expect(page.getByText('（另一窗口发送的消息）')).toBeVisible()
  await expect(composer(page)).toHaveValue('我以为我是最新的')
  await page.waitForTimeout(1500)
  await expect(committed(page, '我以为我是最新的')).toHaveCount(0)
  await shot(page, 'chat-stale-head')
  report.staleHead = {draftKept: true, autoResent: false}

  // A06 leaving mid-stream: the unmounted view writes nothing; coming back shows one committed turn.
  await composer(page).fill('离开再回来')
  await composer(page).press('Enter')
  await expect(page.locator('.ew-chat-main .ew-send.is-stop')).toBeVisible()
  await page.goto('/#/discover')
  await page.waitForTimeout(4500)
  await page.goto(chatUrl)
  await expect(committed(page, '离开再回来')).toHaveCount(1, {timeout: 20_000})
  await idle(page)
  await expect(composer(page)).toHaveValue('') // the sent text is not resurrected as an old draft
  report.leaveMidStream = {committedTurns: await committed(page, '离开再回来').count()}

  // A05 expired sign-in on send: the text comes back, nothing is recorded. (Switched on in
  // the mock panel, not by reloading — the reload's own requests would consume it first.)
  await page.getByTestId('mock-panel-open').click()
  await page.getByLabel(/下一次受保护请求：登录过期 401/).check()
  await page.keyboard.press('Escape')
  await composer(page).fill('登录过期时的一句')
  await composer(page).press('Enter')
  await expect(page.getByText('登录已过期。草稿已保留，重新登录后可以继续。')).toBeVisible({timeout: 15_000})
  await expect(composer(page)).toHaveValue('登录过期时的一句')
  await expect(committed(page, '登录过期时的一句')).toHaveCount(0)
  await shot(page, 'chat-auth-expired')

  // A06 friend reset elsewhere: epoch changes, the old conversation turns read-only.
  await scenario(page, {'chat.friend_reset_elsewhere': true})
  await composer(page).fill('重置后的消息')
  await composer(page).press('Enter')
  await expect(page.getByText('这位好友的状态在别处发生了变化（例如重置）。旧会话已变为只读，请重新打开。')).toBeVisible({timeout: 15_000})
  await shot(page, 'chat-epoch-changed')
  await page.getByRole('button', {name: '重试', exact: true}).click()
  await expect(composer(page)).toBeEnabled({timeout: 15_000})
  await expect(committed(page, '只发一次')).toHaveCount(0) // new epoch → fresh conversation
  if (!(await page.getByText('较早的会话').isVisible())) await page.getByRole('button', {name: '工具'}).click()
  await expect(page.getByRole('button', {name: /epoch 1/})).toBeVisible()
  await page.getByRole('button', {name: /epoch 1/}).click()
  await expect(page.locator('dialog[open]')).toContainText('只发一次')
  await shot(page, 'chat-old-epoch-read-only')
  await page.keyboard.press('Escape')
  report.epochChanged = {oldConversationReadOnly: true}
  writeJSON('chat-races', report)
})

test('reading old messages is not pulled down; reading position, draft and selection survive side panel, profile and reload', async ({browser}) => {
  test.setTimeout(180_000)
  const ctx = await browser.newContext({viewport: {width: 1280, height: 640}, locale: 'zh-CN'})
  const page = await ctx.newPage()
  await befriend(page, 'official-iris', 'e2e-scroll@example.com')
  const box = page.locator('.ew-chat-main .ew-transcript')
  for (let i = 1; i <= 8; i++) {
    await say(page, `第 ${i} 句`)
    if (await box.evaluate(e => e.scrollHeight - e.clientHeight > 600)) break
  }
  // A reply is streaming; the reader scrolls up to old messages meanwhile.
  await composer(page).fill('新的一句')
  await composer(page).press('Enter')
  await expect(page.locator('.ew-chat-main .ew-send.is-stop')).toBeVisible()
  await box.evaluate(e => { e.scrollTop = 0; e.dispatchEvent(new Event('scroll')) })
  const samples: number[] = []
  for (let i = 0; i < 24; i++) {
    samples.push(await box.evaluate(e => e.scrollTop))
    if (await committed(page, '新的一句').count() && !(await page.locator('.ew-chat-main .ew-send.is-stop').count())) break
    await page.waitForTimeout(250)
  }
  await expect(committed(page, '新的一句')).toHaveCount(1, {timeout: 20_000})
  samples.push(await box.evaluate(e => e.scrollTop))
  expect(Math.max(...samples)).toBeLessThanOrEqual(2)
  await expect(page.locator('.ew-new-pill')).toBeVisible()
  await shot(page, 'chat-reading-old-new-pill')

  // Read a little further down (second turn aligned to the top), then keep a draft with a selection.
  await box.evaluate(e => {
    const turn = e.querySelectorAll<HTMLElement>('.ew-turn')[1]
    e.scrollTop += turn.getBoundingClientRect().top - e.getBoundingClientRect().top
    e.dispatchEvent(new Event('scroll'))
  })
  await page.waitForTimeout(200)
  const anchor = () => box.evaluate(e => {
    const items = Array.from(e.querySelectorAll<HTMLElement>('[data-anchor]'))
    const first = items.find(el => el.offsetTop + el.offsetHeight > e.scrollTop)
    return first?.dataset.anchor ?? null
  })
  const a0 = await anchor()
  await composer(page).fill('草稿与选区')
  await composer(page).press('End')
  await composer(page).press('Shift+ArrowLeft')
  await composer(page).press('Shift+ArrowLeft')
  const sel = () => composer(page).evaluate(e => [(e as HTMLTextAreaElement).selectionStart, (e as HTMLTextAreaElement).selectionEnd])
  expect(await sel()).toEqual([3, 5])
  // Side panel open/close changes the transcript width: same anchor.
  await page.getByRole('button', {name: '工具'}).click()
  await page.waitForTimeout(300)
  const a1 = await anchor()
  await page.getByRole('button', {name: '资料'}).click()
  await expect(page.locator('dialog[open]')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', {name: '工具'}).click()
  await page.waitForTimeout(300)
  const a2 = await anchor()
  await expect(composer(page)).toHaveValue('草稿与选区')
  await page.waitForTimeout(300)
  await page.reload()
  await expect(composer(page)).toHaveValue('草稿与选区')
  await page.waitForTimeout(400)
  const a3 = await anchor()
  const selAfter = await sel()
  const atEnd = await box.evaluate(e => e.scrollHeight - e.scrollTop - e.clientHeight < 40)
  await shot(page, 'chat-reading-position-after-reload')
  writeJSON('chat-reading-position', {scrollTopWhileStreaming: samples, anchors: {beforePanels: a0, panelOpen: a1, afterProfileAndClose: a2, afterReload: a3}, selectionAfterReload: selAfter, atEndAfterReload: atEnd})
  expect([a1, a2, a3]).toEqual([a0, a0, a0])
  expect(selAfter).toEqual([3, 5])
  expect(atEnd).toBe(false)
  await ctx.close()
})

test('games: a lost start receipt finds the one game; a missing game is not replaced; a failed table line leaves the board untouched', async ({page}) => {
  await page.goto('/#/games/vegas/prepare')
  await page.evaluate(() => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify({'game.unknown_start': true})))
  await page.reload()
  const before = await dbGames(page)
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//, {timeout: 20_000})
  const after = await dbGames(page)
  expect(after).toBe(before + 1)
  const gameUrl = page.url()

  // A missing game: an error with Retry / Recent — no substitute table is created.
  await page.goto('/#/play/game/game_does_not_exist')
  await expect(page.getByText('找不到这项内容，可能已被删除或无权访问。')).toBeVisible()
  await page.getByRole('button', {name: '重试', exact: true}).click()
  await expect(page.getByText('找不到这项内容，可能已被删除或无权访问。')).toBeVisible()
  expect(await dbGames(page)).toBe(after)
  await shot(page, 'game-missing-no-substitute')

  // Table chat line fails: the committed board and its revision do not move.
  await page.goto(gameUrl)
  await expect(page.getByTestId('table-status')).toBeVisible()
  const pause = page.getByRole('button', {name: '暂停 AI'})
  if (await pause.isVisible()) await pause.click()
  await page.waitForTimeout(1200)
  const rev0 = Number(await page.locator('.ew-table-shell').getAttribute('data-revision'))
  await page.evaluate(() => sessionStorage.setItem('everwith.mock.scenarios', JSON.stringify({'game.text_failed': true})))
  await page.reload()
  await expect(page.getByTestId('table-status')).toBeVisible()
  const pause2 = page.getByRole('button', {name: '暂停 AI'})
  if (await pause2.isVisible()) await pause2.click()
  await page.waitForTimeout(1200)
  const rev1 = Number(await page.locator('.ew-table-shell').getAttribute('data-revision'))
  const box = page.locator('.ew-table-chat textarea')
  await box.fill('这把你会怎么下？')
  await box.press('Enter')
  await expect(page.getByText('这次没能生成台词；牌局已提交的内容不受影响。')).toBeVisible({timeout: 10_000})
  const rev2 = Number(await page.locator('.ew-table-shell').getAttribute('data-revision'))
  await shot(page, 'game-table-line-failed')
  writeJSON('game-edge', {gamesBefore: before, gamesAfterLostReceipt: after, missingGameCreatedNothing: true, revisionBeforeChat: rev1, revisionAfterFailedLine: rev2, rev0})
  expect(rev2).toBe(rev1)
})

test('table stays operable: fullscreen refused, Esc twice after a dialog, immersive on', async ({page}) => {
  await page.goto('/#/games/vegas/prepare')
  await page.getByRole('button', {name: '2 人', exact: true}).click()
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  await expect(page.getByTestId('table-status')).toBeVisible()
  const id = page.url()
  // The browser refuses fullscreen: a readable notice, same layout, same table.
  await page.evaluate(() => { HTMLElement.prototype.requestFullscreen = function () { return Promise.reject(new DOMException('denied', 'NotAllowedError')) } })
  await page.getByRole('button', {name: '全屏', exact: true}).click()
  await expect(page.getByText('浏览器拒绝了全屏，已保留当前布局。')).toBeVisible()
  expect(await page.evaluate(() => !!document.fullscreenElement)).toBe(false)
  // A modal, then Esc twice: one layer per Esc, focus back on the trigger, nothing else closes.
  const rules = page.getByRole('button', {name: '规则', exact: true})
  await rules.click()
  await expect(page.locator('dialog[open]')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  await expect(page.locator('dialog[open]')).toHaveCount(0)
  await expect(rules).toBeFocused()
  await page.getByRole('button', {name: '沉浸', exact: true}).click()
  await page.keyboard.press('Escape')
  // The board still takes a move on the same session.
  await page.waitForFunction(() => !!document.querySelector('[data-testid="royale-roll"]:not([disabled])'), null, {timeout: 30_000})
  const rev = Number(await page.locator('.ew-table-shell').getAttribute('data-revision'))
  await page.getByTestId('royale-roll').click()
  await page.waitForFunction(r => Number(document.querySelector<HTMLElement>('.ew-table-shell')?.dataset.revision) > r, rev, {timeout: 10_000})
  expect(page.url()).toBe(id)
  await shot(page, 'game-operable-after-refused-fullscreen')
  writeJSON('game-fullscreen-refused', {sameSession: true, revisionBefore: rev, moved: true})
})
