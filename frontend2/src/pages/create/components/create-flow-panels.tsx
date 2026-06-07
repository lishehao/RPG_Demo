import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import type { NarrativeStoryBrief } from "../../../api/contracts"
import { useT, type StringKey } from "../../../shared/lib/i18n"
import { transitions } from "../../../shared/lib/motion-presets"
import type { StoryGuideInlineLedger } from "../../../shared/lib/story-guide-loop"
import type { StoryShapeRead } from "../create-types"
import { busyStageStyles, busyTipStyles, cpStyles } from "../create-styles"

const TENSION_PROFILE_LABEL_KEYS: Record<NarrativeStoryBrief["tension_profile"], StringKey> = {
  high_drama: "create.brief_profile_high_drama",
  cozy_mystery: "create.brief_profile_cozy_mystery",
  comedy: "create.brief_profile_comedy",
  fantasy_sci_fi: "create.brief_profile_fantasy_sci_fi",
  family_social: "create.brief_profile_family_social",
}

const FIT_STATUS_LABEL_KEYS: Record<NarrativeStoryBrief["runtime_fit_status"], StringKey> = {
  fit: "create.brief_fit",
  needs_revision: "create.brief_needs_revision",
  not_fit: "create.brief_not_fit",
}

const CONSTRAINT_DISPOSITION_LABEL_KEYS = {
  preserved: "create.brief_preserved",
  compressed: "create.brief_compressed",
  dropped: "create.brief_dropped",
  softened: "create.brief_softened",
} as const

// Rotating creative tips while user waits 5-10s for opening to generate.
// Reads as "the AI is doing real work, here's what" instead of static
// "loading..." which feels frozen at second 6.
const BUSY_TIP_KEYS: StringKey[] = [
  "create.busy_tip_1",
  "create.busy_tip_2",
  "create.busy_tip_3",
  "create.busy_tip_4",
  "create.busy_tip_5",
]

const BUSY_STAGE_KEYS: StringKey[] = [
  "create.busy_stage_cast",
  "create.busy_stage_leverage",
  "create.busy_stage_opening",
  "create.busy_stage_ready",
]
export const BUSY_STAGE_COUNT = BUSY_STAGE_KEYS.length

export function BusyStages({ activeIndex, compact }: { activeIndex: number; compact: boolean }) {
  const t = useT()
  return (
    <div
      style={{
        ...busyStageStyles.rail,
        ...(compact ? busyStageStyles.railCompact : null),
      }}
      aria-label={t("create.busy_stage_aria")}
    >
      {BUSY_STAGE_KEYS.map((key, index) => {
        const complete = index < activeIndex
        const active = index === activeIndex
        return (
          <span
            key={key}
            style={{
              ...busyStageStyles.stage,
              ...(compact ? busyStageStyles.stageCompact : null),
              ...(complete ? busyStageStyles.stageComplete : null),
              ...(active ? busyStageStyles.stageActive : null),
            }}
          >
            <span style={busyStageStyles.stageMark} aria-hidden>
              {complete ? "✓" : index + 1}
            </span>
            <span style={busyStageStyles.stageText}>{t(key)}</span>
          </span>
        )
      })}
    </div>
  )
}

export function BusyTip() {
  const t = useT()
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setIdx((v) => (v + 1) % BUSY_TIP_KEYS.length), 2200)
    return () => clearInterval(id)
  }, [])
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={idx}
        style={busyTipStyles.tip}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={transitions.base}
      >
        {t(BUSY_TIP_KEYS[idx])}
      </motion.div>
    </AnimatePresence>
  )
}

