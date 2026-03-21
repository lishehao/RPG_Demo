import { useEffect, useMemo, useState } from "react"
import type { AuthorJobResultResponse, AuthorJobStatusResponse, AuthorLoadingCard, StoryVisibility } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorMessage } from "../../../../shared/lib/errors"

const CARD_ROTATION_MIN_MS = 2000
const CARD_ROTATION_MAX_MS = 3000

const CARD_ORDER: AuthorLoadingCard["card_id"][] = [
  "theme",
  "structure",
  "working_title",
  "tone",
  "story_premise",
  "story_stakes",
  "cast_count",
  "cast_anchor",
  "beat_count",
  "opening_beat",
  "final_beat",
  "generation_status",
  "token_budget",
]

function isCardReady(card: AuthorLoadingCard): boolean {
  return card.label.trim().length > 0 && card.value.trim().length > 0
}

function mergeCardPool(currentPool: AuthorLoadingCard[], nextCards: AuthorLoadingCard[]): AuthorLoadingCard[] {
  const readyCards = nextCards.filter(isCardReady)
  if (readyCards.length === 0) {
    return currentPool
  }

  const merged = new Map(currentPool.map((card) => [card.card_id, card]))
  for (const card of readyCards) {
    merged.set(card.card_id, card)
  }

  const orderIndex = new Map(CARD_ORDER.map((cardId, index) => [cardId, index]))
  return Array.from(merged.values()).sort((left, right) => {
    return (orderIndex.get(left.card_id) ?? 999) - (orderIndex.get(right.card_id) ?? 999)
  })
}

function nextCardId(pool: AuthorLoadingCard[], currentCardId: string | null): string | null {
  if (pool.length === 0) {
    return null
  }
  if (pool.length === 1) {
    return pool[0].card_id
  }
  if (!currentCardId) {
    const randomIndex = Math.floor(Math.random() * pool.length)
    return pool[randomIndex]?.card_id ?? pool[0].card_id
  }
  const candidates = pool.filter((card) => card.card_id !== currentCardId)
  const randomIndex = Math.floor(Math.random() * candidates.length)
  return candidates[randomIndex]?.card_id ?? pool[0].card_id
}

export function useAuthorLoading(jobId: string) {
  const api = useApiClient()
  const [job, setJob] = useState<AuthorJobStatusResponse | null>(null)
  const [result, setResult] = useState<AuthorJobResultResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [publishLoading, setPublishLoading] = useState(false)
  const [cardPool, setCardPool] = useState<AuthorLoadingCard[]>([])
  const [activeCardId, setActiveCardId] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let timer: number | undefined

    setJob(null)
    setResult(null)

    const pollJob = async () => {
      try {
        const nextJob = await api.getAuthorJob(jobId)
        if (!active) {
          return
        }

        setJob(nextJob)
        setError(null)

        if (nextJob.status === "completed") {
          const nextResult = await api.getAuthorJobResult(jobId)
          if (active) {
            setResult(nextResult)
          }
          return
        }

        if (nextJob.status !== "failed") {
          timer = window.setTimeout(() => {
            void pollJob()
          }, 1200)
        }
      } catch (nextError) {
        if (active) {
          setJob(null)
          setResult(null)
          setError(toErrorMessage(nextError))
        }
      }
    }

    void pollJob()

    return () => {
      active = false
      if (timer) {
        window.clearTimeout(timer)
      }
    }
  }, [api, jobId])

  const publishStory = async (visibility: StoryVisibility = "private") => {
    setPublishLoading(true)
    setError(null)

    try {
      const story = await api.publishAuthorJob(jobId, visibility)
      return story.story_id
    } catch (nextError) {
      setError(toErrorMessage(nextError))
      return null
    } finally {
      setPublishLoading(false)
    }
  }

  const progressSnapshot = job?.progress_snapshot ?? result?.progress_snapshot ?? null
  const completionPercent = useMemo(() => Math.round((progressSnapshot?.completion_ratio ?? 0) * 100), [progressSnapshot])

  useEffect(() => {
    const nextCards = progressSnapshot?.loading_cards ?? []
    if (nextCards.length === 0) {
      return
    }

    setCardPool((currentPool) => {
      const nextPool = mergeCardPool(currentPool, nextCards)
      if (nextPool.length === 0) {
        setActiveCardId(null)
        return nextPool
      }
      if (!activeCardId || !nextPool.some((card) => card.card_id === activeCardId)) {
        setActiveCardId((currentCardId) => nextCardId(nextPool, currentCardId))
      }
      return nextPool
    })
  }, [activeCardId, progressSnapshot])

  useEffect(() => {
    if (cardPool.length <= 1 || !activeCardId) {
      return
    }
    const timeoutMs =
      CARD_ROTATION_MIN_MS +
      Math.floor(Math.random() * (CARD_ROTATION_MAX_MS - CARD_ROTATION_MIN_MS + 1))
    const timer = window.setTimeout(() => {
      setActiveCardId((currentCardId) => nextCardId(cardPool, currentCardId))
    }, timeoutMs)
    return () => {
      window.clearTimeout(timer)
    }
  }, [activeCardId, cardPool])

  const activeCard = useMemo(() => {
    if (cardPool.length === 0) {
      return null
    }

    return cardPool.find((card) => card.card_id === activeCardId) ?? cardPool[0]
  }, [activeCardId, cardPool])

  return {
    job,
    result,
    error,
    publishLoading,
    progressSnapshot,
    completionPercent,
    cardPool,
    activeCard,
    publishStory,
  }
}
