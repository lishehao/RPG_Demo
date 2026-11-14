/**
 * Targeted CABO scoring branches on the frozen engine (provisional component profile):
 * shooting the moon, failed CABO +5, caller tie wins, exactly 100 → 50 once, >100 ends.
 * States are real engine states with card VALUES re-assigned by swapping (the 52-value
 * multiset is preserved, so the engine's own conservation checks still pass).
 */
import {describe, expect, it} from 'vitest'
import * as cabo from '../src/games/engines/cabo/engine'

/** Re-deal VALUES: the given hands get exact values; every other card gets the rest of the 52-value multiset. */
function assignHands(s: cabo.CaboState, hands: Record<number, number[]>) {
  const pool = [...cabo.DECK]
  const handIds = new Set<string>()
  for (const [p, values] of Object.entries(hands)) values.forEach((v, i) => {
    const k = pool.indexOf(v); expect(k, `value ${v} exists`).toBeGreaterThanOrEqual(0); pool.splice(k, 1)
    const id = s.players[Number(p)].cards[i]; s.truth[id] = v; handIds.add(id)
  })
  Object.keys(s.truth).filter(id => !handIds.has(id)).forEach((id, i) => { s.truth[id] = pool[i] })
}
const fresh = (players = 3) => {
  let s = cabo.create({players, seed: 4242})
  // Opening peeks for everyone (fixed strategy), so the state is a real “turn” state.
  for (let i = 0; i < 50 && s.phase !== 'turn'; i++) s = cabo.act(s, s.current, cabo.decide(cabo.observe(s, s.current), 'medium', {seed: i + 1}))
  return structuredClone(s)
}

describe('CABO scoring branches (frozen engine)', () => {
  it('shooting the moon: 12/12/13/13 scores 0 for the shooter and +50 for everyone else', () => {
    const s = fresh()
    assignHands(s, {1: [12, 12, 13, 13], 0: [0, 1, 2, 3], 2: [4, 4, 5, 5]})
    cabo.assertState(s)
    const rows = cabo.roundScores(s)
    expect(rows[1]).toMatchObject({gain: 0, reason: 'shootingTheMoon'})
    expect(rows[0]).toMatchObject({gain: 50, reason: 'shootingTheMoon'})
    expect(rows[2]).toMatchObject({gain: 50, reason: 'shootingTheMoon'})
  })
  it('a failed CABO adds 5; a caller tied for lowest wins alone', () => {
    const s = fresh()
    assignHands(s, {0: [6, 6, 7, 7], 1: [1, 1, 2, 2], 2: [3, 3, 4, 4]})
    s.caller = 0
    let rows = cabo.roundScores(s)
    expect(rows[0]).toMatchObject({sum: 26, gain: 31, reason: 'caboFailed'})
    expect(rows[1]).toMatchObject({gain: 0, reason: 'lowest'})
    assignHands(s, {0: [1, 1, 2, 2], 1: [1, 1, 2, 2], 2: [3, 3, 4, 4]}) // seat 0 now tied with seat 1
    rows = cabo.roundScores(s)
    expect(rows[0]).toMatchObject({gain: 0, reason: 'lowest'})
    expect(rows[1]).toMatchObject({gain: 6, reason: 'cardSum'})
  })
  it('exactly 100 resets once to 50; above 100 ends the game with the lowest total winning', () => {
    let s = fresh()
    assignHands(s, {0: [5, 5, 5, 5], 1: [0, 0, 1, 1], 2: [9, 9, 9, 9]})
    s.players[0].total = 80   // 80 + 20 = 100 → back to 50 (first time)
    s.players[2].total = 70   // 70 + 36 = 106 → game ends
    // Seat 1 called CABO earlier; seat 0 takes the last turn of the final queue.
    s.caller = 1; s.finalQueue = [0]; s.current = 0; s.phase = 'turn'
    s = cabo.act(s, 0, {type: 'draw', source: 'deck'})
    s = cabo.act(s, 0, {type: 'discard', useAbility: false})
    const row0 = s.roundResults.find(r => r.player === 0)!
    expect(row0).toMatchObject({rawAfter: 100, reset: true, after: 50})
    expect(s.players[0]).toMatchObject({total: 50, resetUsed: true})
    expect(s.ended).toBe(true)
    expect(s.winners).toEqual([1])
  })
})
