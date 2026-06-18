import { type CSSProperties, type PointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion, useReducedMotion, type TargetAndTransition } from "motion/react"
import type {
  NarrativeAdvisorMessage,
  NarrativeAgentEvent,
  NarrativeAgentEventPayload,
  NarrativeAgentPlan,
  NarrativeContractJudgeResult,
  NarrativeEnding,
  NarrativeLLMCallEvent,
  NarrativeNPCPulse,
  NarrativePlayedLeverageCard,
  NarrativeStepJudgeResult,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import { useApi } from "../../../app/api-context"
import { Truncated } from "../../../shared/ui/truncated"
import { friendlyError } from "../../../shared/lib/friendly-error"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../../shared/lib/i18n"
import {
  cascadeDelay,
  fadeTransition,
  fadeVariants,
  hoverLift,
  hoverNudge,
  itemTransition,
  itemVariants,
  labelChipSpring,
  pulseVariants,
  slideInRightTransition,
  slideInRightVariants,
  tapPress,
  transitions,
} from "../../../shared/lib/motion-presets"
import {
  getAvatarForCastMember,
  getEndingIllustration,
  getTierSplash,
} from "../../../shared/lib/webtoon-assets"
import { actionPalette, ppStyles } from "../play-styles"
import type { GameplayActionForecast } from "../play-gameplay-envelope"
import type { ActionCommitmentSummary, LeverageCardView, PlayAdvanceAction } from "../play-types"
import { useCompactLayout } from "../hooks/use-compact-layout"

const ACTION_LEVERAGE_RAIL_ID = "play-leverage-rail"

type DecisionForecastGroup = "cost" | "upside" | "shift"

type SceneParallaxOffset = {
  x: number
  y: number
}

function SceneParallaxBanner({ sceneUrl }: { sceneUrl: string }) {
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
      style={ppStyles.beatSceneBanner}
      onPointerMove={handlePointerMove}
      onPointerLeave={resetOffset}
      onPointerCancel={resetOffset}
      data-play-segment-parallax="true"
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

function fitTextareaToContent(node: HTMLTextAreaElement | null) {
  if (!node) return
  node.style.height = "auto"
  node.style.height = `${node.scrollHeight}px`
}

export function buildAdvisorSuggestions({
  story,
  lastNarrator,
  leverageCards,
  turnsRemaining,
}: {
  story: NarrativeStoryHistoryResponse
  lastNarrator: NarrativeStoryMessage | null
  leverageCards: LeverageCardView[]
  turnsRemaining: number
}): string[] {
  const language = story.template.language
  const cast = story.template.cast
  const openLeverage = leverageCards.find((card) => !card.used)
  const fallbackName = language === "zh" ? "对方" : "the other side"
  const castById = new Map(cast.map((member) => [member.character_id, member.display_name]))
  const playerRole = story.session.player_role
  const isLikelyPlayerCast = (member: NarrativeStoryHistoryResponse["template"]["cast"][number]): boolean => {
    const relation = member.relation_to_protagonist.toLowerCase()
    const roleText = `${playerRole?.label ?? ""} ${playerRole?.public_persona ?? ""}`.toLowerCase()
    if (relation.includes("you are") || relation.includes("主角") || relation.includes("玩家")) return true
    return Boolean(roleText && `${member.role} ${member.relation_to_protagonist}`.toLowerCase().includes(roleText))
  }
  const pulseTarget = (lastNarrator?.npc_pulse ?? [])
    .map((pulse) => {
      const member = cast.find((item) => item.character_id === pulse.npc_id)
      return member && !isLikelyPlayerCast(member) ? castById.get(pulse.npc_id) : null
    })
    .find((name): name is string => Boolean(name))
  const focalNpc =
    pulseTarget ??
    openLeverage?.target_name ??
    cast.find((member) => !isLikelyPlayerCast(member))?.display_name ??
    cast[1]?.display_name ??
    cast[0]?.display_name ??
    fallbackName
  const hasRiskyOption = Boolean(lastNarrator?.options.some((option) => /risk|风险/i.test(option.hint ?? "")))
  const suggestions: string[] = []

  if (language === "zh") {
    suggestions.push(`${focalNpc} 现在真正想从我这里得到什么？`)
    suggestions.push(hasRiskyOption ? "哪一个选择最不容易翻车？" : "我下一步该稳住谁？")
    if (openLeverage) {
      suggestions.push(`我什么时候该亮出 ${openLeverage.target_name} 的把柄？`)
    } else {
      suggestions.push("谁是现在最值得施压的人？")
    }
    if (turnsRemaining <= 3) {
      suggestions.push(`只剩 ${turnsRemaining} 回合了，怎么收成一个强结局？`)
    }
    return suggestions.slice(0, 4)
  }

  suggestions.push(`What does ${focalNpc} want from me right now?`)
  suggestions.push(hasRiskyOption ? "Which choice is least likely to backfire?" : "Who should I stabilize next?")
  if (openLeverage) {
    suggestions.push(`When should I reveal the leverage over ${openLeverage.target_name}?`)
  } else {
    suggestions.push("Who is most worth pressuring next?")
  }
  if (turnsRemaining <= 3) {
    suggestions.push(`Only ${turnsRemaining} turns left. How do I land a strong ending?`)
  }
  return suggestions.slice(0, 4)
}

type FailedActionRecovery = {
  kicker: string
  title: string
  detail: string
  chips: string[]
}

function truncateRecoveryText(value: string, max = 64): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

export function buildFailedActionRecovery({
  action,
  options,
  castNameById,
  t,
}: {
  action: PlayAdvanceAction | null
  options: NarrativeStoryMessage["options"]
  castNameById: Record<string, string>
  t: ReturnType<typeof useT>
}): FailedActionRecovery | null {
  if (!action) return null
  const chips: string[] = []
  if (action.diary?.trim()) {
    chips.push(t("play.recovery_private_attached"))
  }

  if (action.played_leverage) {
    const target = castNameById[action.played_leverage.npc_id] ?? action.played_leverage.npc_id
    chips.unshift(t("play.recovery_chip_target", { target }))
    chips.push(t("play.recovery_chip_evidence", {
      evidence: truncateRecoveryText(action.played_leverage.leverage),
    }))
    return {
      kicker: t("play.recovery_kicker"),
      title: t("play.recovery_leverage_title"),
      detail: t("play.recovery_leverage_detail"),
      chips,
    }
  }

  if (action.free_input?.trim()) {
    chips.unshift(t("play.recovery_chip_move", {
      move: truncateRecoveryText(action.free_input),
    }))
    return {
      kicker: t("play.recovery_kicker"),
      title: t("play.recovery_free_title"),
      detail: t("play.recovery_free_detail"),
      chips,
    }
  }

  if (action.chosen_option_index != null) {
    const option = options[action.chosen_option_index]
    if (option) {
      chips.unshift(t("play.recovery_chip_choice", {
        choice: truncateRecoveryText(option.label),
      }))
    }
    return {
      kicker: t("play.recovery_kicker"),
      title: t("play.recovery_option_title"),
      detail: t("play.recovery_option_detail"),
      chips,
    }
  }

  return null
}

export function RunContextPanel({
  story,
  turnsCompleted,
  turnBudget,
  turnsRemaining,
  liveInventory,
  leverageCards,
  isComplete,
}: {
  story: NarrativeStoryHistoryResponse
  turnsCompleted: number
  turnBudget: number
  turnsRemaining: number
  liveInventory: string[]
  leverageCards: LeverageCardView[]
  isComplete: boolean
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
  const runProgressLabel = t("stage_bar.aria", {
    turn: turnsCompleted,
    total: turnBudget,
    stage,
  })
  const runProgressPercent = Math.max(
    0,
    Math.min(100, (turnsCompleted / Math.max(turnBudget, 1)) * 100),
  )
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
              <span>{item}</span>
            </span>
          ))}
          {hiddenInventoryCount > 0 ? (
            <span style={ppStyles.runInventoryMore}>
              {t("play.run_assets_more", { count: hiddenInventoryCount })}
            </span>
          ) : null}
        </span>
      </div>
    ) : null
  const renderRunProgress = () =>
    !isComplete ? (
      <span
        style={ppStyles.runProgressTrack}
        role="progressbar"
        aria-label={runProgressLabel}
        aria-valuemin={0}
        aria-valuemax={turnBudget}
        aria-valuenow={turnsCompleted}
      >
        <span
          style={{
            ...ppStyles.runProgressFill,
            width: `${runProgressPercent}%`,
          }}
        />
      </span>
    ) : null

  if (compactRunContext) {
    return (
      <motion.section
        style={{ ...ppStyles.runContextPanel, ...ppStyles.runContextPanelCompact }}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={itemTransition}
        aria-label={t("play.run_context_label")}
      >
        <div style={ppStyles.runCompactHeader}>
          <span style={ppStyles.runCompactRoleTag}>{t("play.run_identity_prefix")}</span>
          <Truncated style={ppStyles.runCompactRoleTitle}>
            {role?.label ?? story.template.title}
          </Truncated>
          <span style={ppStyles.runCompactMeta}>{runMetaText}</span>
        </div>
        {role ? (
          <div style={ppStyles.runCompactObjective}>
            <strong style={ppStyles.runCompactObjectiveText}>
              {role.hidden_objective}
            </strong>
          </div>
        ) : null}
        {renderInventoryLine()}
        {renderRunProgress()}
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
    >
      <div style={ppStyles.runContextHeader}>
        <span style={ppStyles.runKicker}>{t("play.run_identity_prefix")}</span>
        <Truncated style={ppStyles.runRoleTitle}>
          {role?.label ?? story.template.title}
        </Truncated>
        <span style={ppStyles.runContextMeta}>{runMetaText}</span>
      </div>
      {role ? (
        <div style={ppStyles.runContextObjectiveLine}>
          <strong style={ppStyles.runContextObjectiveText}>{role.hidden_objective}</strong>
        </div>
      ) : null}
      {renderInventoryLine()}
      {renderRunProgress()}
    </motion.section>
  )
}

