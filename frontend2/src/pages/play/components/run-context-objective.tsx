import type { NarrativeStoryHistoryResponse } from "../../../api/contracts"
import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"

type PlayerRole = NonNullable<NarrativeStoryHistoryResponse["session"]["player_role"]>

export function RunContextObjective({
  role,
  compact = false,
}: {
  role: PlayerRole
  compact?: boolean
}) {
  const t = useT()

  if (compact) {
    return (
      <div style={ppStyles.runCompactObjective} data-play-run-objective="true">
        <strong style={ppStyles.runCompactObjectiveText}>
          {role.hidden_objective}
        </strong>
        <span style={ppStyles.runContextObjectiveHint} data-play-run-context-lens="true">
          {t("play.run_context_lens_hint")}
        </span>
      </div>
    )
  }

  return (
    <div style={ppStyles.runContextObjectiveLine} data-play-run-objective="true">
      <strong style={ppStyles.runContextObjectiveText}>{role.hidden_objective}</strong>
      <span style={ppStyles.runContextObjectiveHint} data-play-run-context-lens="true">
        {t("play.run_context_lens_hint")}
      </span>
    </div>
  )
}
