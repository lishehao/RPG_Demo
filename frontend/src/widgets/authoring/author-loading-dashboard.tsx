import type { AuthorJobResultResponse, AuthorJobStatusResponse, AuthorLoadingCard, StoryVisibility } from "../../index"
import { LoadingCardSpotlight } from "../../entities/authoring/ui/loading-card-spotlight"
import { StudioFooter } from "../chrome/studio-footer"

export function AuthorLoadingDashboard({
  job,
  result,
  error,
  completionPercent,
  publishLoading,
  cardPool,
  activeCard,
  publishVisibility,
  onPublishVisibilityChange,
  onPublish,
}: {
  job: AuthorJobStatusResponse | null
  result: AuthorJobResultResponse | null
  error: string | null
  completionPercent: number
  publishLoading: boolean
  cardPool: AuthorLoadingCard[]
  activeCard: AuthorLoadingCard | null
  publishVisibility: StoryVisibility
  onPublishVisibilityChange: (visibility: StoryVisibility) => void
  onPublish: () => void
}) {
  const progressSnapshot = job?.progress_snapshot ?? result?.progress_snapshot ?? null
  const statusLabel = job?.status ?? "queued"

  return (
    <div className="editorial-page editorial-page--loading">
      <section className="loading-hero">
        <div className="loading-session-meta">
          <span>Session {job?.job_id.slice(0, 4).toUpperCase() ?? "0000"}</span>
        </div>

        <div className="loading-headline">
          <h1>
            Forging the <span>narrative arc.</span>
          </h1>
          <div className="loading-progress-track">
            <div className="loading-progress-fill" style={{ width: `${completionPercent}%` }} />
          </div>
          <div className="loading-progress-meta">
            <span>{progressSnapshot?.stage_label ?? "Queued"}</span>
            <span>{completionPercent}% manifested</span>
          </div>
        </div>
      </section>

      <section className="loading-focus-grid">
        <div className="loading-focus-card">
          {progressSnapshot ? (
            <LoadingCardSpotlight activeCard={activeCard} cardPool={cardPool} />
          ) : (
            <div className="editorial-empty-state">
              <h3>Waiting for the first snapshot</h3>
              <p>The author job has started, but the first loading card has not arrived yet.</p>
            </div>
          )}

          {error ? <p className="editorial-error">{error}</p> : null}
        </div>

        <div className="loading-context-card">
          <span className="editorial-metadata-label">Current Story</span>
          <h2>{result?.summary?.title ?? job?.preview.story.title ?? "Preparing summary"}</h2>
          <p>{job?.preview.story.premise ?? "The dossier will populate once the latest snapshot lands."}</p>

          <div className="loading-context-stats">
            <div>
              <span className="editorial-metadata-label">Theme</span>
              <p>{result?.summary?.theme ?? job?.preview.flashcards.find((card) => card.card_id === "theme")?.value ?? "Pending"}</p>
            </div>
            <div>
              <span className="editorial-metadata-label">Tone</span>
              <p>{result?.summary?.tone ?? job?.preview.story.tone ?? "Pending"}</p>
            </div>
            <div>
              <span className="editorial-metadata-label">NPCs</span>
              <p>{result?.summary?.npc_count ?? job?.preview.structure.expected_npc_count ?? 0}</p>
            </div>
            <div>
              <span className="editorial-metadata-label">Beats</span>
              <p>{result?.summary?.beat_count ?? job?.preview.structure.expected_beat_count ?? 0}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="loading-ledger">
        <div className="loading-ledger__cluster">
          <div>
            <span className="editorial-metadata-label">Established</span>
            <p>MMXXVI</p>
          </div>
          <div>
            <span className="editorial-metadata-label">Location</span>
            <p>The Grey Archive</p>
          </div>
        </div>

        <div className="loading-ledger__stamp">
          {result?.summary ? (
            <div className="loading-publish-controls">
              <label className="loading-publish-controls__field">
                <span className="editorial-metadata-label">Publish Visibility</span>
                <select onChange={(event) => onPublishVisibilityChange(event.target.value as StoryVisibility)} value={publishVisibility}>
                  <option value="private">Private</option>
                  <option value="public">Public</option>
                </select>
              </label>
              <button className="studio-button studio-button--primary" disabled={publishLoading} onClick={onPublish} type="button">
                {publishLoading ? "Publishing..." : "Publish to Library"}
              </button>
            </div>
          ) : (
            <>
              <div className="loading-stamp-icon">
                <span className="material-symbols-outlined">autorenew</span>
              </div>
              <div>
                <span className="editorial-metadata-label is-accent">{statusLabel}</span>
                <p>Please wait for the story to manifest.</p>
              </div>
            </>
          )}
        </div>
      </section>

      <StudioFooter />
    </div>
  )
}
