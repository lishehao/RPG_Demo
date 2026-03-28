import { useState } from "react"
import type {
  AuthorCopilotSessionResponse,
  AuthorEditorStateResponse,
  StoryLanguage,
} from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorMessage } from "../../../../shared/lib/errors"

export function useCopilotSession(
  jobId: string,
  {
    enabled,
    editorState,
    uiLanguage,
    onLocked,
  }: {
    enabled: boolean
    editorState: AuthorEditorStateResponse | null
    uiLanguage: StoryLanguage
    onLocked?: (reason: string | null) => void
  },
) {
  const api = useApiClient()
  const [session, setSession] = useState<AuthorCopilotSessionResponse | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [sessionLoading, setSessionLoading] = useState(false)

  const loadSession = async (sessionId: string) => {
    if (!enabled || !editorState) {
      return null
    }
    setSessionLoading(true)
    try {
      const nextSession = await api.getAuthorCopilotSession(jobId, sessionId)
      setSession(nextSession)
      setSessionError(null)
      onLocked?.(null)
      return nextSession
    } catch (nextError) {
      setSessionError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setSessionLoading(false)
    }
  }

  return {
    session,
    setSession,
    sessionLoading,
    sessionError,
    setSessionError,
    loadSession,
  }
}
