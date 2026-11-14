/**
 * Pure-engine complete games through the SAME module layer the mock authority uses,
 * plus projection checks: what seat 0 receives never carries other seats' hidden facts.
 * Synthetic seeds only; no UI, no network. (UI full games are in e2e/games.spec.ts.)
 */
import {describe, expect, it} from 'vitest'
import {createHash} from 'node:crypto'
import {readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import * as royale from '../src/games/engines/royale/engine'
import * as splendor from '../src/games/engines/splendor/splendor/rules'
import * as cabo from '../src/games/engines/cabo/engine'
import {GAME_MODULES} from '../src/mock/games/modules'
import type {GameId} from '../src/mock/games/modules'

const ROOT = resolve(__dirname, '..')

function playOut(id: GameId, players: number, seed: number, profile?: string, inspect?: (state: unknown) => void) {
  const m = GAME_MODULES[id]
  let state = m.create(players, seed, profile)
  let steps = 0
  while (!m.ended(state) && steps < 6000) {
    const actor = m.actor(state)
    const seat = actor === 'any' ? 0 : actor
    const action = m.ai(state, seat, seed + steps)
    state = m.apply(state, seat, action)
    m.check(state)
    inspect?.(state)
    steps++
  }
  return {state, steps, settle: m.settle(state)}
}

describe('frozen engine copies', () => {
  it('are byte-identical to the handoff (sha256 from PROVENANCE.json)', () => {
    const prov = JSON.parse(readFileSync(resolve(ROOT, 'src/games/engines/PROVENANCE.json'), 'utf8')) as {files: {file: string; sha256: string}[]}
    expect(prov.files.length).toBeGreaterThanOrEqual(9)
    for (const f of prov.files) expect(createHash('sha256').update(readFileSync(resolve(ROOT, 'src/games/engines', f.file))).digest('hex'), f.file).toBe(f.sha256)
  })
})

describe('Royale (las-vegas-royale-broadway-zh-intro-v1)', () => {
  for (const players of [2, 3, 4, 5]) it(`${players} players play three full rounds to a settled result`, () => {
    const {state, settle} = playOut('vegas', players, 917 + players, undefined, s => {
      const v = GAME_MODULES.vegas.view(s, 0) as Record<string, unknown> & {players: {id: number; earnings: unknown[]; cash: number | null}[]}
      expect('rng' in v).toBe(false)
      expect('deck' in v).toBe(false)
      if ((s as royale.State).phase !== 'ended') for (const p of v.players.filter(p => p.id !== 0)) { expect(p.cash).toBeNull(); expect(p.earnings.every(e => e === null)).toBe(true) }
    })
    const s = state as royale.State
    expect(s.phase).toBe('ended')
    expect(s.round).toBe(3)
    expect(s.roundHistory).toHaveLength(3)
    expect(s.roundHistory.every(r => r.length === 6)).toBe(true)
    expect(settle.winners.length).toBeGreaterThan(0)
    expect(settle.scores).toEqual(s.players.map(royale.wealth))
  })
})

describe('Splendor', () => {
  for (const players of [2, 3, 4]) it(`v2 · ${players} players reach 15 and finish the round`, () => {
    let blindSeen = false
    const {state, settle} = playOut('gems', players, 31 + players, 'splendor-base-2024-v2', st => {
      const s = st as splendor.SplendorState
      const v = GAME_MODULES.gems.view(s, 0) as {decks: Record<string, unknown>; players: {reserved: {card: string | null; hidden: boolean}[]}[]; seed?: unknown}
      expect(Object.values(v.decks).every(x => typeof x === 'number')).toBe(true)
      expect('seed' in v).toBe(false)
      // Other seats' blind reserves never reach seat 0 as card ids.
      const blind = new Set<string>()
      s.events.forEach(e => { if (e.type === 'reserve' && e.blind === true) blindSeen = true })
      s.players.forEach((p, i) => { if (i === 0) return; p.reserved.forEach((id, k) => { if (id && v.players[i].reserved[k].hidden) blind.add(id) }) })
      for (const id of blind) expect(JSON.stringify(v.players.slice(1))).not.toContain(`"${id}"`)
    })
    const s = state as splendor.SplendorState
    expect(s.ended).toBe(true)
    expect(Math.max(...s.players.map(splendor.score))).toBeGreaterThanOrEqual(15)
    expect(s.current).toBe(players - 1) // the round was completed (last seat moved)
    expect(settle.scores).toEqual(s.players.map(splendor.score))
    void blindSeen
  })
  it('legacy v1 saves keep their own rules and still finish', () => {
    const {state} = playOut('gems', 3, 7, 'splendor-legacy-v1')
    const s = state as splendor.SplendorState
    expect(s.version).toBe(1)
    expect(splendor.rulesProfileFor(s)).toBe('splendor-legacy-v1')
    expect(s.ended).toBe(true)
  })
  it('refuses unknown rule profiles instead of upgrading', () => {
    expect(() => splendor.createGame({rulesProfile: 'splendor-unknown', players: 2, seed: 'x'})).toThrow()
    expect(() => splendor.rulesProfileFor({version: 2, rulesProfile: 'other'})).toThrow()
  })
})

describe('CABO (cabo-shareful-2025-en-slice-provisional)', () => {
  for (const players of [2, 3, 4, 5]) it(`${players} players play to a cumulative end (>100)`, () => {
    const {state, settle} = playOut('cabo', players, 711 + players, undefined, st => {
      const s = st as cabo.CaboState
      const o = GAME_MODULES.cabo.view(s, 0) as cabo.CaboObservation
      expect(o.observer).toBe(0)
      expect(o.deck.every(x => x === null)).toBe(true)
      expect('truth' in (o as object)).toBe(false)
      const inRound = !['roundEnd', 'ended'].includes(s.phase)
      if (inRound) for (const p of o.players) for (const c of p.cards) if (!s.up[c.id]) expect(c.value).toBeNull()
      // Knowledge only lists cards seat 0 legitimately knows.
      for (const id of Object.keys(o.knowledge)) expect(s.knowledge[0][id]).toBe(s.truth[id])
      if (s.drawn && s.current !== 0 && s.drawnFrom === 'deck') expect(o.drawn?.value).toBeNull()
      if (o.privateReveal) expect(o.privateReveal.player).toBe(0)
    })
    const s = state as cabo.CaboState
    expect(s.ended).toBe(true)
    expect(s.players.some(p => p.total > 100)).toBe(true)
    expect(settle.winners.every(w => s.players[w].total === Math.min(...s.players.map(p => p.total)))).toBe(true)
  })
  it('marks the component profile and ability numbers as provisional', () => {
    expect(cabo.ability(7)).toBe('peek'); expect(cabo.ability(9)).toBe('spy'); expect(cabo.ability(11)).toBe('swap'); expect(cabo.ability(6)).toBeNull()
    expect(cabo.DECK).toHaveLength(52)
  })
})
