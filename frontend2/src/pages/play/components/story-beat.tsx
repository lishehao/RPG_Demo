import { type CSSProperties, type PointerEvent, useCallback, useEffect, useState } from "react"
import { motion, useReducedMotion } from "motion/react"
import type {
  NarrativeNPCPulse,
  NarrativePlayedLeverageCard,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { cleanNarrativeDisplayText } from "../../../shared/lib/narrative-display-text"
import { itemTransition, itemVariants, transitions } from "../../../shared/lib/motion-presets"
import { ppStyles } from "../play-styles"
import { useCompactLayout } from "../hooks/use-compact-layout"
import { parseOptionLabel } from "../play-option-label"

type SceneParallaxOffset = {
  x: number
  y: number
}

function SceneParallaxBanner({ sceneUrl, compact }: { sceneUrl: string; compact?: boolean }) {
  const reducedMotion = useReducedMotion()
  const [motionEnabled, setMotionEnabled] = useState(false)
  const [offset, setOffset] = useState<SceneParallaxOffset>({ x: 0, y: 0 })

  useEffect(() => {
    if (reducedMotion || typeof window === "undefined") {
      setMotionEnabled(false)
      setOffset({ x: 0, y: 0 })
      return
    }

    const media = window.matchMedia("(min-width: 721px) and (hover: hover) and (pointer: fine)")
    const sync = () => {
      setMotionEnabled(media.matches)
      if (!media.matches) setOffset({ x: 0, y: 0 })
    }
    sync()
    media.addEventListener("change", sync)
    return () => media.removeEventListener("change", sync)
  }, [reducedMotion])

  const handlePointerMove = useCallback((event: PointerEvent<HTMLDivElement>) => {
    if (!motionEnabled) return
    const rect = event.currentTarget.getBoundingClientRect()
    const x = ((event.clientX - rect.left) / rect.width - 0.5) * 2
    const y = ((event.clientY - rect.top) / rect.height - 0.5) * 2
    setOffset({
      x: Math.max(-1, Math.min(1, x)),
      y: Math.max(-1, Math.min(1, y)),
    })
  }, [motionEnabled])

  const resetOffset = useCallback(() => {
    setOffset({ x: 0, y: 0 })
  }, [])

  const transformTransition = motionEnabled
    ? "transform 210ms cubic-bezier(0.22, 0.61, 0.36, 1)"
    : "none"
  const planeTransform = motionEnabled
    ? `translate3d(${(offset.x * 6).toFixed(2)}px, ${(offset.y * 4).toFixed(2)}px, 0) scale(1.07) rotateX(${(-offset.y * 0.8).toFixed(2)}deg) rotateY(${(offset.x * 1.1).toFixed(2)}deg)`
    : "translate3d(0, 0, 0) scale(1.05)"
  const lightTransform = motionEnabled
    ? `translate3d(${(-offset.x * 3).toFixed(2)}px, ${(-offset.y * 2).toFixed(2)}px, 0) rotate(${(offset.x * 1.2).toFixed(2)}deg)`
    : "none"
  const vignetteTransform = motionEnabled
    ? `translate3d(${(-offset.x * 1.5).toFixed(2)}px, ${(-offset.y * 1).toFixed(2)}px, 0)`
    : "none"

  return (
    <motion.div
      initial={{ opacity: 0, scale: 1.015 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={transitions.slow}
      style={{
        ...ppStyles.beatSceneBanner,
        ...(compact ? ppStyles.beatSceneBannerCompact : null),
      }}
      onPointerMove={handlePointerMove}
      onPointerLeave={resetOffset}
      onPointerCancel={resetOffset}
      data-play-segment-parallax="true"
      data-play-segment-banner-density={compact ? "compact" : "full"}
      data-play-segment-motion={motionEnabled ? "pointer" : "static"}
      aria-hidden
    >
      <div
        style={{
          ...ppStyles.beatScenePlane,
          backgroundImage: `linear-gradient(180deg, rgba(12,12,16,0.03) 0%, rgba(12,12,16,0.20) 52%, rgba(12,12,16,0.62) 100%), url(${sceneUrl})`,
          transform: planeTransform,
          transition: transformTransition,
        }}
        data-play-segment-image="true"
      />
      <div
        style={{
          ...ppStyles.beatSceneLight,
          transform: lightTransform,
          transition: transformTransition,
        }}
      />
      <div
        style={{
          ...ppStyles.beatSceneVignette,
          transform: vignetteTransform,
          transition: transformTransition,
        }}
      />
      <div style={ppStyles.beatSceneGoldLine} />
    </motion.div>
  )
}
// ---------------------------------------------------------------------------
// Single story beat (narrator passage or player move)
// ---------------------------------------------------------------------------

export function StoryBeat({
  message,
  previousPlayerMessage,
  castNameById,
  intensity = "calm",
  sceneUrl,
  effectiveInventoryDelta,
  pickedHandle,
  pickedActionText,
  isLatestNarrator,
  hasFollowingPlayerEcho,
  suppressLatestFeedbackDigest,
  isBookmarked,
  onToggleBookmark,
}: {
  message: NarrativeStoryMessage
  previousPlayerMessage?: NarrativeStoryMessage
  castNameById?: Record<string, string>
  intensity?: "calm" | "rising" | "peak"
  sceneUrl?: string
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"]
  /** When this player message was an option pick, the option's
   *  readable label/tag. Used so players can remember exactly
   *  which action they committed. */
  pickedHandle?: string
  pickedActionText?: string
  isLatestNarrator?: boolean
  hasFollowingPlayerEcho?: boolean
  suppressLatestFeedbackDigest?: boolean
  /** True if the user has bookmarked this narrator beat. */
  isBookmarked?: boolean
  /** Click handler for the bookmark icon. Undefined hides the icon
   *  (e.g. for player messages or after the run is complete). */
  onToggleBookmark?: () => void
}) {
  const t = useT()
  if (message.role === "narrator") {
    const pulses = message.npc_pulse ?? []
    const impactPulses = pulses.filter((p) => p.shift !== "steady")
    const delta = effectiveInventoryDelta ?? message.inventory_delta
    const hasDelta = !!(delta && (delta.added.length > 0 || delta.removed.length > 0))
    const outcomeItems = buildOutcomeReceiptItems({
      pulses,
      impactPulses,
      delta,
      castNameById,
      t,
    })
    const intentRead = buildIntentReadReceipt({
      playerMessage: previousPlayerMessage,
      impactPulses,
      castNameById,
      t,
    })
    const playedLeverage = previousPlayerMessage?.played_leverage ?? null
    const hasBroken = impactPulses.some((p) => p.shift === "broken")
    const shouldOpenImpactEvidence = impactPulses.some((p) => p.shift === "broken")
    const shouldShowSceneBanner = !!sceneUrl && (intensity === "peak" || isLatestNarrator)
    const showDetailedOutcome =
      outcomeItems.length > 0 && (isLatestNarrator || hasBroken || intensity === "peak")
    const showDetailedImpactEvidence =
      impactPulses.length > 0 && isLatestNarrator && (shouldOpenImpactEvidence || intensity === "peak")
    const inlineImpactPulses = [...impactPulses]
      .sort((a, b) => outcomePriority(b.shift) - outcomePriority(a.shift))
      .slice(0, 3)
    const latestDigestPulses = [...impactPulses]
      .sort((a, b) => outcomePriority(b.shift) - outcomePriority(a.shift))
      .slice(0, 2)
    const latestOptionCount = message.options.length
    const isLatestActionableBeat =
      !!isLatestNarrator && latestOptionCount > 0 && !hasFollowingPlayerEcho
    const shouldCompactSceneBanner =
      isLatestActionableBeat && intensity !== "peak"
    const showLatestDigestInventory = hasDelta && latestDigestPulses.length === 0
    const showLatestBeatDigest =
      !suppressLatestFeedbackDigest &&
      !!isLatestNarrator &&
      !hasFollowingPlayerEcho &&
      (latestDigestPulses.length > 0 || hasDelta || latestOptionCount > 0)
    const latestDigestA11yItems = [
      ...latestDigestPulses.map((pulse) => {
        const name = (castNameById && castNameById[pulse.npc_id]) || pulse.npc_id
        return `${name} ${pulseDeltaLabel(pulse.shift, t)}`
      }),
      ...(showLatestDigestInventory
        ? [`${t("play.latest_beat_digest_hand")} ${t("play.latest_beat_digest_hand_changed")}`]
        : []),
      ...(latestOptionCount > 0
        ? [
            `${t("play.latest_beat_digest_next")} ${t("play.latest_beat_digest_options", {
              count: latestOptionCount,
            })}`,
          ]
        : []),
    ]
    const latestDigestA11yLabel = latestDigestA11yItems.length
      ? `${t("play.latest_beat_digest_label")}: ${latestDigestA11yItems.join("; ")}`
      : t("play.latest_beat_digest_label")
    const hasTensionShift = impactPulses.some(
      (p) => p.shift === "colder" || p.shift === "wary",
    )
    const beatSignal =
      intensity === "peak"
        ? {
            title: t("play.beat_signal_peak_title"),
            detail: hasBroken
              ? t("play.beat_signal_broken_detail")
              : hasDelta
                ? t("play.beat_signal_delta_detail")
                : hasTensionShift
                  ? t("play.beat_signal_tension_detail")
                  : t("play.beat_signal_peak_detail"),
            style: ppStyles.beatSignalPeak,
          }
        : intensity === "rising" && outcomeItems.length === 0
            ? {
                title: t("play.beat_signal_rising_title"),
                detail: t("play.beat_signal_rising_detail"),
                style: ppStyles.beatSignalRising,
              }
            : null
    // Visual tier: calm = default; rising = +size + decor line; peak =
    // larger type + bold left rail + scene banner overlay.
    const beatStyle =
      intensity === "peak"
        ? { ...ppStyles.narratorBeat, ...ppStyles.narratorBeatPeak }
        : intensity === "rising"
          ? { ...ppStyles.narratorBeat, ...ppStyles.narratorBeatRising }
          : ppStyles.narratorBeat
    const textStyle =
      intensity === "peak"
        ? { ...ppStyles.narratorText, ...ppStyles.narratorTextPeak }
        : intensity === "rising"
          ? { ...ppStyles.narratorText, ...ppStyles.narratorTextRising }
          : ppStyles.narratorText
    return (
      <motion.article
        layout
        initial="initial"
        animate="animate"
        variants={itemVariants}
        transition={itemTransition}
        style={{
          ...beatStyle,
          position: "relative",
          ...(isLatestActionableBeat ? ppStyles.narratorBeatActionable : null),
          ...(isBookmarked ? ppStyles.narratorBeatBookmarked : null),
        }}
        data-play-story-beat="true"
        data-play-story-beat-role="narrator"
        data-play-latest-narrator={isLatestNarrator ? "true" : undefined}
      >
        {/* Bookmark toggle — top-right of every narrator beat while
            the run is active. Lets the user mark "this is the
            moment I want to remember" so it shows up in the ending
            highlights with their own badge, alongside (or instead
            of) the LLM picks. */}
        {onToggleBookmark ? (
          <button
            type="button"
            onClick={onToggleBookmark}
            aria-label={isBookmarked ? t("play.bookmark_remove_title") : t("play.bookmark_add_title")}
            aria-pressed={!!isBookmarked}
            style={{
              ...ppStyles.beatBookmarkBtn,
              ...(isBookmarked ? ppStyles.beatBookmarkBtnActive : null),
            }}
            title={isBookmarked ? t("play.bookmark_remove_title") : t("play.bookmark_add_title")}
          >
            {isBookmarked ? "★" : "☆"}
          </button>
        ) : null}
        {shouldShowSceneBanner ? (
          <SceneParallaxBanner sceneUrl={sceneUrl} compact={shouldCompactSceneBanner} />
        ) : null}
        {intensity === "rising" || intensity === "peak" ? (
          <div
            style={
              intensity === "peak" ? ppStyles.beatDecorPeak : ppStyles.beatDecorRising
            }
            aria-hidden
          />
        ) : null}
        {beatSignal ? (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08, ...itemTransition }}
            style={{ ...ppStyles.beatSignal, ...beatSignal.style }}
          >
            <span style={ppStyles.beatSignalMark} aria-hidden />
            <span style={ppStyles.beatSignalCopy}>
              <strong style={ppStyles.beatSignalTitle}>{beatSignal.title}</strong>
              <span style={ppStyles.beatSignalDetail}>{beatSignal.detail}</span>
            </span>
          </motion.div>
        ) : null}
        <div style={textStyle}>{cleanNarrativeDisplayText(message.content)}</div>
        {showLatestBeatDigest ? (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08, ...itemTransition }}
            style={{
              ...ppStyles.latestBeatDigest,
              ...(isLatestActionableBeat ? ppStyles.latestBeatDigestActionable : null),
            }}
            aria-label={latestDigestA11yLabel}
            data-play-latest-beat-digest="true"
          >
            <span style={ppStyles.latestBeatDigestLabel}>
              {t("play.latest_beat_digest_label")}
            </span>
            <span
              style={ppStyles.latestBeatDigestHint}
              data-play-latest-beat-digest-hint="true"
            >
              {t("play.latest_beat_digest_hint")}
            </span>
            <span style={ppStyles.latestBeatDigestItems}>
              {latestDigestPulses.map((pulse) => {
                const name = (castNameById && castNameById[pulse.npc_id]) || pulse.npc_id
                return (
                  <span
                    key={`${pulse.npc_id}:${pulse.shift}:latest-digest`}
                    style={ppStyles.latestBeatDigestItem}
                    data-play-latest-beat-digest-pulse={pulse.npc_id}
                  >
                    <span style={ppStyles.latestBeatDigestName}>{name}</span>
                    <strong style={ppStyles.latestBeatDigestValue}>
                      {pulseDeltaLabel(pulse.shift, t)}
                    </strong>
                  </span>
                )
              })}
              {showLatestDigestInventory ? (
                <span
                  style={ppStyles.latestBeatDigestItem}
                  data-play-latest-beat-digest-inventory="true"
                >
                  <span style={ppStyles.latestBeatDigestName}>{t("play.latest_beat_digest_hand")}</span>
                  <strong style={ppStyles.latestBeatDigestValue}>
                    {t("play.latest_beat_digest_hand_changed")}
                  </strong>
                </span>
              ) : null}
              {latestOptionCount > 0 ? (
                <span
                  style={ppStyles.latestBeatDigestItem}
                  data-play-latest-beat-digest-options="true"
                >
                  <span style={ppStyles.latestBeatDigestName}>{t("play.latest_beat_digest_next")}</span>
                  <strong style={ppStyles.latestBeatDigestValue}>
                    {t("play.latest_beat_digest_options", { count: latestOptionCount })}
                  </strong>
                </span>
              ) : null}
            </span>
          </motion.div>
        ) : null}
        {isBookmarked ? (
          <motion.div
            initial={{ opacity: 0, y: -3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05, ...itemTransition }}
            style={ppStyles.beatBookmarkInline}
          >
            <span style={ppStyles.beatBookmarkInlineMark}>★</span>
            <span>{t("play.bookmark_user_mark_label")}</span>
          </motion.div>
        ) : null}
        {playedLeverage ? (
          <LeveragePayoff
            played={playedLeverage}
            impactPulses={impactPulses}
            castNameById={castNameById}
          />
        ) : null}
        {outcomeItems.length > 0 && !suppressLatestFeedbackDigest ? (
          <OutcomeReceipt
            items={outcomeItems}
            compact={!showDetailedOutcome || showDetailedImpactEvidence}
          />
        ) : null}
        {intentRead ? <IntentReadReceipt read={intentRead} /> : null}
        {message.chosen_option_index != null && message.options.length > 0 && !hasFollowingPlayerEcho ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.12, ...itemTransition }}
            style={ppStyles.chosenChip}
          >
            <span style={ppStyles.chosenLabel}>{t("play.beat_chosen_label")}</span>
            <span style={ppStyles.chosenText}>
              {message.options[message.chosen_option_index]?.label ?? "?"}
            </span>
          </motion.div>
        ) : null}
        {showDetailedImpactEvidence ? (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.18, ...itemTransition }}
            style={ppStyles.pulseImpactPanel}
            aria-label={t("play.impact_feed_label")}
          >
            <div style={ppStyles.pulseImpactSummary}>
              <span style={ppStyles.pulseImpactSummaryCopy}>
                <span style={ppStyles.pulseImpactTitle}>{t("play.impact_inline_label")}</span>
                <span style={ppStyles.pulseImpactCount}>
                  {t("play.impact_count", { count: impactPulses.length })}
                </span>
              </span>
            </div>
            <div style={ppStyles.pulseImpactGrid}>
              {impactPulses.slice(0, 3).map((p, idx) => {
                const name = (castNameById && castNameById[p.npc_id]) || p.npc_id
                const shiftStyle =
                  ppStyles[
                    ("pulseShift_" + p.shift) as keyof typeof ppStyles
                  ] as CSSProperties | undefined
                return (
                  <motion.div
                    key={`${p.npc_id}-impact-${idx}`}
                    style={{ ...ppStyles.pulseImpactCard, ...(shiftStyle ?? {}) }}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{
                      opacity: 1,
                      y: 0,
                    }}
                    transition={{
                      delay: 0.22 + idx * 0.06,
                      ...itemTransition,
                    }}
                  >
                    <span style={ppStyles.pulseImpactMark}>
                      <span style={ppStyles.pulseImpactArrow}>{shiftArrow(p.shift)}</span>
                      <motion.span
                        style={ppStyles.pulseImpactDelta}
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.28 + idx * 0.06, ...itemTransition }}
                      >
                        {pulseDeltaLabel(p.shift, t)}
                      </motion.span>
                    </span>
                    <span style={ppStyles.pulseImpactBody}>
                      <strong style={ppStyles.pulseImpactName}>{name}</strong>
                      <span style={ppStyles.pulseImpactShift}>{pulseImpactLabel(p.shift, t)}</span>
                    </span>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>
        ) : impactPulses.length > 0 && outcomeItems.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16, ...itemTransition }}
            style={ppStyles.pulseImpactInline}
          >
            <span style={ppStyles.pulseImpactInlineLabel}>{t("play.impact_inline_label")}</span>
            <span style={ppStyles.pulseImpactInlineItems}>
              {inlineImpactPulses.map((p) => {
                const name = (castNameById && castNameById[p.npc_id]) || p.npc_id
                return (
                  <span key={`${p.npc_id}-impact-inline-${p.shift}`} style={ppStyles.pulseImpactInlineItem}>
                    <span style={ppStyles.pulseImpactInlineName}>{name}</span>
                    <strong style={ppStyles.pulseImpactInlineDelta}>{pulseDeltaLabel(p.shift, t)}</strong>
                  </span>
                )
              })}
            </span>
          </motion.div>
        ) : null}
      </motion.article>
    )
  }
  // player move (echoed action)
  const played = message.played_leverage
  const playedTarget = played ? (castNameById?.[played.npc_id] ?? played.npc_id) : ""
  const parsedPlayerMove = parseOptionLabel(message.content)
  const playerMoveBody = pickedActionText ?? (parsedPlayerMove.body || message.content)
  const playerMoveHandle = pickedHandle ?? parsedPlayerMove.tag
  return (
    <motion.article
      layout
      initial="initial"
      animate="animate"
      variants={itemVariants}
      transition={itemTransition}
      style={{
        ...ppStyles.playerBeat,
        ...(played ? ppStyles.playerBeatLeverageMove : null),
      }}
      data-play-story-beat="true"
      data-play-story-beat-role="player"
    >
      <div style={ppStyles.playerLabel}>
        {t("play.beat_player_label")}
        {playerMoveHandle ? (
          <>
            <span style={ppStyles.playerLabelSeparator}>{" · "}</span>
            <span style={ppStyles.playerHandleText} title={message.content}>
              {playerMoveHandle}
            </span>
          </>
        ) : null}
      </div>
      <div style={ppStyles.playerText}>{playerMoveBody}</div>
      {played || message.diary ? (
        <div style={ppStyles.playerMetaLine}>
          {played ? (
            <span style={ppStyles.playerMetaItem}>
              <span style={ppStyles.playerLeverageTag}>
                {t("play.beat_leverage_tag", { target: playedTarget })}
              </span>
              <span style={ppStyles.playerLeverageText}>{played.leverage}</span>
            </span>
          ) : null}
          {message.diary ? (
            <span style={ppStyles.playerMetaItem}>
              <span style={ppStyles.playerDiaryTag}>{t("play.beat_diary_tag")}</span>
              <span style={ppStyles.playerDiaryText}>{message.diary}</span>
            </span>
          ) : null}
        </div>
      ) : null}
    </motion.article>
  )
}
// Mirror of backend _stage_for. Used to drive visual intensity and to
// map a narrator beat back to a segment scene asset.
function stageForLocal(turnIndex: number, turnBudget: number): string {
  if (turnIndex <= 1) return "hook"
  const midpoint = turnBudget / 2
  if (turnIndex < midpoint - 0.5) return "pressure"
  if (turnIndex < midpoint + 0.5) return "reversal"
  if (turnIndex < turnBudget - 1) return "climax"
  if (turnIndex < turnBudget) return "pre_finale"
  return "pre_finale_open"
}

