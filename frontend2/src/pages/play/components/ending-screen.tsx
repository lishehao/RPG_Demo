import { useEffect, useState } from "react"
import { motion, useReducedMotion, type TargetAndTransition } from "motion/react"
import type { NarrativeEnding, NarrativeStoryMessage } from "../../../api/contracts"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../../shared/lib/i18n"
import {
  cascadeDelay,
  itemTransition,
  itemVariants,
  labelChipSpring,
  tapPress,
  transitions,
} from "../../../shared/lib/motion-presets"
import { getEndingIllustration, getTierSplash } from "../../../shared/lib/webtoon-assets"
import { ppStyles } from "../play-styles"
import { parseOptionLabel } from "../play-option-label"

type EndingFallbackRecapItem = {
  ord: number
  turn: number
  move: string
  reaction: string
}

function truncateEndingRecapText(value: string, max = 136): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function buildFallbackEndingRecap(messages: NarrativeStoryMessage[]): EndingFallbackRecapItem[] {
  const playerMessages = messages.filter((message) => message.role === "player")
  return playerMessages
    .slice(-3)
    .map((message) => {
      const parsedMove = parseOptionLabel(message.content)
      const move = truncateEndingRecapText(parsedMove.body || message.content, 118)
      const nextNarrator = messages.find(
        (candidate) => candidate.role === "narrator" && candidate.ord > message.ord,
      )
      return {
        ord: message.ord,
        turn: Math.floor(message.ord / 2) + 1,
        move,
        reaction: nextNarrator
          ? truncateEndingRecapText(nextNarrator.content)
          : "",
      }
    })
    .filter((item) => item.move.length > 0)
}

