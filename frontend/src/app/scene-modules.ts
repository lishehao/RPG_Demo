import { lazy } from "react"

export type SceneName =
  | "auth"
  | "create-story"
  | "author-loading"
  | "story-library"
  | "story-detail"
  | "play-session"

const loadAuthScene = () => import("../pages/auth/auth-page").then((module) => ({ default: module.AuthPage }))
const loadCreateStoryScene = () => import("../pages/authoring/create-story-page").then((module) => ({ default: module.CreateStoryPage }))
const loadAuthorLoadingScene = () => import("../pages/authoring/author-loading-page").then((module) => ({ default: module.AuthorLoadingPage }))
const loadStoryLibraryScene = () => import("../pages/play/story-library-page").then((module) => ({ default: module.StoryLibraryPage }))
const loadStoryDetailScene = () => import("../pages/play/story-detail-page").then((module) => ({ default: module.StoryDetailPage }))
const loadPlaySessionScene = () => import("../pages/play/play-session-page").then((module) => ({ default: module.PlaySessionPage }))

export const LazyAuthPage = lazy(loadAuthScene)
export const LazyCreateStoryPage = lazy(loadCreateStoryScene)
export const LazyAuthorLoadingPage = lazy(loadAuthorLoadingScene)
export const LazyStoryLibraryPage = lazy(loadStoryLibraryScene)
export const LazyStoryDetailPage = lazy(loadStoryDetailScene)
export const LazyPlaySessionPage = lazy(loadPlaySessionScene)

const sceneLoaders: Record<SceneName, () => Promise<unknown>> = {
  auth: loadAuthScene,
  "create-story": loadCreateStoryScene,
  "author-loading": loadAuthorLoadingScene,
  "story-library": loadStoryLibraryScene,
  "story-detail": loadStoryDetailScene,
  "play-session": loadPlaySessionScene,
}

const prefetchedScenes = new Map<SceneName, Promise<void>>()

export function prefetchScene(sceneName: SceneName): Promise<void> {
  const existing = prefetchedScenes.get(sceneName)
  if (existing) {
    return existing
  }

  const pending = sceneLoaders[sceneName]().then(() => undefined)
  prefetchedScenes.set(sceneName, pending)
  return pending
}