// Visual intensity heuristic — purely client-side from data we already
// have. Peak: any pulse broken, OR inventory delta fired, OR (climax/
// pre_finale stage AND any colder/wary). Rising: reversal/climax stages
// without peak signal. Calm: hook + early pressure.
export function computeBeatIntensity(
  message: NarrativeStoryMessage,
  turnBudget: number,
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"],
): "calm" | "rising" | "peak" {
  if (message.role !== "narrator") return "calm"
  const turnIndex = Math.floor(message.ord / 2)
  // Opening (ord=0) is always calm — sets the scene, no visual punch yet.
  if (turnIndex === 0) return "calm"
  const stage = stageForLocal(turnIndex, turnBudget)
  const pulses = message.npc_pulse ?? []
  const hasBroken = pulses.some((p) => p.shift === "broken")
  const hasColderOrWary = pulses.some(
    (p) => p.shift === "colder" || p.shift === "wary",
  )
  const delta = effectiveInventoryDelta ?? message.inventory_delta
  const hasDelta = !!(
    delta && (delta.added.length > 0 || delta.removed.length > 0)
  )
  if (hasBroken) return "peak"
  if (hasDelta) return "peak"
  if ((stage === "climax" || stage === "pre_finale" || stage === "pre_finale_open") && hasColderOrWary) {
    return "peak"
  }
  if (stage === "reversal" || stage === "climax" || stage === "pre_finale" || stage === "pre_finale_open") {
    return "rising"
  }
  return "calm"
}
function shiftArrow(shift: NarrativeNPCPulse["shift"]): string {
  switch (shift) {
    case "warmer": return "↗"
    case "colder": return "↘"
    case "wary":   return "⚠"
    case "broken": return "✕"
    case "steady":
    default:       return "—"
  }
}

