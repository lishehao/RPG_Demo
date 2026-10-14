/**
 * @long Three complete games through the NEW UI at normal product speed, recorded on video.
 * The player seat is driven only by clicking visible controls; NPC seats are the mock's
 * fixed-strategy “rule-simulated companions”. Each run also checks pause / sidebar /
 * immersive / fullscreen / reload continuity on the same session id.
 */
import {expect, test} from '@playwright/test'
import type {Page} from '@playwright/test'
import {renameSync} from 'node:fs'
import {act, evidencePath, gameRecord, shot, tableSnap, writeJSON} from './helpers'

test.describe.configure({mode: 'serial'})
// actionTimeout: a control that never becomes clickable fails the run with a precise line instead of hanging.
test.use({video: {mode: 'on', size: {width: 1280, height: 800}}, viewport: {width: 1280, height: 800}, actionTimeout: 20_000})

type Log = {checks: Record<string, unknown>; myActions: number; shots: string[]}

/** Resume AI seats. The button keeps its id until the hold(false) request returns, so never block on it:
 *  click if it is still there, then wait until the toolbar shows “暂停 AI” again. */
async function resumeAI(page: Page) {
  await page.getByTestId('continue-ai').click({timeout: 3000}).catch(() => undefined)
  await expect(page.getByTestId('continue-ai')).toHaveCount(0, {timeout: 8000}).catch(() => undefined)
}

