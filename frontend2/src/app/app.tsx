import { useEffect } from "react"
import { ApiProvider } from "./api-context"
import { AuthProvider } from "./auth-context"
import { LanguageProvider } from "../shared/lib/i18n"
import { type AppRoute, useAppRoute } from "./routes"
import { HomePage } from "../pages/home/home-page"
import { CreatePage } from "../pages/create/create-page"
import { PlayPage } from "../pages/play/play-page"
import { PlayActionStateFixture } from "../pages/play/components/play-action-state-fixture"
import { PlayRetryFailureFixture } from "../pages/play/components/play-retry-recovery"
import { AboutPage } from "../pages/about/about-page"
import { LoginPage } from "../pages/auth/login-page"
import { ReplayPage } from "../pages/replay/replay-page"
import { TemplateDetailPage } from "../pages/world/world-detail-page"
import { PortfolioPage } from "../pages/portfolio/portfolio-page"
import { ReviewerPage } from "../pages/portfolio/reviewer-page"

function NotFoundRedirect({ navigate }: { navigate: (next: AppRoute) => void }) {
  useEffect(() => {
    navigate({ name: "home" })
  }, [navigate])
  return null
}

function routeFromLoginNext(next?: string): AppRoute {
  if (!next) return { name: "home" }
  const normalized = next.replace(/^#/, "").replace(/^\//, "")
  const [pathname, search = ""] = normalized.split("?")
  const segments = pathname.split("/").filter(Boolean)
  const params = new URLSearchParams(search)

  if (segments[0] === "create") return { name: "create" }
  if (segments[0] === "template" && segments[1]) {
    return { name: "template", templateId: segments[1] }
  }
  if (segments[0] === "play" && segments[1]) {
    return { name: "play", sessionId: segments[1], reviewer: params.get("reviewer") === "1" }
  }
  if (segments[0] === "replay" && segments[1]) {
    return { name: "replay", sessionId: segments[1] }
  }
  if (segments[0] === "reviewer") return { name: "reviewer" }
  if (segments[0] === "portfolio") return { name: "portfolio" }
  if (segments[0] === "about") return { name: "about" }
  return { name: "home" }
}

function renderRoute(route: AppRoute, navigate: (next: AppRoute) => void) {
  switch (route.name) {
    case "home":
      return (
        <HomePage
          onOpenCreate={() => navigate({ name: "create" })}
          onOpenPlay={(sessionId) => navigate({ name: "play", sessionId })}
        />
      )
    case "login":
      return (
        <LoginPage
          next={route.next}
          onBackHome={() => navigate({ name: "home" })}
          onOpenCreate={() => navigate({ name: "create" })}
          onLoggedIn={(next) => navigate(routeFromLoginNext(next))}
        />
      )
    case "create":
      return (
        <CreatePage
          onBackHome={() => navigate({ name: "home" })}
          onSessionStarted={(sessionId) => navigate({ name: "play", sessionId })}
        />
      )
    case "playActionFixture":
      return <PlayActionStateFixture onBackHome={() => navigate({ name: "home" })} />
    case "playRetryFixture":
      return <PlayRetryFailureFixture onBackHome={() => navigate({ name: "home" })} />
    case "template":
      return (
        <TemplateDetailPage
          templateId={route.templateId}
          onBackHome={() => navigate({ name: "home" })}
          onOpenCreate={() => navigate({ name: "create" })}
          onSessionStarted={(sessionId) => navigate({ name: "play", sessionId })}
        />
      )
    case "play":
      return (
        <PlayPage
          sessionId={route.sessionId}
          reviewerMode={route.reviewer}
          onBackHome={() => navigate({ name: "home" })}
        />
      )
    case "replay":
      return (
        <ReplayPage
          sessionId={route.sessionId}
          onBackHome={() => navigate({ name: "home" })}
          onOpenTemplate={(templateId) => navigate({ name: "template", templateId })}
        />
      )
    case "portfolio":
      return (
        <PortfolioPage
          onBackHome={() => navigate({ name: "home" })}
          onOpenCreate={() => navigate({ name: "create" })}
          onOpenReviewer={() => navigate({ name: "reviewer" })}
        />
      )
    case "reviewer":
      return (
        <ReviewerPage
          onBackHome={() => navigate({ name: "home" })}
          onOpenCreate={() => navigate({ name: "create" })}
          onSessionStarted={(sessionId) => navigate({ name: "play", sessionId, reviewer: true })}
        />
      )
    case "about":
      return (
        <AboutPage
          onBackHome={() => navigate({ name: "home" })}
          onOpenCreate={() => navigate({ name: "create" })}
        />
      )
  }
  return <NotFoundRedirect navigate={navigate} />
}

function routeKey(route: AppRoute): string {
  switch (route.name) {
    case "home": return "home"
    case "login": return "login"
    case "create": return "create"
    case "playActionFixture": return "playActionFixture"
    case "playRetryFixture": return "playRetryFixture"
    case "about": return "about"
    case "portfolio": return "portfolio"
    case "reviewer": return "reviewer"
    case "template": return `template:${route.templateId}`
    case "play": return route.reviewer ? `play:${route.sessionId}:reviewer` : `play:${route.sessionId}`
    case "replay": return `replay:${route.sessionId}`
  }
}

function Router() {
  const { route, navigate } = useAppRoute()
  const key = routeKey(route)
  // Reset scroll on every navigation. AnimatePresence handles the
  // mount/unmount choreography but doesn't touch window scroll, so
  // routes can land on a non-zero scroll position from the previous
  // page and feel jarring. Keying on routeKey runs once per real
  // route change, not on every render of the same page.
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" })
  }, [key])
  // Route changes intentionally skip exit animation. The previous
  // `AnimatePresence`/`popLayout` version looked smoother, but left
  // invisible old route controls in the browser-visible DOM. Immediate
  // unmount keeps click and accessibility targeting deterministic.
  return (
    <div key={key}>
      {renderRoute(route, navigate)}
    </div>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      <ApiProvider>
        <AuthProvider>
          <Router />
        </AuthProvider>
      </ApiProvider>
    </LanguageProvider>
  )
}