function pulseImpactLabel(
  shift: NarrativeNPCPulse["shift"],
  t: ReturnType<typeof useT>,
): string {
  switch (shift) {
    case "warmer":
      return t("play.impact_warmer")
    case "colder":
      return t("play.impact_colder")
    case "wary":
      return t("play.impact_wary")
    case "broken":
      return t("play.impact_broken")
    case "steady":
    default:
      return t("play.impact_steady")
  }
}

function pulseDeltaLabel(
  shift: NarrativeNPCPulse["shift"],
  t: ReturnType<typeof useT>,
): string {
  switch (shift) {
    case "warmer":
      return t("play.delta_trust_up")
    case "colder":
      return t("play.delta_trust_down")
    case "wary":
      return t("play.delta_suspicion_up")
    case "broken":
      return t("play.delta_bond_broken")
    case "steady":
    default:
      return t("play.delta_no_shift")
  }
}

function pulseNextMoveLabel(
  shift: NarrativeNPCPulse["shift"],
  t: ReturnType<typeof useT>,
): string {
  switch (shift) {
    case "warmer":
      return t("play.impact_feed_next_warmer")
    case "colder":
      return t("play.impact_feed_next_colder")
    case "wary":
      return t("play.impact_feed_next_wary")
    case "broken":
      return t("play.impact_feed_next_broken")
    case "steady":
    default:
      return t("play.impact_feed_next_steady")
  }
}

