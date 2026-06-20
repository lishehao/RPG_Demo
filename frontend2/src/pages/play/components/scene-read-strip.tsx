import type { NarrativeNPCPulse } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"
import type { LeverageCardView } from "../play-types"

export type SceneClockView = {
  label: string
  value: string
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

export function buildSceneClocks({
  turnsCompleted,
  turnBudget,
  latestNpcPulses,
  leverageCards,
  t,
}: {
  turnsCompleted: number
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

export function SceneReadStrip({
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
    <div
      style={ppStyles.sceneReadStrip}
      aria-label={t("play.scene_read_label")}
      data-play-scene-read-strip="true"
    >
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
