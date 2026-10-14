/**
 * Component-level checks in jsdom: IME-safe Enter (synthetic composition events only —
 * a real macOS/Windows Chinese IME pass still needs a person) and hidden-information
 * rendering on the CABO / Splendor boards.
 */
import {afterEach, describe, expect, it, vi} from 'vitest'
import {useState} from 'react'
import {cleanup, fireEvent, render} from '@testing-library/react'
import {Composer} from '../src/chat/Composer'
import {CaboBoard} from '../src/features/games/boards/CaboBoard'
import {SplendorBoard} from '../src/features/games/boards/SplendorBoard'
import * as cabo from '../src/games/engines/cabo/engine'
import * as splendor from '../src/games/engines/splendor/splendor/rules'
import {splendorProjection} from '../src/mock/games/modules'
import type {GameViewJSON} from '../src/api/types'
import {LiveStage} from '../src/live2d/LiveStage'
import {CHARACTERS} from '../src/live2d/characters'
import {SpotArt, StageBackdrop} from '../src/components/Art'
import {missingUrl} from '../src/components/Portrait'

afterEach(cleanup)

function Harness({onSubmit}: {onSubmit: (t: string) => void}) {
  const [v, setV] = useState('你好')
  return <Composer value={v} onChange={setV} onSubmit={onSubmit} label="input" placeholder="input" />
}

describe('Composer IME safety', () => {
  it('Enter sends; Shift+Enter does not', () => {
    const sent = vi.fn()
    const {container} = render(<Harness onSubmit={sent} />)
    const ta = container.querySelector('textarea')!
    fireEvent.keyDown(ta, {key: 'Enter', shiftKey: true})
    expect(sent).not.toHaveBeenCalled()
    fireEvent.keyDown(ta, {key: 'Enter'})
    expect(sent).toHaveBeenCalledTimes(1)
  })
  it('the * button wraps the selected text as an action span', () => {
    const {container} = render(<Harness onSubmit={() => {}} />)
    const ta = container.querySelector('textarea')!
    ta.focus(); ta.setSelectionRange(0, 2)
    fireEvent.mouseDown(container.querySelector('.ew-star')!)
    fireEvent.click(container.querySelector('.ew-star')!)
    expect(ta.value).toBe('*你好*')
  })
  it('double-click on Send: one send, and the second click does not hit the Stop that replaced it', () => {
    const sent = vi.fn(), stop = vi.fn()
    function BusyHarness() {
      const [v, setV] = useState('你好'), [busy, setBusy] = useState(false)
      return <Composer value={v} onChange={setV} onSubmit={t => { sent(t); setBusy(true) }} onStop={stop} busy={busy} label="input" placeholder="input" />
    }
    const {container} = render(<BusyHarness />)
    fireEvent.click(container.querySelector('.ew-send')!, {detail: 1})
    const stopBtn = container.querySelector('.ew-send.is-stop')!
    expect(stopBtn).toBeTruthy()
    fireEvent.click(stopBtn, {detail: 2}) // second half of the double-click
    expect(sent).toHaveBeenCalledTimes(1)
    expect(stop).not.toHaveBeenCalled()
    fireEvent.click(stopBtn, {detail: 1}) // a deliberate, separate click still stops
    expect(stop).toHaveBeenCalledTimes(1)
  })
  it('no send while composing (compositionstart / isComposing / keyCode 229) nor right after compositionend', async () => {
    const sent = vi.fn()
    const {container} = render(<Harness onSubmit={sent} />)
    const ta = container.querySelector('textarea')!
    fireEvent.compositionStart(ta)
    fireEvent.keyDown(ta, {key: 'Enter', isComposing: true})
    fireEvent.keyDown(ta, {key: 'Enter', keyCode: 229})
    fireEvent.compositionEnd(ta)
    fireEvent.keyDown(ta, {key: 'Enter'}) // the trailing Enter some IMEs deliver right after commit
    expect(sent).not.toHaveBeenCalled()
    await new Promise(r => setTimeout(r, 80))
    fireEvent.keyDown(ta, {key: 'Enter'})
    expect(sent).toHaveBeenCalledTimes(1)
  })
})

const seat = (n: number, name: string) => ({seat: n, kind: n === 0 ? 'player' as const : 'temporary' as const, identity: `id-${n}`, friend_epoch: null, name, source_id: null, source_version: null, avatar: null, live2d: null})
const wrap = (game_id: 'cabo' | 'gems', player_view: unknown, players: number, revision = 5): GameViewJSON => ({
  schema_version: 'everwith-game-view-v1', mode: 'rule_simulated_companions', id: 'g1', game_id, profile: game_id === 'cabo' ? 'cabo-shareful-2025-en-slice-provisional' : 'splendor-base-2024-v2',
  seats: Array.from({length: players}, (_, i) => seat(i, i ? `NPC${i}` : 'You')), lifecycle: 'active', revision, ai_hold: false, actor_seat: 0, phase: 'x', player_view, settlement: null,
  origin: {kind: 'discover', return_hash: '#/discover'}, created_at: '', updated_at: '', rematch_of: null, archived: false, log: [], expressions: {}, chat_count: 0,
})