function outcomeToneForShift(shift: NarrativeNPCPulse["shift"]): OutcomeReceiptTone {
  switch (shift) {
    case "warmer":
      return "safe"
    case "colder":
      return "neutral"
    case "wary":
      return "tense"
    case "broken":
      return "danger"
    case "steady":
    default:
      return "neutral"
  }
}

function outcomePriority(shift: NarrativeNPCPulse["shift"]): number {
  switch (shift) {
    case "broken":
      return 5
    case "wary":
      return 4
    case "colder":
      return 3
    case "warmer":
      return 2
    case "steady":
    default:
      return 1
  }
}

function inventoryOutcomeValue({
  delta,
  t,
}: {
  delta: NonNullable<NarrativeStoryMessage["inventory_delta"]>
  t: ReturnType<typeof useT>
}): string {
  const added = delta.added
  const removed = delta.removed
  if (added.length === 1 && removed.length === 0) {
    return t("play.outcome_inventory_gain_item", { item: added[0] ?? "" })
  }
  if (removed.length === 1 && added.length === 0) {
    return t("play.outcome_inventory_loss_item", { item: removed[0] ?? "" })
  }
  if (added.length > 0 && removed.length > 0) {
    return t("play.outcome_inventory_mixed", {
      added: added.length,
      removed: removed.length,
    })
  }
  if (added.length > 0) return t("play.outcome_inventory_gain", { count: added.length })
  return t("play.outcome_inventory_loss", { count: removed.length })
}

