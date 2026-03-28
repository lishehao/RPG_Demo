import { useEffect, useState } from "react"
import type { AuthorEditorStateResponse, StoryLanguage } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorCode, toErrorMessage } from "../../../../shared/lib/errors"
import { getAuthorUiCopy } from "../../../../shared/lib/author-ui-copy"

export function useAuthorEditorState(jobId: string, enabled: boolean, uiLanguage: StoryLanguage) {
  const api = useApiClient()
  const copy = getAuthorUiCopy(uiLanguage)
  const [editorState, setEditorState] = useState<AuthorEditorStateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lockedReason, setLockedReason] = useState<string | null>(null)

  const refreshEditorState = async () => {
    if (!enabled) {
      setEditorState(null)
      return null
    }
    setLoading(true)
    try {
      const nextEditorState = await api.getAuthorJobEditorState(jobId)
      setEditorState(nextEditorState)
      setLockedReason(null)
      setError(null)
      return nextEditorState
    } catch (nextError) {
      const errorCode = toErrorCode(nextError)
      if (errorCode === "author_copilot_job_already_published") {
        setLockedReason(copy.lockedBeforePublish)
        setError(null)
        return null
      }
      setError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshEditorState()
  }, [enabled, jobId])

  return {
    editorState,
    setEditorState,
    loadingEditorState: loading,
    editorStateError: error,
    setEditorStateError: setError,
    lockedReason,
    setLockedReason,
    refreshEditorState,
  }
}
