import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"

export function SelectedMoveConfirmationReadout({
  moveNumber,
  targetName,
  summary,
}: {
  moveNumber: number
  targetName?: string | null
  summary: string
}) {
  const t = useT()

  return (
    <>
      <span style={ppStyles.optionCardConfirmMeta}>
        {t("play.selected_move_number", { index: moveNumber })}
      </span>
      <span
        style={ppStyles.optionCardSubmitSummary}
        data-play-selected-move-submit-summary="true"
      >
        <span style={ppStyles.optionCardSubmitSummaryHead}>
          <span style={ppStyles.optionCardSubmitSummaryLabel}>
            {t("play.selected_move_ready_label")}
          </span>
          <span style={ppStyles.optionCardSubmitSummaryTarget}>
            {targetName
              ? t("play.selected_move_target_chip", { target: targetName })
              : t("play.selected_move_room_chip")}
          </span>
        </span>
        <span style={ppStyles.optionCardSubmitSummaryText} title={summary}>
          {summary}
        </span>
      </span>
    </>
  )
}
