import type {
  NarrativeNPCPulse,
  NarrativePlayedLeverageCard,
  NarrativePlayerLeverageOverNPC,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../api/contracts"
import type { StringKey } from "../../shared/lib/i18n"

export type PlayAdvanceAction = {
  chosen_option_index?: number
  free_input?: string
  diary?: string
  played_leverage?: NarrativePlayedLeverageCard
}

export type LeverageCardView = {
  card_id: string
  npc_id: string
  target_name: string
  leverage: string
  used: boolean
}

export type ActionCommitmentSummary = {
  kind: "option" | "leverage" | "free"
  kicker: string
  title: string
  detail?: string
  motive?: string
}

export type FailedActionRecovery = {
  kicker: string
  title: string
  detail: string
  chips: string[]
}

export type IntentReadReceiptView = {
  publicMove: string
  privateIntent: string
  reaction: string
}

export type OutcomeReceiptTone = "safe" | "neutral" | "tense" | "danger" | "gold"

export type OutcomeReceiptItem = {
  label: string
  value: string
  tone?: OutcomeReceiptTone
}

export type SceneClockView = {
  label: string
  value: string
}

type PlayT = (
  key: StringKey,
  paramsOrFallback?: Record<string, string | number> | string,
  fallback?: string,
) => string

const SCAFFOLD_PARTY_DISPLAY_NAMES = new Set([
  "player",
  "mix-up witness",
  "embarrassed helper",
  "deadline host",
  "deadline holder",
  "concerned witness",
  "outside voice",
  "organizer",
])

export function leverageCardId(
  roleId: string | undefined,
  lev: NarrativePlayerLeverageOverNPC,
  index: number,
): string {
  return `lev:${roleId || "role"}:${lev.npc_id}:${index}`
}

export function leveragePlayInput(
  card: LeverageCardView,
  language: NarrativeStoryHistoryResponse["template"]["language"],
): string {
  if (language === "zh") {
    return `我亮出手里针对 ${card.target_name} 的把柄：${card.leverage}`
  }
  return `I reveal the leverage I hold over ${card.target_name}: ${card.leverage}`
}

export function isBackgroundStakeholder(
  member: NarrativeStoryHistoryResponse["template"]["cast"][number],
): boolean {
  const role = member.role.toLowerCase()
  const relation = member.relation_to_protagonist.toLowerCase()
  return role.includes("background stakeholder") || relation.includes("visible context")
}

export function isScaffoldPartyDisplayName(name: string): boolean {
  return SCAFFOLD_PARTY_DISPLAY_NAMES.has(name.trim().toLowerCase())
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

export function buildFailedActionRecovery({
  action,
  options,
  castNameById,
  t,
}: {
  action: PlayAdvanceAction | null
  options: NarrativeStoryMessage["options"]
  castNameById: Record<string, string>
  t: PlayT
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

export function stageForLocal(turnIndex: number, turnBudget: number): string {
  if (turnIndex <= 1) return "hook"
  const midpoint = turnBudget / 2
  if (turnIndex < midpoint - 0.5) return "pressure"
  if (turnIndex < midpoint + 0.5) return "reversal"
  if (turnIndex < turnBudget - 1) return "climax"
  if (turnIndex < turnBudget) return "pre_finale"
  return "pre_finale_open"
}

export function computeBeatIntensity(
  message: NarrativeStoryMessage,
  turnBudget: number,
): "calm" | "rising" | "peak" {
  if (message.role !== "narrator") return "calm"
  const turnIndex = Math.floor(message.ord / 2)
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

export function parseOptionLabel(label: string): { tag: string | null; body: string } {
  const m = label.match(/^\s*[\[【]([^\]】]{1,8})[\]】]\s*(.*)$/)
  if (m) {
    return { tag: m[1].trim(), body: (m[2] ?? "").trim() }
  }
  return { tag: null, body: label }
}

export function shiftArrow(shift: NarrativeNPCPulse["shift"]): string {
  switch (shift) {
    case "warmer": return "↗"
    case "colder": return "↘"
    case "wary":   return "⚠"
    case "broken": return "✕"
    case "steady":
    default:       return "—"
  }
}

export function pulseImpactLabel(
  shift: NarrativeNPCPulse["shift"],
  t: PlayT,
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

export function pulseDeltaLabel(
  shift: NarrativeNPCPulse["shift"],
  t: PlayT,
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

export function pulseNextMoveLabel(
  shift: NarrativeNPCPulse["shift"],
  t: PlayT,
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

export function outcomeToneForShift(shift: NarrativeNPCPulse["shift"]): OutcomeReceiptTone {
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

export function outcomePriority(shift: NarrativeNPCPulse["shift"]): number {
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

export function buildIntentReadReceipt({
  playerMessage,
  impactPulses,
  castNameById,
  t,
}: {
  playerMessage?: NarrativeStoryMessage
  impactPulses: NarrativeNPCPulse[]
  castNameById?: Record<string, string>
  t: PlayT
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

export function buildOutcomeReceiptItems({
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
  t: PlayT
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

  return items.slice(0, 4)
}

export function buildSceneClocks({
  turnsCompleted,
  turnsRemaining: _turnsRemaining,
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
  t: PlayT
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

export function findActionTarget(
  body: string,
  hint: string | undefined,
  castNameById: Record<string, string>,
  latestNpcPulses: NarrativeNPCPulse[],
): { name: string; pulse?: NarrativeNPCPulse } | null {
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
    name: matched.name,
    pulse: latestNpcPulses.find((pulse) => pulse.npc_id === matched.id),
  }
}

export function truncateRecoveryText(value: string, max = 64): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function truncateIntentSnippet(value: string, max = 118): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function inventoryOutcomeValue({
  delta,
  t,
}: {
  delta: NonNullable<NarrativeStoryMessage["inventory_delta"]>
  t: PlayT
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