export function GuideInlineLedger({
  ledger,
  compact,
}: {
  ledger: StoryGuideInlineLedger
  compact: boolean
}) {
  return (
    <div style={{ ...cpStyles.guideLoopLedger, ...(compact ? cpStyles.guideLoopLedgerCompact : null) }}>
      <span style={cpStyles.guideLoopLedgerRow}>
        <strong>{ledger.knownLabel}</strong>
        <span>{ledger.known}</span>
      </span>
      <span style={cpStyles.guideLoopLedgerRow}>
        <strong>{ledger.stillNeedLabel}</strong>
        <span>{ledger.stillNeed}</span>
      </span>
      <span style={{ ...cpStyles.guideLoopLedgerRow, ...cpStyles.guideLoopLedgerQuestion }}>
        <strong>{ledger.nextQuestionLabel}</strong>
        <span>{ledger.nextQuestion}</span>
      </span>
    </div>
  )
}

export function StoryShapeReadLedger({
  shapeRead,
  compact,
  inBrief = false,
}: {
  shapeRead: StoryShapeRead
  compact: boolean
  inBrief?: boolean
}) {
  const t = useT()
  const rows = [
    { label: t("create.setting_run_length"), value: shapeRead.runLength },
    { label: t("create.setting_pressure_mode"), value: shapeRead.pressureMode },
    { label: t("create.setting_story_language"), value: shapeRead.storyLanguage },
    { label: t("create.setting_tone"), value: shapeRead.tone },
  ]
  return (
    <div
      style={{
        ...cpStyles.storyShapeLedger,
        ...(compact ? cpStyles.storyShapeLedgerCompact : null),
        ...(inBrief ? cpStyles.storyShapeLedgerInBrief : null),
      }}
    >
      {rows.map((row) => (
        <span key={row.label} style={cpStyles.storyShapeLedgerRow}>
          <strong>{row.label}</strong>
          <span>{row.value}</span>
        </span>
      ))}
    </div>
  )
}