describe('CABO board never renders an unknown value', () => {
  it('opponent face-down cards are backs with no numbers; my known cards carry a badge without a number', () => {
    let s = cabo.create({players: 3, seed: 5})
    // Play setup + a few turns with the fixed strategy until it is seat 0's turn.
    for (let i = 0; i < 200 && !(s.phase === 'turn' && s.current === 0 && s.setupDone.length === 3); i++) s = cabo.act(s, s.current, cabo.decide(cabo.observe(s, s.current), 'medium', {seed: i + 1}))
    expect(s.phase).toBe('turn')
    const o = cabo.observe(s, 0)
    const {container} = render(<CaboBoard view={wrap('cabo', o, 3)} pending={false} act={async () => true} seatName={n => n ? `NPC${n}` : 'You'} readOnly={false} />)
    for (const p of s.players.filter(p => p.id !== 0)) for (const id of p.cards) {
      if (s.up[id]) continue
      const el = container.querySelector(`[data-testid="cabo-seat${p.id}-${p.positions[id]}"]`)!
      expect(el, `seat ${p.id} slot ${p.positions[id]}`).toBeTruthy()
      expect(el.querySelector('.cb-front')).toBeNull()
      expect(el.getAttribute('aria-label')).toMatch(/盖着|face down/)
      expect(el.textContent).not.toMatch(/\d/)
    }
    const knownOwn = s.players[0].cards.filter(id => typeof s.knowledge[0][id] === 'number' && !s.up[id])
    expect(knownOwn.length).toBeGreaterThan(0)
    for (const id of knownOwn) {
      const el = container.querySelector(`[data-testid="cabo-own-${s.players[0].positions[id]}"]`)!
      expect(el.querySelector('.cb-known')).toBeTruthy()
      expect(el.querySelector('.cb-front')).toBeNull()
      expect(el.textContent).not.toMatch(/\d/)
    }
  })
})

describe('Splendor board hides other seats\' blind reserves', () => {
  it('shows only a tier back: no card id, no click target, no tooltip with card data', () => {
    let s = splendor.createGame({players: 2, seed: 'unit-blind'})
    const take = splendor.legalActions(s, 0).find(a => a.type === 'take')!
    s = splendor.applyAction(s, 0, take)
    s = splendor.applyAction(s, 1, {type: 'reserve', tier: 2})
    const hiddenId = s.players[1].reserved[0]!
    const {container} = render(<SplendorBoard view={wrap('gems', splendorProjection(s, 0), 2)} pending={false} act={async () => true} seatName={n => n ? 'NPC1' : 'You'} readOnly={false} />)
    expect(container.innerHTML).not.toContain(hiddenId)
    const seat1 = container.querySelector('[data-seat="1"]')!
    const back = seat1.querySelector('.sp-card.is-back')!
    expect(back.tagName).toBe('SPAN')
    expect(back.getAttribute('aria-label')).toMatch(/暗预留|Blind reserve/)
    expect(back.getAttribute('data-card')).toBeNull()
  })
  it('offers exactly the engine\'s legal takes and buys to seat 0', () => {
    const s = splendor.createGame({players: 3, seed: 'unit-legal'})
    const {container} = render(<SplendorBoard view={wrap('gems', splendorProjection(s, 0), 3)} pending={false} act={async () => true} seatName={n => `P${n}`} readOnly={false} />)
    const legal = container.querySelector('[data-testid="splendor-legal"]')!
    const engineTakes = splendor.legalActions(s, 0).filter(a => a.type === 'take').map(a => [...(a as {colors: string[]}).colors].sort().join('+')).sort()
    expect((legal.getAttribute('data-take') ?? '').split(' ').filter(Boolean).sort()).toEqual(engineTakes)
    expect(container.querySelectorAll('button[data-testid^="splendor-bank-gold"]').length).toBe(0)
  })
})

describe('generated art (user-provided batch) stays decorative', () => {
  // active={false}: no WebGL in jsdom; the static layer and the backdrop are what is under test.
  it('the stage backdrop follows the character, falls back to the generic room, and can be turned off', () => {
    const {container, rerender} = render(<LiveStage character={CHARACTERS.nora} name="Nora" active={false} />)
    const src = () => container.querySelector('.ew-backdrop img')?.getAttribute('src') ?? null
    expect(src()).toBe('/generated/batch-01/backdrop-nora.webp')
    expect(container.querySelector('.ew-backdrop')?.getAttribute('aria-hidden')).toBe('true')
    rerender(<LiveStage character={null} name="Mine" active={false} />)
    expect(src()).toBe('/generated/batch-01/backdrop-generic.webp')
    rerender(<LiveStage character={CHARACTERS.nora} name="Nora" active={false} backdrop={null} />)
    expect(container.querySelector('.ew-backdrop')).toBeNull()
  })
  it('the missing-assets scenario rewrites package and generated paths alike', () => {
    expect(missingUrl('/generated/batch-01/backdrop-iris.webp')).toBe('/generated/__missing__/batch-01/backdrop-iris.webp')
    expect(missingUrl('/handoff/assets/companions/feed/iris.webp')).toBe('/handoff/__missing__/assets/companions/feed/iris.webp')
    expect(missingUrl('/elsewhere.png')).toBe('/elsewhere.png')
  })
  it('a backdrop or spot illustration that fails to load disappears instead of showing a broken image', () => {
    const {container} = render(<div><StageBackdrop src="/generated/batch-01/backdrop-iris.webp" /><SpotArt kind="recent" /></div>)
    expect(container.querySelectorAll('img')).toHaveLength(2)
    expect(container.querySelector('.ew-spot')?.getAttribute('alt')).toBe('')
    fireEvent.error(container.querySelector('.ew-backdrop img')!)
    fireEvent.error(container.querySelector('.ew-spot')!)
    expect(container.querySelectorAll('img')).toHaveLength(0)
  })
})
