import type {
  AuthorCopilotPreviewResponse,
  AuthorCopilotProposalResponse,
  AuthorEditorStateResponse,
  StoryLanguage,
} from "../../index"
import { getAuthorUiCopy } from "../../shared/lib/author-ui-copy"
import { CopilotSectionDiff } from "./copilot-section-diff"

function humanizeFieldName(value: string) {
  return value
    .split("_")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ")
}

function formatFieldLabel(
  field: string,
  uiLanguage: StoryLanguage,
) {
  switch (field) {
    case "title":
      return uiLanguage === "zh" ? "标题" : "Title"
    case "premise":
      return uiLanguage === "zh" ? "前提" : "Premise"
    case "tone":
      return uiLanguage === "zh" ? "语气" : "Tone"
    case "stakes":
      return uiLanguage === "zh" ? "代价" : "Stakes"
    case "style_guard":
      return uiLanguage === "zh" ? "风格守则" : "Style guide"
    case "name":
      return uiLanguage === "zh" ? "名字" : "Name"
    case "role":
      return uiLanguage === "zh" ? "角色职责" : "Role"
    case "agenda":
      return uiLanguage === "zh" ? "动机" : "Agenda"
    case "red_line":
      return uiLanguage === "zh" ? "底线" : "Red line"
    case "pressure_signature":
      return uiLanguage === "zh" ? "施压方式" : "Pressure signature"
    case "goal":
      return uiLanguage === "zh" ? "目标" : "Goal"
    case "milestone_kind":
      return uiLanguage === "zh" ? "节拍类型" : "Beat kind"
    case "route_pivot_tag":
      return uiLanguage === "zh" ? "转向标签" : "Pivot tag"
    case "progress_required":
      return uiLanguage === "zh" ? "推进要求" : "Progress needed"
    case "toward":
      return uiLanguage === "zh" ? "收束方向" : "Ending tilt"
    case "intensity":
      return uiLanguage === "zh" ? "强度" : "Intensity"
    default:
      return uiLanguage === "zh" ? humanizeFieldName(field).replace(/ /g, "") : humanizeFieldName(field)
  }
}

function formatTargetLabel(
  operation: AuthorCopilotProposalResponse["operations"][number],
  editorState: AuthorEditorStateResponse | null,
  uiLanguage: StoryLanguage,
  copy: ReturnType<typeof getAuthorUiCopy>,
) {
  switch (operation.op) {
    case "update_story_frame":
      return copy.storyFrameLabel
    case "update_cast_member":
      return editorState?.cast_view.find((member) => member.npc_id === operation.target)?.name ?? copy.castLabel
    case "update_beat":
      return editorState?.beat_view.find((beat) => beat.beat_id === operation.target)?.title ?? copy.beatSpineLabel
    case "adjust_ending_tilt":
      return copy.endingTiltLabel
    default:
      return uiLanguage === "zh" ? humanizeFieldName(operation.target).replace(/ /g, "") : humanizeFieldName(operation.target)
  }
}

function formatSectionLabel(
  section: string,
  copy: ReturnType<typeof getAuthorUiCopy>,
) {
  switch (section) {
    case "story_frame":
      return copy.storyFrameLabel
    case "cast":
      return copy.castLabel
    case "beats":
      return copy.beatSpineLabel
    case "rule_pack":
      return copy.endingTiltLabel
    default:
      return section
  }
}

