/**
 * Lazy loader for the hash-verified Cubism runtime subset copied by `assets:sync`
 * (Core script from /public/handoff, Framework TypeScript from src/vendor). When the
 * runtime is absent the glob is empty and every stage falls back to its static image.
 */
export type CubismIdHandle = {getString(): {s: string} | string}
export interface CubismModelLike {
  getParameterCount(): number; getDrawableCount(): number
  getParameterId(i: number): CubismIdHandle
  getParameterDefaultValue(i: number): number; getParameterMinimumValue(i: number): number; getParameterMaximumValue(i: number): number
  getParameterValueByIndex(i: number): number; setParameterValueByIndex(i: number, v: number, w?: number): void
  getDrawableVertexPositions(i: number): Float32Array; getDrawableVertexCount(i: number): number
  getDrawableDynamicFlagIsVisible(i: number): boolean; getDrawableOpacity(i: number): number
  getCanvasWidth(): number; getCanvasHeight(): number
  update(): void
}
export interface CubismMocLike { createModel(): CubismModelLike | null; deleteModel(m: CubismModelLike): void; release(): void }
export interface CubismRendererLike {
  initialize(model: CubismModelLike, maskBufferCount?: number): void; startUp(gl: WebGLRenderingContext | WebGL2RenderingContext): void
  bindTexture(no: number, tex: WebGLTexture): void; setIsPremultipliedAlpha(v: boolean): void; setMvpMatrix(m: unknown): void
  setRenderState(fbo: WebGLFramebuffer | null, viewport: number[]): void; drawModel(shaderPath?: string | null): void; release(): void
  setRenderTargetSize?(w: number, h: number): void
}
export interface CubismPhysicsLike { evaluate(model: CubismModelLike, dt: number): void }
export type Framework = {
  Moc: {create(buf: ArrayBuffer, check: boolean): CubismMocLike | null; delete(m: CubismMocLike): void}
  Renderer: new (w: number, h: number) => CubismRendererLike
  Physics: {create(buf: ArrayBuffer, size: number): CubismPhysicsLike | null; delete(p: CubismPhysicsLike): void}
  Matrix44: new () => {setMatrix(m: Float32Array): void}
  ShaderManager: {getInstance(): {getShader(gl: WebGLRenderingContext): unknown}}
  shaderPath: string
}

const CORE_URL = '/handoff/assets/runtime/cubism/Core/live2dcubismcore.min.js'
const SHADER_PATH = '/handoff/assets/runtime/cubism/Framework/Shaders/WebGL/'
const modules = import.meta.glob('../vendor/cubism-framework/src/**/*.ts')
const mod = async <T>(path: string): Promise<T> => {
  const loader = modules[`../vendor/cubism-framework/src/${path}`]
  if (!loader) throw Error('live2d_framework_missing')
  return await loader() as T
}

let flight: Promise<Framework> | null = null
function loadCore(): Promise<void> {
  if ((window as unknown as {Live2DCubismCore?: unknown}).Live2DCubismCore) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = CORE_URL; script.async = true
    script.onload = () => (window as unknown as {Live2DCubismCore?: unknown}).Live2DCubismCore ? resolve() : reject(Error('live2d_core_missing'))
    script.onerror = () => reject(Error('live2d_core_missing'))
    document.head.appendChild(script)
  })
}
export function loadFramework(): Promise<Framework> {
  if (flight) return flight
  flight = (async () => {
    await loadCore()
    const fw = await mod<{CubismFramework: {startUp(o: unknown): boolean; initialize(m?: number): void; isInitialized(): boolean}; Option: new () => {logFunction: unknown; loggingLevel: number}; LogLevel: Record<string, number>}>('live2dcubismframework.ts')
    const [moc, renderer, physics, matrix, shader] = await Promise.all([
      mod<{CubismMoc: Framework['Moc']}>('model/cubismmoc.ts'),
      mod<{CubismRenderer_WebGL: Framework['Renderer']}>('rendering/cubismrenderer_webgl.ts'),
      mod<{CubismPhysics: Framework['Physics']}>('physics/cubismphysics.ts'),
      mod<{CubismMatrix44: Framework['Matrix44']}>('math/cubismmatrix44.ts'),
      mod<{CubismShaderManager_WebGL: Framework['ShaderManager']}>('rendering/cubismshader_webgl.ts'),
    ])
    if (!fw.CubismFramework.isInitialized()) {
      const option = new fw.Option()
      option.logFunction = (message: string) => { if (/error/i.test(message)) console.warn('[Cubism]', message) }
      option.loggingLevel = fw.LogLevel.LogLevel_Error
      fw.CubismFramework.startUp(option)
      fw.CubismFramework.initialize()
    }
    return {Moc: moc.CubismMoc, Renderer: renderer.CubismRenderer_WebGL, Physics: physics.CubismPhysics, Matrix44: matrix.CubismMatrix44, ShaderManager: shader.CubismShaderManager_WebGL, shaderPath: SHADER_PATH}
  })()
  flight.catch(() => { flight = null })
  return flight
}
export const frameworkAvailable = () => Object.keys(modules).length > 0
