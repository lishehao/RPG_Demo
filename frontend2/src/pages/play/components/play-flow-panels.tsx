import { type CSSProperties, type PointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import type {
  NarrativeNPCPulse,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import { Truncated } from "../../../shared/ui/truncated"
import { useT } from "../../../shared/lib/i18n"
import {
  itemTransition,
  transitions,
} from "../../../shared/lib/motion-presets"
import { actionPalette, ppStyles } from "../play-styles"
import type { GameplayActionForecast } from "../play-gameplay-envelope"
import type { ActionCommitmentSummary, LeverageCardView } from "../play-types"
import { useCompactLayout } from "../hooks/use-compact-layout"
import { parseOptionLabel } from "../play-option-label"
import { ActionCollapsedForecast, ActionSelectedOptionDetail } from "./action-option-card"
import { FreeActionContextBanner, FreeActionStarterRows, buildFreeActionStarterMoves } from "./free-action-prompts"
import { LeverageEmptySummary, LeverageSummaryButton } from "./leverage-summary"
import { RunContextObjective } from "./run-context-objective"
import { RunContextProgressMeter } from "./run-context-progress"
import { stageDisplayName } from "./run-context-stage-label"
import { SceneReadStrip, buildSceneClocks } from "./scene-read-strip"
import { SelectedMoveConfirmationReadout } from "./selected-move-confirmation"

const ACTION_LEVERAGE_RAIL_ID = "play-leverage-rail"

type ResolvingCommitmentSignal = {
  id: string
  label: string
  tone: GameplayActionForecast["tone"]
  title?: string
}

function resolvingSignalToneStyle(tone: GameplayActionForecast["tone"]): CSSProperties {
  if (tone === "cost") return ppStyles.gameplayDecisionGroupCost
  if (tone === "gain" || tone === "unlock") return ppStyles.gameplayDecisionGroupUpside
  return ppStyles.gameplayDecisionGroupShift
}


function fitTextareaToContent(node: HTMLTextAreaElement | null) {
  if (!node) return
  node.style.height = "auto"
  node.style.height = `${node.scrollHeight}px`
}

function truncateRecoveryText(value: string, max = 64): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function joinReadableLabelParts(parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => part?.replace(/\s+/g, " ").trim().replace(/[.!?。！？]+$/, "") ?? "")
    .filter(Boolean)
    .join(". ")
}

export function RunContextPanel({
  story,
  turnsCompleted,
  turnBudget,
  turnsRemaining,
  liveInventory,
  leverageCards,
  isComplete,
  onUseInventoryItem,
}: {
  story: NarrativeStoryHistoryResponse
  turnsCompleted: number
  turnBudget: number
  turnsRemaining: number
  liveInventory: string[]
  leverageCards: LeverageCardView[]
  isComplete: boolean
  onUseInventoryItem?: (item: string) => void
}) {
  const t = useT()
  const compactRunContext = useCompactLayout("(max-width: 680px)")
  const role = story.session.player_role
  const upcomingTurn = Math.min(turnBudget - 1, turnsCompleted + 1)
  const stageKey = stageForLocal(upcomingTurn, turnBudget)
  const stageLabelKey = `stage_bar.${stageKey === "pre_finale_open" ? "pre_finale" : stageKey}` as Parameters<typeof t>[0]
  const stage = t(stageLabelKey, stageDisplayName(stageKey))
  const availableLeverageCards = leverageCards.filter((card) => !card.used)
  const trumpResourceText =
    availableLeverageCards.length === 1
      ? t("play.status_trump_one")
      : availableLeverageCards.length > 1
        ? t("play.status_trump_many", { count: availableLeverageCards.length })
        : leverageCards.length > 0
          ? t("play.status_trump_empty")
          : ""
  const itemResourceText =
    liveInventory.length === 1
      ? t("play.status_item_one")
      : liveInventory.length > 1
        ? t("play.status_item_many", { count: liveInventory.length })
        : ""
  const privateResourceParts = [trumpResourceText, itemResourceText].filter(Boolean)
  const privateResourceText = role ? privateResourceParts.join(" · ") : ""
  const runStatusText = isComplete
    ? t("play.status_done")
    : t("play.status_turns_left", { count: turnsRemaining })
  const runMetaText = [stage, runStatusText, privateResourceText].filter(Boolean).join(" · ")
  const visibleInventory = liveInventory.slice(0, 3)
  const hiddenInventoryCount = Math.max(0, liveInventory.length - visibleInventory.length)
  const renderInventoryLine = () =>
    visibleInventory.length > 0 ? (
      <div style={ppStyles.runInventoryLine}>
        <span style={ppStyles.runInventoryKicker}>{t("play.run_assets_label")}</span>
        <span style={ppStyles.runInventoryItems}>
          {visibleInventory.map((item, index) => (
            <span key={`${item}-${index}`} style={ppStyles.runInventoryItem}>
              {index > 0 ? <span style={ppStyles.runInventoryDivider}>·</span> : null}
              {onUseInventoryItem ? (
                <button
                  type="button"
                  style={ppStyles.runInventoryItemButton}
                  onClick={() => onUseInventoryItem(item)}
                  data-play-run-inventory-use="true"
                  data-play-run-inventory-item={item}
                  aria-label={t("play.run_assets_use_title", { item })}
                  title={t("play.run_assets_use_title", { item })}
                >
                  {item}
                </button>
              ) : (
                <span>{item}</span>
              )}
            </span>
          ))}
          {hiddenInventoryCount > 0 ? (
            <span style={ppStyles.runInventoryMore}>
              {t("play.run_assets_more", { count: hiddenInventoryCount })}
            </span>
          ) : null}
        </span>
        <span style={ppStyles.runInventoryHint}>
          {t("play.run_assets_hint")}
        </span>
      </div>
    ) : null

  if (compactRunContext) {
    return (
      <motion.section
        style={{ ...ppStyles.runContextPanel, ...ppStyles.runContextPanelCompact }}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={itemTransition}
        aria-label={t("play.run_context_label")}
        data-play-run-context="true"
      >
        <div style={ppStyles.runCompactHeader}>
          <span style={ppStyles.runCompactRoleTag}>{t("play.run_identity_prefix")}</span>
          <Truncated style={ppStyles.runCompactRoleTitle}>
            {role?.label ?? story.template.title}
          </Truncated>
          <span style={ppStyles.runCompactMeta}>{runMetaText}</span>
        </div>
        {role ? <RunContextObjective role={role} compact /> : null}
        {renderInventoryLine()}
        <RunContextProgressMeter
          isComplete={isComplete}
          turnsCompleted={turnsCompleted}
          turnBudget={turnBudget}
          stage={stage}
        />
      </motion.section>
    )
  }

  return (
    <motion.section
      style={{
        ...ppStyles.runContextPanel,
        ...(compactRunContext ? ppStyles.runContextPanelCompact : null),
      }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={itemTransition}
      aria-label={t("play.run_context_label")}
      data-play-run-context="true"
    >
      <div style={ppStyles.runContextHeader}>
        <span style={ppStyles.runKicker}>{t("play.run_identity_prefix")}</span>
        <Truncated style={ppStyles.runRoleTitle}>
          {role?.label ?? story.template.title}
        </Truncated>
        <span style={ppStyles.runContextMeta}>{runMetaText}</span>
      </div>
      {role ? <RunContextObjective role={role} /> : null}
      {renderInventoryLine()}
      <RunContextProgressMeter
        isComplete={isComplete}
        turnsCompleted={turnsCompleted}
        turnBudget={turnBudget}
        stage={stage}
      />
    </motion.section>
  )
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

export function Header({
  onBackHome,
  title,
  cast,
  turnCount,
  turnBudget,
  coverUrl,
}: {
  onBackHome: () => void
  title: string
  cast?: string[]
  turnCount?: number
  turnBudget?: number
  coverUrl?: string
}) {
  const t = useT()
  const compactHeader = useCompactLayout()
  const showCoverHeader = Boolean(coverUrl && !compactHeader)
  const headerStyle: CSSProperties = showCoverHeader
    ? {
        ...ppStyles.header,
        ...ppStyles.headerWithCover,
        backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.55) 0%, rgba(20,16,12,0.92) 100%), url(${coverUrl})`,
      }
    : compactHeader
      ? { ...ppStyles.header, ...ppStyles.headerCompact }
    : ppStyles.header

  const showProgress = typeof turnCount === "number" && typeof turnBudget === "number"
  const pct = showProgress ? Math.min(100, (turnCount! / turnBudget!) * 100) : 0
  const headerMeta = showProgress
    ? t("play.header_turn_count", { current: turnCount!, total: turnBudget! })
    : cast && cast.length
      ? cast.slice(0, 3).join(" · ")
      : ""

  return (
    <header style={headerStyle}>
      <div style={{ ...ppStyles.headerRow, ...(compactHeader ? ppStyles.headerRowCompact : null) }}>
        <button
          style={
            showCoverHeader
              ? { ...ppStyles.backBtn, ...ppStyles.backBtnOnCover }
              : { ...ppStyles.backBtn, ...(compactHeader ? ppStyles.backBtnCompact : null) }
          }
          onClick={onBackHome}
          type="button"
        >
          {compactHeader ? t("play.back_home_short") : t("play.back_home")}
        </button>
        <div style={ppStyles.headerTitle}>
          <Truncated
            style={
              showCoverHeader
                ? { ...ppStyles.headerTitleLine, color: "white" }
                : { ...ppStyles.headerTitleLine, ...(compactHeader ? ppStyles.headerTitleLineCompact : null) }
            }
          >
            {title}
          </Truncated>
          {!compactHeader && headerMeta ? (
            <div
              style={
                showCoverHeader
                  ? { ...ppStyles.headerCast, color: "rgba(255,255,255,0.78)" }
                  : ppStyles.headerCast
              }
              title={headerMeta}
            >
              {headerMeta}
            </div>
          ) : null}
        </div>
        {compactHeader && showProgress ? (
          <span style={ppStyles.headerTurnsCompact}>
            {t("play.header_turn_count_short", { current: turnCount!, total: turnBudget! })}
          </span>
        ) : (
          <span style={ppStyles.headerSpacer} />
        )}
      </div>
      {showProgress ? (
        <div style={ppStyles.progressTrack}>
          <div
            style={{
              ...ppStyles.progressFill,
              width: `${pct}%`,
            }}
          />
        </div>
      ) : null}
    </header>
  )
}


type EffectiveInventoryDelta = NonNullable<NarrativeStoryMessage["inventory_delta"]>

function computeInventoryProgress(
  startingAssets: string[],
  messages: NarrativeStoryMessage[],
): { inventory: string[]; effectiveDeltasByOrd: Map<number, EffectiveInventoryDelta> } {
  const normalizeInventoryItem = (item: string) => item.replace(/\s+/g, " ").trim().toLowerCase()
  const inv: string[] = []
  const addInventoryItem = (item: string): string | null => {
    const clean = item.replace(/\s+/g, " ").trim()
    if (!clean) return null
    const key = normalizeInventoryItem(clean)
    if (inv.some((existing) => normalizeInventoryItem(existing) === key)) return null
    inv.push(clean)
    return clean
  }
  const removeInventoryItem = (item: string): string | null => {
    const target = normalizeInventoryItem(item)
    for (let i = 0; i < inv.length; i += 1) {
      const current = normalizeInventoryItem(inv[i] ?? "")
      if (current && (current.includes(target) || target.includes(current))) {
        const [removed] = inv.splice(i, 1)
        return removed ?? item.replace(/\s+/g, " ").trim()
      }
    }
    return null
  }
  startingAssets.forEach(addInventoryItem)
  const effectiveDeltasByOrd = new Map<number, EffectiveInventoryDelta>()
  for (const msg of messages) {
    if (msg.role !== "narrator" || !msg.inventory_delta) continue
    const effectiveDelta: EffectiveInventoryDelta = {
      added: [],
      removed: [],
      reason: msg.inventory_delta.reason,
    }
    for (const added of msg.inventory_delta.added) {
      const effectiveAdded = addInventoryItem(added)
      if (effectiveAdded) effectiveDelta.added.push(effectiveAdded)
    }
    for (const removed of msg.inventory_delta.removed) {
      const effectiveRemoved = removeInventoryItem(removed)
      if (effectiveRemoved) effectiveDelta.removed.push(effectiveRemoved)
    }
    effectiveDeltasByOrd.set(msg.ord, effectiveDelta)
  }
  return { inventory: inv, effectiveDeltasByOrd }
}

export function computeLiveInventory(
  startingAssets: string[],
  messages: NarrativeStoryMessage[],
): string[] {
  return computeInventoryProgress(startingAssets, messages).inventory
}

export function computeEffectiveInventoryDeltas(
  startingAssets: string[],
  messages: NarrativeStoryMessage[],
): Map<number, EffectiveInventoryDelta> {
  return computeInventoryProgress(startingAssets, messages).effectiveDeltasByOrd
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


// Color palette for the 8 known tags. Active/aggressive tags use warm
// gold or red; passive/defensive use neutral or purple. Unknown tags
// fall back to neutral.
function optionTagStyle(tag: string): CSSProperties {
  const ACTIVE_HOT = {
    color: "rgba(245,180,170,0.96)",
  }
  const ACTIVE_GOLD = {
    color: "rgba(245,210,140,0.96)",
  }
  const ACTIVE_PURPLE = {
    color: "rgba(200,170,235,0.96)",
  }
  const ACTIVE_TEAL = {
    color: "rgba(170,225,235,0.94)",
  }
  const PASSIVE = {
    color: "var(--text-muted)",
  }
  // Chinese tag set (legacy) and English mirror (used when template
  // language=en). Unknown tags fall through to PASSIVE — the directive
  // in engine.py keeps both sets stable, so this list rarely needs
  // updating.
  if (tag === "Leverage" || tag === "反将牌") return ACTIVE_GOLD
  if (
    tag === "挑拨" ||
    tag === "硬刚" ||
    ["Provoke", "Confront", "Press", "Push", "Challenge", "Accuse"].includes(tag)
  ) return ACTIVE_HOT
  if (
    tag === "反将" ||
    tag === "合作" ||
    ["Counter", "Ally", "Support", "Reassure", "Cooperate"].includes(tag)
  ) return ACTIVE_TEAL
  if (
    tag === "试探" ||
    ["Probe", "Ask", "Question", "Search", "Listen", "Inspect"].includes(tag)
  ) return ACTIVE_PURPLE
  // 妥协 / 观望 / 示弱 / Yield / Watch / Submit / unknown → PASSIVE
  return PASSIVE
}

function optionTagGuide(tag: string, t: ReturnType<typeof useT>): string {
  const normalized = tag.trim().toLowerCase()
  if (
    ["probe", "ask", "question", "search", "listen", "inspect"].includes(normalized) ||
    tag === "试探"
  ) return t("play.option_intent_probe")
  if (
    ["confront", "provoke", "press", "push", "challenge", "accuse"].includes(normalized) ||
    tag === "硬刚" ||
    tag === "挑拨"
  ) {
    return t("play.option_intent_confront")
  }
  if (
    ["ally", "counter", "support", "reassure", "cooperate"].includes(normalized) ||
    tag === "合作" ||
    tag === "反将"
  ) {
    return t("play.option_intent_ally")
  }
  if (
    ["hold", "cover", "deflect", "distract", "stall", "calm", "wait", "watch", "yield"].includes(normalized) ||
    ["稳住", "掩护", "转移", "拖延", "观望", "妥协"].includes(tag)
  ) {
    return t("play.option_intent_stabilize")
  }
  if (normalized === "leverage" || tag === "反将牌") return t("play.option_intent_leverage")
  return t("play.option_intent_default")
}


function ResolvingTurnPanel({
  moveTag,
  moveText,
  privateIntent,
  target,
  commitmentSignals = [],
  isFinalTurn = false,
}: {
  moveTag?: string
  moveText: string
  privateIntent?: string
  target?: string
  commitmentSignals?: ResolvingCommitmentSignal[]
  isFinalTurn?: boolean
}) {
  const t = useT()
  const reducedMotion = useReducedMotion()
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const privateIntentCopy = privateIntent?.trim()
  const moveMeta = moveTag?.trim()
  const progressCopy =
    elapsedSeconds >= 10
      ? t("play.resolve_progress_slow", { seconds: elapsedSeconds })
      : elapsedSeconds > 0
      ? t("play.resolve_progress_elapsed", { seconds: elapsedSeconds })
      : t("play.resolve_progress")
  const resolveStatus = target
    ? t("play.resolve_status_target", { target })
    : t("play.resolve_status_room")
  const moveCopy = moveText || t("play.resolve_custom_move")
  const feedbackSteps = [
    { id: "receipt", label: t("play.feedback_pending_receipt_label"), state: "done" },
    { id: "reaction", label: t("play.feedback_pending_reaction_label"), state: "active" },
    {
      id: "update",
      label: isFinalTurn
        ? t("play.feedback_pending_finale_label")
        : t("play.feedback_pending_update_label"),
      state: "waiting",
    },
  ] as const
  const reactionCues = [
    target ? t("play.feedback_pending_cue_target", { target }) : t("play.feedback_pending_cue_people"),
    t("play.feedback_pending_cue_state"),
    isFinalTurn ? t("play.feedback_pending_cue_finale") : t("play.feedback_pending_cue_next"),
  ]
  const resolvingAriaLabel = [t("play.resolve_title"), moveMeta, moveCopy, resolveStatus, progressCopy]
    .filter(Boolean)
    .join(". ")
  useEffect(() => {
    setElapsedSeconds(0)
    const startedAt = Date.now()
    const id = window.setInterval(() => {
      setElapsedSeconds(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => window.clearInterval(id)
  }, [moveCopy])
  return (
    <motion.div
      key="turn-resolving"
      style={ppStyles.resolvingPanel}
      data-play-pending-reaction-panel="true"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={transitions.snap}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label={resolvingAriaLabel}
    >
      <div style={ppStyles.moveReceiptPanel} data-play-move-receipt="true">
        <span style={ppStyles.resolvingTitle}>{t("play.move_receipt_title")}</span>
        <span style={ppStyles.moveReceiptBody}>
          {moveMeta ? <span style={ppStyles.resolvingReceiptMeta}>{moveMeta}</span> : null}
          <strong style={ppStyles.resolvingMoveText} title={moveCopy}>
            {moveCopy}
          </strong>
        </span>
        {privateIntentCopy ? (
          <span style={ppStyles.resolvingPrivateLine}>
            <span style={ppStyles.resolvingPrivateLabel}>{t("play.move_packet_private_label")}</span>
            <span style={ppStyles.resolvingPrivateCopy} title={privateIntentCopy}>{privateIntentCopy}</span>
          </span>
        ) : null}
        {commitmentSignals.length ? (
          <span
            style={ppStyles.resolvingCommitmentSignals}
            data-play-move-receipt-signals="true"
            aria-label={t("play.move_receipt_signals_label")}
          >
            <span
              style={ppStyles.resolvingCommitmentSignalsLabel}
              data-play-move-receipt-signals-label="true"
            >
              {t("play.move_receipt_signals_label")}
            </span>
            {commitmentSignals.map((signal) => (
              <span
                key={signal.id}
                style={{
                  ...ppStyles.gameplayDeltaChip,
                  ...ppStyles.resolvingCommitmentSignalChip,
                  ...resolvingSignalToneStyle(signal.tone),
                }}
                data-play-move-receipt-signal="true"
                data-play-move-receipt-signal-tone={signal.tone}
                title={signal.title ?? signal.label}
              >
                {signal.label}
              </span>
            ))}
          </span>
        ) : null}
      </div>
      <div style={ppStyles.roomReactingPanel} data-play-room-reacting="true">
        <span style={ppStyles.roomReactingRail} aria-hidden />
        <span style={ppStyles.roomReactingCopy}>
          <span style={ppStyles.resolvingStatus}>{resolveStatus}</span>
          <strong style={ppStyles.roomReactingTitle}>{t("play.room_reacting_title")}</strong>
          <span style={ppStyles.resolvingProgressText}>{progressCopy}</span>
          <span style={ppStyles.roomReactingCues} data-play-room-reacting-cues="true">
            {reactionCues.map((cue) => (
              <span key={cue} style={ppStyles.roomReactingCue} data-play-room-reacting-cue="true">
                {cue}
              </span>
            ))}
          </span>
        </span>
        <span style={ppStyles.resolvingDots} aria-hidden>
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              style={ppStyles.resolvingDot}
              animate={reducedMotion ? undefined : { opacity: [0.24, 1, 0.24] }}
              transition={reducedMotion
                ? undefined
                : {
                    duration: 1.1,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: i * 0.14,
                  }}
            />
          ))}
        </span>
      </div>
      <div
        style={ppStyles.feedbackPendingTimeline}
        data-play-feedback-timeline="true"
        aria-label={t("play.feedback_pending_timeline_label")}
      >
        {feedbackSteps.map((step) => (
          <span
            key={step.id}
            style={{
              ...ppStyles.feedbackPendingStep,
              ...(step.state === "done"
                ? ppStyles.feedbackPendingStepDone
                : step.state === "active"
                  ? ppStyles.feedbackPendingStepActive
                  : null),
            }}
            data-play-feedback-step={step.id}
            data-play-feedback-step-state={step.state}
          >
            <span style={ppStyles.feedbackPendingStepDot} aria-hidden />
            <span style={ppStyles.feedbackPendingStepLabel}>{step.label}</span>
          </span>
        ))}
        <span style={ppStyles.feedbackPendingHint} data-play-feedback-timeline-hint="true">
          {isFinalTurn
            ? t("play.feedback_pending_finale_hint")
            : t("play.feedback_pending_next_hint")}
        </span>
      </div>
    </motion.div>
  )
}

export function findActionTarget(
  body: string,
  hint: string | undefined,
  castNameById: Record<string, string>,
  latestNpcPulses: NarrativeNPCPulse[],
): { id: string; name: string; pulse?: NarrativeNPCPulse } | null {
  const haystack = `${body} ${hint ?? ""}`.toLowerCase()
  const matched = Object.entries(castNameById)
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => b.name.length - a.name.length)
    .find(({ name }) => {
      const lowerName = name.toLowerCase()
      if (haystack.includes(lowerName)) return true
      return lowerName
        .split(/\s+/)
        .filter((part) => part.length >= 3)
        .some((part) => haystack.includes(part))
    })
  if (!matched) return null
  return {
    id: matched.id,
    name: matched.name,
    pulse: latestNpcPulses.find((pulse) => pulse.npc_id === matched.id),
  }
}

export type GameplayResourceFocusId = "time" | "pressure" | "evidence"

export function isResourceFocusAction(
  resourceId: GameplayResourceFocusId,
  body: string,
  hint: string | undefined,
  forecasts: GameplayActionForecast[],
): boolean {
  const forecastText = forecasts.map((chip) => chip.label).join(" ")
  if (resourceId === "time") {
    if (/\b(time|turn|clock|delay|wait|minutes?)\b/i.test(forecastText)) return true
    const haystack = `${body} ${hint ?? ""}`.toLowerCase()
    return /\b(time|clock|countdown|minute|deadline|delay|stall|wait|hold|freeze|rush|hurry)\b/.test(haystack)
  }
  if (resourceId === "pressure") {
    if (/\b(pressure|risk|danger|heat|suspicion|public)\b/i.test(forecastText)) return true
    const haystack = `${body} ${hint ?? ""}`.toLowerCase()
    return /\b(pressure|risk|danger|threat|panic|public|expose|accuse|confront|force|sponsor|suspicion)\b/.test(haystack)
  }
  if (/\b(evidence|clue|proof|lead|badge|recording|footage|document|receipt|log)\b/i.test(forecastText)) {
    return true
  }
  const haystack = `${body} ${hint ?? ""}`.toLowerCase()
  return /\b(clue|evidence|proof|recording|footage|badge|phone|message|lead|find|discover|document|receipt|log|memo|security)\b/.test(haystack)
}

function resourceFocusDetailText(
  t: ReturnType<typeof useT>,
  resourceId: GameplayResourceFocusId,
  matchCount: number,
): string {
  if (resourceId === "time") {
    return matchCount > 0
      ? t(
          matchCount === 1
            ? "play.resource_focus_time_match_detail_one"
            : "play.resource_focus_time_match_detail_many",
          { count: matchCount },
        )
      : t("play.resource_focus_time_no_match")
  }
  if (resourceId === "pressure") {
    return matchCount > 0
      ? t(
          matchCount === 1
            ? "play.resource_focus_pressure_match_detail_one"
            : "play.resource_focus_pressure_match_detail_many",
          { count: matchCount },
        )
      : t("play.resource_focus_pressure_no_match")
  }
  return matchCount > 0
    ? t(
        matchCount === 1
          ? "play.resource_focus_evidence_match_detail_one"
          : "play.resource_focus_evidence_match_detail_many",
        { count: matchCount },
      )
    : t("play.resource_focus_evidence_no_match")
}

// ---------------------------------------------------------------------------
// Action area — options + free input
// ---------------------------------------------------------------------------

export function ActionArea({
  options,
  actionForecasts,
  leverageCards,
  roleHasNoLeverage,
  latestNpcPulses,
  castNameById,
  turnsCompleted,
  turnsRemaining,
  turnBudget,
  hasRecentImpact,
  actorFocus,
  resourceFocus,
  inventoryFocusItem,
  showFreeInput,
  freeInput,
  setFreeInput,
  setShowFreeInput,
  diary,
  setDiary,
  showDiary,
  setShowDiary,
  busy,
  onCommitmentActiveChange,
  onCommitmentSummaryChange,
  onClearActorFocus,
  onClearResourceFocus,
  onClearInventoryFocus,
  onPickOption,
  onPlayLeverage,
  onSubmitFree,
}: {
  options: NarrativeStoryMessage["options"]
  actionForecasts?: GameplayActionForecast[][]
  leverageCards: LeverageCardView[]
  roleHasNoLeverage: boolean
  latestNpcPulses: NarrativeNPCPulse[]
  castNameById: Record<string, string>
  turnsCompleted: number
  turnsRemaining: number
  turnBudget: number
  hasRecentImpact?: boolean
  actorFocus?: { id: string; name: string } | null
  resourceFocus?: { id: GameplayResourceFocusId; label: string } | null
  inventoryFocusItem?: string | null
  showFreeInput: boolean
  freeInput: string
  setFreeInput: (v: string) => void
  setShowFreeInput: (v: boolean) => void
  diary: string
  setDiary: (v: string) => void
  showDiary: boolean
  setShowDiary: (v: boolean) => void
  busy: boolean
  onCommitmentActiveChange: (active: boolean) => void
  onCommitmentSummaryChange: (summary: ActionCommitmentSummary | null) => void
  onClearActorFocus?: () => void
  onClearResourceFocus?: () => void
  onClearInventoryFocus?: () => void
  onPickOption: (idx: number, diaryOverride?: string) => void
  onPlayLeverage: (card: LeverageCardView, diaryOverride?: string) => void
  onSubmitFree: (diaryOverride?: string, freeInputOverride?: string) => void
}) {
  const t = useT()
  // Local "I picked option N this turn" so we can immediately reflect
  // the choice — instead of just dimming everything to 50% opacity
  // and waiting 5-8s for the LLM. State resets every turn because
  // the parent gives us key={beat.ord}, remounting ActionArea.
  const [pickedIndex, setPickedIndex] = useState<number | null>(null)
  const [selectedOptionIndex, setSelectedOptionIndex] = useState<number | null>(null)
  const [submittedFree, setSubmittedFree] = useState(false)
  const [submittedLeverageLabel, setSubmittedLeverageLabel] = useState<string | null>(null)
  const [submittedLeverageTarget, setSubmittedLeverageTarget] = useState<string | null>(null)
  const [leverageExpanded, setLeverageExpanded] = useState(false)
  const [revealingLeverageCardId, setRevealingLeverageCardId] = useState<string | null>(null)
  const leverageRevealTimerRef = useRef<number | null>(null)
  const actionSubmitLockedRef = useRef(false)
  const commitFocusRef = useRef<HTMLElement | null>(null)
  const freeActionRef = useRef<HTMLDivElement | null>(null)
  const freeTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const diaryTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const diaryScopeRef = useRef("idle")
  const setCommitFocusNode = useCallback((node: HTMLElement | null) => {
    commitFocusRef.current = node
  }, [])
  const setFreeActionNode = useCallback((node: HTMLDivElement | null) => {
    freeActionRef.current = node
  }, [])
  const compactLeverage = useCompactLayout()
  const compactActionChrome = useCompactLayout("(max-width: 680px)")
  const reducedMotion = useReducedMotion()
  const playableLeverageCards = useMemo(
    () => leverageCards.filter((card) => !card.used),
    [leverageCards],
  )
  const spentLeverageCards = useMemo(
    () => leverageCards.filter((card) => card.used),
    [leverageCards],
  )
  const [armedCardId, setArmedCardId] = useState<string | null>(null)
  const sceneClocks = buildSceneClocks({
    turnsCompleted,
    turnBudget,
    latestNpcPulses,
    leverageCards,
    t,
  })
  const armedCard = playableLeverageCards.find((card) => card.card_id === armedCardId) ?? null
  const armedCardTargetName = armedCard?.target_name ?? ""
  const armedCardLeverage = armedCard?.leverage ?? ""
  const isRevealingLeverage = revealingLeverageCardId !== null
  const showLeverageCards = leverageExpanded || !!armedCard
  const hasSinglePlayableLeverage = playableLeverageCards.length === 1
  const hasMultiplePlayableLeverage = playableLeverageCards.length > 1
  const primaryLeverageCard = armedCard ?? playableLeverageCards[0] ?? null
  const playableLeverageTargetText = (() => {
    const names = playableLeverageCards.map((card) => card.target_name)
    const visibleNames = names.slice(0, 2).join(" · ")
    const remaining = Math.max(0, names.length - 2)
    return remaining > 0 ? `${visibleNames} · +${remaining}` : visibleNames
  })()
  const leverageSummaryText = armedCard
    ? t("play.leverage_summary_prepared", { target: armedCard.target_name })
    : hasSinglePlayableLeverage && primaryLeverageCard
      ? t("play.leverage_summary_action", { target: primaryLeverageCard.target_name })
      : playableLeverageTargetText
        ? t("play.leverage_summary_choose")
        : t("play.leverage_summary_count", { count: playableLeverageCards.length })
  const leverageSummaryMetaText = armedCard
    ? t("play.leverage_summary_meta_target", { target: armedCard.target_name })
    : hasSinglePlayableLeverage && primaryLeverageCard
      ? `${t("play.leverage_summary_meta_target", { target: primaryLeverageCard.target_name })} · ${primaryLeverageCard.leverage}`
      : `${t("play.leverage_summary_count", { count: playableLeverageCards.length })} · ${t("play.leverage_rail_hint")}`
  const leverageSummaryToggleText = leverageExpanded
    ? t("play.leverage_collapse")
    : armedCard
      ? t("play.leverage_change")
      : hasSinglePlayableLeverage
        ? t("play.leverage_summary_prepare")
        : t("play.leverage_expand")
  const leverageSummaryChipTarget = primaryLeverageCard?.target_name ?? ""
  const spentLeverageTargets = spentLeverageCards.map((card) => card.target_name).join(" · ")
  const leverageEmptyMetaText = spentLeverageTargets
    ? t("play.leverage_empty_meta", { targets: spentLeverageTargets })
    : roleHasNoLeverage
      ? t("play.leverage_summary_meta_no_role_cards")
      : t("play.leverage_summary_meta_empty")
  const leverageEmptyTitle = roleHasNoLeverage
    ? t("play.leverage_empty_none_title")
    : t("play.leverage_empty_title")
  const leverageEmptyBadge = roleHasNoLeverage
    ? t("play.leverage_empty_none_title")
    : t("play.leverage_spent")
  const leverageConfirmCancelText = hasMultiplePlayableLeverage
    ? t("play.leverage_confirm_choose_another")
    : t("play.leverage_confirm_cancel")
  const commitmentSurfaceOpen =
    selectedOptionIndex !== null ||
    armedCardId !== null ||
    showFreeInput ||
    options.length === 0
  const handleLeverageSummaryActivate = () => {
    if (!primaryLeverageCard || busy || actionSubmitLockedRef.current || isRevealingLeverage) return
    if (hasSinglePlayableLeverage) {
      setSelectedOptionIndex(null)
      setShowFreeInput(false)
      onClearInventoryFocus?.()
      setLeverageExpanded(false)
      setArmedCardId(primaryLeverageCard.card_id)
      return
    }
    setLeverageExpanded((value) => !value)
  }
  const handleOptionSelect = (i: number) => {
    if (busy || actionSubmitLockedRef.current || isRevealingLeverage) return
    setArmedCardId(null)
    setShowFreeInput(false)
    onClearInventoryFocus?.()
    setSelectedOptionIndex(i)
  }
  const handleActionAreaPointerDownCapture = (event: PointerEvent<HTMLDivElement>) => {
    if (selectedOptionIndex === null || busy || actionSubmitLockedRef.current || pickedIndex !== null) return
    const target = event.target as HTMLElement | null
    if (!target) return
    if (
      target.closest(
        [
          "[data-play-action-option-card='true']",
          "[data-play-action-card-confirm-panel='true']",
          "[data-play-collapse-exempt='true']",
          "button",
          "textarea",
          "input",
          "[role='dialog']",
        ].join(","),
      )
    ) {
      return
    }
    setSelectedOptionIndex(null)
    if (showDiary && diaryContext === "option") {
      setShowDiary(false)
    }
  }

  const handleOptionCommit = (i: number, diaryOverride?: string) => {
    if (busy || actionSubmitLockedRef.current || isRevealingLeverage) return
    actionSubmitLockedRef.current = true
    setPickedIndex(i)
    setSelectedOptionIndex(i)
    onPickOption(i, diaryOverride)
  }

  const handleLeverageReveal = (card: LeverageCardView, diaryOverride?: string) => {
    if (busy || actionSubmitLockedRef.current || card.used || isRevealingLeverage) return
    actionSubmitLockedRef.current = true
    setSubmittedFree(true)
    setSubmittedLeverageLabel(t("play.leverage_submit_echo", { target: card.target_name }))
    setSubmittedLeverageTarget(card.target_name)
    setRevealingLeverageCardId(card.card_id)
    leverageRevealTimerRef.current = window.setTimeout(() => {
      onPlayLeverage(card, diaryOverride)
      leverageRevealTimerRef.current = null
    }, 360)
  }

  useEffect(() => () => {
    if (leverageRevealTimerRef.current !== null) {
      window.clearTimeout(leverageRevealTimerRef.current)
    }
    onCommitmentActiveChange(false)
    onCommitmentSummaryChange(null)
  }, [onCommitmentActiveChange, onCommitmentSummaryChange])

  useEffect(() => {
    onCommitmentActiveChange(commitmentSurfaceOpen)
  }, [commitmentSurfaceOpen, onCommitmentActiveChange])

  useEffect(() => {
    if (busy) return
    setShowDiary(false)
  }, [armedCardId, busy, options.length, selectedOptionIndex, setShowDiary, showFreeInput])

  const actionSubmissionInFlight = pickedIndex !== null || submittedFree || isRevealingLeverage
  const actionControlsDisabled = busy || actionSubmissionInFlight
  const inlineActionDisabledStyle = actionControlsDisabled ? ppStyles.inlineActionDisabled : null
  const showPickedReflection = actionSubmissionInFlight

  useEffect(() => {
    if (!showPickedReflection && busy) return
    if (!showPickedReflection && !commitmentSurfaceOpen) return
    const frame = window.requestAnimationFrame(() => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      const behavior: ScrollBehavior = prefersReducedMotion ? "auto" : "smooth"
      if (showPickedReflection && busy) {
        const pendingPanel = document.querySelector<HTMLElement>("[data-play-pending-reaction-panel='true']")
        if (pendingPanel) {
          const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
          const rect = pendingPanel.getBoundingClientRect()
          const top = Math.max(0, window.scrollY + rect.top - headerHeight - 12)
          window.scrollTo({ top, left: 0, behavior })
          return
        }
      }
      if (selectedOptionIndex !== null && !showPickedReflection) {
        const confirmPanel = document.querySelector<HTMLElement>("[data-play-action-card-confirm-panel='true']")
        if (confirmPanel) {
          const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
          const rect = confirmPanel.getBoundingClientRect()
          const visibleTop = headerHeight + 12
          const visibleBottom = window.innerHeight - 12
          if (rect.bottom > visibleBottom || rect.top < visibleTop) {
            const top =
              rect.bottom > visibleBottom
                ? Math.max(0, window.scrollY + rect.bottom - visibleBottom)
                : Math.max(0, window.scrollY + rect.top - visibleTop)
            window.scrollTo({ top, left: 0, behavior })
            return
          }
        }
      }
      const selectedMove = document.querySelector<HTMLElement>("[data-play-selected-move='true']")
      if (selectedMove) {
        const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
        const rect = selectedMove.getBoundingClientRect()
        const top = Math.max(0, window.scrollY + rect.top - headerHeight - 12)
        window.scrollTo({ top, left: 0, behavior })
        return
      }
      commitFocusRef.current?.scrollIntoView({
        block: "center",
        behavior,
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [busy, commitmentSurfaceOpen, selectedOptionIndex, showPickedReflection])

  useEffect(() => {
    if (armedCardId && !playableLeverageCards.some((card) => card.card_id === armedCardId)) {
      setArmedCardId(null)
    }
  }, [armedCardId, playableLeverageCards])

  // Once the parent flips busy=false (turn settled, narrator beat
  // arrived), the parent will remount us via key change anyway. But
  // if the request fails and busy goes false without remount, clear
  // the picked state so the user can retry.
  useEffect(() => {
    if (!busy) {
      actionSubmitLockedRef.current = false
      setPickedIndex(null)
      setSelectedOptionIndex(null)
      setSubmittedFree(false)
      setSubmittedLeverageLabel(null)
      setSubmittedLeverageTarget(null)
      setRevealingLeverageCardId(null)
    }
  }, [busy])

  // Keyboard shortcuts:
  //   1 / 2 / 3 ... pick the corresponding option (when not focused
  //   in a text input / textarea — otherwise the digit just types).
  // The hint chips on each option button reflect this.
  useEffect(() => {
    if (busy) return
    const handler = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement | null
      if (!tgt) return
      // When the advisor drawer or any other modal is open, its buttons
      // and composer own the keyboard. The play-surface shortcuts must
      // not leak through and arm/submit an action behind the dialog.
      if (document.querySelector("[role='dialog'][aria-modal='true']")) return
      const inEditable =
        tgt.tagName === "TEXTAREA" ||
        tgt.tagName === "INPUT" ||
        tgt.isContentEditable
      if (inEditable) return
      if (actionSubmitLockedRef.current) {
        if (e.key === "Enter" || e.key === "Escape") {
          e.preventDefault()
        }
        return
      }
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return
      if (e.key >= "1" && e.key <= "9") {
        const idx = parseInt(e.key, 10) - 1
        if (idx >= 0 && idx < options.length) {
          e.preventDefault()
          if (selectedOptionIndex === idx) {
            handleOptionCommit(idx)
          } else {
            handleOptionSelect(idx)
          }
        }
      }
      if (
        e.key.toLowerCase() === "t" &&
        playableLeverageCards.length > 0 &&
        !armedCard &&
        selectedOptionIndex === null &&
        !showFreeInput
      ) {
        e.preventDefault()
        handleLeverageSummaryActivate()
      }
      if (e.key === "Enter" && selectedOptionIndex !== null) {
        e.preventDefault()
        handleOptionCommit(selectedOptionIndex)
      } else if (e.key === "Enter" && armedCard) {
        e.preventDefault()
        handleLeverageReveal(armedCard)
      } else if (e.key === "Escape") {
        e.preventDefault()
        setSelectedOptionIndex(null)
        setArmedCardId(null)
        if (showFreeInput && options.length > 0) {
          setShowFreeInput(false)
          if (!freeInput.trim()) {
            setFreeInput("")
          }
        }
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, options.length, selectedOptionIndex, armedCardId, isRevealingLeverage, showFreeInput, freeInput])

  const isOptionCommitPending =
    showPickedReflection && pickedIndex !== null && selectedOptionIndex === pickedIndex
  const pickedOption = pickedIndex !== null ? options[pickedIndex] : null
  const pickedOptionParsed = pickedOption ? parseOptionLabel(pickedOption.label) : null
  const selectedOption = selectedOptionIndex !== null ? options[selectedOptionIndex] : null
  const selectedOptionParsed = selectedOption ? parseOptionLabel(selectedOption.label) : null
  const visibleOptionEntries = options
    .map((opt, i) => ({ opt, i }))
  const optionTargets = useMemo(() => options.map((opt) => {
    const parsed = parseOptionLabel(opt.label)
    return findActionTarget(parsed.body, opt.hint, castNameById, latestNpcPulses)
  }), [castNameById, latestNpcPulses, options])
  const actorFocusOptionMatches = useMemo(() => {
    if (!actorFocus) return optionTargets.map(() => false)
    return optionTargets.map((target) => target?.id === actorFocus.id)
  }, [actorFocus, optionTargets])
  const actorFocusMatchCount = actorFocusOptionMatches.filter(Boolean).length
  const actorFocusLeverageCard = useMemo(() => {
    if (!actorFocus) return null
    const focusedName = actorFocus.name.trim().toLowerCase()
    const focusedId = actorFocus.id.trim().toLowerCase()
    return (
      playableLeverageCards.find((card) => {
        const targetName = card.target_name.trim().toLowerCase()
        return targetName === focusedName || targetName === focusedId
      }) ?? null
    )
  }, [actorFocus, playableLeverageCards])
  const actorFocusMatchedMoves = useMemo(() => {
    if (!actorFocus) return []
    return options
      .map((opt, index) => ({
        match: actorFocusOptionMatches[index],
        index,
        label: parseOptionLabel(opt.label).body || opt.label,
      }))
      .filter((entry) => entry.match)
      .slice(0, 3)
  }, [actorFocus, actorFocusOptionMatches, options])
  const actorFocusDetail = actorFocus
    ? actorFocusMatchCount > 0
      ? t(
          actorFocusMatchCount === 1
            ? "play.actor_focus_match_detail_one"
            : "play.actor_focus_match_detail_many",
          { count: actorFocusMatchCount },
        )
      : actorFocusLeverageCard
        ? t("play.actor_focus_leverage_detail", { name: actorFocus.name })
        : t("play.actor_focus_no_match")
    : ""
  const resourceFocusOptionMatches = useMemo(() => {
    if (!resourceFocus) return options.map(() => false)
    return options.map((opt, index) => {
      const parsed = parseOptionLabel(opt.label)
      return isResourceFocusAction(resourceFocus.id, parsed.body, opt.hint, actionForecasts?.[index] ?? [])
    })
  }, [actionForecasts, options, resourceFocus])
  const resourceFocusMatchCount = resourceFocusOptionMatches.filter(Boolean).length
  const resourceFocusMatchedMoves = useMemo(() => {
    if (!resourceFocus) return []
    return options
      .map((opt, index) => ({
        match: resourceFocusOptionMatches[index],
        index,
        label: parseOptionLabel(opt.label).body || opt.label,
      }))
      .filter((entry) => entry.match)
      .slice(0, 3)
  }, [options, resourceFocus, resourceFocusOptionMatches])
  const resourceFocusDetail = resourceFocus ? resourceFocusDetailText(t, resourceFocus.id, resourceFocusMatchCount) : ""
  const freeActionFocusContext = actorFocus && actorFocusMatchCount === 0
    ? {
        kind: "actor" as const,
        id: actorFocus.id,
        label: actorFocus.name,
        detail: actorFocusLeverageCard
          ? t("play.free_context_actor_leverage_detail", { name: actorFocus.name })
          : t("play.free_context_actor_detail", { name: actorFocus.name }),
        placeholder: t("play.action_free_actor_placeholder", { name: actorFocus.name }),
        toggleText: t("play.action_open_free_actor", { name: actorFocus.name }),
        toggleHint: t("play.action_open_free_actor_hint"),
        toggleTitle: t("play.action_open_free_actor_title", { name: actorFocus.name }),
      }
    : resourceFocus && resourceFocusMatchCount === 0
      ? {
          kind: "resource" as const,
          id: resourceFocus.id,
          label: resourceFocus.label,
          detail: resourceFocusDetail,
          placeholder: resourceFocus.id === "time"
            ? t("play.action_free_time_placeholder")
            : resourceFocus.id === "pressure"
              ? t("play.action_free_pressure_placeholder")
              : t("play.action_free_evidence_placeholder"),
          toggleText: t("play.action_open_free_resource", { label: resourceFocus.label }),
          toggleHint: t("play.action_open_free_resource_hint"),
          toggleTitle: t("play.action_open_free_resource_title", { label: resourceFocus.label }),
        }
      : inventoryFocusItem
        ? {
            kind: "inventory" as const,
            id: inventoryFocusItem,
            label: inventoryFocusItem,
            detail: t("play.free_context_inventory_detail", { item: inventoryFocusItem }),
            placeholder: t("play.action_free_inventory_placeholder", { item: inventoryFocusItem }),
            toggleText: t("play.action_open_free_inventory", { item: inventoryFocusItem }),
            toggleHint: t("play.action_open_free_inventory_hint"),
            toggleTitle: t("play.action_open_free_inventory_title", { item: inventoryFocusItem }),
          }
      : null
  const freeActionDraft = freeInput.trim()
  const freeActionReady = freeActionDraft.length > 0
  const freeActionTarget = freeActionDraft
    ? findActionTarget(freeActionDraft, undefined, castNameById, latestNpcPulses)
    : null
  const freeActionTargetName = freeActionTarget?.name ?? ""
  const freeActionContextTargetName =
    freeActionFocusContext?.kind === "actor" ? freeActionFocusContext.label : ""
  const freeActionReceiptPrefix =
    freeActionFocusContext?.kind === "actor" || freeActionFocusContext?.kind === "inventory"
      ? freeActionFocusContext.label
      : ""
  const freeActionTargetNameForFeedback = freeActionContextTargetName || freeActionTargetName
  const freeActionSubmittedText =
    freeActionDraft &&
    freeActionReceiptPrefix &&
    !freeActionDraft.toLocaleLowerCase().includes(freeActionReceiptPrefix.toLocaleLowerCase())
      ? `${freeActionReceiptPrefix} — ${freeActionDraft}`
      : freeActionDraft
  const freeActionStarterMoves = !freeActionDraft
    ? buildFreeActionStarterMoves({ context: freeActionFocusContext, t })
    : []
  const freeComposerOpen = showFreeInput || options.length === 0
  const diaryContext = armedCard
    ? "leverage"
    : selectedOption && selectedOptionParsed && pickedIndex === null && !busy
      ? "option"
      : freeComposerOpen
        ? "free"
        : "idle"
  const isWritingOptionDiary = showDiary && diaryContext === "option"
  const isWritingLeverageDiary = showDiary && diaryContext === "leverage"
  const isWritingFreeDiary = showDiary && diaryContext === "free"
  const selectedOptionGuideTitle = selectedOptionParsed?.tag
    ? isWritingOptionDiary
      ? t("play.turn_guide_inner_motive_title")
      : t("play.turn_guide_selected_named_title", { tag: selectedOptionParsed.tag })
    : isWritingOptionDiary
      ? t("play.turn_guide_inner_motive_title")
      : t("play.turn_guide_selected_title")
  const selectedOptionGuideDetail = selectedOptionParsed?.body
    ? isWritingOptionDiary
      ? t("play.turn_guide_inner_motive_detail")
      : t("play.turn_guide_selected_named_detail", {
          action: truncateRecoveryText(selectedOptionParsed.body, 72),
        })
    : isWritingOptionDiary
      ? t("play.turn_guide_inner_motive_detail")
      : t("play.turn_guide_selected_detail")

  useEffect(() => {
    if (busy || !freeComposerOpen || !freeActionReady) return
    const frame = window.requestAnimationFrame(() => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      freeActionRef.current?.scrollIntoView({
        block: "center",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [busy, freeActionReady, freeComposerOpen])

  useEffect(() => {
    if (busy || !freeComposerOpen) return
    const focusFreeTextarea = () => {
      const node = freeTextareaRef.current
      if (!node || node.disabled) return
      fitTextareaToContent(node)
      node.focus({ preventScroll: true })
      const cursor = node.value.length
      node.setSelectionRange(cursor, cursor)
    }
    const frame = window.requestAnimationFrame(() => {
      focusFreeTextarea()
    })
    const timers = [90, 240, 420].map((delay) => window.setTimeout(focusFreeTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, freeComposerOpen])

  useEffect(() => {
    if (!freeComposerOpen) return
    const frame = window.requestAnimationFrame(() => {
      fitTextareaToContent(freeTextareaRef.current)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [freeComposerOpen, freeInput])

  const isFinalTurn = turnsRemaining <= 1
  const isEndgameTurn = turnsRemaining <= 2
  const turnGuide =
    armedCard
      ? {
          title: t("play.turn_guide_leverage_title", { target: armedCard.target_name }),
          detail: t("play.turn_guide_leverage_detail"),
          tone: ppStyles.turnGuideLeverage,
        }
      : selectedOptionParsed
        ? {
            title: selectedOptionGuideTitle,
            detail: selectedOptionGuideDetail,
            tone: ppStyles.turnGuideSelected,
          }
        : showFreeInput && freeActionReady
          ? {
              title: t("play.turn_guide_free_ready_title"),
              detail: t("play.turn_guide_free_ready_detail"),
              tone: ppStyles.turnGuideSelected,
            }
        : showFreeInput
          ? {
              title: t("play.turn_guide_free_title"),
              detail: t("play.turn_guide_free_detail"),
              tone: ppStyles.turnGuideFree,
            }
          : options.length === 0
            ? {
                title: t("play.turn_guide_free_title"),
                detail: t("play.turn_guide_no_options_detail"),
                tone: ppStyles.turnGuideFree,
              }
          : isFinalTurn
            ? {
                title: t("play.turn_guide_final_title"),
                detail: t("play.turn_guide_final_detail"),
                tone: ppStyles.turnGuideFinal,
              }
            : isEndgameTurn
              ? {
                  title: t("play.turn_guide_endgame_title"),
                  detail: t("play.turn_guide_endgame_detail", { count: turnsRemaining }),
                  tone: ppStyles.turnGuideEndgame,
                }
              : {
                  title: hasRecentImpact
                    ? t("play.turn_guide_after_impact_title")
                    : t("play.turn_guide_idle_title"),
                  detail: hasRecentImpact
                    ? t("play.turn_guide_after_impact_detail")
                    : playableLeverageCards.length > 0
                      ? t("play.turn_guide_idle_detail_with_leverage")
                      : t("play.turn_guide_idle_detail"),
                  tone: null,
                }
  const showActionTelemetry = !commitmentSurfaceOpen && !showPickedReflection && options.length === 0
  const showLeverageCardPicker =
    showLeverageCards && playableLeverageCards.length > 0 && !armedCard && !hasSinglePlayableLeverage
  const showFreeActionSurface = !armedCard && selectedOptionIndex === null && !showPickedReflection
  const showFreeComposer = showFreeActionSurface && freeComposerOpen
  const showStandardOptions = !armedCard && !showFreeComposer && !showPickedReflection
  const showLeverageRail = leverageCards.length > 0 && !commitmentSurfaceOpen
  const showFreeActionToggle =
    showFreeActionSurface &&
    !showFreeInput &&
    options.length > 0
  const freeActionToggleShownInFocusCue =
    showStandardOptions &&
    ((actorFocus && actorFocusMatchCount === 0) || (resourceFocus && resourceFocusMatchCount === 0))
  const showAlternateFreeActionToggle = showFreeActionToggle && !freeActionToggleShownInFocusCue
  const freeActionToggleText = freeInput.trim()
    ? t("play.action_resume_free")
    : freeActionFocusContext?.toggleText ?? t("play.action_open_free")
  const freeActionDraftPreview = freeActionDraft
    ? truncateRecoveryText(freeActionDraft, 72)
    : ""
  const freeActionToggleHint = freeInput.trim()
    ? t("play.action_resume_free_hint", { draft: freeActionDraftPreview })
    : freeActionFocusContext?.toggleHint ?? t("play.action_open_free_hint")
  const freeActionToggleTitle = freeInput.trim()
    ? t("play.action_resume_free_title")
    : freeActionFocusContext?.toggleTitle ?? t("play.action_open_free_title")
  const freeTextareaPlaceholder =
    freeActionFocusContext?.placeholder ?? t("play.action_free_placeholder")
  const openFreeActionComposer = () => {
    if (actionControlsDisabled) return
    setSelectedOptionIndex(null)
    setArmedCardId(null)
    setShowFreeInput(true)
    window.requestAnimationFrame(() => {
      freeTextareaRef.current?.focus()
    })
  }
  const handleSubmitFreeWithReflect = (diaryOverride?: string) => {
    if (!freeActionSubmittedText || busy || actionSubmitLockedRef.current) return
    actionSubmitLockedRef.current = true
    setSelectedOptionIndex(null)
    setArmedCardId(null)
    setSubmittedFree(true)
    onSubmitFree(diaryOverride, freeActionSubmittedText)
  }
  const freeTextareaCanClose = options.length > 0
  const freeTextareaKeyShortcuts = freeTextareaCanClose
    ? "Meta+Enter Control+Enter Escape"
    : "Meta+Enter Control+Enter"
  const freeTextareaTitle = freeTextareaCanClose
    ? `${t("play.shortcut_mod_enter_submit")} · ${t("play.shortcut_escape_cancel")}`
    : t("play.shortcut_mod_enter_submit")
  const resolvingMoveTag =
    pickedOptionParsed?.tag ??
    (submittedLeverageLabel ? t("play.leverage_option_tag") : submittedFree ? t("play.preview_approach_custom") : "")
  const resolvingMoveText =
    pickedOptionParsed?.body ??
    submittedLeverageLabel ??
    (submittedFree ? freeActionSubmittedText || t("play.resolve_custom_move") : "")
  const resolvingTarget =
    pickedOption && pickedOptionParsed
      ? findActionTarget(pickedOptionParsed.body, pickedOption.hint, castNameById, latestNpcPulses)?.name
      : submittedLeverageLabel
        ? submittedLeverageTarget ?? undefined
        : freeActionTargetNameForFeedback || undefined
  const pickedOptionTarget =
    pickedOption && pickedOptionParsed
      ? findActionTarget(pickedOptionParsed.body, pickedOption.hint, castNameById, latestNpcPulses)
      : null
  const pickedOptionForecasts = pickedIndex !== null ? actionForecasts?.[pickedIndex] ?? [] : []
  const resolvingCommitmentSignals = useMemo<ResolvingCommitmentSignal[]>(() => {
    const signals: ResolvingCommitmentSignal[] = []
    const pushSignal = (signal: ResolvingCommitmentSignal) => {
      if (signals.some((existing) => existing.label === signal.label)) return
      signals.push(signal)
    }
    if (pickedOptionTarget) {
      pushSignal({
        id: `target:${pickedOptionTarget.id}`,
        label: `${t("play.action_target_label")} ${pickedOptionTarget.name}`,
        tone: "shift",
        title: t("play.action_target_title", { name: pickedOptionTarget.name }),
      })
    } else if (submittedLeverageTarget) {
      pushSignal({
        id: `target:leverage:${submittedLeverageTarget}`,
        label: `${t("play.action_target_label")} ${submittedLeverageTarget}`,
        tone: "shift",
        title: t("play.action_target_title", { name: submittedLeverageTarget }),
      })
    } else if (submittedFree && freeActionTargetNameForFeedback) {
      pushSignal({
        id: `target:free:${freeActionTargetNameForFeedback}`,
        label: `${t("play.action_target_label")} ${freeActionTargetNameForFeedback}`,
        tone: "shift",
        title: t("play.action_target_title", { name: freeActionTargetNameForFeedback }),
      })
    }
    pickedOptionForecasts.filter((forecast) => !forecast.detail).slice(0, 3).forEach((forecast, index) => {
      pushSignal({
        id: `forecast:${index}:${forecast.label}`,
        label: forecast.label,
        tone: forecast.tone,
        title: forecast.detail ?? forecast.label,
      })
    })
    return signals.slice(0, 3)
  }, [
    freeActionTargetNameForFeedback,
    pickedOptionForecasts,
    pickedOptionTarget,
    submittedFree,
    submittedLeverageTarget,
    t,
  ])
  const diaryDraft = diary.trim()
  const diaryPreview =
    diaryDraft.length > 130 ? `${diaryDraft.slice(0, 127)}...` : diaryDraft
  const selectedOptionBody = selectedOptionParsed?.body ?? ""
  const selectedOptionHint = selectedOption?.hint ?? ""
  const selectedOptionForecasts =
    selectedOptionIndex !== null ? actionForecasts?.[selectedOptionIndex] ?? [] : []
  const selectedOptionSubmitForecasts = selectedOptionForecasts.filter((chip) => !chip.detail)
  const selectedOptionTarget =
    selectedOptionIndex !== null ? optionTargets[selectedOptionIndex] ?? null : null
  const selectedOptionSubmitSummary =
    selectedOptionSubmitForecasts.length > 0
      ? selectedOptionSubmitForecasts.slice(0, 2).map((chip) => chip.label).join(" · ")
      : selectedOptionHint || selectedOptionForecasts.find((chip) => chip.detail)?.detail || t("play.selected_move_ready_detail")
  const selectedOptionConfirmReadableLabel = joinReadableLabelParts([
    t("play.selected_move_aria"),
    selectedOptionBody,
    selectedOptionTarget
      ? t("play.selected_move_target_chip", { target: selectedOptionTarget.name })
      : t("play.selected_move_room_chip"),
    selectedOptionSubmitSummary,
  ])
  const actionState =
    showPickedReflection
      ? "pending"
      : armedCard
        ? "leverage-ready"
        : selectedOptionIndex !== null
          ? "option-selected"
          : freeComposerOpen && freeActionReady
            ? "free-ready"
            : freeComposerOpen
              ? "free-open"
              : "idle"
  const actionStatusLabel =
    showPickedReflection
      ? `${t("play.resolve_title")}: ${resolvingMoveText || t("play.resolve_custom_move")}`
      : t("play.action_status_ready")
  const actionCommitmentSummary = useMemo<ActionCommitmentSummary | null>(() => {
    const motive = diaryDraft || undefined
    if (armedCardId && armedCardTargetName) {
      return {
        kind: "leverage",
        kicker: t("play.advisor_commitment_kind_leverage"),
        title: t("play.leverage_confirm_title", { target: armedCardTargetName }),
        detail: armedCardLeverage,
        motive,
      }
    }
    if (selectedOptionIndex !== null && selectedOptionBody && pickedIndex === null && !busy) {
      return {
        kind: "option",
        kicker: t("play.advisor_commitment_kind_option"),
        title: selectedOptionBody,
        detail: selectedOptionHint || undefined,
        motive,
      }
    }
    if (freeComposerOpen && freeActionDraft) {
      return {
        kind: "free",
        kicker: t("play.advisor_commitment_kind_free"),
        title: freeActionSubmittedText,
        detail: freeActionTargetNameForFeedback
          ? t("play.preview_action_target_value", { target: freeActionTargetNameForFeedback })
          : t("play.preview_action_read_room"),
        motive,
      }
    }
    if (freeComposerOpen) {
      return {
        kind: "free",
        kicker: t("play.advisor_commitment_kind_free"),
        title: t("play.advisor_commitment_free_empty_title"),
        detail: t("play.advisor_commitment_free_empty_detail"),
        motive,
      }
    }
    return null
  }, [
    armedCardId,
    armedCardLeverage,
    armedCardTargetName,
    busy,
    diaryDraft,
    freeActionDraft,
    freeActionSubmittedText,
    freeActionTargetNameForFeedback,
    pickedIndex,
    selectedOptionBody,
    selectedOptionHint,
    selectedOptionIndex,
    freeComposerOpen,
    t,
  ])
  useEffect(() => {
    onCommitmentSummaryChange(actionCommitmentSummary)
  }, [actionCommitmentSummary, onCommitmentSummaryChange])
  const diaryScopeKey = armedCard
    ? `leverage:${armedCard.card_id}`
    : selectedOptionIndex !== null && pickedIndex === null && !busy
      ? `option:${selectedOptionIndex}`
      : freeComposerOpen
        ? "free"
        : "idle"
  const showTurnGuide = !showPickedReflection

  useEffect(() => {
    if (actionSubmissionInFlight) return

    const previousScope = diaryScopeRef.current
    if (diaryScopeKey === "idle") {
      if (previousScope !== "idle") {
        if (diary.trim()) setDiary("")
        if (showDiary) setShowDiary(false)
      }
      diaryScopeRef.current = "idle"
      return
    }

    if (previousScope !== "idle" && previousScope !== diaryScopeKey) {
      if (diary.trim()) setDiary("")
      if (showDiary) setShowDiary(false)
    }
    diaryScopeRef.current = diaryScopeKey
  }, [actionSubmissionInFlight, diary, diaryScopeKey, setDiary, setShowDiary, showDiary])

  useEffect(() => {
    if (!showDiary || diaryContext === "idle" || busy) return
    const focusDiaryTextarea = () => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      const node = diaryTextareaRef.current
      if (!node || node.disabled) return
      fitTextareaToContent(node)
      node.focus({ preventScroll: true })
      const cursor = node.value.length
      node.setSelectionRange(cursor, cursor)
      node.scrollIntoView({
        block: "nearest",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      })
    }
    const frame = window.requestAnimationFrame(focusDiaryTextarea)
    const timers = [90, 220].map((delay) => window.setTimeout(focusDiaryTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, diaryContext, showDiary])

  useEffect(() => {
    if (!showDiary || diaryContext === "idle") return
    const frame = window.requestAnimationFrame(() => {
      fitTextareaToContent(diaryTextareaRef.current)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [diary, diaryContext, showDiary])

  const renderDiaryAttachPreview = (context: "leverage" | "option" | "free") => {
    const isEditingThisContext = showDiary && diaryContext === context
    if (isEditingThisContext) {
      return null
    }
    const diaryAttachTitle = diaryDraft
      ? t("play.diary_attach_edit_title", { motive: diaryDraft })
      : t("play.diary_attach_add_title")

    if (!diaryDraft) {
      return (
        <button
          type="button"
          aria-label={diaryAttachTitle}
          title={diaryAttachTitle}
          style={{
            ...ppStyles.diaryAttachPreview,
            ...ppStyles.diaryAttachPreviewEmpty,
            ...inlineActionDisabledStyle,
          }}
          onClick={() => setShowDiary(true)}
          disabled={actionControlsDisabled}
        >
          <span style={ppStyles.diaryAttachEmptyCopy}>
            <span style={ppStyles.diaryAttachEmptyText}>{t("play.diary_attach_empty")}</span>
            <span style={ppStyles.diaryAttachEmptyHint}>{t("play.diary_attach_empty_hint")}</span>
          </span>
        </button>
      )
    }

    return (
      <button
        type="button"
        aria-label={diaryAttachTitle}
        title={diaryAttachTitle}
        style={{
          ...ppStyles.diaryAttachPreview,
          ...ppStyles.diaryAttachPreviewFilled,
          ...inlineActionDisabledStyle,
        }}
        onClick={() => setShowDiary(true)}
        disabled={actionControlsDisabled}
      >
        <span style={ppStyles.diaryAttachTag}>{t("play.diary_attached_label")}</span>
        <span style={ppStyles.diaryAttachText} title={diaryDraft}>{diaryPreview}</span>
        <span style={ppStyles.diaryAttachEdit}>
          {t("play.diary_lane_edit")}
        </span>
      </button>
    )
  }
  const renderDiaryEditor = (context: "leverage" | "option" | "free") => {
    const optionMotiveNeedsText = context === "option" && !diary.trim()
    const diarySubmitDisabled =
      actionControlsDisabled ||
      (context === "option" && selectedOptionIndex === null) ||
      optionMotiveNeedsText ||
      (context === "leverage" && !armedCard) ||
      (context === "free" && !freeInput.trim())
    const diaryPublicMove =
      context === "option"
        ? selectedOptionBody
        : context === "leverage"
          ? armedCardLeverage || (armedCardTargetName ? t("play.leverage_confirm_title", { target: armedCardTargetName }) : "")
          : freeInput.trim()
    const diarySubmitLabel =
      context === "leverage"
        ? t("play.leverage_confirm_cta")
        : context === "option" || (context === "free" && diaryDraft)
          ? t("play.inner_motive_submit_cta")
          : t("play.action_submit")

    return showDiary && diaryContext === context ? (
      <div
        style={ppStyles.diaryBox}
        data-play-inner-motive-panel={context === "option" ? "true" : undefined}
      >
        <div style={ppStyles.diaryHeader}>
          <span style={ppStyles.diaryKicker}>{t("play.diary_inner_label")}</span>
          <span style={ppStyles.diaryMeta}>{t("play.private_intent_hint")}</span>
        </div>
        <div
          style={ppStyles.diaryIntentFrame}
          data-play-inner-motive-frame={context === "option" ? "true" : undefined}
        >
          <span style={ppStyles.diaryIntentRow}>
            <span style={ppStyles.diaryIntentLabel}>{t("play.diary_public_move_label")}</span>
            <span style={ppStyles.diaryIntentText} title={diaryPublicMove}>
              {diaryPublicMove || t("play.diary_public_move_empty")}
            </span>
          </span>
          <span style={ppStyles.diaryIntentRow}>
            <span style={ppStyles.diaryIntentLabel}>{t("play.diary_private_motive_label")}</span>
            <span style={ppStyles.diaryIntentText}>
              {t("play.diary_private_motive_detail")}
            </span>
          </span>
        </div>
        <div
          style={ppStyles.diaryWritingHint}
          data-play-inner-motive-writing-hint={context === "option" ? "true" : undefined}
        >
          {t("play.diary_writing_hint")}
        </div>
        <textarea
          className="play-diary-textarea"
          ref={diaryTextareaRef}
          style={ppStyles.diaryTextarea}
          value={diary}
          placeholder={t("play.diary_placeholder")}
          aria-label={t("play.diary_inner_label")}
          aria-keyshortcuts="Meta+Enter Control+Enter Escape"
          title={`${t("play.shortcut_mod_enter_submit")} · ${t("play.shortcut_escape_cancel")}`}
          onChange={(e) => setDiary(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault()
              if (actionControlsDisabled) return
              const currentDiary = e.currentTarget.value
              setDiary(currentDiary)
              if (context === "option" && selectedOptionIndex !== null) {
                handleOptionCommit(selectedOptionIndex, currentDiary)
              } else if (context === "leverage" && armedCard) {
                handleLeverageReveal(armedCard, currentDiary)
              } else if (context === "free" && freeInput.trim()) {
                handleSubmitFreeWithReflect(currentDiary)
              }
            } else if (e.key === "Escape") {
              e.preventDefault()
              setShowDiary(false)
            }
          }}
          disabled={actionControlsDisabled}
          spellCheck={false}
          rows={2}
          maxLength={600}
        />
        {optionMotiveNeedsText ? (
          <span
            style={ppStyles.diaryDisabledReason}
            data-play-inner-motive-disabled-reason="true"
          >
            {t("play.inner_motive_submit_disabled_hint")}
          </span>
        ) : null}
        <div style={ppStyles.diaryActions}>
          <button
            style={{
              ...(context === "option" ? ppStyles.diarySubmitButton : ppStyles.actionPrimaryLine),
              ...(compactActionChrome && context !== "option" ? ppStyles.actionPrimaryLineCompact : null),
              ...(context !== "option" ? ppStyles.inlineCommitPrimaryActions : null),
              ...(diarySubmitDisabled ? ppStyles.actionPrimaryLineDisabled : null),
              ...(diarySubmitDisabled && context === "option" ? ppStyles.diarySubmitButtonDisabled : null),
            }}
            onClick={() => {
              const currentDiary = diary.trim()
              if (context === "option" && selectedOptionIndex !== null) {
                handleOptionCommit(selectedOptionIndex, currentDiary)
              } else if (context === "leverage" && armedCard) {
                handleLeverageReveal(armedCard, currentDiary)
              } else if (context === "free" && freeInput.trim()) {
                handleSubmitFreeWithReflect(currentDiary)
              }
            }}
            disabled={diarySubmitDisabled}
            aria-keyshortcuts="Meta+Enter Control+Enter"
            title={
              optionMotiveNeedsText
                ? t("play.inner_motive_submit_disabled_hint")
                : t("play.shortcut_mod_enter_submit")
            }
            type="button"
          >
            {diarySubmitLabel}
          </button>
          <button
            onClick={() => setShowDiary(false)}
            disabled={actionControlsDisabled}
            type="button"
            aria-keyshortcuts="Escape"
            title={t("play.shortcut_escape_cancel")}
            style={{
              ...ppStyles.diaryTextButton,
              ...inlineActionDisabledStyle,
            }}
          >
            {diaryDraft ? t("play.diary_keep") : t("play.diary_skip")}
          </button>
          {diaryDraft ? (
            <button
              onClick={() => {
                setShowDiary(false)
                setDiary("")
              }}
              disabled={actionControlsDisabled}
              type="button"
              style={{
                ...ppStyles.diaryTextButton,
                ...inlineActionDisabledStyle,
              }}
            >
              {t("play.diary_remove")}
            </button>
          ) : null}
        </div>
      </div>
    ) : null
  }
  const renderSelectedOptionConfirm = () =>
    selectedOption && selectedOptionParsed && selectedOptionIndex !== null && (pickedIndex === null || isOptionCommitPending) ? (
      <motion.div
        key={`option-confirm-${selectedOptionIndex}`}
        ref={setCommitFocusNode}
        style={{
          ...ppStyles.optionCardConfirmPanel,
          ...(isWritingOptionDiary ? ppStyles.optionCardConfirmPanelWriting : null),
          ...(reducedMotion ? ppStyles.reducedMotionTransition : null),
        }}
        data-play-action-card-confirm-panel="true"
        data-play-action-card-confirm-readable-label={selectedOptionConfirmReadableLabel}
        aria-label={selectedOptionConfirmReadableLabel}
        initial={reducedMotion ? false : { opacity: 0, y: -6 }}
        animate={reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
        exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: -4 }}
        transition={reducedMotion ? { duration: 0.01 } : { duration: 0.18, ease: [0.22, 0.61, 0.36, 1] }}
      >
        {isWritingOptionDiary ? null : (
          <div
            style={{
              ...ppStyles.optionCardConfirmRail,
              ...(compactActionChrome ? ppStyles.optionCardConfirmRailCompact : null),
            }}
          >
            <div
              style={{
                ...ppStyles.optionCardPrimaryRow,
                ...(compactActionChrome ? ppStyles.optionCardPrimaryRowCompact : null),
              }}
            >
              <SelectedMoveConfirmationReadout
                moveNumber={selectedOptionIndex + 1}
                targetName={selectedOptionTarget?.name ?? null}
                summary={selectedOptionSubmitSummary}
              />
              <div
                style={{
                  ...ppStyles.optionCardPrimaryActionGrid,
                  ...(compactActionChrome ? ppStyles.optionCardPrimaryActionGridCompact : null),
                }}
              >
                <motion.button
                  style={{
                    ...ppStyles.optionPrimaryCommitButton,
                    ...(compactActionChrome ? ppStyles.optionPrimaryCommitButtonCompact : null),
                    ...(actionControlsDisabled ? ppStyles.optionPrimaryCommitButtonDisabled : null),
                    ...(reducedMotion ? ppStyles.reducedMotionTransition : null),
                  }}
                  type="button"
                  data-play-action-card-confirm="true"
                  data-play-primary-commit="true"
                  aria-keyshortcuts="Enter"
                  title={t("play.shortcut_enter_submit")}
                  onClick={() => {
                    if (selectedOptionIndex !== null) {
                      handleOptionCommit(selectedOptionIndex)
                    }
                  }}
                  disabled={actionControlsDisabled}
                  whileHover={actionControlsDisabled || reducedMotion ? undefined : { y: -1, filter: "brightness(1.07)" }}
                  whileTap={actionControlsDisabled || reducedMotion ? undefined : { scale: 0.985, filter: "brightness(1.14)" }}
                  animate={
                    isOptionCommitPending && !reducedMotion
                      ? {
                          boxShadow: [
                            actionPalette.primaryPendingGlow,
                            actionPalette.primaryPendingGlowStrong,
                          ],
                        }
                      : undefined
                  }
                  transition={isOptionCommitPending && !reducedMotion ? { duration: 0.9, repeat: Infinity, repeatType: "mirror" } : undefined}
                >
                  <span style={ppStyles.optionPrimaryButtonLabel}>
                    {isOptionCommitPending ? t("play.action_busy") : t("play.selected_move_commit_cta")}
                  </span>
                  <span style={ppStyles.optionPrimaryButtonHint}>
                    {t("play.selected_move_commit_hint")}
                  </span>
                </motion.button>
                <motion.button
                  style={{
                    ...ppStyles.optionMotiveCommitButton,
                    ...(showDiary ? ppStyles.optionMotiveCommitButtonActive : null),
                    ...(compactActionChrome ? ppStyles.optionPrimaryCommitButtonCompact : null),
                    ...(actionControlsDisabled ? ppStyles.optionMotiveCommitButtonDisabled : null),
                    ...(reducedMotion ? ppStyles.reducedMotionTransition : null),
                  }}
                  type="button"
                  data-play-inner-motive-primary="true"
                  aria-expanded={showDiary && diaryContext === "option"}
                  title={diaryDraft ? t("play.diary_attach_edit_title", { motive: diaryDraft }) : t("play.diary_attach_add_title")}
                  onClick={() => setShowDiary(true)}
                  disabled={actionControlsDisabled}
                  whileHover={actionControlsDisabled || reducedMotion ? undefined : { y: -1, filter: "brightness(1.06)" }}
                  whileTap={actionControlsDisabled || reducedMotion ? undefined : { scale: 0.985, filter: "brightness(1.12)" }}
                >
                  <span style={ppStyles.optionMotiveButtonLabel}>
                    {diaryDraft ? t("play.inner_motive_edit_cta") : t("play.inner_motive_cta")}
                  </span>
                  <span style={ppStyles.optionMotiveButtonHint}>
                    {diaryDraft ? t("play.inner_motive_attached_hint") : t("play.inner_motive_button_hint")}
                  </span>
                </motion.button>
              </div>
            </div>
            {isOptionCommitPending || !diaryDraft ? null : (
              <div
                style={{
                  ...ppStyles.optionCardSecondaryRow,
                  ...(compactActionChrome ? ppStyles.optionCardSecondaryRowCompact : null),
                }}
                data-play-support-actions="true"
              >
                <span style={ppStyles.diaryAttachTag}>{t("play.diary_attached_label")}</span>
                <span style={ppStyles.diaryAttachText} title={diaryDraft}>{diaryPreview}</span>
              </div>
            )}
          </div>
        )}
        {renderDiaryEditor("option")}
      </motion.div>
    ) : null

  return (
    <motion.div
      data-play-action-area="true"
      data-play-action-state={actionState}
      data-play-action-collapse-zone="true"
      style={ppStyles.actionArea}
      onPointerDownCapture={handleActionAreaPointerDownCapture}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.08, ...itemTransition }}
    >
      <span style={ppStyles.srOnly} aria-live="polite" aria-atomic="true">
        {actionStatusLabel}
      </span>
      {showTurnGuide ? (
        <div
          style={{
            ...ppStyles.turnGuide,
            ...(turnGuide.tone ?? {}),
            ...(compactActionChrome ? ppStyles.turnGuideCompact : null),
          }}
          aria-label={t("play.turn_guide_kicker")}
          data-play-turn-guide="true"
        >
          <div style={ppStyles.turnGuideCopy}>
            <strong style={ppStyles.turnGuideTitle}>{turnGuide.title}</strong>
            <span style={ppStyles.turnGuideDetail} data-play-turn-guide-detail="true">{turnGuide.detail}</span>
          </div>
        </div>
      ) : null}

      {showLeverageRail ? (
        <section
          id={ACTION_LEVERAGE_RAIL_ID}
          data-play-leverage-rail="true"
          data-play-leverage-state={playableLeverageCards.length > 0 ? "playable" : "empty"}
          data-play-leverage-playable-count={playableLeverageCards.length}
          style={{
            ...ppStyles.leverageRail,
            ...(compactActionChrome ? ppStyles.leverageRailCompact : null),
          }}
          aria-label={t("play.leverage_rail_label")}
        >
          {playableLeverageCards.length === 0 ? (
            <LeverageEmptySummary
              title={leverageEmptyTitle}
              metaText={leverageEmptyMetaText}
              badge={leverageEmptyBadge}
            />
          ) : (
            <LeverageSummaryButton
              text={leverageSummaryText}
              metaText={leverageSummaryMetaText}
              showChips={!!primaryLeverageCard}
              chipTarget={leverageSummaryChipTarget}
              toggleText={leverageSummaryToggleText}
              expanded={showLeverageCards}
              compact={compactActionChrome}
              disabled={actionControlsDisabled}
              onActivate={handleLeverageSummaryActivate}
            />
          )}
          {showLeverageCardPicker ? (
            <div
              style={{
                ...ppStyles.leverageCardsRow,
                ...(compactLeverage ? ppStyles.leverageCardsRowCompact : null),
              }}
            >
              {playableLeverageCards.map((card) => {
                const isPrepared = armedCardId === card.card_id && !card.used
                const leverageCardTitle = `${t("play.leverage_card_target", { target: card.target_name })}: ${card.leverage}`
                return (
                  <button
                    key={card.card_id}
                    type="button"
                    data-play-leverage-card="true"
                    data-play-leverage-card-state={isPrepared ? "prepared" : "available"}
                    data-play-leverage-card-target={card.target_name}
                    style={{
                      ...ppStyles.leverageMiniCard,
                      ...(isPrepared ? ppStyles.leverageMiniCardArmed : null),
                      ...(card.used ? ppStyles.leverageMiniCardUsed : null),
                    }}
                    onClick={() => {
                      if (card.used || actionControlsDisabled) return
                      setSelectedOptionIndex(null)
                      setShowFreeInput(false)
                      onClearInventoryFocus?.()
                      setArmedCardId(isPrepared ? null : card.card_id)
                      if (compactLeverage && !isPrepared) {
                        setLeverageExpanded(false)
                      }
                    }}
                    disabled={actionControlsDisabled || card.used}
                    aria-pressed={isPrepared}
                    aria-label={leverageCardTitle}
                    title={leverageCardTitle}
                  >
                    <strong style={ppStyles.leverageMiniTarget} title={card.target_name}>{card.target_name}</strong>
                    <span style={ppStyles.leverageMiniActionHint}>
                      {isPrepared ? t("play.leverage_mini_prepared_hint") : t("play.leverage_mini_cta")}
                    </span>
                    <span
                      style={{
                        ...ppStyles.leverageMiniText,
                        ...(compactLeverage ? ppStyles.leverageMiniTextCompact : null),
                      }}
                      title={card.leverage}
                    >
                      {card.leverage}
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}
          {spentLeverageCards.length > 0 && playableLeverageCards.length > 0 ? (
            <div style={ppStyles.leverageSpentRow} aria-label={t("play.leverage_spent_group")}>
              <span style={ppStyles.leverageSpentLabel}>{t("play.leverage_spent_group")}</span>
              <span style={ppStyles.leverageSpentTargets} title={spentLeverageTargets}>
                {spentLeverageTargets}
              </span>
            </div>
          ) : null}
        </section>
      ) : null}

      {showStandardOptions && actorFocus ? (
        <div
          style={{
            ...ppStyles.actorFocusCue,
            ...(actorFocusMatchCount > 0 || actorFocusLeverageCard ? ppStyles.actorFocusCueMatched : ppStyles.actorFocusCueEmpty),
          }}
          data-play-actor-focus-cue="true"
          data-play-actor-focus-id={actorFocus.id}
          data-play-actor-focus-match-count={actorFocusMatchCount}
          data-play-actor-focus-leverage={actorFocusLeverageCard ? "true" : undefined}
          aria-label={`${t("play.actor_focus_label")}: ${actorFocus.name}. ${actorFocusDetail}`}
        >
          <span style={ppStyles.actorFocusCueHead} data-play-actor-focus-cue-head="true">
            <span style={ppStyles.actorFocusCueLabel}>{t("play.actor_focus_label")}</span>
            <strong style={ppStyles.actorFocusCueName}>
              {actorFocusMatchCount === 0
                ? actorFocusLeverageCard
                  ? t("play.actor_focus_leverage_label", { name: actorFocus.name })
                  : t("play.actor_focus_custom_label", { name: actorFocus.name })
                : t("play.actor_focus_showing_label", { name: actorFocus.name })}
            </strong>
          </span>
          {onClearActorFocus ? (
            <button
              type="button"
              style={{
                ...ppStyles.actorFocusCueClear,
                ...inlineActionDisabledStyle,
              }}
              onClick={onClearActorFocus}
              disabled={actionControlsDisabled}
              data-play-actor-focus-clear="true"
              aria-label={t("play.actor_focus_clear")}
              title={t("play.actor_focus_clear")}
            >
              {t("play.actor_focus_clear")}
            </button>
          ) : null}
          <span style={ppStyles.actorFocusCueDetail}>
            {actorFocusDetail}
          </span>
          {actorFocusMatchCount > 0 ? (
            <span
              style={ppStyles.actorFocusCueInstruction}
              data-play-actor-focus-instruction="true"
            >
              {t("play.actor_focus_instruction")}
            </span>
          ) : null}
          <span
            style={ppStyles.actorFocusCueFilterNote}
            data-play-actor-focus-filter-note="true"
          >
            {t("play.actor_focus_filter_note")}
          </span>
          {actorFocusMatchedMoves.length > 0 ? (
            <span
              style={ppStyles.actorFocusMatches}
              data-play-actor-focus-matches="true"
              aria-label={t("play.actor_focus_matches_label")}
            >
              <span style={ppStyles.actorFocusMatchesLabel}>
                {t("play.actor_focus_matches_label")}
              </span>
              {actorFocusMatchedMoves.map(({ index, label }) => (
                <button
                  key={`${index}-${label}`}
                  type="button"
                  style={ppStyles.actorFocusMatchChip}
                  onClick={() => handleOptionSelect(index)}
                  disabled={actionControlsDisabled}
                  title={label}
                  data-play-actor-focus-match-chip="true"
                  data-play-actor-focus-match-option-index={index}
                  aria-label={t("play.actor_focus_select_match", { move: label })}
                >
                  {truncateRecoveryText(label, 56)}
                </button>
              ))}
            </span>
          ) : null}
          {actorFocusMatchCount === 0 && showFreeActionToggle ? (
            <button
              type="button"
              style={{
                ...ppStyles.resourceFocusCueAction,
                ...inlineActionDisabledStyle,
              }}
              onClick={openFreeActionComposer}
              disabled={actionControlsDisabled}
              data-play-actor-focus-custom-move="true"
              aria-label={freeActionToggleTitle}
              title={freeActionToggleTitle}
            >
              {freeActionToggleText}
            </button>
          ) : null}
        </div>
      ) : null}

      {showStandardOptions && resourceFocus ? (
        <div
          style={{
            ...ppStyles.resourceFocusCue,
            ...(resourceFocusMatchCount > 0 ? ppStyles.resourceFocusCueMatched : ppStyles.resourceFocusCueEmpty),
          }}
          data-play-resource-focus-cue="true"
          data-play-resource-focus-id={resourceFocus.id}
          data-play-resource-focus-match-count={resourceFocusMatchCount}
          aria-label={`${t("play.resource_focus_label")}: ${resourceFocus.label}. ${resourceFocusDetail}`}
        >
          <span style={ppStyles.resourceFocusCueHead} data-play-resource-focus-cue-head="true">
            <span style={ppStyles.resourceFocusCueLabel}>{t("play.resource_focus_label")}</span>
            <strong style={ppStyles.resourceFocusCueName}>
              {t("play.resource_focus_showing_label", { name: resourceFocus.label })}
            </strong>
          </span>
          {onClearResourceFocus ? (
            <button
              type="button"
              style={{
                ...ppStyles.resourceFocusCueClear,
                ...inlineActionDisabledStyle,
              }}
              onClick={onClearResourceFocus}
              disabled={actionControlsDisabled}
              data-play-resource-focus-clear="true"
              aria-label={t("play.resource_focus_clear")}
              title={t("play.resource_focus_clear")}
            >
              {t("play.resource_focus_clear")}
            </button>
          ) : null}
          <span style={ppStyles.resourceFocusCueDetail}>{resourceFocusDetail}</span>
          {resourceFocusMatchCount > 0 ? (
            <span
              style={ppStyles.resourceFocusCueInstruction}
              data-play-resource-focus-instruction="true"
            >
              {t("play.resource_focus_instruction")}
            </span>
          ) : null}
          <span
            style={ppStyles.resourceFocusCueFilterNote}
            data-play-resource-focus-filter-note="true"
          >
            {t("play.resource_focus_filter_note")}
          </span>
          {resourceFocusMatchedMoves.length > 0 ? (
            <span
              style={ppStyles.resourceFocusMatches}
              data-play-resource-focus-matches="true"
              aria-label={t("play.resource_focus_matches_label")}
            >
              <span style={ppStyles.resourceFocusMatchesLabel}>
                {t("play.resource_focus_matches_label")}
              </span>
              {resourceFocusMatchedMoves.map(({ index, label }) => (
                <button
                  key={`${index}-${label}`}
                  type="button"
                  style={ppStyles.resourceFocusMatchChip}
                  onClick={() => handleOptionSelect(index)}
                  disabled={actionControlsDisabled}
                  title={label}
                  data-play-resource-focus-match-chip="true"
                  data-play-resource-focus-match-option-index={index}
                  aria-label={t("play.resource_focus_select_match", { move: label })}
                >
                  {truncateRecoveryText(label, 56)}
                </button>
              ))}
            </span>
          ) : null}
          {resourceFocusMatchCount === 0 && showFreeActionToggle ? (
            <button
              type="button"
              style={{
                ...ppStyles.resourceFocusCueAction,
                ...inlineActionDisabledStyle,
              }}
              onClick={openFreeActionComposer}
              disabled={actionControlsDisabled}
              data-play-resource-focus-custom-move="true"
              aria-label={freeActionToggleTitle}
              title={freeActionToggleTitle}
            >
              {freeActionToggleText}
            </button>
          ) : null}
        </div>
      ) : null}

      {armedCard ? (
          <section
            ref={setCommitFocusNode}
            data-play-leverage-reveal="true"
            data-play-leverage-reveal-target={armedCard.target_name}
            style={{
              ...ppStyles.leverageRevealPanel,
              ...(isRevealingLeverage ? ppStyles.leverageRevealPanelActive : null),
            }}
            aria-label={t("play.leverage_confirm_label")}
          >
            <div style={ppStyles.leverageRevealHeader}>
              <strong style={ppStyles.leverageRevealTitle}>
                {t("play.leverage_confirm_title", { target: armedCard.target_name })}
              </strong>
              <span style={ppStyles.leverageRevealHint}>
                {t("play.leverage_confirm_hint", { target: armedCard.target_name })}
              </span>
            </div>
            <div style={ppStyles.leverageRevealStatement}>
              <span style={ppStyles.leverageRevealEvidenceLabel}>
                {t("play.leverage_evidence_label")}
              </span>
              <div style={ppStyles.leverageRevealEvidence}>{armedCard.leverage}</div>
            </div>
            {isRevealingLeverage ? (
              <motion.div
                style={ppStyles.leverageRevealCeremony}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={transitions.snap}
                aria-live="polite"
              >
                {[
                  t("play.leverage_ceremony_exposed"),
                  t("play.leverage_ceremony_target", { target: armedCard.target_name }),
                  t("play.leverage_ceremony_room"),
                ].map((step, index) => (
                  <motion.span
                    key={step}
                    style={ppStyles.leverageRevealCeremonyStep}
                    initial={{ opacity: 0.35, y: 4 }}
                    animate={{ opacity: [0.42, 1, 0.78], y: [4, 0, 0] }}
                    transition={{
                      duration: 0.9,
                      delay: index * 0.12,
                      repeat: Infinity,
                      repeatDelay: 0.6,
                    }}
                  >
                    {index > 0 ? <span style={ppStyles.leverageRevealCeremonyDivider} aria-hidden>·</span> : null}
                    <span style={ppStyles.leverageRevealCeremonyText}>{step}</span>
                  </motion.span>
                ))}
              </motion.div>
            ) : null}
            {isWritingLeverageDiary ? null : (
              <div style={ppStyles.leverageRevealActions}>
                <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
                  <button
                    data-play-leverage-reveal-cta="true"
                    style={{
                      ...ppStyles.actionPrimaryLine,
                      ...(compactActionChrome ? ppStyles.actionPrimaryLineCompact : null),
                      ...(actionControlsDisabled ? ppStyles.actionPrimaryLineDisabled : null),
                    }}
                    type="button"
                    aria-keyshortcuts="Enter"
                    title={t("play.shortcut_enter_submit")}
                    onClick={() => handleLeverageReveal(armedCard)}
                    disabled={actionControlsDisabled}
                  >
                    {isRevealingLeverage ? t("play.leverage_revealing") : t("play.leverage_confirm_cta")}
                  </button>
                  {renderDiaryAttachPreview("leverage")}
                </div>
                <div
                  style={{
                    ...ppStyles.commitSecondaryActions,
                    ...ppStyles.inlineCommitSecondaryActions,
                    ...(compactActionChrome ? ppStyles.commitSecondaryActionsCompact : null),
                  }}
                >
                  <button
                    type="button"
                    style={{
                      ...ppStyles.commitTextButton,
                      ...inlineActionDisabledStyle,
                    }}
                    onClick={() => {
                      setArmedCardId(null)
                      setLeverageExpanded(hasMultiplePlayableLeverage)
                    }}
                    disabled={actionControlsDisabled}
                    aria-keyshortcuts={hasMultiplePlayableLeverage ? undefined : "Escape"}
                    title={hasMultiplePlayableLeverage ? t("play.leverage_confirm_choose_another") : t("play.shortcut_escape_cancel")}
                  >
                    {leverageConfirmCancelText}
                  </button>
                </div>
              </div>
            )}
            {renderDiaryEditor("leverage")}
          </section>
        ) : null}

      {showStandardOptions ? (
        <>
          <div
            style={{
              ...ppStyles.optionsList,
              ...(compactActionChrome ? ppStyles.optionsListCompact : null),
            }}
          >
            {options.length === 0 ? (
              <div style={ppStyles.noOptions}>
                {t("play.action_no_options")}
              </div>
            ) : (
              visibleOptionEntries.map(({ opt, i }) => {
                const parsed = parseOptionLabel(opt.label)
                const isSelected = selectedOptionIndex === i
                const isPicked = pickedIndex === i
                const isUnpicked = pickedIndex !== null && pickedIndex !== i
                const optionForecasts = actionForecasts?.[i] ?? []
                const actionTarget = optionTargets[i] ?? null
                const optionIntentGuide = parsed.tag
                  ? {
                      tag: parsed.tag,
                      description: optionTagGuide(parsed.tag, t),
                    }
                  : null
                const isActorFocusMatch = actorFocusOptionMatches[i] ?? false
                const isActorFocusDimmed = Boolean(actorFocus && actorFocusMatchCount > 0 && !isActorFocusMatch)
                const isResourceFocusMatch = resourceFocusOptionMatches[i] ?? false
                const isResourceFocusDimmed = Boolean(resourceFocus && resourceFocusMatchCount > 0 && !isResourceFocusMatch)
                const optionShortcutKey = i < 9 ? String(i + 1) : null
                const isChoiceDimmed =
                  selectedOptionIndex !== null && !isSelected && pickedIndex === null
                const showRecentImpactHint =
                  hasRecentImpact && !!opt.hint && !isSelected && optionForecasts.length === 0
                return (
                  <div key={i} style={ppStyles.optionChoiceShell}>
                    <motion.button
                      style={{
                        ...ppStyles.optionBtn,
                        ...(compactActionChrome ? ppStyles.optionBtnCompact : null),
                        // While picked: highlight the chosen one (gold border),
                        // fade the unchosen ones harder than busy default.
                        ...(isSelected && pickedIndex === null ? ppStyles.optionBtnSelected : null),
                        ...(isSelected && pickedIndex === null ? ppStyles.optionBtnExpanded : null),
                        ...(isChoiceDimmed ? ppStyles.optionBtnDeemphasized : null),
                        ...(isActorFocusMatch ? ppStyles.optionBtnActorFocusMatch : null),
                        ...(isActorFocusDimmed ? ppStyles.optionBtnActorFocusDimmed : null),
                        ...(isResourceFocusMatch ? ppStyles.optionBtnResourceFocusMatch : null),
                        ...(isResourceFocusDimmed ? ppStyles.optionBtnResourceFocusDimmed : null),
                        ...(isPicked ? ppStyles.optionBtnPicked : null),
                        ...(reducedMotion ? ppStyles.reducedMotionTransition : null),
                        opacity: isUnpicked
                          ? 0.28
                          : actionControlsDisabled && !isPicked
                            ? 0.5
                            : isChoiceDimmed
                              ? 0.54
                              : isActorFocusDimmed
                                ? 0.66
                                : isResourceFocusDimmed
                                  ? 0.66
                                  : 1,
                        pointerEvents: actionControlsDisabled ? "none" : "auto",
                      }}
                      onClick={() => handleOptionSelect(i)}
                      disabled={actionControlsDisabled}
                      type="button"
                      data-play-action-option-card="true"
                      data-play-selected-move={isSelected ? "true" : undefined}
                      data-play-action-card-expanded={isSelected ? "true" : undefined}
                      data-play-action-actor-focus-match={isActorFocusMatch ? "true" : undefined}
                      data-play-action-actor-focus-dimmed={isActorFocusDimmed ? "true" : undefined}
                      data-play-action-resource-focus-match={isResourceFocusMatch ? "true" : undefined}
                      data-play-action-resource-focus-dimmed={isResourceFocusDimmed ? "true" : undefined}
                      aria-pressed={isSelected}
                      aria-expanded={isSelected}
                      aria-keyshortcuts={optionShortcutKey ?? undefined}
                      title={
                        optionShortcutKey
                          ? t("play.option_shortcut_title", { key: optionShortcutKey })
                          : undefined
                      }
                      layout={reducedMotion ? false : "position"}
                      whileHover={
                        actionControlsDisabled || reducedMotion
                          ? undefined
                          : {
                              y: isSelected ? -1 : -2,
                              filter: "brightness(1.05)",
                            }
                      }
                      whileTap={actionControlsDisabled || reducedMotion ? undefined : { scale: 0.994 }}
                      transition={reducedMotion ? { duration: 0.01 } : { type: "spring", stiffness: 300, damping: 28 }}
                    >
                      <div
                        style={{
                          ...ppStyles.optionLabel,
                          ...(compactActionChrome ? ppStyles.optionLabelCompact : null),
                        }}
                      >
                        {/* Number key hint — visual cue that pressing the
                            digit picks this option. Lives on the leading
                            edge so it reads as "shortcut: 1, then this
                            action." Hidden on the small handful of options
                            beyond 9 (we cap at the first 9 for sanity). */}
                        {optionShortcutKey ? (
                          <kbd
                            style={ppStyles.optionKbd}
                            aria-label={t("play.option_shortcut_title", { key: optionShortcutKey })}
                          >
                            {optionShortcutKey}
                          </kbd>
                        ) : null}
                        <span
                          style={ppStyles.optionTitleLine}
                          data-play-action-card-title="true"
                        >
                          {parsed.tag ? (
                            <span
                              style={{
                                ...ppStyles.optionTagChip,
                                ...optionTagStyle(parsed.tag),
                              }}
                              data-play-action-card-intent="true"
                              aria-label={optionIntentGuide?.description}
                              title={optionIntentGuide?.description}
                            >
                              {parsed.tag}
                            </span>
                          ) : null}
                          <span
                            style={ppStyles.optionActionText}
                            data-play-action-card-body="true"
                        >
                          {parsed.body}
                        </span>
                        {actionTarget && !isSelected ? (
                          <span
                            style={ppStyles.optionTargetChip}
                            data-play-action-target-chip="true"
                            data-play-action-target-id={actionTarget.id}
                            aria-label={t("play.action_target_title", { name: actionTarget.name })}
                            title={t("play.action_target_title", { name: actionTarget.name })}
                          >
                            <span style={ppStyles.optionTargetLabel}>{t("play.action_target_label")}</span>
                            {" "}
                            <span style={ppStyles.optionTargetName}>{actionTarget.name}</span>
                          </span>
                        ) : null}
                      </span>
                        {opt.hint && !isSelected && optionForecasts.length === 0 ? (
                          showRecentImpactHint ? (
                            <span
                              style={{
                                ...ppStyles.optionOpenedByChange,
                                ...(compactActionChrome ? ppStyles.optionOpenedByChangeCompact : null),
                              }}
                              data-play-option-opened-by-change="true"
                              title={opt.hint}
                            >
                              <span style={ppStyles.optionOpenedByChangeLabel}>
                                {t("play.option_opened_by_change_label")}
                              </span>
                              <span style={ppStyles.optionOpenedByChangeText}>{opt.hint}</span>
                            </span>
                          ) : (
                            <span
                              style={{
                                ...ppStyles.optionHintInline,
                                ...(compactActionChrome ? ppStyles.optionHintInlineCompact : null),
                              }}
                              title={opt.hint}
                            >
                              {opt.hint}
                            </span>
                          )
                        ) : null}
                        {optionForecasts.length && !isSelected ? (
                          <span
                            style={ppStyles.gameplayDecisionForecastShell}
                            data-gameplay-action-forecast="true"
                          >
                            <ActionCollapsedForecast chips={optionForecasts} />
                          </span>
                        ) : null}
                        <span
                          style={{
                            ...ppStyles.optionExpandCue,
                            ...(isSelected ? ppStyles.optionExpandCueActive : null),
                          }}
                          data-play-action-card-select-cue="true"
                        >
                          {isSelected ? t("play.selected_move_kicker") : t("play.option_expand_cta")}
                        </span>
                        {isSelected ? (
                          <ActionSelectedOptionDetail
                            hint={opt.hint ?? ""}
                            forecasts={optionForecasts}
                            target={actionTarget}
                            intentGuide={optionIntentGuide}
                            compact={compactActionChrome ?? undefined}
                            reducedMotion={reducedMotion ?? undefined}
                          />
                        ) : null}
                      </div>
                    </motion.button>
                    <AnimatePresence initial={false}>
                      {isSelected && (pickedIndex === null || (isPicked && showPickedReflection)) ? renderSelectedOptionConfirm() : null}
                    </AnimatePresence>
                  </div>
                )
              })
            )}
          </div>
        </>
      ) : null}

      {/* Turn resolving echo — confirms the just-submitted move while
          the LLM composes the next beat. It stays typographic so the
          wait reads as narration, not another panel inside the story. */}
      <AnimatePresence>
        {showPickedReflection && busy ? (
          <ResolvingTurnPanel
            moveTag={resolvingMoveTag}
            moveText={resolvingMoveText}
            privateIntent={diaryDraft}
            target={resolvingTarget}
            commitmentSignals={resolvingCommitmentSignals}
            isFinalTurn={isFinalTurn}
          />
        ) : null}
      </AnimatePresence>

      {showFreeActionSurface ? (
        showFreeComposer ? (
          <div
            ref={setCommitFocusNode}
            style={ppStyles.freeInputBox}
          >
            {freeActionFocusContext ? (
              <FreeActionContextBanner context={freeActionFocusContext} />
            ) : null}
            <FreeActionStarterRows
              starters={freeActionStarterMoves}
              disabled={actionControlsDisabled}
              onUseStarter={setFreeInput}
            />
            <textarea
              className="play-free-textarea"
              data-play-free-action-input="true"
              ref={freeTextareaRef}
              style={ppStyles.freeTextarea}
              value={freeInput}
              placeholder={freeTextareaPlaceholder}
              aria-label={t("play.free_action_title")}
              aria-keyshortcuts={freeTextareaKeyShortcuts}
              title={freeTextareaTitle}
              onChange={(e) => setFreeInput(e.target.value)}
              onKeyDown={(e) => {
                // Cmd/Ctrl + Enter submits — the standard "send" pattern
                // for any modern textarea input. Plain Enter still
                // line-breaks because the input is multi-line drama.
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  if (!freeInput.trim() || actionControlsDisabled) return
                  e.preventDefault()
                  handleSubmitFreeWithReflect()
                } else if (e.key === "Escape" && options.length > 0) {
                  e.preventDefault()
                  setShowFreeInput(false)
                  onClearInventoryFocus?.()
                  if (!freeInput.trim()) {
                    setFreeInput("")
                  }
                }
              }}
              disabled={actionControlsDisabled}
              spellCheck={false}
              autoFocus
              rows={2}
            />
            <div style={ppStyles.freeBoundaryHint} data-play-free-action-boundary="true">
              {t("play.free_action_boundary_hint")}
            </div>
            {isWritingFreeDiary ? null : (
              <div
                style={{
                  ...ppStyles.freeCommitDock,
                  ...(compactActionChrome ? ppStyles.freeCommitDockCompact : null),
                }}
              >
                <div ref={setFreeActionNode} style={ppStyles.freeInputActions}>
                  {freeActionDraft ? (
                    <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
                      <button
                        style={{
                          ...ppStyles.freeSubmitButton,
                          ...(actionControlsDisabled ? ppStyles.freeSubmitButtonDisabled : null),
                        }}
                        onClick={() => handleSubmitFreeWithReflect()}
                        disabled={actionControlsDisabled}
                        data-play-free-action-submit="true"
                        aria-keyshortcuts="Meta+Enter Control+Enter"
                        title={t("play.shortcut_mod_enter_submit")}
                        type="button"
                      >
                        {actionControlsDisabled ? t("play.action_busy") : t("play.action_submit")}
                      </button>
                      {renderDiaryAttachPreview("free")}
                    </div>
                  ) : (
                    <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
                      <span style={ppStyles.freeEmptyHint}>{t("play.free_empty_hint")}</span>
                    </div>
                  )}
                  <div
                    style={{
                      ...ppStyles.commitSecondaryActions,
                      ...ppStyles.inlineCommitSecondaryActions,
                      ...(compactActionChrome ? ppStyles.commitSecondaryActionsCompact : null),
                    }}
                  >
                    {options.length > 0 ? (
                      <button
                        style={{
                          ...ppStyles.commitTextButton,
                          ...inlineActionDisabledStyle,
                        }}
                        onClick={() => {
                          setShowFreeInput(false)
                          onClearInventoryFocus?.()
                          if (!freeActionDraft) {
                            setFreeInput("")
                          }
                        }}
                        disabled={actionControlsDisabled}
                        type="button"
                        aria-keyshortcuts="Escape"
                        title={t("play.shortcut_escape_cancel")}
                      >
                        {freeActionDraft ? t("play.action_hide_free") : t("play.action_cancel")}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            )}
            {freeActionDraft ? renderDiaryEditor("free") : null}
          </div>
        ) : null
      ) : null}

      {showAlternateFreeActionToggle ? (
        <div style={ppStyles.alternateActionRow}>
          {showAlternateFreeActionToggle ? (
            <button
              style={{
                ...ppStyles.alternateActionButton,
                ...inlineActionDisabledStyle,
              }}
              onClick={openFreeActionComposer}
              disabled={actionControlsDisabled}
              aria-label={freeActionToggleTitle}
              title={freeActionToggleTitle}
              type="button"
              data-play-free-action-toggle="true"
            >
              <span style={ppStyles.alternateActionLabel}>{freeActionToggleText}</span>
              <span style={ppStyles.alternateActionHint}>{freeActionToggleHint}</span>
            </button>
          ) : null}
        </div>
      ) : null}

      {showActionTelemetry ? (
        <SceneReadStrip
          clocks={sceneClocks}
          pulses={latestNpcPulses}
          castNameById={castNameById}
        />
      ) : null}
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
