import { motion } from "motion/react"
import type { GameplayActionForecast } from "../play-gameplay-envelope"
import { ppStyles } from "../play-styles"
import { useT } from "../../../shared/lib/i18n"

type DecisionForecastGroup = "cost" | "upside" | "shift"

type ActionTargetView = {
  id: string
  name: string
}

type ActionIntentGuideView = {
  tag: string
  description: string
}

function decisionForecastGroupForChip(chip: GameplayActionForecast): DecisionForecastGroup {
  if (chip.tone === "cost") return "cost"
  if (chip.tone === "gain" || chip.tone === "unlock") return "upside"
  return "shift"
}

function forecastToneStyle(chip: GameplayActionForecast) {
  if (chip.tone === "gain") return ppStyles.gameplayToneGain
  if (chip.tone === "cost") return ppStyles.gameplayToneCost
  if (chip.tone === "unlock") return ppStyles.gameplayToneUnlock
  return {}
}

function forecastChipReadableText(chip: GameplayActionForecast) {
  return chip.detail ? `${chip.label}: ${chip.detail}` : chip.label
}

function normalizeForecastEchoText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9+\-\s]+/gi, " ").replace(/\s+/g, " ").trim()
}

function hintEchoesForecastChips(value: string, forecasts: GameplayActionForecast[]) {
  const normalizedHint = normalizeForecastEchoText(value)
  const normalizedLabels = forecasts
    .map((chip) => normalizeForecastEchoText(chip.label))
    .filter(Boolean)
  if (!normalizedHint || normalizedLabels.length === 0) return false
  if (normalizedLabels.includes(normalizedHint)) return true
  const remainder = normalizedLabels.reduce(
    (remaining, label) => remaining.replace(label, " "),
    normalizedHint,
  ).replace(/\s+/g, "").trim()
  return remainder.length <= 2
}

