import { useEffect, useMemo, useRef, useState } from "react"
import type { AuthorLoadingCard } from "../../../index"
import { getAuthorLoadingCardLabel } from "../../../shared/lib/author-loading"
import { useMotionProfile } from "../../../shared/lib/motion"

const SPOTLIGHT_TRANSITION_VARIANTS = ["fade-up", "fade-down", "drift-left", "drift-right"] as const
type SpotlightTransitionVariant = (typeof SPOTLIGHT_TRANSITION_VARIANTS)[number]

export function LoadingCardSpotlight({
  activeCard,
  uiLanguage = "en",
}: {
  activeCard: AuthorLoadingCard | null
  uiLanguage?: "en" | "zh"
}) {
  if (!activeCard) {
    return null
  }

  const { reducedMotion, tier } = useMotionProfile()
  const signature = useMemo(
    () => `${activeCard.card_id}:${activeCard.value}`,
    [activeCard.card_id, activeCard.value],
  )
  const lastSignatureRef = useRef<string | null>(null)
  const transitionTimerRef = useRef<number | null>(null)
  const [isSwapping, setIsSwapping] = useState(false)
  const [transitionVariant, setTransitionVariant] = useState<SpotlightTransitionVariant>("fade-up")

  useEffect(() => {
    if (lastSignatureRef.current === null) {
      lastSignatureRef.current = signature
      return
    }
    if (lastSignatureRef.current === signature) {
      return
    }
    lastSignatureRef.current = signature
    if (reducedMotion) {
      setIsSwapping(false)
      return
    }
    if (tier === "desktop") {
      const nextVariant =
        SPOTLIGHT_TRANSITION_VARIANTS[
          Math.floor(Math.random() * SPOTLIGHT_TRANSITION_VARIANTS.length)
        ] ?? "fade-up"
      setTransitionVariant(nextVariant)
    } else {
      setTransitionVariant("fade-up")
    }
    setIsSwapping(true)
    if (transitionTimerRef.current) {
      window.clearTimeout(transitionTimerRef.current)
    }
    transitionTimerRef.current = window.setTimeout(() => {
      setIsSwapping(false)
      transitionTimerRef.current = null
    }, 180)

    return () => {
      if (transitionTimerRef.current) {
        window.clearTimeout(transitionTimerRef.current)
        transitionTimerRef.current = null
      }
    }
  }, [reducedMotion, signature, tier])

  return (
    <div aria-live="polite" className="loading-spotlight">
      <div
        className={`loading-spotlight-card emphasis-${activeCard.emphasis} ${uiLanguage === "zh" ? "is-zh" : ""} ${isSwapping ? `swap-${transitionVariant}` : ""}`}
      >
        <span className={`loading-spotlight-label ${isSwapping ? "is-swapping" : ""}`}>{getAuthorLoadingCardLabel(activeCard.card_id, activeCard.label, uiLanguage)}</span>
        <div className={`loading-spotlight-value ${isSwapping ? "is-swapping" : ""}`}>
          <strong>{activeCard.value}</strong>
        </div>
      </div>
    </div>
  )
}
