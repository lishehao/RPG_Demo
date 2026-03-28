import { useCallback, useEffect, useRef, useState } from "react"
import { prefersReducedMotionNow } from "./motion"

type ReadingSection<TSection extends string> = {
  id: string
  value: TSection
}

function getReadingLineOffset() {
  const topbar = document.querySelector(".studio-topbar") as HTMLElement | null
  const stickyHeaderBottom = topbar ? topbar.getBoundingClientRect().height : window.innerWidth <= 720 ? 72 : 78
  return stickyHeaderBottom + (window.innerWidth <= 720 ? 20 : 32)
}

export function useReadingSection<TSection extends string>(
  sections: ReadingSection<TSection>[],
  initialSection: TSection,
) {
  const [activeSection, setActiveSection] = useState<TSection>(initialSection)
  const rafRef = useRef<number | null>(null)
  const pendingSectionRef = useRef<{ id: string; value: TSection; expiresAt: number } | null>(null)

  const updateActiveSection = useCallback(() => {
    if (sections.length === 0) {
      return
    }

    const readingLine = getReadingLineOffset()
    const documentHeight = document.documentElement.scrollHeight
    const nearPageBottom = window.innerHeight + window.scrollY >= documentHeight - 48

    if (nearPageBottom) {
      const lastSection = sections[sections.length - 1]
      pendingSectionRef.current = null
      setActiveSection(lastSection.value)
      return
    }

    const pendingSection = pendingSectionRef.current
    if (pendingSection) {
      const pendingTarget = document.getElementById(pendingSection.id)
      if (pendingTarget) {
        const distanceFromReadingLine = Math.abs(pendingTarget.getBoundingClientRect().top - readingLine)
        if (distanceFromReadingLine <= 24) {
          pendingSectionRef.current = null
          setActiveSection(pendingSection.value)
          return
        }
      }

      if (pendingSection.expiresAt > Date.now()) {
        setActiveSection(pendingSection.value)
        return
      }

      pendingSectionRef.current = null
    }

    let nextSection = sections[0].value

    for (const section of sections) {
      const node = document.getElementById(section.id)
      if (!node) {
        continue
      }

      if (node.getBoundingClientRect().top <= readingLine + 24) {
        nextSection = section.value
        continue
      }

      break
    }

    setActiveSection((current) => (current === nextSection ? current : nextSection))
  }, [sections])

  useEffect(() => {
    const scheduleUpdate = () => {
      if (rafRef.current !== null) {
        return
      }

      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = null
        updateActiveSection()
      })
    }

    const timeoutId = window.setTimeout(updateActiveSection, 160)
    const intervalId = window.setInterval(updateActiveSection, 240)

    updateActiveSection()
    window.addEventListener("scroll", scheduleUpdate, { passive: true })
    document.addEventListener("scroll", scheduleUpdate, { capture: true, passive: true })
    window.addEventListener("resize", scheduleUpdate)

    return () => {
      window.removeEventListener("scroll", scheduleUpdate)
      document.removeEventListener("scroll", scheduleUpdate, true)
      window.removeEventListener("resize", scheduleUpdate)
      window.clearTimeout(timeoutId)
      window.clearInterval(intervalId)
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current)
      }
    }
  }, [updateActiveSection])

  const jumpToSection = useCallback((targetId: string, targetSection: TSection) => {
    pendingSectionRef.current = {
      id: targetId,
      value: targetSection,
      expiresAt: Date.now() + 1400,
    }
    setActiveSection(targetSection)
    document
      .getElementById(targetId)
      ?.scrollIntoView({ behavior: prefersReducedMotionNow() ? "auto" : "smooth", block: "start" })
  }, [])

  return {
    activeSection,
    jumpToSection,
  }
}
