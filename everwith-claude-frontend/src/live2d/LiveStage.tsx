import {useEffect, useRef, useState, useSyncExternalStore} from 'react'
import {ModelRuntime} from './runtime'
import {director} from './director'
import {frameworkAvailable} from './framework'
import {demoVoice} from './audio'
import type {CharacterRuntimeConfig, FramingPreset} from './characters'
import type {Expression} from './performer'
import {scenarios} from '../mock/scenarios'
import {useApp} from '../app/store'
import {useI18n} from '../app/i18n'
import {Portrait} from '../components/Portrait'
import {StageBackdrop} from '../components/Art'
import {backdropFor} from '../art/generated'
import {classNames} from '../lib/util'

/**
 * Unified character performance surface (friends, NPCs, table-mates and previews use
 * the same component). Static image of the SAME character underneath while loading
 * or when the model/Core/WebGL is unavailable — never another character's face.
 * Behind both sits the character's room (generated batch; generic room for characters
 * without one). `backdrop={null}` turns it off when the surrounding card already has one.
 */
export function LiveStage({character, name, fallbackImage, expression = 'neutral', speaking = false, preset = 'stage', className = '', active = true, showStatus = true, label, backdrop}: {
  character: CharacterRuntimeConfig | null; name: string; fallbackImage?: string | null; expression?: Expression; speaking?: boolean
  preset?: FramingPreset; className?: string; active?: boolean; showStatus?: boolean; label?: string; backdrop?: string | null
}) {
  const {t} = useI18n()
  const reducedMotion = useApp(s => s.reducedMotion)
  const missing = useSyncExternalStore(scenarios.subscribe, () => scenarios.isOn('live2d.model_missing'), () => false)
  const hostRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const runtimeRef = useRef<ModelRuntime | null>(null)
  const [status, setStatus] = useState<'static' | 'loading' | 'ready' | 'failed'>('static')
  const [paused, setPaused] = useState(false)
  const wantLive = !!character && active && !missing && frameworkAvailable()
  const staticSrc = character?.staticPortrait ?? fallbackImage ?? null

  useEffect(() => {
    const canvas = canvasRef.current, host = hostRef.current
    if (!wantLive || !canvas || !host || !character) { setStatus(character && active ? 'failed' : 'static'); return }
    const runtime = new ModelRuntime(canvas, character, {reducedMotion, preset})
    runtimeRef.current = runtime
    setStatus('loading')
    let disposed = false
    const resize = () => { const r = host.getBoundingClientRect(); runtime.resize(r.width, r.height, window.devicePixelRatio || 1) }
    const ro = new ResizeObserver(resize)
    ro.observe(host)
    const io = new IntersectionObserver(entries => {
      const visible = entries.some(e => e.isIntersecting)
      director.setVisible(runtime, visible); setPaused(!visible)
    }, {threshold: .02})
    io.observe(host)
    void runtime.load().then(() => {
      if (disposed) return
      if (runtime.status === 'ready') { resize(); director.register(runtime); setStatus('ready') } else setStatus('failed')
    })
    return () => {
      disposed = true
      ro.disconnect(); io.disconnect()
      director.unregister(runtime)
      runtime.dispose()
      if (runtimeRef.current === runtime) runtimeRef.current = null
    }
    // A new character/preset/activation creates a new runtime (and a new lease).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantLive, character?.key, preset])

  useEffect(() => { runtimeRef.current?.setReducedMotion(reducedMotion) }, [reducedMotion])
  useEffect(() => { if (status === 'ready') runtimeRef.current?.setExpression(expression) }, [expression, status])
  useEffect(() => {
    const runtime = runtimeRef.current
    if (!runtime || status !== 'ready' || !character) return
    runtime.setMouthSource(speaking ? () => demoVoice.speaker === character.key ? demoVoice.level() : null : null)
    return () => runtime.setMouthSource(null)
  }, [speaking, status, character])

  const showCanvas = status === 'ready' || status === 'loading'
  return (
    <div ref={hostRef} className={classNames('ew-stage', `preset-${preset}`, className, status === 'ready' && 'is-live')} data-live2d-status={status} data-character={character?.key ?? 'none'}
      role="img" aria-label={label ?? `${name} · ${t(`expr.${expression}`)}`}>
      <StageBackdrop src={backdrop === undefined ? backdropFor(character?.key) : backdrop} />
      <div className="ew-stage-static" aria-hidden={status === 'ready'}>
        <Portrait src={staticSrc} name={name} fit="cover" position="50% 0%" className="ew-stage-img" />
      </div>
      {/* A disposed runtime loses its WebGL context; a new character/preset gets a fresh canvas element. */}
      <canvas key={`${character?.key ?? 'none'}:${preset}:${wantLive ? 'live' : 'off'}`} ref={canvasRef} className="ew-stage-canvas" hidden={!showCanvas} aria-hidden="true" />
      {showStatus && status === 'failed' && <span className="ew-stage-chip warn">{t('live2d.unavailable')}</span>}
      {showStatus && status === 'loading' && <span className="ew-stage-chip">{t('live2d.loading')}</span>}
      {showStatus && status === 'ready' && paused && <span className="ew-stage-chip">{t('live2d.paused')}</span>}
    </div>
  )
}