type IntentReadReceiptView = {
  publicMove: string
  privateIntent: string
  reaction: string
}

function truncateIntentSnippet(value: string, max = 118): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function buildIntentReadReceipt({
  playerMessage,
  impactPulses,
  castNameById,
  t,
}: {
  playerMessage?: NarrativeStoryMessage
  impactPulses: NarrativeNPCPulse[]
  castNameById?: Record<string, string>
  t: ReturnType<typeof useT>
}): IntentReadReceiptView | null {
  const privateIntent = playerMessage?.diary?.trim()
  if (!playerMessage || !privateIntent) return null

  const focusPulse = [...impactPulses].sort(
    (a, b) => outcomePriority(b.shift) - outcomePriority(a.shift),
  )[0]
  const reaction = focusPulse
    ? t("play.intent_read_reaction_target", {
        target: castNameById?.[focusPulse.npc_id] ?? focusPulse.npc_id,
        shift: pulseImpactLabel(focusPulse.shift, t),
      })
    : t("play.intent_read_reaction_room")

  return {
    publicMove: truncateIntentSnippet(playerMessage.content),
    privateIntent: truncateIntentSnippet(privateIntent),
    reaction,
  }
}

function buildOutcomeReceiptItems({
  pulses,
  impactPulses,
  delta,
  castNameById,
  t,
}: {
  pulses: NarrativeNPCPulse[]
  impactPulses: NarrativeNPCPulse[]
  delta: NarrativeStoryMessage["inventory_delta"]
  castNameById?: Record<string, string>
  t: ReturnType<typeof useT>
}): OutcomeReceiptItem[] {
  const items: OutcomeReceiptItem[] = []
  const focusPulse = [...impactPulses].sort(
    (a, b) => outcomePriority(b.shift) - outcomePriority(a.shift),
  )[0]

  if (focusPulse) {
    const name = castNameById?.[focusPulse.npc_id] ?? focusPulse.npc_id
    items.push({
      label: t("play.outcome_focus_label"),
      value: `${name} · ${pulseDeltaLabel(focusPulse.shift, t)}`,
      tone: outcomeToneForShift(focusPulse.shift),
    })
  }

  if (impactPulses.length > 1) {
    const hasDanger = impactPulses.some((pulse) => pulse.shift === "broken")
    const hasTense = impactPulses.some(
      (pulse) => pulse.shift === "wary" || pulse.shift === "colder",
    )
    items.push({
      label: t("play.outcome_npc_label"),
      value: t("play.outcome_npc_value", { count: impactPulses.length }),
      tone: hasDanger ? "danger" : hasTense ? "tense" : "safe",
    })
  }

  const added = delta?.added.length ?? 0
  const removed = delta?.removed.length ?? 0
  if (delta && (added > 0 || removed > 0)) {
    items.push({
      label: t("play.outcome_inventory_label"),
      value: inventoryOutcomeValue({ delta, t }),
      tone: removed > 0 && added === 0 ? "tense" : "gold",
    })
  }

  const hasBroken = impactPulses.some((pulse) => pulse.shift === "broken")
  const hasRisingHeat = impactPulses.some(
    (pulse) => pulse.shift === "wary" || pulse.shift === "colder",
  )
  const hasSoftened = impactPulses.some((pulse) => pulse.shift === "warmer")
  if (hasBroken || hasRisingHeat || hasSoftened) {
    items.push({
      label: t("play.outcome_heat_label"),
      value: hasBroken
        ? t("play.outcome_heat_critical")
        : hasRisingHeat
          ? t("play.outcome_heat_rising")
          : t("play.outcome_heat_softened"),
      tone: hasBroken ? "danger" : hasRisingHeat ? "tense" : "safe",
    })
  }

  if (items.length === 0 && pulses.length > 0) {
    items.push({
      label: t("play.outcome_room_label"),
      value: t("play.outcome_room_steady"),
      tone: "neutral",
    })
  }

  return items.slice(0, 3)
}

