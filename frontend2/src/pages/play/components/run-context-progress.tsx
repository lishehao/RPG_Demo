import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"

export function RunContextProgressMeter({
  isComplete,
  turnsCompleted,
  turnBudget,
  stage,
}: {
  isComplete: boolean
  turnsCompleted: number
  turnBudget: number
  stage: string
}) {
  const t = useT()
  if (isComplete) return null

  const runProgressLabel = t("stage_bar.aria", {
    turn: turnsCompleted,
    total: turnBudget,
    stage,
  })
  const runProgressPercent = Math.max(
    0,
    Math.min(100, (turnsCompleted / Math.max(turnBudget, 1)) * 100),
  )

  return (
    <span
      style={ppStyles.runProgressTrack}
      role="progressbar"
      aria-label={runProgressLabel}
      aria-valuemin={0}
      aria-valuemax={turnBudget}
      aria-valuenow={turnsCompleted}
      data-play-run-progress="true"
    >
      <span
        style={{
          ...ppStyles.runProgressFill,
          width: `${runProgressPercent}%`,
        }}
      />
    </span>
  )
}
