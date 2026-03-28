import { useEffect, useState } from "react"
import { useMotionProfile } from "../lib/motion"

export function StreamingText({
  text,
  speedMs = 14,
  delayMs = 0,
  variant = "body",
}: {
  text: string
  speedMs?: number
  delayMs?: number
  variant?: "headline" | "body"
}) {
  const { reducedMotion, tier } = useMotionProfile()
  const [{ visibleLength, revealReady, typewriter }, setState] = useState(() => ({
    visibleLength: text.length,
    revealReady: true,
    typewriter: false,
  }))

  useEffect(() => {
    if (!text) {
      setState({ visibleLength: 0, revealReady: true, typewriter: false })
      return
    }

    const shouldTypewriter = !reducedMotion && tier === "desktop" && variant === "headline"
    const shouldReveal = !reducedMotion && !shouldTypewriter

    if (!shouldTypewriter && !shouldReveal) {
      setState({ visibleLength: text.length, revealReady: true, typewriter: false })
      return
    }

    if (shouldReveal) {
      setState({ visibleLength: text.length, revealReady: false, typewriter: false })
      const timeoutId = window.setTimeout(() => {
        setState({ visibleLength: text.length, revealReady: true, typewriter: false })
      }, tier === "mobile" ? 0 : Math.max(delayMs, 0))

      return () => {
        window.clearTimeout(timeoutId)
      }
    }

    setState({ visibleLength: 0, revealReady: true, typewriter: true })
    let index = 0
    let intervalId: number | undefined
    const timeoutId = window.setTimeout(() => {
      intervalId = window.setInterval(() => {
        index += 1
        setState({ visibleLength: index, revealReady: true, typewriter: true })
        if (index >= text.length) {
          if (intervalId) {
            window.clearInterval(intervalId)
          }
        }
      }, Math.max(speedMs, 8))
    }, Math.max(delayMs, 0))

    return () => {
      window.clearTimeout(timeoutId)
      if (intervalId) {
        window.clearInterval(intervalId)
      }
    }
  }, [delayMs, reducedMotion, speedMs, text, tier, variant])

  const visibleText = text.slice(0, Math.max(visibleLength, 0))
  const streaming = typewriter && visibleLength < text.length

  return (
    <span
      aria-label={text}
      className={`streaming-text ${revealReady ? "is-visible" : "is-waiting"} ${typewriter ? "is-typewriter" : "is-reveal"}`}
    >
      {visibleText}
      {streaming ? <span aria-hidden="true" className="streaming-text__cursor" /> : null}
    </span>
  )
}