export function CopilotProposalReview({
  uiLanguage,
  editorState,
  proposal,
  previewState,
  applyingProposal,
  previewingProposal,
  proposalLoading,
  successMessage,
  undoSuccessMessage,
  noMoreVariants,
  undoAvailable,
  undoSummary,
  showUndoPlaceholder,
  undoingProposal,
  onApplyProposal,
  onUndoProposal,
  onGenerateAnother,
  onDismissProposal,
}: {
  uiLanguage: StoryLanguage
  editorState: AuthorEditorStateResponse | null
  proposal: AuthorCopilotProposalResponse | null
  previewState: AuthorCopilotPreviewResponse | null
  applyingProposal: boolean
  previewingProposal: boolean
  proposalLoading: boolean
  successMessage: string | null
  undoSuccessMessage: string | null
  noMoreVariants: boolean
  undoAvailable: boolean
  undoSummary: string | null
  showUndoPlaceholder: boolean
  undoingProposal: boolean
  onApplyProposal: () => void
  onUndoProposal: () => void
  onGenerateAnother: () => void
  onDismissProposal: () => void
}) {
  const copy = getAuthorUiCopy(uiLanguage)
  const showUndoAction = undoAvailable || showUndoPlaceholder

  if (!proposal && !showUndoAction && !undoSuccessMessage) {
    return (
      <section className="copilot-proposal-review copilot-proposal-review--empty">
        <div className="copilot-proposal-review__header">
          <div>
            <span className="editorial-metadata-label">{copy.reviewChanges}</span>
            <h2>{copy.suggestedRevision}</h2>
          </div>
        </div>
        <p className="editorial-support">{copy.noProposalYet}</p>
      </section>
    )
  }

  if (!proposal) {
    return (
      <section className="copilot-proposal-review copilot-proposal-review--empty">
        <div className="copilot-proposal-review__header">
          <div>
            <span className="editorial-metadata-label">{copy.changesApplied}</span>
            <h2>{undoSuccessMessage ?? undoSummary ?? copy.undoReady}</h2>
          </div>
        </div>
        {undoSuccessMessage ? <p className="author-copilot-panel__success">{undoSuccessMessage}</p> : null}
        {!undoSuccessMessage ? <p className="editorial-support">{undoSummary ?? copy.undoReady}</p> : null}
        {showUndoAction ? (
          <div className="author-copilot-panel__status-row">
            <button
              className="studio-button studio-button--ghost"
              disabled={!undoAvailable || undoingProposal}
              onClick={onUndoProposal}
              type="button"
            >
              {undoingProposal ? copy.undoing : copy.undo}
            </button>
            {!undoAvailable ? <p className="author-copilot-panel__status-note">{copy.undoUnavailable}</p> : null}
          </div>
        ) : null}
      </section>
    )
  }

  return (
    <section className="copilot-proposal-review">
      <div className="copilot-proposal-review__header">
        <div>
          <span className="editorial-metadata-label">{copy.suggestedRevision}</span>
          <h2>{proposal.request_summary}</h2>
          <p className="editorial-support">{proposal.rewrite_brief}</p>
        </div>
        <span className="editorial-badge">{proposal.variant_label}</span>
      </div>

      <div className="copilot-proposal-review__meta">
        <div>
          <span className="editorial-metadata-label">{copy.rewriteScope}</span>
          <p>{proposal.rewrite_scope}</p>
        </div>
        <div>
          <span className="editorial-metadata-label">{copy.affectedAreas}</span>
          <div className="detail-header__chips">
            {proposal.affected_sections.map((section) => (
              <span className="editorial-chip" key={section}>
                {formatSectionLabel(section, copy)}
              </span>
            ))}
          </div>
        </div>
      </div>

      {proposal.operations.length > 0 ? (
        <div className="copilot-proposal-review__section">
          <span className="editorial-metadata-label">{copy.whatWillChange}</span>
          <div className="author-copilot-operation-list">
            {proposal.operations.map((operation, index) => (
              <article className="author-copilot-operation" key={`${operation.op}-${operation.target}-${index}`}>
                <strong>{formatTargetLabel(operation, editorState, uiLanguage, copy)}</strong>
                <p>{Object.entries(operation.changes).map(([field, value]) => `${formatFieldLabel(field, uiLanguage)}: ${String(value)}`).join(" · ")}</p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {proposal.impact_summary.length > 0 ? (
        <div className="copilot-proposal-review__section">
          <span className="editorial-metadata-label">{copy.expectedImpact}</span>
          <ul className="author-copilot-panel__list">
            {proposal.impact_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {proposal.stability_guards.length > 0 ? (
        <div className="copilot-proposal-review__section">
          <span className="editorial-metadata-label">{copy.preservedGuards}</span>
          <ul className="author-copilot-panel__list">
            {proposal.stability_guards.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {proposal.warnings.length > 0 ? (
        <div className="copilot-proposal-review__section">
          <span className="editorial-metadata-label">{copy.watchOuts}</span>
          <ul className="author-copilot-panel__list">
            {proposal.warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {(successMessage || undoSuccessMessage || showUndoAction) ? (
        <div className="author-copilot-panel__status-row">
          {successMessage ? <p className="author-copilot-panel__success">{successMessage}</p> : null}
          {undoSuccessMessage ? <p className="author-copilot-panel__success">{undoSuccessMessage}</p> : null}
          {showUndoAction ? (
            <button
              className="studio-button studio-button--ghost"
              disabled={!undoAvailable || undoingProposal}
              onClick={onUndoProposal}
              type="button"
            >
              {undoingProposal ? copy.undoing : copy.undo}
            </button>
          ) : null}
        </div>
      ) : null}
      {showUndoAction ? (
        <p className="author-copilot-panel__status-note">{undoAvailable ? (undoSummary ?? copy.undoReady) : copy.undoUnavailable}</p>
      ) : null}
      {noMoreVariants ? <p className="author-copilot-panel__hint">{copy.noMoreVariants}</p> : null}

      {editorState && previewState ? (
        <div className="copilot-proposal-review__section">
          <span className="editorial-metadata-label">{copy.reviewChanges}</span>
          <CopilotSectionDiff
            affectedSections={proposal.affected_sections}
            baseState={editorState}
            previewState={previewState}
            uiLanguage={uiLanguage}
          />
        </div>
      ) : previewingProposal ? (
        <p className="editorial-support">{copy.preparingReview}</p>
      ) : null}

      <div className="copilot-proposal-review__actions">
        {proposal.status !== "applied" && proposal.status !== "undone" ? (
          <button className="studio-button studio-button--primary" disabled={applyingProposal || !previewState} onClick={onApplyProposal} type="button">
            {applyingProposal ? copy.applyingChanges : copy.applyChanges}
          </button>
        ) : null}
        {proposal.status !== "applied" && proposal.status !== "undone" ? (
          <button
            className="studio-button studio-button--secondary"
            disabled={proposalLoading || previewingProposal || noMoreVariants}
            onClick={onGenerateAnother}
            type="button"
          >
            {proposalLoading || previewingProposal ? copy.generating : copy.tryAnother}
          </button>
        ) : null}
        <button className="studio-button studio-button--ghost" onClick={onDismissProposal} type="button">
          {copy.dismiss}
        </button>
      </div>
    </section>
  )
}
