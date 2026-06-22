import { motion } from "motion/react"
import type {
  NarrativeAgentEvent,
  NarrativeAgentEventPayload,
  NarrativeAgentPlan,
  NarrativeContractJudgeResult,
  NarrativeEnding,
  NarrativeLLMCallEvent,
  NarrativeStepJudgeResult,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../../shared/lib/i18n"
import { itemTransition } from "../../../shared/lib/motion-presets"
import { ppStyles } from "../play-styles"

function truncateRuntimeText(value: string, max = 64): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

export function RuntimeInspector({
  story,
  ending,
  lastNarrator,
  turnsRemaining,
  liveInventory,
  effectiveLastInventoryDelta,
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
  effectiveLastInventoryDelta?: NarrativeStoryMessage["inventory_delta"]
  agentPlan: NarrativeAgentPlan | null
  agentEvents: NarrativeAgentEvent[]
  llmEvents: NarrativeLLMCallEvent[]
  agentTraceAccessGranted: boolean
}) {
  const { lang } = useLanguage()
  const t = useT()
  const endingLabel = ending
    ? displayRuntimeEndingLabel(ending.label, lang)
    : story.session.ending_label
      ? displayRuntimeEndingLabel(story.session.ending_label, lang)
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
    effectiveInventoryDelta: effectiveLastInventoryDelta,
  })
  const trajectory = trajectoryEvidence(agentEvents)
  const latestStatus = worstStatus([
    latestStepJudge?.status ?? "missing",
    latestContractJudge?.status ?? "missing",
  ])
  const score = evaluationScore(criteria)
  const hasArchivedJudgeEvidence = Boolean(latestStepJudge || latestContractJudge)
  const reviewerEvidenceLimitLabel = hasArchivedJudgeEvidence ? "Archived checks" : "Evidence limits"
  const archivedCheckStatus = hasArchivedJudgeEvidence ? latestStatus : "not available yet"
  const archivedScore = hasArchivedJudgeEvidence ? `${score}/100` : "not archived yet"
  const reasonCategory = hasArchivedJudgeEvidence
    ? evaluationReasonCategory(latestStepJudge, latestContractJudge, llmEvents)
    : "not archived yet"
  const latestEvidence = evaluationObservedEvidence(latestStepJudge, latestContractJudge, lastNarrator, effectiveLastInventoryDelta)
  const playableMoveCount = lastNarrator?.options.length ?? 0
  const hasLiveStateChange = reviewerHasLiveStateChange(lastNarrator, effectiveLastInventoryDelta)
  const liveImpactSummary = reviewerLiveImpactSummary(
    lastNarrator,
    "awaiting next story beat",
    effectiveLastInventoryDelta,
  )
  const telemetryRows = llmEvents.slice(-8).reverse()
  const traceRows = agentPlan
    ? [
        { label: "Turn", value: `ord ${agentPlan.narrator_ord} · ${agentPlan.turn_index}/${agentPlan.turn_budget}` },
        { label: "Stage", value: `${agentPlan.director.stage_phase} · ${agentPlan.director.expected_pressure}` },
        { label: "Intent", value: agentIntentSummary(agentPlan, "none") },
        { label: "Twist", value: agentTwistSummary(agentPlan, "none") },
        { label: "Memory", value: agentMemorySummary(agentPlan) },
        { label: "Move", value: agentActionSummary(agentPlan, "none") },
        { label: "Impact", value: agentImpactSummary(lastNarrator, "pending", effectiveLastInventoryDelta) },
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
      <p style={ppStyles.reviewerEvidencePrimer} data-reviewer-evidence-primer="true">
        Start with the live evidence checks. Archived scoring stays collapsed under the evidence summary, so this view
        checks playability first and still lets reviewers inspect the deeper record.
      </p>
      <section
        style={ppStyles.reviewerProofStrip}
        aria-label="Reviewer evidence summary"
        data-reviewer-proof-strip="true"
      >
        <span style={ppStyles.reviewerProofTitle}>What this checks</span>
        <div style={ppStyles.reviewerProofGrid}>
          <div style={ppStyles.reviewerProofChip} data-reviewer-proof-chip="playable">
            <span style={ppStyles.reviewerProofLabel}>Playable state</span>
            <strong style={ppStyles.reviewerProofValue}>
              {playableMoveCount ? `${playableMoveCount} next moves` : "waiting for moves"}
            </strong>
            <span style={ppStyles.reviewerProofDetail}>{turnsRemaining} turns left</span>
          </div>
          <div style={ppStyles.reviewerProofChip} data-reviewer-proof-chip="state">
            <span style={ppStyles.reviewerProofLabel}>{hasLiveStateChange ? "State changed" : "Change to verify"}</span>
            <strong style={ppStyles.reviewerProofValue}>
              {hasLiveStateChange ? liveImpactSummary : "waiting for first move"}
            </strong>
            <span style={ppStyles.reviewerProofDetail}>
              {hasLiveStateChange ? "visible consequence on the latest beat" : "play one move to verify consequences"}
            </span>
          </div>
          <div style={ppStyles.reviewerProofChip} data-reviewer-proof-chip="checks">
            <span style={ppStyles.reviewerProofLabel}>{reviewerEvidenceLimitLabel}</span>
            <strong style={ppStyles.reviewerProofValue}>{archivedCheckStatus}</strong>
            <span style={ppStyles.reviewerProofDetail}>
              {hasArchivedJudgeEvidence ? "step and contract checks attached" : "live state visible; archive not claimed yet"}
            </span>
          </div>
        </div>
      </section>
      <details
        style={ppStyles.reviewerArchiveDetails}
        data-reviewer-archive-details="true"
      >
        <summary style={ppStyles.reviewerArchiveSummary} data-reviewer-archive-summary="true">
          <span>{hasArchivedJudgeEvidence ? "Archived evaluation available" : "Archived evaluation not available yet"}</span>
          <strong>
            {hasArchivedJudgeEvidence ? `${archivedScore} · ${archivedCheckStatus}` : "live evidence is enough for this view"}
          </strong>
        </summary>
        <p style={ppStyles.reviewerArchiveScopeSummary} data-reviewer-archive-scope-summary="true">
          Local reviewer evidence, not a public benchmark. Pair with repo/demo preflight before citing.
        </p>
        <div style={ppStyles.reviewerArchiveScopeNote} data-reviewer-archive-scope-note="true">
          <strong>Archive scope</strong>
          <span>
            Use this as local reviewer evidence: it verifies playable state, consequences, and contract checks for this run.
            It is not a public benchmark; pair it with repo/demo preflight before citing it.
          </span>
        </div>
        <div style={ppStyles.evaluationHero}>
          <div style={ppStyles.evaluationVerdictBlock}>
            <span style={ppStyles.evaluationLabel}>{reviewerEvidenceLimitLabel}</span>
            <strong style={ppStyles.evaluationVerdict} data-evaluation-verdict={hasArchivedJudgeEvidence ? latestStatus : "pending"}>
              {archivedCheckStatus}
            </strong>
          </div>
          <div style={ppStyles.evaluationScoreBlock}>
            <span style={ppStyles.evaluationLabel}>Score</span>
            <strong style={ppStyles.evaluationScore}>{archivedScore}</strong>
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

        <section style={ppStyles.evaluationSection} data-reviewer-generation-record="true">
          <span style={ppStyles.evaluationSectionTitle}>Generation record</span>
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
              {agentTraceAccessGranted ? "No generation log is attached to this local evidence run yet." : "Reviewer access not granted."}
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
      </details>

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
  effectiveInventoryDelta,
}: {
  agentPlan: NarrativeAgentPlan | null
  latestStepJudge: NarrativeStepJudgeResult | null
  latestContractJudge: NarrativeContractJudgeResult | null
  lastNarrator: NarrativeStoryMessage | null
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"]
}): EvaluationCriterion[] {
  const stepStatus = latestStepJudge?.status ?? "missing"
  const contractStatus = latestContractJudge?.status ?? "missing"
  const stepCodes = new Set(latestStepJudge?.violations.map((v) => v.code) ?? [])
  const contractCodes = new Set(latestContractJudge?.violations.map((v) => v.code) ?? [])
  const hasImpact = Boolean(
    (lastNarrator?.npc_pulse ?? []).some((pulse) => pulse.shift !== "steady") ||
      (effectiveInventoryDelta?.added.length ?? lastNarrator?.inventory_delta?.added.length ?? 0) > 0 ||
      (effectiveInventoryDelta?.removed.length ?? lastNarrator?.inventory_delta?.removed.length ?? 0) > 0,
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
      evidence: agentImpactSummary(lastNarrator, "no pulse or inventory delta observed", effectiveInventoryDelta),
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
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"],
): string {
  const violationEvidence = firstViolationEvidence(step) || firstViolationEvidence(contract)
  if (violationEvidence) return violationEvidence
  const impact = agentImpactSummary(lastNarrator, "", effectiveInventoryDelta)
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
    return truncateRuntimeText(chosen, 96)
  }
  const content = action["content"]
  if (typeof content === "string" && content.trim()) {
    return truncateRuntimeText(content, 96)
  }
  return emptyLabel
}

