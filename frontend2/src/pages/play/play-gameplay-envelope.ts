import type {
  NarrativeGameplayEnvelope,
  NarrativeNPCPulse,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
  NarrativeStoryOption,
} from "../../api/contracts"
import type { LeverageCardView } from "./play-types"

export type GameplayChipTone = "gain" | "cost" | "unlock" | "shift"

export type GameplayActionForecast = {
  label: string
  tone: GameplayChipTone
  detail?: string
}

export type GameplayPressureTrack = {
  id: string
  label: string
  value: string
  tone: GameplayChipTone
}

export type GameplayImpactDelta = {
  label: string
  tone: GameplayChipTone
}

export type GameplayEnvelope = {
  source: "backend" | "live_enriched" | "ui-derived"
  objective: string
  objectiveSource: "goal" | "role" | "story"
  tracks: GameplayPressureTrack[]
  actionForecasts: GameplayActionForecast[][]
  impact: GameplayImpactDelta[]
}

const NEGATIVE_SHIFTS = new Set(["colder", "wary", "broken"])
const POSITIVE_SHIFTS = new Set(["warmer"])
const CHIP_TONES = new Set<GameplayChipTone>(["gain", "cost", "unlock", "shift"])

function textOf(...parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join(" ").toLowerCase()
}

function compactLabel(value: string, max = 64): string {
  const oneLine = value.replace(/\s+/g, " ").trim()
  if (oneLine.length <= max) return oneLine
  return `${oneLine.slice(0, Math.max(0, max - 1)).trim()}…`
}

function normalizeInventoryItem(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase()
}

function addUniqueChip(
  chips: GameplayActionForecast[],
  label: string,
  tone: GameplayChipTone,
): void {
  if (chips.some((chip) => chip.label === label)) return
  chips.push({ label, tone })
}

function normalizeTone(value: unknown): GameplayChipTone {
  return typeof value === "string" && CHIP_TONES.has(value as GameplayChipTone)
    ? (value as GameplayChipTone)
    : "shift"
}

function normalizeChipRows(
  rows: NarrativeGameplayEnvelope["action_forecasts"],
  baseRows: GameplayActionForecast[][],
): GameplayActionForecast[][] {
  const rowCount = Math.max(baseRows.length, rows?.length ?? 0)
  return Array.from({ length: rowCount }, (_, index) => {
    const sourceRow = rows?.[index] ?? []
    const normalized = sourceRow
      .map((chip) => ({
        label: compactLabel(chip.label, 64),
        tone: normalizeTone(chip.tone),
        detail:
          typeof chip.detail === "string" && chip.detail.trim()
            ? compactLabel(chip.detail, 140)
            : undefined,
      }))
      .filter((chip) => chip.label.length > 0)
      .slice(0, 3)
    return normalized.length > 0 ? normalized : baseRows[index] ?? []
  })
}

function normalizeChipList(
  chips: NarrativeGameplayEnvelope["impact"],
  max = 6,
): GameplayImpactDelta[] {
  const normalized: GameplayImpactDelta[] = []
  for (const chip of chips ?? []) {
    const label = compactLabel(chip.label, 64)
    if (!label || normalized.some((item) => item.label === label)) continue
    normalized.push({ label, tone: normalizeTone(chip.tone) })
    if (normalized.length >= max) break
  }
  return normalized
}

function chipInventoryValue(label: string, prefix: "Evidence" | "Clue" | "Spent"): string | null {
  const match = label.match(new RegExp(`^${prefix}:\\s*(.+)$`, "i"))
  return match?.[1]?.replace(/…$/u, "").trim() || null
}

function inventoryChipMatchesItem(chipValue: string, item: string): boolean {
  const normalizedChip = normalizeInventoryItem(chipValue)
  const normalizedItem = normalizeInventoryItem(item)
  if (!normalizedChip || !normalizedItem) return false
  return (
    normalizedChip === normalizedItem ||
    normalizedItem.startsWith(normalizedChip) ||
    normalizedChip.startsWith(normalizedItem)
  )
}

