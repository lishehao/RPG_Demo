import { useEffect, useState } from "react"

function useCompactLayout(query = "(max-width: 720px)") {
  const [compact, setCompact] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    const media = window.matchMedia(query)
    const update = () => setCompact(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [query])
  return compact
}

export { useCompactLayout }