function agentImpactSummary(
  message: NarrativeStoryMessage | null,
  pendingLabel: string,
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"],
): string {
  if (!message) return pendingLabel
  const pulseCount = message.npc_pulse?.length ?? 0
  const added = effectiveInventoryDelta?.added.length ?? message.inventory_delta?.added.length ?? 0
  const removed = effectiveInventoryDelta?.removed.length ?? message.inventory_delta?.removed.length ?? 0
  const delta = added || removed ? `inventory +${added}/-${removed}` : "inventory steady"
  return `pulse ${pulseCount} · ${delta}`
}

function reviewerLiveImpactSummary(
  message: NarrativeStoryMessage | null,
  pendingLabel: string,
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"],
): string {
  if (!message) return pendingLabel
  const reactionCount = (message.npc_pulse ?? []).filter((pulse) => pulse.shift !== "steady").length
  const added = effectiveInventoryDelta?.added.length ?? message.inventory_delta?.added.length ?? 0
  const removed = effectiveInventoryDelta?.removed.length ?? message.inventory_delta?.removed.length ?? 0
  const parts: string[] = []

  if (reactionCount === 1) parts.push("1 character reaction")
  if (reactionCount > 1) parts.push(`${reactionCount} character reactions`)
  if (added === 1) parts.push("1 story item gained")
  if (added > 1) parts.push(`${added} story items gained`)
  if (removed === 1) parts.push("1 story item spent")
  if (removed > 1) parts.push(`${removed} story items spent`)

  return parts.length ? parts.join(" · ") : "latest beat keeps state stable"
}

function reviewerHasLiveStateChange(
  message: NarrativeStoryMessage | null,
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"],
): boolean {
  if (!message) return false
  const hasReaction = (message.npc_pulse ?? []).some((pulse) => pulse.shift !== "steady")
  const added = effectiveInventoryDelta?.added.length ?? message.inventory_delta?.added.length ?? 0
  const removed = effectiveInventoryDelta?.removed.length ?? message.inventory_delta?.removed.length ?? 0
  return hasReaction || added > 0 || removed > 0
}

function displayRuntimeEndingLabel(label: string, lang: ReturnType<typeof useLanguage>["lang"]): string {
  const translated = ENDING_LABEL_DISPLAY[lang]?.[label]
  if (translated) return translated
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase())
}
