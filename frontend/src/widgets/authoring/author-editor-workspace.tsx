import type { AuthorJobResultResponse, StoryLanguage, StoryVisibility } from "../../index"
import type { AuthorEditorStateResponse } from "../../api/contracts"
import type { useAuthorCopilot } from "../../features/authoring/copilot/model/use-author-copilot"
import { getAuthorUiCopy } from "../../shared/lib/author-ui-copy"
import { formatAffordanceTag, formatMilestoneKind, formatThemeLabel } from "../../shared/lib/story-taxonomy"
import { EditorialMedia } from "../../shared/ui/editorial-media"
import { StudioFooter } from "../chrome/studio-footer"
import { AuthorCopilotPanel } from "./author-copilot-panel"

function compactTemplateVersion(value: string | null | undefined) {
  const normalized = String(value ?? "").trim()
  if (!normalized) {
    return null
  }
  return normalized.length > 16 ? normalized.slice(0, 12) : normalized
}

export function AuthorEditorWorkspace({
  editorState,
  result,
  copilot,
  uiLanguage,
  publishVisibility,
  publishLoading,
  onPublishVisibilityChange,
  onPublish,
}: {
  editorState: AuthorEditorStateResponse | null
  result: AuthorJobResultResponse | null
  copilot: ReturnType<typeof useAuthorCopilot>
  uiLanguage: StoryLanguage
  publishVisibility: StoryVisibility
  publishLoading: boolean
  onPublishVisibilityChange: (visibility: StoryVisibility) => void
  onPublish: () => void
}) {
  const copy = getAuthorUiCopy(uiLanguage)
  const summary = editorState?.summary ?? result?.summary ?? null
  const premise = editorState?.story_frame_view.premise ?? summary?.premise ?? copy.packageReadyReview
  const canPublish = (editorState?.publishable ?? result?.publishable ?? false) === true
  const readOnlyReason = copilot.lockedReason ?? copy.lockedBeforePublish
  const canEditCopilot = canPublish && !copilot.lockedReason
  const workspaceView = editorState?.copilot_view ?? {
    mode: "primary" as const,
    headline: canEditCopilot ? copy.steerBeforePublishHeadline : copy.reviewAfterPublishHeadline,
    supporting_text: canEditCopilot ? copy.continueShaping : copy.readOnlyAfterPublish,
    publish_readiness_text: canPublish ? copy.publishReadiness : copy.publishedReadiness,
    suggested_instructions: [],
  }
  const protagonist = editorState?.play_profile_view.protagonist ?? null

  return (
    <div className="editorial-page editorial-page--author-studio">
      <div className="author-studio-layout">
        <section className="author-studio-main">
          <AuthorCopilotPanel
            activeSuggestionId={copilot.activeSuggestionId}
            applyingProposal={copilot.applyingProposal}
            editable={canEditCopilot}
            editorState={copilot.editorState}
            error={copilot.error}
            lockedReason={readOnlyReason}
            messageDraft={copilot.messageDraft}
            noMoreVariants={copilot.noMoreVariants}
            onApplyProposal={() => {
              void copilot.applyProposal()
            }}
            onDismissProposal={copilot.dismissProposal}
            onGenerateAnother={() => {
              void copilot.tryAnother()
            }}
            onGenerateProposal={() => {
              void copilot.generateProposal()
            }}
            onMessageDraftChange={copilot.setMessageDraft}
            onUseSuggestion={copilot.useSuggestion}
            previewState={copilot.previewState}
            previewingProposal={copilot.previewingProposal}
            proposal={copilot.proposal}
            proposalLoading={copilot.proposalLoading}
            successMessage={copilot.successMessage}
            undoingProposal={copilot.undoingProposal}
            undoSuccessMessage={copilot.undoSuccessMessage}
            undoAvailable={copilot.undoAvailable}
            undoSummary={copilot.undoSummary}
            showUndoPlaceholder={copilot.showUndoPlaceholder}
            suggestedInstructions={copilot.suggestedInstructions}
            uiLanguage={uiLanguage}
            workspaceView={workspaceView}
            onUndoProposal={() => {
              void copilot.undoProposal()
            }}
          />

          {editorState ? (
            <div className="author-studio-context-stack">
              <section className="author-studio-card">
                <div className="author-studio-card__header">
                  <div>
                    <span className="editorial-metadata-label">{copy.continueDraftContext}</span>
                    <h2>{copy.whatDraftTryingToDo}</h2>
                  </div>
                </div>
                <p className="editorial-support">{copy.draftContextSupport}</p>
                <div className="author-studio-grid author-studio-grid--two">
                  <div className="author-studio-detail-block">
                    <span className="editorial-metadata-label">{copy.oneLineSetup}</span>
                    <p>{editorState.summary.one_liner}</p>
                  </div>
                  <div className="author-studio-detail-block">
                    <span className="editorial-metadata-label">{copy.theme}</span>
                    <p>{formatThemeLabel(editorState.summary.theme, uiLanguage)}</p>
                  </div>
                  <div className="author-studio-detail-block">
                    <span className="editorial-metadata-label">{copy.tone}</span>
                    <p>{editorState.story_frame_view.tone}</p>
                  </div>
                  <div className="author-studio-detail-block">
                    <span className="editorial-metadata-label">{copy.stakes}</span>
                    <p>{editorState.story_frame_view.stakes}</p>
                  </div>
                </div>
              </section>

              <section className="author-studio-card">
                <div className="author-studio-card__header">
                  <div>
                    <span className="editorial-metadata-label">{copy.beatSpine}</span>
                    <h2>{copy.howPlayableArcWorks}</h2>
                  </div>
                </div>
                <div className="author-studio-sequence">
                  {editorState.beat_view.map((beat) => (
                    <article className="author-studio-sequence__item" key={beat.beat_id}>
                      <div className="author-studio-sequence__meta">
                        <strong>{beat.title}</strong>
                        <span>{formatMilestoneKind(beat.milestone_kind, uiLanguage)}</span>
                      </div>
                      <p>{beat.goal}</p>
                      {beat.affordance_tags.length > 0 ? (
                        <div className="detail-header__chips">
                          {beat.affordance_tags.map((tag) => (
                            <span className="editorial-chip" key={tag}>
                              {formatAffordanceTag(tag, uiLanguage)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>

              <section className="author-studio-card">
                <div className="author-studio-card__header">
                  <div>
                    <span className="editorial-metadata-label">{copy.castExtractionReview}</span>
                    <h2>{copy.whoCarriesPressure}</h2>
                  </div>
                </div>
                <p className="editorial-support">{copy.extractionReviewSupport}</p>
                <div className="author-studio-cast-grid">
                  {editorState.cast_view.map((member) => (
                    <article className={`author-studio-cast-card ${member.portrait_url ? "author-studio-cast-card--with-portrait" : ""}`} key={member.npc_id}>
                      {member.portrait_url ? (
                        <EditorialMedia
                          alt={member.name}
                          className="author-studio-cast-card__portrait"
                          overlay
                          ratio="4 / 5"
                          src={member.portrait_url}
                        />
                      ) : null}
                      <div className="author-studio-cast-card__content">
                        <div className="author-studio-cast-card__header">
                          <div>
                            <strong>{member.name}</strong>
                            {(member.roster_character_id || member.template_version) ? (
                              <div className="author-studio-cast-card__chips">
                                {member.roster_character_id ? (
                                  <span className="editorial-muted-chip">{uiLanguage === "zh" ? "角色库人物" : "Roster character"}</span>
                                ) : null}
                                {member.template_version ? (
                                  <span className="editorial-muted-chip">
                                    {copy.templateVersion} {compactTemplateVersion(member.template_version)}
                                  </span>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                          <span className="author-studio-cast-card__role">{member.role}</span>
                        </div>
                        {member.roster_public_summary ? (
                          <div className="author-studio-cast-card__detail">
                            <span className="editorial-metadata-label">{copy.canonicalAnchor}</span>
                            <p>{member.roster_public_summary}</p>
                          </div>
                        ) : null}
                        <div className="author-studio-cast-card__detail">
                          <span className="editorial-metadata-label">{copy.currentDrive}</span>
                          <p>{member.agenda}</p>
                        </div>
                        <div className="author-studio-cast-card__detail">
                          <span className="editorial-metadata-label">{copy.redLine}</span>
                          <p>{member.red_line}</p>
                        </div>
                        <div className="author-studio-cast-card__detail">
                          <span className="editorial-metadata-label">{copy.pressureSignature}</span>
                          <p>{member.pressure_signature}</p>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <section className="author-studio-card author-studio-card--muted">
              <div className="author-studio-card__header">
                <div>
                  <span className="editorial-metadata-label">{copy.draftReview}</span>
                  <h2>{copilot.loadingEditorState ? copy.preparingAuthorStudio : copy.studioStateUnavailable}</h2>
                </div>
              </div>
              <p>{copilot.loadingEditorState ? copy.fetchingCanonicalState : premise}</p>
            </section>
          )}
        </section>

        <aside className="author-studio-side">
          <section className="author-studio-card">
            <div className="author-studio-card__header">
              <div>
                <span className="editorial-metadata-label">{copy.publish}</span>
                <h2>{canPublish ? copy.shipToLibrary : copy.alreadyPublished}</h2>
              </div>
            </div>
            <p>{workspaceView.publish_readiness_text}</p>
            {canPublish ? (
              <>
                <label className="loading-publish-controls__field">
                  <span className="editorial-metadata-label">{copy.publishVisibility}</span>
                  <select onChange={(event) => onPublishVisibilityChange(event.target.value as StoryVisibility)} value={publishVisibility}>
                    <option value="private">{copy.privateVisibility}</option>
                    <option value="public">{copy.publicVisibility}</option>
                  </select>
                </label>
                <button className="studio-button studio-button--primary" disabled={publishLoading} onClick={onPublish} type="button">
                  {publishLoading ? copy.publishing : copy.publishToLibrary}
                </button>
              </>
            ) : (
              <p className="author-studio-readonly-note">{readOnlyReason}</p>
            )}
          </section>

          {editorState ? (
            <>
              <section className="author-studio-card">
                <div className="author-studio-card__header">
                  <div>
                    <span className="editorial-metadata-label">{copy.playProfile}</span>
                    <h2>{copy.whoPlayerBecomes}</h2>
                  </div>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.protagonist}</span>
                  <p>
                    <strong>{protagonist?.name}</strong>
                    <br />
                    {protagonist?.role}
                  </p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.mandate}</span>
                  <p>{protagonist?.agenda}</p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.runtime}</span>
                  <p>{editorState.play_profile_view.runtime_profile_label}</p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.closeoutTilt}</span>
                  <p>{editorState.play_profile_view.closeout_profile_label}</p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.turnCap}</span>
                  <p>{editorState.play_profile_view.max_turns}</p>
                </div>
              </section>

              <section className="author-studio-card">
                <div className="author-studio-card__header">
                  <div>
                    <span className="editorial-metadata-label">{copy.focusedBrief}</span>
                    <h2>{copy.whatModelLockedOnto}</h2>
                  </div>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.storyKernel}</span>
                  <p>{editorState.focused_brief.story_kernel}</p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.coreConflict}</span>
                  <p>{editorState.focused_brief.core_conflict}</p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.settingSignal}</span>
                  <p>{editorState.focused_brief.setting_signal}</p>
                </div>
                <div className="author-studio-detail-block">
                  <span className="editorial-metadata-label">{copy.toneSignal}</span>
                  <p>{editorState.focused_brief.tone_signal}</p>
                </div>
              </section>
            </>
          ) : summary ? (
            <section className="author-studio-card">
              <div className="author-studio-card__header">
                <div>
                  <span className="editorial-metadata-label">{copy.storyFrame}</span>
                  <h2>{copy.whatDraftTryingToDo}</h2>
                </div>
              </div>
              <div className="author-studio-detail-block">
                <span className="editorial-metadata-label">{copy.oneLineSetup}</span>
                <p>{summary.one_liner}</p>
              </div>
              <div className="author-studio-detail-block">
                <span className="editorial-metadata-label">{copy.theme}</span>
                <p>{formatThemeLabel(summary.theme, uiLanguage)}</p>
              </div>
              <div className="author-studio-detail-block">
                <span className="editorial-metadata-label">{copy.tone}</span>
                <p>{summary.tone}</p>
              </div>
            </section>
          ) : null}
        </aside>
      </div>

      <StudioFooter uiLanguage={uiLanguage} />
    </div>
  )
}
