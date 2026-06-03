import { type CSSProperties, useEffect, useState } from "react"
import type { NarrativePublicReplayResponse, NarrativeStoryMessage } from "../../api/contracts"
import { useApi } from "../../app/api-context"
import { friendlyError } from "../../shared/lib/friendly-error"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../shared/lib/i18n"
import { LoadingShim } from "../../shared/ui/loading-shim"
import { EmptyState } from "../../shared/ui/empty-state"
import {
  getAdvisorAvatar,
  getCoverForTemplate,
  getEndingIllustration,
} from "../../shared/lib/webtoon-assets"

/**
 * Public, auth-free replay of a completed (or in-progress) session.
 * Anyone with the URL can read the full playthrough including the
 * advisor sidechat. The whole point is to make sharing genuinely
 * compelling — your friend reads YOUR choices and YOUR ending,
 * then can fork the same template to play their own.
 */
export function ReplayPage({
  sessionId,
  onBackHome,
  onOpenTemplate,
}: {
  sessionId: string
  onBackHome: () => void
  onOpenTemplate: (templateId: string) => void
}) {
  const api = useApi()
  const t = useT()
  const { lang } = useLanguage()
  const [replay, setReplay] = useState<NarrativePublicReplayResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Entry mode for shared replay links:
  //   "preview" — hero + 5 highlight records + CTA. The default.
  //   Friends arriving from a shared link see the
  //   shape of the story at a glance, decide if they want to dive in.
  //   "full"    — the original 12-beat read, with skim toggle.
  // Switching is a single tap; preference is per-tab (not persisted).
  const [viewMode, setViewMode] = useState<"preview" | "full">("preview")
  // Skim mode: collapse narrator beats to a 3-line preview by default.
  // Friends opening a 12-turn replay link don't necessarily want to
  // read all 4000 words — they want to see the shape, then expand
  // the bits that catch their eye. Click a beat to expand it.
  const [skimMode, setSkimMode] = useState(true)
  const [expandedOrds, setExpandedOrds] = useState<Set<number>>(new Set())
  const toggleBeat = (ord: number) => {
    setExpandedOrds((prev) => {
      const next = new Set(prev)
      if (next.has(ord)) next.delete(ord)
      else next.add(ord)
      return next
    })
  }

  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .getNarrativePublicReplay(sessionId)
      .then((r) => {
        if (cancelled) return
        setReplay(r)
      })
      .catch((err) => {
        if (cancelled) return
        setError(friendlyError(err, t("replay.error_load_failed")))
      })
    return () => {
      cancelled = true
    }
  }, [api, sessionId, t])

  if (!replay) {
    return (
      <div style={rpStyles.page}>
        {error ? (
          <EmptyState
            title={t("replay.error_title")}
            hint={error}
            action={
              <button
                style={rpStyles.primaryAction}
                type="button"
                onClick={onBackHome}
              >
                {t("replay.error_back_plaza")}
              </button>
            }
          />
        ) : (
          <LoadingShim label={t("replay.loading_label")} />
        )}
      </div>
    )
  }

  const endingLabelText = replay.ending
    ? ENDING_LABEL_DISPLAY[lang][replay.ending.label] ?? replay.ending.label
    : ""
  const replayTitle = replayDisplayTitle({
    title: replay.template_title,
    completed: replay.completed,
    endingLabel: endingLabelText,
    t,
  })
  const replaySeedText = replay.template_seed.trim()
  // Build a synthetic template-like object so we can reuse the cover helper.
  const templateLike = {
    template_id: sessionId, // stable hash on session_id for the cover pick
    seed: replaySeedText || replayTitle,
    title: replayTitle,
    cast: replay.cast,
  }
  // For completed replays, use the ending-specific illustration as the
  // hero — that's the visual identity of *this particular* playthrough.
  // Incomplete replays fall back to the shell cover.
  const cover = replay.completed && replay.ending
    ? getEndingIllustration(replay.ending.label)
    : getCoverForTemplate(templateLike)
  const advisorAvatar = getAdvisorAvatar(sessionId, replay.advisor_persona)
  const endingSubtitleText = replay.ending
    ? lang === "en" ? `"${replay.ending.subtitle}"` : `「${replay.ending.subtitle}」`
    : ""
  const castLine = replay.cast.map((c) => c.display_name).join(" · ")
  const hasPreviewHighlights = Boolean(replay.ending?.highlights && replay.ending.highlights.length > 0)
  const castNameById = Object.fromEntries(replay.cast.map((c) => [c.character_id, c.display_name]))
  const finalPlayerMessage = [...replay.messages].reverse().find((m) => m.role === "player")
  const finalNarratorMessage = [...replay.messages].reverse().find((m) => m.role === "narrator")
  const replayPayoffHighlights = replay.ending?.highlights?.slice(0, 3) ?? []
  const replayChangedNames = replayChangedEntityNames(finalNarratorMessage, castNameById)
  const replayChangedText =
    replayChangedNames.length > 0
      ? replayChangedNames.join(" · ")
      : replayPayoffHighlights[0]?.headline ??
        (replay.ending ? (ENDING_LABEL_DISPLAY[lang][replay.ending.label] ?? replay.ending.label) : replay.template_title)
  const replayWhy =
    replayPayoffHighlights.find((h) => h.why_pivotal.trim().length > 0)?.why_pivotal ||
    (replay.ending ? replayLeadSentence(replay.ending.passage, t("replay.payoff_default_why")) : "")
  const replayFinalMove = replaySummarizeFinalMove(finalPlayerMessage, t("replay.payoff_default_move"))

  return (
    <div style={rpStyles.page}>
      {/* Hero: shell cover banner with title + meta */}
      <div
        style={{
          ...rpStyles.hero,
          backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.18) 0%, rgba(20,16,12,0.65) 60%, var(--bg) 100%), url(${cover})`,
        }}
      >
        <div style={rpStyles.heroInner}>
          <button style={rpStyles.crumb} onClick={onBackHome} type="button">
            {t("replay.crumb_back_home")}
          </button>
          <div style={rpStyles.replayBadge}>{t("replay.badge")}</div>
          <h1 style={rpStyles.title}>{replayTitle}</h1>
          {replaySeedText ? <p style={rpStyles.heroSeed}>"{replaySeedText}"</p> : null}
          <div style={rpStyles.heroMetaLine}>
            {castLine ? <span>{castLine}</span> : null}
            {castLine ? <span style={rpStyles.heroMetaDot}>·</span> : null}
            <span>
              {replay.completed
                ? t("replay.completed_meta")
                : t("replay.turns_meta", {
                    current: replay.turn_count,
                    total: replay.turn_budget,
                  })}
            </span>
          </div>
          {replay.completed && replay.ending ? (
            <div style={rpStyles.heroEnding}>
              <div style={rpStyles.heroEndingLabel}>
                {endingLabelText}
              </div>
              <div style={rpStyles.heroEndingSubtitle}>{endingSubtitleText}</div>
            </div>
          ) : (
            <div style={rpStyles.heroIncomplete}>
              {t("replay.in_progress_meta", {
                current: replay.turn_count,
                total: replay.turn_budget,
              })}
            </div>
          )}
          <div style={rpStyles.heroActions}>
            <button
              style={rpStyles.primaryAction}
              onClick={() => replay.template_forkable ? onOpenTemplate(replay.template_id) : onBackHome()}
              type="button"
            >
              {replay.template_forkable ? t("replay.cta_play_template") : t("replay.cta_back_plaza")}
            </button>
          </div>
        </div>
      </div>

      <main style={rpStyles.main}>
        {replay.completed && replay.ending ? (
          <section style={rpStyles.payoffSummary}>
            <div style={rpStyles.payoffTopLine}>
              <span style={rpStyles.payoffKicker}>{t("replay.payoff_kicker")}</span>
              <span style={rpStyles.payoffMeta}>
                {t("replay.payoff_turn_meta", { count: replay.turn_count })}
              </span>
            </div>
            <div style={rpStyles.payoffGrid}>
              <div style={rpStyles.payoffResult}>
                <div style={rpStyles.payoffLabel}>
                  {endingLabelText}
                </div>
                <h2 style={rpStyles.payoffTitle}>{endingSubtitleText}</h2>
                <p style={rpStyles.payoffLead}>
                  {replayLeadSentence(replay.ending.passage, replay.ending.subtitle)}
                </p>
                <div style={rpStyles.payoffFinalMove}>
                  <span style={rpStyles.payoffRowLabel}>{t("replay.payoff_final_move")}</span>
                  <span style={rpStyles.payoffRowText}>{replayFinalMove}</span>
                </div>
              </div>
              <div style={rpStyles.payoffLedger}>
                <div style={rpStyles.payoffLedgerRow}>
                  <span style={rpStyles.payoffLedgerLabel}>{t("replay.payoff_changed")}</span>
                  <span style={rpStyles.payoffLedgerValue}>{replayChangedText}</span>
                </div>
                <div style={rpStyles.payoffLedgerRow}>
                  <span style={rpStyles.payoffLedgerLabel}>{t("replay.payoff_why")}</span>
                  <span style={rpStyles.payoffLedgerValue}>{replayWhy}</span>
                </div>
                <div style={rpStyles.payoffLedgerRow}>
                  <span style={rpStyles.payoffLedgerLabel}>{t("replay.payoff_highlights")}</span>
                  <span style={rpStyles.payoffLedgerValue}>
                    {replay.ending.highlights && replay.ending.highlights.length > 0
                      ? t("replay.payoff_highlight_count", { count: replay.ending.highlights.length })
                      : t("replay.payoff_no_highlights")}
                  </span>
                </div>
              </div>
            </div>
            {replayPayoffHighlights.length > 0 ? (
              <div style={rpStyles.payoffHighlightStrip}>
                {replayPayoffHighlights.map((h, i) => (
                  <div key={`payoff-${h.beat_ord}-${i}`} style={rpStyles.payoffHighlight}>
                    <span style={rpStyles.payoffHighlightIndex}>{i + 1}</span>
                    <span style={rpStyles.payoffHighlightText}>{h.headline}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        {/* Preview / Full view-mode toggle. Hidden when there are no
            highlights to preview (incomplete run or LLM failure) —
            in that case "full" is the only sensible mode anyway. */}
        {hasPreviewHighlights ? (
          <div style={rpStyles.viewModeRow}>
            <span style={rpStyles.viewModeLabel}>
              {viewMode === "preview" ? t("replay.view_preview") : t("replay.view_full")}
            </span>
            <button
              type="button"
              style={rpStyles.viewModeAction}
              onClick={() => setViewMode(viewMode === "preview" ? "full" : "preview")}
              aria-label={
                viewMode === "preview"
                  ? t("replay.view_full")
                  : t("replay.view_preview")
              }
            >
              {viewMode === "preview" ? t("replay.view_full") : t("replay.view_preview")}
            </button>
          </div>
        ) : null}

        {/* PREVIEW MODE — highlight carousel with CTA. Skipped when
            no ending/highlights or when user picked full mode. */}
        {viewMode === "preview" &&
        replay.ending?.highlights &&
        replay.ending.highlights.length > 0 ? (
          <>
            <section style={rpStyles.section}>
              <div style={rpStyles.sectionLabel}>
                {t("replay.preview_label", { count: replay.ending.highlights.length })}
              </div>
              <p style={rpStyles.previewHint}>{t("replay.preview_hint")}</p>
              <div style={rpStyles.highlightCarousel}>
                {replay.ending.highlights.map((h, i) => (
                  <article key={`${h.beat_ord}-${i}`} style={rpStyles.previewRecord}>
                    <div style={rpStyles.previewRecordIndex}>{i + 1}.</div>
                    <div style={rpStyles.previewRecordText}>
                      <h3 style={rpStyles.previewRecordHeadline}>{h.headline}</h3>
                      <p style={rpStyles.previewRecordBody}>{h.body_excerpt}</p>
                      <p style={rpStyles.previewRecordWhy}>{h.why_pivotal}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            {/* CTA — switch to full read or play yourself. */}
            <div style={rpStyles.cta}>
              <p style={rpStyles.ctaHint}>{t("replay.preview_cta_hint")}</p>
              <div style={rpStyles.ctaRow}>
                <button
                  style={rpStyles.primaryAction}
                  onClick={() => replay.template_forkable ? onOpenTemplate(replay.template_id) : onBackHome()}
                  type="button"
                >
                  {replay.template_forkable ? t("replay.cta_play_template") : t("replay.cta_back_plaza")}
                </button>
                <button
                  style={rpStyles.ctaTextButton}
                  onClick={() => setViewMode("full")}
                  type="button"
                >
                  {t("replay.preview_cta_full")}
                </button>
              </div>
            </div>
          </>
        ) : null}

        {/* FULL MODE — advisor toggle + story column + ending. */}
        {viewMode === "full" || !replay.ending?.highlights || replay.ending.highlights.length === 0 ? (
        <>
        {/* Story column with optional inline advisor messages */}
        <section style={rpStyles.storyColumn}>
          {/* Skim toggle — friends landing on a shared replay don't
              necessarily want to read all 12 narrator beats top to
              bottom. Skim mode collapses each beat to a 3-line
              preview; click any beat to expand. Default is "skim"
              because that matches the entry behavior of someone
              who just opened a link. */}
          <div style={rpStyles.readModeLine}>
            <span style={rpStyles.readModeLabel}>
              {skimMode ? t("replay.skim_compact") : t("replay.skim_full")}
            </span>
            <button
              type="button"
              style={rpStyles.readModeAction}
              onClick={() => setSkimMode((current) => !current)}
              aria-pressed={!skimMode}
            >
              {skimMode ? t("replay.skim_full") : t("replay.skim_compact")}
            </button>
          </div>
          {renderInterleavedStream(replay, advisorAvatar, t, skimMode, expandedOrds, toggleBeat)}

          {/* Ending block at the very bottom */}
          {replay.ending ? (
            <div style={rpStyles.endingDivider}>
              <span style={rpStyles.endingDividerLabel}>{t("replay.ending_divider")}</span>
            </div>
          ) : null}
          {replay.ending ? (
            <div style={rpStyles.endingCard}>
              <div style={rpStyles.endingLabelChip}>
                {endingLabelText}
              </div>
              <h2 style={rpStyles.endingSubtitle}>{endingSubtitleText}</h2>
              <div style={rpStyles.endingPassage}>{replay.ending.passage}</div>
            </div>
          ) : null}
        </section>

        <div style={rpStyles.cta}>
          <p style={rpStyles.ctaHint}>{t("replay.cta_hint")}</p>
          {replay.template_forkable ? (
            <button
              style={rpStyles.primaryAction}
              onClick={() => onOpenTemplate(replay.template_id)}
              type="button"
            >
              {t("replay.cta_play_template")}
            </button>
          ) : null}
          <button
            style={rpStyles.ctaTextButtonMuted}
            onClick={onBackHome}
            type="button"
          >
            {t("replay.cta_back_plaza")}
          </button>
        </div>
        </>
        ) : null}
      </main>
    </div>
  )
}

function replaySummarizeFinalMove(message: NarrativeStoryMessage | undefined, fallback: string): string {
  const raw = message?.content?.trim()
  if (!raw) return fallback
  const leverage = message?.played_leverage?.leverage?.trim()
  return replayClampText(leverage ? `${raw} · ${leverage}` : raw, 170)
}

function replayChangedEntityNames(
  message: NarrativeStoryMessage | undefined,
  castNameById: Record<string, string>,
): string[] {
  const names: string[] = []
  for (const pulse of message?.npc_pulse ?? []) {
    if (pulse.shift === "steady") continue
    const name = replayDisplayNameForEntity(pulse.npc_id, castNameById)
    if (!names.includes(name)) names.push(name)
  }
  return names.slice(0, 3)
}

function replayDisplayTitle({
  title,
  completed,
  endingLabel,
  t,
}: {
  title: string
  completed: boolean
  endingLabel: string
  t: ReturnType<typeof useT>
}): string {
  const cleaned = title.replace(/\s+/g, " ").trim()
  if (cleaned && cleaned !== "Shared private story") return cleaned
  if (completed && endingLabel) {
    return t("replay.private_completed_title", { label: endingLabel })
  }
  return t("replay.private_in_progress_title")
}

function replayDisplayNameForEntity(id: string, castNameById: Record<string, string>): string {
  const direct = castNameById[id]?.trim()
  if (direct) return direct
  const normalizedId = replayNormalizeEntityKey(id)
  for (const [castId, displayName] of Object.entries(castNameById)) {
    if (
      replayNormalizeEntityKey(castId) === normalizedId ||
      replayNormalizeEntityKey(displayName) === normalizedId
    ) {
      return displayName
    }
  }
  return replayHumanizeEntityId(id)
}

function replayNormalizeEntityKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "")
}

function replayHumanizeEntityId(id: string): string {
  const cleaned = id.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
  return cleaned || id
}

function replayLeadSentence(text: string, fallback: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (!cleaned) return fallback
  const sentence = cleaned.match(/^(.{1,180}?[.!?。！？])(\s|$)/u)?.[1] ?? cleaned
  return replayClampText(sentence, 220)
}

function replayClampText(text: string, limit: number): string {
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (cleaned.length <= limit) return cleaned
  return `${cleaned.slice(0, limit).trimEnd()}...`
}

/**
 * The advisor messages are timestamp-less in the replay payload — we don't
 * know exactly which story turn they correspond to. For v1 we render the
 * full advisor track separately from the main story, but keep it as
 * transcript content instead of another control panel. A future enhancement
 * would be to interleave by ord-correlation; for now keep it readable.
 */
function renderInterleavedStream(
  replay: NarrativePublicReplayResponse,
  advisorAvatar: string,
  t: ReturnType<typeof useT>,
  skimMode: boolean,
  expandedOrds: Set<number>,
  toggleBeat: (ord: number) => void,
) {
  return (
    <>
      {replay.messages.map((m) =>
        m.role === "narrator" ? (
          (() => {
            const isExpanded = !skimMode || expandedOrds.has(m.ord)
            return (
              <article
                key={`n-${m.ord}`}
                style={{
                  ...rpStyles.narratorBeat,
                  ...(skimMode ? { cursor: "pointer" } : null),
                }}
                onClick={() => skimMode && toggleBeat(m.ord)}
                role={skimMode ? "button" : undefined}
                tabIndex={skimMode ? 0 : undefined}
                aria-expanded={skimMode ? isExpanded : undefined}
                onKeyDown={(e) => {
                  if (skimMode && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault()
                    toggleBeat(m.ord)
                  }
                }}
              >
                <div
                  style={{
                    ...rpStyles.narratorText,
                    ...(isExpanded ? null : rpStyles.narratorTextSkim),
                  }}
                >
                  {m.content}
                </div>
                {!isExpanded ? (
                  <div style={rpStyles.skimMore}>{t("replay.skim_expand")}</div>
                ) : null}
                {m.chosen_option_index != null && m.options.length > 0 ? (
                  <div style={rpStyles.chosenChip}>
                    <span style={rpStyles.chosenLabel}>{t("replay.chosen_label")}</span>
                    {" "}
                    <span style={rpStyles.chosenText}>
                      {m.options[m.chosen_option_index]?.label ?? "?"}
                    </span>
                  </div>
                ) : null}
              </article>
            )
          })()
        ) : (
          <article key={`p-${m.ord}`} style={rpStyles.playerBeat}>
            <div style={rpStyles.playerLabel}>{t("replay.player_label")}</div>
            <div style={rpStyles.playerText}>{m.content}</div>
          </article>
        ),
      )}

      {/* Advisor block (collapsed/expanded). Rendered below the main story
          stream as a separate vertical track, since we can't reliably
          interleave by turn without additional ord metadata. */}
      {replay.advisor_messages.length > 0 ? (
        <section style={rpStyles.advisorTrack}>
          <div style={rpStyles.advisorTrackHeader}>
            <img
              src={advisorAvatar}
              alt=""
              style={rpStyles.advisorTrackAvatar}
              loading="lazy"
            />
            <div style={rpStyles.advisorTrackTitle}>{t("replay.advisor_track_title")}</div>
          </div>
          {replay.advisor_messages.map((m) => (
            <div
              key={`a-${m.role}-${m.ord}`}
              style={
                m.role === "player" ? rpStyles.advisorRowPlayer : rpStyles.advisorRowAdvisor
              }
            >
              <div style={rpStyles.advisorTranscriptLine}>
                <span
                  style={{
                    ...rpStyles.advisorSpeaker,
                    ...(m.role === "player" ? rpStyles.advisorSpeakerPlayer : null),
                  }}
                >
                  {m.role === "player"
                    ? t("replay.advisor_speaker_player")
                    : t("replay.advisor_speaker_advisor")}
                </span>
                <div
                  style={
                    m.role === "player"
                      ? rpStyles.advisorBubblePlayer
                      : rpStyles.advisorBubbleAdvisor
                  }
                >
                  {m.content}
                </div>
              </div>
            </div>
          ))}
        </section>
      ) : null}
    </>
  )
}

const rpStyles: Record<string, CSSProperties> = {
  page: { minHeight: "100%", background: "var(--bg)" },
  center: {
    padding: 80,
    textAlign: "center",
    color: "var(--text-muted)",
    fontSize: 14,
  },

  hero: {
    width: "100%",
    minHeight: 320,
    backgroundSize: "cover",
    backgroundPosition: "center",
    color: "white",
    display: "flex",
    alignItems: "flex-end",
  },
  heroInner: {
    width: "100%",
    maxWidth: 720,
    margin: "0 auto",
    padding: "32px 32px 60px",
  },
  crumb: {
    display: "block",
    width: "fit-content",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.22)",
    color: "white",
    fontSize: 12.5,
    cursor: "pointer",
    padding: "0 0 4px",
    borderRadius: 0,
    marginBottom: 18,
  },
  replayBadge: {
    display: "inline-block",
    padding: 0,
    background: "transparent",
    color: "var(--accent)",
    borderRadius: 0,
    fontSize: 12.5,
    letterSpacing: 0,
    fontWeight: 650,
    marginBottom: 14,
  },
  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 38,
    lineHeight: 1.18,
    fontWeight: 400,
    margin: "0 0 12px",
    color: "white",
    textShadow: "0 2px 18px rgba(0,0,0,0.5)",
  },
  heroSeed: {
    fontSize: 14,
    color: "rgba(255,255,255,0.78)",
    fontStyle: "italic",
    margin: "0 0 10px",
    lineHeight: 1.6,
  },
  heroMetaLine: {
    display: "flex",
    alignItems: "baseline",
    flexWrap: "wrap" as const,
    gap: 7,
    marginBottom: 22,
    color: "rgba(255,255,255,0.62)",
    fontSize: 12,
    lineHeight: 1.4,
  },
  heroMetaDot: {
    color: "rgba(245,200,120,0.70)",
  },
  heroEnding: {
    display: "inline-flex",
    flexDirection: "column",
    gap: 6,
    padding: "4px 0 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  heroEndingLabel: {
    display: "inline-block",
    padding: 0,
    background: "transparent",
    color: "var(--accent)",
    borderRadius: 0,
    fontSize: 12,
    fontWeight: 600,
    width: "fit-content",
  },
  heroEndingSubtitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 18,
    lineHeight: 1.4,
    color: "white",
  },
  heroIncomplete: {
    display: "inline-block",
    padding: "4px 0 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    fontSize: 13,
    color: "rgba(255,255,255,0.85)",
  },
  heroActions: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap" as const,
    gap: 14,
    marginTop: 18,
  },
  primaryAction: {
    width: "fit-content",
    padding: "5px 0 6px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.44)",
    borderRadius: 0,
    color: "rgba(255,226,172,0.96)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 850,
    lineHeight: 1.2,
    textAlign: "left",
  },
  main: { maxWidth: 720, margin: "-40px auto 0", padding: "0 32px 80px", position: "relative", zIndex: 2 },

  payoffSummary: {
    marginBottom: 28,
    padding: "20px 0 22px",
    borderTop: "1px solid rgba(245,200,120,0.22)",
    borderBottom: "1px solid rgba(255,255,255,0.09)",
    background: "linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.012))",
  },
  payoffTopLine: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    gap: 14,
    flexWrap: "wrap" as const,
    marginBottom: 18,
  },
  payoffKicker: {
    color: "rgba(245,200,120,0.92)",
    fontSize: 12,
    lineHeight: 1.35,
    fontWeight: 760,
    letterSpacing: 0,
  },
  payoffMeta: {
    color: "var(--text-muted)",
    fontSize: 12,
    lineHeight: 1.35,
    fontWeight: 650,
  },
  payoffGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 22,
    alignItems: "start",
  },
  payoffResult: {
    minWidth: 0,
  },
  payoffLabel: {
    color: "var(--accent)",
    fontSize: 12.5,
    lineHeight: 1.35,
    fontWeight: 700,
    marginBottom: 12,
  },
  payoffTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 24,
    lineHeight: 1.32,
    fontWeight: 400,
    color: "var(--text)",
    margin: "0 0 14px",
  },
  payoffLead: {
    margin: "0 0 18px",
    color: "rgba(255,235,210,0.88)",
    fontFamily: "var(--font-narrative)",
    fontSize: 15,
    lineHeight: 1.65,
  },
  payoffFinalMove: {
    display: "grid",
    gridTemplateColumns: "94px minmax(0, 1fr)",
    gap: 12,
    padding: "12px 0 0",
    borderTop: "1px solid rgba(255,255,255,0.085)",
  },
  payoffRowLabel: {
    color: "rgba(245,200,120,0.78)",
    fontSize: 11.5,
    lineHeight: 1.4,
    fontWeight: 760,
  },
  payoffRowText: {
    color: "var(--text)",
    fontSize: 13,
    lineHeight: 1.6,
  },
  payoffLedger: {
    borderTop: "1px solid rgba(255,255,255,0.085)",
  },
  payoffLedgerRow: {
    display: "grid",
    gridTemplateColumns: "96px minmax(0, 1fr)",
    gap: 12,
    padding: "12px 0",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  payoffLedgerLabel: {
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.45,
    fontWeight: 700,
  },
  payoffLedgerValue: {
    color: "rgba(255,235,210,0.9)",
    fontSize: 13,
    lineHeight: 1.55,
  },
  payoffHighlightStrip: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 0,
    marginTop: 14,
    borderTop: "1px solid rgba(255,255,255,0.075)",
  },
  payoffHighlight: {
    display: "grid",
    gridTemplateColumns: "24px minmax(0, 1fr)",
    gap: 8,
    padding: "12px 12px 0 0",
    borderRight: "1px solid rgba(255,255,255,0.055)",
  },
  payoffHighlightIndex: {
    color: "rgba(245,200,120,0.72)",
    fontFamily: "var(--font-narrative)",
    fontSize: 12,
    lineHeight: 1.35,
  },
  payoffHighlightText: {
    color: "var(--text)",
    fontSize: 12.5,
    lineHeight: 1.45,
  },

  section: { marginBottom: 28 },
  sectionLabel: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    letterSpacing: 0,
    fontWeight: 650,
    marginBottom: 10,
  },
  storyColumn: {},
  viewModeRow: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 5,
    flexWrap: "wrap" as const,
    margin: "0 0 24px",
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  viewModeLabel: {
    color: "rgba(245,200,120,0.78)",
    fontSize: 12.5,
    lineHeight: 1.25,
    fontWeight: 720,
  },
  viewModeAction: {
    background: "transparent",
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    color: "var(--text-muted)",
    fontSize: 12.5,
    padding: "0 0 3px",
    borderRadius: 0,
    borderBottom: "1px solid rgba(255,255,255,0.14)",
    letterSpacing: 0,
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 650,
  },
  highlightCarousel: {
    display: "grid",
    gridAutoFlow: "row",
    gap: 18,
    marginTop: 12,
  },
  previewRecord: {
    padding: "4px 0 10px",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "grid",
    gridTemplateColumns: "44px minmax(0, 1fr)",
    gap: 16,
  },
  previewRecordIndex: {
    fontFamily: "var(--font-narrative)",
    fontSize: 13,
    fontWeight: 500,
    letterSpacing: 0,
    color: "rgba(245,200,120,0.62)",
  },
  previewRecordText: {
    minWidth: 0,
  },
  previewRecordHeadline: {
    fontFamily: "var(--font-narrative)",
    fontSize: 19,
    fontWeight: 500,
    color: "rgba(255,235,210,0.96)",
    lineHeight: 1.3,
    margin: 0,
  },
  previewRecordBody: {
    fontFamily: "var(--font-narrative)",
    fontSize: 14.5,
    lineHeight: 1.7,
    color: "var(--text)",
    margin: 0,
    fontStyle: "italic" as const,
  },
  previewRecordWhy: {
    fontSize: 12.5,
    lineHeight: 1.55,
    color: "var(--text-muted)",
    margin: 0,
  },
  previewHint: {
    fontSize: 13,
    color: "var(--text-muted)",
    lineHeight: 1.6,
    margin: "8px 0 0",
  },
  ctaRow: {
    display: "flex",
    gap: 20,
    flexWrap: "wrap" as const,
    alignItems: "center",
    justifyContent: "flex-start",
  },
  readModeLine: {
    marginBottom: 24,
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 5,
    flexWrap: "wrap" as const,
  },
  readModeLabel: {
    color: "rgba(245,200,120,0.78)",
    fontSize: 12,
    lineHeight: 1.25,
    fontWeight: 720,
  },
  readModeAction: {
    background: "transparent",
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    borderBottom: "1px solid rgba(255,255,255,0.14)",
    borderRadius: 0,
    color: "var(--text-muted)",
    fontSize: 12,
    padding: "0 0 3px",
    letterSpacing: 0,
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 650,
  },
  narratorBeat: { marginBottom: 28 },
  narratorText: {
    fontFamily: "var(--font-narrative)",
    fontSize: 16,
    lineHeight: 1.85,
    color: "var(--text)",
    whiteSpace: "pre-wrap",
  },
  // Skim mode: clamp narrator content to 3 lines with a soft fade
  // at the bottom so it reads as "more below" rather than a hard cut.
  narratorTextSkim: {
    display: "-webkit-box",
    WebkitLineClamp: 3,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
    maskImage: "linear-gradient(180deg, var(--text) 60%, transparent)",
    WebkitMaskImage: "linear-gradient(180deg, var(--text) 60%, transparent)",
  },
  skimMore: {
    fontSize: 11.5,
    color: "var(--accent)",
    marginTop: 8,
    letterSpacing: 0,
    cursor: "pointer",
  },
  chosenChip: {
    marginTop: 12,
    fontSize: 12,
    color: "var(--text-faint)",
    display: "block",
    gap: 8,
    padding: "5px 0",
    border: "none",
    borderRadius: 0,
    background: "transparent",
  },
  chosenLabel: { letterSpacing: 0, fontWeight: 650, marginRight: 6 },
  chosenText: { color: "var(--text-muted)" },

  playerBeat: { marginBottom: 24, paddingLeft: 0 },
  playerLabel: {
    fontSize: 12,
    color: "var(--accent)",
    letterSpacing: 0,
    fontWeight: 650,
    marginBottom: 4,
  },
  playerText: {
    fontSize: 14,
    lineHeight: 1.6,
    color: "var(--text-muted)",
    fontStyle: "italic",
  },

  advisorTrack: {
    marginTop: 42,
    padding: "18px 0 0",
    background: "transparent",
    borderRadius: 0,
    border: "none",
    borderTop: "1px solid rgba(255,255,255,0.075)",
  },
  advisorTrackHeader: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
    paddingBottom: 4,
  },
  advisorTrackAvatar: { width: 32, height: 32, borderRadius: "50%", objectFit: "cover" },
  advisorTrackTitle: { fontSize: 13, color: "var(--text)", letterSpacing: 0, fontWeight: 650 },
  advisorRowPlayer: { display: "block", marginBottom: 12 },
  advisorRowAdvisor: { display: "block", marginBottom: 12 },
  advisorTranscriptLine: {
    display: "grid",
    gridTemplateColumns: "72px minmax(0, 1fr)",
    alignItems: "baseline",
    gap: 12,
  },
  advisorSpeaker: {
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.4,
    fontWeight: 650,
    letterSpacing: 0,
  },
  advisorSpeakerPlayer: {
    color: "rgba(212,168,83,0.72)",
  },
  advisorBubblePlayer: {
    background: "transparent",
    color: "rgba(255,236,198,0.90)",
    padding: 0,
    borderRadius: 0,
    fontSize: 13,
    lineHeight: 1.55,
    maxWidth: "100%",
  },
  advisorBubbleAdvisor: {
    background: "transparent",
    color: "var(--text)",
    padding: 0,
    borderRadius: 0,
    fontSize: 13,
    lineHeight: 1.6,
    maxWidth: "100%",
    border: "none",
  },

  endingDivider: {
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-start",
    margin: "40px 0 18px",
    paddingTop: 18,
    borderTop: "1px solid rgba(255,255,255,0.085)",
  },
  endingDividerLabel: {
    background: "transparent",
    padding: 0,
    fontSize: 12.5,
    color: "var(--text-muted)",
    letterSpacing: 0,
    fontWeight: 650,
  },
  endingCard: {
    padding: "20px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    boxShadow: "none",
  },
  endingLabelChip: {
    display: "inline-block",
    padding: 0,
    background: "transparent",
    color: "var(--accent)",
    borderRadius: 0,
    fontSize: 13,
    fontWeight: 650,
    letterSpacing: 0,
    marginBottom: 16,
  },
  endingSubtitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 24,
    lineHeight: 1.35,
    fontWeight: 400,
    margin: "0 0 22px",
    color: "var(--text)",
  },
  endingPassage: {
    fontFamily: "var(--font-narrative)",
    fontSize: 15.5,
    lineHeight: 1.85,
    color: "var(--text)",
    whiteSpace: "pre-wrap",
  },

  cta: {
    marginTop: 56,
    padding: "24px 0 0",
    textAlign: "left",
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: 14,
  },
  ctaTextButton: {
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.32)",
    borderRadius: 0,
    color: "var(--accent)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 700,
    padding: "4px 0",
  },
  ctaTextButtonMuted: {
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 0,
    color: "var(--text-muted)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 650,
    padding: "4px 0",
  },
  ctaHint: { fontSize: 13, color: "var(--text-muted)", margin: 0, lineHeight: 1.5 },
}
