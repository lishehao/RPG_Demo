import { useEffect, useMemo, useRef, useState } from "react"
import type { AuthorPreviewResponse, StoryLanguage } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorMessage } from "../../../../shared/lib/errors"
import { prefersReducedMotionNow } from "../../../../shared/lib/motion"
import { isPreviewOutputHealthy } from "../../../../shared/lib/story-content-quality"
import { uiText } from "../../../../shared/lib/ui-language"

const DEFAULT_SEED = ""
const SPARK_REVEAL_INTERVAL_MS = 32
const SPARK_REVEAL_TARGET_DURATION_MS = 1800
const SPARK_REVEAL_MAX_DURATION_MS = 2300

export function useCreateStoryFlow(
  initialLanguage: StoryLanguage,
  uiLanguage: StoryLanguage,
  onDraftStateChange: (isDirty: boolean) => void,
) {
  const api = useApiClient()
  const [seed, setSeed] = useState(DEFAULT_SEED)
  const [language] = useState<StoryLanguage>(initialLanguage)
  const [preview, setPreview] = useState<AuthorPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [sparkLoading, setSparkLoading] = useState(false)
  const [jobLoading, setJobLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const sparkRevealIntervalRef = useRef<number | null>(null)
  const sparkRevealTimeoutRef = useRef<number | null>(null)
  const [sparkRevealActive, setSparkRevealActive] = useState(false)
  const [sparkRevealVisibleText, setSparkRevealVisibleText] = useState("")
  const [sparkRevealFullText, setSparkRevealFullText] = useState<string | null>(null)

  const flashcards = useMemo(() => preview?.flashcards ?? [], [preview])
  const isDirty =
    seed.trim().length > 0 ||
    preview !== null ||
    previewLoading ||
    sparkLoading ||
    jobLoading ||
    Boolean(error)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      if (sparkRevealIntervalRef.current) {
        window.clearInterval(sparkRevealIntervalRef.current)
      }
      if (sparkRevealTimeoutRef.current) {
        window.clearTimeout(sparkRevealTimeoutRef.current)
      }
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    onDraftStateChange(isDirty)
  }, [isDirty, onDraftStateChange])

  useEffect(() => {
    return () => {
      onDraftStateChange(false)
    }
  }, [onDraftStateChange])

  useEffect(() => {
    if (sparkRevealIntervalRef.current) {
      window.clearInterval(sparkRevealIntervalRef.current)
      sparkRevealIntervalRef.current = null
    }
    if (sparkRevealTimeoutRef.current) {
      window.clearTimeout(sparkRevealTimeoutRef.current)
      sparkRevealTimeoutRef.current = null
    }
    setPreview(null)
    setPreviewLoading(false)
    setSparkLoading(false)
    setJobLoading(false)
    setError(null)
    setSparkRevealActive(false)
    setSparkRevealVisibleText("")
    setSparkRevealFullText(null)
  }, [api])

  const clearSparkReveal = () => {
    if (sparkRevealIntervalRef.current) {
      window.clearInterval(sparkRevealIntervalRef.current)
      sparkRevealIntervalRef.current = null
    }
    if (sparkRevealTimeoutRef.current) {
      window.clearTimeout(sparkRevealTimeoutRef.current)
      sparkRevealTimeoutRef.current = null
    }
  }

  const finishSparkReveal = (finalText: string) => {
    clearSparkReveal()
    if (!mountedRef.current) {
      return
    }
    setSparkRevealActive(false)
    setSparkRevealVisibleText(finalText)
    setSparkRevealFullText(null)
  }

  const commitSeed = (nextSeed: string) => {
    setSeed(nextSeed)
    if (preview && preview.prompt_seed !== nextSeed) {
      setPreview(null)
    }
  }

  const startSparkReveal = (nextSeed: string) => {
    clearSparkReveal()

    if (!nextSeed || prefersReducedMotionNow()) {
      finishSparkReveal(nextSeed)
      return
    }

    const stepCount = Math.max(1, Math.floor(SPARK_REVEAL_TARGET_DURATION_MS / SPARK_REVEAL_INTERVAL_MS))
    const chunkSize = Math.max(1, Math.ceil(nextSeed.length / stepCount))
    let visibleLength = 0

    setSparkRevealActive(true)
    setSparkRevealVisibleText("")
    setSparkRevealFullText(nextSeed)

    sparkRevealIntervalRef.current = window.setInterval(() => {
      visibleLength = Math.min(nextSeed.length, visibleLength + chunkSize)
      if (!mountedRef.current) {
        clearSparkReveal()
        return
      }
      setSparkRevealVisibleText(nextSeed.slice(0, visibleLength))
      if (visibleLength >= nextSeed.length) {
        finishSparkReveal(nextSeed)
      }
    }, SPARK_REVEAL_INTERVAL_MS)

    sparkRevealTimeoutRef.current = window.setTimeout(() => {
      finishSparkReveal(nextSeed)
    }, SPARK_REVEAL_MAX_DURATION_MS)
  }

  const updateSeed = (nextSeed: string) => {
    clearSparkReveal()
    setSparkRevealActive(false)
    setSparkRevealVisibleText("")
    setSparkRevealFullText(null)
    commitSeed(nextSeed)
  }

  const requestSpark = async () => {
    if (sparkRevealActive) {
      return null
    }

    setSparkLoading(true)
    setError(null)

    try {
      const nextSpark = await api.createStorySpark({ language })
      if (!mountedRef.current) {
        return null
      }
      setPreview(null)
      commitSeed(nextSpark.prompt_seed)
      startSparkReveal(nextSpark.prompt_seed)
      return nextSpark
    } catch (nextError) {
      if (!mountedRef.current) {
        return null
      }
      setError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      if (mountedRef.current) {
        setSparkLoading(false)
      }
    }
  }

  const requestPreview = async () => {
    if (sparkRevealActive) {
      return null
    }

    const trimmedSeed = seed.trim()
    if (!trimmedSeed) {
      setError(uiText(uiLanguage, { en: "Enter a story seed first.", zh: "请先写下一个故事种子。" }))
      return null
    }

    setPreviewLoading(true)
    setError(null)

    try {
      const nextPreview = await api.createStoryPreview({ prompt_seed: trimmedSeed, language })
      if (!mountedRef.current) {
        return null
      }
      setPreview(nextPreview)
      return nextPreview
    } catch (nextError) {
      if (!mountedRef.current) {
        return null
      }
      setError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      if (mountedRef.current) {
        setPreviewLoading(false)
      }
    }
  }

  const createAuthorJob = async () => {
    if (sparkRevealActive) {
      return null
    }

    if (!preview) {
      setError(uiText(uiLanguage, { en: "Generate a preview before starting the author job.", zh: "开始正式生成前，请先生成预览。" }))
      return null
    }
    if (!isPreviewOutputHealthy(preview)) {
      setError(uiText(uiLanguage, { en: "Preview needs cleanup before authoring. Refresh the preview and try again.", zh: "预览还不够稳定，先刷新预览，再开始生成。" }))
      return null
    }

    setJobLoading(true)
    setError(null)

    try {
      const job = await api.createAuthorJob({
        prompt_seed: preview.prompt_seed,
        preview_id: preview.preview_id,
        language,
      })
      if (!mountedRef.current) {
        return null
      }
      return job.job_id
    } catch (nextError) {
      if (!mountedRef.current) {
        return null
      }
      setError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      if (mountedRef.current) {
        setJobLoading(false)
      }
    }
  }

  return {
    seed,
    language,
    preview,
    flashcards,
    previewLoading,
    sparkLoading,
    sparkRevealActive,
    sparkRevealVisibleText,
    sparkRevealFullText,
    jobLoading,
    error,
    updateSeed,
    requestSpark,
    requestPreview,
    createAuthorJob,
  }
}
