import { useEffect, useState } from "react"

export function StreamingText({
  text,
  speedMs = 14,
  delayMs = 0,
}: {
  text: string
  speedMs?: number
  delayMs?: number
}) {
  const [visibleLength, setVisibleLength] = useState(text.length)

  useEffect(() => {
    if (!text) {
      setVisibleLength(0)
      return
    }

    setVisibleLength(0)
    let index = 0
    let intervalId: number | undefined
    const timeoutId = window.setTimeout(() => {
      intervalId = window.setInterval(() => {
        index += 1
        setVisibleLength(index)
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
  }, [delayMs, speedMs, text])

  const visibleText = text.slice(0, Math.max(visibleLength, 0))
  const streaming = visibleLength < text.length

  return (
    <span aria-label={text} className="streaming-text">
      {visibleText}
      {streaming ? <span aria-hidden="true" className="streaming-text__cursor" /> : null}
    </span>
  )
}
