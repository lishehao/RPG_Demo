import { useT } from "../../../shared/lib/i18n"
import { ppStyles } from "../play-styles"

export function LeverageEmptySummary({
  title,
  metaText,
  badge,
}: {
  title: string
  metaText: string
  badge: string
}) {
  const t = useT()

  return (
    <div style={ppStyles.leverageEmptySummary}>
      <span style={ppStyles.leverageSummaryMain}>
        <span style={ppStyles.leverageSummaryEyebrow}>{t("play.leverage_resource_label")}</span>
        <strong style={ppStyles.leverageSummaryText}>{title}</strong>
        <span style={ppStyles.leverageSummaryMeta} title={metaText}>
          {metaText}
        </span>
      </span>
      <span style={ppStyles.leverageEmptyBadge}>{badge}</span>
    </div>
  )
}

export function LeverageSummaryButton({
  text,
  metaText,
  showChips,
  chipTarget,
  toggleText,
  expanded,
  compact,
  disabled,
  onActivate,
}: {
  text: string
  metaText: string
  showChips: boolean
  chipTarget: string
  toggleText: string
  expanded: boolean
  compact: boolean
  disabled: boolean
  onActivate: () => void
}) {
  const t = useT()

  return (
    <button
      type="button"
      data-play-leverage-summary="true"
      style={{
        ...ppStyles.leverageSummaryButton,
        ...(expanded ? ppStyles.leverageSummaryButtonOpen : null),
        ...(compact ? ppStyles.leverageSummaryButtonCompact : null),
      }}
      onClick={onActivate}
      disabled={disabled}
      aria-expanded={expanded}
      aria-keyshortcuts="T"
      title={t("play.leverage_shortcut_title")}
    >
      <span style={ppStyles.leverageSummaryMain}>
        <span style={ppStyles.leverageSummaryEyebrow}>{t("play.leverage_resource_label")}</span>
        <strong style={ppStyles.leverageSummaryText}>{text}</strong>
        <span style={ppStyles.leverageSummaryMeta} title={metaText}>{metaText}</span>
        {showChips ? (
          <span style={ppStyles.leverageSummaryChips} data-play-leverage-summary-chips="true">
            <span style={ppStyles.leverageSummaryChip}>
              <span style={ppStyles.leverageSummaryChipLabel}>{t("play.leverage_summary_chip_target")}</span>
              <strong style={ppStyles.leverageSummaryChipValue}>{chipTarget}</strong>
            </span>
            <span style={ppStyles.leverageSummaryChip}>
              <span style={ppStyles.leverageSummaryChipLabel}>{t("play.leverage_summary_chip_risk")}</span>
              <strong style={ppStyles.leverageSummaryChipValue}>{t("play.leverage_card_risk")}</strong>
            </span>
          </span>
        ) : null}
      </span>
      <span
        style={{
          ...ppStyles.leverageSummaryToggle,
          ...(compact ? ppStyles.leverageSummaryToggleCompact : null),
        }}
      >
        {toggleText}
      </span>
    </button>
  )
}