export function EndingScreen({
  ending,
  sessionId,
  templateId,
  messages,
  bookmarkedOrds,
  shareCopied,
  onShare,
  onReadFullStory,
  onPlayAgain,
  onBackHome,
}: {
  ending: NarrativeEnding
  sessionId: string
  templateId: string
  messages: NarrativeStoryMessage[]
  bookmarkedOrds: Set<number>
  shareCopied: boolean
  onShare: () => void
  onReadFullStory: () => void
  onPlayAgain: () => void
  onBackHome: () => void
}) {
  void templateId
  const t = useT()
  const { lang } = useLanguage()

  // Merge user bookmarks into the LLM's highlight list. User picks
  // get a `userMarked` flag and a synthesized headline / body
  // excerpt so they slot into the same card layout. Dedupe against
  // LLM picks (same ord = the LLM and the user both flagged it,
  // collapse into one card with the badge).
  type DisplayHighlight = {
    beat_ord: number
    headline: string
    body_excerpt: string
    why_pivotal: string
    userMarked: boolean
  }
  const llmHighlights: DisplayHighlight[] = (ending.highlights ?? []).map((h) => ({
    beat_ord: h.beat_ord,
    headline: h.headline,
    body_excerpt: h.body_excerpt,
    why_pivotal: h.why_pivotal,
    userMarked: bookmarkedOrds.has(h.beat_ord),
  }))
  const llmOrds = new Set(llmHighlights.map((h) => h.beat_ord))
  const narratorByOrd = new Map(
    messages.filter((m) => m.role === "narrator").map((m) => [m.ord, m]),
  )
  const userOnlyHighlights: DisplayHighlight[] = Array.from(bookmarkedOrds)
    .filter((ord) => !llmOrds.has(ord))
    .map((ord) => {
      const m = narratorByOrd.get(ord)
      return {
        beat_ord: ord,
        headline: t("play.ending_user_bookmark"),
        body_excerpt: m?.content?.slice(0, 200) ?? "",
        why_pivotal: "",
        userMarked: true,
      }
    })
    .filter((h) => h.body_excerpt.length > 0)
  const mergedHighlights: DisplayHighlight[] = [
    // User-only marks lead so the user's voice is first.
    ...userOnlyHighlights,
    ...llmHighlights,
  ].sort((a, b) => a.beat_ord - b.beat_ord)
  const fallbackRecap = mergedHighlights.length === 0
    ? buildFallbackEndingRecap(messages)
    : []

  // Skip the 1.7s choreography in two cases:
  //  1. User prefers reduced motion (a11y system pref)
  //  2. They've already seen this exact ending in this browser session
  //     — re-opening the run page (back/forward, refresh) shouldn't
  //     replay the splash; it's the first view that earns the
  //     ceremony.
  const reducedMotion = useReducedMotion()
  const [hasSeenBefore] = useState(() => {
    if (typeof window === "undefined") return false
    try {
      return window.sessionStorage.getItem(
        `tiny-stories-ending-seen-${sessionId}`,
      ) === "1"
    } catch {
      return false
    }
  })
  useEffect(() => {
    try {
      window.sessionStorage.setItem(
        `tiny-stories-ending-seen-${sessionId}`,
        "1",
      )
    } catch {
      // sessionStorage unavailable (private mode) — fail silently;
      // worst case the splash plays again on refresh.
    }
  }, [sessionId])
  const skipChoreography = Boolean(reducedMotion) || hasSeenBefore

  // Helper: collapse `initial` state to `false` (= start at animate
  // target, no entrance) and zero out staggered delays when skipping.
  const initialOr = (
    full: TargetAndTransition,
  ): TargetAndTransition | false => (skipChoreography ? false : full)
  const delayOr = (delay: number): number =>
    skipChoreography ? 0 : delay

  const illustration = getEndingIllustration(ending.label)
  const endingDisplayLabel = displayEndingLabel(ending.label, lang)
  const endingSubtitle = lang === "en" ? `"${ending.subtitle}"` : `「${ending.subtitle}」`
  const tier = ending.tier ?? "compromised"
  const tierSplash = getTierSplash(tier)
  const tierVisuals: Record<string, { ribbon: string; labelColor: string; gradient: string; badgeText: string }> = {
    victory: {
      ribbon: t("play.ending_ribbon_victory"),
      badgeText: t("play.ending_tier_victory"),
      labelColor: "rgba(245,210,140,0.96)",
      gradient: "linear-gradient(180deg, rgba(180,140,40,0.0) 0%, rgba(60,40,15,0.55) 75%, var(--bg-elev) 100%)",
    },
    compromised: {
      ribbon: t("play.ending_ribbon_compromised"),
      badgeText: t("play.ending_tier_compromised"),
      labelColor: "var(--text)",
      gradient: "linear-gradient(180deg, rgba(20,16,12,0.15) 0%, rgba(20,16,12,0.6) 75%, var(--bg-elev) 100%)",
    },
    collapsed: {
      ribbon: ending.early_terminated ? t("play.ending_ribbon_early") : t("play.ending_ribbon_collapsed"),
      badgeText: ending.early_terminated ? t("play.ending_tier_early") : t("play.ending_tier_collapsed"),
      labelColor: "rgba(245,180,170,0.96)",
      gradient: "linear-gradient(180deg, rgba(60,10,10,0.25) 0%, rgba(50,8,8,0.78) 75%, var(--bg-elev) 100%)",
    },
  }
  const tv = tierVisuals[tier]
  return (
    <motion.section
      data-play-ending-screen="true"
      style={ppStyles.endingSection}
      initial={skipChoreography ? "animate" : "initial"}
      animate="animate"
      transition={{
        staggerChildren: skipChoreography ? 0 : 0.18,
        delayChildren: delayOr(0.1),
      }}
    >
      <motion.div
        variants={itemVariants}
        transition={itemTransition}
        style={ppStyles.endingDivider}
      >
        <span style={ppStyles.endingDividerLabel}>{tv.ribbon}</span>
      </motion.div>
      <motion.div
        variants={itemVariants}
        transition={itemTransition}
        style={ppStyles.endingCard}
      >
        <div style={ppStyles.endingCardInner}>
          <motion.div
            initial={initialOr({ opacity: 0, scale: 0.6 })}
            animate={{ opacity: 1, scale: 1 }}
            transition={
              skipChoreography
                ? transitions.snap
                : labelChipSpring
            }
            style={{ ...ppStyles.endingLabelChip, color: tv.labelColor }}
          >
            {endingDisplayLabel}
          </motion.div>
          <motion.h2
            initial={initialOr({ opacity: 0, y: 14 })}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: delayOr(0.6), ...itemTransition }}
            style={ppStyles.endingSubtitle}
          >
            {endingSubtitle}
          </motion.h2>
          <motion.div
            initial={initialOr({ opacity: 0 })}
            animate={{ opacity: 1 }}
            transition={{ delay: delayOr(0.85), ...transitions.slow }}
            style={ppStyles.endingPassage}
          >
            {ending.passage}
          </motion.div>

          <motion.div
            data-play-ending-actions="true"
            initial={initialOr({ opacity: 0, y: 8 })}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: delayOr(0.95), ...itemTransition }}
            style={ppStyles.endingActions}
          >
            <span data-play-ending-next-step-label="true" style={ppStyles.endingActionsLabel}>
              {t("play.ending_next_steps")}
            </span>
            <span
              data-play-ending-next-step-hint="true"
              style={ppStyles.endingActionsHint}
            >
              {t("play.ending_next_steps_hint")}
            </span>
            <div style={ppStyles.endingActionsRow}>
              <motion.button
                onClick={onShare}
                type="button"
                style={ppStyles.endingPrimaryAction}
                whileHover={{ scale: 1.02 }}
                whileTap={tapPress}
                key={shareCopied ? "copied" : "default"}
                initial={shareCopied ? { scale: 0.92 } : false}
                animate={shareCopied ? { scale: [0.92, 1.06, 1] } : { scale: 1 }}
                transition={transitions.base}
              >
                {shareCopied ? t("play.ending_share_copied") : t("play.ending_share")}
              </motion.button>
              <motion.button
                data-play-ending-read-full="true"
                style={ppStyles.endingTextAction}
                onClick={onReadFullStory}
                type="button"
                whileHover={{ scale: 1.02 }}
                whileTap={tapPress}
              >
                {t("play.ending_read_full")}
              </motion.button>
              {/* Replay-with-different-role — closes the loop. Without
                  this, finishing a run was a dead end; user had to nav
                  back home → find template → re-pick role. Now it's
                  one click. We deliberately route through the template
                  detail page rather than auto-picking a new role —
                  seeing the role cards is part of the re-engagement. */}
              <motion.button
                style={ppStyles.endingTextAction}
                onClick={onPlayAgain}
                type="button"
                whileHover={{ scale: 1.02 }}
                whileTap={tapPress}
              >
                {t("play.ending_replay")}
              </motion.button>
              <motion.button
                style={ppStyles.endingTextActionMuted}
                onClick={onBackHome}
                type="button"
                whileHover={{ scale: 1.02 }}
                whileTap={tapPress}
              >
                {t("action.back_home")}
              </motion.button>
            </div>
            <p style={ppStyles.endingShareHint}>
              {t("play.ending_share_hint")}
            </p>
          </motion.div>

          {/* Illustrated banner is secondary to the result text: it adds
              ceremony after the player has already read what ending they hit
              and seen the available next actions. */}
          <motion.div
            data-play-ending-illustration="true"
            initial={initialOr({ opacity: 0, scale: 1.04 })}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: delayOr(1.15), ...transitions.slow }}
            style={{
              ...ppStyles.endingHero,
              backgroundImage: `${tv.gradient}, url(${illustration})`,
            }}
          >
            {tierSplash ? (
              <motion.div
                initial={initialOr({ opacity: 0, scale: 1.08 })}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: delayOr(1.25), ...transitions.ceremony }}
                style={{
                  ...ppStyles.endingSplashOverlay,
                  backgroundImage: `url(${tierSplash})`,
                }}
              />
            ) : null}
            <div style={ppStyles.endingTierBadge}>
              <span style={ppStyles.endingTierBadgeText}>{tv.badgeText}</span>
              {ending.early_terminated && ending.failure_trigger ? (
                <span style={ppStyles.endingTierTrigger}>
                  {t("play.ending_trigger_prefix", { trigger: ending.failure_trigger })}
                </span>
              ) : null}
            </div>
          </motion.div>

          {fallbackRecap.length > 0 ? (
            <motion.section
              data-play-ending-recap="fallback"
              initial={initialOr({ opacity: 0, y: 12 })}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: delayOr(1.28), ...itemTransition }}
              style={ppStyles.endingRecapSection}
            >
              <div style={ppStyles.endingRecapLabel}>
                {t("play.ending_recap_title")}
              </div>
              <p style={ppStyles.endingRecapHint}>
                {t("play.ending_recap_hint")}
              </p>
              <div style={ppStyles.endingRecapList}>
                {fallbackRecap.map((item) => (
                  <div key={`ending-recap-${item.ord}`} style={ppStyles.endingRecapItem}>
                    <div style={ppStyles.endingRecapTurn}>
                      {t("play.ending_recap_turn", { turn: item.turn })}
                    </div>
                    <div style={ppStyles.endingRecapMove}>{item.move}</div>
                    {item.reaction ? (
                      <div style={ppStyles.endingRecapReaction}>
                        <span style={ppStyles.endingRecapReactionLabel}>
                          {t("play.ending_recap_reaction")}
                        </span>
                        <span>{item.reaction}</span>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </motion.section>
          ) : null}

        {/* Highlight reel — LLM picks merged with user bookmarks. Kept as
            a text recap instead of a stack of separate cards. */}
        {mergedHighlights.length > 0 ? (
          <motion.section
            initial={initialOr({ opacity: 0, y: 12 })}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: delayOr(1.0), ...itemTransition }}
            style={ppStyles.highlightReel}
          >
            <div style={ppStyles.highlightReelLabel}>
              {t("play.ending_highlights_title", { count: mergedHighlights.length })}
            </div>
            <div style={ppStyles.highlightList}>
              {mergedHighlights.map((h, i) => (
                <motion.div
                  key={`${h.beat_ord}-${i}`}
                  initial={initialOr({ opacity: 0, x: -8 })}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: delayOr(1.05 + cascadeDelay(i, 0.08)), ...itemTransition }}
                  style={{
                    ...ppStyles.highlightCard,
                    ...(h.userMarked ? ppStyles.highlightCardUserMarked : null),
                  }}
                >
                  <div style={ppStyles.highlightHeader}>
                    <span style={ppStyles.highlightIndex}>{i + 1}</span>
                    {h.userMarked ? (
                      <span style={ppStyles.highlightUserMark} aria-label={t("play.bookmark_user_mark_label")}>
                        ★
                      </span>
                    ) : null}
                    <span style={ppStyles.highlightHeadline}>{h.headline}</span>
                  </div>
                  <div style={ppStyles.highlightBody}>{h.body_excerpt}</div>
                  {h.why_pivotal ? (
                    <div style={ppStyles.highlightWhy}>{h.why_pivotal}</div>
                  ) : null}
                </motion.div>
              ))}
            </div>
          </motion.section>
        ) : null}

        {/* Branches — alternate paths the player didn't take, driving replay
            intent without switching into dashboard cards. */}
        {ending.branches && ending.branches.length > 0 ? (
          <motion.section
            initial={initialOr({ opacity: 0, y: 12 })}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: delayOr(1.25), ...itemTransition }}
            style={ppStyles.branchesSection}
          >
            <div style={ppStyles.branchesLabel}>
              {t("play.ending_branches_title", { count: ending.branches.length })}
            </div>
            <p style={ppStyles.branchesHint}>
              {t("play.ending_branches_hint")}
            </p>
            <div style={ppStyles.branchList}>
              {ending.branches.map((b, i) => {
                const tierStyle =
                  b.alternate_ending_tier === "victory"
                    ? ppStyles.branchTierVictory
                    : b.alternate_ending_tier === "collapsed"
                      ? ppStyles.branchTierCollapsed
                      : ppStyles.branchTierCompromised
                return (
                  <motion.div
                    key={`${b.pivot_beat_ord}-${i}`}
                    initial={initialOr({ opacity: 0, x: -8 })}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: delayOr(1.3 + cascadeDelay(i, 0.08)), ...itemTransition }}
                    style={ppStyles.branchCard}
                  >
                    <div style={ppStyles.branchTurnBadge}>
                      {t("play.ending_branch_turn", { turn: Math.floor(b.pivot_beat_ord / 2) })}
                    </div>
                    <div style={ppStyles.branchPaths}>
                      <div style={ppStyles.branchChosen}>
                        <span style={ppStyles.branchPathTag}>{t("play.ending_branch_chosen_tag")}</span>
                        <span style={ppStyles.branchPathText}>{b.chosen_path_summary}</span>
                      </div>
                      <div style={ppStyles.branchArrow}>{t("play.ending_branch_arrow")}</div>
                      <div style={ppStyles.branchAlternate}>
                        <span style={ppStyles.branchPathTag}>{t("play.ending_branch_alt_tag")}</span>
                        <span style={ppStyles.branchPathText}>{b.alternate_path_summary}</span>
                      </div>
                    </div>
                    <div style={ppStyles.branchOutcome}>
                      <span style={{ ...ppStyles.branchEndingChip, ...tierStyle }}>
                        {displayEndingLabel(b.alternate_ending_label, lang)}
                      </span>
                      <span style={ppStyles.branchRationale}>{b.rationale}</span>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </motion.section>
        ) : null}

        </div>
      </motion.div>
    </motion.section>
  )
}

function displayEndingLabel(label: string, lang: ReturnType<typeof useLanguage>["lang"]): string {
  const translated = ENDING_LABEL_DISPLAY[lang]?.[label]
  if (translated) return translated
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase())
}
