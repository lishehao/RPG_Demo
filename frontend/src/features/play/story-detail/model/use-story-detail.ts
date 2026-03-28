import { useEffect, useState } from "react"
import type { PublishedStoryDetailResponse, StoryLanguage, StoryVisibility } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import type { FrontendApiClient } from "../../../../api/http-client"
import { isAbortError, toErrorMessage } from "../../../../shared/lib/errors"
import { deleteCachedValue, readCachedValue, writeCachedValue } from "../../../../shared/lib/resource-cache"

const STORY_DETAIL_CACHE_TTL_MS = 60_000
const STORY_DETAIL_CACHE = new Map<string, { value: PublishedStoryDetailResponse; expiresAt: number }>()

export async function prefetchStoryDetail(api: FrontendApiClient, storyId: string) {
  const cached = readCachedValue(STORY_DETAIL_CACHE, storyId)
  if (cached) {
    return cached
  }
  const detail = await api.getStory(storyId)
  writeCachedValue(STORY_DETAIL_CACHE, storyId, detail, STORY_DETAIL_CACHE_TTL_MS)
  return detail
}

export function useStoryDetail(storyId: string, uiLanguage: StoryLanguage) {
  const api = useApiClient()
  const [detail, setDetail] = useState<PublishedStoryDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [playLoading, setPlayLoading] = useState(false)
  const [visibilityLoading, setVisibilityLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const abortController = new AbortController()

    const loadDetail = async () => {
      const cached = readCachedValue(STORY_DETAIL_CACHE, storyId)
      if (cached) {
        setDetail(cached)
        setError(null)
        setLoading(false)
      } else {
        setLoading(true)
        setDetail(null)
      }
      try {
        const response = await api.getStory(storyId, { signal: abortController.signal })
        if (active) {
          writeCachedValue(STORY_DETAIL_CACHE, storyId, response, STORY_DETAIL_CACHE_TTL_MS)
          setDetail(response)
          setError(null)
        }
      } catch (nextError) {
        if (isAbortError(nextError)) {
          return
        }
        if (active) {
          setDetail(null)
          setError(toErrorMessage(nextError, uiLanguage))
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadDetail()

    return () => {
      active = false
      abortController.abort()
    }
  }, [api, storyId, uiLanguage])

  const createPlaySession = async () => {
    setPlayLoading(true)
    setError(null)

    try {
      const session = await api.createPlaySession({ story_id: storyId })
      return session.session_id
    } catch (nextError) {
      setError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setPlayLoading(false)
    }
  }

  const updateVisibility = async (visibility: StoryVisibility) => {
    setVisibilityLoading(true)
    setError(null)

    try {
      const updatedStory = await api.updateStoryVisibility(storyId, { visibility })
      setDetail((current) => {
        if (!current) {
          return current
        }
        const nextDetail = {
          ...current,
          story: updatedStory,
          presentation: current.presentation
            ? {
                ...current.presentation,
                visibility: updatedStory.visibility,
                viewer_can_manage: updatedStory.viewer_can_manage,
              }
            : current.presentation,
        }
        writeCachedValue(STORY_DETAIL_CACHE, storyId, nextDetail, STORY_DETAIL_CACHE_TTL_MS)
        return nextDetail
      })
      return updatedStory
    } catch (nextError) {
      setError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setVisibilityLoading(false)
    }
  }

  const deleteStory = async () => {
    setDeleteLoading(true)
    setError(null)
    try {
      await api.deleteStory(storyId)
      deleteCachedValue(STORY_DETAIL_CACHE, storyId)
      setDetail(null)
      return true
    } catch (nextError) {
      setError(toErrorMessage(nextError, uiLanguage))
      return false
    } finally {
      setDeleteLoading(false)
    }
  }

  return {
    detail,
    loading,
    playLoading,
    visibilityLoading,
    deleteLoading,
    error,
    createPlaySession,
    updateVisibility,
    deleteStory,
  }
}
