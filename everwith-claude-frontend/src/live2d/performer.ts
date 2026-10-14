/**
 * Pure per-frame performance composer (no WebGL). One instance per model runtime;
 * the runtime's frame loop is the ONLY caller and the only writer to the model.
 * Inputs are intents (target expression, mouth level source); output is one frame.
 */
import type {CharacterRuntimeConfig} from './characters'
import {sampleMotion} from './motion'
import type {Motion} from './motion'
import {seededRandom} from '../lib/util'

export type Expression = 'neutral' | 'happy' | 'surprised'
export type Frame = {
  canonical: Record<string, number>
  extras: Record<string, number>
  state: {expression: Expression; target: Expression; swapping: boolean; eye: number; mouth: number; idle: 'authored' | 'procedural'}
}
const TAU = Math.PI * 2
const SWAP = {close: .09, hold: .15, open: .13}
const easeIn = (k: number) => k * k * k
const easeOut = (k: number) => 1 - (1 - k) ** 3
/** Smooth limiter: approaches the cap without a hard flat edge. */
const soft = (v: number, cap: number) => cap <= 0 ? 0 : cap * Math.tanh(v / cap)

export class Performer {
  private current: Expression = 'neutral'
  private target: Expression = 'neutral'
  private swapStart: number | null = null
  private swapFrom: Expression = 'neutral'
  private swapTo: Expression = 'neutral'
  private blinkAt: number
  private blinkPhase: {start: number; double: boolean} | null = null
  private rand: () => number
  private mouth = 0
  private lastT = 0
  mouthSource: (() => number | null) | null = null

  constructor(private cfg: CharacterRuntimeConfig, private opts: {reducedMotion: boolean; idleMotion: Motion | null}) {
    this.rand = seededRandom(cfg.seed * 7919)
    this.blinkAt = 1.2 + this.rand() * 2
  }
  setReducedMotion(v: boolean) { this.opts.reducedMotion = v }
  setExpression(e: Expression) { this.target = e }
  /** Cancel / switch: go back to a recognisable neutral face (through a blink). */
  neutral() { this.target = 'neutral'; this.mouthSource = null }
  get state() { return {current: this.current, target: this.target} }

  private idle(t: number): {x: number; y: number; z: number; bx: number; by: number; bz: number; breath: number; eye: number} {
    const c = this.cfg, rm = this.opts.reducedMotion
    if (c.idle.kind === 'authored' && this.opts.idleMotion) {
      const s = sampleMotion(this.opts.idleMotion, t, ['ParamAngleX', 'ParamAngleY', 'ParamAngleZ', 'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ', 'ParamBreath', 'ParamEyeLOpen'])
      // A slow, incommensurate layer keeps the 12 s loop from reading as a short repeat.
      const drift = Math.sin(TAU * t / 17.3 + c.seed) * .35 + Math.sin(TAU * t / 29.7 + c.seed * .7) * .2
      const k = rm ? .25 : 1
      return {
        x: (s.ParamAngleX ?? 0) * c.idle.scale.x * k + drift * c.headCaps.x * .25 * k,
        y: (s.ParamAngleY ?? 0) * c.idle.scale.y * k + Math.sin(TAU * t / 11.1 + c.seed) * c.headCaps.y * .2 * k,
        z: (s.ParamAngleZ ?? 0) * c.idle.scale.z * k + drift * c.headCaps.z * .2 * k,
        bx: (s.ParamBodyAngleX ?? 0) * k, by: (s.ParamBodyAngleY ?? 0) * k, bz: (s.ParamBodyAngleZ ?? 0) * k,
        breath: s.ParamBreath ?? (.5 + .5 * Math.sin(TAU * t / 3.6)), eye: s.ParamEyeLOpen ?? 1,
      }
    }
    // Procedural idle for runtimes without an authored loop (Arthur, Iris).
    const p = c.seed, k = rm ? .2 : 1
    const x = c.headCaps.x * k * (.55 * Math.sin(TAU * t / 7.9 + p) + .22 * Math.sin(TAU * t / 3.7 + p * 1.3) + .12 * Math.sin(TAU * t / 13.3 + p * .4))
    const y = c.headCaps.y * k * (.5 * Math.sin(TAU * t / 5.3 + p * .9) + .25 * Math.sin(TAU * t / 2.9 + p * 2.1))
    const z = c.headCaps.z * k * (.6 * Math.sin(TAU * t / 9.1 + p * .5) + .2 * Math.sin(TAU * t / 4.1 + p))
    return {x, y, z, bx: x * .35, by: y * .3, bz: z * .4, breath: .5 + .5 * Math.sin(TAU * t / (rm ? 4.8 : 3.6) + p), eye: this.blink(t)}
  }
  private blink(t: number): number {
    if (!this.blinkPhase && t >= this.blinkAt) this.blinkPhase = {start: t, double: this.rand() < .15}
    if (!this.blinkPhase) return 1
    const e = t - this.blinkPhase.start
    const one = (u: number) => u < .07 ? 1 - easeIn(u / .07) : u < .11 ? 0 : u < .23 ? easeOut((u - .11) / .12) : 1
    const v = this.blinkPhase.double ? (e < .23 ? one(e) : one(e - .3)) : one(e)
    if (e > (this.blinkPhase.double ? .55 : .25)) { this.blinkPhase = null; this.blinkAt = t + 2.2 + this.rand() * 3.4 }
    return v
  }

