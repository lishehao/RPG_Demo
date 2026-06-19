export function isPlayActionAreaAwayFromViewport(actionArea: HTMLElement): boolean {
  const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
  const rect = actionArea.getBoundingClientRect()
  const upperComfortEdge = headerHeight + 64
  const lowerComfortEdge = window.innerHeight - 24
  return (
    rect.bottom < upperComfortEdge ||
    rect.top > lowerComfortEdge
  )
}

export function scrollToPlayActionArea() {
  if (typeof document === "undefined") return
  const actionArea = document.querySelector<HTMLElement>("[data-play-action-area='true']")
  if (!actionArea) return
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const scrollActionIntoView = (behavior: ScrollBehavior) => {
    const rect = actionArea.getBoundingClientRect()
    const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
    const centerOffset = Math.max(
      headerHeight + 16,
      Math.round((window.innerHeight - Math.min(rect.height, window.innerHeight * 0.72)) / 2),
    )
    const top = Math.max(0, window.scrollY + rect.top - centerOffset)
    window.scrollTo({ top, left: 0, behavior })
  }

  scrollActionIntoView(prefersReducedMotion ? "auto" : "smooth")
  window.setTimeout(() => {
    if (isPlayActionAreaAwayFromViewport(actionArea)) {
      scrollActionIntoView("auto")
    }
  }, prefersReducedMotion ? 0 : 320)
}

export function scrollToPlayImpactSummaryOrAction() {
  if (typeof document === "undefined") return
  const impactSummary = document.querySelector<HTMLElement>("[data-gameplay-impact-summary='true']")
  if (!impactSummary) {
    scrollToPlayActionArea()
    return
  }
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
  const comfortOffset = headerHeight + 16
  const scrollImpactIntoView = (behavior: ScrollBehavior) => {
    const rect = impactSummary.getBoundingClientRect()
    const top = Math.max(0, window.scrollY + rect.top - comfortOffset)
    window.scrollTo({ top, left: 0, behavior })
  }

  scrollImpactIntoView(prefersReducedMotion ? "auto" : "smooth")
  window.setTimeout(() => {
    const rect = impactSummary.getBoundingClientRect()
    if (rect.top < comfortOffset - 8 || rect.top > window.innerHeight * 0.42) {
      scrollImpactIntoView("auto")
    }
  }, prefersReducedMotion ? 0 : 320)
}
