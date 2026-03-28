import { useEffect, useState } from "react"

export type MotionTier = "desktop" | "tablet" | "mobile"

function readViewportWidth() {
  return typeof window === "undefined" ? 1440 : window.innerWidth
}

export function getMotionTier(): MotionTier {
  const width = readViewportWidth()
  if (width <= 720) {
    return "mobile"
  }
  if (width <= 1100) {
    return "tablet"
  }
  return "desktop"
}

export function prefersReducedMotionNow() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

function readMotionProfile() {
  return {
    reducedMotion: prefersReducedMotionNow(),
    tier: getMotionTier(),
  }
}

export function useMotionProfile() {
  const [profile, setProfile] = useState(readMotionProfile)

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)")
    const updateProfile = () => {
      setProfile(readMotionProfile())
    }

    updateProfile()
    window.addEventListener("resize", updateProfile)
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", updateProfile)
      return () => {
        window.removeEventListener("resize", updateProfile)
        mediaQuery.removeEventListener("change", updateProfile)
      }
    }

    mediaQuery.addListener(updateProfile)
    return () => {
      window.removeEventListener("resize", updateProfile)
      mediaQuery.removeListener(updateProfile)
    }
  }, [])

  return profile
}
