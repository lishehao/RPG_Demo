import { useEffect, useState } from "react"
import type { PublishedStoryListView } from "../index"

export type AppRoute =
  | { name: "auth"; mode?: "login" | "register"; next?: string }
  | { name: "create-story" }
  | { name: "author-loading"; jobId: string }
  | { name: "story-library"; q?: string; theme?: string; view?: PublishedStoryListView }
  | { name: "story-detail"; storyId: string }
  | { name: "play-session"; sessionId: string }

export function parseHashRoute(hash: string): AppRoute {
  const raw = hash.replace(/^#/, "") || "/stories"
  const [pathname, search = ""] = raw.split("?")
  const segments = pathname.split("/").filter(Boolean)
  const params = new URLSearchParams(search)

  if (segments[0] === "auth") {
    const mode = params.get("mode")
    return {
      name: "auth",
      mode: mode === "register" ? "register" : "login",
      next: params.get("next") ?? undefined,
    }
  }

  if (segments[0] === "author-jobs" && segments[1]) {
    return { name: "author-loading", jobId: segments[1] }
  }

  if (segments[0] === "stories" && segments[1]) {
    return { name: "story-detail", storyId: segments[1] }
  }

  if (segments[0] === "stories") {
    return {
      name: "story-library",
      q: params.get("q") ?? undefined,
      theme: params.get("theme") ?? undefined,
      view: (params.get("view") as PublishedStoryListView | null) ?? undefined,
    }
  }

  if (segments[0] === "play" && segments[1] === "sessions" && segments[2]) {
    return { name: "play-session", sessionId: segments[2] }
  }

  return { name: "create-story" }
}

export function buildHash(route: AppRoute): string {
  switch (route.name) {
    case "auth": {
      const params = new URLSearchParams()
      if (route.mode) {
        params.set("mode", route.mode)
      }
      if (route.next) {
        params.set("next", route.next)
      }
      const query = params.toString()
      return query ? `#/auth?${query}` : "#/auth"
    }

    case "author-loading":
      return `#/author-jobs/${route.jobId}`

    case "story-library": {
      const params = new URLSearchParams()
      if (route.q) {
        params.set("q", route.q)
      }
      if (route.theme) {
        params.set("theme", route.theme)
      }
      if (route.view) {
        params.set("view", route.view)
      }
      const query = params.toString()
      return query ? `#/stories?${query}` : "#/stories"
    }

    case "story-detail":
      return `#/stories/${route.storyId}`

    case "play-session":
      return `#/play/sessions/${route.sessionId}`

    case "create-story":
      return "#/create-story"
  }
}

export function useAppRoute() {
  const [route, setRoute] = useState<AppRoute>(() => parseHashRoute(window.location.hash))

  useEffect(() => {
    const syncRoute = () => {
      setRoute(parseHashRoute(window.location.hash))
    }

    window.addEventListener("hashchange", syncRoute)
    window.addEventListener("popstate", syncRoute)

    if (!window.location.hash) {
      window.history.replaceState(null, "", buildHash({ name: "story-library" }))
      setRoute({ name: "story-library" })
    }

    return () => {
      window.removeEventListener("hashchange", syncRoute)
      window.removeEventListener("popstate", syncRoute)
    }
  }, [])

  const navigate = (nextRoute: AppRoute) => {
    const nextHash = buildHash(nextRoute)
    if (window.location.hash === nextHash) {
      setRoute(nextRoute)
      return
    }
    window.history.pushState(null, "", nextHash)
    setRoute(nextRoute)
  }

  return { route, navigate }
}
