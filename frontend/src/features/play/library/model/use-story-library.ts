import { useDeferredValue, useEffect, useMemo, useState } from "react"
import type { PublishedStoryCard, PublishedStoryListView, PublishedStoryThemeFacet } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorMessage } from "../../../../shared/lib/errors"

const PAGE_SIZE = 12

export function useStoryLibrary(
  initialStoryId?: string,
  searchQuery?: string,
  theme?: string | null,
  view: PublishedStoryListView = "accessible",
) {
  const api = useApiClient()
  const [stories, setStories] = useState<PublishedStoryCard[]>([])
  const [themeFacets, setThemeFacets] = useState<PublishedStoryThemeFacet[]>([])
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(initialStoryId ?? null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const deferredSearchQuery = useDeferredValue(searchQuery?.trim() ?? "")
  const deferredTheme = useDeferredValue(theme?.trim() ?? "")
  const deferredView = useDeferredValue(view)

  useEffect(() => {
    let active = true

    const loadStories = async () => {
      setLoading(true)
      try {
        const response = await api.listStories({
          q: deferredSearchQuery || undefined,
          theme: deferredTheme || undefined,
          view: deferredView,
          limit: PAGE_SIZE,
        })
        if (!active) {
          return
        }

        setStories(response.stories)
        setThemeFacets(response.facets?.themes ?? [])
        setTotal(response.meta?.total ?? response.stories.length)
        setHasMore(response.meta?.has_more ?? false)
        setNextCursor(response.meta?.next_cursor ?? null)
        setSelectedStoryId((current) => {
          const preferredStoryId = current ?? initialStoryId ?? response.stories[0]?.story_id ?? null
          if (!preferredStoryId) {
            return null
          }
          return response.stories.some((story) => story.story_id === preferredStoryId)
            ? preferredStoryId
            : response.stories[0]?.story_id ?? null
        })
        setError(null)
      } catch (nextError) {
        if (active) {
          setError(toErrorMessage(nextError))
          setStories([])
          setThemeFacets([])
          setTotal(0)
          setHasMore(false)
          setNextCursor(null)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadStories()

    return () => {
      active = false
    }
  }, [api, deferredSearchQuery, deferredTheme, deferredView, initialStoryId])

  const loadMore = async () => {
    if (!nextCursor || loading || loadingMore) {
      return
    }

    setLoadingMore(true)
    try {
      const response = await api.listStories({
        q: deferredSearchQuery || undefined,
        theme: deferredTheme || undefined,
        view: deferredView,
        limit: PAGE_SIZE,
        cursor: nextCursor,
      })

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
      setError(toErrorMessage(nextError))
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    if (initialStoryId) {
      setSelectedStoryId(initialStoryId)
    }
  }, [initialStoryId])

  const selectedStory = useMemo(() => {
    if (stories.length === 0) {
      return null
    }

    return stories.find((story) => story.story_id === selectedStoryId) ?? stories[0]
  }, [selectedStoryId, stories])

  return {
    stories,
    themeFacets,
    selectedStoryId: selectedStory?.story_id ?? null,
    selectedStory,
    loading,
    loadingMore,
    error,
    total,
    hasMore,
    query: deferredSearchQuery,
    theme: deferredTheme || null,
    view: deferredView,
    selectStory: setSelectedStoryId,
    loadMore,
  }
}
