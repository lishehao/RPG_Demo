import { useEffect, useState } from "react"
import { useStoryDetail } from "../../features/play/story-detail/model/use-story-detail"
import { buildClassificationLabel, buildDossierRef } from "../../shared/lib/story-detail"
import { PlayDomainSidebar } from "../../widgets/chrome/play-domain-sidebar"
import { StudioFooter } from "../../widgets/chrome/studio-footer"

type DetailSwitcherPanel = "topology" | "protagonist" | "cast"

export function StoryDetailPage({
  isAuthenticated,
  storyId,
  onOpenLibrary,
  onDeleteToLibrary,
  onOpenPlaySession,
  onRequireAuth,
}: {
  isAuthenticated: boolean
  storyId: string
  onOpenLibrary: (storyId: string) => void
  onDeleteToLibrary: () => void
  onOpenPlaySession: (sessionId: string) => void
  onRequireAuth: () => void
}) {
  const detailState = useStoryDetail(storyId)
  const [activePanel, setActivePanel] = useState<DetailSwitcherPanel>("topology")
  const [activeNavSection, setActiveNavSection] = useState<"overview" | "structure" | "cast" | "start-play">("overview")

  const scrollToSection = (sectionId: string) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  const openSection = (
    sectionId: string,
    navSection: "overview" | "structure" | "cast" | "start-play",
    panel?: DetailSwitcherPanel,
  ) => {
    setActiveNavSection(navSection)
    if (panel) {
      setActivePanel(panel)
    }
    scrollToSection(sectionId)
  }

  const handleCreatePlaySession = async () => {
    if (!isAuthenticated) {
      onRequireAuth()
      return
    }
    const sessionId = await detailState.createPlaySession()
    if (sessionId) {
      onOpenPlaySession(sessionId)
    }
  }

  const handleDeleteStory = async () => {
    const confirmed = window.confirm("Delete this story from your library? This cannot be undone.")
    if (!confirmed) {
      return
    }
    const deleted = await detailState.deleteStory()
    if (deleted) {
      onDeleteToLibrary()
    }
  }

  const presentation = detailState.detail?.presentation
  const playOverview = detailState.detail?.play_overview
  const canManageVisibility = Boolean(presentation?.viewer_can_manage)

  useEffect(() => {
    if (!detailState.loading && !detailState.detail && detailState.error) {
      onDeleteToLibrary()
    }
  }, [detailState.detail, detailState.error, detailState.loading, onDeleteToLibrary])

  return (
    <main className="editorial-page editorial-page--detail">
      <div className="play-domain-layout">
        <PlayDomainSidebar
          items={[
            {
              icon: "menu_book",
              label: "Overview",
              active: activeNavSection === "overview",
              onSelect: () => openSection("story-detail-overview", "overview"),
            },
            {
              icon: "reorder",
              label: "Structure",
              active: activeNavSection === "structure",
              onSelect: () => openSection("story-detail-structure", "structure"),
            },
            {
              icon: "history_edu",
              label: "Cast",
              active: activeNavSection === "cast",
              onSelect: () => openSection("story-detail-cast", "cast", "cast"),
            },
            {
              icon: "north_east",
              label: "Start Play",
              active: activeNavSection === "start-play",
              onSelect: () => openSection("story-detail-start-play", "start-play"),
            },
          ]}
          subtitle={presentation?.status_label ?? "Open for play"}
          title="Story Dossier"
        />

        <section className="detail-canvas">
          {detailState.loading ? (
            <div className="editorial-empty-state">
              <h3>Loading story detail</h3>
              <p>Fetching the published card and preview.</p>
            </div>
          ) : detailState.detail ? (
            <>
              <header className="detail-header">
                <div className="detail-header__meta">
                  <div>
                    <span className="editorial-kicker">{presentation?.dossier_ref ?? buildDossierRef(detailState.detail.story)}</span>
                    <p className="editorial-status-label">Status</p>
                    <p className="detail-header__status">{presentation?.status_label ?? "Open for play"}</p>
                    {presentation?.visibility ? <p className="detail-header__visibility">Visibility: {presentation.visibility}</p> : null}
                  </div>
                </div>

                <div className="detail-header__title">
                  <h1>{detailState.detail.story.title}</h1>
                  <div className="detail-header__chips">
                    <span className="editorial-chip">{detailState.detail.story.theme}</span>
                    <span className="editorial-chip">{detailState.detail.story.tone}</span>
                    <span className="editorial-muted-chip">{presentation?.classification_label ?? buildClassificationLabel(detailState.detail.preview)}</span>
                  </div>
                </div>
              </header>

              <div className="detail-body-grid">
                <section className="detail-main-column detail-anchor-target" id="story-detail-overview">
                  {playOverview ? (
                    <div className="detail-block">
                      <h2>Opening Framing</h2>
                      <p className="detail-premise">{playOverview.opening_narration}</p>
                    </div>
                  ) : null}

                  <div className="detail-block">
                    <h2>Premise</h2>
                    <p className="detail-premise">{detailState.detail.story.premise}</p>
                    <p className="detail-body-copy">{detailState.detail.preview.story.stakes}</p>
                  </div>

                  <div className="detail-split-copy">
                    <div>
                      <span className="editorial-metadata-label">Theme</span>
                      <p>{detailState.detail.story.theme}</p>
                    </div>
                    <div>
                      <span className="editorial-metadata-label">Tone</span>
                      <p>{detailState.detail.story.tone}</p>
                    </div>
                  </div>

                  <div className="detail-structure-card detail-anchor-target" id="story-detail-structure">
                    <span className="editorial-metadata-label">Narrative Structure</span>
                    <div className="detail-structure-list">
                      {detailState.detail.preview.beats.map((beat, index) => (
                        <div className="detail-structure-row" key={beat.title}>
                          <div>
                            <strong>
                              Act {index + 1}: {beat.title}
                            </strong>
                            <p>{beat.goal}</p>
                          </div>
                          <span>{beat.milestone_kind}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="detail-cast-switcher detail-anchor-target" id="story-detail-cast">
                    <div className="detail-cast-switcher__header">
                      <span className="editorial-metadata-label">Cast Session</span>
                      <div className="detail-cast-switcher__tabs" role="tablist" aria-label="Story detail supporting cards">
                        <button
                          aria-selected={activePanel === "topology"}
                          className={`detail-cast-switcher__tab ${activePanel === "topology" ? "is-active" : ""}`}
                          onClick={() => setActivePanel("topology")}
                          role="tab"
                          type="button"
                        >
                          Topology
                        </button>
                        <button
                          aria-selected={activePanel === "protagonist"}
                          className={`detail-cast-switcher__tab ${activePanel === "protagonist" ? "is-active" : ""}`}
                          onClick={() => setActivePanel("protagonist")}
                          role="tab"
                          type="button"
                        >
                          Player Role
                        </button>
                        <button
                          aria-selected={activePanel === "cast"}
                          className={`detail-cast-switcher__tab ${activePanel === "cast" ? "is-active" : ""}`}
                          onClick={() => setActivePanel("cast")}
                          role="tab"
                          type="button"
                        >
                          Cast Manifest
                        </button>
                      </div>
                    </div>

                    <div className="detail-cast-switcher__panel" role="tabpanel">
                      {activePanel === "topology" ? (
                        <div className="detail-side-list">
                          <div className="detail-side-list__item">
                            <div className="detail-side-list__rule" />
                            <div>
                              <strong>{detailState.detail.story.topology}</strong>
                              <p>Cast topology from the published story card.</p>
                            </div>
                          </div>
                          <div className="detail-side-list__item">
                            <div className="detail-side-list__rule is-muted" />
                            <div>
                              <strong>{detailState.detail.preview.structure.expected_beat_count} authored beats</strong>
                              <p>Preview structure locked before play begins.</p>
                            </div>
                          </div>
                        </div>
                      ) : null}

                      {activePanel === "protagonist" ? (
                        playOverview ? (
                          <div className="detail-side-list">
                            <div className="detail-side-list__item">
                              <div className="detail-side-list__rule" />
                              <div>
                                <strong>{playOverview.protagonist.title}</strong>
                                <p>{playOverview.protagonist.mandate}</p>
                              </div>
                            </div>
                            <div className="detail-side-list__item">
                              <div className="detail-side-list__rule is-muted" />
                              <div>
                                <strong>{playOverview.runtime_profile_label}</strong>
                                <p>{playOverview.protagonist.identity_summary}</p>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <p className="detail-body-copy">No protagonist setup is available for this story.</p>
                        )
                      ) : null}

                      {activePanel === "cast" ? (
                        <div className="detail-manifest">
                          {detailState.detail.preview.cast_slots.map((slot) => (
                            <div className="detail-manifest__row" key={slot.slot_label}>
                              <strong>{slot.slot_label}</strong>
                              <span>{slot.public_role}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </section>

                <aside className="detail-side-column">
                  <div className="detail-start-card detail-anchor-target" id="story-detail-start-play">
                    {canManageVisibility ? (
                      <label className="detail-visibility-control">
                        <span className="editorial-metadata-label">Visibility</span>
                        <select
                          disabled={detailState.visibilityLoading}
                          onChange={(event) => {
                            void detailState.updateVisibility(event.target.value as "private" | "public")
                          }}
                          value={detailState.detail.presentation?.visibility ?? detailState.detail.story.visibility}
                        >
                          <option value="private">Private</option>
                          <option value="public">Public</option>
                        </select>
                      </label>
                    ) : null}

                    <span className="editorial-metadata-label">Ready to Play</span>
                    <div className="detail-start-card__copy">
                      <strong>{playOverview?.protagonist.title ?? "Session Entry"}</strong>
                      <p>
                        {playOverview
                          ? "You have the opening framing, runtime profile, and turn budget. Start when you are ready to move from dossier reading into action."
                          : "This story is ready to move from dossier reading into a live play session."}
                      </p>
                    </div>

                    <div className="detail-start-card__meta">
                      <div>
                        <span className="editorial-metadata-label">Engine</span>
                        <p>{presentation?.engine_label ?? "System ready"}</p>
                      </div>
                      {playOverview ? (
                        <>
                          <div>
                            <span className="editorial-metadata-label">Runtime Profile</span>
                            <p>{playOverview.runtime_profile_label}</p>
                          </div>
                          <div>
                            <span className="editorial-metadata-label">Max Turns</span>
                            <p>{playOverview.max_turns}</p>
                          </div>
                        </>
                      ) : null}
                    </div>

                    <button className="studio-button studio-button--primary studio-button--wide" disabled={detailState.playLoading} onClick={() => void handleCreatePlaySession()} type="button">
                      {detailState.playLoading ? "Creating Session..." : isAuthenticated ? "Start Play Session" : "Sign In to Start Play"}
                    </button>
                    {canManageVisibility ? (
                      <button className="studio-button studio-button--secondary" disabled={detailState.deleteLoading} onClick={() => void handleDeleteStory()} type="button">
                        {detailState.deleteLoading ? "Deleting..." : "Delete Story"}
                      </button>
                    ) : null}
                    <button className="studio-button studio-button--ghost" onClick={() => onOpenLibrary(storyId)} type="button">
                      Back to Library
                    </button>
                  </div>
                </aside>
              </div>

              {detailState.error ? <p className="editorial-error">{detailState.error}</p> : null}
            </>
          ) : (
            <div className="editorial-empty-state">
              <h3>Story unavailable</h3>
              <p>{detailState.error ?? "This story could not be loaded from the current library."}</p>
              <button className="studio-button studio-button--secondary" onClick={onDeleteToLibrary} type="button">
                Back to Library
              </button>
            </div>
          )}

          <StudioFooter />
        </section>
      </div>
    </main>
  )
}