function isStaleInventoryChip(
  label: string,
  rawInventoryDelta: NarrativeStoryMessage["inventory_delta"],
  effectiveInventoryDelta: NarrativeStoryMessage["inventory_delta"],
): boolean {
  if (!rawInventoryDelta || !effectiveInventoryDelta) return false
  const addedKeys = new Set(effectiveInventoryDelta.added.map(normalizeInventoryItem))
  const removedKeys = new Set(effectiveInventoryDelta.removed.map(normalizeInventoryItem))
  const staleAdded = rawInventoryDelta.added.filter(
    (item) => !addedKeys.has(normalizeInventoryItem(item)),
  )
  const staleRemoved = rawInventoryDelta.removed.filter(
    (item) => !removedKeys.has(normalizeInventoryItem(item)),
  )

  const evidenceValue = chipInventoryValue(label, "Evidence")
  if (evidenceValue && staleAdded.some((item) => inventoryChipMatchesItem(evidenceValue, item))) {
    return true
  }

  const clueValue = chipInventoryValue(label, "Clue")
  if (clueValue && staleAdded.some((item) => inventoryChipMatchesItem(clueValue, item))) {
    return true
  }

  const spentValue = chipInventoryValue(label, "Spent")
  if (spentValue && staleRemoved.some((item) => inventoryChipMatchesItem(spentValue, item))) {
    return true
  }

  return false
}

function stripStaleInventoryChips(
  chips: NarrativeGameplayEnvelope["impact"],
  rawInventoryDelta: NarrativeStoryMessage["inventory_delta"],
  effectiveInventoryDelta: NarrativeStoryMessage["inventory_delta"],
): NarrativeGameplayEnvelope["impact"] {
  if (!rawInventoryDelta || !effectiveInventoryDelta) return chips
  return (chips ?? []).filter(
    (chip) => !isStaleInventoryChip(chip.label, rawInventoryDelta, effectiveInventoryDelta),
  )
}

function isHoldingImpactChip(chip: GameplayImpactDelta): boolean {
  return /^Holding:/i.test(chip.label)
}

function shouldPreferBaseImpact(backendImpact: GameplayImpactDelta[], baseImpact: GameplayImpactDelta[]): boolean {
  if (backendImpact.length === 0) return false
  return (
    backendImpact.every(isHoldingImpactChip) &&
    baseImpact.some((chip) => chip.label === "New choices opened")
  )
}

function normalizeTrackList(
  tracks: NarrativeGameplayEnvelope["tracks"],
): GameplayPressureTrack[] {
  return (tracks ?? [])
    .map((track) => ({
      id: compactLabel(track.id, 40),
      label: compactLabel(track.label, 40),
      value: compactLabel(track.value, 80),
      tone: normalizeTone(track.tone),
    }))
    .filter((track) => track.id.length > 0 && track.label.length > 0 && track.value.length > 0)
    .slice(0, 6)
}

function normalizeBackendEnvelope(
  raw: NarrativeGameplayEnvelope | null | undefined,
  base: GameplayEnvelope,
  rawInventoryDelta: NarrativeStoryMessage["inventory_delta"],
  effectiveInventoryDelta: NarrativeStoryMessage["inventory_delta"],
): GameplayEnvelope | null {
  if (!raw || (raw.source !== "backend" && raw.source !== "live_enriched")) return null
  const tracks = normalizeTrackList(raw.tracks)
  const impact = normalizeChipList(
    stripStaleInventoryChips(raw.impact, rawInventoryDelta, effectiveInventoryDelta),
  )
  const opportunities = normalizeChipList(
    stripStaleInventoryChips(raw.opportunities, rawInventoryDelta, effectiveInventoryDelta),
  )
  const mergedImpact = normalizeChipList([...impact, ...opportunities], 6)
  const resolvedImpact = shouldPreferBaseImpact(mergedImpact, base.impact)
    ? base.impact
    : mergedImpact
  const hasBackendShape =
    Boolean(raw.objective && raw.objective.trim()) ||
    tracks.length > 0 ||
    impact.length > 0 ||
    opportunities.length > 0 ||
    (raw.action_forecasts ?? []).some((row) => row.length > 0)

  if (!hasBackendShape) return null

  return {
    ...base,
    source: raw.source,
    objective: raw.objective ? compactLabel(raw.objective, 92) : base.objective,
    tracks: tracks.length > 0 ? tracks : base.tracks,
    actionForecasts: normalizeChipRows(raw.action_forecasts, base.actionForecasts),
    impact: resolvedImpact.length > 0 ? resolvedImpact.slice(0, 3) : base.impact,
  }
}

