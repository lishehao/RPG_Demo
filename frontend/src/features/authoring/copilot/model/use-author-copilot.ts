import { useEffect, useState } from "react"
import type { AuthorEditorStateResponse, StoryLanguage } from "../../../../index"
import { getAuthorUiCopy } from "../../../../shared/lib/author-ui-copy"
import { useAuthorEditorState } from "./use-author-editor-state"
import { useCopilotProposalReview } from "./use-copilot-proposal-review"
import { useCopilotSession } from "./use-copilot-session"

export function useAuthorCopilot(
  jobId: string,
  enabled: boolean,
  {
    onApplied,
    onUndone,
    uiLanguage = "en",
  }: {
    onApplied?: (editorState: AuthorEditorStateResponse) => Promise<void> | void
    onUndone?: (editorState: AuthorEditorStateResponse) => Promise<void> | void
    uiLanguage?: StoryLanguage
  } = {},
) {
  const copy = getAuthorUiCopy(uiLanguage)
  const editorState = useAuthorEditorState(jobId, enabled, uiLanguage)
  const session = useCopilotSession(jobId, {
    enabled,
    editorState: editorState.editorState,
    uiLanguage,
    onLocked: editorState.setLockedReason,
  })
  const [messageDraft, setMessageDraftState] = useState("")
  const [activeSuggestionId, setActiveSuggestionId] = useState<string | null>(null)
  const proposal = useCopilotProposalReview(jobId, {
    enabled,
    uiLanguage,
    onApplied: async (nextEditorState) => {
      editorState.setEditorState(nextEditorState)
      await onApplied?.(nextEditorState)
    },
    onUndone: async (nextEditorState) => {
      editorState.setEditorState(nextEditorState)
      await onUndone?.(nextEditorState)
    },
    onLocked: editorState.setLockedReason,
  })

  const workspaceView = editorState.editorState?.copilot_view
  const suggestedInstructions = workspaceView?.suggested_instructions ?? []
  const undoAvailable = workspaceView?.undo_available === true && Boolean(workspaceView.undo_proposal_id)
  const undoProposalId = workspaceView?.undo_proposal_id ?? null
  const undoSummary = workspaceView?.undo_request_summary ?? null

  const matchSuggestionId = (value: string) => {
    const trimmedValue = value.trim()
    if (!trimmedValue) {
      return null
    }
    return suggestedInstructions.find((suggestion) => suggestion.instruction.trim() === trimmedValue)?.suggestion_id ?? null
  }

  const clearReviewState = () => {
    proposal.dismissProposal()
  }

  const setMessageDraft = (value: string) => {
    clearReviewState()
    setMessageDraftState(value)
    setActiveSuggestionId(matchSuggestionId(value))
  }

  const useSuggestion = (suggestionId: string, instruction: string) => {
    clearReviewState()
    setMessageDraftState(instruction)
    setActiveSuggestionId(suggestionId)
  }

  useEffect(() => {
    session.setSession(null)
    setMessageDraftState("")
    setActiveSuggestionId(null)
    clearReviewState()
  }, [jobId])

  useEffect(() => {
    if (!enabled) {
      session.setSession(null)
      setMessageDraftState("")
      setActiveSuggestionId(null)
      clearReviewState()
    }
  }, [enabled])

  useEffect(() => {
    const activeSessionId = editorState.editorState?.copilot_view.active_session_id
    if (!enabled || !activeSessionId || session.session?.session_id === activeSessionId) {
      return
    }
    void session.loadSession(activeSessionId)
  }, [enabled, editorState.editorState?.copilot_view.active_session_id])

  useEffect(() => {
    const latestInstruction = session.session?.rewrite_brief.latest_instruction?.trim()
    if (!latestInstruction || messageDraft.trim()) {
      return
    }

    setMessageDraftState(latestInstruction)
    setActiveSuggestionId(matchSuggestionId(latestInstruction))
  }, [session.session?.session_id, editorState.editorState?.copilot_view.active_session_id, suggestedInstructions.length])

  const combinedError = proposal.proposalError ?? editorState.editorStateError ?? null

  const generateProposal = async () => {
    const instruction = messageDraft.trim() || session.session?.rewrite_brief.latest_instruction?.trim() || ""
    if (!instruction) {
      proposal.setProposalError(copy.writeInstructionFirst)
      return null
    }

    setMessageDraftState(instruction)
    return await proposal.generateProposal({ instruction })
  }

  const tryAnother = async () => {
    const currentProposalId = proposal.proposal?.proposal_id ?? null
    const instruction = proposal.proposal?.instruction.trim() || messageDraft.trim() || ""
    if (!instruction) {
      proposal.setProposalError(copy.writeInstructionFirst)
      return null
    }

    setMessageDraftState(instruction)
    return await proposal.generateProposal({
      instruction,
      retryFromProposalId: currentProposalId,
    })
  }

  const undoProposal = async () => {
    if (!undoProposalId) {
      return null
    }
    return await proposal.undoProposal(undoProposalId)
  }

  const showUndoPlaceholder =
    Boolean(proposal.successMessage) && !undoAvailable && !proposal.undoSuccessMessage

  return {
    editorState: editorState.editorState,
    loadingEditorState: editorState.loadingEditorState,
    refreshEditorState: editorState.refreshEditorState,
    session: session.session,
    messageDraft,
    setMessageDraft,
    activeSuggestionId,
    useSuggestion,
    suggestedInstructions,
    proposal: proposal.proposal,
    previewState: proposal.previewState,
    generateProposal,
    applyProposal: proposal.applyProposal,
    dismissProposal: proposal.dismissProposal,
    discardProposal: proposal.dismissProposal,
    tryAnother,
    instruction: messageDraft,
    setInstruction: setMessageDraft,
    proposalLoading: proposal.proposalLoading,
    previewingProposal: proposal.previewingProposal,
    applyingProposal: proposal.applyingProposal,
    undoingProposal: proposal.undoingProposal,
    lockedReason: editorState.lockedReason,
    error: combinedError,
    successMessage: proposal.successMessage,
    undoSuccessMessage: proposal.undoSuccessMessage,
    noMoreVariants: proposal.noMoreVariants,
    undoAvailable,
    undoProposalId,
    undoSummary,
    showUndoPlaceholder,
    undoProposal,
  }
}
