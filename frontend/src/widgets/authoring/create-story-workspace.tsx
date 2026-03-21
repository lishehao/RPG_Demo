import type { FormEvent } from "react"
import type { AuthorPreviewResponse } from "../../index"
import { StreamingText } from "../../shared/ui/streaming-text"
import { StudioFooter } from "../chrome/studio-footer"

export function CreateStoryWorkspace({
  seed,
  preview,
  previewLoading,
  jobLoading,
  error,
  onSeedChange,
  onRequestPreview,
  onCreateAuthorJob,
  onOpenLibrary,
}: {
  seed: string
  preview: AuthorPreviewResponse | null
  previewLoading: boolean
  jobLoading: boolean
  error: string | null
  onSeedChange: (value: string) => void
  onRequestPreview: () => void
  onCreateAuthorJob: () => void
  onOpenLibrary: () => void
}) {
  const primaryActionLabel = preview ? (jobLoading ? "Starting Authoring..." : "Start Authoring") : previewLoading ? "Generating Preview..." : "Generate Preview"
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onRequestPreview()
  }

  return (
    <div className="editorial-page editorial-page--create">
      <div className="create-layout">
        <section className="create-main">
          <p className="editorial-kicker">New Project</p>
          <h1 className="editorial-display">Start with a story seed</h1>

          <form className="create-form" onSubmit={handleSubmit}>
            <div className="create-form__lead">
              <label className="create-seed-label" htmlFor="story-seed-input">
                Story Seed (English)
              </label>
              <p className="create-seed-help">
                One or two sentences on the protagonist, the pressure, and the manipulation.
              </p>
            </div>
            <textarea
              aria-label="Story Seed"
              className="create-seed-input"
              id="story-seed-input"
              onChange={(event) => onSeedChange(event.target.value)}
              placeholder="Example: A bridge superintendent discovers ration convoy diversions were staged to justify emergency command powers."
              rows={6}
              value={seed}
            />

            <div className="create-actions">
              <button
                className="studio-button studio-button--primary"
                disabled={preview ? jobLoading : previewLoading}
                onClick={preview ? onCreateAuthorJob : undefined}
                type={preview ? "button" : "submit"}
              >
                {primaryActionLabel}
              </button>
              <button
                className="studio-button studio-button--secondary"
                onClick={preview ? () => onRequestPreview() : onOpenLibrary}
                type={preview ? "button" : "button"}
              >
                {preview ? "Refresh Preview" : "Browse Library"}
              </button>
              {preview ? (
                <button className="studio-button studio-button--ghost" onClick={onOpenLibrary} type="button">
                  Browse Library
                </button>
              ) : null}
            </div>

            {error ? <p className="editorial-error">{error}</p> : null}
          </form>

          <div className="create-footnotes">
            <div>
              <span className="editorial-metadata-label">Methodology</span>
              <p>Our studio expands the seed into a playable dossier without changing the frontend contract surface.</p>
            </div>
            <div>
              <span className="editorial-metadata-label">System Version</span>
              <p>
                v4.2.0 "The Archivist"
                <br />
                Preview engine active.
              </p>
            </div>
          </div>
        </section>

        <aside className="create-preview-pane">
          <div className="create-preview-pane__header">
            <h2>Structural Preview</h2>
            <span className={`editorial-badge ${previewLoading ? "is-loading" : preview ? "is-ready" : ""}`}>
              {previewLoading ? "Generating" : preview ? "Preview Ready" : "Awaiting Input"}
            </span>
          </div>

          <div className={`preview-card ${previewLoading ? "is-loading" : ""}`}>
            <div className="preview-title-lockup">
              <div className="preview-title-lockup__rule" />
              <div>
                <span className="editorial-metadata-label">Working Title</span>
                <h3>
                  {previewLoading && !preview ? (
                    "Building the dossier"
                  ) : preview?.story.title ? (
                    <StreamingText delayMs={80} speedMs={18} text={preview.story.title} />
                  ) : (
                    "No story drafted yet"
                  )}
                </h3>
              </div>
            </div>

            {previewLoading ? (
              <div className="preview-loading-shell" aria-hidden="true">
                <span className="preview-loading-shell__line preview-loading-shell__line--lead" />
                <span className="preview-loading-shell__line preview-loading-shell__line--body" />
                <span className="preview-loading-shell__line preview-loading-shell__line--body" />
                <span className="preview-loading-shell__line preview-loading-shell__line--tail" />
                <div className="preview-loading-shell__grid">
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : (
              <>
                <div className="preview-detail-list">
                  <div>
                    <span className="editorial-metadata-label">Premise Archetype</span>
                    <p>
                      {preview?.story.premise ? (
                        <StreamingText delayMs={140} speedMs={8} text={preview.story.premise} />
                      ) : (
                        "Generate a structural preview to populate the dossier."
                      )}
                    </p>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">Tone Profile</span>
                    <p>{preview?.story.tone ? <StreamingText delayMs={260} speedMs={16} text={preview.story.tone} /> : "Pending"}</p>
                  </div>
                </div>

                <div className="preview-stat-grid">
                  <div>
                    <span className="editorial-metadata-label">Core Theme</span>
                    <p>{preview?.flashcards.find((card) => card.card_id === "theme")?.value ?? "Pending"}</p>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">Structure</span>
                    <p>{preview?.flashcards.find((card) => card.card_id === "cast_topology")?.value ?? "Pending"}</p>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">Exp. NPCs</span>
                    <strong>{preview?.structure.expected_npc_count ?? "00"}</strong>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">Narrative Beats</span>
                    <strong>{preview?.structure.expected_beat_count ?? "00"}</strong>
                  </div>
                </div>
              </>
            )}

            <p className="preview-footnote">
              * Figures are projected from the current preview contract and will stabilize once authoring begins.
            </p>
          </div>

          <div className="editorial-note">
            <span className="material-symbols-outlined">history_edu</span>
            <p>
              Latest focus: <span>{preview?.theme.primary_theme ?? "No theme routed"}</span>
            </p>
          </div>
        </aside>
      </div>

      <StudioFooter />
    </div>
  )
}