async function startGame(page: Page, gameId: string, players: number) {
  await page.goto(`/#/games/${gameId}/prepare`)
  await page.getByRole('button', {name: `${players} 人`, exact: true}).click()
  await expect(page.locator('.ew-seat-row')).toHaveCount(players)
  await shot(page, `game-${gameId}-prepare`)
  await page.locator('.ew-start-btn').click()
  await page.waitForURL(/#\/play\/game\//)
  await expect(page.getByTestId('table-status')).toBeVisible()
  return decodeURIComponent(page.url().split('/play/game/')[1])
}

/** Same session, same mounted board: pause, sidebar, immersive, fullscreen, reload. */
async function continuityChecks(page: Page, game: string, log: Log) {
  const id = (await tableSnap(page)).url
  // Pause AI (if running) and confirm nothing advances.
  const pause = page.getByRole('button', {name: '暂停 AI'})
  if (await pause.isVisible()) await pause.click()
  const r0 = (await tableSnap(page)).rev
  await page.waitForTimeout(2500)
  const r1 = (await tableSnap(page)).rev
  log.checks.pauseHolds = {before: r0, after2500ms: r1, ok: r1 === r0}
  await page.evaluate(() => { (document.querySelector('.gb-board') as unknown as {__e2e?: string}).__e2e = 'mounted-once' })
  const mark = () => page.evaluate(() => (document.querySelector('.gb-board') as unknown as {__e2e?: string} | null)?.__e2e ?? null)
  await page.getByRole('button', {name: '人物与桌聊'}).click()
  await shot(page, `game-${game}-rail-closed`)
  await page.getByRole('button', {name: '人物与桌聊'}).click()
  await page.getByRole('button', {name: '沉浸', exact: true}).click()
  await shot(page, `game-${game}-immersive`)
  await page.getByRole('button', {name: '退出沉浸'}).click()
  await page.getByRole('button', {name: '全屏', exact: true}).click()
  await page.waitForTimeout(600)
  const fs = await page.evaluate(() => !!document.fullscreenElement)
  if (fs) { await shot(page, `game-${game}-fullscreen`); await page.evaluate(() => document.exitFullscreen()); await page.waitForTimeout(400) }
  const s2 = await tableSnap(page)
  log.checks.sameBoardAfterToggles = {mark: await mark(), sameUrl: s2.url === id, rev: s2.rev, revUnchangedWhilePaused: s2.rev === r0, fullscreenEntered: fs}
  expect(await mark()).toBe('mounted-once')
  expect(s2.url).toBe(id)
  // Resume, then leave by reloading: the in-flight step finishes, later steps pause.
  if (await page.getByTestId('continue-ai').isVisible()) await resumeAI(page)
  await page.waitForTimeout(900)
  const before = await tableSnap(page)
  await page.reload()
  await expect(page.getByTestId('table-status')).toBeVisible()
  const after = await tableSnap(page)
  const banner = await page.getByText('离开期间后续行动已暂停').isVisible().catch(() => false)
  log.checks.reload = {urlBefore: before.url, urlAfter: after.url, revBefore: before.rev, revAfter: after.rev, leftPausedBanner: banner}
  expect(after.url).toBe(before.url)
  expect(after.rev).toBeGreaterThanOrEqual(before.rev)
  if (banner) { await shot(page, `game-${game}-reload-paused`); await resumeAI(page) }
}

async function finish(page: Page, game: string, id: string, log: Log, t0: number) {
  await expect(page.getByTestId('result')).toBeVisible()
  await page.waitForTimeout(1200)
  await shot(page, `game-${game}-result`)
  const rec = await gameRecord(page, id)
  // Locked result can still be chatted about; the score does not move.
  const box = page.locator('.ew-table-chat textarea')
  await box.fill('这一局打得不错')
  await box.press('Enter')
  await expect(page.locator('.ew-chat-line.is-me').last()).toContainText('这一局打得不错')
  const rec2 = await gameRecord(page, id)
  log.checks.chatAfterEndKeepsScore = JSON.stringify(rec2?.settlement?.scores) === JSON.stringify(rec?.settlement?.scores) && rec2?.revision === rec?.revision
  await shot(page, `game-${game}-result-chat`)
  writeJSON(`game-${game}`, {game, session: id, profile: rec?.profile, syntheticSeed: rec?.seed, finalRevision: rec?.revision, lifecycle: rec?.lifecycle,
    seats: rec?.seats, settlement: rec?.settlement, myActions: log.myActions, wallClockSeconds: Math.round((Date.now() - t0) / 1000), checks: log.checks,
    note: 'Normal product pacing (820 ms per NPC step). NPC seats = fixed-strategy mock; JEV not connected.'})
  expect(rec?.lifecycle).toBe('ended')
}

async function saveVideo(page: Page, name: string) {
  const video = page.video()
  await page.close()
  if (video) { const p = await video.path(); renameSync(p, evidencePath('videos', `${name}.webm`)) }
}

test('Royale · 4 players · three rounds to the final settlement @long', async ({page}) => {
  test.setTimeout(20 * 60_000)
  const id = await startGame(page, 'vegas', 4)
  const log: Log = {checks: {}, myActions: 0, shots: []}
  const t0 = Date.now()
  let passed = false, chose = 0, checked = false
  const rounds = new Set<string>()
  while (Date.now() - t0 < 18 * 60_000) {
    const s = await tableSnap(page)
    if (s.result) break
    const b = s.buttons
    if (!checked && s.rev > 25 && b.includes('royale-roll')) { checked = true; await continuityChecks(page, 'royale', log); continue }
    if (b.includes('royale-roll')) { await act(page, 'royale-roll'); log.myActions++; if (log.myActions === 1) { await page.waitForTimeout(300); await shot(page, 'game-royale-rolling') } continue }
    const face = b.find(x => x.startsWith('royale-face-'))
    if (face) {
      chose++
      if (!passed && chose === 2 && b.includes('royale-pass')) { passed = true; await page.getByTestId('royale-pass').click(); await shot(page, 'game-royale-pass-confirm'); await act(page, 'royale-confirm'); log.myActions++; continue }
      await page.getByTestId(face).click()
      if (chose === 1) await shot(page, 'game-royale-select-confirm')
      await act(page, 'royale-confirm'); log.myActions++; continue
    }
    if (b.includes('royale-payout')) { await act(page, 'royale-payout'); log.myActions++; continue }
    if (b.includes('royale-next')) { const r = await page.locator('.rb-board').getAttribute('data-round'); if (r && !rounds.has(r)) { rounds.add(r); await shot(page, `game-royale-round${r}-end`) } await act(page, 'royale-next'); log.myActions++; continue }
    if (b.includes('continue-ai')) { await resumeAI(page); continue }
    await page.waitForTimeout(250)
  }
  log.checks.passUsed = passed
  await finish(page, 'royale', id, log, t0)
  // Rematch keeps the same people and creates a NEW session; the old result stays.
  await page.getByRole('button', {name: '原桌再来一局'}).first().click()
  await page.waitForURL(u => !u.toString().includes(id))
  const fresh = decodeURIComponent(page.url().split('/play/game/')[1])
  const a = await gameRecord(page, id), b = await gameRecord(page, fresh)
  writeJSON('game-royale-rematch', {old: id, oldLifecycle: a?.lifecycle, oldScores: a?.settlement?.scores, fresh, freshSeats: b?.seats, sameNames: JSON.stringify(a?.seats.map(s => s.name)) === JSON.stringify(b?.seats.map(s => s.name))})
  expect(a?.lifecycle).toBe('ended')
  expect(b?.revision).toBe(1)
  await saveVideo(page, 'royale-full-game')
})

test('Splendor v2 · 4 players · 15 points and the round completed @long', async ({page}) => {
  test.setTimeout(20 * 60_000)
  const id = await startGame(page, 'gems', 4)
  const log: Log = {checks: {}, myActions: 0, shots: []}
  const t0 = Date.now()
  let turns = 0, reserved = false, checked = false
  const seen = new Set<string>()
  while (Date.now() - t0 < 18 * 60_000) {
    const s = await tableSnap(page)
    if (s.result) break
    if (s.current !== '0' || !s.buttons.some(x => x.startsWith('splendor-'))) {
      if (s.buttons.includes('continue-ai')) { await resumeAI(page); continue }
      if (!checked && s.rev > 30) { checked = true; await continuityChecks(page, 'splendor', log); continue }
      await page.waitForTimeout(250); continue
    }
    if (s.phase === 'return') {
      if (!seen.has('return')) { seen.add('return'); await shot(page, 'game-splendor-return-before') }
      // Plan exactly K returns from the counts shown on my own gem buttons.
      const prompt = await page.locator('.gb-prompt').innerText()
      let need = Number(prompt.match(/归还 (\d+) 枚|return (\d+)/)?.slice(1).find(Boolean) ?? 0)
      const options = await page.locator('[data-testid^="splendor-return-"]').evaluateAll(els => els.map(e => ({id: (e as HTMLElement).dataset.testid!, count: Number(e.querySelector('b')?.textContent ?? 0)})))
      for (const o of options) for (let k = 0; k < o.count && need > 0; k++, need--) await page.getByTestId(o.id).click()
      await shot(page, 'game-splendor-return-selected')
      await page.getByTestId('splendor-confirm').click(); log.myActions++
      await page.waitForFunction(() => document.querySelector<HTMLElement>('.gb-board')?.dataset.phase !== 'return' || document.querySelector<HTMLElement>('.gb-board')?.dataset.current !== '0', null, {timeout: 15_000})
      continue
    }
    if (s.phase === 'noble') {
      await page.locator('[data-testid^="splendor-noble-"]').first().click()
      await shot(page, 'game-splendor-noble-choice')
      await act(page, 'splendor-confirm'); log.myActions++; continue
    }
    turns++
    const legal = await page.getByTestId('splendor-legal').evaluate(e => ({buy: (e.dataset.buy ?? '').split(' ').filter(Boolean), take: (e.dataset.take ?? '').split(' ').filter(Boolean), reserve: (e.dataset.reserve ?? '').split(' ').filter(Boolean), blind: (e.dataset.blind ?? '').split(' ').filter(Boolean)}))
    if (legal.buy.length) {
      await page.getByTestId(`splendor-card-${legal.buy[0]}`).click()
      if (!seen.has('buy')) { seen.add('buy'); await shot(page, 'game-splendor-buy-preview') }
      await act(page, 'splendor-buy'); log.myActions++; continue
    }
    if (!reserved && turns === 3 && legal.reserve.length) {
      reserved = true
      await page.getByTestId(`splendor-card-${legal.reserve[0]}`).click()
      await shot(page, 'game-splendor-reserve-preview')
      await act(page, 'splendor-reserve'); log.myActions++; continue
    }
    if (legal.take.length) {
      const best = legal.take.reduce((a, b) => b.split('+').length > a.split('+').length ? b : a)
      for (const c of best.split('+')) await page.getByTestId(`splendor-bank-${c}`).click()
      if (!seen.has('take')) { seen.add('take'); await shot(page, 'game-splendor-take-selected') }
      await act(page, 'splendor-confirm'); log.myActions++; continue
    }
    if (legal.blind.length) { await page.getByTestId(`splendor-deck-${legal.blind[0]}`).click(); await act(page, 'splendor-confirm'); log.myActions++; continue }
    throw new Error('no legal action offered to seat 0')
  }
  log.checks.reserveUsed = reserved
  log.checks.returnPhaseSeen = seen.has('return')
  await finish(page, 'splendor', id, log, t0)
  await saveVideo(page, 'splendor-full-game')
})

test('CABO · 4 players · cumulative end above 100 @long', async ({page}) => {
  test.setTimeout(25 * 60_000)
  const id = await startGame(page, 'cabo', 4)
  const log: Log = {checks: {}, myActions: 0, shots: []}
  const t0 = Date.now()
  let called = false, checked = false
  const seen = new Set<string>()
  const cabo = () => page.getByTestId('cabo-state').evaluate(e => ({phase: e.dataset.phase!, current: e.dataset.current!, drawn: e.dataset.drawn ? Number(e.dataset.drawn) : null, ability: e.dataset.ability || null, totals: e.dataset.totals!, caller: e.dataset.caller}))
  while (Date.now() - t0 < 23 * 60_000) {
    const s = await tableSnap(page)
    if (s.result) break
    const b = s.buttons
    const c = await cabo()
    const round = Number(await page.locator('.cb-board').getAttribute('data-round'))
    if (process.env.E2E_DEBUG) console.log(`[cabo] r${s.rev} round ${round} phase ${c.phase} cur ${c.current} drawn ${c.drawn} ability ${c.ability} buttons ${b.join(',')}`)
    if (b.includes('cabo-next-round')) { if (!seen.has(`end${round}`)) { seen.add(`end${round}`); await shot(page, `game-cabo-round${round}-scores`) } await act(page, 'cabo-next-round'); log.myActions++; continue }
    if (!b.some(x => x.startsWith('cabo-'))) {
      if (b.includes('continue-ai')) { await resumeAI(page); continue }
      if (!checked && s.rev > 40) { checked = true; await continuityChecks(page, 'cabo', log); continue }
      await page.waitForTimeout(250); continue
    }
    if (c.phase === 'setup') {
      await page.getByTestId('cabo-own-0').click(); await page.getByTestId('cabo-own-1').click()
      if (!seen.has('setup')) { seen.add('setup'); await shot(page, 'game-cabo-setup-select') }
      await act(page, 'cabo-peek-confirm'); log.myActions++; continue
    }
    if (c.phase === 'reveal') {
      if (!seen.has(`reveal${round}`)) { seen.add(`reveal${round}`); await shot(page, `game-cabo-private-reveal-r${round}`) }
      await act(page, 'cabo-ack'); log.myActions++
      if (!seen.has('after-ack')) { seen.add('after-ack'); await shot(page, 'game-cabo-after-ack-known-badges') }
      continue
    }
    if (c.phase === 'turn') {
      if (!called && round >= 2 && c.caller === '' && b.includes('cabo-call')) {
        called = true
        await page.getByTestId('cabo-call').click(); await shot(page, 'game-cabo-call-confirm')
        await act(page, 'cabo-call-confirm'); log.myActions++; continue
      }
      const top = await page.getByTestId('cabo-discard-top').getAttribute('aria-label', {timeout: 2000}).catch(() => '')
      const topValue = Number((top ?? '').match(/[：:]\s*(\d+)/)?.[1] ?? 99)
      if (topValue <= 2 && b.includes('cabo-draw-discard')) { await act(page, 'cabo-draw-discard'); log.myActions++; continue }
      await act(page, 'cabo-draw-deck'); log.myActions++; continue
    }
    if (c.phase === 'exchange') { await page.getByTestId('cabo-own-3').or(page.getByTestId('cabo-own-0')).first().click(); await act(page, 'cabo-exchange'); log.myActions++; continue }
    if (c.phase === 'drawn') {
      if (!seen.has('drawn')) { seen.add('drawn'); await shot(page, 'game-cabo-drawn') }
      if (c.drawn !== null && c.drawn <= 4) { await page.locator('[data-testid^="cabo-own-"]').last().click(); await act(page, 'cabo-exchange'); log.myActions++; continue }
      if (b.includes('cabo-discard-ability')) { await act(page, 'cabo-discard-ability'); log.myActions++; continue }
      await act(page, 'cabo-discard'); log.myActions++; continue
    }
    if (c.phase === 'ability') {
      if (!seen.has(`ability-${c.ability}`)) { seen.add(`ability-${c.ability}`) }
      if (c.ability === 'peek') await page.locator('button[data-testid^="cabo-own-"]').first().click()
      else if (c.ability === 'spy') await page.locator('button[data-testid^="cabo-seat"]').first().click()
      else { await page.locator('button[data-testid^="cabo-own-"]').first().click(); await page.locator('button[data-testid^="cabo-seat"]').first().click() }
      if (await page.getByTestId('cabo-ability-confirm').isEnabled({timeout: 3000}).catch(() => false)) { await shot(page, `game-cabo-ability-${c.ability}`); await act(page, 'cabo-ability-confirm') } else await act(page, 'cabo-ability-cancel')
      log.myActions++; continue
    }
    await page.waitForTimeout(250)
  }
  log.checks.cabocalled = called
  log.checks.abilitiesSeen = [...seen].filter(x => x.startsWith('ability-'))
  await finish(page, 'cabo', id, log, t0)
  const totals = (await gameRecord(page, id))?.settlement?.scores ?? []
  expect(Math.max(...totals)).toBeGreaterThan(100)
  await saveVideo(page, 'cabo-full-game')
})
