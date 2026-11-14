import {useEffect, useState, useSyncExternalStore} from 'react'
import {scenarios} from '../mock/scenarios'

/** Package files (/handoff/) and the user-provided generated batch (/generated/) both go “missing” in that scenario. */
export function missingUrl(src: string): string {
  for (const prefix of ['/handoff/', '/generated/']) if (src.startsWith(prefix)) return src.replace(prefix, `${prefix}__missing__/`)
  return src
}
/** Rewrites asset URLs when the “assets missing” mock scenario is on. */
export function useAssetUrl(src: string | null | undefined): string | null {
  const missing = useSyncExternalStore(scenarios.subscribe, () => scenarios.isOn('assets.missing'), () => false)
  if (!src) return null
  return missing ? missingUrl(src) : src
}

/**
 * Image bound to an identity. On failure it shows a neutral placeholder with the
 * same person's initial — never another character's face.
 */
export function Portrait({src, name, className = '', alt, fit = 'cover', position}: {src: string | null | undefined; name: string; className?: string; alt?: string; fit?: 'cover' | 'contain'; position?: string}) {
  const url = useAssetUrl(src)
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  if (!url || failed) {
    return (
      <span className={`ew-portrait is-placeholder ${className}`} role="img" aria-label={alt ?? name} data-missing={src ? 'true' : 'none'}>
        <span aria-hidden="true">{[...name.trim()][0]?.toUpperCase() ?? '·'}</span>
      </span>
    )
  }
  return <img className={`ew-portrait ${className}`} src={url} alt={alt ?? name} loading="lazy" decoding="async" style={{objectFit: fit, objectPosition: position}} onError={() => setFailed(true)} />
}
