import { Suspense, useEffect, useMemo, useState } from "react"
import { getDefaultApiClient } from "./config/api-client"
import { AuthProvider, useAuth } from "./providers/auth-provider"
import { ApiClientProvider } from "./providers/api-client-provider"
import { buildHash, parseHashRoute, type AppRoute, useAppRoute } from "./routes"
import { LazyAuthPage, LazyAuthorLoadingPage, LazyCreateStoryPage, LazyPlaySessionPage, LazyStoryDetailPage, LazyStoryLibraryPage, prefetchScene } from "./scene-modules"
import type { PublishedStoryListView, StoryLanguage } from "../index"
import { AppShell } from "../shared/ui/app-shell"
import { SceneLoadingShell } from "../shared/ui/scene-loading-shell"
import { readStoredUiLanguage, uiText, writeStoredUiLanguage } from "../shared/lib/ui-language"
import { prefetchStoryDetail } from "../features/play/story-detail/model/use-story-detail"
import { AppHeader } from "../widgets/chrome/app-header"

function sceneKeyFor(route: AppRoute) {
  switch (route.name) {
    case "author-loading":
      return `author-loading:${route.jobId}`
    case "story-detail":
      return `story-detail:${route.storyId}`
    case "play-session":
      return `play-session:${route.sessionId}`
    default:
      return route.name
  }
}

function AppScene({
  route,
  uiLanguage,
  onUiLanguageChange,
  navigate,
  librarySearchQuery,
  libraryTheme,
  libraryView,
  openLibrary,
  onLibrarySearchChange,
  onLibraryThemeChange,
  onLibraryViewChange,
  authenticated,
  onRequireAuth,
  onResolveAuth,
  onPrefetchAuthorLoading,
  onPrefetchCreateStory,
  onPrefetchPlaySession,
  onPrefetchStoryDetail,
  onCreateDraftStateChange,
}: {
  route: AppRoute
  uiLanguage: StoryLanguage
  onUiLanguageChange: (language: StoryLanguage) => void
  navigate: (nextRoute: AppRoute) => void
  librarySearchQuery: string
  libraryTheme: string | null
  libraryView: PublishedStoryListView
  openLibrary: (options?: { preserveFilters?: boolean }) => void
  onLibrarySearchChange: (value: string) => void
  onLibraryThemeChange: (theme: string | null, queryOverride?: string) => void
  onLibraryViewChange: (view: PublishedStoryListView, queryOverride?: string) => void
  authenticated: boolean
  onRequireAuth: (nextHash: string, mode?: "login" | "register") => void
  onResolveAuth: (nextHash?: string) => void
  onPrefetchAuthorLoading: () => void
  onPrefetchCreateStory: () => void
  onPrefetchPlaySession: () => void
  onPrefetchStoryDetail: (storyId: string) => void
  onCreateDraftStateChange: (isDirty: boolean) => void
}) {
  switch (route.name) {
    case "auth":
      return (
        <LazyAuthPage
          uiLanguage={uiLanguage}
          mode={route.mode ?? "login"}
          nextHash={route.next}
          onModeChange={(mode) => navigate({ name: "auth", mode, next: route.next })}
          onOpenLibrary={() => openLibrary({ preserveFilters: true })}
          onResolveAuth={onResolveAuth}
        />
      )

    case "create-story":
      return (
        <LazyCreateStoryPage
          key={`create-story:${uiLanguage}`}
          uiLanguage={uiLanguage}
          onOpenAuthorJob={(jobId) => navigate({ name: "author-loading", jobId })}
          onOpenLibrary={() => openLibrary({ preserveFilters: true })}
          onPrefetchAuthorLoading={onPrefetchAuthorLoading}
          onDraftStateChange={onCreateDraftStateChange}
        />
      )

    case "author-loading":
      return (
        <LazyAuthorLoadingPage
          jobId={route.jobId}
          uiLanguage={uiLanguage}
          onOpenStoryDetail={(storyId) => navigate({ name: "story-detail", storyId })}
        />
      )

    case "story-library":
      return (
        <LazyStoryLibraryPage
          authenticated={authenticated}
          uiLanguage={uiLanguage}
          searchQuery={librarySearchQuery}
          selectedTheme={libraryTheme}
          selectedView={libraryView}
          onOpenCreateStory={() => navigate({ name: "create-story" })}
          onRequireAuth={() => onRequireAuth(buildHash({ name: "create-story" }))}
          onOpenStoryDetail={(storyId) => navigate({ name: "story-detail", storyId })}
          onPrefetchCreateStory={onPrefetchCreateStory}
          onPrefetchStoryDetail={onPrefetchStoryDetail}
          onSearchChange={onLibrarySearchChange}
          onThemeChange={onLibraryThemeChange}
          onViewChange={onLibraryViewChange}
        />
      )

    case "story-detail":
      return (
        <LazyStoryDetailPage
          isAuthenticated={authenticated}
          storyId={route.storyId}
          uiLanguage={uiLanguage}
          onUiLanguageChange={onUiLanguageChange}
          onOpenLibrary={() => openLibrary({ preserveFilters: true })}
          onDeleteToLibrary={() => openLibrary({ preserveFilters: true })}
          onOpenPlaySession={(sessionId) => navigate({ name: "play-session", sessionId })}
          onPrefetchPlaySession={authenticated ? onPrefetchPlaySession : () => {
            void prefetchScene("auth")
          }}
          onRequireAuth={() => onRequireAuth(buildHash({ name: "story-detail", storyId: route.storyId }))}
        />
      )

    case "play-session":
      return (
        <LazyPlaySessionPage
          sessionId={route.sessionId}
          uiLanguage={uiLanguage}
          onUiLanguageChange={onUiLanguageChange}
          onOpenLibrary={() => openLibrary({ preserveFilters: true })}
        />
      )
  }
}

