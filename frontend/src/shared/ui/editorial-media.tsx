import { useState } from "react"

export function EditorialMedia({
  src,
  alt = "",
  className = "",
  overlay = false,
  ratio = "4 / 5",
}: {
  src?: string | null
  alt?: string
  className?: string
  overlay?: boolean
  ratio?: string
}) {
  const [failed, setFailed] = useState(false)

  if (!src || failed) {
    return (
      <div
        aria-hidden="true"
        className={["editorial-media", "is-placeholder", overlay ? "has-grade" : "", className].filter(Boolean).join(" ")}
        style={{ aspectRatio: ratio }}
      />
    )
  }

  return (
    <div
      className={["editorial-media", overlay ? "has-grade" : "", className].filter(Boolean).join(" ")}
      style={{ aspectRatio: ratio }}
    >
      <img alt={alt} className="editorial-media__image" onError={() => setFailed(true)} src={src} />
    </div>
  )
}