function IntentReadReceipt({ read }: { read: IntentReadReceiptView }) {
  const t = useT()
  const lanes = [
    {
      id: "public",
      label: t("play.intent_read_public_label"),
      value: read.publicMove,
    },
    {
      id: "private",
      label: t("play.intent_read_private_label"),
      value: read.privateIntent,
    },
    {
      id: "reaction",
      label: t("play.intent_read_reaction_label"),
      value: read.reaction,
    },
  ].filter((lane) => lane.value)
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.14, ...itemTransition }}
      style={ppStyles.intentReadReceipt}
      aria-label={t("play.intent_read_label")}
      data-play-intent-read-receipt="true"
    >
      <span style={ppStyles.intentReadKicker}>{t("play.intent_read_label")}</span>
      <span style={ppStyles.intentReadSentence}>
        {lanes.map((lane, index) => (
          <span
            key={lane.id}
            style={ppStyles.intentReadPhrase}
            data-play-intent-read-lane={lane.id}
          >
            {index > 0 ? <span style={ppStyles.intentReadDivider} aria-hidden>·</span> : null}
            <span style={ppStyles.intentReadLaneLabel}>{lane.label}:</span>
            {" "}
            <strong style={ppStyles.intentReadLaneValue}>{lane.value}</strong>
          </span>
        ))}
      </span>
    </motion.div>
  )
}

