/**
 * One Live2D model on one canvas. Owns every GL resource it creates and releases
 * them on dispose. The frame loop is the single writer: performer → verified frame
 * writer (frozen caps / Iris carrier units) → breath & body → physics → update → draw.
 */
import {loadFramework} from './framework'
import type {CubismModelLike, CubismMocLike, CubismPhysicsLike, CubismRendererLike, Framework} from './framework'
import type {CharacterRuntimeConfig, FramingPreset} from './characters'
import {parseMotion} from './motion'
import {Performer} from './performer'
import type {Expression, Frame} from './performer'
import {bindVerifiedFrameWriter} from './verified-frame-writer'
import type {CoreModel} from './verified-frame-writer'

export type RuntimeStatus = 'loading' | 'ready' | 'failed' | 'lost' | 'disposed'
export type RuntimeStats = {frames: number; avgFrameMs: number; maxFrameMs: number; startedAt: number; lastError: string | null; textureBytes: number; contextLosses: number; restores: number}

async function sha256(buf: ArrayBuffer) {
  const d = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(d), b => b.toString(16).padStart(2, '0')).join('')
}
async function fetchBuffer(url: string, signal: AbortSignal) {
  const r = await fetch(url, {signal, cache: 'force-cache'})
  if (!r.ok) throw Error(`asset_missing:${url}`)
  return r.arrayBuffer()
}
function loadImage(url: string, signal: AbortSignal): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.decoding = 'async'
    img.onload = () => resolve(img)
    img.onerror = () => reject(Error(`asset_missing:${url}`))
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), {once: true})
    img.src = url
  })
}

/** Framing from the frozen face ROI + measured head top: whole head, face as large as fits. */
export function framingMatrix(cfg: CharacterRuntimeConfig, bounds: {top: number; bottom: number}, cssW: number, cssH: number, preset: FramingPreset) {
  const [x0, x1, y0, y1] = cfg.faceBox
  const faceH = cfg.referenceFace[3] - cfg.referenceFace[2]
  const plan = {
    stage: {below: .9, topMargin: .045, widthFrac: .9},
    zoom: {below: .7, topMargin: .04, widthFrac: .82},
    card: {below: 1.25, topMargin: .06, widthFrac: .86},
    rail: {below: .45, topMargin: .05, widthFrac: .92},
    thumb: {below: .25, topMargin: .03, widthFrac: .98},
  }[preset]
  const top = Math.max(y1, bounds.top) // hair top must stay inside the frame while moving
  // Never frame below the artwork's own lower edge (hides rounded bust corners).
  const bottom = Math.max(y0 - faceH * plan.below, bounds.bottom + .06)
  const span = top - bottom
  const ppu = Math.min(cssH * (1 - plan.topMargin * 2) / span, cssW * plan.widthFrac / ((x1 - x0) * 1.55))
  const cx = (x0 + x1) / 2
  const sx = 2 * ppu / cssW, sy = 2 * ppu / cssH
  const tx = -cx * sx
  // Place the head top at the top margin; extra space (if width-limited) goes below.
  const topPx = cssH * plan.topMargin
  const ty = 1 - 2 * topPx / cssH - top * sy
  return new Float32Array([sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, 1, 0, tx, ty, 0, 1])
}

export class ModelRuntime {
  status: RuntimeStatus = 'loading'
  error: string | null = null
  stats: RuntimeStats = {frames: 0, avgFrameMs: 0, maxFrameMs: 0, startedAt: performance.now(), lastError: null, textureBytes: 0, contextLosses: 0, restores: 0}
  lastFrame: Frame | null = null
  readonly lease = Symbol('lease')
  private fw: Framework | null = null
  private gl: WebGLRenderingContext | null = null
  private moc: CubismMocLike | null = null
  private model: CubismModelLike | null = null
  private renderer: CubismRendererLike | null = null
  private physics: CubismPhysicsLike | null = null
  private texture: WebGLTexture | null = null
  private image: HTMLImageElement | null = null
  private writer: ReturnType<typeof bindVerifiedFrameWriter> | null = null
  private performer: Performer | null = null
  private extrasIndex = new Map<string, {i: number; lo: number; hi: number}>()
  private bounds = {top: 0, bottom: 0}
  private matrix: InstanceType<Framework['Matrix44']> | null = null
  private abort = new AbortController()
  private size = {w: 1, h: 1, dpr: 1}
  private t0 = performance.now()
  private onLost = (e: Event) => { e.preventDefault(); this.status = 'lost'; this.stats.contextLosses++ }
  private onRestored = () => { void this.restore() }

  constructor(readonly canvas: HTMLCanvasElement, readonly cfg: CharacterRuntimeConfig, private opts: {reducedMotion: boolean; preset: FramingPreset}) {}

