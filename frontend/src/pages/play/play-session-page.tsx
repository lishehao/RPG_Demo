import { useEffect, useState, type FormEvent, type ReactNode } from "react"
import { EndingSummary } from "../../entities/play/ui/ending-summary"
import { StateBarList } from "../../entities/play/ui/state-bar-list"
import { SuggestedActions } from "../../entities/play/ui/suggested-actions"
import { TranscriptView } from "../../entities/play/ui/transcript-view"
import { usePlaySession } from "../../features/play/session/model/use-play-session"
import { PlayDomainSidebar } from "../../widgets/chrome/play-domain-sidebar"
import { StudioFooter } from "../../widgets/chrome/studio-footer"

function formatLedgerLabel(key: string): string {
  return key.replace(/_/g, " ")
}

function formatDelta(value: number): string {
  return value > 0 ? `+${value}` : String(value)
}

function surfaceState(snapshot: ReturnType<typeof usePlaySession>["snapshot"], key: "inventory" | "map") {
  const surface = snapshot?.support_surfaces?.[key]
  if (surface) {
    return surface
  }
  return {
    enabled: false,
    disabled_reason: `${formatLedgerLabel(key)} is not available in the current public session snapshot.`,
  }
}

function PlayMetaPanel({
  title,
  sectionId,
  defaultOpen = false,
  children,
}: {
  title: string
  sectionId?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section className={`play-session-meta__card play-meta-panel play-anchor-target ${open ? "is-open" : "is-collapsed"}`} id={sectionId}>
      <button
        aria-expanded={open}
        className="play-meta-panel__toggle"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className="editorial-metadata-label">{title}</span>
        <span aria-hidden="true" className="material-symbols-outlined play-meta-panel__icon">
          {open ? "remove" : "add"}
        </span>
      </button>

      {open ? <div className="play-meta-panel__body">{children}</div> : null}
    </section>
  )
}

