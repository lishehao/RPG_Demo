import { useEffect, useMemo, useState } from "react"
import type { AuthorPreviewResponse } from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { toErrorMessage } from "../../../../shared/lib/errors"

const DEFAULT_SEED = ""

export function useCreateStoryFlow() {
  const api = useApiClient()
  const [seed, setSeed] = useState(DEFAULT_SEED)
  const [preview, setPreview] = useState<AuthorPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [jobLoading, setJobLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const flashcards = useMemo(() => preview?.flashcards ?? [], [preview])

  useEffect(() => {
    setPreview(null)
    setPreviewLoading(false)
    setJobLoading(false)
    setError(null)
  }, [api])

  const updateSeed = (nextSeed: string) => {
    setSeed(nextSeed)
    if (preview && preview.prompt_seed !== nextSeed) {
      setPreview(null)
    }
  }

  const requestPreview = async () => {
    const trimmedSeed = seed.trim()
    if (!trimmedSeed) {
      setError("Enter a story seed first.")
      return null
    }

    setPreviewLoading(true)
    setError(null)

    try {
      const nextPreview = await api.createStoryPreview({ prompt_seed: trimmedSeed })
      setPreview(nextPreview)
      return nextPreview
    } catch (nextError) {
      setError(toErrorMessage(nextError))
      return null
    } finally {
      setPreviewLoading(false)
    }
  }

  const createAuthorJob = async () => {
    if (!preview) {
      setError("Generate a preview before starting the author job.")
      return null
    }

    setJobLoading(true)
    setError(null)

    try {
      const job = await api.createAuthorJob({
        prompt_seed: preview.prompt_seed,
        preview_id: preview.preview_id,
      })
      return job.job_id
    } catch (nextError) {
      setError(toErrorMessage(nextError))
      return null
    } finally {
      setJobLoading(false)
    }
  }

  return {
    seed,
    preview,
    flashcards,
    previewLoading,
    jobLoading,
    error,
    updateSeed,
    requestPreview,
    createAuthorJob,
  }
}