export function StoryBriefCard({
  brief,
  canGenerate,
  nextStep,
  compact,
  busy,
  shapeRead,
  onGenerate,
  onKeepCorrecting,
  onApplyRevisionAction,
}: {
  brief: NarrativeStoryBrief
  canGenerate: boolean
  nextStep: string
  compact: boolean
  busy: boolean
  shapeRead: StoryShapeRead
  onGenerate: () => void
  onKeepCorrecting: () => void
  onApplyRevisionAction: (seedAppend: string) => void
}) {
  const t = useT()
  const primary = brief.cast_plan.primary_active_entities
  const secondary = brief.cast_plan.secondary_background_entities
  const omitted = brief.cast_plan.omitted_entities
  const decisions = brief.constraint_dispositions.slice(0, 8)
  const primaryNames = primary.map((entity) => entity.display_name).join(" · ")
  const surfacedConstraints = brief.constraints
    .map((item) => item.label)
    .filter((label) => label.toLowerCase() !== "core premise")
    .slice(0, 4)
  const visiblePressure = [...brief.time_event_anchors, ...brief.world_setting_pressure]
    .map((item) => item.label)
    .filter(Boolean)
    .slice(0, 2)
    .join(" · ")
  const visibleRules = surfacedConstraints.length > 0 ? surfacedConstraints.join(" · ") : brief.genre_tone

  return (
    <section style={{ ...cpStyles.briefRail, ...(compact ? cpStyles.briefRailCompact : null) }}>
      <div style={cpStyles.briefHeader}>
        <span style={cpStyles.briefEyebrow}>{t("create.brief_card_label")}</span>
        <span
          style={{
            ...cpStyles.briefFitPill,
            ...(brief.runtime_fit_status === "not_fit" ? cpStyles.briefFitPillWarn : null),
          }}
        >
          {t(FIT_STATUS_LABEL_KEYS[brief.runtime_fit_status])}
        </span>
      </div>
      <div style={cpStyles.briefBetaNote}>{brief.adaptation_note}</div>
      <p style={cpStyles.briefPremise}>{brief.premise_summary}</p>
      <StoryShapeReadLedger shapeRead={shapeRead} compact={compact} inBrief />
      <div style={{ ...cpStyles.briefMetaGrid, ...(compact ? cpStyles.briefMetaGridCompact : null) }}>
        <BriefField label={t("create.brief_profile")} value={brief.genre_tone || t(TENSION_PROFILE_LABEL_KEYS[brief.tension_profile])} />
        <BriefField label={t("create.brief_primary_cast")} value={primaryNames || t("create.brief_empty")} />
        <BriefField label={t("create.brief_kernel")} value={brief.story_kernel} />
        <BriefField label={t("create.brief_constraints")} value={visibleRules} />
        <BriefField label={t("create.brief_card_mechanic")} value={brief.intervention_card_label} />
      </div>
      {surfacedConstraints.length > 0 ? (
        <BriefList
          label={t("create.brief_key_details")}
          items={surfacedConstraints}
          empty={t("create.brief_empty")}
        />
      ) : null}
      {visiblePressure ? (
        <BriefList
          label={t("create.brief_event_pressure")}
          items={[visiblePressure]}
          empty={t("create.brief_empty")}
        />
      ) : null}
      {brief.warnings.length > 0 || brief.revision_suggestions.length > 0 ? (
        <div style={cpStyles.briefWarningBlock}>
          {brief.warnings.slice(0, 1).map((warning) => (
            <div key={warning} style={cpStyles.briefWarningLine}>{warning}</div>
          ))}
          {brief.revision_suggestions.slice(0, 1).map((suggestion) => (
            <div key={suggestion} style={cpStyles.briefSuggestionLine}>{suggestion}</div>
          ))}
        </div>
      ) : null}
      <details style={cpStyles.briefDetails}>
        <summary style={cpStyles.briefDetailsSummary}>
          <span>{t("create.brief_details_toggle")}</span>
          <span style={cpStyles.briefDetailsTitle}>{t("create.brief_details_title")}</span>
        </summary>
        <div style={{ ...cpStyles.briefCastGrid, ...(compact ? cpStyles.briefCastGridCompact : null) }}>
          <BriefEntityList
            label={t("create.brief_primary_cast")}
            items={primary.map((entity) => ({ label: entity.display_name, detail: entity.rationale }))}
            empty={t("create.brief_empty")}
          />
          <BriefEntityList
            label={t("create.brief_secondary_cast")}
            items={secondary.map((entity) => ({ label: entity.display_name, detail: entity.rationale }))}
            empty={t("create.brief_empty")}
          />
        </div>
        {omitted.length > 0 ? (
          <BriefPlanSection
            label={t("create.brief_omitted_cast")}
            items={omitted.map((entity) => ({ label: entity.display_name, rationale: entity.rationale }))}
            empty={t("create.brief_empty")}
          />
        ) : null}
        <BriefPlanSection label={t("create.brief_event_pressure")} items={[...brief.time_event_anchors, ...brief.world_setting_pressure]} empty={t("create.brief_empty")} />
        <BriefPlanSection label={t("create.brief_constraints")} items={brief.constraints} empty={t("create.brief_empty")} />
        <BriefPlanSection label={t("create.brief_tone_constraints")} items={brief.tone_constraints} empty={t("create.brief_empty")} />
        {decisions.length > 0 ? (
          <div style={cpStyles.briefConstraintRow}>
            {decisions.map((decision) => (
              <span key={`${decision.disposition}:${decision.label}`} style={cpStyles.briefConstraintChip} title={decision.rationale}>
                <span style={cpStyles.briefConstraintKind}>{t(CONSTRAINT_DISPOSITION_LABEL_KEYS[decision.disposition])}</span>
                {decision.label}
              </span>
            ))}
          </div>
        ) : null}
        {brief.warnings.length > 1 || brief.revision_suggestions.length > 1 ? (
          <div style={cpStyles.briefWarningBlock}>
            {brief.warnings.slice(1, 3).map((warning) => (
              <div key={warning} style={cpStyles.briefWarningLine}>{warning}</div>
            ))}
            {brief.revision_suggestions.slice(1, 2).map((suggestion) => (
              <div key={suggestion} style={cpStyles.briefSuggestionLine}>{suggestion}</div>
            ))}
          </div>
        ) : null}
      </details>
      {brief.revision_actions.length > 0 ? (
        <div style={cpStyles.briefRevisionActions} aria-label={t("create.brief_revision_actions")}>
          <span style={cpStyles.briefFieldLabel}>{t("create.brief_revision_actions")}</span>
          <div style={cpStyles.briefRevisionActionRow}>
            {brief.revision_actions.slice(0, 5).map((action) => (
              <button
                key={action.action_id}
                type="button"
                style={cpStyles.briefRevisionAction}
                title={action.description}
                onClick={() => onApplyRevisionAction(action.seed_append)}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div style={cpStyles.briefFooter}>
        <span>{brief.runtime_fit_rationale}</span>
        <strong>{canGenerate ? nextStep : t("create.brief_revise_first")}</strong>
      </div>
      <div style={cpStyles.briefChatActions}>
        {canGenerate ? (
          <button
            type="button"
            style={cpStyles.briefChatPrimary}
            onClick={onGenerate}
            disabled={busy}
          >
            {busy ? t("create.cta_busy") : t("create.brief_cta_generate")}
          </button>
        ) : null}
        <button
          type="button"
          style={cpStyles.briefChatSecondary}
          onClick={onKeepCorrecting}
          disabled={busy}
        >
          {t("create.brief_keep_correcting")}
        </button>
      </div>
    </section>
  )
}

function BriefField({ label, value }: { label: string; value: string }) {
  return (
    <div style={cpStyles.briefField}>
      <span style={cpStyles.briefFieldLabel}>{label}</span>
      <span style={cpStyles.briefFieldValue}>{value}</span>
    </div>
  )
}

function BriefList({ label, items, empty }: { label: string; items: string[]; empty: string }) {
  return (
    <div style={cpStyles.briefList}>
      <span style={cpStyles.briefFieldLabel}>{label}</span>
      <span style={cpStyles.briefListValue}>{items.length > 0 ? items.join(" · ") : empty}</span>
    </div>
  )
}

function BriefEntityList({
  label,
  items,
  empty,
  compactOnly = false,
}: {
  label: string
  items: { label: string; detail: string }[]
  empty: string
  compactOnly?: boolean
}) {
  return (
    <div style={cpStyles.briefList}>
      <span style={cpStyles.briefFieldLabel}>{label}</span>
      {compactOnly ? (
        <span style={cpStyles.briefListValue}>{items.length > 0 ? items.map((item) => item.label).join(" · ") : empty}</span>
      ) : (
        <div style={cpStyles.briefStackedList}>
          {items.length > 0 ? items.map((item) => (
            <span key={item.label} style={cpStyles.briefStackedItem}>
              <strong>{item.label}</strong>
              <span>{item.detail}</span>
            </span>
          )) : <span style={cpStyles.briefListValue}>{empty}</span>}
        </div>
      )}
    </div>
  )
}

function BriefPlanSection({
  label,
  items,
  empty,
}: {
  label: string
  items: { label: string; rationale: string }[]
  empty: string
}) {
  return (
    <div style={cpStyles.briefPlanSection}>
      <span style={cpStyles.briefFieldLabel}>{label}</span>
      <div style={cpStyles.briefPlanItems}>
        {items.length > 0 ? items.slice(0, 8).map((item) => (
          <span key={`${label}:${item.label}`} style={cpStyles.briefPlanItem} title={item.rationale}>
            <strong>{item.label}</strong>
            <span>{item.rationale}</span>
          </span>
        )) : <span style={cpStyles.briefListValue}>{empty}</span>}
      </div>
    </div>
  )
}