export function deriveActionForecastChips(option: NarrativeStoryOption): GameplayActionForecast[] {
  const haystack = textOf(option.label, option.hint, option.handle)
  const chips: GameplayActionForecast[] = []

  if (/\b(wait|watch|stall|delay|countdown|time|minute|clock|search|check|look|scan|follow|trail|quiet)\b/.test(haystack)) {
    addUniqueChip(chips, "Time -1", "cost")
  }
  if (/\b(confront|challenge|accuse|expose|reveal|public|announce|pressure|push|force|demand|call out|interrupt)\b/.test(haystack)) {
    addUniqueChip(chips, "Pressure +1", "cost")
  }
  if (/\b(trust|calm|cover|protect|help|ally|promise|reassure|soften|support)\b/.test(haystack)) {
    addUniqueChip(chips, "Trust +1", "gain")
  }
  if (/\b(ask|probe|question|interview|witness|account|source|handled|last seen|saw)\b/.test(haystack)) {
    addUniqueChip(chips, "May reveal evidence", "unlock")
  }
  if (/\b(clue|evidence|proof|recording|footage|badge|phone|message|lead|find|discover|document|receipt)\b/.test(haystack)) {
    addUniqueChip(chips, "May reveal evidence", "unlock")
  }
  if (/\b(leverage|trump|blackmail|secret|threat|trade|bargain|deal)\b/.test(haystack)) {
    addUniqueChip(chips, "Use leverage", "unlock")
  }
  if (/\b(risk|danger|escalate|reckless|storm|break|shatter|corner|trap)\b/.test(haystack)) {
    addUniqueChip(chips, "Risk +1", "cost")
  }

  if (chips.length === 0) {
    addUniqueChip(chips, "Read the room", "shift")
  }
  return chips.slice(0, 3)
}

function pressureLabelFromPulses(pulses: NarrativeNPCPulse[]): GameplayPressureTrack {
  const dangerCount = pulses.filter((pulse) => NEGATIVE_SHIFTS.has(pulse.shift)).length
  const warmerCount = pulses.filter((pulse) => POSITIVE_SHIFTS.has(pulse.shift)).length
  if (dangerCount > 0) {
    return { id: "pressure", label: "Pressure", value: "rising", tone: "cost" }
  }
  if (warmerCount > 0) {
    return { id: "pressure", label: "Pressure", value: "opening", tone: "gain" }
  }
  return { id: "pressure", label: "Pressure", value: "held", tone: "shift" }
}

function personTrackFromPulses(pulses: NarrativeNPCPulse[], castNameById: Record<string, string>): GameplayPressureTrack {
  const named = pulses
    .map((pulse) => castNameById[pulse.npc_id])
    .filter((name): name is string => Boolean(name))
  if (named.length > 0) {
    return {
      id: "people",
      label: "People",
      value: compactLabel(named.slice(0, 2).join(" / "), 34),
      tone: "shift",
    }
  }
  return { id: "people", label: "People", value: "watching", tone: "shift" }
}

function turnsLeftTrackValue(turnsRemaining: number): string {
  const count = Math.max(0, turnsRemaining)
  return count === 1 ? "1 turn left" : `${count} turns left`
}

function objectiveForStory(story: NarrativeStoryHistoryResponse): Pick<GameplayEnvelope, "objective" | "objectiveSource"> {
  const firstGoal = story.template.player_goals?.[0]?.goal
  if (firstGoal) {
    return { objective: compactLabel(firstGoal, 92), objectiveSource: "goal" }
  }
  const roleObjective = story.session.player_role?.hidden_objective
  if (roleObjective) {
    return { objective: compactLabel(roleObjective, 92), objectiveSource: "role" }
  }
  return {
    objective: compactLabel(story.template.seed || story.template.title || "Steer the scene toward a playable ending.", 92),
    objectiveSource: "story",
  }
}