function outcomeReceiptToneStyle(tone?: OutcomeReceiptTone): CSSProperties | null {
  switch (tone) {
    case "safe":
      return ppStyles.outcomeReceiptChipSafe
    case "tense":
      return ppStyles.outcomeReceiptChipTense
    case "danger":
      return ppStyles.outcomeReceiptChipDanger
    case "gold":
      return ppStyles.outcomeReceiptChipGold
    case "neutral":
    default:
      return null
  }
}

function OutcomeReceipt({ items, compact = false }: { items: OutcomeReceiptItem[]; compact?: boolean }) {
  const t = useT()
  const compactLayout = useCompactLayout("(max-width: 520px)")
  if (items.length === 0) return null
  const rootStyle = compact
    ? {
        ...ppStyles.outcomeReceiptInline,
        ...(compactLayout ? ppStyles.outcomeReceiptInlineMobile : null),
      }
    : {
        ...ppStyles.outcomeReceipt,
        ...(compactLayout ? ppStyles.outcomeReceiptMobile : null),
      }
  const sentenceStyle = {
    ...ppStyles.outcomeReceiptSentence,
    ...(compact ? ppStyles.outcomeReceiptSentenceCompact : null),
    ...(compactLayout ? ppStyles.outcomeReceiptSentenceMobile : null),
  }
  const phraseStyle = {
    ...ppStyles.outcomeReceiptPhrase,
    ...(compactLayout ? ppStyles.outcomeReceiptPhraseMobile : null),
  }
  const valueStyleBase = {
    ...ppStyles.outcomeReceiptValue,
    ...(compactLayout ? ppStyles.outcomeReceiptValueMobile : null),
  }
  const outcomeReceiptA11yItems = items.map((item) => `${item.label} ${item.value}`)
  const outcomeReceiptA11yLabel = outcomeReceiptA11yItems.length
    ? `${compact ? t("play.outcome_inline_label") : t("play.outcome_label")}: ${outcomeReceiptA11yItems.join("; ")}`
    : compact ? t("play.outcome_inline_label") : t("play.outcome_label")
  const content = (
    <>
      <span style={compact ? ppStyles.outcomeReceiptInlineLabel : ppStyles.outcomeReceiptHeader}>
        <span style={compact ? undefined : ppStyles.outcomeReceiptKicker}>
          {compact ? t("play.outcome_inline_label") : t("play.outcome_kicker")}
        </span>
        {compact ? null : (
          <span style={ppStyles.outcomeReceiptHint}>{t("play.outcome_next_hint")}</span>
        )}
      </span>
      <span style={sentenceStyle}>
        {items.map((item) => (
          <span
            key={`${item.label}:${item.value}`}
            style={phraseStyle}
            title={`${item.label}: ${item.value}`}
            data-play-outcome-receipt-item="true"
            data-play-outcome-receipt-tone={item.tone ?? "neutral"}
          >
            <span style={ppStyles.outcomeReceiptItemLabel}>{item.label}:</span>
            <strong
              style={{
                ...valueStyleBase,
                ...(outcomeReceiptToneStyle(item.tone) ?? {}),
              }}
            >
              {item.value}
            </strong>
          </span>
        ))}
      </span>
    </>
  )
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.1, ...itemTransition }}
      style={rootStyle}
      aria-label={outcomeReceiptA11yLabel}
      data-play-outcome-receipt="true"
      data-play-outcome-receipt-mode={compact ? "compact" : "summary"}
    >
      {content}
    </motion.div>
  )
}