  setExpression(e: Expression) { this.performer?.setExpression(e) }
  setMouthSource(fn: (() => number | null) | null) { if (this.performer) this.performer.mouthSource = fn }
  neutral() { this.performer?.neutral() }
  setReducedMotion(v: boolean) { this.opts.reducedMotion = v; this.performer?.setReducedMotion(v) }
  setPreset(p: FramingPreset) { this.opts.preset = p; this.updateMatrix() }
  get expression() { return this.performer?.state ?? {current: 'neutral' as Expression, target: 'neutral' as Expression} }

  async load(): Promise<void> {
    const signal = this.abort.signal
    try {
      const fw = this.fw = await loadFramework()
      const base = this.cfg.model3.slice(0, this.cfg.model3.lastIndexOf('/') + 1)
      const setting = await (await fetch(this.cfg.model3, {signal})).json() as {FileReferences: {Moc: string; Textures: string[]; Physics?: string}}
      const mocBuf = await fetchBuffer(base + setting.FileReferences.Moc, signal)
      // Identity pin: refuse any MOC that is not the frozen, accepted candidate.
      if (await sha256(mocBuf) !== this.cfg.mocSha256) throw Error('model_pin_mismatch')
      const moc = this.moc = fw.Moc.create(mocBuf, true)
      if (!moc) throw Error('moc_invalid')
      const model = this.model = moc.createModel()
      if (!model) throw Error('model_invalid')
      this.writer = bindVerifiedFrameWriter(this.cfg.key, model as unknown as CoreModel)
      for (let i = 0; i < model.getParameterCount(); i++) {
        const raw = model.getParameterId(i).getString()
        const id = typeof raw === 'string' ? raw : raw.s
        if (['ParamBreath', 'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ'].includes(id)) this.extrasIndex.set(id, {i, lo: model.getParameterMinimumValue(i), hi: model.getParameterMaximumValue(i)})
      }
      if (setting.FileReferences.Physics) {
        const buf = await fetchBuffer(base + setting.FileReferences.Physics, signal)
        this.physics = fw.Physics.create(buf, buf.byteLength)
      }
      let idleMotion = null
      if (this.cfg.idle.kind === 'authored') idleMotion = parseMotion(await (await fetch(base + this.cfg.idle.motion, {signal})).json())
      this.performer = new Performer(this.cfg, {reducedMotion: this.opts.reducedMotion, idleMotion})
      this.image = await loadImage(base + setting.FileReferences.Textures[0], signal)
      this.measureBounds()
      this.setupGL()
      this.status = 'ready'
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      this.status = 'failed'; this.error = error instanceof Error ? error.message : 'live2d_failed'; this.stats.lastError = this.error
    }
  }

  private measureBounds() {
    const m = this.model!
    this.writer!({})
    m.update()
    let top = -Infinity, bottom = Infinity
    for (let d = 0; d < m.getDrawableCount(); d++) {
      if (!m.getDrawableDynamicFlagIsVisible(d) || m.getDrawableOpacity(d) <= .01) continue
      const v = m.getDrawableVertexPositions(d)
      for (let k = 1; k < v.length; k += 2) { top = Math.max(top, v[k]); bottom = Math.min(bottom, v[k]) }
    }
    this.bounds = {top: Number.isFinite(top) ? top + .02 : this.cfg.faceBox[3], bottom: Number.isFinite(bottom) ? bottom : this.cfg.faceBox[2]}
  }

