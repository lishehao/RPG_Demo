import { useEffect, useRef, useState } from "react"

export type AppRoute =
  | { name: "home" }
  | { name: "login"; next?: string }
  | { name: "create" }
  | { name: "homeStartFixture" }
  | { name: "playAdvisorFixture" }
  | { name: "playActionFixture"; scenario?: "long-history" }
  | { name: "playEndingFixture" }
  | { name: "playGameplayLoopFixture" }
  | { name: "playLeverageFixture" }
  | { name: "playReviewerEvidenceFixture" }
  | { name: "playRetryFixture" }
  | { name: "replayFixture"; view?: "full" }
  | { name: "template"; templateId: string }
  | { name: "play"; sessionId: string; reviewer?: boolean }
  | { name: "replay"; sessionId: string; view?: "full" }
  | { name: "portfolio" }
  | { name: "reviewer" }
  | { name: "publicReviewerDemo" }
  | { name: "about" }

export type NavDirection = "forward" | "backward"

// Where each route sits in the conceptual depth tree. The router
// uses this to decide whether a transition is "going deeper" (forward
// = slide-up) or "going back" (backward = slide-down). Without this,
// every page transition was the same y: 8 nudge regardless of where
// the user was heading.
const ROUTE_DEPTH: Record<AppRoute["name"], number> = {
  home: 0,
  about: 1,
  login: 1,
  create: 1,
  homeStartFixture: 1,
  replay: 1,
  portfolio: 1,
  reviewer: 1,
  publicReviewerDemo: 1,
  playAdvisorFixture: 1,
  playActionFixture: 1,
  playEndingFixture: 1,
  playGameplayLoopFixture: 1,
  playLeverageFixture: 1,
  playReviewerEvidenceFixture: 1,
  playRetryFixture: 1,
  replayFixture: 1,
  template: 1,
  play: 2,
}

function allowsLocalQaRoute(): boolean {
  if (import.meta.env.DEV) return true
  const host = window.location.hostname
  return host === "localhost" || host === "127.0.0.1" || host === "::1"
}

function depthOf(route: AppRoute): number {
  return ROUTE_DEPTH[route.name] ?? 0
}

function parseRoute(hash: string): AppRoute {
  const raw = hash.replace(/^#/, "") || "/"
  const [pathname, search = ""] = raw.split("?")
  const segments = pathname.split("/").filter(Boolean)
  const params = new URLSearchParams(search)

  if (segments.length === 0) {
    return { name: "home" }
  }
  if (segments[0] === "login") {
    return { name: "login", next: params.get("next") ?? undefined }
  }
  if (segments[0] === "create") {
    return { name: "create" }
  }
  if (segments[0] === "qa" && allowsLocalQaRoute()) {
    if (segments[1] === "home-start") return { name: "homeStartFixture" }
    if (segments[1] === "play-advisor") return { name: "playAdvisorFixture" }
    if (segments[1] === "play-action") {
      return {
        name: "playActionFixture",
        scenario: params.get("scenario") === "long-history" ? "long-history" : undefined,
      }
    }
    if (segments[1] === "play-ending") return { name: "playEndingFixture" }
    if (segments[1] === "play-gameplay-loop") return { name: "playGameplayLoopFixture" }
    if (segments[1] === "play-leverage") return { name: "playLeverageFixture" }
    if (segments[1] === "play-reviewer-evidence") return { name: "playReviewerEvidenceFixture" }
    if (segments[1] === "play-retry") return { name: "playRetryFixture" }
    if (segments[1] === "replay") {
      return { name: "replayFixture", view: params.get("view") === "full" ? "full" : undefined }
    }
  }
  if (segments[0] === "template" && segments[1]) {
    return { name: "template", templateId: segments[1] }
  }
  if (segments[0] === "play" && segments[1]) {
    return { name: "play", sessionId: segments[1], reviewer: params.get("reviewer") === "1" }
  }
  if (segments[0] === "replay" && segments[1]) {
    return {
      name: "replay",
      sessionId: segments[1],
      view: params.get("view") === "full" ? "full" : undefined,
    }
  }
  if (segments[0] === "portfolio") {
    return { name: "portfolio" }
  }
  if (segments[0] === "reviewer") {
    return { name: "reviewer" }
  }
  if (segments[0] === "demo" && segments[1] === "reviewer") {
    return { name: "publicReviewerDemo" }
  }
  if (segments[0] === "about") {
    return { name: "about" }
  }
  return { name: "home" }
}

export function buildHash(route: AppRoute): string {
  switch (route.name) {
    case "home":
      return "#/"
    case "login": {
      if (route.next) {
        const params = new URLSearchParams({ next: route.next })
        return `#/login?${params.toString()}`
      }
      return "#/login"
    }
    case "create":
      return "#/create"
    case "homeStartFixture":
      return "#/qa/home-start"
    case "playAdvisorFixture":
      return "#/qa/play-advisor"
    case "playActionFixture":
      if (route.scenario === "long-history") return "#/qa/play-action?scenario=long-history"
      return "#/qa/play-action"
    case "playEndingFixture":
      return "#/qa/play-ending"
    case "playGameplayLoopFixture":
      return "#/qa/play-gameplay-loop"
    case "playLeverageFixture":
      return "#/qa/play-leverage"
    case "playReviewerEvidenceFixture":
      return "#/qa/play-reviewer-evidence"
    case "playRetryFixture":
      return "#/qa/play-retry"
    case "replayFixture":
      return route.view === "full" ? "#/qa/replay?view=full" : "#/qa/replay"
    case "template":
      return `#/template/${route.templateId}`
    case "play":
      return route.reviewer
        ? `#/play/${route.sessionId}?reviewer=1`
        : `#/play/${route.sessionId}`
    case "replay":
      return route.view === "full"
        ? `#/replay/${route.sessionId}?view=full`
        : `#/replay/${route.sessionId}`
    case "portfolio":
      return "#/portfolio"
    case "reviewer":
      return "#/reviewer"
    case "publicReviewerDemo":
      return "#/demo/reviewer"
    case "about":
      return "#/about"
  }
}

export function useAppRoute() {
  const [route, setRoute] = useState<AppRoute>(() => parseRoute(window.location.hash))
  const [direction, setDirection] = useState<NavDirection>("forward")
  const prevRouteRef = useRef<AppRoute>(route)

  useEffect(() => {
    const onChange = () => {
      const next = parseRoute(window.location.hash)
      const prev = prevRouteRef.current
      // Same-name navigation (e.g. play/A → play/B) reads as
      // "forward" — switching sessions feels like a step into a
      // new run, not a step back.
      if (depthOf(next) >= depthOf(prev)) {
        setDirection("forward")
      } else {
        setDirection("backward")
      }
      prevRouteRef.current = next
      setRoute(next)
    }
    window.addEventListener("hashchange", onChange)
    if (!window.location.hash) {
      window.history.replaceState(null, "", buildHash({ name: "home" }))
      setRoute({ name: "home" })
      prevRouteRef.current = { name: "home" }
    }
    return () => window.removeEventListener("hashchange", onChange)
  }, [])

  const navigate = (next: AppRoute) => {
    const nextHash = buildHash(next)
    if (window.location.hash === nextHash) {
      setRoute(next)
      return
    }
    window.location.hash = nextHash
  }

  return { route, navigate, direction }
}
