import {expect} from '@playwright/test'
import type {Page} from '@playwright/test'
import {mkdirSync, writeFileSync} from 'node:fs'
import {dirname, resolve} from 'node:path'

export const EVIDENCE = resolve(process.cwd(), 'evidence')
export function evidencePath(...parts: string[]) { const p = resolve(EVIDENCE, ...parts); mkdirSync(dirname(p), {recursive: true}); return p }
/** Wait until visible images and fonts are ready (bounded), so screenshots show real art. */
export async function settle(page: Page, ms = 6000) {
  await Promise.race([page.waitForLoadState('networkidle').catch(() => undefined), page.waitForTimeout(ms)])
  // Loading skeletons gone (the page shows content, not its loading state).
  await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, {timeout: ms}).catch(() => undefined)
  // Visible images loaded AND decoded (lazy + decoding="async" can be "complete" before the first paint).
  await page.waitForFunction(() => Array.from(document.images).filter(i => { const r = i.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.width > 0 }).every(i => i.complete), null, {timeout: ms}).catch(() => undefined)
  await page.evaluate(async () => {
    const visible = Array.from(document.images).filter(i => { const r = i.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.width > 0 })
    await Promise.race([Promise.all(visible.map(i => i.decode().catch(() => undefined))), new Promise(r => setTimeout(r, 3000))])
    await document.fonts.ready
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
  }).catch(() => undefined)
}
export async function shot(page: Page, name: string, fullPage = false) { await settle(page, 4000); await page.screenshot({path: evidencePath('screenshots', `${name}.png`), fullPage}) }
export function writeJSON(name: string, data: unknown) { writeFileSync(evidencePath('reports', `${name}.json`), JSON.stringify(data, null, 2)) }

/** Atomic read of the table state (one evaluate; avoids mixing two revisions). */
export type TableSnap = {rev: number; lifecycle: string; phase: string; current: string; buttons: string[]; result: boolean; url: string}
export async function tableSnap(page: Page): Promise<TableSnap> {
  return page.evaluate(() => {
    const shell = document.querySelector<HTMLElement>('.ew-table-shell')
    const board = document.querySelector<HTMLElement>('.gb-board')
    const buttons = [...document.querySelectorAll<HTMLButtonElement>('button[data-testid]')].filter(b => !b.disabled && b.offsetParent !== null).map(b => b.dataset.testid!)
    return {rev: Number(shell?.dataset.revision ?? -1), lifecycle: shell?.dataset.lifecycle ?? '', phase: board?.dataset.phase ?? '', current: board?.dataset.current ?? '',
      buttons, result: !!document.querySelector('[data-testid="result"]'), url: location.hash}
  })
}
/** Click, then wait until the authoritative revision moves (or a short timeout). */
export async function act(page: Page, testId: string) {
  const before = (await tableSnap(page)).rev
  await page.getByTestId(testId).first().click()
  await page.waitForFunction(r => Number(document.querySelector<HTMLElement>('.ew-table-shell')?.dataset.revision ?? -1) !== r, before, {timeout: 10_000}).catch(() => undefined)
}
export async function signUp(page: Page, email: string, password = 'password123') {
  const dialog = page.locator('dialog[open]')
  await expect(dialog).toBeVisible()
  await dialog.getByText(/没有账号？注册|No account\? Create one/).click()
  await dialog.locator('input[type=email]').fill(email)
  await dialog.locator('input[type=password]').fill(password)
  await dialog.locator('button[type=submit]').click()
  // The sign-in layer closes; the interrupted step (e.g. naming) may reopen as its own dialog.
  await expect(page.locator('dialog[open] input[type=email]')).toHaveCount(0)
}
export type GameRecord = {seed: number; profile: string; revision: number; lifecycle: string; settlement: {scores: number[]; winners: number[]} | null; seats: {seat: number; kind: string; name: string}[]}
/** Reads the synthetic seed of a game from the local mock DB (evidence only). */
export async function gameRecord(page: Page, id: string): Promise<GameRecord | null> {
  return page.evaluate(gid => {
    const db = JSON.parse(localStorage.getItem('everwith.mock.db.v1') ?? '{}')
    const g = db.games?.[gid]
    return g ? {seed: g.seed, profile: g.profile, revision: g.revision, lifecycle: g.lifecycle, settlement: g.settlement, seats: g.seats.map((s: {seat: number; kind: string; name: string}) => ({seat: s.seat, kind: s.kind, name: s.name}))} : null
  }, id)
}