  private setupGL() {
    const fw = this.fw!
    const gl = this.gl = this.canvas.getContext('webgl', {alpha: true, premultipliedAlpha: true, antialias: true, preserveDrawingBuffer: true})
    if (!gl) throw Error('webgl_unavailable')
    this.canvas.addEventListener('webglcontextlost', this.onLost)
    this.canvas.addEventListener('webglcontextrestored', this.onRestored)
    const tex = gl.createTexture()!
    gl.bindTexture(gl.TEXTURE_2D, tex)
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 1)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, this.image!)
    gl.generateMipmap(gl.TEXTURE_2D)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 0)
    gl.bindTexture(gl.TEXTURE_2D, null)
    this.texture = tex
    this.stats.textureBytes = this.image!.naturalWidth * this.image!.naturalHeight * 4 * 4 / 3
    const renderer = this.renderer = new fw.Renderer(Math.max(1, this.canvas.width), Math.max(1, this.canvas.height))
    renderer.initialize(this.model!, 1)
    if (this.cfg.key === 'nora') (renderer as unknown as {setClippingMaskBufferSize(n: number): void}).setClippingMaskBufferSize(512)
    renderer.startUp(gl)
    renderer.bindTexture(0, tex)
    renderer.setIsPremultipliedAlpha(true)
    this.matrix = new fw.Matrix44()
    this.updateMatrix()
  }

  private async restore() {
    if (this.status === 'disposed' || !this.model) return
    try {
      this.releaseGL(false)
      this.setupGL()
      this.status = 'ready'; this.stats.restores++
    } catch (e) { this.status = 'failed'; this.error = e instanceof Error ? e.message : 'restore_failed' }
  }

  resize(cssW: number, cssH: number, dpr: number) {
    const d = Math.min(2, Math.max(1, dpr))
    const w = Math.max(1, Math.round(cssW * d)), h = Math.max(1, Math.round(cssH * d))
    this.size = {w: cssW, h: cssH, dpr: d}
    if (this.canvas.width !== w || this.canvas.height !== h) { this.canvas.width = w; this.canvas.height = h }
    this.renderer?.setRenderTargetSize?.(w, h)
    this.updateMatrix()
  }
  private updateMatrix() {
    if (!this.matrix) return
    this.matrix.setMatrix(framingMatrix(this.cfg, this.bounds, Math.max(1, this.size.w), Math.max(1, this.size.h), this.opts.preset))
  }

  /** Called by the director's single RAF. Returns false if nothing was drawn. */
  frame(now: number): boolean {
    if (this.status !== 'ready' || !this.gl || !this.renderer || !this.model || !this.performer || !this.writer) return false
    // The context can be lost before the async 'webglcontextlost' event arrives.
    if (this.gl.isContextLost()) return false
    const start = performance.now()
    const t = (now - this.t0) / 1000
    const frame = this.performer.frame(t)
    this.writer(frame.canonical) // resets every parameter to its default, then writes validated channels
    for (const [id, value] of Object.entries(frame.extras)) {
      const p = this.extrasIndex.get(id)
      if (!p) continue
      const v = id === 'ParamBreath' ? Math.max(0, Math.min(1, value)) : Math.max(p.lo, Math.min(p.hi, value))
      this.model.setParameterValueByIndex(p.i, v, 1)
    }
    this.physics?.evaluate(this.model, 1 / 60)
    this.model.update()
    const gl = this.gl
    gl.viewport(0, 0, this.canvas.width, this.canvas.height)
    gl.clearColor(0, 0, 0, 0)
    gl.clear(gl.COLOR_BUFFER_BIT)
    this.renderer.setMvpMatrix(this.matrix)
    this.renderer.setRenderState(null, [0, 0, this.canvas.width, this.canvas.height])
    this.renderer.drawModel(this.fw!.shaderPath)
    this.lastFrame = frame
    this.frameErrorRun = 0
    const ms = performance.now() - start
    this.stats.frames++
    this.stats.avgFrameMs = this.stats.avgFrameMs ? this.stats.avgFrameMs * .95 + ms * .05 : ms
    this.stats.maxFrameMs = Math.max(this.stats.maxFrameMs * .999, ms)
    return true
  }

  /** A frame threw (director keeps running). Many in a row → give up to the static fallback. */
  private frameErrorRun = 0
  noteFrameError(error: unknown) {
    this.stats.lastError = error instanceof Error ? error.message : String(error)
    if (++this.frameErrorRun > 90 && this.status === 'ready') { this.status = 'failed'; this.error = 'frame_failed' }
  }

  private releaseGL(loseContext: boolean) {
    const gl = this.gl
    try { this.renderer?.release() } catch { /* context may already be lost */ }
    this.renderer = null
    if (gl) {
      try { if (this.texture) gl.deleteTexture(this.texture) } catch { /* ignore */ }
      // Drop this context's cached shader programs from the framework singleton.
      try {
        const manager = this.fw?.ShaderManager.getInstance() as unknown as {_shaderMap?: Map<WebGLRenderingContext, {release(): void}>}
        manager?._shaderMap?.get(gl)?.release(); manager?._shaderMap?.delete(gl)
      } catch { /* ignore */ }
      if (loseContext) gl.getExtension('WEBGL_lose_context')?.loseContext()
    }
    this.texture = null
  }
  dispose() {
    if (this.status === 'disposed') return
    this.abort.abort()
    this.canvas.removeEventListener('webglcontextlost', this.onLost)
    this.canvas.removeEventListener('webglcontextrestored', this.onRestored)
    this.releaseGL(true)
    try { if (this.moc && this.model) this.moc.deleteModel(this.model) } catch { /* ignore */ }
    try { this.moc?.release() } catch { /* ignore */ }
    try { if (this.physics) this.fw?.Physics.delete(this.physics) } catch { /* ignore */ }
    this.model = null; this.moc = null; this.physics = null; this.performer = null; this.writer = null; this.image = null; this.gl = null
    this.status = 'disposed'
  }
}