  frame(t: number): Frame {
    const dt = Math.max(0, Math.min(.1, t - this.lastT)); this.lastT = t
    const c = this.cfg, idle = this.idle(t)
    // Expression transitions happen behind a blink so a face swap is never visible.
    if (this.swapStart === null && this.target !== this.current) { this.swapStart = t; this.swapFrom = this.current; this.swapTo = this.target }
    let eyeSwap = 1, mix = 1, swapping = false
    if (this.swapStart !== null) {
      swapping = true
      const e = t - this.swapStart
      if (e < SWAP.close + SWAP.hold) this.swapTo = this.target // retarget only while the eyes are still closing/closed
      if (e < SWAP.close) { eyeSwap = 1 - easeIn(e / SWAP.close); mix = 0 }
      else if (e < SWAP.close + SWAP.hold) { eyeSwap = 0; mix = (e - SWAP.close) / SWAP.hold }
      else if (e < SWAP.close + SWAP.hold + SWAP.open) { this.current = this.swapTo; eyeSwap = easeOut((e - SWAP.close - SWAP.hold) / SWAP.open) }
      else { this.current = this.swapTo; this.swapStart = null; swapping = false }
    }
    const weights = (e: Expression) => ({happy: e === 'happy' ? 1 : 0, surprised: e === 'surprised' ? 1 : 0})
    const from = weights(this.swapFrom), to = weights(this.swapStart !== null ? this.swapTo : this.current)
    let happy = this.swapStart !== null ? from.happy + (to.happy - from.happy) * mix : to.happy
    let surprised = this.swapStart !== null ? from.surprised + (to.surprised - from.surprised) * mix : to.surprised
    if (c.expressionMode === 'discrete') { happy = happy >= .5 ? 1 : 0; surprised = surprised >= .5 ? 1 : 0 }
    const eye = Math.min(idle.eye, eyeSwap)
    // Mouth follows a real audio level only; silent → closed. Closed during any swap.
    const level = this.mouthSource?.() ?? null
    const targetMouth = swapping || level === null ? 0 : Math.max(0, Math.min(1, (level - .02) * 3.2))
    if (swapping) this.mouth = 0
    else this.mouth += (targetMouth - this.mouth) * Math.min(1, (targetMouth > this.mouth ? 22 : 12) * dt)
    const mouth = this.mouth < .01 ? 0 : this.mouth
    const fractional = (happy > 0 && happy < 1) || (surprised > 0 && surprised < 1)
    const canonical: Record<string, number> = {
      ParamAngleX: soft(idle.x, c.headCaps.x), ParamAngleY: soft(idle.y, c.headCaps.y), ParamAngleZ: soft(idle.z, c.headCaps.z),
      ParamEyeLOpen: fractional ? 0 : eye, ParamEyeROpen: fractional ? 0 : eye,
      ParamMouthOpenY: fractional ? 0 : mouth, ParamExpressionHappy: happy, ParamExpressionSurprised: surprised,
    }
    // Nora gaze OFF (and no gaze for anyone): eyeball channels are never written.
    return {canonical, extras: {ParamBreath: idle.breath, ParamBodyAngleX: idle.bx, ParamBodyAngleY: idle.by, ParamBodyAngleZ: idle.bz},
      state: {expression: this.current, target: this.target, swapping, eye, mouth, idle: c.idle.kind === 'authored' && this.opts.idleMotion ? 'authored' : 'procedural'}}
  }
}