export function PlaySessionPage({
  sessionId,
  onOpenLibrary,
}: {
  sessionId: string
  onOpenLibrary: (storyId?: string) => void
}) {
  const playSession = usePlaySession(sessionId)
  const [activeNavSection, setActiveNavSection] = useState<"transcript" | "chapters" | "research" | "settings">("transcript")
  const inventorySurface = surfaceState(playSession.snapshot, "inventory")
  const mapSurface = surfaceState(playSession.snapshot, "map")
  const hasAvailableSupportSurface = inventorySurface.enabled || mapSurface.enabled
  const scrollToSection = (sectionId: string, navSection: "transcript" | "chapters" | "research" | "settings") => {
    setActiveNavSection(navSection)
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void playSession.submitTurn()
  }

  useEffect(() => {
    if (!playSession.loading && !playSession.snapshot && playSession.error) {
      onOpenLibrary()
    }
  }, [onOpenLibrary, playSession.error, playSession.loading, playSession.snapshot])

  return (
    <main className="editorial-page editorial-page--play">
      <div className="play-domain-layout">
        <PlayDomainSidebar
          footer={
            playSession.snapshot ? (
              <div className="play-sidebar-stats">
                <div>
                  <div className="play-sidebar-stats__row">
                    <span>Progress</span>
                    <span>{playSession.snapshot.progress?.display_percent ?? 0}%</span>
                  </div>
                  <div className="play-sidebar-stats__track">
                    <div className="play-sidebar-stats__fill" style={{ width: `${playSession.snapshot.progress?.display_percent ?? 0}%` }} />
                  </div>
                </div>
                <div className="play-sidebar-stats__meta">
                  <div>
                    <span className="editorial-metadata-label">Story</span>
                    <p>{playSession.snapshot.story_title}</p>
                  </div>
                  <div>
                    <span className="editorial-metadata-label">Beat</span>
                    <p>{playSession.snapshot.beat_title}</p>
                  </div>
                </div>
              </div>
            ) : null
          }
          items={[
            {
              icon: "menu_book",
              label: "Story So Far",
              active: activeNavSection === "transcript",
              onSelect: () => scrollToSection("play-transcript", "transcript"),
            },
            {
              icon: "reorder",
              label: "Progress",
              active: activeNavSection === "chapters",
              onSelect: () => scrollToSection("play-session-meta", "chapters"),
            },
            {
              icon: "history_edu",
              label: "Consequences",
              active: activeNavSection === "research",
              onSelect: () => scrollToSection("play-consequences", "research"),
            },
            ...(hasAvailableSupportSurface
              ? [
                  {
                    icon: "settings",
                    label: "Tools",
                    active: activeNavSection === "settings",
                    onSelect: () => scrollToSection("play-support-surfaces", "settings"),
                  },
                ]
              : []),
          ]}
          subtitle={playSession.snapshot?.beat_title ?? "Live story navigation"}
          title={playSession.snapshot?.story_title ?? "Play Session"}
        />

        <section className="play-canvas">
          {playSession.loading ? (
            <div className="editorial-empty-state">
              <h3>Loading play session</h3>
              <p>Fetching the current snapshot and transcript state.</p>
            </div>
          ) : !playSession.snapshot ? (
            <div className="editorial-empty-state">
              <h3>Session unavailable</h3>
              <p>{playSession.error ?? "This session is not visible to the current account."}</p>
            </div>
          ) : (
            <>
              <div className="play-content-grid">
                <section className="play-transcript-column play-anchor-target" id="play-transcript">
                  <TranscriptView entries={playSession.transcript} pendingPlayerText={playSession.pendingTurnInput} submitting={playSession.submitting} />
                </section>

                <aside className="play-session-meta">
                  {playSession.snapshot?.protagonist ? (
                    <PlayMetaPanel defaultOpen title="Protagonist">
                      <div className="play-session-meta__headline">
                        <strong>{playSession.snapshot.protagonist.title}</strong>
                        <p>{playSession.snapshot.protagonist.mandate}</p>
                      </div>
                      <p className="editorial-support">{playSession.snapshot.protagonist.identity_summary}</p>
                    </PlayMetaPanel>
                  ) : null}

                  <PlayMetaPanel sectionId="play-session-meta" title="Session Metadata">
                    <div className="play-session-meta__headline">
                      <strong>{playSession.snapshot?.story_title}</strong>
                      <p>{playSession.snapshot?.beat_title}</p>
                    </div>
                    {playSession.snapshot?.progress ? (
                      <div className="play-feedback-ledgers">
                        <div>
                          <span className="editorial-metadata-label">Progress Breakdown</span>
                          <ul className="play-feedback-ledgers__list">
                            <li>
                              <span>Completed beats</span>
                              <strong>
                                {playSession.snapshot.progress.completed_beats}/{playSession.snapshot.progress.total_beats}
                              </strong>
                            </li>
                            <li>
                              <span>Current beat</span>
                              <strong>
                                {playSession.snapshot.progress.current_beat_progress}/{playSession.snapshot.progress.current_beat_goal}
                              </strong>
                            </li>
                            <li>
                              <span>Turns</span>
                              <strong>
                                {playSession.snapshot.progress.turn_index}/{playSession.snapshot.progress.max_turns}
                              </strong>
                            </li>
                          </ul>
                        </div>
                      </div>
                    ) : null}
                  </PlayMetaPanel>

                  <PlayMetaPanel defaultOpen title="State Bars">
                    {playSession.snapshot ? <StateBarList bars={playSession.snapshot.state_bars} /> : null}
                  </PlayMetaPanel>

                  {playSession.snapshot?.feedback ? (
                    <PlayMetaPanel sectionId="play-consequences" title="Recent Consequences">
                      <div className="play-feedback-summary">
                        {playSession.snapshot.feedback.last_turn_consequences.length > 0 ? (
                          <ul className="play-feedback-summary__list">
                            {playSession.snapshot.feedback.last_turn_consequences.map((consequence) => (
                              <li key={consequence}>{consequence}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="editorial-support">No turn consequences recorded yet.</p>
                        )}

                        <div className="play-feedback-ledgers">
                          <div>
                            <span className="editorial-metadata-label">Success Ledger</span>
                            <ul className="play-feedback-ledgers__list">
                              {Object.entries(playSession.snapshot.feedback.ledgers.success).map(([key, value]) => (
                                <li key={key}>
                                  <span>{formatLedgerLabel(key)}</span>
                                  <strong>{value}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span className="editorial-metadata-label">Cost Ledger</span>
                            <ul className="play-feedback-ledgers__list">
                              {Object.entries(playSession.snapshot.feedback.ledgers.cost).map(([key, value]) => (
                                <li key={key}>
                                  <span>{formatLedgerLabel(key)}</span>
                                  <strong>{value}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        {Object.keys(playSession.snapshot.feedback.last_turn_axis_deltas).length > 0 ? (
                          <div>
                            <span className="editorial-metadata-label">Axis Deltas</span>
                            <ul className="play-feedback-ledgers__list">
                              {Object.entries(playSession.snapshot.feedback.last_turn_axis_deltas).map(([key, value]) => (
                                <li key={key}>
                                  <span>{formatLedgerLabel(key)}</span>
                                  <strong>{formatDelta(value)}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}

                        {Object.keys(playSession.snapshot.feedback.last_turn_stance_deltas).length > 0 ? (
                          <div>
                            <span className="editorial-metadata-label">Stance Deltas</span>
                            <ul className="play-feedback-ledgers__list">
                              {Object.entries(playSession.snapshot.feedback.last_turn_stance_deltas).map(([key, value]) => (
                                <li key={key}>
                                  <span>{formatLedgerLabel(key)}</span>
                                  <strong>{formatDelta(value)}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}

                        {playSession.snapshot.feedback.last_turn_tags.length > 0 ? (
                          <div>
                            <span className="editorial-metadata-label">Turn Tags</span>
                            <div className="detail-header__chips">
                              {playSession.snapshot.feedback.last_turn_tags.map((tag) => (
                                <span className="editorial-muted-chip" key={tag}>
                                  {formatLedgerLabel(tag)}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </PlayMetaPanel>
                  ) : null}

                  <PlayMetaPanel defaultOpen title="Suggested Actions">
                    {playSession.snapshot ? (
                      <SuggestedActions
                        actions={playSession.snapshot.suggested_actions}
                        onSelect={playSession.selectSuggestedAction}
                        selectedSuggestionId={playSession.selectedSuggestionId}
                      />
                    ) : null}
                  </PlayMetaPanel>

                  <PlayMetaPanel sectionId="play-support-surfaces" title="Support Surfaces">
                    <div className="play-support-surfaces">
                      <button className={`play-support-surface ${inventorySurface.enabled ? "is-enabled" : "is-disabled"}`} disabled={!inventorySurface.enabled} type="button">
                        <strong>Inventory</strong>
                        <span>{inventorySurface.enabled ? "Available" : "Disabled"}</span>
                      </button>
                      <button className={`play-support-surface ${mapSurface.enabled ? "is-enabled" : "is-disabled"}`} disabled={!mapSurface.enabled} type="button">
                        <strong>Map</strong>
                        <span>{mapSurface.enabled ? "Available" : "Disabled"}</span>
                      </button>
                    </div>
                    <div className="play-support-surfaces__notes">
                      {!inventorySurface.enabled && inventorySurface.disabled_reason ? <p>{inventorySurface.disabled_reason}</p> : null}
                      {!mapSurface.enabled && mapSurface.disabled_reason ? <p>{mapSurface.disabled_reason}</p> : null}
                    </div>
                  </PlayMetaPanel>

                  {playSession.snapshot?.ending ? <EndingSummary ending={playSession.snapshot.ending} /> : null}
                </aside>
              </div>

              <form className={`play-input-dock ${playSession.submitting ? "is-submitting" : ""}`} onSubmit={handleSubmit}>
                {playSession.submitting ? (
                  <div className="play-input-dock__status" aria-live="polite">
                    <div className="play-input-dock__signal" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </div>
                    <div className="play-input-dock__status-copy">
                      <strong>Resolving consequences</strong>
                      <p>The system is updating pressure, witnesses, and scene fallout before returning the next beat.</p>
                    </div>
                  </div>
                ) : null}

                <div className="play-input-dock__field">
                  <textarea
                    className="play-input-dock__textarea"
                    disabled={playSession.submitting || playSession.snapshot?.status === "completed"}
                    onChange={(event) => playSession.setInputText(event.target.value)}
                    placeholder="Describe your intent..."
                    rows={1}
                    value={playSession.inputText}
                  />
                  <button className="play-input-dock__submit" disabled={playSession.submitting || playSession.snapshot?.status === "completed"} type="submit">
                    <span className="material-symbols-outlined">north_east</span>
                  </button>
                </div>

                <div className="play-input-dock__meta">
                  <div className="play-input-dock__tools">
                    <button
                      className={!inventorySurface.enabled ? "is-disabled" : ""}
                      disabled={!inventorySurface.enabled}
                      title={inventorySurface.disabled_reason ?? undefined}
                      type="button"
                    >
                      Inventory
                    </button>
                    <button
                      className={!mapSurface.enabled ? "is-disabled" : ""}
                      disabled={!mapSurface.enabled}
                      title={mapSurface.disabled_reason ?? undefined}
                      type="button"
                    >
                      Map
                    </button>
                  </div>

                  <div className="play-input-dock__actions">
                    <button className="studio-button studio-button--ghost" onClick={() => playSession.snapshot && onOpenLibrary(playSession.snapshot.story_id)} type="button">
                      Leave Session
                    </button>
                    <span>{playSession.submitting ? "Submitting turn..." : "Alt + Enter to submit"}</span>
                  </div>
                </div>

                {playSession.error ? <p className="editorial-error">{playSession.error}</p> : null}
              </form>
            </>
          )}

          <StudioFooter />
        </section>
      </div>
    </main>
  )
}