function AppInner() {
  const auth = useAuth()
  const client = useMemo(() => getDefaultApiClient(), [])
  const { route, navigate } = useAppRoute()
  const [uiLanguage, setUiLanguage] = useState<StoryLanguage>(() => readStoredUiLanguage())
  const [librarySearchQuery, setLibrarySearchQuery] = useState(route.name === "story-library" ? route.q ?? "" : "")
  const [libraryTheme, setLibraryTheme] = useState<string | null>(route.name === "story-library" ? route.theme ?? null : null)
  const [libraryView, setLibraryView] = useState<PublishedStoryListView>(route.name === "story-library" ? route.view ?? (auth.authenticated ? "accessible" : "public") : (auth.authenticated ? "accessible" : "public"))
  const [isCreateDraftDirty, setIsCreateDraftDirty] = useState(false)
  const effectiveLibraryView: PublishedStoryListView = auth.authenticated ? libraryView : "public"

  useEffect(() => {
    const schedule = window.setTimeout(() => {
      if (route.name === "story-library") {
        void prefetchScene("create-story")
        void prefetchScene("story-detail")
      } else if (route.name === "create-story") {
        void prefetchScene("author-loading")
      } else if (route.name === "story-detail") {
        void prefetchScene("play-session")
      } else if (route.name === "auth") {
        void prefetchScene("story-library")
      }
    }, 180)

    return () => {
      window.clearTimeout(schedule)
    }
  }, [route.name])

  useEffect(() => {
    writeStoredUiLanguage(uiLanguage)
  }, [uiLanguage])

  useEffect(() => {
    if (route.name !== "story-library") {
      return
    }
    setLibrarySearchQuery(route.q ?? "")
    setLibraryTheme(route.theme ?? null)
    setLibraryView(route.view ?? (auth.authenticated ? "accessible" : "public"))
  }, [auth.authenticated, route])

  useEffect(() => {
    if (route.name !== "create-story") {
      setIsCreateDraftDirty(false)
    }
  }, [route.name])

  useEffect(() => {
    if (auth.loading || auth.authenticated) {
      return
    }
    if (route.name === "create-story" || route.name === "author-loading" || route.name === "play-session") {
      navigate({
        name: "auth",
        mode: "login",
        next: buildHash(route),
      })
    }
  }, [auth.authenticated, auth.loading, navigate, route])

  useEffect(() => {
    if (auth.loading || !auth.authenticated || route.name !== "auth") {
      return
    }
    resolveAuth(route.name === "auth" ? route.next : undefined)
  }, [auth.authenticated, auth.loading, route])

  const openLibrary = (options?: { preserveFilters?: boolean }) => {
    const preserveFilters = options?.preserveFilters ?? true
    navigate({
      name: "story-library",
      q: preserveFilters ? librarySearchQuery.trim() || undefined : undefined,
      theme: preserveFilters ? libraryTheme ?? undefined : undefined,
      view: preserveFilters ? effectiveLibraryView : (auth.authenticated ? "accessible" : "public"),
    })
  }

  const openAuth = (mode: "login" | "register", nextHash?: string) => {
    navigate({
      name: "auth",
      mode,
      next: nextHash,
    })
  }

  const resolveAuth = (nextHash?: string) => {
    navigate(parseHashRoute(nextHash || buildHash({ name: "story-library", view: "accessible" })))
  }

  const handleLibrarySearchChange = (value: string) => {
    setLibrarySearchQuery(value)
    const normalizedQuery = value.trim()
    const nextTheme = libraryTheme ?? undefined
    navigate({
      name: "story-library",
      q: normalizedQuery || undefined,
      theme: nextTheme,
      view: effectiveLibraryView,
    })
  }

  const handleLibraryThemeChange = (theme: string | null, queryOverride?: string) => {
    setLibraryTheme(theme)
    const normalizedQuery = (queryOverride ?? librarySearchQuery).trim()
    navigate({
      name: "story-library",
      q: normalizedQuery || undefined,
      theme: theme ?? undefined,
      view: effectiveLibraryView,
    })
  }

  const handleLibraryViewChange = (view: PublishedStoryListView, queryOverride?: string) => {
    const normalizedQuery = (queryOverride ?? librarySearchQuery).trim()
    if (!auth.authenticated) {
      setLibraryView("public")
      navigate({
        name: "story-library",
        q: normalizedQuery || undefined,
        theme: libraryTheme ?? undefined,
        view: "public",
      })
      return
    }
    setLibraryView(view)
    navigate({
      name: "story-library",
      q: normalizedQuery || undefined,
      theme: libraryTheme ?? undefined,
      view,
    })
  }

  const handleOpenCreateStory = () => {
    if (auth.authenticated) {
      navigate({ name: "create-story" })
      return
    }
    openAuth("login", buildHash({ name: "create-story" }))
  }

  const handleLogout = async () => {
    await auth.logout()
    if (route.name === "create-story" || route.name === "author-loading" || route.name === "play-session") {
      openLibrary({ preserveFilters: false })
    }
  }

  const handleUiLanguageChange = (nextLanguage: StoryLanguage) => {
    if (nextLanguage === uiLanguage) {
      return
    }

    if (route.name !== "create-story") {
      setUiLanguage(nextLanguage)
      return
    }

    if (!isCreateDraftDirty) {
      setUiLanguage(nextLanguage)
      return
    }

    const confirmed = window.confirm(
      uiText(uiLanguage, {
        en: "Switching language will clear the current seed and preview. Continue?",
        zh: "切换语言会清空当前的种子和预览。要继续吗？",
      }),
    )

    if (confirmed) {
      setUiLanguage(nextLanguage)
    }
  }

  return (
    <ApiClientProvider client={client}>
      <AppShell>
        <AppHeader
          authenticated={auth.authenticated}
          authLoading={auth.loading}
          user={auth.user}
          onLogout={() => {
            void handleLogout()
          }}
          onOpenAuth={openAuth}
          routeName={route.name}
          uiLanguage={uiLanguage}
          onUiLanguageChange={handleUiLanguageChange}
          onOpenCreateStory={handleOpenCreateStory}
          onOpenLibrary={() => openLibrary({ preserveFilters: true })}
          onPrefetchAuth={() => {
            void prefetchScene("auth")
          }}
          onPrefetchCreateStory={() => {
            void prefetchScene("create-story")
          }}
          onPrefetchLibrary={() => {
            void prefetchScene("story-library")
          }}
        />
        <Suspense fallback={<SceneLoadingShell routeName={route.name} uiLanguage={uiLanguage} />}>
          <div className="studio-scene" data-route={route.name} key={sceneKeyFor(route)}>
            <AppScene
              authenticated={auth.authenticated}
              uiLanguage={uiLanguage}
              onUiLanguageChange={handleUiLanguageChange}
              librarySearchQuery={librarySearchQuery}
              libraryTheme={libraryTheme}
              libraryView={effectiveLibraryView}
              navigate={navigate}
              onLibrarySearchChange={handleLibrarySearchChange}
              onLibraryThemeChange={handleLibraryThemeChange}
              onLibraryViewChange={handleLibraryViewChange}
              onPrefetchAuthorLoading={() => {
                void prefetchScene("author-loading")
              }}
              onPrefetchCreateStory={() => {
                void prefetchScene("create-story")
              }}
              onPrefetchPlaySession={() => {
                void prefetchScene("play-session")
              }}
              onPrefetchStoryDetail={(storyId) => {
                void prefetchScene("story-detail")
                void prefetchStoryDetail(client, storyId)
              }}
              onCreateDraftStateChange={setIsCreateDraftDirty}
              onRequireAuth={(nextHash, mode = "login") => openAuth(mode, nextHash)}
              onResolveAuth={resolveAuth}
              openLibrary={openLibrary}
              route={route}
            />
          </div>
        </Suspense>
      </AppShell>
    </ApiClientProvider>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  )
}