function LeveragePayoff({
  played,
  impactPulses,
  castNameById,
}: {
  played: NarrativePlayedLeverageCard
  impactPulses: NarrativeNPCPulse[]
  castNameById?: Record<string, string>
}) {
  const t = useT()
  const target = castNameById?.[played.npc_id] ?? played.npc_id
  const targetPulse =
    impactPulses.find((pulse) => pulse.npc_id === played.npc_id) ??
    [...impactPulses].sort((a, b) => outcomePriority(b.shift) - outcomePriority(a.shift))[0] ??
    null
  const payoffTone =
    targetPulse
      ? (ppStyles[
          ("leveragePayoff_" + targetPulse.shift) as keyof typeof ppStyles
        ] as CSSProperties | undefined)
      : undefined
  const readout = targetPulse
    ? pulseImpactLabel(targetPulse.shift, t)
    : t("play.leverage_payoff_room_reacts")
  const reason = targetPulse?.reason || t("play.leverage_payoff_reason_default")
  const next = targetPulse
    ? pulseNextMoveLabel(targetPulse.shift, t)
    : t("play.leverage_payoff_next_default")

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.08, ...transitions.snap }}
      style={{ ...ppStyles.leveragePayoff, ...(payoffTone ?? {}) }}
      aria-label={t("play.leverage_payoff_label")}
    >
      <span style={ppStyles.leveragePayoffKicker}>{t("play.leverage_payoff_kicker")}</span>
      <span style={ppStyles.leveragePayoffSentence}>
        <strong style={ppStyles.leveragePayoffEvidence}>{played.leverage}</strong>
        <span style={ppStyles.leveragePayoffMetaDivider} aria-hidden>·</span>
        <strong style={ppStyles.leveragePayoffMetaValue}>{target}</strong>
        <span style={ppStyles.leveragePayoffMetaDivider} aria-hidden>·</span>
        <span style={ppStyles.leveragePayoffMetaValue}>{readout}</span>
        <span style={ppStyles.leveragePayoffMetaDivider} aria-hidden>·</span>
        <span style={ppStyles.leveragePayoffMetaValue}>{next}</span>
      </span>
      <span style={ppStyles.leveragePayoffReasonText}>{reason}</span>
    </motion.div>
  )
}

type OutcomeReceiptTone = "safe" | "neutral" | "tense" | "danger" | "gold"

type OutcomeReceiptItem = {
  label: string
  value: string
  tone?: OutcomeReceiptTone
}
