import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react"
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
  StoryBeat,
  buildAdvisorSuggestions,
  buildFailedActionRecovery,
  computeBeatIntensity,
  computeLiveInventory,
  latestAgentPlanFromEvents,
  parseOptionLabel,
} from "./components/play-flow-panels"
import { PlayRetryRecoveryBanner } from "./components/play-retry-recovery"

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

  const scrollToPlayActionArea = useCallback(() => {
    if (typeof document === "undefined") return
    const actionArea = document.querySelector<HTMLElement>("[data-play-action-area='true']")
    if (!actionArea) return
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    actionArea.scrollIntoView({
      block: "center",
      behavior: prefersReducedMotion ? "auto" : "smooth",
    })
  }, [])

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
    if (!story || !compactPlayChrome || busy || advisorOpen || ending) {
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
      const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
      const rect = actionArea.getBoundingClientRect()
      const lowerComfortEdge = window.innerHeight - 132
      const isAwayFromAction =
        rect.top < headerHeight + 10 ||
        rect.top > lowerComfortEdge ||
        rect.bottom > window.innerHeight + 48
      setShowActionJump(isAwayFromAction)
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
        />

        <PlaySurfaceGrid compact={compactPlayChrome}>
          <StoryTimeline innerRef={scrollerRef}>
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
                isBookmarked={m.role === "narrator" && bookmarkedOrds.has(m.ord)}
                onToggleBookmark={
                  m.role === "narrator" && !isComplete
                    ? () => toggleBookmark(m.ord)
                    : undefined
                }
              />
            )
          })}

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
              leverageCards={leverageCards}
              roleHasNoLeverage={Boolean(story.session.player_role) && leverageCards.length === 0}
              latestNpcPulses={lastNarrator.npc_pulse ?? []}
              castNameById={castNameById}
              turnsCompleted={turnsCompleted}
              turnsRemaining={turnsRemaining}
              turnBudget={turnBudget}
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
              onOpenAdvisor={openAdvisor}
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
              onSubmitFree={(diaryOverride) => {
                if (!freeInput.trim()) return
                void handleAdvance({
                  free_input: freeInput.trim(),
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
          <motion.button
            key="play-action-jump"
            type="button"
            data-play-action-jump="true"
            style={ppStyles.actionJumpButton}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={transitions.snap}
            onClick={scrollToPlayActionArea}
            aria-label={t("play.action_jump_title")}
            title={t("play.action_jump_title")}
          >
            <span style={ppStyles.actionJumpKicker}>{t("play.action_jump_kicker")}</span>
            <strong style={ppStyles.actionJumpText}>{t("play.action_jump_label")}</strong>
          </motion.button>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
