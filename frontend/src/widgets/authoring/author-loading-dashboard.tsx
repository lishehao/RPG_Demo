import type { AuthorJobResultResponse, AuthorJobStatusResponse, AuthorLoadingCard, StoryLanguage, StoryVisibility } from "../../index"
import type { useAuthorCopilot } from "../../features/authoring/copilot/model/use-author-copilot"
import { getAuthorUiCopy } from "../../shared/lib/author-ui-copy"
import { getAuthorStageLabel, getAuthorStageMessage } from "../../shared/lib/author-loading"
import { pickHealthyLabel, pickHealthyText } from "../../shared/lib/story-content-quality"
import { formatThemeLabel } from "../../shared/lib/story-taxonomy"
import { LoadingCardSpotlight } from "../../entities/authoring/ui/loading-card-spotlight"
import { StudioIcon } from "../../shared/ui/studio-icon"
import { AuthorLoadingThemePanel } from "./author-loading-theme-panel"
import { AuthorEditorWorkspace } from "./author-editor-workspace"
import { StudioFooter } from "../chrome/studio-footer"

export function AuthorLoadingDashboard({
  job,
  result,
  error,
  completionPercent,
  publishLoading,
  cardPool,
  activeCard,
  copilot,
  publishVisibility,
  onPublishVisibilityChange,
  onPublish,
  uiLanguage,
}: {
  job: AuthorJobStatusResponse | null
  result: AuthorJobResultResponse | null
  error: string | null
  completionPercent: number
  publishLoading: boolean
  cardPool: AuthorLoadingCard[]
  activeCard: AuthorLoadingCard | null
  copilot: ReturnType<typeof useAuthorCopilot>
  publishVisibility: StoryVisibility
  onPublishVisibilityChange: (visibility: StoryVisibility) => void
  onPublish: () => void
  uiLanguage: StoryLanguage
}) {
  const copy = getAuthorUiCopy(uiLanguage)
  const progressSnapshot = job?.progress_snapshot ?? result?.progress_snapshot ?? null
  const statusLabel = job?.status ?? "queued"
  const stageLabel = progressSnapshot?.stage_label ?? getAuthorStageLabel(progressSnapshot?.stage ?? statusLabel, progressSnapshot?.stage_label, uiLanguage)
  const stageMessage = progressSnapshot?.stage_message ?? getAuthorStageMessage(progressSnapshot?.stage ?? statusLabel, progressSnapshot?.stage_label, uiLanguage)
  const storyLanguage = result?.summary?.language ?? job?.preview.language ?? "en"
  const finalSummaryReady = Boolean(result?.summary)
  const summaryTitle = finalSummaryReady
    ? pickHealthyLabel(storyLanguage, [result?.summary?.title], copy.storyPackageReady)
    : pickHealthyLabel(storyLanguage, [job?.preview.story.title], copy.preparingSummary)
  const summaryPremise = finalSummaryReady
    ? pickHealthyText(storyLanguage, [result?.summary?.premise, result?.summary?.one_liner], copy.packageReadyReview)
    : pickHealthyText(storyLanguage, [job?.preview.story.premise], copy.summaryPopulate)
  const summaryTheme = finalSummaryReady
    ? formatThemeLabel(pickHealthyLabel(storyLanguage, [result?.summary?.theme], copy.pending), uiLanguage)
    : formatThemeLabel(pickHealthyLabel(storyLanguage, [job?.preview.flashcards.find((card) => card.card_id === "theme")?.value], copy.pending), uiLanguage)
  const summaryTone = finalSummaryReady
    ? pickHealthyLabel(storyLanguage, [result?.summary?.tone], copy.pending)
    : pickHealthyLabel(storyLanguage, [job?.preview.story.tone], copy.pending)
  const primaryTheme = progressSnapshot?.primary_theme ?? job?.preview.theme.primary_theme ?? null
  const completionCard =
    activeCard ??
    (finalSummaryReady
      ? {
          card_id: "generation_status" as const,
          emphasis: "stable" as const,
          label: copy.storyPackageReady,
          value: result?.summary?.title ?? copy.yourStoryReady,
        }
      : null)

  if (finalSummaryReady) {
    return (
      <AuthorEditorWorkspace
        copilot={copilot}
        editorState={copilot.editorState}
        result={result}
        onPublish={onPublish}
        onPublishVisibilityChange={onPublishVisibilityChange}
        publishLoading={publishLoading}
        publishVisibility={publishVisibility}
        uiLanguage={uiLanguage}
      />
    )
  }

  return (
    <div className="editorial-page editorial-page--loading">
      <section className="loading-hero">
        <div className="loading-headline">
          <h1>
            {copy.authoringTitleLead}<span>{copy.authoringTitleAccent}</span>
          </h1>
          <div className="loading-progress-track">
            <div className="loading-progress-fill" style={{ width: `${completionPercent}%` }} />
          </div>
          <div className="loading-progress-meta">
            <span>{stageLabel}</span>
            <span>{copy.completion(completionPercent)}</span>
          </div>
        </div>
      </section>

      <section className="loading-focus-grid">
        <div className="loading-focus-card loading-focus-card--spotlight">
          {progressSnapshot ? (
            <LoadingCardSpotlight activeCard={completionCard} uiLanguage={uiLanguage} />
          ) : (
            <div className="editorial-empty-state">
              <h3>{copy.waitingSnapshot}</h3>
              <p>{copy.waitingSnapshotBody}</p>
            </div>
          )}

          {error ? <p className="editorial-error">{error}</p> : null}
        </div>

        <AuthorLoadingThemePanel
          fallback={(
            <div className="loading-context-card">
              <span className="editorial-metadata-label">{copy.currentStory}</span>
              <h2>{summaryTitle}</h2>
              <p>{summaryPremise}</p>

              <div className="loading-context-stats">
                <div>
                  <span className="editorial-metadata-label">{copy.theme}</span>
                  <p>{summaryTheme}</p>
                </div>
                <div>
                  <span className="editorial-metadata-label">{copy.tone}</span>
                  <p>{summaryTone}</p>
                </div>
                <div>
                  <span className="editorial-metadata-label">{copy.npcs}</span>
                  <p>{result?.summary?.npc_count ?? job?.preview.structure.expected_npc_count ?? 0}</p>
                </div>
                <div>
                  <span className="editorial-metadata-label">{copy.beats}</span>
                  <p>{result?.summary?.beat_count ?? job?.preview.structure.expected_beat_count ?? 0}</p>
                </div>
              </div>
            </div>
          )}
          primaryTheme={primaryTheme}
          uiLanguage={uiLanguage}
        />
      </section>

      <section className="loading-ledger">
        <div className="loading-ledger__stamp">
          <>
            <div className="loading-stamp-icon">
              <StudioIcon name="autorenew" />
            </div>
            <div>
              <p>{stageMessage}</p>
            </div>
          </>
        </div>
      </section>

      <StudioFooter uiLanguage={uiLanguage} />
    </div>
  )
}
