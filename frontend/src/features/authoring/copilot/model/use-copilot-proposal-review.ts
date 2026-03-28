import { useState } from "react"
import type {
  AuthorCopilotPreviewResponse,
  AuthorCopilotProposalResponse,
  AuthorEditorStateResponse,
  StoryLanguage,
} from "../../../../index"
import { useApiClient } from "../../../../app/providers/api-client-provider"
import { getAuthorUiCopy } from "../../../../shared/lib/author-ui-copy"
import { toErrorCode, toErrorMessage } from "../../../../shared/lib/errors"

export function useCopilotProposalReview(
  jobId: string,
  {
    enabled,
    uiLanguage,
    onApplied,
    onUndone,
    onLocked,
  }: {
    enabled: boolean
    uiLanguage: StoryLanguage
    onApplied?: (editorState: AuthorEditorStateResponse) => Promise<void> | void
    onUndone?: (editorState: AuthorEditorStateResponse) => Promise<void> | void
    onLocked?: (reason: string | null) => void
  },
) {
  const api = useApiClient()
  const copy = getAuthorUiCopy(uiLanguage)
  const [proposal, setProposal] = useState<AuthorCopilotProposalResponse | null>(null)
  const [previewState, setPreviewState] = useState<AuthorCopilotPreviewResponse | null>(null)
  const [proposalLoading, setProposalLoading] = useState(false)
  const [previewingProposal, setPreviewingProposal] = useState(false)
  const [applyingProposal, setApplyingProposal] = useState(false)
  const [undoingProposal, setUndoingProposal] = useState(false)
  const [proposalError, setProposalError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [undoSuccessMessage, setUndoSuccessMessage] = useState<string | null>(null)
  const [noMoreVariants, setNoMoreVariants] = useState(false)

  const runPreview = async (proposalId: string) => {
    setPreviewingProposal(true)
    try {
      const nextPreview = await api.previewAuthorCopilotProposal(jobId, proposalId)
      setPreviewState(nextPreview)
      setProposalError(null)
      return nextPreview
    } catch (nextError) {
      const errorCode = toErrorCode(nextError)
      if (errorCode === "author_copilot_proposal_stale" || errorCode === "author_copilot_proposal_superseded") {
        setProposalError(copy.staleSuggestion)
        return null
      }
      setProposalError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setPreviewingProposal(false)
    }
  }

  const generateProposal = async ({
    instruction,
    retryFromProposalId,
  }: {
    instruction: string
    retryFromProposalId?: string | null
  }) => {
    const finalInstruction = instruction.trim()

    if (!enabled || !finalInstruction) {
      return null
    }

    setProposalLoading(true)
    try {
      const nextProposal = await api.createAuthorCopilotProposal(jobId, {
        instruction: finalInstruction,
        retry_from_proposal_id: retryFromProposalId ?? null,
      })
      setProposal(nextProposal)
      setPreviewState(null)
      setProposalError(null)
      setSuccessMessage(null)
      setUndoSuccessMessage(null)
      setNoMoreVariants(false)
      await runPreview(nextProposal.proposal_id)
      return nextProposal
    } catch (nextError) {
      const errorCode = toErrorCode(nextError)
      if (errorCode === "author_copilot_no_more_variants") {
        setNoMoreVariants(true)
        setProposalError(null)
        return null
      }
      if (errorCode === "author_copilot_proposal_stale" || errorCode === "author_copilot_proposal_superseded") {
        setProposalError(copy.staleSuggestion)
        return null
      }
      if (errorCode === "author_copilot_job_already_published") {
        onLocked?.(copy.lockedBeforePublish)
        setProposalError(null)
        return null
      }
      if (errorCode === "author_copilot_instruction_unsupported") {
        setProposalError(copy.unsupportedInstruction)
        return null
      }
      setProposalError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setProposalLoading(false)
    }
  }

  const applyProposal = async () => {
    if (!proposal) {
      return null
    }
    setApplyingProposal(true)
    try {
      const applied = await api.applyAuthorCopilotProposal(jobId, proposal.proposal_id)
      setProposal(applied.proposal)
      setPreviewState(null)
      setProposalError(null)
      setSuccessMessage(copy.changesApplied)
      setUndoSuccessMessage(null)
      setNoMoreVariants(false)
      await onApplied?.(applied.editor_state)
      return applied
    } catch (nextError) {
      const errorCode = toErrorCode(nextError)
      if (errorCode === "author_copilot_proposal_stale" || errorCode === "author_copilot_proposal_superseded") {
        setProposalError(copy.staleSuggestion)
        return null
      }
      if (errorCode === "author_copilot_job_already_published") {
        onLocked?.(copy.lockedBeforePublish)
        setProposalError(null)
        return null
      }
      if (errorCode === "author_copilot_proposal_already_applied") {
        setSuccessMessage(copy.changesApplied)
        setProposalError(null)
        return null
      }
      setProposalError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setApplyingProposal(false)
    }
  }

  const undoProposal = async (proposalId: string) => {
    if (!proposalId) {
      return null
    }
    setUndoingProposal(true)
    try {
      const undone = await api.undoAuthorCopilotProposal(jobId, proposalId)
      setProposal(undone.proposal)
      setPreviewState(null)
      setProposalError(null)
      setSuccessMessage(null)
      setUndoSuccessMessage(copy.changesUndone)
      setNoMoreVariants(false)
      await onUndone?.(undone.editor_state)
      return undone
    } catch (nextError) {
      const errorCode = toErrorCode(nextError)
      if (errorCode === "author_copilot_undo_stale") {
        setProposalError(copy.undoStale)
        return null
      }
      if (errorCode === "author_copilot_proposal_not_undoable") {
        setProposalError(copy.undoNotUndoable)
        return null
      }
      if (errorCode === "author_copilot_job_already_published") {
        onLocked?.(copy.lockedBeforePublish)
        setProposalError(null)
        return null
      }
      setProposalError(toErrorMessage(nextError, uiLanguage))
      return null
    } finally {
      setUndoingProposal(false)
    }
  }

  const dismissProposal = () => {
    setProposal(null)
    setPreviewState(null)
    setProposalError(null)
    setSuccessMessage(null)
    setUndoSuccessMessage(null)
    setNoMoreVariants(false)
  }

  return {
    proposal,
    setProposal,
    previewState,
    setPreviewState,
    proposalLoading,
    previewingProposal,
    applyingProposal,
    undoingProposal,
    proposalError,
    setProposalError,
    successMessage,
    undoSuccessMessage,
    noMoreVariants,
    generateProposal,
    runPreview,
    applyProposal,
    undoProposal,
    dismissProposal,
  }
}