export function RuntimeInspector({
  story,
  ending,
  lastNarrator,
  turnsRemaining,
  liveInventory,
  agentPlan,
  agentEvents,
  llmEvents,
  agentTraceAccessGranted,
}: {
  story: NarrativeStoryHistoryResponse
  ending: NarrativeEnding | null
  lastNarrator: NarrativeStoryMessage | null
  turnsRemaining: number
  liveInventory: string[]
  agentPlan: NarrativeAgentPlan | null
  agentEvents: NarrativeAgentEvent[]
  llmEvents: NarrativeLLMCallEvent[]
  agentTraceAccessGranted: boolean
}) {
  const { lang } = useLanguage()
  const t = useT()
  const playerTurns = story.messages.filter((m) => m.role === "player").length
  const endingLabel = ending
    ? displayEndingLabel(ending.label, lang)
    : story.session.ending_label
      ? displayEndingLabel(story.session.ending_label, lang)
      : t("play.runtime_pending")
  const inventoryState =
    liveInventory.length === 1
      ? t("play.status_item_one")
      : t("play.status_item_many", { count: liveInventory.length })
  const latestStepJudge = latestJudgeFromEvents<NarrativeStepJudgeResult>(
    agentEvents,
    "step_judge",
    "step_judge.v1",
  )
  const latestContractJudge = latestJudgeFromEvents<NarrativeContractJudgeResult>(
    agentEvents,
    "contract_judge",
    "contract_judge.v1",
  )
  const criteria = evaluationCriteria({
    agentPlan,
    latestStepJudge,
    latestContractJudge,
    lastNarrator,
  })
  const trajectory = trajectoryEvidence(agentEvents)
  const latestStatus = worstStatus([
    latestStepJudge?.status ?? "missing",
    latestContractJudge?.status ?? "missing",
  ])
  const score = evaluationScore(criteria)
  const reasonCategory = evaluationReasonCategory(latestStepJudge, latestContractJudge, llmEvents)
  const latestEvidence = evaluationObservedEvidence(latestStepJudge, latestContractJudge, lastNarrator)
  const telemetryRows = llmEvents.slice(-8).reverse()
  const traceRows = agentPlan
    ? [
        { label: "Turn", value: `ord ${agentPlan.narrator_ord} · ${agentPlan.turn_index}/${agentPlan.turn_budget}` },
        { label: "Stage", value: `${agentPlan.director.stage_phase} · ${agentPlan.director.expected_pressure}` },
        { label: "Intent", value: agentIntentSummary(agentPlan, "none") },
        { label: "Twist", value: agentTwistSummary(agentPlan, "none") },
        { label: "Memory", value: agentMemorySummary(agentPlan) },
        { label: "Move", value: agentActionSummary(agentPlan, "none") },
        { label: "Impact", value: agentImpactSummary(lastNarrator, "pending") },
      ]
    : []

  return (
    <motion.section
      style={ppStyles.runtimeInspector}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={itemTransition}
      aria-label="Evaluation evidence"
      data-play-primitive="EvaluationDrawer"
      data-reviewer-evidence="true"
    >
      <div style={ppStyles.runtimeInspectorHeader}>
        <span style={ppStyles.runtimeInspectorKicker}>Reviewer only</span>
        <strong>Evaluation evidence</strong>
      </div>
      <div style={ppStyles.evaluationHero}>
        <div style={ppStyles.evaluationVerdictBlock}>
          <span style={ppStyles.evaluationLabel}>Latest step</span>
          <strong style={ppStyles.evaluationVerdict} data-evaluation-verdict={latestStatus}>
            {latestStatus}
          </strong>
        </div>
        <div style={ppStyles.evaluationScoreBlock}>
          <span style={ppStyles.evaluationLabel}>Score</span>
          <strong style={ppStyles.evaluationScore}>{score}/100</strong>
        </div>
      </div>
      <div style={ppStyles.evaluationReasonRow}>
        <span style={ppStyles.runtimeInspectorRowLabel}>Reason category</span>
        <strong style={ppStyles.agentTraceValue}>{reasonCategory}</strong>
      </div>
      <div style={ppStyles.evaluationEvidenceQuote}>{latestEvidence}</div>

      <section style={ppStyles.evaluationSection}>
        <span style={ppStyles.evaluationSectionTitle}>Score points</span>
        <div style={ppStyles.evaluationCriteriaGrid}>
          {criteria.map((row) => (
            <div
              key={row.criterion}
              style={ppStyles.evaluationCriterionRow}
              data-evaluation-criterion={row.criterion}
              data-evaluation-status={row.status}
            >
              <div style={ppStyles.evaluationCriterionTopline}>
                <strong>{row.criterion}</strong>
                <span style={ppStyles.evaluationStatus}>{row.status}</span>
              </div>
              <span style={ppStyles.evaluationCriterionEvidence}>{row.evidence}</span>
              <span style={ppStyles.evaluationCriterionRationale}>{row.rationale}</span>
            </div>
          ))}
        </div>
      </section>

      <section style={ppStyles.evaluationSection}>
        <span style={ppStyles.evaluationSectionTitle}>Trajectory</span>
        <div style={ppStyles.trajectoryTrack} data-evaluation-trajectory="true">
          {trajectory.turns.length ? trajectory.turns.map((turn) => (
            <span
              key={turn.ord}
              title={turn.label}
              style={{
                ...ppStyles.trajectoryDot,
                ...(turn.status === "pass"
                  ? ppStyles.trajectoryDotPass
                  : turn.status === "warn"
                    ? ppStyles.trajectoryDotWarn
                    : turn.status === "fail"
                      ? ppStyles.trajectoryDotFail
                      : ppStyles.trajectoryDotMissing),
              }}
              data-trajectory-status={turn.status}
            >
              {turn.turn}
            </span>
          )) : (
            <span style={ppStyles.agentTraceEmpty}>
              {agentTraceAccessGranted ? "No judged turns yet." : "Reviewer access not granted."}
            </span>
          )}
        </div>
        <div style={ppStyles.evaluationReasonRow}>
          <span style={ppStyles.runtimeInspectorRowLabel}>Trajectory trend</span>
          <strong style={ppStyles.agentTraceValue}>{trajectory.summary}</strong>
        </div>
      </section>

      <section style={ppStyles.evaluationSection}>
        <span style={ppStyles.evaluationSectionTitle}>Telemetry</span>
        {telemetryRows.length ? (
          <div style={ppStyles.telemetryList}>
            {telemetryRows.map((event) => (
              <div
                key={event.event_id}
                style={ppStyles.telemetryRow}
                data-telemetry-operation={event.operation}
              >
                <strong style={ppStyles.telemetryOperation}>{shortOperation(event.operation)}</strong>
                <span style={ppStyles.telemetryMeta}>
                  {event.source_label} · {event.status} · {event.latency_ms ?? event.operation_latency_ms ?? "?"}ms
                </span>
                <span style={ppStyles.telemetryTokens}>
                  in {tokenValue(event.input_tokens)} · cache {tokenValue(event.cached_input_tokens)} · out {tokenValue(event.output_tokens)} · total {tokenValue(event.total_tokens)}
                </span>
                {event.retry_count || event.repair_count || event.fallback_reason ? (
                  <span style={ppStyles.telemetryMeta}>
                    retry {event.retry_count} · repair {event.repair_count}
                    {event.fallback_reason ? ` · ${event.fallback_reason}` : ""}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <span style={ppStyles.agentTraceEmpty}>
            {agentTraceAccessGranted ? "No LLM call events for this session yet." : "Reviewer access not granted."}
          </span>
        )}
      </section>

      {traceRows.length ? (
        <details style={ppStyles.agentTraceDetails}>
          <summary style={ppStyles.runtimeInspectorDetailsSummary}>
            Agent trace summary
          </summary>
          <div style={ppStyles.agentTraceGrid}>
            {traceRows.map((row) => (
              <div style={ppStyles.agentTraceRow} key={row.label}>
                <span style={ppStyles.runtimeInspectorRowLabel}>{row.label}</span>
                <strong style={ppStyles.agentTraceValue} title={row.value}>{row.value}</strong>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <div style={ppStyles.evaluationFooter}>
        Session {story.session.turn_count}/{story.session.turn_budget} · {inventoryState} · ending {endingLabel} · {turnsRemaining} left
      </div>
    </motion.section>
  )
}

export function latestAgentPlanFromEvents(events?: NarrativeAgentEvent[]): NarrativeAgentPlan | null {
  if (!events || events.length === 0) return null
  const planEvents = events.filter((event) => event.event_type === "agent_plan")
  if (planEvents.length === 0) return null
  const latest = [...planEvents].sort((a, b) => {
    if (a.ord !== b.ord) return a.ord - b.ord
    return a.event_index - b.event_index
  }).at(-1)
  const payload = latest?.payload
  return payload?.schema_version === "agent_plan.v1" ? payload : null
}

function latestJudgeFromEvents<T extends NarrativeStepJudgeResult | NarrativeContractJudgeResult>(
  events: NarrativeAgentEvent[],
  eventType: NarrativeAgentEvent["event_type"],
  schemaVersion: T["schema_version"],
): T | null {
  const judgeEvents = events.filter((event) => event.event_type === eventType)
  if (judgeEvents.length === 0) return null
  const latest = [...judgeEvents].sort((a, b) => {
    if (a.ord !== b.ord) return a.ord - b.ord
    return a.event_index - b.event_index
  }).at(-1)
  const payload: NarrativeAgentEventPayload | undefined = latest?.payload
  return payload?.schema_version === schemaVersion ? payload as T : null
}

type EvaluationStatus = "pass" | "warn" | "fail" | "missing"

type EvaluationCriterion = {
  criterion: string
  status: EvaluationStatus
  evidence: string
  rationale: string
}

type TrajectoryTurnEvidence = {
  ord: number
  turn: number
  status: EvaluationStatus
  label: string
}

function evaluationCriteria({
  agentPlan,
  latestStepJudge,
  latestContractJudge,
  lastNarrator,
}: {
  agentPlan: NarrativeAgentPlan | null
  latestStepJudge: NarrativeStepJudgeResult | null
  latestContractJudge: NarrativeContractJudgeResult | null
  lastNarrator: NarrativeStoryMessage | null
}): EvaluationCriterion[] {
  const stepStatus = latestStepJudge?.status ?? "missing"
  const contractStatus = latestContractJudge?.status ?? "missing"
  const stepCodes = new Set(latestStepJudge?.violations.map((v) => v.code) ?? [])
  const contractCodes = new Set(latestContractJudge?.violations.map((v) => v.code) ?? [])
  const hasImpact = Boolean(
    (lastNarrator?.npc_pulse ?? []).some((pulse) => pulse.shift !== "steady") ||
      (lastNarrator?.inventory_delta?.added.length ?? 0) > 0 ||
      (lastNarrator?.inventory_delta?.removed.length ?? 0) > 0,
  )
  const optionsPlayable =
    contractCodes.has("options_count_invalid") || contractCodes.has("option_label_missing")
      ? "fail"
      : lastNarrator && lastNarrator.options.length > 0
        ? "pass"
        : "missing"
  const entityStatus = [...contractCodes].some((code) => code.startsWith("unknown_"))
    ? "fail"
    : contractStatus === "missing"
      ? "missing"
      : "pass"
  const unsafeStatus = contractCodes.has("hidden_info_leak") ? "fail" : contractStatus === "missing" ? "missing" : "pass"
  const consequenceStatus =
    stepCodes.has("played_leverage_no_observable_impact") ||
    stepCodes.has("twist_turn_no_consequence") ||
    stepCodes.has("expected_pressure_not_observed") ||
    contractCodes.has("stage_contract_no_consequence")
      ? "warn"
      : hasImpact
        ? "pass"
        : stepStatus
  return [
    {
      criterion: "player agency preserved",
      status: lastNarrator?.options.length ? "pass" : "missing",
      evidence: lastNarrator?.options.length ? `${lastNarrator.options.length} next moves visible` : "no current option evidence",
      rationale: "The turn leaves the player with playable next actions.",
    },
    {
      criterion: "consequence follows move",
      status: consequenceStatus,
      evidence: agentImpactSummary(lastNarrator, "no pulse or inventory delta observed"),
      rationale: latestStepJudge?.summary ?? "Step Judge has not been archived yet.",
    },
    {
      criterion: "Brief contract honored",
      status: contractStatus,
      evidence: firstViolationEvidence(latestContractJudge) || "contract check clear",
      rationale: latestContractJudge?.summary ?? "Contract Judge has not been archived yet.",
    },
    {
      criterion: "entities remain coherent",
      status: entityStatus,
      evidence: [...contractCodes].filter((code) => code.startsWith("unknown_")).join(", ") || "no unknown ids",
      rationale: "Runtime ids and visible references stay inside the persisted cast/session contract.",
    },
    {
      criterion: "tone/profile respected",
      status: stepCodes.has("expected_pressure_not_observed") ? "warn" : stepStatus,
      evidence: agentPlan ? `${agentPlan.director.stage_phase} · ${agentPlan.director.expected_pressure}` : "no AgentPlan evidence",
      rationale: "The turn is compared against the director pressure and phase expectation.",
    },
    {
      criterion: "options are playable",
      status: optionsPlayable,
      evidence: `${lastNarrator?.options.length ?? 0} option(s)`,
      rationale: "The current narrator beat must expose usable next moves.",
    },
    {
      criterion: "unsafe/out-of-spec drift avoided",
      status: unsafeStatus,
      evidence: contractCodes.has("hidden_info_leak") ? "hidden_info_leak" : "no hidden-info or out-of-contract leak",
      rationale: "Reviewer evidence checks for hidden-info leakage and invalid runtime shape.",
    },
    {
      criterion: "trajectory advances",
      status: agentPlan ? "pass" : "missing",
      evidence: agentPlan ? `turn ${agentPlan.turn_index}/${agentPlan.turn_budget}` : "no turn plan yet",
      rationale: "The run has a concrete turn index, stage, and remaining budget.",
    },
  ]
}

function trajectoryEvidence(events: NarrativeAgentEvent[]): { turns: TrajectoryTurnEvidence[]; summary: string } {
  const byOrd = new Map<number, { step?: EvaluationStatus; contract?: EvaluationStatus }>()
  for (const event of events) {
    const bucket = byOrd.get(event.ord) ?? {}
    if (event.event_type === "step_judge" && event.payload.schema_version === "step_judge.v1") {
      bucket.step = event.payload.status
    }
    if (event.event_type === "contract_judge" && event.payload.schema_version === "contract_judge.v1") {
      bucket.contract = event.payload.status
    }
    byOrd.set(event.ord, bucket)
  }
  const turns = [...byOrd.entries()]
    .sort(([a], [b]) => a - b)
    .map(([ord, row], index) => {
      const status = worstStatus([row.step ?? "missing", row.contract ?? "missing"])
      return {
        ord,
        turn: index + 1,
        status,
        label: `turn ${index + 1}: step ${row.step ?? "missing"} · contract ${row.contract ?? "missing"}`,
      }
    })
  const counts = turns.reduce<Record<EvaluationStatus, number>>((acc, turn) => {
    acc[turn.status] += 1
    return acc
  }, { pass: 0, warn: 0, fail: 0, missing: 0 })
  const overall = worstStatus(turns.map((turn) => turn.status))
  return {
    turns,
    summary: turns.length
      ? `${overall} · ${turns.length} judged turn(s) · pass ${counts.pass} / warn ${counts.warn} / fail ${counts.fail}`
      : "missing · no judged turns yet",
  }
}

function worstStatus(statuses: EvaluationStatus[]): EvaluationStatus {
  if (statuses.includes("fail")) return "fail"
  if (statuses.includes("warn")) return "warn"
  if (statuses.includes("missing")) return "missing"
  return "pass"
}

function evaluationScore(rows: EvaluationCriterion[]): number {
  if (!rows.length) return 0
  const score = rows.reduce((sum, row) => {
    if (row.status === "pass") return sum + 100
    if (row.status === "warn") return sum + 68
    if (row.status === "fail") return sum + 35
    return sum + 0
  }, 0) / rows.length
  return Math.round(score)
}

function evaluationReasonCategory(
  step: NarrativeStepJudgeResult | null,
  contract: NarrativeContractJudgeResult | null,
  llmEvents: NarrativeLLMCallEvent[],
): string {
  const firstCode = step?.violations[0]?.code ?? contract?.violations[0]?.code
  if (firstCode) return taxonomyForCode(firstCode)
  const recovery = [...llmEvents].reverse().find((event) =>
    event.fallback_reason || event.status === "repaired" || event.status === "fallback_used",
  )
  if (recovery) return recovery.status === "repaired" ? "invalid_output_recovered" : "latency_recovery"
  if (step || contract) return "clear"
  return "pending"
}

function taxonomyForCode(code: string): string {
  if (code.includes("unknown") || code.includes("npc")) return "entity_mismatch"
  if (code.includes("option")) return "option_unplayable"
  if (code.includes("pressure") || code.includes("stage")) return "brief_drift"
  if (code.includes("leverage") || code.includes("consequence") || code.includes("inventory")) return "weak_consequence"
  if (code.includes("hidden") || code.includes("leak")) return "safety_redirect"
  return "runtime_invariant"
}

function evaluationObservedEvidence(
  step: NarrativeStepJudgeResult | null,
  contract: NarrativeContractJudgeResult | null,
  lastNarrator: NarrativeStoryMessage | null,
): string {
  const violationEvidence = firstViolationEvidence(step) || firstViolationEvidence(contract)
  if (violationEvidence) return violationEvidence
  const impact = agentImpactSummary(lastNarrator, "")
  if (impact) return impact
  return "Awaiting the next judged narrator turn."
}

function firstViolationEvidence(result: NarrativeStepJudgeResult | NarrativeContractJudgeResult | null): string {
  if (!result || result.violations.length === 0) return ""
  const violation = result.violations[0]
  const evidence = violation.evidence[0] ? ` · ${violation.evidence[0]}` : ""
  return `${violation.code}${evidence}`
}

function shortOperation(operation: string): string {
  return operation.replace(/^create\./, "").replace(/^narrative\./, "")
}

function tokenValue(value: number | null | undefined): string {
  return value == null ? "unknown" : String(value)
}

function agentIntentSummary(plan: NarrativeAgentPlan, emptyLabel: string): string {
  if (plan.npc_intents.length === 0) {
    if (plan.director.active_npc_ids.length === 0) return emptyLabel
    return plan.director.active_npc_ids.join(", ")
  }
  return plan.npc_intents
    .map((intent) => {
      const who = intent.display_name || intent.npc_id
      const what = intent.intent_brief || intent.intent
      return `${who}: ${what}`
    })
    .join(" · ")
}

function agentTwistSummary(plan: NarrativeAgentPlan, emptyLabel: string): string {
  if (plan.director.twist_kind) return plan.director.twist_kind
  if (plan.twist_directive?.["kind"]) return plan.twist_directive["kind"]
  return emptyLabel
}

function agentMemorySummary(plan: NarrativeAgentPlan): string {
  const memory = plan.memory
  const pulseCount = Object.keys(memory.npc_pulse_trend).length
  const unusedLeverageCount = memory.unused_leverage.length
  const played = memory.played_leverage["card_id"]
    ? `${memory.played_leverage["npc_id"] ?? "npc"}:${memory.played_leverage["action"] ?? "played"}`
    : "none"
  return `pulse ${pulseCount} · unused leverage ${unusedLeverageCount} · inventory ${memory.current_inventory_count} · played ${played}`
}

function agentActionSummary(plan: NarrativeAgentPlan, emptyLabel: string): string {
  const action = plan.memory.last_player_action
  const leverage = action["played_leverage_card"]
  if (leverage && typeof leverage === "object") {
    const card = leverage as Record<string, unknown>
    const target = typeof card["npc_id"] === "string" ? card["npc_id"] : "npc"
    const move = typeof card["action"] === "string" ? card["action"] : "played"
    return `leverage ${move} -> ${target}`
  }
  const chosen = action["chosen_label"]
  if (typeof chosen === "string" && chosen.trim()) {
    return truncateRecoveryText(chosen, 96)
  }
  const content = action["content"]
  if (typeof content === "string" && content.trim()) {
    return truncateRecoveryText(content, 96)
  }
  return emptyLabel
}

function agentJudgeSummary(
  result: NarrativeStepJudgeResult | NarrativeContractJudgeResult | null,
  pendingLabel: string,
): string {
  if (!result) return pendingLabel
  const codes = result.violations.map((violation) => violation.code).slice(0, 3)
  return codes.length > 0 ? `${result.status} · ${codes.join(", ")}` : `${result.status} · clear`
}

function agentImpactSummary(message: NarrativeStoryMessage | null, pendingLabel: string): string {
  if (!message) return pendingLabel
  const pulseCount = message.npc_pulse?.length ?? 0
  const added = message.inventory_delta?.added.length ?? 0
  const removed = message.inventory_delta?.removed.length ?? 0
  const delta = added || removed ? `inventory +${added}/-${removed}` : "inventory steady"
  return `pulse ${pulseCount} · ${delta}`
}

function stageDisplayName(stage: string): string {
  if (stage === "hook") return "Prelude"
  if (stage === "pressure") return "Build"
  if (stage === "reversal") return "Turn"
  if (stage === "climax") return "Climax"
  if (stage === "pre_finale" || stage === "pre_finale_open") return "Coda"
  return stage.replace(/_/g, " ")
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

export function EndingScreen({
  ending,
  sessionId,
  templateId,
  messages,
  bookmarkedOrds,
  shareCopied,
  onShare,
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
        {/* Illustrated banner — the visual punctuation that makes the
            ending feel like a closed object the player can screenshot. */}
        <motion.div
          initial={initialOr({ opacity: 0, scale: 1.06 })}
          animate={{ opacity: 1, scale: 1 }}
          transition={transitions.slow}
          style={{
            ...ppStyles.endingHero,
            backgroundImage: `${tv.gradient}, url(${illustration})`,
          }}
        >
          {tierSplash ? (
            <motion.div
              initial={initialOr({ opacity: 0, scale: 1.12 })}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: delayOr(0.25), ...transitions.ceremony }}
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

        <motion.div
          initial={initialOr({ opacity: 0, y: 8 })}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: delayOr(1.7), ...itemTransition }}
          style={ppStyles.endingActions}
        >
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
        </div>
      </motion.div>
    </motion.section>
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
  pickedHandle,
  pickedActionText,
  isLatestNarrator,
  hasFollowingPlayerEcho,
  isBookmarked,
  onToggleBookmark,
}: {
  message: NarrativeStoryMessage
  previousPlayerMessage?: NarrativeStoryMessage
  castNameById?: Record<string, string>
  intensity?: "calm" | "rising" | "peak"
  sceneUrl?: string
  /** When this player message was an option pick, the option's
   *  readable label/tag. Used so players can remember exactly
   *  which action they committed. */
  pickedHandle?: string
  pickedActionText?: string
  isLatestNarrator?: boolean
  hasFollowingPlayerEcho?: boolean
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
    const delta = message.inventory_delta
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
    const showLatestDigestInventory = hasDelta && latestDigestPulses.length === 0
    const showLatestBeatDigest =
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
          ...(isBookmarked ? ppStyles.narratorBeatBookmarked : null),
        }}
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
          <SceneParallaxBanner sceneUrl={sceneUrl} />
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
        <div style={textStyle}>{message.content}</div>
        {showLatestBeatDigest ? (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08, ...itemTransition }}
            style={ppStyles.latestBeatDigest}
            aria-label={latestDigestA11yLabel}
            data-play-latest-beat-digest="true"
          >
            <span style={ppStyles.latestBeatDigestLabel}>
              {t("play.latest_beat_digest_label")}
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
        {outcomeItems.length > 0 ? (
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

export function computeLiveInventory(
  startingAssets: string[],
  messages: NarrativeStoryMessage[],
): string[] {
  const inv: string[] = [...startingAssets]
  for (const msg of messages) {
    if (msg.role !== "narrator" || !msg.inventory_delta) continue
    for (const added of msg.inventory_delta.added) {
      inv.push(added)
    }
    for (const removed of msg.inventory_delta.removed) {
      const target = removed.toLowerCase()
      for (let i = 0; i < inv.length; i += 1) {
        const item = inv[i]?.toLowerCase() ?? ""
        if (item && (item.includes(target) || target.includes(item))) {
          inv.splice(i, 1)
          break
        }
      }
    }
  }
  return inv
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
  const delta = message.inventory_delta
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

// Parse an option label that may start with an intent tag like "[挑拨] xxx".
// Returns { tag: "挑拨", body: "xxx" } or { tag: null, body: full label }.
// Used so the UI can render the tag as a colored chip + the action body
// as plain text, giving players a visual scan-tag for what the choice
// means before reading the full action.
export function parseOptionLabel(label: string): { tag: string | null; body: string } {
  const m = label.match(/^\s*[\[【]([^\]】]{1,8})[\]】]\s*(.*)$/)
  if (m) {
    return { tag: m[1].trim(), body: (m[2] ?? "").trim() }
  }
  return { tag: null, body: label }
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
  if (tag === "挑拨" || tag === "硬刚" || tag === "Provoke" || tag === "Confront") return ACTIVE_HOT
  if (tag === "反将" || tag === "合作" || tag === "Counter" || tag === "Ally") return ACTIVE_TEAL
  if (tag === "试探" || tag === "Probe") return ACTIVE_PURPLE
  // 妥协 / 观望 / 示弱 / Yield / Watch / Submit / unknown → PASSIVE
  return PASSIVE
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
  const lanes = [read.publicMove, read.privateIntent, read.reaction].filter(Boolean)
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.14, ...itemTransition }}
      style={ppStyles.intentReadReceipt}
      aria-label={t("play.intent_read_label")}
    >
      <span style={ppStyles.intentReadKicker}>{t("play.intent_read_label")}</span>
      <span style={ppStyles.intentReadSentence}>
        {lanes.map((lane, index) => (
          <span key={`${index}:${lane}`} style={ppStyles.intentReadPhrase}>
            {index > 0 ? <span style={ppStyles.intentReadDivider} aria-hidden>·</span> : null}
            <strong style={ppStyles.intentReadLaneValue}>{lane}</strong>
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

function displayEndingLabel(label: string, lang: ReturnType<typeof useLanguage>["lang"]): string {
  const translated = ENDING_LABEL_DISPLAY[lang]?.[label]
  if (translated) return translated
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase())
}

type OutcomeReceiptTone = "safe" | "neutral" | "tense" | "danger" | "gold"

type OutcomeReceiptItem = {
  label: string
  value: string
  tone?: OutcomeReceiptTone
}

type SceneClockView = {
  label: string
  value: string
}

function buildSceneClocks({
  turnsCompleted,
  turnsRemaining,
  turnBudget,
  latestNpcPulses,
  leverageCards,
  t,
}: {
  turnsCompleted: number
  turnsRemaining: number
  turnBudget: number
  latestNpcPulses: NarrativeNPCPulse[]
  leverageCards: LeverageCardView[]
  t: ReturnType<typeof useT>
}): SceneClockView[] {
  const clocks: SceneClockView[] = [
    {
      label: t("play.clock_time_label"),
      value: t("play.clock_time_value", { current: turnsCompleted, total: turnBudget }),
    },
  ]

  if (latestNpcPulses.length > 0) {
    const scoreByShift: Record<NarrativeNPCPulse["shift"], number> = {
      warmer: 0.45,
      steady: 0.85,
      colder: 1.65,
      wary: 2.35,
      broken: 3,
    }
    const pressureScore = latestNpcPulses.reduce(
      (sum, pulse) => sum + scoreByShift[pulse.shift],
      0,
    )
    const pressureProgress = Math.min(1, pressureScore / (latestNpcPulses.length * 3))
    const hasBroken = latestNpcPulses.some((pulse) => pulse.shift === "broken")
    const hasWary = latestNpcPulses.some((pulse) => pulse.shift === "wary")
    const hasColder = latestNpcPulses.some((pulse) => pulse.shift === "colder")
    const heatIsCritical =
      hasBroken || pressureProgress >= 0.78
    const heatIsRising =
      hasWary || hasColder || pressureProgress >= 0.55
    const heatValue =
      heatIsCritical
        ? t("play.clock_heat_critical")
        : heatIsRising
          ? t("play.clock_heat_rising")
          : t("play.clock_heat_stable")
    clocks.push({
      label: t("play.clock_heat_label"),
      value: heatValue,
    })
  }

  if (leverageCards.length > 0) {
    const spentCount = leverageCards.filter((card) => card.used).length
    clocks.push({
      label: t("play.clock_leverage_label"),
      value: t("play.clock_leverage_value", {
        used: spentCount,
        total: leverageCards.length,
      }),
    })
  }

  return clocks
}

function SceneReadStrip({
  clocks,
  pulses,
  castNameById,
}: {
  clocks: SceneClockView[]
  pulses: NarrativeNPCPulse[]
  castNameById: Record<string, string>
}) {
  const t = useT()
  const notablePulses = [...pulses]
    .sort((a, b) => outcomePriority(b.shift) - outcomePriority(a.shift))
    .slice(0, 2)
  if (clocks.length === 0 && notablePulses.length === 0) return null

  return (
    <div style={ppStyles.sceneReadStrip} aria-label={t("play.scene_read_label")}>
      <span style={ppStyles.sceneReadLabel}>{t("play.scene_read_label")}</span>
      <span style={ppStyles.sceneReadItems}>
        {clocks.slice(0, 3).map((clock) => (
          <span key={`${clock.label}:${clock.value}`} style={ppStyles.sceneReadItem}>
            <span style={ppStyles.sceneReadName}>{clock.label}</span>
            <span style={ppStyles.sceneReadJoiner} aria-hidden>:</span>
            <strong style={ppStyles.sceneReadValue}>{clock.value}</strong>
          </span>
        ))}
        {notablePulses.map((pulse) => {
          const name = castNameById[pulse.npc_id] ?? pulse.npc_id
          return (
            <span key={`${pulse.npc_id}:${pulse.shift}:${pulse.state}`} style={ppStyles.sceneReadItem}>
              <span style={ppStyles.sceneReadName}>{name}</span>
              <span style={ppStyles.sceneReadJoiner} aria-hidden>:</span>
              <strong style={ppStyles.sceneReadValue}>{pulseDeltaLabel(pulse.shift, t)}</strong>
            </span>
          )
        })}
      </span>
    </div>
  )
}

function ResolvingTurnPanel({
  moveTag,
  moveText,
  privateIntent,
  target,
}: {
  moveTag?: string
  moveText: string
  privateIntent?: string
  target?: string
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
    { id: "update", label: t("play.feedback_pending_update_label"), state: "waiting" },
  ] as const
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
      </div>
      <div style={ppStyles.roomReactingPanel} data-play-room-reacting="true">
        <span style={ppStyles.roomReactingRail} aria-hidden />
        <span style={ppStyles.roomReactingCopy}>
          <span style={ppStyles.resolvingStatus}>{resolveStatus}</span>
          <strong style={ppStyles.roomReactingTitle}>{t("play.room_reacting_title")}</strong>
          <span style={ppStyles.resolvingProgressText}>{progressCopy}</span>
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
      </div>
    </motion.div>
  )
}

function findActionTarget(
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

type GameplayResourceFocusId = "time" | "pressure" | "evidence"

function isResourceFocusAction(
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
      ? t("play.resource_focus_time_match_detail", { count: matchCount })
      : t("play.resource_focus_time_no_match")
  }
  if (resourceId === "pressure") {
    return matchCount > 0
      ? t("play.resource_focus_pressure_match_detail", { count: matchCount })
      : t("play.resource_focus_pressure_no_match")
  }
  return matchCount > 0
    ? t("play.resource_focus_evidence_match_detail", { count: matchCount })
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
  actorFocus,
  resourceFocus,
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
  actorFocus?: { id: string; name: string } | null
  resourceFocus?: { id: GameplayResourceFocusId; label: string } | null
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
    turnsRemaining,
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
      ? primaryLeverageCard.target_name
      : playableLeverageTargetText || t("play.leverage_summary_count", { count: playableLeverageCards.length })
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

  useEffect(() => {
    if (busy) return
    if (!commitmentSurfaceOpen) return
    const frame = window.requestAnimationFrame(() => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      commitFocusRef.current?.scrollIntoView({
        block: "center",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [busy, commitmentSurfaceOpen])

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

  const actionSubmissionInFlight = pickedIndex !== null || submittedFree || isRevealingLeverage
  const actionControlsDisabled = busy || actionSubmissionInFlight
  const inlineActionDisabledStyle = actionControlsDisabled ? ppStyles.inlineActionDisabled : null
  const showPickedReflection = actionSubmissionInFlight
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
  const resourceFocusOptionMatches = useMemo(() => {
    if (!resourceFocus) return options.map(() => false)
    return options.map((opt, index) => {
      const parsed = parseOptionLabel(opt.label)
      return isResourceFocusAction(resourceFocus.id, parsed.body, opt.hint, actionForecasts?.[index] ?? [])
    })
  }, [actionForecasts, options, resourceFocus])
  const resourceFocusMatchCount = resourceFocusOptionMatches.filter(Boolean).length
  const resourceFocusDetail = resourceFocus ? resourceFocusDetailText(t, resourceFocus.id, resourceFocusMatchCount) : ""
  const freeActionFocusContext = actorFocus && actorFocusMatchCount === 0
    ? {
        kind: "actor" as const,
        id: actorFocus.id,
        label: actorFocus.name,
        detail: t("play.free_context_actor_detail", { name: actorFocus.name }),
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
      : null
  const freeActionDraft = freeInput.trim()
  const freeActionReady = freeActionDraft.length > 0
  const freeActionTarget = freeActionDraft
    ? findActionTarget(freeActionDraft, undefined, castNameById, latestNpcPulses)
    : null
  const freeActionTargetName = freeActionTarget?.name ?? ""
  const freeActionContextTargetName =
    freeActionFocusContext?.kind === "actor" ? freeActionFocusContext.label : ""
  const freeActionTargetNameForFeedback = freeActionContextTargetName || freeActionTargetName
  const freeActionSubmittedText =
    freeActionDraft && freeActionContextTargetName && freeActionTargetName !== freeActionContextTargetName
      ? `${freeActionContextTargetName} — ${freeActionDraft}`
      : freeActionDraft
  const freeComposerOpen = showFreeInput || options.length === 0
  const selectedOptionGuideTitle = selectedOptionParsed?.tag
    ? t("play.turn_guide_selected_named_title", { tag: selectedOptionParsed.tag })
    : t("play.turn_guide_selected_title")
  const selectedOptionGuideDetail = selectedOptionParsed?.body
    ? t("play.turn_guide_selected_named_detail", {
        action: truncateRecoveryText(selectedOptionParsed.body, 72),
      })
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
                  title: t("play.turn_guide_idle_title"),
                  detail: playableLeverageCards.length > 0
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
  const showLeverageRail = (leverageCards.length > 0 || roleHasNoLeverage) && !commitmentSurfaceOpen
  const showFreeActionToggle =
    showFreeActionSurface &&
    !showFreeInput &&
    options.length > 0
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
  const diaryDraft = diary.trim()
  const diaryPreview =
    diaryDraft.length > 130 ? `${diaryDraft.slice(0, 127)}...` : diaryDraft
  const selectedOptionBody = selectedOptionParsed?.body ?? ""
  const selectedOptionHint = selectedOption?.hint ?? ""
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
      : `${turnGuide.title}. ${turnGuide.detail}`
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
        block: "center",
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
    const diarySubmitDisabled =
      actionControlsDisabled ||
      (context === "option" && selectedOptionIndex === null) ||
      (context === "leverage" && !armedCard) ||
      (context === "free" && !freeInput.trim())

    return showDiary && diaryContext === context ? (
      <div
        style={ppStyles.diaryBox}
        data-play-inner-motive-panel={context === "option" ? "true" : undefined}
      >
        <div style={ppStyles.diaryHeader}>
          <span style={ppStyles.diaryKicker}>{t("play.diary_inner_label")}</span>
          <span style={ppStyles.diaryMeta}>{t("play.private_intent_hint")}</span>
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
            title={t("play.shortcut_mod_enter_submit")}
            type="button"
          >
            {context === "leverage"
              ? t("play.leverage_confirm_cta")
              : context === "option"
                ? t("play.inner_motive_submit_cta")
                : t("play.action_submit")}
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
        aria-label={t("play.selected_move_aria")}
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
              <span style={ppStyles.optionCardConfirmMeta}>
                {t("play.selected_move_number", { index: selectedOptionIndex + 1 })}
              </span>
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
                  {isOptionCommitPending ? t("play.action_busy") : t("play.selected_move_commit_cta")}
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

  const decisionForecastLabelForGroup = useCallback((group: DecisionForecastGroup) => {
    if (group === "cost") return t("play.gameplay_decision_cost_label")
    if (group === "upside") return t("play.gameplay_decision_upside_label")
    return t("play.gameplay_decision_shift_label")
  }, [t])

  const decisionForecastGroupForChip = useCallback((chip: GameplayActionForecast): DecisionForecastGroup => {
    if (chip.tone === "cost") return "cost"
    if (chip.tone === "gain" || chip.tone === "unlock") return "upside"
    return "shift"
  }, [])

  const renderDecisionForecast = useCallback((
    chips: GameplayActionForecast[],
    options?: { compact?: boolean; detail?: boolean },
  ) => {
    if (!chips.length) return null
    const groups: Array<{ id: DecisionForecastGroup; chips: GameplayActionForecast[] }> = [
      { id: "cost" as DecisionForecastGroup, chips: chips.filter((chip) => decisionForecastGroupForChip(chip) === "cost") },
      { id: "upside" as DecisionForecastGroup, chips: chips.filter((chip) => decisionForecastGroupForChip(chip) === "upside") },
      { id: "shift" as DecisionForecastGroup, chips: chips.filter((chip) => decisionForecastGroupForChip(chip) === "shift") },
    ].filter((group) => group.chips.length > 0)

    return (
      <span
        style={{
          ...ppStyles.gameplayDecisionForecast,
          ...(options?.compact ? ppStyles.gameplayDecisionForecastCompact : null),
          ...(options?.detail ? ppStyles.gameplayDecisionForecastDetail : null),
        }}
        data-gameplay-decision-forecast="true"
        aria-label={t("play.gameplay_decision_forecast_label")}
      >
        <span style={ppStyles.gameplayDecisionForecastHeader}>
          {t("play.gameplay_decision_forecast_label")}
        </span>
        <span
          style={{
            ...ppStyles.gameplayDecisionGroups,
            ...(options?.compact ? ppStyles.gameplayDecisionGroupsCompact : null),
          }}
        >
          {groups.map((group) => (
            <span
              key={group.id}
              style={{
                ...ppStyles.gameplayDecisionGroup,
                ...(group.id === "cost"
                  ? ppStyles.gameplayDecisionGroupCost
                  : group.id === "upside"
                    ? ppStyles.gameplayDecisionGroupUpside
                    : ppStyles.gameplayDecisionGroupShift),
              }}
              data-gameplay-decision-group={group.id}
            >
              <span style={ppStyles.gameplayDecisionGroupLabel}>
                {decisionForecastLabelForGroup(group.id)}
              </span>
              <span style={ppStyles.gameplayDecisionChipRow}>
                {group.chips.map((chip) => (
                  <span
                    key={`${group.id}-${chip.label}`}
                    title={chip.detail ? `${chip.label}: ${chip.detail}` : chip.label}
                    aria-label={chip.detail ? `${chip.label}: ${chip.detail}` : chip.label}
                    style={{
                      ...ppStyles.gameplayForecastChip,
                      ...(chip.tone === "gain"
                        ? ppStyles.gameplayToneGain
                        : chip.tone === "cost"
                          ? ppStyles.gameplayToneCost
                          : chip.tone === "unlock"
                            ? ppStyles.gameplayToneUnlock
                            : {}),
                    }}
                    data-gameplay-forecast-chip="normal-play"
                  >
                    {chip.label}
                  </span>
                ))}
              </span>
            </span>
          ))}
        </span>
      </span>
    )
  }, [decisionForecastGroupForChip, decisionForecastLabelForGroup, t])

  const renderSelectedOptionDetail = (
    hint: string,
    forecasts: GameplayActionForecast[],
    target?: { id: string; name: string } | null,
  ) => {
    const forecastDetails = forecasts.filter((chip) => chip.detail)
    return (
      <motion.span
        style={{
          ...ppStyles.optionExpandedDetail,
          ...(compactActionChrome ? ppStyles.optionExpandedDetailCompact : null),
          ...(reducedMotion ? ppStyles.reducedMotionTransition : null),
        }}
        data-play-action-card-detail="true"
        initial={reducedMotion ? false : { opacity: 0, y: -4 }}
        animate={reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
        exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: -3 }}
        transition={reducedMotion ? { duration: 0.01 } : { duration: 0.16, ease: [0.22, 0.61, 0.36, 1] }}
      >
        <span
          style={{
            ...ppStyles.optionExpandedDetailSection,
            ...(compactActionChrome ? ppStyles.optionExpandedDetailSectionCompact : null),
          }}
          data-play-action-card-detail-section="result"
        >
          <span style={ppStyles.optionExpandedDetailLabel}>
            {t("play.option_expanded_result_label")}
          </span>
          <span style={ppStyles.optionExpandedDetailText}>
            {hint || t("play.preview_action_risk_default")}
          </span>
        </span>
        {target ? (
          <span
            style={{
              ...ppStyles.optionExpandedDetailSection,
              ...(compactActionChrome ? ppStyles.optionExpandedDetailSectionCompact : null),
            }}
            data-play-action-target-detail="true"
            data-play-action-target-detail-id={target.id}
          >
            <span style={ppStyles.optionExpandedDetailLabel}>
              {t("play.action_target_detail_label")}
            </span>
            <span
              style={ppStyles.optionExpandedDetailText}
              title={t("play.action_target_title", { name: target.name })}
            >
              {t("play.action_target_detail_text", { name: target.name })}
            </span>
          </span>
        ) : null}
        {forecasts.length ? (
          <span
            style={{
              ...ppStyles.optionExpandedDetailSection,
              ...(compactActionChrome ? ppStyles.optionExpandedDetailSectionCompact : null),
            }}
            data-play-action-card-detail-section="forecast"
          >
            {renderDecisionForecast(forecasts, { compact: compactActionChrome, detail: true })}
          </span>
        ) : null}
        {forecastDetails.map((chip) => (
          <span
            key={`${chip.label}-${chip.detail}`}
            style={{
              ...ppStyles.optionExpandedDetailSection,
              ...(compactActionChrome ? ppStyles.optionExpandedDetailSectionCompact : null),
            }}
            data-play-action-card-detail-section="why-now"
          >
            <span style={ppStyles.optionExpandedDetailLabel}>
              {t("play.gameplay_forecast_detail_label")}
            </span>
            <span
              style={ppStyles.optionExpandedDetailText}
              data-gameplay-forecast-detail="normal-play"
              title={chip.detail}
            >
              {chip.detail}
            </span>
          </span>
        ))}
      </motion.span>
    )
  }

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
        >
          <div style={ppStyles.turnGuideCopy}>
            <strong style={ppStyles.turnGuideTitle}>{turnGuide.title}</strong>
            <span style={ppStyles.turnGuideDetail}>{turnGuide.detail}</span>
          </div>
        </div>
      ) : null}

      {showLeverageRail ? (
        <section
          id={ACTION_LEVERAGE_RAIL_ID}
          style={{
            ...ppStyles.leverageRail,
            ...(compactActionChrome ? ppStyles.leverageRailCompact : null),
          }}
          aria-label={t("play.leverage_rail_label")}
        >
          {playableLeverageCards.length === 0 ? (
            <div style={ppStyles.leverageEmptySummary}>
              <span style={ppStyles.leverageSummaryMain}>
                <span style={ppStyles.leverageSummaryEyebrow}>{t("play.leverage_resource_label")}</span>
                <strong style={ppStyles.leverageSummaryText}>{leverageEmptyTitle}</strong>
                <span style={ppStyles.leverageSummaryMeta} title={leverageEmptyMetaText}>
                  {leverageEmptyMetaText}
                </span>
              </span>
              <span style={ppStyles.leverageEmptyBadge}>{leverageEmptyBadge}</span>
            </div>
          ) : (
            <button
              type="button"
              style={{
                ...ppStyles.leverageSummaryButton,
                ...(showLeverageCards ? ppStyles.leverageSummaryButtonOpen : null),
                ...(compactActionChrome ? ppStyles.leverageSummaryButtonCompact : null),
              }}
              onClick={handleLeverageSummaryActivate}
              disabled={actionControlsDisabled}
              aria-expanded={showLeverageCards}
              aria-keyshortcuts="T"
              title={t("play.leverage_shortcut_title")}
            >
              <span style={ppStyles.leverageSummaryMain}>
                <span style={ppStyles.leverageSummaryEyebrow}>{t("play.leverage_resource_label")}</span>
                <strong style={ppStyles.leverageSummaryText}>{leverageSummaryText}</strong>
                <span style={ppStyles.leverageSummaryMeta} title={leverageSummaryMetaText}>{leverageSummaryMetaText}</span>
              </span>
              <span
                style={{
                  ...ppStyles.leverageSummaryToggle,
                  ...(compactActionChrome ? ppStyles.leverageSummaryToggleCompact : null),
                }}
              >
                {leverageSummaryToggleText}
              </span>
            </button>
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
                    style={{
                      ...ppStyles.leverageMiniCard,
                      ...(isPrepared ? ppStyles.leverageMiniCardArmed : null),
                      ...(card.used ? ppStyles.leverageMiniCardUsed : null),
                    }}
                    onClick={() => {
                      if (card.used || actionControlsDisabled) return
                      setSelectedOptionIndex(null)
                      setShowFreeInput(false)
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
            ...(actorFocusMatchCount > 0 ? ppStyles.actorFocusCueMatched : ppStyles.actorFocusCueEmpty),
          }}
          data-play-actor-focus-cue="true"
          data-play-actor-focus-id={actorFocus.id}
          data-play-actor-focus-match-count={actorFocusMatchCount}
          aria-label={t("play.actor_focus_label")}
        >
          <span style={ppStyles.actorFocusCueLabel}>{t("play.actor_focus_label")}</span>
          <strong style={ppStyles.actorFocusCueName}>{actorFocus.name}</strong>
          <span style={ppStyles.actorFocusCueDetail}>
            {actorFocusMatchCount > 0
              ? t("play.actor_focus_match_detail", { name: actorFocus.name, count: actorFocusMatchCount })
              : t("play.actor_focus_no_match", { name: actorFocus.name })}
          </span>
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
          <span style={ppStyles.resourceFocusCueLabel}>{t("play.resource_focus_label")}</span>
          <strong style={ppStyles.resourceFocusCueName}>{resourceFocus.label}</strong>
          <span style={ppStyles.resourceFocusCueDetail}>{resourceFocusDetail}</span>
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
                const isActorFocusMatch = actorFocusOptionMatches[i] ?? false
                const isActorFocusDimmed = Boolean(actorFocus && actorFocusMatchCount > 0 && !isActorFocusMatch)
                const isResourceFocusMatch = resourceFocusOptionMatches[i] ?? false
                const isResourceFocusDimmed = Boolean(resourceFocus && resourceFocusMatchCount > 0 && !isResourceFocusMatch)
                const optionShortcutKey = i < 9 ? String(i + 1) : null
                const isChoiceDimmed =
                  selectedOptionIndex !== null && !isSelected && pickedIndex === null
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
                        {actionTarget ? (
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
                          <span
                            style={{
                              ...ppStyles.optionHintInline,
                              ...(compactActionChrome ? ppStyles.optionHintInlineCompact : null),
                            }}
                            title={opt.hint}
                          >
                            {opt.hint}
                          </span>
                        ) : null}
                        {optionForecasts.length && !isSelected ? (
                          <span
                            style={ppStyles.gameplayDecisionForecastShell}
                            data-gameplay-action-forecast="true"
                          >
                            {renderDecisionForecast(optionForecasts, { compact: compactActionChrome })}
                          </span>
                        ) : null}
                        <span
                          style={{
                            ...ppStyles.optionExpandCue,
                            ...(isSelected ? ppStyles.optionExpandCueActive : null),
                          }}
                        >
                          {isSelected ? t("play.selected_move_kicker") : t("play.option_expand_cta")}
                        </span>
                        {isSelected ? renderSelectedOptionDetail(opt.hint ?? "", optionForecasts, actionTarget) : null}
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
              <div
                style={ppStyles.freeActionContext}
                data-play-free-action-context="true"
                data-play-free-action-context-kind={freeActionFocusContext.kind}
                data-play-free-action-context-id={freeActionFocusContext.id}
              >
                <span style={ppStyles.freeActionContextLabel}>
                  {freeActionFocusContext.kind === "actor"
                    ? t("play.free_context_actor_label")
                    : t("play.free_context_resource_label")}
                </span>
                <strong style={ppStyles.freeActionContextName}>
                  {freeActionFocusContext.label}
                </strong>
                <span style={ppStyles.freeActionContextDetail}>
                  {freeActionFocusContext.detail}
                </span>
              </div>
            ) : null}
            <textarea
              className="play-free-textarea"
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
                          ...ppStyles.actionPrimaryLine,
                          ...(compactActionChrome ? ppStyles.actionPrimaryLineCompact : null),
                          ...(actionControlsDisabled ? ppStyles.actionPrimaryLineDisabled : null),
                        }}
                        onClick={() => handleSubmitFreeWithReflect()}
                        disabled={actionControlsDisabled}
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

      {showFreeActionToggle ? (
        <div style={ppStyles.alternateActionRow}>
          {showFreeActionToggle ? (
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
// Floating Advisor button
// ---------------------------------------------------------------------------

export function AdvisorFab({
  onOpen,
  avatarUrl,
  persona,
}: {
  onOpen: () => void
  avatarUrl: string
  persona: string
}) {
  const t = useT()
  const compactFab = useCompactLayout("(max-width: 680px)")
  return (
    <button
      className="advisor-fab"
      style={{
        ...ppStyles.fab,
        ...(compactFab ? ppStyles.fabCompact : null),
      }}
      onClick={onOpen}
      title={t("play.fab_title", { persona })}
      aria-label={t("play.fab_label")}
      aria-haspopup="dialog"
      type="button"
    >
      <span className="advisor-fab__label" style={ppStyles.fabLabel}>
        {t("play.fab_label")}
      </span>
      <img className="advisor-fab__avatar" src={avatarUrl} alt="" style={ppStyles.fabAvatarImg} loading="lazy" />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Advisor sidechat panel
// ---------------------------------------------------------------------------

export function AdvisorSidechat({
  sessionId,
  persona,
  avatarUrl,
  turnsRemaining,
  isComplete,
  isCommitmentActive,
  commitmentSummary,
  suggestions,
  onClose,
  onOracleConsumed,
}: {
  sessionId: string
  persona: string
  avatarUrl: string
  turnsRemaining: number
  isComplete: boolean
  isCommitmentActive: boolean
  commitmentSummary: ActionCommitmentSummary | null
  suggestions: string[]
  onClose: () => void
  onOracleConsumed: (newBudget: number) => void
}) {
  const api = useApi()
  const t = useT()
  const [messages, setMessages] = useState<NarrativeAdvisorMessage[]>([])
  const [oracleOrds, setOracleOrds] = useState<Set<number>>(new Set())
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingOracleQuestion, setPendingOracleQuestion] = useState<string | null>(null)
  const [draftFocusToken, setDraftFocusToken] = useState(0)
  const panelRef = useRef<HTMLElement | null>(null)
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const latestMessageRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const oracleConfirmRef = useRef<HTMLButtonElement | null>(null)
  const initialFocusDoneRef = useRef(false)
  const compactAdvisor = useCompactLayout("(max-width: 520px)")
  const isEmptyAdvisor = messages.length === 0 && !busy
  const hasAdvisorDraft = draft.trim().length > 0
  const canUseOracle = !isComplete && turnsRemaining > 1
  const oracleBudgetAfter = Math.max(1, turnsRemaining - 1)
  const visibleSuggestions = useMemo(() => {
    const contextual =
      commitmentSummary?.kind === "option"
        ? [t("play.advisor_suggest_option_backfire"), t("play.advisor_suggest_option_improve")]
        : commitmentSummary?.kind === "leverage"
          ? [t("play.advisor_suggest_leverage_timing"), t("play.advisor_suggest_leverage_value")]
          : commitmentSummary?.kind === "free"
            ? [t("play.advisor_suggest_free_target"), t("play.advisor_suggest_free_wording")]
            : []
    const deduped = [...contextual]
    for (const suggestion of suggestions) {
      if (!deduped.includes(suggestion)) {
        deduped.push(suggestion)
      }
    }
    return deduped.slice(0, 4)
  }, [commitmentSummary?.kind, suggestions, t])
  const advisorPanelVariants = compactAdvisor
    ? {
        initial: { opacity: 0, x: 0, y: 24 },
        animate: { opacity: 1, x: 0, y: 0 },
        exit: { opacity: 0, x: 0, y: 18 },
      }
    : slideInRightVariants

  const cancelPendingOracle = useCallback(() => {
    setPendingOracleQuestion(null)
    setDraftFocusToken((token) => token + 1)
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .getNarrativeAdvisorHistory(sessionId)
      .then((res) => {
        if (cancelled) return
        setMessages(res.messages)
      })
      .catch((err) => {
        if (cancelled) return
        setError(friendlyError(err, t("play.advisor_history_failed")))
      })
    return () => {
      cancelled = true
    }
  }, [api, sessionId])

  useEffect(() => {
    const el = scrollerRef.current
    const latest = latestMessageRef.current
    if (!el || !latest) return
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const top = Math.max(0, latest.offsetTop - el.offsetTop)
    const frame = window.requestAnimationFrame(() => {
      el.scrollTo({ top, behavior: prefersReducedMotion ? "auto" : "smooth" })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [messages.length])

  useEffect(() => {
    if (!pendingOracleQuestion || busy) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      e.preventDefault()
      cancelPendingOracle()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [busy, cancelPendingOracle, pendingOracleQuestion])

  useEffect(() => {
    if (pendingOracleQuestion || busy) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      const target = e.target as HTMLElement | null
      const inEditable =
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "INPUT" ||
        !!target?.isContentEditable
      if (inEditable && draft.trim()) {
        e.preventDefault()
        return
      }
      e.preventDefault()
      onClose()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [busy, draft, onClose, pendingOracleQuestion])

  const focusAdvisorTextarea = useCallback(() => {
    const node = textareaRef.current
    if (!node || node.disabled) return
    node.focus({ preventScroll: true })
    const cursor = node.value.length
    node.setSelectionRange(cursor, cursor)
  }, [])

  useEffect(() => {
    if (initialFocusDoneRef.current || busy || pendingOracleQuestion) return
    initialFocusDoneRef.current = true
    const frame = window.requestAnimationFrame(focusAdvisorTextarea)
    const timers = [90, 220].map((delay) => window.setTimeout(focusAdvisorTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, focusAdvisorTextarea, pendingOracleQuestion])

  useEffect(() => {
    if (!draftFocusToken || busy || pendingOracleQuestion) return
    const frame = window.requestAnimationFrame(focusAdvisorTextarea)
    const timers = [90, 220].map((delay) => window.setTimeout(focusAdvisorTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, draftFocusToken, focusAdvisorTextarea, pendingOracleQuestion])

  useEffect(() => {
    if (!pendingOracleQuestion || busy) return
    const focusConfirm = () => {
      const node = oracleConfirmRef.current
      if (!node || node.disabled) return
      node.focus({ preventScroll: true })
    }
    const frame = window.requestAnimationFrame(focusConfirm)
    const timers = [90, 220].map((delay) => window.setTimeout(focusConfirm, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, pendingOracleQuestion])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return
      const panel = panelRef.current
      if (!panel) return
      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>(
          [
            "button:not([disabled])",
            "textarea:not([disabled])",
            "input:not([disabled])",
            "select:not([disabled])",
            "a[href]",
            "[tabindex]:not([tabindex='-1'])",
          ].join(","),
        ),
      ).filter((node) => node.offsetParent !== null)
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus({ preventScroll: true })
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus({ preventScroll: true })
      } else if (active instanceof Node && !panel.contains(active)) {
        e.preventDefault()
        first.focus({ preventScroll: true })
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  const submitAsk = async (question: string, oracle: boolean) => {
    setBusy(true)
    setError(null)
    setDraft("")
    setPendingOracleQuestion(null)
    try {
      const res = await api.askNarrativeAdvisor(sessionId, {
        question,
        ...(oracle ? { oracle_mode: true } : {}),
      })
      setMessages((prev) => [...prev, res.player_message, res.advisor_message])
      if (res.oracle_used) {
        setOracleOrds((prev) => {
          const next = new Set(prev)
          next.add(res.advisor_message.ord)
          return next
        })
        if (typeof res.turn_budget_after === "number") {
          onOracleConsumed(res.turn_budget_after)
        }
      }
    } catch (err) {
      setError(friendlyError(err, t("play.advisor_ask_failed")))
      setDraft(question)
      setDraftFocusToken((token) => token + 1)
    } finally {
      setBusy(false)
    }
  }

  const handleAsk = (oracle: boolean) => {
    const question = draft.trim()
    if (!question || busy) return
    if (oracle && isComplete) {
      setError(t("play.oracle_completed_error"))
      return
    }
    if (oracle) {
      setPendingOracleQuestion(question)
      return
    }
    void submitAsk(question, false)
  }
  const applySuggestion = (suggestion: string) => {
    setDraft(suggestion)
    setDraftFocusToken((token) => token + 1)
  }

  const renderSuggestionBlock = (variant: "empty" | "composer") =>
    visibleSuggestions.length > 0 ? (
      <div
        style={{
          ...ppStyles.advisorSuggestionBlock,
          ...(variant === "empty" ? ppStyles.advisorSuggestionBlockEmpty : null),
          ...(variant === "composer" && compactAdvisor ? ppStyles.advisorSuggestionBlockComposerCompact : null),
        }}
      >
        <span style={ppStyles.advisorSuggestionLabel}>
          {t("play.advisor_suggestions_label")}
        </span>
        <div
          style={{
            ...ppStyles.advisorSuggestionRow,
            ...(variant === "empty" ? ppStyles.advisorSuggestionRowEmpty : null),
            ...(variant === "composer" && compactAdvisor ? ppStyles.advisorSuggestionRowComposerCompact : null),
          }}
        >
          {visibleSuggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              aria-label={t("play.advisor_suggestion_apply_title", { question: suggestion })}
              title={t("play.advisor_suggestion_apply_title", { question: suggestion })}
              style={{
                ...ppStyles.advisorSuggestionChip,
                ...(variant === "empty" ? ppStyles.advisorSuggestionChipEmpty : null),
                ...(variant === "composer" && compactAdvisor ? ppStyles.advisorSuggestionChipComposerCompact : null),
              }}
              onClick={() => applySuggestion(suggestion)}
              disabled={busy || !!pendingOracleQuestion}
            >
              <span style={ppStyles.advisorSuggestionText}>{suggestion}</span>
              <span aria-hidden="true" style={ppStyles.advisorSuggestionArrow}>
                {t("play.advisor_suggestion_insert")}
              </span>
            </button>
          ))}
        </div>
      </div>
    ) : null

  return (
    <>
      <motion.div
        style={{
          ...ppStyles.advisorBackdrop,
          ...(compactAdvisor ? ppStyles.advisorBackdropCompact : null),
        }}
        onClick={onClose}
        variants={fadeVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={fadeTransition}
      />
      <motion.aside
        ref={panelRef}
        style={{
          ...ppStyles.advisorPanel,
          ...(compactAdvisor ? ppStyles.advisorPanelCompact : null),
          ...(compactAdvisor && (messages.length > 0 || busy) ? ppStyles.advisorPanelCompactReading : null),
        }}
        variants={advisorPanelVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={compactAdvisor ? transitions.snap : slideInRightTransition}
        onAnimationComplete={() => {
          if (!busy && !pendingOracleQuestion) {
            focusAdvisorTextarea()
          }
        }}
        role="dialog"
        aria-modal="true"
        aria-label={t("play.advisor_title")}
      >
        <header
          style={{
            ...ppStyles.advisorHeader,
            ...(compactAdvisor ? ppStyles.advisorHeaderCompact : null),
          }}
        >
          <img
            src={avatarUrl}
            alt=""
            style={{
              ...ppStyles.advisorHeaderAvatar,
              ...(compactAdvisor ? ppStyles.advisorHeaderAvatarCompact : null),
            }}
            loading="lazy"
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={ppStyles.advisorTitle}>{t("play.advisor_title")}</div>
            <div style={{ ...ppStyles.advisorPersona, ...(compactAdvisor ? ppStyles.advisorPersonaCompact : null) }}>
              {persona}
            </div>
          </div>
          <button
            style={ppStyles.advisorClose}
            onClick={onClose}
            type="button"
            aria-label={t("play.advisor_close")}
            aria-keyshortcuts="Escape"
            title={t("play.shortcut_escape_cancel")}
          >
            ✕
          </button>
        </header>

        {isCommitmentActive ? (
          <div
            style={{
              ...ppStyles.advisorContextLine,
              ...(compactAdvisor ? ppStyles.advisorContextLineCompact : null),
            }}
          >
            <span style={ppStyles.advisorContextKicker}>
              {commitmentSummary?.kicker ?? t("play.advisor_commitment_notice_kicker")}
            </span>
            <span
              style={{
                ...ppStyles.advisorContextText,
                ...(compactAdvisor ? ppStyles.advisorContextTextCompact : null),
              }}
            >
              {commitmentSummary
                ? [
                    commitmentSummary.title,
                    commitmentSummary.detail,
                    commitmentSummary.motive
                      ? t("play.advisor_commitment_motive", { motive: commitmentSummary.motive })
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : t("play.advisor_commitment_notice_body")}
            </span>
          </div>
        ) : null}

        <div
          style={{
            ...ppStyles.advisorMessages,
            ...(compactAdvisor ? ppStyles.advisorMessagesCompact : null),
            ...(isEmptyAdvisor ? ppStyles.advisorMessagesEmpty : null),
          }}
          ref={scrollerRef}
        >
          {messages.length === 0 ? (
            hasAdvisorDraft ? null : renderSuggestionBlock("empty")
          ) : (
            messages.map((m, index) => {
              const isOracle = m.role === "advisor" && oracleOrds.has(m.ord)
              const isLatestMessage = index === messages.length - 1
              return (
                <motion.div
                  ref={isLatestMessage ? latestMessageRef : undefined}
                  key={`${m.role}-${m.ord}`}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={itemTransition}
                  style={m.role === "player" ? ppStyles.advisorRowPlayer : ppStyles.advisorRowAdvisor}
                >
                  {isOracle ? (
                    <div style={{ ...ppStyles.advisorTranscriptLine, ...ppStyles.advisorTranscriptLineOracle }}>
                      <span style={{ ...ppStyles.advisorTranscriptSpeaker, ...ppStyles.oracleBadge }}>
                        {t("play.oracle_badge")}
                      </span>
                      <span style={ppStyles.advisorBubbleOracle}>{m.content}</span>
                    </div>
                  ) : (
                    <div style={ppStyles.advisorTranscriptLine}>
                      <span
                        style={{
                          ...ppStyles.advisorTranscriptSpeaker,
                          ...(m.role === "player" ? ppStyles.advisorTranscriptSpeakerPlayer : null),
                        }}
                      >
                        {m.role === "player" ? t("play.advisor_speaker_player") : t("play.advisor_speaker_friend")}
                      </span>
                      <span
                        style={
                          m.role === "player"
                            ? ppStyles.advisorBubblePlayer
                            : ppStyles.advisorBubbleAdvisor
                        }
                      >
                        {m.content}
                      </span>
                    </div>
                  )}
                </motion.div>
              )
            })
          )}
          {busy ? <TypingDots /> : null}
        </div>

        {error ? <div style={ppStyles.advisorError}>{error}</div> : null}

        <div
          style={{
            ...ppStyles.advisorInput,
            ...(compactAdvisor ? ppStyles.advisorInputCompact : null),
            ...(isEmptyAdvisor ? ppStyles.advisorInputEmpty : null),
          }}
        >
          <div
            style={{
              ...ppStyles.advisorComposer,
              ...(compactAdvisor ? ppStyles.advisorComposerCompact : null),
              ...(isEmptyAdvisor ? ppStyles.advisorComposerEmpty : null),
              ...(pendingOracleQuestion ? ppStyles.advisorComposerOracleArmed : null),
            }}
          >
            <textarea
              ref={textareaRef}
              style={ppStyles.advisorTextarea}
              value={draft}
              placeholder={t("play.advisor_textarea_placeholder")}
              aria-label={t("play.advisor_textarea_placeholder")}
              aria-keyshortcuts="Meta+Enter Control+Enter"
              title={t("play.shortcut_mod_enter_submit")}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault()
                  if (pendingOracleQuestion) {
                    void submitAsk(pendingOracleQuestion, true)
                    return
                  }
                  handleAsk(false)
                }
              }}
              disabled={busy || !!pendingOracleQuestion}
              rows={2}
            />
            {pendingOracleQuestion ? (
              <div style={ppStyles.oracleInlineLine}>
                <span style={ppStyles.oracleInlineCopy}>
                  {t("play.oracle_inline_summary", {
                    before: turnsRemaining,
                    after: oracleBudgetAfter,
                  })}
                </span>
                {isCommitmentActive ? (
                  <span style={ppStyles.oracleInlineKeepMove}>
                    {t("play.oracle_inline_keep_move")}
                  </span>
                ) : null}
                <div style={ppStyles.oracleInlineActions}>
                  <button
                    ref={oracleConfirmRef}
                    style={ppStyles.advisorSendBtn}
                    type="button"
                    onClick={() => void submitAsk(pendingOracleQuestion, true)}
                    disabled={busy}
                  >
                    {t("play.oracle_inline_confirm")}
                  </button>
                  <button
                    style={ppStyles.oracleInlineCancelBtn}
                    type="button"
                    onClick={cancelPendingOracle}
                    disabled={busy}
                    aria-keyshortcuts="Escape"
                    title={t("play.shortcut_escape_cancel")}
                  >
                    {t("play.oracle_inline_cancel")}
                  </button>
                </div>
              </div>
            ) : (
              <>
                {isEmptyAdvisor || hasAdvisorDraft ? null : renderSuggestionBlock("composer")}
                {hasAdvisorDraft ? (
                  <div
                    style={{
                      ...ppStyles.advisorBtnRow,
                      ...(compactAdvisor ? ppStyles.advisorBtnRowCompact : null),
                    }}
                  >
                    <button
                      style={{
                        ...ppStyles.advisorSendBtn,
                        ...(compactAdvisor ? ppStyles.advisorActionBtnCompact : null),
                        ...(busy ? ppStyles.advisorActionDisabled : null),
                      }}
                      onClick={() => handleAsk(false)}
                      disabled={busy}
                      type="button"
                      aria-keyshortcuts="Meta+Enter Control+Enter"
                      title={t("play.shortcut_mod_enter_submit")}
                    >
                      {t("play.advisor_send")}
                    </button>
                    <button
                      style={{
                        ...ppStyles.oracleBtn,
                        ...(compactAdvisor ? ppStyles.advisorActionBtnCompact : null),
                        ...(busy || !canUseOracle ? ppStyles.advisorActionDisabled : null),
                      }}
                      onClick={() => handleAsk(true)}
                      disabled={busy || !canUseOracle}
                      type="button"
                      title={
                        isComplete
                          ? t("play.oracle_tip_complete")
                          : turnsRemaining <= 1
                            ? t("play.oracle_tip_no_turns")
                            : t("play.oracle_tip_active", { turns: turnsRemaining })
                    }
                  >
                      {canUseOracle
                        ? t("play.oracle_button_with_cost")
                        : t("play.oracle_button")}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      </motion.aside>
    </>
  )
}

// Bouncing 3-dot typing indicator. Used in advisor sidechat while waiting
// for the LLM response. Pure CSS keyframes via inline animation.
function TypingDots() {
  const t = useT()
  return (
    <div
      style={ppStyles.typingRow}
      role="status"
      aria-live="polite"
      aria-label={t("play.advisor_typing_status")}
    >
      <div style={ppStyles.typingBubble} aria-hidden>
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            style={ppStyles.typingDot}
            animate={{ y: [0, -4, 0] }}
            transition={{
              duration: 0.9,
              repeat: Infinity,
              delay: i * 0.15,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
