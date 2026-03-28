import type {
  AuthorCopilotPreviewResponse,
  AuthorCopilotProposalResponse,
  AuthorCopilotSuggestion,
  AuthorCopilotWorkspaceView,
  AuthorEditorStateResponse,
  StoryLanguage,
} from "../../index"
import { getAuthorUiCopy } from "../../shared/lib/author-ui-copy"
import { CopilotComposer } from "./copilot-composer"
import { CopilotProposalReview } from "./copilot-proposal-review"

export function AuthorCopilotPanel({
  uiLanguage,
  workspaceView,
  editorState,
  editable,
  lockedReason,
  error,
  messageDraft,
  activeSuggestionId,
  suggestedInstructions,
  proposal,
  previewState,
  proposalLoading,
  previewingProposal,
  applyingProposal,
  undoingProposal,
  successMessage,
  undoSuccessMessage,
  noMoreVariants,
  undoAvailable,
  undoSummary,
  showUndoPlaceholder,
  onMessageDraftChange,
  onUseSuggestion,
  onGenerateProposal,
  onApplyProposal,
  onUndoProposal,
  onGenerateAnother,
  onDismissProposal,
}: {
  uiLanguage: StoryLanguage
  workspaceView: AuthorCopilotWorkspaceView
  editorState: AuthorEditorStateResponse | null
  editable: boolean
  lockedReason: string | null
  error: string | null
  messageDraft: string
  activeSuggestionId: string | null
  suggestedInstructions: AuthorCopilotSuggestion[]
  proposal: AuthorCopilotProposalResponse | null
  previewState: AuthorCopilotPreviewResponse | null
  proposalLoading: boolean
  previewingProposal: boolean
  applyingProposal: boolean
  undoingProposal: boolean
  successMessage: string | null
  undoSuccessMessage: string | null
  noMoreVariants: boolean
  undoAvailable: boolean
  undoSummary: string | null
  showUndoPlaceholder: boolean
  onMessageDraftChange: (value: string) => void
  onUseSuggestion: (suggestionId: string, instruction: string) => void
  onGenerateProposal: () => void
  onApplyProposal: () => void
  onUndoProposal: () => void
  onGenerateAnother: () => void
  onDismissProposal: () => void
}) {
  const copy = getAuthorUiCopy(uiLanguage)

  return (
    <section className="author-copilot-panel">
      <div className="author-copilot-panel__frame">
        <div className="author-copilot-panel__frame-copy">
          <div className="author-copilot-panel__frame-badges">
            <span className="editorial-badge">{copy.authorCopilot}</span>
            <span className="editorial-badge">{editable ? copy.readyToEdit : copy.alreadyPublished}</span>
          </div>
          <h1>{workspaceView.headline}</h1>
          <p>{workspaceView.supporting_text}</p>
        </div>
      </div>

      {error ? <p className="editorial-error">{error}</p> : null}

      {editable ? (
        <>
          <CopilotComposer
            activeSuggestionId={activeSuggestionId}
            disabled={applyingProposal}
            generatingProposal={proposalLoading}
            messageDraft={messageDraft}
            onGenerateProposal={onGenerateProposal}
            onMessageDraftChange={onMessageDraftChange}
            onUseSuggestion={onUseSuggestion}
            suggestedInstructions={suggestedInstructions}
            uiLanguage={uiLanguage}
          />

          <CopilotProposalReview
            applyingProposal={applyingProposal}
            editorState={editorState}
            noMoreVariants={noMoreVariants}
            onApplyProposal={onApplyProposal}
            onDismissProposal={onDismissProposal}
            onGenerateAnother={onGenerateAnother}
            previewState={previewState}
            previewingProposal={previewingProposal}
            proposal={proposal}
            proposalLoading={proposalLoading}
            successMessage={successMessage}
            undoingProposal={undoingProposal}
            undoSuccessMessage={undoSuccessMessage}
            undoAvailable={undoAvailable}
            undoSummary={undoSummary}
            showUndoPlaceholder={showUndoPlaceholder}
            uiLanguage={uiLanguage}
            onUndoProposal={onUndoProposal}
          />
        </>
      ) : (
        <section className="copilot-proposal-review copilot-proposal-review--empty">
          <div className="copilot-proposal-review__header">
            <div>
              <span className="editorial-metadata-label">{copy.authorCopilot}</span>
              <h2>{copy.reviewAfterPublishHeadline}</h2>
            </div>
          </div>
          <p className="editorial-support">{lockedReason ?? copy.readOnlyAfterPublish}</p>
        </section>
      )}
    </section>
  )
}
