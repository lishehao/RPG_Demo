import { type CSSProperties, useCallback, useEffect, useRef, useState } from "react"
import { AnimatePresence, motion, useReducedMotion, type TargetAndTransition } from "motion/react"
import type {
  NarrativeAgentEventPayload,
  NarrativeAgentEvent,
  NarrativeAgentPlan,
  NarrativeContractJudgeResult,
  NarrativeAdvisorMessage,
  NarrativeEnding,
  NarrativeLLMCallEvent,
  NarrativeNPCPulse,
  NarrativePlayerLeverageOverNPC,
  NarrativeStepJudgeResult,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../api/contracts"
import { useApi } from "../../app/api-context"
import { useAuth } from "../../app/auth-context"
import { LoadingShim } from "../../shared/ui/loading-shim"
import { Truncated } from "../../shared/ui/truncated"
import { useBookmarks } from "../../shared/lib/bookmarks"
import { friendlyError } from "../../shared/lib/friendly-error"
import { ENDING_LABEL_DISPLAY, useLanguage, useT } from "../../shared/lib/i18n"
import {
  cascadeDelay,
  fadeTransition,
  fadeVariants,
  hoverLift,
  hoverNudge,
  itemTransition,
  itemVariants,
  labelChipSpring,
  pulseVariants,
  slideInRightTransition,
  slideInRightVariants,
  tapPress,
  transitions,
} from "../../shared/lib/motion-presets"
import {
  getAdvisorAvatar,
  getCoverForTemplate,
  getEndingIllustration,
  getSceneByPhase,
  getTierSplash,
} from "../../shared/lib/webtoon-assets"
import { ppStyles } from "./play-styles"
import { useCompactLayout } from "./hooks/use-compact-layout"
import type { ActionCommitmentSummary, LeverageCardView, PlayAdvanceAction } from "./play-types"
import {
  MoodPlate,
  PlayShell,
  PlaySurfaceGrid,
  SceneSupportRail,
  StoryTimeline,
} from "./components/play-editorial-primitives"
import {
  ActionArea,
  AdvisorFab,
  AdvisorSidechat,
  EndingScreen,
  Header,
  RuntimeInspector,
  RunContextPanel,
  StoryBeat,
  buildAdvisorSuggestions,
  buildFailedActionRecovery,
  computeBeatIntensity,
  computeLiveInventory,
  findActionTarget,
  isResourceFocusAction,
  latestAgentPlanFromEvents,
  parseOptionLabel,
} from "./components/play-flow-panels"
import { PlayActionJumpButton } from "./components/play-action-jump"
import { isPlayActionAreaAwayFromViewport, scrollToPlayActionArea } from "./components/play-action-jump-utils"
import { PlayRetryRecoveryBanner } from "./components/play-retry-recovery"
import {
  buildGameplayEnvelope,
  type GameplayChipTone,
  type GameplayEnvelope,
} from "./play-gameplay-envelope"

function leverageCardId(roleId: string | undefined, lev: NarrativePlayerLeverageOverNPC, index: number): string {
  return `lev:${roleId || "role"}:${lev.npc_id}:${index}`
}

function leveragePlayInput(card: LeverageCardView, language: NarrativeStoryHistoryResponse["template"]["language"]): string {
  if (language === "zh") {
    return `我亮出手里针对 ${card.target_name} 的把柄：${card.leverage}`
  }
  return `I reveal the leverage I hold over ${card.target_name}: ${card.leverage}`
}

function playSegmentPhaseForMessage(
  message: NarrativeStoryMessage,
  turnBudget: number,
): "opening" | "pressure" | "reversal" | "reveal" | "terminal" {
  const turnIndex = Math.floor(message.ord / 2)
  if (turnIndex <= 0) return "opening"
  if (turnIndex >= turnBudget) return "terminal"
  const ratio = turnBudget > 0 ? turnIndex / turnBudget : 0
  if (ratio < 0.35) return "pressure"
  if (ratio < 0.6) return "reversal"
  if (ratio < 0.9) return "reveal"
  return "terminal"
}

function playSegmentSceneCorpus(
  story: NarrativeStoryHistoryResponse,
  message: NarrativeStoryMessage,
): string {
  return [
    story.template.seed,
    story.template.title,
    story.template.cast
      .map((member) => `${member.display_name} ${member.role} ${member.relation_to_protagonist}`)
      .join(" "),
    message.content,
  ].join(" ")
}

function mergeAgentEvents(
  existing: NarrativeAgentEvent[],
  incoming: NarrativeAgentEvent[],
): NarrativeAgentEvent[] {
  const byKey = new Map<string, NarrativeAgentEvent>()
  for (const event of [...existing, ...incoming]) {
    byKey.set(`${event.event_index}:${event.ord}:${event.event_type}`, event)
  }
  return [...byKey.values()].sort((a, b) => {
    if (a.event_index !== b.event_index) return a.event_index - b.event_index
    if (a.ord !== b.ord) return a.ord - b.ord
    return a.event_type.localeCompare(b.event_type)
  })
}

function shouldUseLocalAdvanceFailureHarness(): boolean {
  if (!import.meta.env.DEV || typeof window === "undefined") return false
  const [, hashSearch = ""] = window.location.hash.split("?")
  if (!hashSearch) return false
  return new URLSearchParams(hashSearch).get("playTurnFailure") === "once"
}

function gameplayToneStyle(tone: GameplayChipTone): CSSProperties | null {
  if (tone === "gain") return ppStyles.gameplayToneGain
  if (tone === "cost") return ppStyles.gameplayToneCost
  if (tone === "unlock") return ppStyles.gameplayToneUnlock
  return null
}

type GameplayResourceFocusId = "time" | "pressure" | "evidence"

function isGameplayResourceFocusId(value: string): value is GameplayResourceFocusId {
  return value === "time" || value === "pressure" || value === "evidence"
}

function gameplayResourceFocusTitle(t: ReturnType<typeof useT>, id: GameplayResourceFocusId): string {
  if (id === "time") return t("play.resource_focus_time_title")
  if (id === "pressure") return t("play.resource_focus_pressure_title")
  return t("play.resource_focus_evidence_title")
}

function parseRelationshipDeltaLabel(label: string): { name: string; shift: string } | null {
  const match = label.match(/^(.+?):\s*(warmer|colder|wary|broken|steady)$/i)
  if (!match) return null
  return {
    name: match[1]?.trim() ?? "",
    shift: match[2]?.trim().toLowerCase() ?? "",
  }
}

function relationshipShiftCopy(t: ReturnType<typeof useT>, shift: string): string {
  if (shift === "warmer") return t("play.impact_warmer")
  if (shift === "colder") return t("play.impact_colder")
  if (shift === "wary") return t("play.impact_wary")
  if (shift === "broken") return t("play.impact_broken")
  return t("play.impact_steady")
}

function actorFromDisplayName(
  name: string,
  castNameById: Record<string, string>,
): { id: string; name: string } | null {
  const normalizedName = name.trim().toLowerCase()
  if (!normalizedName) return null
  const matched = Object.entries(castNameById)
    .find(([, displayName]) => displayName.trim().toLowerCase() === normalizedName)
  if (!matched) return null
  return { id: matched[0], name: matched[1] }
}

function impactDeltaKey(delta: GameplayEnvelope["impact"][number]): string {
  const parsed = parseRelationshipDeltaLabel(delta.label)
  if (parsed) return `relationship:${parsed.name.toLowerCase()}:${parsed.shift.toLowerCase()}`
  return `${delta.tone}:${delta.label.replace(/\s+/g, " ").trim().toLowerCase()}`
}

function isLowSignalForecastLabel(label: string): boolean {
  return /^(Target |Room read$)/i.test(label.trim())
}

function impactSourceMoveText(message: NarrativeStoryMessage | null): string | null {
  if (!message || message.role !== "player") return null
  const parsed = parseOptionLabel(message.content)
  const text = (parsed.body || message.content).trim()
  if (!text) return null
  return text.length > 88 ? `${text.slice(0, 85)}...` : text
}

function uniqueActionTargetsForOptions(
  options: NarrativeStoryMessage["options"],
  castNameById: Record<string, string>,
  latestNpcPulses: NarrativeNPCPulse[],
): Array<{ id: string; name: string }> {
  const seen = new Set<string>()
  return options
    .map((option) => {
      const parsed = parseOptionLabel(option.label)
      return findActionTarget(parsed.body, option.hint, castNameById, latestNpcPulses)
    })
    .filter((target): target is { id: string; name: string } => Boolean(target))
    .filter((target) => {
      if (seen.has(target.id)) return false
      seen.add(target.id)
      return true
    })
    .slice(0, 3)
}

function actionTargetCountsForOptions(
  options: NarrativeStoryMessage["options"],
  castNameById: Record<string, string>,
  latestNpcPulses: NarrativeNPCPulse[],
): Record<string, number> {
  const counts: Record<string, number> = {}
  options.forEach((option) => {
    const parsed = parseOptionLabel(option.label)
    const target = findActionTarget(parsed.body, option.hint, castNameById, latestNpcPulses)
    if (!target) return
    counts[target.id] = (counts[target.id] ?? 0) + 1
  })
  return counts
}

function resourceActionCountsForOptions(
  options: NarrativeStoryMessage["options"],
  actionForecasts: GameplayEnvelope["actionForecasts"],
): Record<GameplayResourceFocusId, number> {
  const counts: Record<GameplayResourceFocusId, number> = {
    time: 0,
    pressure: 0,
    evidence: 0,
  }
  const focusIds: GameplayResourceFocusId[] = ["time", "pressure", "evidence"]
  options.forEach((option, index) => {
    const parsed = parseOptionLabel(option.label)
    focusIds.forEach((resourceId) => {
      if (isResourceFocusAction(resourceId, parsed.body, option.hint, actionForecasts[index] ?? [])) {
        counts[resourceId] += 1
      }
    })
  })
  return counts
}

function GameplayStatePanel({
  envelope,
  focusedResourceId,
  resourceActionCounts,
  onFocusResource,
}: {
  envelope: GameplayEnvelope
  focusedResourceId?: GameplayResourceFocusId | null
  resourceActionCounts?: Record<GameplayResourceFocusId, number>
  onFocusResource?: (id: GameplayResourceFocusId) => void
}) {
  const t = useT()
  return (
    <section
      style={ppStyles.gameplayEnvelopePanel}
      data-gameplay-envelope="true"
      data-gameplay-envelope-source={envelope.source}
      aria-label={t("play.gameplay_state_label")}
    >
      <div style={ppStyles.gameplayObjectiveRow} data-gameplay-objective="normal-play">
        <span style={ppStyles.gameplayObjectiveKicker}>{t("play.gameplay_objective_label")}</span>
        <strong style={ppStyles.gameplayObjectiveText} data-gameplay-objective-text="normal-play">
          {envelope.objective}
        </strong>
      </div>
      <div style={ppStyles.gameplayStakesHeader} data-gameplay-stakes-header="normal-play">
        <span style={ppStyles.gameplayStakesLabel}>{t("play.gameplay_tracks_label")}</span>
        <span style={ppStyles.gameplayStakesHint}>{t("play.gameplay_tracks_hint")}</span>
      </div>
      <div style={ppStyles.gameplayTrackGrid} aria-label={t("play.gameplay_tracks_label")}>
        {envelope.tracks.map((track) => {
          const focusableTrackId = isGameplayResourceFocusId(track.id) ? track.id : null
          const isFocused = focusedResourceId === focusableTrackId && focusableTrackId !== null
          const focusTitle = focusableTrackId ? gameplayResourceFocusTitle(t, focusableTrackId) : ""
          const resourceMatchCount = focusableTrackId
            ? resourceActionCounts?.[focusableTrackId] ?? 0
            : 0
          const resourceActionLabel = isFocused
            ? resourceMatchCount > 0
              ? resourceMatchCount === 1
                ? t("play.resource_focus_active_count_one")
                : t("play.resource_focus_active_count_many", { count: resourceMatchCount })
              : t("play.resource_focus_active_none")
            : resourceMatchCount === 1
              ? t("play.resource_focus_cta_count_one")
              : resourceMatchCount > 1
                ? t("play.resource_focus_cta_count_many", { count: resourceMatchCount })
                : t("play.resource_focus_cta_none")
          const trackStyle = {
            ...ppStyles.gameplayTrack,
            ...(focusableTrackId ? ppStyles.gameplayTrackButton : null),
            ...(gameplayToneStyle(track.tone) ?? {}),
            ...(isFocused ? ppStyles.gameplayTrackFocused : null),
          }
          const content = (
            <>
              <span style={ppStyles.gameplayTrackLabel}>{track.label}</span>
              <span style={ppStyles.gameplayTrackValue}>{track.value}</span>
              {focusableTrackId ? (
                <span style={ppStyles.gameplayTrackAction}>
                  {resourceActionLabel}
                </span>
              ) : null}
            </>
          )
          return focusableTrackId ? (
            <button
              key={track.id}
              type="button"
              style={trackStyle}
              data-gameplay-pressure-track={track.id}
              data-gameplay-resource-track={focusableTrackId}
              data-gameplay-evidence-resource={focusableTrackId === "evidence" ? "true" : undefined}
              data-gameplay-resource-focus={isFocused ? "true" : undefined}
              data-gameplay-resource-action-count={resourceMatchCount}
              aria-pressed={isFocused}
              aria-label={`${track.label}: ${track.value}. ${focusTitle}`}
              title={focusTitle}
              onClick={() => onFocusResource?.(focusableTrackId)}
            >
              {content}
            </button>
          ) : (
            <span
              key={track.id}
              style={trackStyle}
              data-gameplay-pressure-track={track.id}
            >
              {content}
            </span>
          )
        })}
      </div>
    </section>
  )
}

function GameplayImpactSummary({
  envelope,
  castNameById,
  nextChoiceTargets,
  sourceMoveText,
  focusedActorId,
  onFocusActor,
}: {
  envelope: GameplayEnvelope
  castNameById: Record<string, string>
  nextChoiceTargets?: Array<{ id: string; name: string }>
  sourceMoveText?: string | null
  focusedActorId?: string | null
  onFocusActor?: (actor: { id: string; name: string }) => void
}) {
  const t = useT()
  if (envelope.impact.length === 0) return null
  const primaryImpact =
    envelope.impact.find((delta) => delta.tone === "cost") ??
    envelope.impact.find((delta) => delta.tone === "unlock" || delta.tone === "gain") ??
    envelope.impact.find((delta) => delta.tone === "shift") ??
    envelope.impact[0]
  const primaryImpactKey = primaryImpact ? impactDeltaKey(primaryImpact) : null
  const secondaryImpacts = envelope.impact.filter(
    (delta) => impactDeltaKey(delta) !== primaryImpactKey,
  )
  const forecastChoiceSignals = envelope.actionForecasts
    .map((row) => row.find((chip) => chip.detail || chip.tone === "unlock" || chip.tone === "gain" || chip.tone === "cost") ?? null)
    .filter((chip): chip is NonNullable<typeof chip> => Boolean(chip))
    .filter((chip) => chip.detail || !isLowSignalForecastLabel(chip.label))
    .filter((chip, index, all) => all.findIndex((candidate) => candidate.label === chip.label) === index)
    .slice(0, 2)
  const uniqueNextChoiceTargets = (nextChoiceTargets ?? []).filter(
    (target, index, all) => all.findIndex((candidate) => candidate.id === target.id) === index,
  )
  const targetChoiceSignals = uniqueNextChoiceTargets.map((target) => ({
    label: `${t("play.action_target_label")} ${target.name}`,
    detail: t("play.action_target_title", { name: target.name }),
    tone: "shift" as GameplayChipTone,
    targetId: target.id,
    targetName: target.name,
  }))
  const nextChoiceSignals = (forecastChoiceSignals.length > 0
    ? forecastChoiceSignals
    : targetChoiceSignals.length > 1
      ? [{
          label: t("play.feedback_next_choice_changed_label"),
          detail: t("play.feedback_next_choice_changed_detail"),
          tone: "shift" as GameplayChipTone,
        }]
      : targetChoiceSignals)
    .filter((chip, index, all) => all.findIndex((candidate) => candidate.label === chip.label) === index)
    .slice(0, 3)
  const impactGroups = [
    {
      id: "cost",
      label: t("play.feedback_impact_cost_label"),
      items: secondaryImpacts.filter((delta) => delta.tone === "cost"),
    },
    {
      id: "opened",
      label: t("play.feedback_impact_opened_label"),
      items: secondaryImpacts.filter((delta) => delta.tone === "gain" || delta.tone === "unlock"),
    },
    {
      id: "shift",
      label: t("play.feedback_impact_shift_label"),
      items: secondaryImpacts.filter((delta) => delta.tone === "shift"),
    },
  ].filter((group) => group.items.length > 0)
  const renderImpactValue = (
    delta: (typeof envelope.impact)[number],
    mode: "spotlight" | "chip",
  ) => {
    const parsed = parseRelationshipDeltaLabel(delta.label)
    if (!parsed) return delta.label
    const actor = actorFromDisplayName(parsed.name, castNameById)
    const shiftCopy = relationshipShiftCopy(t, parsed.shift)
    const relationshipContent = (
      <>
        <span style={ppStyles.gameplayRelationshipDeltaName}>{parsed.name}</span>
        <span style={ppStyles.gameplayRelationshipDeltaShift}>
          {shiftCopy}
        </span>
      </>
    )
    if (actor && onFocusActor) {
      const isFocused = focusedActorId === actor.id
      return (
        <button
          type="button"
          style={{
            ...(mode === "spotlight" ? ppStyles.gameplayRelationshipDeltaSpotlight : ppStyles.gameplayRelationshipDelta),
            ...ppStyles.gameplayRelationshipDeltaButton,
            ...(isFocused ? ppStyles.gameplayRelationshipDeltaButtonFocused : null),
          }}
          data-gameplay-relationship-delta="true"
          data-gameplay-impact-actor-focus="true"
          data-gameplay-impact-actor-id={actor.id}
          data-gameplay-impact-actor-focused={isFocused ? "true" : undefined}
          aria-pressed={isFocused}
          aria-label={`${parsed.name} ${shiftCopy}. ${t("play.impact_focus_actor_title", { name: actor.name })}`}
          title={t("play.impact_focus_actor_title", { name: actor.name })}
          onClick={() => onFocusActor(actor)}
        >
          {relationshipContent}
        </button>
      )
    }
    return (
      <span
        style={mode === "spotlight" ? ppStyles.gameplayRelationshipDeltaSpotlight : ppStyles.gameplayRelationshipDelta}
        data-gameplay-relationship-delta="true"
        aria-label={`${parsed.name} ${shiftCopy}`}
      >
        {relationshipContent}
      </span>
    )
  }

  return (
    <section
      style={ppStyles.gameplayImpactPanel}
      data-gameplay-impact-summary="true"
      aria-label={t("play.gameplay_impact_label")}
    >
      <div style={ppStyles.gameplayImpactHeader}>
        <span style={ppStyles.gameplayImpactKicker}>{t("play.gameplay_impact_label")}</span>
        <span style={ppStyles.gameplayImpactHint}>{t("play.feedback_impact_hint")}</span>
      </div>
      {sourceMoveText ? (
        <div
          style={ppStyles.gameplayImpactSourceMove}
          data-gameplay-impact-source-move="true"
          title={sourceMoveText}
        >
          <span style={ppStyles.gameplayImpactSourceLabel}>
            {t("play.feedback_source_move_label")}{" "}
          </span>
          <strong style={ppStyles.gameplayImpactSourceText}>{sourceMoveText}</strong>
        </div>
      ) : null}
      {primaryImpact ? (
        <div
          style={ppStyles.gameplayImpactSpotlight}
          data-gameplay-impact-spotlight="true"
          data-gameplay-impact-spotlight-tone={primaryImpact.tone}
          aria-label={`${t("play.feedback_key_consequence_label")}: ${primaryImpact.label}`}
        >
          <span style={ppStyles.gameplayImpactSpotlightLabel}>{t("play.feedback_key_consequence_label")}</span>
          <strong
            style={{
              ...ppStyles.gameplayImpactSpotlightValue,
              ...(gameplayToneStyle(primaryImpact.tone) ?? {}),
            }}
            title={primaryImpact.label}
          >
            {renderImpactValue(primaryImpact, "spotlight")}
          </strong>
        </div>
      ) : null}
      <div style={ppStyles.gameplayImpactGroups}>
        {impactGroups.map((group) => (
          <div
            key={group.id}
            style={ppStyles.gameplayImpactGroup}
            data-gameplay-impact-group={group.id}
          >
            <span style={ppStyles.gameplayImpactGroupLabel}>{group.label}</span>
            <div style={ppStyles.gameplayImpactList}>
              {group.items.map((delta, index) => (
                <span
                  key={`${delta.label}-${index}`}
                  style={{ ...ppStyles.gameplayDeltaChip, ...(gameplayToneStyle(delta.tone) ?? {}) }}
                  data-gameplay-delta="normal-play"
                  title={delta.label}
                >
                  {renderImpactValue(delta, "chip")}
                </span>
              ))}
            </div>
          </div>
        ))}
        {nextChoiceSignals.length > 0 ? (
          <div
            style={ppStyles.gameplayImpactGroup}
            data-gameplay-impact-group="next"
            data-gameplay-next-choice-signals="true"
          >
            <span style={ppStyles.gameplayImpactGroupLabel}>{t("play.feedback_next_choice_label")}</span>
            <div style={ppStyles.gameplayImpactList}>
              {nextChoiceSignals.map((signal, index) => {
                const targetSignal = "targetId" in signal && signal.targetId
                  ? signal as typeof signal & { targetId: string; targetName: string }
                  : null
                const signalStyle = {
                  ...ppStyles.gameplayDeltaChip,
                  ...ppStyles.gameplayNextChoiceChip,
                  ...(gameplayToneStyle(signal.tone) ?? {}),
                  ...(targetSignal ? ppStyles.gameplayNextChoiceTargetChip : null),
                  ...(targetSignal && focusedActorId === targetSignal.targetId ? ppStyles.gameplayNextChoiceTargetFocused : null),
                }
                if (targetSignal && onFocusActor) {
                  return (
                    <button
                      key={`${signal.label}-${index}`}
                      type="button"
                      style={{
                        ...signalStyle,
                        ...ppStyles.gameplayNextChoiceTargetButton,
                      }}
                      data-gameplay-next-choice-signal="normal-play"
                      data-gameplay-next-choice-target-focus="true"
                      data-gameplay-next-choice-target-id={targetSignal.targetId}
                      aria-pressed={focusedActorId === targetSignal.targetId}
                      aria-label={`${signal.label}. ${t("play.impact_focus_actor_title", { name: targetSignal.targetName })}`}
                      title={signal.detail ?? signal.label}
                      onClick={() => onFocusActor({ id: targetSignal.targetId, name: targetSignal.targetName })}
                    >
                      {signal.label}
                    </button>
                  )
                }
                return (
                  <span
                    key={`${signal.label}-${index}`}
                    style={signalStyle}
                    data-gameplay-next-choice-signal="normal-play"
                    data-gameplay-next-choice-target-id={targetSignal?.targetId}
                    title={signal.detail ?? signal.label}
                  >
                    {signal.label}
                  </span>
                )
              })}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}

type GameplayLoopStage = "read" | "choose" | "react" | "update" | "ending"

function GameplayLoopGuide({
  stage,
  hasImpact,
}: {
  stage: GameplayLoopStage
  hasImpact: boolean
}) {
  const t = useT()
  const steps: Array<{
    id: GameplayLoopStage
    label: string
    detail: string
  }> = [
    {
      id: "read",
      label: t("play.gameplay_loop_read_label"),
      detail: t("play.gameplay_loop_read_detail"),
    },
    {
      id: "choose",
      label: t("play.gameplay_loop_choose_label"),
      detail: t("play.gameplay_loop_choose_detail"),
    },
    {
      id: "react",
      label: t("play.gameplay_loop_react_label"),
      detail: t("play.gameplay_loop_react_detail"),
    },
    {
      id: "update",
      label: t("play.gameplay_loop_update_label"),
      detail: t("play.gameplay_loop_update_detail"),
    },
  ]
  const stageOrder: GameplayLoopStage[] = ["read", "choose", "react", "update"]
  const activeIndex = stage === "ending" ? steps.length : Math.max(0, stageOrder.indexOf(stage))

  return (
    <section
      style={ppStyles.gameplayLoopPanel}
      data-gameplay-loop-guide="normal-play"
      data-gameplay-loop-stage={stage}
      aria-label={t("play.gameplay_loop_label")}
    >
      <div style={ppStyles.gameplayLoopHeader}>
        <span style={ppStyles.gameplayLoopKicker}>{t("play.gameplay_loop_kicker")}</span>
        <strong style={ppStyles.gameplayLoopTitle}>
          {stage === "ending"
            ? t("play.gameplay_loop_status_ending")
            : stage === "react"
              ? t("play.gameplay_loop_status_react")
              : hasImpact && stage === "update"
                ? t("play.gameplay_loop_status_update")
                : t("play.gameplay_loop_status_choose")}
        </strong>
      </div>
      <ol style={ppStyles.gameplayLoopSteps}>
        {steps.map((step, index) => {
          const isActive = step.id === stage
          const isDone = stage === "ending" || index < activeIndex
          return (
            <li
              key={step.id}
              style={{
                ...ppStyles.gameplayLoopStep,
                ...(isActive ? ppStyles.gameplayLoopStepActive : {}),
                ...(isDone ? ppStyles.gameplayLoopStepDone : {}),
              }}
              data-gameplay-loop-step={step.id}
              data-gameplay-loop-step-active={isActive ? "true" : "false"}
              data-gameplay-loop-step-done={isDone ? "true" : "false"}
            >
              <span style={ppStyles.gameplayLoopIndex}>{index + 1}</span>
              <span style={ppStyles.gameplayLoopStepText}>
                <strong style={ppStyles.gameplayLoopStepLabel}>{step.label}</strong>
                <span style={ppStyles.gameplayLoopStepDetail}>{step.detail}</span>
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

export function PlayPage({
  sessionId,
  reviewerMode = false,
  onBackHome,
}: {
  sessionId: string
  reviewerMode?: boolean
  onBackHome: () => void
}) {
  const api = useApi()
  const auth = useAuth()
  const t = useT()
  const [story, setStory] = useState<NarrativeStoryHistoryResponse | null>(null)
  const [ending, setEnding] = useState<NarrativeEnding | null>(null)
  const [latestAgentPlan, setLatestAgentPlan] = useState<NarrativeAgentPlan | null>(null)
  const [latestAgentEvents, setLatestAgentEvents] = useState<NarrativeAgentEvent[]>([])
  const [llmEvents, setLlmEvents] = useState<NarrativeLLMCallEvent[]>([])
  // Per-session bookmarks — beats the user marked as "I want to
  // remember this." Merged into ending highlights at finalize so
  // the user's call has authority alongside the LLM's picks.
  const { marked: bookmarkedOrds, toggle: toggleBookmark, count: bookmarkCount } =
    useBookmarks(sessionId)
  void bookmarkCount
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Remember the last action that errored so the inline error banner
  // can offer a one-tap retry instead of forcing the user to re-type
  // / re-pick what they just submitted.
  const lastFailedActionRef = useRef<PlayAdvanceAction | null>(null)
  const advanceInFlightRef = useRef(false)
  const localAdvanceFailureHarnessRef = useRef(shouldUseLocalAdvanceFailureHarness())
  const [freeInput, setFreeInput] = useState("")
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [diary, setDiary] = useState("")
  const [showDiary, setShowDiary] = useState(false)
  const [advisorOpen, setAdvisorOpen] = useState(false)
  const advisorReturnFocusRef = useRef<HTMLElement | null>(null)
  const [actionCommitmentActive, setActionCommitmentActive] = useState(false)
  const [actionCommitmentSummary, setActionCommitmentSummary] = useState<ActionCommitmentSummary | null>(null)
  const [focusedActorId, setFocusedActorId] = useState<string | null>(null)
  const [focusedResourceId, setFocusedResourceId] = useState<GameplayResourceFocusId | null>(null)
  const [showActionJump, setShowActionJump] = useState(false)
  const [shareCopied, setShareCopied] = useState(false)
  const compactPlayChrome = useCompactLayout("(max-width: 680px)")
  const canRequestAgentTrace = reviewerMode && auth.canViewAgentTrace

  const refreshReviewerEvidence = useCallback(async () => {
    if (!canRequestAgentTrace) {
      setLlmEvents([])
      return
    }
    try {
      const response = await api.getNarrativeLLMEvents(sessionId)
      setLlmEvents(response.items)
    } catch {
      setLlmEvents([])
    }
  }, [api, canRequestAgentTrace, sessionId])

  // Initial load: story + (if already completed) the ending.
  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .getNarrativeStory(sessionId, canRequestAgentTrace ? { agentTrace: true } : undefined)
      .then(async (response) => {
        if (cancelled) return
        setStory(response)
        const agentEvents = canRequestAgentTrace ? response.agent_events ?? [] : []
        setLatestAgentEvents(agentEvents)
        setLatestAgentPlan(canRequestAgentTrace ? latestAgentPlanFromEvents(agentEvents) : null)
        void refreshReviewerEvidence()
        // If session already finished, fetch the ending so we can render
        // the closing screen on direct-link visits.
        if (response.session.ending_label) {
          try {
            const e = await api.getNarrativeSessionEnding(sessionId)
            if (!cancelled && e) setEnding(e)
          } catch {
            // ignore — the summary still has the label/subtitle if needed
          }
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(friendlyError(err, t("play.error_load_story")))
      })
    return () => {
      cancelled = true
    }
  }, [api, canRequestAgentTrace, refreshReviewerEvidence, sessionId])

  // Auto-scroll to the current decision point whenever content arrives.
  // The page uses native document scroll for a less pane-like reading
  // feel, but this still tolerates older nested-scroll layouts.
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const previousScrollStoryRef = useRef<{ sessionId: string; messageCount: number } | null>(null)
  useEffect(() => {
    const el = scrollerRef.current
    if (!el || !story || story.session.ending_label) return
    const messageCount = story.messages.length
    const previousScrollStory = previousScrollStoryRef.current
    const shouldRevealLatestBeat =
      previousScrollStory?.sessionId === story.session.session_id &&
      messageCount > previousScrollStory.messageCount
    previousScrollStoryRef.current = {
      sessionId: story.session.session_id,
      messageCount,
    }
    if (!shouldRevealLatestBeat) return

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const smoothBehavior: ScrollBehavior = prefersReducedMotion ? "auto" : "smooth"

    let secondFrame = 0
    const scrollToDecision = (behavior: ScrollBehavior) => {
      const canScrollColumn = el.scrollHeight > el.clientHeight + 8
      if (canScrollColumn) {
        el.scrollTo({ top: el.scrollHeight, behavior })
      }
      const latestBeat = document.querySelector<HTMLElement>("[data-play-latest-narrator='true']")
      const actionArea = document.querySelector<HTMLElement>("[data-play-action-area='true']")
      const scrollTarget = latestBeat ?? actionArea
      if (!scrollTarget) return
      const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
      const rect = scrollTarget.getBoundingClientRect()
      const viewportBottom = window.innerHeight - 24
      if (rect.top >= headerHeight + 8 && rect.bottom <= viewportBottom) return
      const root = document.scrollingElement ?? document.documentElement
      root.scrollTo({
        top: Math.max(0, rect.top + root.scrollTop - headerHeight - 16),
        behavior,
      })
    }
    const firstFrame = window.requestAnimationFrame(() => {
      scrollToDecision(smoothBehavior)
      secondFrame = window.requestAnimationFrame(() => scrollToDecision("auto"))
    })
    const lateLayoutTimer = window.setTimeout(() => scrollToDecision("auto"), 220)

    return () => {
      window.cancelAnimationFrame(firstFrame)
      if (secondFrame) window.cancelAnimationFrame(secondFrame)
      window.clearTimeout(lateLayoutTimer)
    }
  }, [story, story?.messages.length, story?.session.ending_label, story?.session.session_id])

  const handleAdvance = useCallback(
    async (
      action: PlayAdvanceAction,
      options?: { keepRecoveryVisible?: boolean },
    ) => {
      if (advanceInFlightRef.current || busy) return
      advanceInFlightRef.current = true
      setBusy(true)
      if (!options?.keepRecoveryVisible) {
        setError(null)
      }
      setActionCommitmentActive(false)
      setActionCommitmentSummary(null)
      if (!options?.keepRecoveryVisible) {
        lastFailedActionRef.current = null
      }
      try {
        if (localAdvanceFailureHarnessRef.current) {
          localAdvanceFailureHarnessRef.current = false
          throw new Error(t("play.error_advance"))
        }
        const response = await api.advanceNarrativeTurn(
          sessionId,
          action,
          canRequestAgentTrace ? { agentTrace: true } : undefined,
        )
        setLatestAgentPlan(canRequestAgentTrace ? response.agent_plan ?? null : null)
        setLatestAgentEvents((prev) =>
          canRequestAgentTrace ? mergeAgentEvents(prev, response.agent_events ?? []) : [],
        )
        void refreshReviewerEvidence()
        setStory((prev) => {
          if (!prev) return prev
          // Mark the prior narrator's chosen_option_index in the local copy
          // so the option chips render the dim+selected state.
          const updated = prev.messages.map((m) => {
            if (
              m.role === "narrator" &&
              m.ord === response.player_message.ord - 1 &&
              action.chosen_option_index != null
            ) {
              return { ...m, chosen_option_index: action.chosen_option_index }
            }
            return m
          })
          return {
            ...prev,
            messages: [...updated, response.player_message, response.narrator_message],
            gameplay_envelope: response.gameplay_envelope ?? null,
            session: {
              ...prev.session,
              turn_count: prev.session.turn_count + 1,
              ending_label: response.ending?.label ?? prev.session.ending_label,
              ending_subtitle: response.ending?.subtitle ?? prev.session.ending_subtitle,
            },
          }
        })
        if (response.ending) {
          setEnding(response.ending)
        }
        setError(null)
        lastFailedActionRef.current = null
        setFreeInput("")
        setShowFreeInput(false)
        setDiary("")
        setShowDiary(false)
      } catch (err) {
        setError(friendlyError(err, t("play.error_advance")))
        lastFailedActionRef.current = action
      } finally {
        advanceInFlightRef.current = false
        setBusy(false)
      }
    },
    [api, busy, canRequestAgentTrace, refreshReviewerEvidence, sessionId, t],
  )

  const openAdvisor = useCallback(() => {
    if (typeof document !== "undefined") {
      const active = document.activeElement
      advisorReturnFocusRef.current = active instanceof HTMLElement ? active : null
    }
    setAdvisorOpen(true)
  }, [])
  const closeAdvisor = useCallback(() => {
    setAdvisorOpen(false)
    if (typeof window === "undefined" || typeof document === "undefined") return
    const restoreFocus = () => {
      const previous = advisorReturnFocusRef.current
      if (previous?.isConnected && !previous.hasAttribute("disabled")) {
        previous.focus({ preventScroll: true })
        return
      }
      document.querySelector<HTMLElement>(".advisor-fab")?.focus({ preventScroll: true })
    }
    const frame = window.requestAnimationFrame(restoreFocus)
    window.setTimeout(() => {
      window.cancelAnimationFrame(frame)
      restoreFocus()
    }, 90)
  }, [])

  useEffect(() => {
    if (!story || busy || advisorOpen || ending) {
      setShowActionJump(false)
      return
    }
    const currentLastNarrator = [...story.messages].reverse().find((m) => m.role === "narrator") ?? null
    const currentActionAreaVisible =
      currentLastNarrator !== null &&
      currentLastNarrator.chosen_option_index == null &&
      !story.session.ending_label
    if (!currentActionAreaVisible) {
      setShowActionJump(false)
      return
    }

    let frame = 0
    const update = () => {
      const actionArea = document.querySelector<HTMLElement>("[data-play-action-area='true']")
      if (!actionArea) {
        setShowActionJump(false)
        return
      }
      setShowActionJump(isPlayActionAreaAwayFromViewport(actionArea))
    }

    const requestUpdate = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(update)
    }
    requestUpdate()
    const lateTimer = window.setTimeout(update, 260)
    window.addEventListener("scroll", requestUpdate, { passive: true })
    window.addEventListener("resize", requestUpdate)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(lateTimer)
      window.removeEventListener("scroll", requestUpdate)
      window.removeEventListener("resize", requestUpdate)
    }
  }, [
    advisorOpen,
    busy,
    compactPlayChrome,
    ending,
    story,
  ])

  const handleActionJump = useCallback(() => {
    setShowActionJump(false)
    scrollToPlayActionArea()
  }, [])

  const lastNarrator = story
    ? [...story.messages].reverse().find((m) => m.role === "narrator") ?? null
    : null
  const isLastNarratorPending =
    lastNarrator !== null && lastNarrator.chosen_option_index == null

  if (!story) {
    return (
      <div style={ppStyles.page}>
        <Header onBackHome={onBackHome} title="" />
        {error ? (
          <div style={ppStyles.centerNote}>{t("play.load_failed", { error })}</div>
        ) : (
          <LoadingShim label={t("play.loading_story")} />
        )}
      </div>
    )
  }

  const cover = getCoverForTemplate(story.template)
  const latestMoodSceneUrl = lastNarrator
    ? getSceneByPhase(
        playSegmentPhaseForMessage(lastNarrator, story.session.turn_budget),
        `${story.template.template_id}|mood|${lastNarrator.ord}`,
        playSegmentSceneCorpus(story, lastNarrator),
      )
    : undefined
  const advisorAvatar = getAdvisorAvatar(
    story.template.template_id,
    story.template.advisor_persona,
  )

  const turnsCompleted = story.session.turn_count
  const turnBudget = story.session.turn_budget
  const turnsRemaining = Math.max(0, turnBudget - turnsCompleted)
  const isFinalApproaching = turnsRemaining <= 2 && !ending
  const isComplete = ending !== null
  const actionAreaVisible = !isComplete && isLastNarratorPending && !!lastNarrator
  const isGauntlet = story.session.difficulty === "gauntlet"
  const castNameById: Record<string, string> = Object.fromEntries(
    story.template.cast.map((c) => [c.character_id, c.display_name]),
  )
  // Live inventory derived from role.starting_assets + Σ delta over
  // narrator messages. Mirrors backend compute_current_inventory.
  const liveInventory = computeLiveInventory(
    story.session.player_role?.starting_assets ?? [],
    story.messages,
  )
  const playedLeverageIds = new Set(
    story.messages
      .map((m) => m.played_leverage?.card_id)
      .filter((id): id is string => Boolean(id)),
  )
  const leverageCards: LeverageCardView[] = (story.session.player_role?.leverages_over_npcs ?? []).map(
    (lev, index) => {
      const cardId = leverageCardId(story.session.player_role?.role_id, lev, index)
      return {
        card_id: cardId,
        npc_id: lev.npc_id,
        target_name: castNameById[lev.npc_id] ?? lev.npc_id,
        leverage: lev.leverage,
        used: playedLeverageIds.has(cardId),
      }
    },
  )
  const previousPlayerForLastNarrator = (() => {
    if (!lastNarrator) return null
    const idx = story.messages.findIndex((m) => m.role === "narrator" && m.ord === lastNarrator.ord)
    if (idx <= 0) return null
    const previous = story.messages[idx - 1]
    return previous?.role === "player" ? previous : null
  })()
  const impactSourceMove = impactSourceMoveText(previousPlayerForLastNarrator)
  const gameplayEnvelope = buildGameplayEnvelope({
    story,
    lastNarrator,
    previousPlayerMessage: previousPlayerForLastNarrator,
    turnsCompleted,
    turnsRemaining,
    turnBudget,
    liveInventory,
    leverageCards,
    castNameById,
    backendEnvelope: story.gameplay_envelope ?? null,
  })
  const showGameplayImpactSummary =
    actionAreaVisible && turnsCompleted > 0 && gameplayEnvelope.impact.length > 0
  const nextChoiceTargets = lastNarrator
    ? uniqueActionTargetsForOptions(lastNarrator.options, castNameById, lastNarrator.npc_pulse ?? [])
    : []
  const actorActionCounts = lastNarrator
    ? actionTargetCountsForOptions(lastNarrator.options, castNameById, lastNarrator.npc_pulse ?? [])
    : {}
  const resourceActionCounts = lastNarrator
    ? resourceActionCountsForOptions(lastNarrator.options, gameplayEnvelope.actionForecasts)
    : { time: 0, pressure: 0, evidence: 0 }
  const gameplayLoopStage: GameplayLoopStage = isComplete
    ? "ending"
    : busy
      ? "react"
      : showGameplayImpactSummary
        ? "update"
        : actionAreaVisible
          ? "choose"
          : "read"
  const actionJumpDetail =
    gameplayLoopStage === "update"
      ? t("play.action_jump_detail_update")
      : gameplayLoopStage === "choose"
        ? t("play.action_jump_detail_choose")
        : t("play.action_jump_detail_default")
  const focusedActorName = focusedActorId ? castNameById[focusedActorId] ?? focusedActorId : null
  const actorFocus = focusedActorId && focusedActorName
    ? { id: focusedActorId, name: focusedActorName }
    : null
  const focusedResourceTrack = focusedResourceId
    ? gameplayEnvelope.tracks.find((track) => track.id === focusedResourceId) ?? null
    : null
  const focusSceneActor = (actor: { id: string; name: string }) => {
    const wasFocused = focusedActorId === actor.id
    setFocusedActorId(wasFocused ? null : actor.id)
    if (!wasFocused) {
      setFocusedResourceId(null)
    }
    if (wasFocused || typeof window === "undefined" || !actionAreaVisible) return
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>("[data-play-action-area='true']")
        ?.scrollIntoView({
          block: "center",
          behavior: prefersReducedMotion ? "auto" : "smooth",
        })
    })
  }
  const focusGameplayResource = (resourceId: GameplayResourceFocusId) => {
    const wasFocused = focusedResourceId === resourceId
    setFocusedResourceId(wasFocused ? null : resourceId)
    if (!wasFocused) {
      setFocusedActorId(null)
    }
    if (wasFocused || typeof window === "undefined" || !actionAreaVisible) return
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>("[data-play-action-area='true']")
        ?.scrollIntoView({
          block: "center",
          behavior: prefersReducedMotion ? "auto" : "smooth",
        })
    })
  }
  const advisorSuggestions = buildAdvisorSuggestions({
    story,
    lastNarrator,
    leverageCards,
    turnsRemaining,
  })
  const failedActionRecovery = error
    ? buildFailedActionRecovery({
        action: lastFailedActionRef.current,
        options: lastNarrator?.options ?? [],
        castNameById,
        t,
      })
    : null

  return (
    <div style={ppStyles.page}>
      <Header
        onBackHome={onBackHome}
        title={story.template.title}
        turnCount={story.session.turn_count}
        turnBudget={story.session.turn_budget}
        coverUrl={cover}
      />

      <PlayShell compact={compactPlayChrome}>
        <MoodPlate
          story={story}
          coverUrl={cover}
          sceneUrl={latestMoodSceneUrl}
          turnsCompleted={turnsCompleted}
          turnBudget={turnBudget}
          turnsRemaining={turnsRemaining}
          compact={compactPlayChrome}
          isComplete={isComplete}
        />

        <PlaySurfaceGrid compact={compactPlayChrome}>
          <StoryTimeline innerRef={scrollerRef}>
          {!isComplete ? (
            <RunContextPanel
              story={story}
              turnsCompleted={turnsCompleted}
              turnBudget={turnBudget}
              turnsRemaining={turnsRemaining}
              liveInventory={liveInventory}
              leverageCards={leverageCards}
              isComplete={isComplete}
            />
          ) : null}

          {/* Gauntlet-mode goals stay as a single reminder line instead of
              another nested panel in the story column. */}
          {isGauntlet && story.template.player_goals && story.template.player_goals.length > 0 ? (
            <div style={ppStyles.goalsCard}>
              <span style={ppStyles.gauntletBadge}>{t("play.gauntlet_badge")}</span>
              <span style={ppStyles.goalsTitle}>{t("play.gauntlet_goals_title")}</span>
              {story.template.player_goals.map((g, idx) => (
                <div key={idx} style={ppStyles.goalRow}>
                  {idx > 0 ? <span style={ppStyles.goalDivider} aria-hidden>·</span> : null}
                  <span style={ppStyles.goalText}>{g.goal}</span>
                  <span style={ppStyles.goalStakes}>
                    {t("play.gauntlet_goal_stakes", { stakes: g.stakes })}
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          {!isComplete ? (
            <>
              <GameplayStatePanel
                envelope={gameplayEnvelope}
                focusedResourceId={focusedResourceId}
                resourceActionCounts={resourceActionCounts}
                onFocusResource={focusGameplayResource}
              />
              <GameplayLoopGuide
                stage={gameplayLoopStage}
                hasImpact={gameplayEnvelope.impact.length > 0}
              />
            </>
          ) : null}

          {isComplete && ending ? (
            <EndingScreen
              ending={ending}
              sessionId={sessionId}
              templateId={story.template.template_id}
              messages={story.messages}
              bookmarkedOrds={bookmarkedOrds}
              shareCopied={shareCopied}
              onShare={() => {
                const url = `${window.location.origin}/#/replay/${sessionId}`
                navigator.clipboard.writeText(url).then(
                  () => {
                    setShareCopied(true)
                    setTimeout(() => setShareCopied(false), 2200)
                  },
                  () => {
                    // Fallback: show URL in an alert if clipboard fails
                    window.prompt(t("play.share_prompt"), url)
                  },
                )
              }}
              onPlayAgain={() => {
                // Land on the template detail page where the user can
                // pick a different role and start a fresh session. We
                // deliberately don't auto-pick a different role for
                // them — letting them browse the role cards is part
                // of the replay loop.
                window.location.hash = `#/template/${story.template.template_id}`
              }}
              onBackHome={onBackHome}
            />
          ) : null}

          {story.messages.map((m, idx) => {
            // For player messages that picked an option, find the
            // previous narrator beat and look up the displayed option.
            // Using this in StoryBeat lets us render the exact option the
            // player chose instead of a terse backend handle like "let him".
            let pickedHandle: string | undefined
            let pickedActionText: string | undefined
            let previousPlayerMessage: NarrativeStoryMessage | undefined
            const hasFollowingPlayerEcho =
              m.role === "narrator" && story.messages[idx + 1]?.role === "player"
            if (m.role === "player" && idx > 0) {
              const prev = story.messages[idx - 1]
              if (
                prev?.role === "narrator" &&
                prev.chosen_option_index != null &&
                prev.options[prev.chosen_option_index]
              ) {
                const pickedOption = prev.options[prev.chosen_option_index]
                const parsedPickedOption = parseOptionLabel(pickedOption.label)
                pickedHandle = parsedPickedOption.tag || undefined
                pickedActionText = parsedPickedOption.body || pickedOption.label
              }
            }
            if (m.role === "narrator" && idx > 0) {
              const prev = story.messages[idx - 1]
              if (prev?.role === "player") {
                previousPlayerMessage = prev
              }
            }
            return (
              <StoryBeat
                key={`${m.role}-${m.ord}`}
                message={m}
                previousPlayerMessage={previousPlayerMessage}
                castNameById={castNameById}
                intensity={
                  m.role === "narrator"
                    ? computeBeatIntensity(m, turnBudget)
                    : "calm"
                }
                sceneUrl={
                  m.role === "narrator"
                    ? getSceneByPhase(
                        playSegmentPhaseForMessage(m, turnBudget),
                        `${story.template.template_id}|${m.ord}`,
                        playSegmentSceneCorpus(story, m),
                      )
                    : undefined
                }
                pickedHandle={pickedHandle}
                pickedActionText={pickedActionText}
                isLatestNarrator={m.role === "narrator" && m.ord === lastNarrator?.ord}
                hasFollowingPlayerEcho={hasFollowingPlayerEcho}
                suppressLatestFeedbackDigest={
                  m.role === "narrator" &&
                  m.ord === lastNarrator?.ord &&
                  showGameplayImpactSummary
                }
                isBookmarked={m.role === "narrator" && bookmarkedOrds.has(m.ord)}
                onToggleBookmark={
                  m.role === "narrator" && !isComplete
                    ? () => toggleBookmark(m.ord)
                    : undefined
                }
              />
            )
          })}

          {!isComplete && !busy && turnsCompleted > 0 ? (
            <GameplayImpactSummary
              envelope={gameplayEnvelope}
              castNameById={castNameById}
              nextChoiceTargets={nextChoiceTargets}
              sourceMoveText={impactSourceMove}
              focusedActorId={focusedActorId}
              onFocusActor={focusSceneActor}
            />
          ) : null}

          <AnimatePresence>
            {error ? (
              <PlayRetryRecoveryBanner
                recovery={failedActionRecovery}
                error={error}
                busy={busy}
                compact={compactPlayChrome}
                onRetry={lastFailedActionRef.current ? () => {
                  const a = lastFailedActionRef.current
                  if (!a) return
                  void handleAdvance(a, { keepRecoveryVisible: true })
                } : undefined}
              />
            ) : null}
          </AnimatePresence>

          {isFinalApproaching && !busy ? (
            <motion.div
              style={ppStyles.approachingFinaleBanner}
              variants={pulseVariants}
              initial="initial"
              animate="animate"
            >
              {turnsRemaining === 0
                ? t("play.finale_wrapping")
                : turnsRemaining === 1
                  ? t("play.finale_one_left")
                  : t("play.finale_two_left")}
            </motion.div>
          ) : null}

          {/* Action area pinned at the bottom of the story column.
              Hidden when the session is complete. */}
          {actionAreaVisible && lastNarrator ? (
            <ActionArea
              // Key on the narrator beat ord so the entire ActionArea
              // remounts each turn — option cascade re-fires from
              // {opacity: 0, x: -6} every advance, instead of only on
              // first paint. Free-input / diary text lives in parent
              // state, so remount doesn't drop user typing.
              key={`actions-${lastNarrator.ord}`}
              options={lastNarrator.options}
              actionForecasts={gameplayEnvelope.actionForecasts}
              leverageCards={leverageCards}
              roleHasNoLeverage={Boolean(story.session.player_role) && leverageCards.length === 0}
              latestNpcPulses={lastNarrator.npc_pulse ?? []}
              castNameById={castNameById}
              turnsCompleted={turnsCompleted}
              turnsRemaining={turnsRemaining}
              turnBudget={turnBudget}
              actorFocus={actorFocus}
              resourceFocus={focusedResourceId && focusedResourceTrack
                ? { id: focusedResourceId, label: focusedResourceTrack.label }
                : null}
              showFreeInput={showFreeInput}
              freeInput={freeInput}
              setFreeInput={setFreeInput}
              setShowFreeInput={setShowFreeInput}
              diary={diary}
              setDiary={setDiary}
              showDiary={showDiary}
              setShowDiary={setShowDiary}
              busy={busy}
              onCommitmentActiveChange={setActionCommitmentActive}
              onCommitmentSummaryChange={setActionCommitmentSummary}
              onClearActorFocus={() => setFocusedActorId(null)}
              onClearResourceFocus={() => setFocusedResourceId(null)}
              onPickOption={(i, diaryOverride) =>
                void handleAdvance({
                  chosen_option_index: i,
                  diary: (diaryOverride ?? diary).trim() || undefined,
                })
              }
              onPlayLeverage={(card, diaryOverride) =>
                void handleAdvance({
                  free_input: leveragePlayInput(card, story.template.language),
                  diary: (diaryOverride ?? diary).trim() || undefined,
                  played_leverage: {
                    card_id: card.card_id,
                    npc_id: card.npc_id,
                    leverage: card.leverage,
                    action: "reveal",
                  },
                })
              }
              onSubmitFree={(diaryOverride, freeInputOverride) => {
                const publicMove = (freeInputOverride ?? freeInput).trim()
                if (!publicMove) return
                void handleAdvance({
                  free_input: publicMove,
                  diary: (diaryOverride ?? diary).trim() || undefined,
                })
              }}
              />
          ) : !isComplete && busy ? (
            <LoadingShim variant="inline" label={t("play.busy_shim")} />
          ) : null}
          </StoryTimeline>

          <aside style={ppStyles.playRightRail}>
            {reviewerMode ? (
              <RuntimeInspector
                story={story}
                ending={ending}
                lastNarrator={lastNarrator}
                turnsRemaining={turnsRemaining}
                liveInventory={liveInventory}
                agentPlan={latestAgentPlan}
                agentEvents={latestAgentEvents}
                llmEvents={llmEvents}
                agentTraceAccessGranted={canRequestAgentTrace}
              />
            ) : null}
            {!isComplete ? (
              <SceneSupportRail
                story={story}
                lastNarrator={lastNarrator}
                compact={compactPlayChrome}
                advisorAvatarUrl={advisorAvatar}
                advisorPersona={story.template.advisor_persona}
                focusedActorId={focusedActorId}
                actorActionCounts={actorActionCounts}
                onFocusActor={focusSceneActor}
                onAskAdvisor={openAdvisor}
              />
            ) : null}
          </aside>
        </PlaySurfaceGrid>
      </PlayShell>

      {/* Floating advisor button + sidechat */}
      <AnimatePresence>
        {!isComplete && !advisorOpen && !actionCommitmentActive && !actionAreaVisible ? (
          <AdvisorFab
            onOpen={openAdvisor}
            avatarUrl={advisorAvatar}
            persona={story.template.advisor_persona}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {!isComplete && advisorOpen ? (
          <AdvisorSidechat
            sessionId={sessionId}
            persona={story.template.advisor_persona}
            avatarUrl={advisorAvatar}
            turnsRemaining={turnsRemaining}
            isComplete={isComplete}
            isCommitmentActive={actionCommitmentActive}
            commitmentSummary={actionCommitmentSummary}
            suggestions={advisorSuggestions}
            onClose={closeAdvisor}
            onOracleConsumed={(newBudget) => {
              // Update local session budget so the header chip updates
              // immediately and the oracle button respects the new
              // remaining count.
              setStory((prev) =>
                prev
                  ? {
                      ...prev,
                      session: { ...prev.session, turn_budget: newBudget },
                    }
                  : prev,
              )
            }}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {showActionJump ? (
          <PlayActionJumpButton
            detail={actionJumpDetail}
            onClick={handleActionJump}
            stage={gameplayLoopStage}
          />
        ) : null}
      </AnimatePresence>
    </div>
  )
}