function buildImpactDeltas(
  narratorMessage: NarrativeStoryMessage | null,
  previousPlayerMessage: NarrativeStoryMessage | null,
  liveInventory: string[],
  castNameById: Record<string, string>,
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"],
): GameplayImpactDelta[] {
  const deltas: GameplayImpactDelta[] = []

  for (const pulse of narratorMessage?.npc_pulse ?? []) {
    const name = castNameById[pulse.npc_id] ?? "Someone"
    const tone: GameplayChipTone = POSITIVE_SHIFTS.has(pulse.shift)
      ? "gain"
      : NEGATIVE_SHIFTS.has(pulse.shift)
        ? "cost"
        : "shift"
    deltas.push({ label: `${name}: ${pulse.shift}`, tone })
  }

  const inventoryDelta = effectiveInventoryDelta ?? narratorMessage?.inventory_delta
  for (const item of inventoryDelta?.added ?? []) {
    deltas.push({ label: `Evidence: ${compactLabel(item, 30)}`, tone: "unlock" })
  }
  for (const item of inventoryDelta?.removed ?? []) {
    deltas.push({ label: `Spent: ${compactLabel(item, 30)}`, tone: "cost" })
  }

  if (previousPlayerMessage?.played_leverage) {
    deltas.push({ label: "Leverage played", tone: "unlock" })
  }

  if (deltas.length === 0 && narratorMessage && narratorMessage.options.length > 0) {
    deltas.push({ label: "New choices opened", tone: "shift" })
  }
  if (deltas.length === 0 && liveInventory.length > 0) {
    deltas.push({ label: `Holding: ${compactLabel(liveInventory[0], 30)}`, tone: "shift" })
  }

  return deltas.slice(0, 3)
}

export function buildGameplayEnvelope({
  story,
  lastNarrator,
  previousPlayerMessage,
  turnsCompleted,
  turnsRemaining,
  turnBudget,
  liveInventory,
  effectiveInventoryDelta,
  leverageCards,
  castNameById,
  backendEnvelope,
}: {
  story: NarrativeStoryHistoryResponse
  lastNarrator: NarrativeStoryMessage | null
  previousPlayerMessage: NarrativeStoryMessage | null
  turnsCompleted: number
  turnsRemaining: number
  turnBudget: number
  liveInventory: string[]
  effectiveInventoryDelta?: NarrativeStoryMessage["inventory_delta"]
  leverageCards: LeverageCardView[]
  castNameById: Record<string, string>
  backendEnvelope?: NarrativeGameplayEnvelope | null
}): GameplayEnvelope {
  const objective = objectiveForStory(story)
  const pulses = lastNarrator?.npc_pulse ?? []
  const playableLeverageCount = leverageCards.filter((card) => !card.used).length
  const evidenceValue =
    liveInventory.length > 0
      ? `${liveInventory.length} held`
      : playableLeverageCount > 0
        ? `${playableLeverageCount} card${playableLeverageCount === 1 ? "" : "s"}`
        : "none"
  const actionForecasts = (lastNarrator?.options ?? []).map(deriveActionForecastChips)

  const baseEnvelope: GameplayEnvelope = {
    source: "ui-derived",
    ...objective,
    tracks: [
      {
        id: "time",
        label: "Time",
        value: turnsLeftTrackValue(turnsRemaining),
        tone: turnsRemaining <= 2 && turnsCompleted > 0 ? "cost" : "shift",
      },
      pressureLabelFromPulses(pulses),
      personTrackFromPulses(pulses, castNameById),
      {
        id: "evidence",
        label: "Evidence",
        value: evidenceValue,
        tone: liveInventory.length > 0 || playableLeverageCount > 0 ? "unlock" : "shift",
      },
    ],
    actionForecasts,
    impact: buildImpactDeltas(lastNarrator, previousPlayerMessage, liveInventory, castNameById, effectiveInventoryDelta),
  }

  return normalizeBackendEnvelope(
    backendEnvelope,
    baseEnvelope,
    lastNarrator?.inventory_delta ?? null,
    effectiveInventoryDelta ?? null,
  ) ?? baseEnvelope
}
