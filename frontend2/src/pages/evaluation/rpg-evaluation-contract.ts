export type EvaluationStatus = "pass" | "warn" | "fail"

export type RpgMemoryFact = {
  fact_id: string
  namespace: string
  key: string
  value: string
  status: "active" | "superseded"
  source_turn: number
  source: "user" | "runtime" | "system" | "imported"
  confidence: number
  superseded_by?: string | null
}

export type RpgMemoryEntity = {
  entity_id: string
  name: string
  state: Record<string, string>
  last_updated_turn: number
}

export type RpgMemorySnapshot = {
  schema_version: "rpg_memory.v1"
  run_id: string
  turn_index: number
  objective: string
  active_facts: RpgMemoryFact[]
  superseded_facts: RpgMemoryFact[]
  open_threads: string[]
  entities: RpgMemoryEntity[]
  recent_events: string[]
  episodic_summary: string
  diagnostics: {
    event_count: number
    active_fact_count: number
    superseded_fact_count: number
    non_story_event_count: number
    dropped_recent_event_count: number
    last_compacted_turn: number
  }
}

export type RpgStateDelta = {
  target: string
  kind: "increase" | "decrease" | "set" | "unlock" | "spend" | "shift"
  label: string
  value?: string
  evidence?: string
}

export type RpgTurnObservation = {
  turn_index: number
  player_action: string
  world_response: string
  options: string[]
  state_deltas: RpgStateDelta[]
  clue_unlocks: string[]
  opportunity_unlocks: string[]
  referenced_entity_ids: string[]
  terminal?: boolean
  objective_progress: number
  progress_basis?: "runtime_reported" | "turn_budget_proxy" | "unknown"
  memory: RpgMemorySnapshot
}

export type RpgEvaluationBundle = {
  schema_version: "rpg_evaluation_bundle.v1"
  run_id: string
  system_label: string
  locale: "en" | "zh" | "mixed"
  scenario: {
    scenario_id: string
    title: string
    genre: string
    objective: string
    turn_budget: number
    entity_ids: string[]
    boundaries: string[]
  }
  turns: RpgTurnObservation[]
}

export type RpgCriterion = {
  criterion:
    | "memory_continuity"
    | "memory_boundedness"
    | "consequence_visibility"
    | "player_agency"
    | "trajectory_progress"
    | "entity_coherence"
    | "choice_diversity"
    | "boundary_hygiene"
  status: EvaluationStatus
  score: number
  summary: string
  evidence: string[]
}

export type RpgEvaluationReport = {
  schema_version: "rpg_evaluation_report.v1"
  run_id: string
  system_label: string
  status: EvaluationStatus
  score: number
  criteria: RpgCriterion[]
  limitations: string[]
}

const TECHNICAL_LEAK = /\b(provider|model id|api key|schema|token count|chain[- ]of[- ]thought|scratchpad|raw json|fallback_used)\b/i

function statusFor(score: number): EvaluationStatus {
  if (score >= 80) return "pass"
  if (score >= 55) return "warn"
  return "fail"
}

function criterion(
  name: RpgCriterion["criterion"],
  score: number,
  summary: string,
  evidence: string[],
): RpgCriterion {
  const boundedScore = Math.max(0, Math.min(100, Math.round(score)))
  return { criterion: name, status: statusFor(boundedScore), score: boundedScore, summary, evidence: evidence.slice(0, 6) }
}