export function ActionDecisionForecast({
  chips,
  compact,
  detail,
}: {
  chips: GameplayActionForecast[]
  compact?: boolean
  detail?: boolean
}) {
  const t = useT()
  if (!chips.length) return null
  const visibleChips = chips.filter((chip) => !chip.detail)
  if (!visibleChips.length) return null
  const labelForGroup = (group: DecisionForecastGroup) => {
    if (group === "cost") return t("play.gameplay_decision_cost_label")
    if (group === "upside") return t("play.gameplay_decision_upside_label")
    return t("play.gameplay_decision_shift_label")
  }
  const groups: Array<{ id: DecisionForecastGroup; chips: GameplayActionForecast[] }> = [
    { id: "cost" as const, chips: visibleChips.filter((chip) => decisionForecastGroupForChip(chip) === "cost") },
    { id: "upside" as const, chips: visibleChips.filter((chip) => decisionForecastGroupForChip(chip) === "upside") },
    { id: "shift" as const, chips: visibleChips.filter((chip) => decisionForecastGroupForChip(chip) === "shift") },
  ].filter((group) => group.chips.length > 0)
  const forecastReadableLabel = [
    t("play.gameplay_decision_forecast_label"),
    ...groups.flatMap((group) =>
      group.chips.map((chip) => `${labelForGroup(group.id)}: ${forecastChipReadableText(chip)}`),
    ),
  ].join(". ")

  return (
    <span
      style={{
        ...ppStyles.gameplayDecisionForecast,
        ...(compact ? ppStyles.gameplayDecisionForecastCompact : null),
        ...(detail ? ppStyles.gameplayDecisionForecastDetail : null),
      }}
      data-gameplay-decision-forecast="true"
      data-gameplay-decision-forecast-readable-label={forecastReadableLabel}
      aria-label={forecastReadableLabel}
    >
      <span style={ppStyles.gameplayDecisionForecastHeader}>
        {t("play.gameplay_decision_forecast_label")}
      </span>
      <span
        style={{
          ...ppStyles.gameplayDecisionGroups,
          ...(compact ? ppStyles.gameplayDecisionGroupsCompact : null),
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
              {labelForGroup(group.id)}
            </span>
            <span style={ppStyles.gameplayDecisionChipRow}>
              {group.chips.map((chip) => (
                <span
                  key={`${group.id}-${chip.label}`}
                  title={chip.detail ? `${chip.label}: ${chip.detail}` : chip.label}
                  aria-label={chip.detail ? `${chip.label}: ${chip.detail}` : chip.label}
                  style={{
                    ...ppStyles.gameplayForecastChip,
                    ...forecastToneStyle(chip),
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
}

export function ActionCollapsedForecast({ chips }: { chips: GameplayActionForecast[] }) {
  const t = useT()
  if (!chips.length) return null
  const reasonChip = chips.find((chip) => chip.detail)
  const visibleChips = chips.filter((chip) => !chip.detail).slice(0, 3)
  const forecastReadableLabel = [
    t("play.gameplay_decision_forecast_label"),
    ...visibleChips.map(forecastChipReadableText),
    ...(reasonChip?.detail ? [`${t("play.gameplay_forecast_detail_label")}: ${reasonChip.detail}`] : []),
  ].join(". ")
  return (
    <span
      style={{
        ...ppStyles.gameplayForecastInline,
        ...(reasonChip?.detail ? ppStyles.gameplayForecastInlineWithReason : null),
      }}
      data-gameplay-action-forecast-summary="true"
      data-gameplay-action-forecast-summary-readable-label={forecastReadableLabel}
      aria-label={forecastReadableLabel}
    >
      <span style={ppStyles.gameplayForecastInlineChips}>
        <span style={ppStyles.gameplayForecastInlineLabel}>
          {t("play.option_forecast_kicker")}
        </span>
        <span style={ppStyles.gameplayForecastChipRow}>
          {visibleChips.map((chip) => (
            <span
              key={`forecast-summary-${chip.label}`}
              title={chip.detail ? `${chip.label}: ${chip.detail}` : chip.label}
              aria-label={chip.detail ? `${chip.label}: ${chip.detail}` : chip.label}
              style={{
                ...ppStyles.gameplayForecastChip,
                ...forecastToneStyle(chip),
              }}
              data-gameplay-forecast-chip="normal-play"
            >
              {chip.label}
            </span>
          ))}
        </span>
      </span>
      {reasonChip?.detail ? (
        <span
          style={ppStyles.gameplayForecastReasonPreview}
          data-gameplay-forecast-reason-preview="normal-play"
          aria-label={`${t("play.gameplay_forecast_detail_label")}: ${reasonChip.detail}`}
          title={reasonChip.detail}
        >
          <span style={ppStyles.gameplayForecastReasonLabel}>
            {t("play.gameplay_forecast_detail_label")}
          </span>
          <span
            style={ppStyles.gameplayForecastReasonText}
            data-gameplay-forecast-reason-text="normal-play"
          >
            {t("play.gameplay_forecast_detail_preview")}
          </span>
        </span>
      ) : null}
    </span>
  )
}

export function ActionSelectedOptionDetail({
  hint,
  forecasts,
  target,
  intentGuide,
  compact,
  reducedMotion,
}: {
  hint: string
  forecasts: GameplayActionForecast[]
  target?: ActionTargetView | null
  intentGuide?: ActionIntentGuideView | null
  compact?: boolean
  reducedMotion?: boolean
}) {
  const t = useT()
  const forecastDetails = forecasts.filter((chip) => chip.detail)
  const showNarrativeResult = hint.trim().length > 0 && !hintEchoesForecastChips(hint, forecasts)
  return (
    <motion.span
      style={{
        ...ppStyles.optionExpandedDetail,
        ...(compact ? ppStyles.optionExpandedDetailCompact : null),
        ...(reducedMotion ? ppStyles.reducedMotionTransition : null),
      }}
      data-play-action-card-detail="true"
      initial={reducedMotion ? false : { opacity: 0, y: -4 }}
      animate={reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
      exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: -3 }}
      transition={reducedMotion ? { duration: 0.01 } : { duration: 0.16, ease: [0.22, 0.61, 0.36, 1] }}
    >
      <span
        style={ppStyles.optionExpandedDetailHeader}
        data-play-action-card-detail-heading="true"
      >
        {t("play.action_decision_check_label")}
      </span>
      {forecasts.length ? (
        <span
          style={{
            ...ppStyles.optionExpandedDetailSection,
            ...(compact ? ppStyles.optionExpandedDetailSectionCompact : null),
          }}
          data-play-action-card-detail-section="forecast"
        >
          <ActionDecisionForecast chips={forecasts} compact={compact} detail />
        </span>
      ) : null}
      {forecastDetails.map((chip) => (
        <span
          key={`${chip.label}-${chip.detail}`}
          style={{
            ...ppStyles.optionExpandedDetailSection,
            ...(compact ? ppStyles.optionExpandedDetailSectionCompact : null),
          }}
          data-play-action-card-detail-section="why-now"
        >
          <span style={ppStyles.optionExpandedDetailLabel}>
            {t("play.gameplay_forecast_detail_label")}
          </span>
          <span style={ppStyles.optionExpandedDetailBody}>
            <span
              style={ppStyles.optionExpandedDetailText}
              data-gameplay-forecast-detail="normal-play"
              title={chip.detail}
            >
              {chip.detail}
            </span>
          </span>
        </span>
      ))}
      {showNarrativeResult ? (
        <span
          style={{
            ...ppStyles.optionExpandedDetailSection,
            ...(compact ? ppStyles.optionExpandedDetailSectionCompact : null),
          }}
          data-play-action-card-detail-section="result"
        >
          <span style={ppStyles.optionExpandedDetailLabel}>
            {t("play.option_expanded_result_label")}
          </span>
          <span style={ppStyles.optionExpandedDetailText}>
            {hint}
          </span>
        </span>
      ) : null}
      {target ? (
        <span
          style={{
            ...ppStyles.optionExpandedDetailSection,
            ...(compact ? ppStyles.optionExpandedDetailSectionCompact : null),
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
      {intentGuide ? (
        <span
          style={{
            ...ppStyles.optionExpandedDetailSection,
            ...(compact ? ppStyles.optionExpandedDetailSectionCompact : null),
          }}
          data-play-action-card-detail-section="intent"
        >
          <span style={ppStyles.optionExpandedDetailLabel}>
            {t("play.option_intent_label")}
          </span>
          <span style={ppStyles.optionExpandedDetailBody}>
            <span
              style={ppStyles.optionExpandedDetailChip}
              data-play-action-intent-chip="true"
              title={intentGuide.description}
            >
              {intentGuide.tag}
            </span>
            <span
              style={ppStyles.optionExpandedDetailText}
              data-play-action-intent-detail="true"
            >
              {intentGuide.description}
            </span>
          </span>
        </span>
      ) : null}
    </motion.span>
  )
}
