/**
 * “演示音轨” — a locally synthesised babble track (NOT TTS, NOT a voice clone) so the
 * mouth can be shown following real audio. The mouth reads RMS from an AnalyserNode
 * on the actual output; when nothing plays, the level is null and the mouth closes.
 * Audio only starts from a user gesture (browser autoplay policy).
 */
import {hash32, seededRandom} from '../lib/util'
import type {CharacterKey} from './characters'

const PITCH: Record<CharacterKey, number> = {lena: 205, nora: 232, iris: 196, arthur: 118, marcus: 104}

export class DemoVoice {
  private ctx: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private buffer: Float32Array<ArrayBuffer> | null = null
  private sources: AudioScheduledSourceNode[] = []
  private endsAt = 0
  private onEnd: (() => void) | null = null
  speaker: CharacterKey | null = null

  get playing() { return !!this.ctx && this.ctx.currentTime < this.endsAt }

  async play(text: string, speaker: CharacterKey, onEnd?: () => void) {
    this.stop()
    const Ctor = window.AudioContext ?? (window as unknown as {webkitAudioContext?: typeof AudioContext}).webkitAudioContext
    if (!Ctor) throw Error('audio_unavailable')
    this.ctx ??= new Ctor()
    await this.ctx.resume()
    const ctx = this.ctx
    this.analyser = ctx.createAnalyser(); this.analyser.fftSize = 512
    this.buffer = new Float32Array(this.analyser.fftSize)
    const master = ctx.createGain(); master.gain.value = .16
    master.connect(this.analyser); this.analyser.connect(ctx.destination)
    const rand = seededRandom(hash32(text + speaker))
    const chars = [...text.replace(/\*[^*]*\*/g, '').trim()].slice(0, 60)
    let t = ctx.currentTime + .05
    const f0 = PITCH[speaker]
    for (let i = 0; i < chars.length; i++) {
      const ch = chars[i]
      if (/[，。！？、,.!?…\n]/.test(ch)) { t += .22; continue }
      if (/\s/.test(ch)) { t += .06; continue }
      const dur = .11 + rand() * .1
      const osc = ctx.createOscillator(); osc.type = 'sawtooth'
      osc.frequency.setValueAtTime(f0 * (.92 + rand() * .2), t)
      osc.frequency.linearRampToValueAtTime(f0 * (.88 + rand() * .2), t + dur)
      const formant = ctx.createBiquadFilter(); formant.type = 'bandpass'; formant.frequency.value = 650 + rand() * 600; formant.Q.value = 2.4
      const env = ctx.createGain(); env.gain.setValueAtTime(0, t)
      env.gain.linearRampToValueAtTime(1, t + .02); env.gain.setValueAtTime(1, t + dur - .05); env.gain.linearRampToValueAtTime(0, t + dur)
      osc.connect(formant); formant.connect(env); env.connect(master)
      osc.start(t); osc.stop(t + dur + .01)
      this.sources.push(osc)
      t += dur + .03 + rand() * .05
    }
    this.endsAt = t
    this.speaker = speaker
    this.onEnd = onEnd ?? null
    const last = this.sources[this.sources.length - 1]
    if (last) last.onended = () => { if (this.ctx && this.ctx.currentTime >= this.endsAt - .02) this.finish() }
    else this.finish()
  }
  private finish() { const cb = this.onEnd; this.onEnd = null; this.sources = []; this.speaker = null; cb?.() }
  /** RMS level of what is actually being played, or null when silent. */
  level(): number | null {
    if (!this.analyser || !this.buffer || !this.playing) return null
    this.analyser.getFloatTimeDomainData(this.buffer)
    let sum = 0
    for (let i = 0; i < this.buffer.length; i++) sum += this.buffer[i] * this.buffer[i]
    return Math.sqrt(sum / this.buffer.length)
  }
  stop() {
    for (const s of this.sources) { try { s.stop() } catch { /* already stopped */ } }
    this.sources = []; this.endsAt = 0
    const cb = this.onEnd; this.onEnd = null; this.speaker = null; cb?.()
  }
  dispose() { this.stop(); void this.ctx?.close(); this.ctx = null }
}
export const demoVoice = new DemoVoice()
