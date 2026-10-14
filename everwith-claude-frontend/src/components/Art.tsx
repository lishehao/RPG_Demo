import {useEffect, useState} from 'react'
import {useAssetUrl} from './Portrait'
import {SPOT_ART} from '../art/generated'
import type {SpotArtKind} from '../art/generated'

/**
 * Decorative room behind a character (generated batch). If the file is missing the
 * surface keeps its own gradient — nothing else is substituted, and never a face.
 */
export function StageBackdrop({src, position, className = ''}: {src: string | null | undefined; position?: string; className?: string}) {
  const url = useAssetUrl(src)
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  if (!url || failed) return null
  return (
    <div className={`ew-backdrop ${className}`} aria-hidden="true">
      <img src={url} alt="" decoding="async" draggable={false} style={position ? {objectPosition: position} : undefined} onError={() => setFailed(true)} />
    </div>
  )
}

/** Illustration for an empty / error / sign-in state. Decorative: the heading carries the meaning. */
export function SpotArt({kind, className = ''}: {kind: SpotArtKind; className?: string}) {
  const url = useAssetUrl(SPOT_ART[kind])
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  if (!url || failed) return null
  return <img className={`ew-spot ${className}`} src={url} alt="" aria-hidden="true" decoding="async" draggable={false} width={160} height={160} data-art={kind} onError={() => setFailed(true)} />
}
