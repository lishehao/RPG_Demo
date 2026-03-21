import { useEffect, useState } from "react"
import type { PublishedStoryDetailResponse, StoryVisibility } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorMessage } from "../../../../shared/lib/errors"

export function useStoryDetail(storyId: string) {
  const api = useApiClient()
  const [detail, setDetail] = useState<PublishedStoryDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [playLoading, setPlayLoading] = useState(false)
  const [visibilityLoading, setVisibilityLoading] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    const loadDetail = async () => {
      setLoading(true)
      setDetail(null)
      try {
        const response = await api.getStory(storyId)
        if (active) {
          setDetail(response)
          setError(null)
        }
      } catch (nextError) {
        if (active) {
          setDetail(null)
          setError(toErrorMessage(nextError))
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
    }
  }, [api, storyId])

  const createPlaySession = async () => {
    setPlayLoading(true)
    setError(null)

    try {
      const session = await api.createPlaySession({ story_id: storyId })
      return session.session_id
    } catch (nextError) {
      setError(toErrorMessage(nextError))
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
        return {
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
      })
      return updatedStory
    } catch (nextError) {
      setError(toErrorMessage(nextError))
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
      setDetail(null)
      return true
    } catch (nextError) {
      setError(toErrorMessage(nextError))
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
