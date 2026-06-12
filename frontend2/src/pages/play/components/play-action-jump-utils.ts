export function isPlayActionAreaAwayFromViewport(actionArea: HTMLElement): boolean {
  const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
  const rect = actionArea.getBoundingClientRect()
  const lowerComfortEdge = window.innerHeight - 132
  return (
    rect.top < headerHeight + 10 ||
    rect.top > lowerComfortEdge ||
    rect.bottom > window.innerHeight + 48
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
