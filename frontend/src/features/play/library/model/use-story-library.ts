import { useDeferredValue, useEffect, useRef, useState } from "react"
import type { PublishedStoryCard, PublishedStoryListView, PublishedStoryThemeFacet, StoryLanguage } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { isAbortError, toErrorMessage } from "../../../../shared/lib/errors"
import { readCachedValue, writeCachedValue } from "../../../../shared/lib/resource-cache"

const PAGE_SIZE = 12
const LIBRARY_CACHE_TTL_MS = 60_000

type CachedLibraryPage = {
  stories: PublishedStoryCard[]
  themeFacets: PublishedStoryThemeFacet[]
  total: number
  hasMore: boolean
  nextCursor: string | null
}

const LIBRARY_PAGE_CACHE = new Map<string, { value: CachedLibraryPage; expiresAt: number }>()

function libraryCacheKey({
  language,
  query,
  theme,
  view,
  cursor,
}: {
  language: StoryLanguage
  query: string
  theme: string
  view: PublishedStoryListView
  cursor?: string | null
}) {
  return JSON.stringify({
    language,
    query,
    theme,
    view,
    cursor: cursor ?? null,
    limit: PAGE_SIZE,
  })
}

export function useStoryLibrary(
  language: StoryLanguage,
  searchQuery?: string,
  theme?: string | null,
  view: PublishedStoryListView = "accessible",
) {
  const api = useApiClient()
  const [stories, setStories] = useState<PublishedStoryCard[]>([])
  const [themeFacets, setThemeFacets] = useState<PublishedStoryThemeFacet[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const hasLoadedOnceRef = useRef(false)
  const deferredSearchQuery = useDeferredValue(searchQuery?.trim() ?? "")
  const deferredTheme = useDeferredValue(theme?.trim() ?? "")
  const deferredView = useDeferredValue(view)

  useEffect(() => {
    let active = true
    const abortController = new AbortController()

    const loadStories = async () => {
      const cacheKey = libraryCacheKey({
        language,
        query: deferredSearchQuery,
        theme: deferredTheme,
        view: deferredView,
      })
      const cached = readCachedValue(LIBRARY_PAGE_CACHE, cacheKey)
      if (cached) {
        setStories(cached.stories)
        setThemeFacets(cached.themeFacets)
        setTotal(cached.total)
        setHasMore(cached.hasMore)
        setNextCursor(cached.nextCursor)
        setError(null)
        setLoading(false)
        setRefreshing(hasLoadedOnceRef.current)
        hasLoadedOnceRef.current = true
      } else {
        setLoading(!hasLoadedOnceRef.current)
        setRefreshing(hasLoadedOnceRef.current)
      }

      try {
        const response = await api.listStories({
          language,
          q: deferredSearchQuery || undefined,
          theme: deferredTheme || undefined,
          view: deferredView,
          limit: PAGE_SIZE,
        }, { signal: abortController.signal })
        if (!active) {
          return
        }

        writeCachedValue(
          LIBRARY_PAGE_CACHE,
          cacheKey,
          {
            stories: response.stories,
            themeFacets: response.facets?.themes ?? [],
            total: response.meta?.total ?? response.stories.length,
            hasMore: response.meta?.has_more ?? false,
            nextCursor: response.meta?.next_cursor ?? null,
          },
          LIBRARY_CACHE_TTL_MS,
        )
        setStories(response.stories)
        setThemeFacets(response.facets?.themes ?? [])
        setTotal(response.meta?.total ?? response.stories.length)
        setHasMore(response.meta?.has_more ?? false)
        setNextCursor(response.meta?.next_cursor ?? null)
        setError(null)
        hasLoadedOnceRef.current = true
      } catch (nextError) {
        if (isAbortError(nextError)) {
          return
        }
        if (active) {
          setError(toErrorMessage(nextError, language))
          if (!hasLoadedOnceRef.current) {
            setStories([])
            setThemeFacets([])
            setTotal(0)
            setHasMore(false)
            setNextCursor(null)
          }
        }
      } finally {
        if (active) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    }

    void loadStories()

    return () => {
      active = false
      abortController.abort()
    }
  }, [api, deferredSearchQuery, deferredTheme, deferredView, language])

  const loadMore = async () => {
    if (!nextCursor || loading || loadingMore) {
      return
    }

    setLoadingMore(true)
    try {
      const cacheKey = libraryCacheKey({
        language,
        query: deferredSearchQuery,
        theme: deferredTheme,
        view: deferredView,
        cursor: nextCursor,
      })
      const cached = readCachedValue(LIBRARY_PAGE_CACHE, cacheKey)
      const response = cached
        ? {
            stories: cached.stories,
            meta: {
              total: cached.total,
              has_more: cached.hasMore,
              next_cursor: cached.nextCursor,
            },
          }
        : await api.listStories({
            language,
            q: deferredSearchQuery || undefined,
            theme: deferredTheme || undefined,
            view: deferredView,
            limit: PAGE_SIZE,
            cursor: nextCursor,
          })
      if (!cached) {
        writeCachedValue(
          LIBRARY_PAGE_CACHE,
          cacheKey,
          {
            stories: response.stories,
            themeFacets,
            total: response.meta?.total ?? total,
            hasMore: response.meta?.has_more ?? false,
            nextCursor: response.meta?.next_cursor ?? null,
          },
          LIBRARY_CACHE_TTL_MS,
        )
      }

      setStories((currentStories) => {
        const storyIds = new Set(currentStories.map((story) => story.story_id))
        const appendedStories = response.stories.filter((story) => !storyIds.has(story.story_id))
        return [...currentStories, ...appendedStories]
      })
      setHasMore(response.meta?.has_more ?? false)
      setNextCursor(response.meta?.next_cursor ?? null)
      setTotal(response.meta?.total ?? total)
      setError(null)
    } catch (nextError) {
      setError(toErrorMessage(nextError, language))
    } finally {
      setLoadingMore(false)
    }
  }

  return {
    stories,
    themeFacets,
    loading,
    refreshing,
    loadingMore,
    error,
    total,
    hasMore,
    query: deferredSearchQuery,
    theme: deferredTheme || null,
    view: deferredView,
    loadMore,
  }
}
