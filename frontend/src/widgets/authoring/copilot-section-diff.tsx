import type {
  AuthorCopilotPreviewResponse,
  AuthorEditorStateResponse,
  StoryLanguage,
} from "../../index"
import { getAuthorUiCopy } from "../../shared/lib/author-ui-copy"

function DiffBlock({
  label,
  before,
  after,
  uiLanguage,
}: {
  label: string
  before: string
  after: string
  uiLanguage: StoryLanguage
}) {
  const copy = getAuthorUiCopy(uiLanguage)
  if (before === after) {
    return null
  }

  return (
    <section className="copilot-section-diff__block">
      <span className="editorial-metadata-label">{label}</span>
      <div className="author-copilot-diff__columns">
        <div className="author-copilot-diff__column">
          <span className="author-copilot-diff__heading">{copy.currentDraftLabel}</span>
          <p>{before}</p>
        </div>
        <div className="author-copilot-diff__column is-after">
          <span className="author-copilot-diff__heading">{copy.candidateDraftLabel}</span>
          <p>{after}</p>
        </div>
      </div>
    </section>
  )
}

function formatStoryFrame(state: AuthorEditorStateResponse) {
  return [
    state.story_frame_view.title,
    state.story_frame_view.premise,
    state.story_frame_view.tone,
    state.story_frame_view.stakes,
  ].join("\n\n")
}

function formatCast(state: AuthorEditorStateResponse) {
  return state.cast_view
    .map((member) => `${member.name} • ${member.role}\n${member.agenda}\n${member.red_line}\n${member.pressure_signature}`)
    .join("\n\n")
}

function formatBeats(state: AuthorEditorStateResponse) {
  return state.beat_view.map((beat, index) => `${index + 1}. ${beat.title}\n${beat.goal}`).join("\n\n")
}

function formatRulePack(state: AuthorEditorStateResponse) {
  return [
    state.play_profile_view.runtime_profile_label,
    state.play_profile_view.closeout_profile_label,
    `turns=${state.play_profile_view.max_turns}`,
  ].join("\n")
}

export function CopilotSectionDiff({
  baseState,
  previewState,
  uiLanguage,
  affectedSections,
}: {
  baseState: AuthorEditorStateResponse
  previewState: AuthorCopilotPreviewResponse
  uiLanguage: StoryLanguage
  affectedSections: string[]
}) {
  const copy = getAuthorUiCopy(uiLanguage)
  const nextState = previewState.editor_state

  return (
    <div className="copilot-section-diff">
      {affectedSections.includes("story_frame") ? (
        <DiffBlock label={copy.storyFrameLabel} before={formatStoryFrame(baseState)} after={formatStoryFrame(nextState)} uiLanguage={uiLanguage} />
      ) : null}
      {affectedSections.includes("cast") ? (
        <DiffBlock label={copy.castLabel} before={formatCast(baseState)} after={formatCast(nextState)} uiLanguage={uiLanguage} />
      ) : null}
      {affectedSections.includes("beats") ? (
        <DiffBlock label={copy.beatSpineLabel} before={formatBeats(baseState)} after={formatBeats(nextState)} uiLanguage={uiLanguage} />
      ) : null}
      {affectedSections.includes("rule_pack") ? (
        <DiffBlock label={copy.endingTiltLabel} before={formatRulePack(baseState)} after={formatRulePack(nextState)} uiLanguage={uiLanguage} />
      ) : null}
    </div>
  )
}