export function evaluateRpgBundle(bundle: RpgEvaluationBundle): RpgEvaluationReport {
  const turns = bundle.turns
  const memoryConflicts: string[] = []
  const memoryOverflow: string[] = []
  const consequenceGaps: string[] = []
  const agencyGaps: string[] = []
  const entityGaps: string[] = []
  const leakage: string[] = []
  const optionSignatures = new Set<string>()
  let previousProgress = 0
  let progressAdvances = 0
  let progressRegressions = 0
  const progressBases = new Set<string>()

  for (const turn of turns) {
    progressBases.add(turn.progress_basis ?? "unknown")
    const activeKeys = new Set<string>()
    const supersededIds = new Set(turn.memory.superseded_facts.map((fact) => fact.fact_id))
    for (const fact of turn.memory.active_facts) {
      const key = `${fact.namespace.toLowerCase()}:${fact.key.toLowerCase()}`
      if (activeKeys.has(key)) memoryConflicts.push(`Turn ${turn.turn_index}: duplicate active fact ${fact.namespace}.${fact.key}`)
      activeKeys.add(key)
      if (fact.status !== "active" || supersededIds.has(fact.fact_id)) {
        memoryConflicts.push(`Turn ${turn.turn_index}: superseded fact remained active`)
      }
    }
    if (turn.memory.active_facts.length > 24 || turn.memory.recent_events.length > 8) {
      memoryOverflow.push(`Turn ${turn.turn_index}: memory exceeded the portable budget`)
    }
    if (turn.state_deltas.length + turn.clue_unlocks.length + turn.opportunity_unlocks.length === 0) {
      consequenceGaps.push(`Turn ${turn.turn_index}: no typed visible consequence`)
    }
    const options = turn.options.map((option) => option.trim().toLowerCase())
    if (!turn.terminal && new Set(options).size < 2) agencyGaps.push(`Turn ${turn.turn_index}: fewer than two distinct options`)
    if (!turn.terminal && options.length > 0) optionSignatures.add(options.join("|"))
    const unknown = turn.referenced_entity_ids.filter((id) => !bundle.scenario.entity_ids.includes(id))
    if (unknown.length > 0) entityGaps.push(`Turn ${turn.turn_index}: unknown entities ${unknown.join(", ")}`)
    if (TECHNICAL_LEAK.test([turn.player_action, turn.world_response, ...turn.options].join(" "))) {
      leakage.push(`Turn ${turn.turn_index}: technical wording appeared in player-facing text`)
    }
    if (turn.objective_progress + 0.001 < previousProgress) progressRegressions += 1
    else if (turn.objective_progress > previousProgress + 0.05) progressAdvances += 1
    previousProgress = Math.max(previousProgress, turn.objective_progress)
  }

  const denominator = Math.max(1, turns.length)
  const nonTerminalTurns = turns.filter((turn) => !turn.terminal).length
  const choiceDiversityScore = nonTerminalTurns > 0
    ? Math.min(100, 100 * optionSignatures.size / nonTerminalTurns)
    : 55
  const playerAgencyScore = nonTerminalTurns > 0
    ? 100 * (nonTerminalTurns - agencyGaps.length) / nonTerminalTurns
    : 55
  const criteria: RpgCriterion[] = [
    criterion("memory_continuity", 100 - memoryConflicts.length * 35,
      memoryConflicts.length === 0 ? "Corrections remain auditable without conflicting active facts." : "Active and superseded facts conflict.",
      memoryConflicts.length > 0 ? memoryConflicts : [`${turns.length} snapshots checked with no active fact conflict.`]),
    criterion("memory_boundedness", 100 - memoryOverflow.length * 40,
      memoryOverflow.length === 0 ? "Memory stays inside the portable fact and recency budgets." : "At least one memory snapshot exceeded its budget.",
      memoryOverflow.length > 0 ? memoryOverflow : ["Active facts <= 24 and recent events <= 8 for every turn."]),
    criterion("consequence_visibility", 100 * (turns.length - consequenceGaps.length) / denominator,
      consequenceGaps.length === 0 ? "Moves resolve into visible state changes, clues, or opportunities." : "Some moves produced prose without a visible game-state consequence.",
      consequenceGaps.length > 0 ? consequenceGaps : [`All ${turns.length} turns expose a typed consequence.`]),
    criterion("player_agency", playerAgencyScore,
      nonTerminalTurns === 0
        ? "A terminal-only run has insufficient evidence for player agency."
        : agencyGaps.length === 0
          ? "Every turn preserves at least two distinct next actions."
          : "At least one turn collapsed into duplicated or singular choice.",
      agencyGaps.length > 0 ? agencyGaps : [`Distinct choices preserved across ${nonTerminalTurns} non-terminal turns.`]),
    criterion("trajectory_progress", previousProgress * 70 + Math.min(30, progressAdvances * 10) - progressRegressions * 25,
      progressRegressions === 0 ? "Reported or explicitly proxied progress advances without unexplained regression." : "Objective progress regressed on at least one turn.",
      [`Final observed progress: ${Math.round(previousProgress * 100)}%.`, `Meaningful advances: ${progressAdvances}; regressions: ${progressRegressions}.`, `Progress basis: ${[...progressBases].sort().join(", ")}.`]),
    criterion("entity_coherence", 100 - entityGaps.length * 35,
      entityGaps.length === 0 ? "People and factions stay inside the scenario registry." : "The run referenced entities outside the scenario contract.",
      entityGaps.length > 0 ? entityGaps : [`Validated against ${bundle.scenario.entity_ids.length} registered entities.`]),
    criterion("choice_diversity", choiceDiversityScore,
      nonTerminalTurns === 0
        ? "A terminal-only run has insufficient evidence for choice diversity."
        : optionSignatures.size === nonTerminalTurns
          ? "Next-action sets change with the trajectory."
          : "Some turns repeated the same full action set.",
      [`${optionSignatures.size} distinct action sets across ${nonTerminalTurns} non-terminal turns.`]),
    criterion("boundary_hygiene", 100 - leakage.length * 50,
      leakage.length === 0 ? "Player-facing text is free of protocol and private-reasoning language." : "Technical implementation wording leaked into player-facing text.",
      leakage.length > 0 ? leakage : ["No provider, schema, token, raw JSON, or private-reasoning terms detected."]),
  ]
  const score = Math.round(criteria.reduce((sum, item) => sum + item.score, 0) / criteria.length)
  return {
    schema_version: "rpg_evaluation_report.v1",
    run_id: bundle.run_id,
    system_label: bundle.system_label,
    status: statusFor(score),
    score,
    criteria,
    limitations: [
      "This deterministic report is a product reliability diagnostic, not a calibrated research metric.",
      "Narrative appeal and emotional quality still require bounded human review.",
      "Imported state deltas are only as trustworthy as the source adapter.",
      ...(progressBases.has("turn_budget_proxy")
        ? ["Trajectory progress for this run uses elapsed turn budget as a proxy, not model-reported goal completion."]
        : []),
    ],
  }
}

export function isRpgEvaluationBundle(value: unknown): value is RpgEvaluationBundle {
  if (!value || typeof value !== "object") return false
  const candidate = value as Partial<RpgEvaluationBundle>
  return candidate.schema_version === "rpg_evaluation_bundle.v1"
    && typeof candidate.run_id === "string"
    && typeof candidate.system_label === "string"
    && Boolean(candidate.scenario && typeof candidate.scenario === "object")
    && Array.isArray(candidate.turns)
    && candidate.turns.length > 0
}

export function isRpgEvaluationReport(value: unknown): value is RpgEvaluationReport {
  if (!value || typeof value !== "object") return false
  const candidate = value as Partial<RpgEvaluationReport>
  return candidate.schema_version === "rpg_evaluation_report.v1"
    && typeof candidate.run_id === "string"
    && typeof candidate.score === "number"
    && Array.isArray(candidate.criteria)
    && candidate.criteria.length === 8
}
