import { useEffect, useState } from "react"

const COMPACT_DESKTOP_QUERY = "(min-width: 1180px) and (min-height: 760px)"

function readMatches(query: string) {
  if (typeof window === "undefined") {
    return false
  }
  return window.matchMedia(query).matches
}

export function useCompactDesktop(query = COMPACT_DESKTOP_QUERY) {
  const [matches, setMatches] = useState(() => readMatches(query))

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    const updateMatches = () => {
      setMatches(mediaQuery.matches)
    }

    updateMatches()
    mediaQuery.addEventListener("change", updateMatches)
    return () => {
      mediaQuery.removeEventListener("change", updateMatches)
    }
  }, [query])

  return matches
}
