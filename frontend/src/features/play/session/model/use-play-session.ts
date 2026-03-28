import { useEffect, useState } from "react"
import type { PlaySessionHistoryEntry, PlaySessionHistoryResponse, PlaySessionSnapshot, PlaySuggestedAction, StoryLanguage } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { isAbortError, toErrorMessage } from "../../../../shared/lib/errors"
import { readCachedValue, writeCachedValue } from "../../../../shared/lib/resource-cache"
import { uiText } from "../../../../shared/lib/ui-language"

type TranscriptEntry = {
  id: string
  speaker: "gm" | "player"
  text: string
}

function transcriptFromHistory(entries: PlaySessionHistoryEntry[]): TranscriptEntry[] {
  return entries.map((entry, index) => ({
    id: `${entry.speaker}-${entry.turn_index}-${index}-${entry.created_at}`,
    speaker: entry.speaker,
    text: entry.text,
  }))
}

function optimisticTranscriptAppend(
  current: TranscriptEntry[],
  {
    turnIndex,
    playerText,
    gmText,
  }: {
    turnIndex: number
    playerText: string
    gmText: string
  },
): TranscriptEntry[] {
  return [
    ...current,
    {
      id: `player-${turnIndex}-${current.length}`,
      speaker: "player",
      text: playerText,
    },
    {
      id: `gm-${turnIndex}-${current.length + 1}`,
      speaker: "gm",
      text: gmText,
    },
  ]
}

const PLAY_SESSION_SNAPSHOT_CACHE_TTL_MS = 30_000
const PLAY_SESSION_HISTORY_CACHE_TTL_MS = 30_000
const PLAY_SESSION_SNAPSHOT_CACHE = new Map<string, { value: PlaySessionSnapshot; expiresAt: number }>()
const PLAY_SESSION_HISTORY_CACHE = new Map<string, { value: PlaySessionHistoryResponse; expiresAt: number }>()

export function usePlaySession(sessionId: string, uiLanguage: StoryLanguage) {
  const api = useApiClient()
  const [snapshot, setSnapshot] = useState<PlaySessionSnapshot | null>(null)
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [inputText, setInputText] = useState("")
  const [pendingTurnInput, setPendingTurnInput] = useState<string | null>(null)
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const abortController = new AbortController()

    const loadSession = async () => {
      const cachedSnapshot = readCachedValue(PLAY_SESSION_SNAPSHOT_CACHE, sessionId)
      const cachedHistory = readCachedValue(PLAY_SESSION_HISTORY_CACHE, sessionId)
      if (cachedSnapshot) {
        setSnapshot(cachedSnapshot)
        setError(null)
      } else {
        setSnapshot(null)
      }
      if (cachedHistory) {
        setTranscript(transcriptFromHistory(cachedHistory.entries))
      } else {
        setTranscript([])
      }
      setLoading(!(cachedSnapshot && cachedHistory))
      try {
        const [nextSnapshot, nextHistory] = await Promise.all([
          api.getPlaySession(sessionId, { signal: abortController.signal }),
          api.getPlaySessionHistory(sessionId, { signal: abortController.signal }),
        ])
        if (active) {
          writeCachedValue(PLAY_SESSION_SNAPSHOT_CACHE, sessionId, nextSnapshot, PLAY_SESSION_SNAPSHOT_CACHE_TTL_MS)
          writeCachedValue(PLAY_SESSION_HISTORY_CACHE, sessionId, nextHistory, PLAY_SESSION_HISTORY_CACHE_TTL_MS)
          setSnapshot(nextSnapshot)
          setTranscript(transcriptFromHistory(nextHistory.entries))
          setError(null)
        }
      } catch (nextError) {
        if (isAbortError(nextError)) {
          return
        }
        if (active) {
          setSnapshot(null)
          setTranscript([])
          setError(toErrorMessage(nextError, uiLanguage))
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadSession()

    return () => {
      active = false
      abortController.abort()
    }
  }, [api, sessionId, uiLanguage])

  const selectSuggestedAction = (action: PlaySuggestedAction) => {
    setSelectedSuggestionId(action.suggestion_id)
    setInputText(action.prompt)
  }

  const submitTurn = async () => {
    if (!snapshot) {
      return
    }

    const trimmedInput = inputText.trim()
    if (!trimmedInput) {
      setError(
        uiText(uiLanguage, {
          en: "Write your action before sending the turn.",
          zh: "请先写下这一回合要做什么。",
        }),
      )
      return
    }

    setSubmitting(true)
    setError(null)
    setPendingTurnInput(trimmedInput)
    setInputText("")

    try {
      const nextSnapshot = await api.submitPlayTurn(sessionId, {
        input_text: trimmedInput,
        selected_suggestion_id: selectedSuggestionId,
      })
      writeCachedValue(PLAY_SESSION_SNAPSHOT_CACHE, sessionId, nextSnapshot, PLAY_SESSION_SNAPSHOT_CACHE_TTL_MS)
      setSnapshot(nextSnapshot)
      setPendingTurnInput(null)
      setSelectedSuggestionId(null)
      setTranscript((current) =>
        optimisticTranscriptAppend(current, {
          turnIndex: nextSnapshot.turn_index,
          playerText: trimmedInput,
          gmText: nextSnapshot.narration,
        }),
      )

      try {
        const nextHistory = await api.getPlaySessionHistory(sessionId)
        writeCachedValue(PLAY_SESSION_HISTORY_CACHE, sessionId, nextHistory, PLAY_SESSION_HISTORY_CACHE_TTL_MS)
        setTranscript(transcriptFromHistory(nextHistory.entries))
        setError(null)
      } catch (historyError) {
        setError(
          uiText(uiLanguage, {
            en: `Turn applied, but transcript refresh failed: ${toErrorMessage(historyError, uiLanguage)}`,
            zh: `回合已经生效，但刷新文本记录失败：${toErrorMessage(historyError, uiLanguage)}`,
          }),
        )
      }
    } catch (nextError) {
      setError(toErrorMessage(nextError, uiLanguage))
      setInputText(trimmedInput)
      setPendingTurnInput(null)
    } finally {
      setSubmitting(false)
    }
  }

  return {
    snapshot,
    transcript,
    inputText,
    pendingTurnInput,
    selectedSuggestionId,
    loading,
    submitting,
    error,
    setInputText,
    selectSuggestedAction,
    submitTurn,
  }
}
