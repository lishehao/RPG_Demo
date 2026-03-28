import { useEffect, useState, type ReactNode } from "react"
import type { StoryLanguage } from "../../index"
import { getAuthorLoadingThemeImagePath } from "../../shared/lib/author-loading-theme"
import { EditorialMedia } from "../../shared/ui/editorial-media"

const THEME_ASSET_STATUS_CACHE = new Map<string, boolean>()

function useThemeImageAvailability(src: string | null) {
  const [available, setAvailable] = useState<boolean | null>(() => {
    if (!src) {
      return false
    }
    const cached = THEME_ASSET_STATUS_CACHE.get(src)
    return cached ?? null
  })

  useEffect(() => {
    if (!src) {
      setAvailable(false)
      return
    }

    const cached = THEME_ASSET_STATUS_CACHE.get(src)
    if (cached !== undefined) {
      setAvailable(cached)
      return
    }

    let active = true
    const controller = new AbortController()

    const probe = async () => {
      try {
        const response = await fetch(src, {
          method: "HEAD",
          signal: controller.signal,
        })
        if (!active) {
          return
        }
        THEME_ASSET_STATUS_CACHE.set(src, response.ok)
        setAvailable(response.ok)
      } catch {
        if (!active) {
          return
        }
        THEME_ASSET_STATUS_CACHE.set(src, false)
        setAvailable(false)
      }
    }

    setAvailable(null)
    void probe()

    return () => {
      active = false
      controller.abort()
    }
  }, [src])

  return available
}

export function AuthorLoadingThemePanel({
  primaryTheme,
  uiLanguage,
  fallback,
}: {
  primaryTheme?: string | null
  uiLanguage: StoryLanguage
  fallback: ReactNode
}) {
  const src = getAuthorLoadingThemeImagePath(primaryTheme)
  const available = useThemeImageAvailability(src)

  if (!src || available === false) {
    return <>{fallback}</>
  }

  if (available === null) {
    return <div className="loading-theme-panel loading-theme-panel--pending" aria-hidden="true" />
  }

  return (
    <div
      aria-label={uiLanguage === "zh" ? "主题氛围图" : "Theme mood image"}
      className={`loading-theme-panel theme-${primaryTheme ?? "unknown"}`}
    >
      <EditorialMedia
        className="loading-theme-panel__media"
        overlay
        ratio="4 / 5"
        src={src}
      />
    </div>
  )
}
