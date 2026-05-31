import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion, useReducedMotion, type TargetAndTransition } from "motion/react"
import type {
  NarrativeAdvisorMessage,
  NarrativeEnding,
  NarrativeNPCPulse,
  NarrativePlayedLeverageCard,
  NarrativePlayerLeverageOverNPC,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../api/contracts"
import { useApi } from "../../app/api-context"
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
  getAvatarForCastMember,
  getCoverForTemplate,
  getEndingIllustration,
  getPeakCloseUp,
  getTierSplash,
} from "../../shared/lib/webtoon-assets"

type PlayAdvanceAction = {
  chosen_option_index?: number
  free_input?: string
  diary?: string
  played_leverage?: NarrativePlayedLeverageCard
}

type LeverageCardView = {
  card_id: string
  npc_id: string
  target_name: string
  leverage: string
  used: boolean
}

type ActionCommitmentSummary = {
  kind: "option" | "leverage" | "free"
  kicker: string
  title: string
  detail?: string
  motive?: string
}

const ACTION_LEVERAGE_RAIL_ID = "play-leverage-rail"

function leverageCardId(roleId: string | undefined, lev: NarrativePlayerLeverageOverNPC, index: number): string {
  return `lev:${roleId || "role"}:${lev.npc_id}:${index}`
}

function leveragePlayInput(card: LeverageCardView, language: NarrativeStoryHistoryResponse["template"]["language"]): string {
  if (language === "zh") {
    return `我亮出手里针对 ${card.target_name} 的把柄：${card.leverage}`
  }
  return `I reveal the leverage I hold over ${card.target_name}: ${card.leverage}`
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
  const t = useT()
  const [story, setStory] = useState<NarrativeStoryHistoryResponse | null>(null)
  const [ending, setEnding] = useState<NarrativeEnding | null>(null)
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
  const lastFailedActionRef = useRef<{
    chosen_option_index?: number
    free_input?: string
    diary?: string
    played_leverage?: NarrativePlayedLeverageCard
  } | null>(null)
  const [freeInput, setFreeInput] = useState("")
  const [showFreeInput, setShowFreeInput] = useState(false)
  const [diary, setDiary] = useState("")
  const [showDiary, setShowDiary] = useState(false)
  const [advisorOpen, setAdvisorOpen] = useState(false)
  const advisorReturnFocusRef = useRef<HTMLElement | null>(null)
  const [actionCommitmentActive, setActionCommitmentActive] = useState(false)
  const [actionCommitmentSummary, setActionCommitmentSummary] = useState<ActionCommitmentSummary | null>(null)
  const [shareCopied, setShareCopied] = useState(false)
  const compactPlayChrome = useCompactLayout("(max-width: 680px)")

  // Initial load: story + (if already completed) the ending.
  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .getNarrativeStory(sessionId)
      .then(async (response) => {
        if (cancelled) return
        setStory(response)
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
  }, [api, sessionId])

  // Auto-scroll to the current decision point whenever content arrives.
  // The page uses native document scroll for a less pane-like reading
  // feel, but this still tolerates older nested-scroll layouts.
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const el = scrollerRef.current
    if (!el || !story || story.session.ending_label) return

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
      const actionArea = document.querySelector<HTMLElement>("[data-play-action-area='true']")
      if (!actionArea) return
      const headerHeight = document.querySelector("header")?.getBoundingClientRect().height ?? 0
      const rect = actionArea.getBoundingClientRect()
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
    async (action: PlayAdvanceAction) => {
      if (busy) return
      setBusy(true)
      setError(null)
      setActionCommitmentActive(false)
      setActionCommitmentSummary(null)
      lastFailedActionRef.current = null
      try {
        const response = await api.advanceNarrativeTurn(sessionId, action)
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
        setFreeInput("")
        setShowFreeInput(false)
        setDiary("")
        setShowDiary(false)
      } catch (err) {
        setError(friendlyError(err, t("play.error_advance")))
        lastFailedActionRef.current = action
      } finally {
        setBusy(false)
      }
    },
    [api, busy, sessionId],
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
        cast={story.template.cast.map((c) => c.display_name)}
        turnCount={story.session.turn_count}
        turnBudget={story.session.turn_budget}
        coverUrl={cover}
      />

      <main style={ppStyles.main}>
        <div className="play-story-column" style={ppStyles.storyColumn} ref={scrollerRef}>
          <RunContextPanel
            story={story}
            turnsCompleted={turnsCompleted}
            turnBudget={turnBudget}
            turnsRemaining={turnsRemaining}
            liveInventory={liveInventory}
            leverageCards={leverageCards}
            isComplete={isComplete}
          />

          {reviewerMode ? (
            <RuntimeInspector
              story={story}
              ending={ending}
              lastNarrator={lastNarrator}
              turnsRemaining={turnsRemaining}
              liveInventory={liveInventory}
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

          {story.messages.map((m, idx) => {
            // For player messages that picked an option, find the
            // previous narrator beat and look up the option's handle.
            // Using this in StoryBeat lets us render "you picked: 亮录音"
            // as a memory anchor instead of the full intent-tagged sentence.
            let pickedHandle: string | undefined
            let previousPlayerMessage: NarrativeStoryMessage | undefined
            const hasFollowingPlayerEcho =
              m.role === "narrator" && story.messages[idx + 1]?.role === "player"
            if (m.role === "player" && idx > 0) {
              const prev = story.messages[idx - 1]
              if (
                prev?.role === "narrator" &&
                prev.chosen_option_index != null &&
                prev.options[prev.chosen_option_index]?.handle
              ) {
                pickedHandle = prev.options[prev.chosen_option_index].handle
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
                sceneUrl={m.role === "narrator" ? getPeakCloseUp(m.ord) : undefined}
                pickedHandle={pickedHandle}
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
              <motion.div
                key="play-error"
                style={{
                  ...ppStyles.errorInline,
                  ...(compactPlayChrome ? ppStyles.errorInlineCompact : null),
                }}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={transitions.snap}
                role="alert"
              >
                <div style={ppStyles.errorInlineCopy}>
                  <span style={ppStyles.errorInlineKicker}>
                    {failedActionRecovery?.kicker ?? t("play.recovery_generic_kicker")}
                  </span>
                  <strong style={ppStyles.errorInlineTitle}>
                    {failedActionRecovery?.title ?? t("play.recovery_generic_title")}
                  </strong>
                  <span style={ppStyles.errorInlineText}>
                    {failedActionRecovery?.detail ?? t("play.recovery_generic_detail")}
                  </span>
                  <span style={ppStyles.errorInlineSignal}>
                    <span style={ppStyles.errorInlineSignalLabel}>{t("play.recovery_signal_label")}</span>
                    {error}
                  </span>
                  {failedActionRecovery?.chips.length ? (
                    <span style={ppStyles.errorInlineChips}>
                      {failedActionRecovery.chips.map((chip) => (
                        <span key={chip} style={ppStyles.errorInlineChip} title={chip}>{chip}</span>
                      ))}
                    </span>
                  ) : null}
                </div>
                {lastFailedActionRef.current ? (
                  <button
                    type="button"
                    style={ppStyles.errorInlineRetry}
                    aria-label={t("play.recovery_retry_same_title")}
                    title={t("play.recovery_retry_same_title")}
                    onClick={() => {
                      const a = lastFailedActionRef.current
                      if (!a) return
                      void handleAdvance(a)
                    }}
                  >
                    {t("play.recovery_retry_same")}
                  </button>
                ) : null}
              </motion.div>
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

          {/* Ending screen — only when the session has finished */}
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
        </div>
      </main>

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
    </div>
  )
}

function buildAdvisorSuggestions({
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
  const focalNpc = cast[0]?.display_name ?? (language === "zh" ? "对方" : "the other side")
  const openLeverage = leverageCards.find((card) => !card.used)
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

type FailedActionRecovery = {
  kicker: string
  title: string
  detail: string
  chips: string[]
}

function truncateRecoveryText(value: string, max = 64): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function buildFailedActionRecovery({
  action,
  options,
  castNameById,
  t,
}: {
  action: PlayAdvanceAction | null
  options: NarrativeStoryMessage["options"]
  castNameById: Record<string, string>
  t: ReturnType<typeof useT>
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

function RunContextPanel({
  story,
  turnsCompleted,
  turnBudget,
  turnsRemaining,
  liveInventory,
  leverageCards,
  isComplete,
}: {
  story: NarrativeStoryHistoryResponse
  turnsCompleted: number
  turnBudget: number
  turnsRemaining: number
  liveInventory: string[]
  leverageCards: LeverageCardView[]
  isComplete: boolean
}) {
  const t = useT()
  const compactRunContext = useCompactLayout("(max-width: 680px)")
  const role = story.session.player_role
  const upcomingTurn = Math.min(turnBudget - 1, turnsCompleted + 1)
  const stageKey = stageForLocal(upcomingTurn, turnBudget)
  const stageLabelKey = `stage_bar.${stageKey === "pre_finale_open" ? "pre_finale" : stageKey}` as Parameters<typeof t>[0]
  const stage = t(stageLabelKey, stageDisplayName(stageKey))
  const trumpResourceText =
    leverageCards.length === 1
      ? t("play.status_trump_one")
      : leverageCards.length > 1
        ? t("play.status_trump_many", { count: leverageCards.length })
        : ""
  const itemResourceText =
    liveInventory.length === 1
      ? t("play.status_item_one")
      : liveInventory.length > 1
        ? t("play.status_item_many", { count: liveInventory.length })
        : ""
  const privateResourceParts = [trumpResourceText, itemResourceText].filter(Boolean)
  const privateResourceText = role ? privateResourceParts.join(" · ") : ""
  const runStatusText = isComplete
    ? t("play.status_done")
    : t("play.status_turns_left", { count: turnsRemaining })
  const runMetaText = [stage, runStatusText, privateResourceText].filter(Boolean).join(" · ")
  const runProgressLabel = t("stage_bar.aria", {
    turn: turnsCompleted,
    total: turnBudget,
    stage,
  })
  const runProgressPercent = Math.max(
    0,
    Math.min(100, (turnsCompleted / Math.max(turnBudget, 1)) * 100),
  )
  const renderRunProgress = () =>
    !isComplete ? (
      <span
        style={ppStyles.runProgressTrack}
        role="progressbar"
        aria-label={runProgressLabel}
        aria-valuemin={0}
        aria-valuemax={turnBudget}
        aria-valuenow={turnsCompleted}
      >
        <span
          style={{
            ...ppStyles.runProgressFill,
            width: `${runProgressPercent}%`,
          }}
        />
      </span>
    ) : null

  if (compactRunContext) {
    return (
      <motion.section
        style={{ ...ppStyles.runContextPanel, ...ppStyles.runContextPanelCompact }}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={itemTransition}
        aria-label={t("play.run_context_label")}
      >
        <div style={ppStyles.runCompactHeader}>
          <span style={ppStyles.runCompactRoleTag}>{t("play.run_identity_prefix")}</span>
          <Truncated style={ppStyles.runCompactRoleTitle}>
            {role?.label ?? story.template.title}
          </Truncated>
          <span style={ppStyles.runCompactMeta}>{runMetaText}</span>
        </div>
        {role ? (
          <div style={ppStyles.runCompactObjective}>
            <strong style={ppStyles.runCompactObjectiveText}>
              {role.hidden_objective}
            </strong>
          </div>
        ) : null}
        {renderRunProgress()}
      </motion.section>
    )
  }

  return (
    <motion.section
      style={{
        ...ppStyles.runContextPanel,
        ...(compactRunContext ? ppStyles.runContextPanelCompact : null),
      }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={itemTransition}
      aria-label={t("play.run_context_label")}
    >
      <div style={ppStyles.runContextHeader}>
        <span style={ppStyles.runKicker}>{t("play.run_identity_prefix")}</span>
        <Truncated style={ppStyles.runRoleTitle}>
          {role?.label ?? story.template.title}
        </Truncated>
        <span style={ppStyles.runContextMeta}>{runMetaText}</span>
      </div>
      {role ? (
        <div style={ppStyles.runContextObjectiveLine}>
          <strong style={ppStyles.runContextObjectiveText}>{role.hidden_objective}</strong>
        </div>
      ) : null}
      {renderRunProgress()}
    </motion.section>
  )
}

function RuntimeInspector({
  story,
  ending,
  lastNarrator,
  turnsRemaining,
  liveInventory,
}: {
  story: NarrativeStoryHistoryResponse
  ending: NarrativeEnding | null
  lastNarrator: NarrativeStoryMessage | null
  turnsRemaining: number
  liveInventory: string[]
}) {
  const { lang } = useLanguage()
  const t = useT()
  const upcomingTurn = Math.min(story.session.turn_budget - 1, story.session.turn_count + 1)
  const stageKey = stageForLocal(upcomingTurn, story.session.turn_budget)
  const stageLabelKey = `stage_bar.${stageKey === "pre_finale_open" ? "pre_finale" : stageKey}` as Parameters<typeof t>[0]
  const stage = t(stageLabelKey, stageDisplayName(stageKey))
  const playerTurns = story.messages.filter((m) => m.role === "player").length
  const endingLabel = ending
    ? displayEndingLabel(ending.label, lang)
    : story.session.ending_label
      ? displayEndingLabel(story.session.ending_label, lang)
      : t("play.runtime_pending")
  const language = story.template.language === "zh" ? t("play.runtime_language_zh") : t("play.runtime_language_en")
  const inventoryState =
    liveInventory.length === 1
      ? t("play.status_item_one")
      : t("play.status_item_many", { count: liveInventory.length })

  const summaryRows = [
    { label: t("play.runtime_current_stage"), value: stage },
    { label: t("play.runtime_turns_played"), value: `${playerTurns} / ${story.session.turn_budget}` },
    { label: t("play.runtime_live_options"), value: String(lastNarrator?.options.length ?? 0) },
    { label: t("play.runtime_inventory_state"), value: inventoryState },
    { label: t("play.runtime_ending_compiler"), value: endingLabel },
  ]
  const detailRows = [
    { label: t("play.runtime_seed"), value: story.template.title },
    { label: t("play.runtime_language"), value: language },
    { label: t("play.runtime_player_role"), value: story.session.player_role?.label ?? t("play.runtime_auto_selected") },
    { label: t("play.runtime_turns_left"), value: String(turnsRemaining) },
  ]

  return (
    <motion.section
      style={ppStyles.runtimeInspector}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={itemTransition}
      aria-label={t("play.runtime_inspector_label")}
    >
      <div style={ppStyles.runtimeInspectorHeader}>
        <span style={ppStyles.runtimeInspectorKicker}>{t("play.runtime_inspector_kicker")}</span>
        <strong>{t("play.runtime_inspector_title")}</strong>
      </div>
      <div style={ppStyles.runtimeInspectorGrid}>
        {summaryRows.map((row) => (
          <div style={ppStyles.runtimeInspectorRow} key={row.label}>
            <span style={ppStyles.runtimeInspectorRowLabel}>{row.label}</span>
            <strong style={ppStyles.runtimeInspectorRowValue}>{row.value}</strong>
          </div>
        ))}
      </div>
      <details style={ppStyles.runtimeInspectorDetails}>
        <summary style={ppStyles.runtimeInspectorDetailsSummary}>
          {t("play.runtime_inspector_summary")}
        </summary>
        <div style={ppStyles.runtimeInspectorDetailGrid}>
          {detailRows.map((row) => (
            <div style={ppStyles.runtimeInspectorDetailRow} key={row.label}>
              <span style={ppStyles.runtimeInspectorRowLabel}>{row.label}</span>
              <strong style={ppStyles.runtimeInspectorRowValue}>{row.value}</strong>
            </div>
          ))}
        </div>
      </details>
    </motion.section>
  )
}

function stageDisplayName(stage: string): string {
  if (stage === "hook") return "Prelude"
  if (stage === "pressure") return "Build"
  if (stage === "reversal") return "Turn"
  if (stage === "climax") return "Climax"
  if (stage === "pre_finale" || stage === "pre_finale_open") return "Coda"
  return stage.replace(/_/g, " ")
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function Header({
  onBackHome,
  title,
  cast,
  turnCount,
  turnBudget,
  coverUrl,
}: {
  onBackHome: () => void
  title: string
  cast?: string[]
  turnCount?: number
  turnBudget?: number
  coverUrl?: string
}) {
  const t = useT()
  const compactHeader = useCompactLayout()
  const showCoverHeader = Boolean(coverUrl && !compactHeader)
  const headerStyle: CSSProperties = showCoverHeader
    ? {
        ...ppStyles.header,
        ...ppStyles.headerWithCover,
        backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.55) 0%, rgba(20,16,12,0.92) 100%), url(${coverUrl})`,
      }
    : compactHeader
      ? { ...ppStyles.header, ...ppStyles.headerCompact }
    : ppStyles.header

  const showProgress = typeof turnCount === "number" && typeof turnBudget === "number"
  const pct = showProgress ? Math.min(100, (turnCount! / turnBudget!) * 100) : 0

  return (
    <header style={headerStyle}>
      <div style={{ ...ppStyles.headerRow, ...(compactHeader ? ppStyles.headerRowCompact : null) }}>
        <button
          style={
            showCoverHeader
              ? { ...ppStyles.backBtn, ...ppStyles.backBtnOnCover }
              : { ...ppStyles.backBtn, ...(compactHeader ? ppStyles.backBtnCompact : null) }
          }
          onClick={onBackHome}
          type="button"
        >
          {compactHeader ? t("play.back_home_short") : t("play.back_home")}
        </button>
        <div style={ppStyles.headerTitle}>
          <Truncated
            style={
              showCoverHeader
                ? { ...ppStyles.headerTitleLine, color: "white" }
                : { ...ppStyles.headerTitleLine, ...(compactHeader ? ppStyles.headerTitleLineCompact : null) }
            }
          >
            {title}
          </Truncated>
          {!compactHeader && cast && cast.length ? (
            <div
              style={
                showCoverHeader
                  ? { ...ppStyles.headerCast, color: "rgba(255,255,255,0.78)" }
                  : ppStyles.headerCast
              }
              title={cast.join(" · ")}
            >
              {cast.join(" · ")}
              {showProgress ? (
                <span style={ppStyles.headerTurns}>
                  {t("play.header_turn_count", { current: turnCount!, total: turnBudget! })}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        {compactHeader && showProgress ? (
          <span style={ppStyles.headerTurnsCompact}>
            {t("play.header_turn_count_short", { current: turnCount!, total: turnBudget! })}
          </span>
        ) : (
          <span style={ppStyles.headerSpacer} />
        )}
      </div>
      {showProgress ? (
        <div style={ppStyles.progressTrack}>
          <div
            style={{
              ...ppStyles.progressFill,
              width: `${pct}%`,
            }}
          />
        </div>
      ) : null}
    </header>
  )
}

function EndingScreen({
  ending,
  sessionId,
  templateId,
  messages,
  bookmarkedOrds,
  shareCopied,
  onShare,
  onPlayAgain,
  onBackHome,
}: {
  ending: NarrativeEnding
  sessionId: string
  templateId: string
  messages: NarrativeStoryMessage[]
  bookmarkedOrds: Set<number>
  shareCopied: boolean
  onShare: () => void
  onPlayAgain: () => void
  onBackHome: () => void
}) {
  void templateId
  const t = useT()
  const { lang } = useLanguage()

  // Merge user bookmarks into the LLM's highlight list. User picks
  // get a `userMarked` flag and a synthesized headline / body
  // excerpt so they slot into the same card layout. Dedupe against
  // LLM picks (same ord = the LLM and the user both flagged it,
  // collapse into one card with the badge).
  type DisplayHighlight = {
    beat_ord: number
    headline: string
    body_excerpt: string
    why_pivotal: string
    userMarked: boolean
  }
  const llmHighlights: DisplayHighlight[] = (ending.highlights ?? []).map((h) => ({
    beat_ord: h.beat_ord,
    headline: h.headline,
    body_excerpt: h.body_excerpt,
    why_pivotal: h.why_pivotal,
    userMarked: bookmarkedOrds.has(h.beat_ord),
  }))
  const llmOrds = new Set(llmHighlights.map((h) => h.beat_ord))
  const narratorByOrd = new Map(
    messages.filter((m) => m.role === "narrator").map((m) => [m.ord, m]),
  )
  const userOnlyHighlights: DisplayHighlight[] = Array.from(bookmarkedOrds)
    .filter((ord) => !llmOrds.has(ord))
    .map((ord) => {
      const m = narratorByOrd.get(ord)
      return {
        beat_ord: ord,
        headline: t("play.ending_user_bookmark"),
        body_excerpt: m?.content?.slice(0, 200) ?? "",
        why_pivotal: "",
        userMarked: true,
      }
    })
    .filter((h) => h.body_excerpt.length > 0)
  const mergedHighlights: DisplayHighlight[] = [
    // User-only marks lead so the user's voice is first.
    ...userOnlyHighlights,
    ...llmHighlights,
  ].sort((a, b) => a.beat_ord - b.beat_ord)

  // Skip the 1.7s choreography in two cases:
  //  1. User prefers reduced motion (a11y system pref)
  //  2. They've already seen this exact ending in this browser session
  //     — re-opening the run page (back/forward, refresh) shouldn't
  //     replay the splash; it's the first view that earns the
  //     ceremony.
  const reducedMotion = useReducedMotion()
  const [hasSeenBefore] = useState(() => {
    if (typeof window === "undefined") return false
    try {
      return window.sessionStorage.getItem(
        `tiny-stories-ending-seen-${sessionId}`,
      ) === "1"
    } catch {
      return false
    }
  })
  useEffect(() => {
    try {
      window.sessionStorage.setItem(
        `tiny-stories-ending-seen-${sessionId}`,
        "1",
      )
    } catch {
      // sessionStorage unavailable (private mode) — fail silently;
      // worst case the splash plays again on refresh.
    }
  }, [sessionId])
  const skipChoreography = Boolean(reducedMotion) || hasSeenBefore

  // Helper: collapse `initial` state to `false` (= start at animate
  // target, no entrance) and zero out staggered delays when skipping.
  const initialOr = (
    full: TargetAndTransition,
  ): TargetAndTransition | false => (skipChoreography ? false : full)
  const delayOr = (delay: number): number =>
    skipChoreography ? 0 : delay

  const illustration = getEndingIllustration(ending.label)
  const endingDisplayLabel = displayEndingLabel(ending.label, lang)
  const endingSubtitle = lang === "en" ? `"${ending.subtitle}"` : `「${ending.subtitle}」`
  const tier = ending.tier ?? "compromised"
  const tierSplash = getTierSplash(tier)
  const tierVisuals: Record<string, { ribbon: string; labelColor: string; gradient: string; badgeText: string }> = {
    victory: {
      ribbon: t("play.ending_ribbon_victory"),
      badgeText: t("play.ending_tier_victory"),
      labelColor: "rgba(245,210,140,0.96)",
      gradient: "linear-gradient(180deg, rgba(180,140,40,0.0) 0%, rgba(60,40,15,0.55) 75%, var(--bg-elev) 100%)",
    },
    compromised: {
      ribbon: t("play.ending_ribbon_compromised"),
      badgeText: t("play.ending_tier_compromised"),
      labelColor: "var(--text)",
      gradient: "linear-gradient(180deg, rgba(20,16,12,0.15) 0%, rgba(20,16,12,0.6) 75%, var(--bg-elev) 100%)",
    },
    collapsed: {
      ribbon: ending.early_terminated ? t("play.ending_ribbon_early") : t("play.ending_ribbon_collapsed"),
      badgeText: ending.early_terminated ? t("play.ending_tier_early") : t("play.ending_tier_collapsed"),
      labelColor: "rgba(245,180,170,0.96)",
      gradient: "linear-gradient(180deg, rgba(60,10,10,0.25) 0%, rgba(50,8,8,0.78) 75%, var(--bg-elev) 100%)",
    },
  }
  const tv = tierVisuals[tier]
  return (
    <motion.section
      style={ppStyles.endingSection}
      initial={skipChoreography ? "animate" : "initial"}
      animate="animate"
      transition={{
        staggerChildren: skipChoreography ? 0 : 0.18,
        delayChildren: delayOr(0.1),
      }}
    >
      <motion.div
        variants={itemVariants}
        transition={itemTransition}
        style={ppStyles.endingDivider}
      >
        <span style={ppStyles.endingDividerLabel}>{tv.ribbon}</span>
      </motion.div>
      <motion.div
        variants={itemVariants}
        transition={itemTransition}
        style={ppStyles.endingCard}
      >
        {/* Illustrated banner — the visual punctuation that makes the
            ending feel like a closed object the player can screenshot. */}
        <motion.div
          initial={initialOr({ opacity: 0, scale: 1.06 })}
          animate={{ opacity: 1, scale: 1 }}
          transition={transitions.slow}
          style={{
            ...ppStyles.endingHero,
            backgroundImage: `${tv.gradient}, url(${illustration})`,
          }}
        >
          {tierSplash ? (
            <motion.div
              initial={initialOr({ opacity: 0, scale: 1.12 })}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: delayOr(0.25), ...transitions.ceremony }}
              style={{
                ...ppStyles.endingSplashOverlay,
                backgroundImage: `url(${tierSplash})`,
              }}
            />
          ) : null}
          <div style={ppStyles.endingTierBadge}>
            <span style={ppStyles.endingTierBadgeText}>{tv.badgeText}</span>
            {ending.early_terminated && ending.failure_trigger ? (
              <span style={ppStyles.endingTierTrigger}>
                {t("play.ending_trigger_prefix", { trigger: ending.failure_trigger })}
              </span>
            ) : null}
          </div>
        </motion.div>
        <div style={ppStyles.endingCardInner}>
        <motion.div
          initial={initialOr({ opacity: 0, scale: 0.6 })}
          animate={{ opacity: 1, scale: 1 }}
          transition={
            skipChoreography
              ? transitions.snap
              : labelChipSpring
          }
          style={{ ...ppStyles.endingLabelChip, color: tv.labelColor }}
        >
          {endingDisplayLabel}
        </motion.div>
        <motion.h2
          initial={initialOr({ opacity: 0, y: 14 })}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: delayOr(0.6), ...itemTransition }}
          style={ppStyles.endingSubtitle}
        >
          {endingSubtitle}
        </motion.h2>
        <motion.div
          initial={initialOr({ opacity: 0 })}
          animate={{ opacity: 1 }}
          transition={{ delay: delayOr(0.85), ...transitions.slow }}
          style={ppStyles.endingPassage}
        >
          {ending.passage}
        </motion.div>

        {/* Highlight reel — LLM picks merged with user bookmarks. Kept as
            a text recap instead of a stack of separate cards. */}
        {mergedHighlights.length > 0 ? (
          <motion.section
            initial={initialOr({ opacity: 0, y: 12 })}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: delayOr(1.0), ...itemTransition }}
            style={ppStyles.highlightReel}
          >
            <div style={ppStyles.highlightReelLabel}>
              {t("play.ending_highlights_title", { count: mergedHighlights.length })}
            </div>
            <div style={ppStyles.highlightList}>
              {mergedHighlights.map((h, i) => (
                <motion.div
                  key={`${h.beat_ord}-${i}`}
                  initial={initialOr({ opacity: 0, x: -8 })}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: delayOr(1.05 + cascadeDelay(i, 0.08)), ...itemTransition }}
                  style={{
                    ...ppStyles.highlightCard,
                    ...(h.userMarked ? ppStyles.highlightCardUserMarked : null),
                  }}
                >
                  <div style={ppStyles.highlightHeader}>
                    <span style={ppStyles.highlightIndex}>{i + 1}</span>
                    {h.userMarked ? (
                      <span style={ppStyles.highlightUserMark} aria-label={t("play.bookmark_user_mark_label")}>
                        ★
                      </span>
                    ) : null}
                    <span style={ppStyles.highlightHeadline}>{h.headline}</span>
                  </div>
                  <div style={ppStyles.highlightBody}>{h.body_excerpt}</div>
                  {h.why_pivotal ? (
                    <div style={ppStyles.highlightWhy}>{h.why_pivotal}</div>
                  ) : null}
                </motion.div>
              ))}
            </div>
          </motion.section>
        ) : null}

        {/* Branches — alternate paths the player didn't take, driving replay
            intent without switching into dashboard cards. */}
        {ending.branches && ending.branches.length > 0 ? (
          <motion.section
            initial={initialOr({ opacity: 0, y: 12 })}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: delayOr(1.25), ...itemTransition }}
            style={ppStyles.branchesSection}
          >
            <div style={ppStyles.branchesLabel}>
              {t("play.ending_branches_title", { count: ending.branches.length })}
            </div>
            <p style={ppStyles.branchesHint}>
              {t("play.ending_branches_hint")}
            </p>
            <div style={ppStyles.branchList}>
              {ending.branches.map((b, i) => {
                const tierStyle =
                  b.alternate_ending_tier === "victory"
                    ? ppStyles.branchTierVictory
                    : b.alternate_ending_tier === "collapsed"
                      ? ppStyles.branchTierCollapsed
                      : ppStyles.branchTierCompromised
                return (
                  <motion.div
                    key={`${b.pivot_beat_ord}-${i}`}
                    initial={initialOr({ opacity: 0, x: -8 })}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: delayOr(1.3 + cascadeDelay(i, 0.08)), ...itemTransition }}
                    style={ppStyles.branchCard}
                  >
                    <div style={ppStyles.branchTurnBadge}>
                      {t("play.ending_branch_turn", { turn: Math.floor(b.pivot_beat_ord / 2) })}
                    </div>
                    <div style={ppStyles.branchPaths}>
                      <div style={ppStyles.branchChosen}>
                        <span style={ppStyles.branchPathTag}>{t("play.ending_branch_chosen_tag")}</span>
                        <span style={ppStyles.branchPathText}>{b.chosen_path_summary}</span>
                      </div>
                      <div style={ppStyles.branchArrow}>{t("play.ending_branch_arrow")}</div>
                      <div style={ppStyles.branchAlternate}>
                        <span style={ppStyles.branchPathTag}>{t("play.ending_branch_alt_tag")}</span>
                        <span style={ppStyles.branchPathText}>{b.alternate_path_summary}</span>
                      </div>
                    </div>
                    <div style={ppStyles.branchOutcome}>
                      <span style={{ ...ppStyles.branchEndingChip, ...tierStyle }}>
                        {displayEndingLabel(b.alternate_ending_label, lang)}
                      </span>
                      <span style={ppStyles.branchRationale}>{b.rationale}</span>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </motion.section>
        ) : null}

        <motion.div
          initial={initialOr({ opacity: 0, y: 8 })}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: delayOr(1.7), ...itemTransition }}
          style={ppStyles.endingActions}
        >
          <div style={ppStyles.endingActionsRow}>
            <motion.button
              onClick={onShare}
              type="button"
              style={ppStyles.endingPrimaryAction}
              whileHover={{ scale: 1.02 }}
              whileTap={tapPress}
              key={shareCopied ? "copied" : "default"}
              initial={shareCopied ? { scale: 0.92 } : false}
              animate={shareCopied ? { scale: [0.92, 1.06, 1] } : { scale: 1 }}
              transition={transitions.base}
            >
              {shareCopied ? t("play.ending_share_copied") : t("play.ending_share")}
            </motion.button>
            {/* Replay-with-different-role — closes the loop. Without
                this, finishing a run was a dead end; user had to nav
                back home → find template → re-pick role. Now it's
                one click. We deliberately route through the template
                detail page rather than auto-picking a new role —
                seeing the role cards is part of the re-engagement. */}
            <motion.button
              style={ppStyles.endingTextAction}
              onClick={onPlayAgain}
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={tapPress}
            >
              {t("play.ending_replay")}
            </motion.button>
            <motion.button
              style={ppStyles.endingTextActionMuted}
              onClick={onBackHome}
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={tapPress}
            >
              {t("action.back_home")}
            </motion.button>
          </div>
          <p style={ppStyles.endingShareHint}>
            {t("play.ending_share_hint")}
          </p>
        </motion.div>
        </div>
      </motion.div>
    </motion.section>
  )
}

// ---------------------------------------------------------------------------
// Single story beat (narrator passage or player move)
// ---------------------------------------------------------------------------

function StoryBeat({
  message,
  previousPlayerMessage,
  castNameById,
  intensity = "calm",
  sceneUrl,
  pickedHandle,
  isLatestNarrator,
  hasFollowingPlayerEcho,
  isBookmarked,
  onToggleBookmark,
}: {
  message: NarrativeStoryMessage
  previousPlayerMessage?: NarrativeStoryMessage
  castNameById?: Record<string, string>
  intensity?: "calm" | "rising" | "peak"
  sceneUrl?: string
  /** When this player message was an option pick, the option's
   *  short memory handle. Used to render a leading chip so users
   *  remember "I picked X" rather than re-parsing the full sentence. */
  pickedHandle?: string
  isLatestNarrator?: boolean
  hasFollowingPlayerEcho?: boolean
  /** True if the user has bookmarked this narrator beat. */
  isBookmarked?: boolean
  /** Click handler for the bookmark icon. Undefined hides the icon
   *  (e.g. for player messages or after the run is complete). */
  onToggleBookmark?: () => void
}) {
  const t = useT()
  if (message.role === "narrator") {
    const pulses = message.npc_pulse ?? []
    const impactPulses = pulses.filter((p) => p.shift !== "steady")
    const delta = message.inventory_delta
    const hasDelta = !!(delta && (delta.added.length > 0 || delta.removed.length > 0))
    const outcomeItems = buildOutcomeReceiptItems({
      pulses,
      impactPulses,
      delta,
      castNameById,
      t,
    })
    const intentRead = buildIntentReadReceipt({
      playerMessage: previousPlayerMessage,
      impactPulses,
      castNameById,
      t,
    })
    const playedLeverage = previousPlayerMessage?.played_leverage ?? null
    const hasBroken = impactPulses.some((p) => p.shift === "broken")
    const shouldOpenImpactEvidence = impactPulses.some((p) => p.shift === "broken")
    const showDetailedOutcome =
      outcomeItems.length > 0 && (isLatestNarrator || hasBroken || intensity === "peak")
    const showDetailedImpactEvidence =
      impactPulses.length > 0 && (shouldOpenImpactEvidence || (isLatestNarrator && intensity === "peak"))
    const inlineImpactPulses = [...impactPulses]
      .sort((a, b) => outcomePriority(b.shift) - outcomePriority(a.shift))
      .slice(0, 3)
    const hasTensionShift = impactPulses.some(
      (p) => p.shift === "colder" || p.shift === "wary",
    )
    const beatSignal =
      intensity === "peak"
        ? {
            title: t("play.beat_signal_peak_title"),
            detail: hasBroken
              ? t("play.beat_signal_broken_detail")
              : hasDelta
                ? t("play.beat_signal_delta_detail")
                : hasTensionShift
                  ? t("play.beat_signal_tension_detail")
                  : t("play.beat_signal_peak_detail"),
            style: ppStyles.beatSignalPeak,
          }
        : intensity === "rising" && outcomeItems.length === 0
            ? {
                title: t("play.beat_signal_rising_title"),
                detail: t("play.beat_signal_rising_detail"),
                style: ppStyles.beatSignalRising,
              }
            : null
    // Visual tier: calm = default; rising = +size + decor line; peak =
    // larger type + bold left rail + scene banner overlay.
    const beatStyle =
      intensity === "peak"
        ? { ...ppStyles.narratorBeat, ...ppStyles.narratorBeatPeak }
        : intensity === "rising"
          ? { ...ppStyles.narratorBeat, ...ppStyles.narratorBeatRising }
          : ppStyles.narratorBeat
    const textStyle =
      intensity === "peak"
        ? { ...ppStyles.narratorText, ...ppStyles.narratorTextPeak }
        : intensity === "rising"
          ? { ...ppStyles.narratorText, ...ppStyles.narratorTextRising }
          : ppStyles.narratorText
    return (
      <motion.article
        layout
        initial="initial"
        animate="animate"
        variants={itemVariants}
        transition={itemTransition}
        style={{
          ...beatStyle,
          position: "relative",
          ...(isBookmarked ? ppStyles.narratorBeatBookmarked : null),
        }}
      >
        {/* Bookmark toggle — top-right of every narrator beat while
            the run is active. Lets the user mark "this is the
            moment I want to remember" so it shows up in the ending
            highlights with their own badge, alongside (or instead
            of) the LLM picks. */}
        {onToggleBookmark ? (
          <button
            type="button"
            onClick={onToggleBookmark}
            aria-label={isBookmarked ? t("play.bookmark_remove_title") : t("play.bookmark_add_title")}
            aria-pressed={!!isBookmarked}
            style={{
              ...ppStyles.beatBookmarkBtn,
              ...(isBookmarked ? ppStyles.beatBookmarkBtnActive : null),
            }}
            title={isBookmarked ? t("play.bookmark_remove_title") : t("play.bookmark_add_title")}
          >
            {isBookmarked ? "★" : "☆"}
          </button>
        ) : null}
        {intensity === "peak" && sceneUrl ? (
          <motion.div
            initial={{ opacity: 0, scale: 1.05 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={transitions.slow}
            style={{
              ...ppStyles.beatSceneBanner,
              backgroundImage: `linear-gradient(180deg, rgba(20,16,12,0.15) 0%, rgba(20,16,12,0.85) 90%, var(--bg) 100%), url(${sceneUrl})`,
            }}
            aria-hidden
          />
        ) : null}
        {intensity === "rising" || intensity === "peak" ? (
          <div
            style={
              intensity === "peak" ? ppStyles.beatDecorPeak : ppStyles.beatDecorRising
            }
            aria-hidden
          />
        ) : null}
        {beatSignal ? (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08, ...itemTransition }}
            style={{ ...ppStyles.beatSignal, ...beatSignal.style }}
          >
            <span style={ppStyles.beatSignalMark} aria-hidden />
            <span style={ppStyles.beatSignalCopy}>
              <strong style={ppStyles.beatSignalTitle}>{beatSignal.title}</strong>
              <span style={ppStyles.beatSignalDetail}>{beatSignal.detail}</span>
            </span>
          </motion.div>
        ) : null}
        <div style={textStyle}>{message.content}</div>
        {playedLeverage ? (
          <LeveragePayoff
            played={playedLeverage}
            impactPulses={impactPulses}
            castNameById={castNameById}
          />
        ) : null}
        {outcomeItems.length > 0 ? (
          <OutcomeReceipt
            items={outcomeItems}
            compact={!showDetailedOutcome || showDetailedImpactEvidence}
          />
        ) : null}
        {intentRead ? <IntentReadReceipt read={intentRead} /> : null}
        {message.chosen_option_index != null && message.options.length > 0 && !hasFollowingPlayerEcho ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.12, ...itemTransition }}
            style={ppStyles.chosenChip}
          >
            <span style={ppStyles.chosenLabel}>{t("play.beat_chosen_label")}</span>
            <span style={ppStyles.chosenText}>
              {message.options[message.chosen_option_index]?.label ?? "?"}
            </span>
          </motion.div>
        ) : null}
        {showDetailedImpactEvidence ? (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.18, ...itemTransition }}
            style={ppStyles.pulseImpactPanel}
            aria-label={t("play.impact_feed_label")}
          >
            <div style={ppStyles.pulseImpactSummary}>
              <span style={ppStyles.pulseImpactSummaryCopy}>
                <span style={ppStyles.pulseImpactTitle}>{t("play.impact_inline_label")}</span>
                <span style={ppStyles.pulseImpactCount}>
                  {t("play.impact_count", { count: impactPulses.length })}
                </span>
              </span>
            </div>
            <div style={ppStyles.pulseImpactGrid}>
              {impactPulses.map((p, idx) => {
                const name = (castNameById && castNameById[p.npc_id]) || p.npc_id
                const shiftStyle =
                  ppStyles[
                    ("pulseShift_" + p.shift) as keyof typeof ppStyles
                  ] as CSSProperties | undefined
                return (
                  <motion.div
                    key={`${p.npc_id}-impact-${idx}`}
                    style={{ ...ppStyles.pulseImpactCard, ...(shiftStyle ?? {}) }}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{
                      opacity: 1,
                      y: 0,
                    }}
                    transition={{
                      delay: 0.22 + idx * 0.06,
                      ...itemTransition,
                    }}
                  >
                    <span style={ppStyles.pulseImpactMark}>
                      <span style={ppStyles.pulseImpactArrow}>{shiftArrow(p.shift)}</span>
                      <motion.span
                        style={ppStyles.pulseImpactDelta}
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.28 + idx * 0.06, ...itemTransition }}
                      >
                        {pulseDeltaLabel(p.shift, t)}
                      </motion.span>
                    </span>
                    <span style={ppStyles.pulseImpactBody}>
                      <strong style={ppStyles.pulseImpactName}>{name}</strong>
                      <span style={ppStyles.pulseImpactShift}>{pulseImpactLabel(p.shift, t)}</span>
                      {p.reason ? (
                        <span style={ppStyles.pulseImpactReason}>{p.reason}</span>
                      ) : null}
                    </span>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>
        ) : impactPulses.length > 0 && outcomeItems.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16, ...itemTransition }}
            style={ppStyles.pulseImpactInline}
          >
            <span style={ppStyles.pulseImpactInlineLabel}>{t("play.impact_inline_label")}</span>
            <span style={ppStyles.pulseImpactInlineItems}>
              {inlineImpactPulses.map((p) => {
                const name = (castNameById && castNameById[p.npc_id]) || p.npc_id
                return (
                  <span key={`${p.npc_id}-impact-inline-${p.shift}`} style={ppStyles.pulseImpactInlineItem}>
                    <span style={ppStyles.pulseImpactInlineName}>{name}</span>
                    <strong style={ppStyles.pulseImpactInlineDelta}>{pulseDeltaLabel(p.shift, t)}</strong>
                  </span>
                )
              })}
            </span>
          </motion.div>
        ) : null}
      </motion.article>
    )
  }
  // player move (echoed action)
  const played = message.played_leverage
  const playedTarget = played ? (castNameById?.[played.npc_id] ?? played.npc_id) : ""
  const parsedPlayerMove = parseOptionLabel(message.content)
  const playerMoveBody = parsedPlayerMove.body || message.content
  const playerMoveHandle = pickedHandle ?? parsedPlayerMove.tag
  return (
    <motion.article
      layout
      initial="initial"
      animate="animate"
      variants={itemVariants}
      transition={itemTransition}
      style={{
        ...ppStyles.playerBeat,
        ...(played ? ppStyles.playerBeatLeverageMove : null),
      }}
    >
      <div style={ppStyles.playerLabel}>
        {t("play.beat_player_label")}
        {playerMoveHandle ? (
          <>
            <span style={ppStyles.playerLabelSeparator}>{" · "}</span>
            <span style={ppStyles.playerHandleText} title={message.content}>
              {playerMoveHandle}
            </span>
          </>
        ) : null}
      </div>
      <div style={ppStyles.playerText}>{playerMoveBody}</div>
      {played || message.diary ? (
        <div style={ppStyles.playerMetaLine}>
          {played ? (
            <span style={ppStyles.playerMetaItem}>
              <span style={ppStyles.playerLeverageTag}>
                {t("play.beat_leverage_tag", { target: playedTarget })}
              </span>
              <span style={ppStyles.playerLeverageText}>{played.leverage}</span>
            </span>
          ) : null}
          {message.diary ? (
            <span style={ppStyles.playerMetaItem}>
              <span style={ppStyles.playerDiaryTag}>{t("play.beat_diary_tag")}</span>
              <span style={ppStyles.playerDiaryText}>{message.diary}</span>
            </span>
          ) : null}
        </div>
      ) : null}
    </motion.article>
  )
}

function computeLiveInventory(
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

// Mirror of backend _stage_for. Used to drive visual intensity and to
// map a narrator beat back to a segment scene asset.
function stageForLocal(turnIndex: number, turnBudget: number): string {
  if (turnIndex <= 1) return "hook"
  const midpoint = turnBudget / 2
  if (turnIndex < midpoint - 0.5) return "pressure"
  if (turnIndex < midpoint + 0.5) return "reversal"
  if (turnIndex < turnBudget - 1) return "climax"
  if (turnIndex < turnBudget) return "pre_finale"
  return "pre_finale_open"
}

// Visual intensity heuristic — purely client-side from data we already
// have. Peak: any pulse broken, OR inventory delta fired, OR (climax/
// pre_finale stage AND any colder/wary). Rising: reversal/climax stages
// without peak signal. Calm: hook + early pressure.
function computeBeatIntensity(
  message: NarrativeStoryMessage,
  turnBudget: number,
): "calm" | "rising" | "peak" {
  if (message.role !== "narrator") return "calm"
  const turnIndex = Math.floor(message.ord / 2)
  // Opening (ord=0) is always calm — sets the scene, no visual punch yet.
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

// Parse an option label that may start with an intent tag like "[挑拨] xxx".
// Returns { tag: "挑拨", body: "xxx" } or { tag: null, body: full label }.
// Used so the UI can render the tag as a colored chip + the action body
// as plain text, giving players a visual scan-tag for what the choice
// means before reading the full action.
function parseOptionLabel(label: string): { tag: string | null; body: string } {
  const m = label.match(/^\s*[\[【]([^\]】]{1,8})[\]】]\s*(.*)$/)
  if (m) {
    return { tag: m[1].trim(), body: (m[2] ?? "").trim() }
  }
  return { tag: null, body: label }
}

// Color palette for the 8 known tags. Active/aggressive tags use warm
// gold or red; passive/defensive use neutral or purple. Unknown tags
// fall back to neutral.
function optionTagStyle(tag: string): CSSProperties {
  const ACTIVE_HOT = {
    color: "rgba(245,180,170,0.96)",
  }
  const ACTIVE_GOLD = {
    color: "rgba(245,210,140,0.96)",
  }
  const ACTIVE_PURPLE = {
    color: "rgba(200,170,235,0.96)",
  }
  const ACTIVE_TEAL = {
    color: "rgba(170,225,235,0.94)",
  }
  const PASSIVE = {
    color: "var(--text-muted)",
  }
  // Chinese tag set (legacy) and English mirror (used when template
  // language=en). Unknown tags fall through to PASSIVE — the directive
  // in engine.py keeps both sets stable, so this list rarely needs
  // updating.
  if (tag === "Leverage" || tag === "反将牌") return ACTIVE_GOLD
  if (tag === "挑拨" || tag === "硬刚" || tag === "Provoke" || tag === "Confront") return ACTIVE_HOT
  if (tag === "反将" || tag === "合作" || tag === "Counter" || tag === "Ally") return ACTIVE_TEAL
  if (tag === "试探" || tag === "Probe") return ACTIVE_PURPLE
  // 妥协 / 观望 / 示弱 / Yield / Watch / Submit / unknown → PASSIVE
  return PASSIVE
}

function shiftArrow(shift: NarrativeNPCPulse["shift"]): string {
  switch (shift) {
    case "warmer": return "↗"
    case "colder": return "↘"
    case "wary":   return "⚠"
    case "broken": return "✕"
    case "steady":
    default:       return "—"
  }
}

function pulseImpactLabel(
  shift: NarrativeNPCPulse["shift"],
  t: ReturnType<typeof useT>,
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

function pulseNextMoveLabel(
  shift: NarrativeNPCPulse["shift"],
  t: ReturnType<typeof useT>,
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

function outcomeToneForShift(shift: NarrativeNPCPulse["shift"]): OutcomeReceiptTone {
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

function inventoryOutcomeValue({
  delta,
  t,
}: {
  delta: NonNullable<NarrativeStoryMessage["inventory_delta"]>
  t: ReturnType<typeof useT>
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

type IntentReadReceiptView = {
  publicMove: string
  privateIntent: string
  reaction: string
}

function truncateIntentSnippet(value: string, max = 118): string {
  const clean = value.replace(/\s+/g, " ").trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 3).trim()}...`
}

function buildIntentReadReceipt({
  playerMessage,
  impactPulses,
  castNameById,
  t,
}: {
  playerMessage?: NarrativeStoryMessage
  impactPulses: NarrativeNPCPulse[]
  castNameById?: Record<string, string>
  t: ReturnType<typeof useT>
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

function buildOutcomeReceiptItems({
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
  t: ReturnType<typeof useT>
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

function IntentReadReceipt({ read }: { read: IntentReadReceiptView }) {
  const t = useT()
  const lanes = [read.publicMove, read.privateIntent, read.reaction].filter(Boolean)
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.14, ...itemTransition }}
      style={ppStyles.intentReadReceipt}
      aria-label={t("play.intent_read_label")}
    >
      <span style={ppStyles.intentReadKicker}>{t("play.intent_read_label")}</span>
      <span style={ppStyles.intentReadSentence}>
        {lanes.map((lane, index) => (
          <span key={`${index}:${lane}`} style={ppStyles.intentReadPhrase}>
            {index > 0 ? <span style={ppStyles.intentReadDivider} aria-hidden>·</span> : null}
            <strong style={ppStyles.intentReadLaneValue}>{lane}</strong>
          </span>
        ))}
      </span>
    </motion.div>
  )
}

function outcomeReceiptToneStyle(tone?: OutcomeReceiptTone): CSSProperties | null {
  switch (tone) {
    case "safe":
      return ppStyles.outcomeReceiptChipSafe
    case "tense":
      return ppStyles.outcomeReceiptChipTense
    case "danger":
      return ppStyles.outcomeReceiptChipDanger
    case "gold":
      return ppStyles.outcomeReceiptChipGold
    case "neutral":
    default:
      return null
  }
}

function OutcomeReceipt({ items, compact = false }: { items: OutcomeReceiptItem[]; compact?: boolean }) {
  const t = useT()
  if (items.length === 0) return null
  const content = (
    <>
      <span style={compact ? ppStyles.outcomeReceiptInlineLabel : ppStyles.outcomeReceiptKicker}>
        {compact ? t("play.outcome_inline_label") : t("play.outcome_kicker")}
      </span>
      <span
        style={{
          ...ppStyles.outcomeReceiptSentence,
          ...(compact ? ppStyles.outcomeReceiptSentenceCompact : null),
        }}
      >
        {items.map((item, index) => (
          <span
            key={`${item.label}:${item.value}`}
            style={ppStyles.outcomeReceiptPhrase}
            title={`${item.label}: ${item.value}`}
          >
            <span style={ppStyles.outcomeReceiptItemLabel}>{item.label}</span>
            <strong
              style={{
                ...ppStyles.outcomeReceiptValue,
                ...(outcomeReceiptToneStyle(item.tone) ?? {}),
              }}
            >
              {item.value}
            </strong>
          </span>
        ))}
      </span>
    </>
  )
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.1, ...itemTransition }}
      style={compact ? ppStyles.outcomeReceiptInline : ppStyles.outcomeReceipt}
      aria-label={compact ? t("play.outcome_inline_label") : t("play.outcome_label")}
    >
      {content}
    </motion.div>
  )
}

function LeveragePayoff({
  played,
  impactPulses,
  castNameById,
}: {
  played: NarrativePlayedLeverageCard
  impactPulses: NarrativeNPCPulse[]
  castNameById?: Record<string, string>
}) {
  const t = useT()
  const target = castNameById?.[played.npc_id] ?? played.npc_id
  const targetPulse =
    impactPulses.find((pulse) => pulse.npc_id === played.npc_id) ??
    [...impactPulses].sort((a, b) => outcomePriority(b.shift) - outcomePriority(a.shift))[0] ??
    null
  const payoffTone =
    targetPulse
      ? (ppStyles[
          ("leveragePayoff_" + targetPulse.shift) as keyof typeof ppStyles
        ] as CSSProperties | undefined)
      : undefined
  const readout = targetPulse
    ? pulseImpactLabel(targetPulse.shift, t)
    : t("play.leverage_payoff_room_reacts")
  const reason = targetPulse?.reason || t("play.leverage_payoff_reason_default")
  const next = targetPulse
    ? pulseNextMoveLabel(targetPulse.shift, t)
    : t("play.leverage_payoff_next_default")

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.08, ...transitions.snap }}
      style={{ ...ppStyles.leveragePayoff, ...(payoffTone ?? {}) }}
      aria-label={t("play.leverage_payoff_label")}
    >
      <span style={ppStyles.leveragePayoffKicker}>{t("play.leverage_payoff_kicker")}</span>
      <span style={ppStyles.leveragePayoffSentence}>
        <strong style={ppStyles.leveragePayoffEvidence}>{played.leverage}</strong>
        <span style={ppStyles.leveragePayoffMetaDivider} aria-hidden>·</span>
        <strong style={ppStyles.leveragePayoffMetaValue}>{target}</strong>
        <span style={ppStyles.leveragePayoffMetaDivider} aria-hidden>·</span>
        <span style={ppStyles.leveragePayoffMetaValue}>{readout}</span>
        <span style={ppStyles.leveragePayoffMetaDivider} aria-hidden>·</span>
        <span style={ppStyles.leveragePayoffMetaValue}>{next}</span>
      </span>
      <span style={ppStyles.leveragePayoffReasonText}>{reason}</span>
    </motion.div>
  )
}

function useCompactLayout(query = "(max-width: 680px)") {
  const [compact, setCompact] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    const media = window.matchMedia(query)
    const update = () => setCompact(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [query])
  return compact
}

function displayEndingLabel(label: string, lang: ReturnType<typeof useLanguage>["lang"]): string {
  const translated = ENDING_LABEL_DISPLAY[lang]?.[label]
  if (translated) return translated
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase())
}

type OutcomeReceiptTone = "safe" | "neutral" | "tense" | "danger" | "gold"

type OutcomeReceiptItem = {
  label: string
  value: string
  tone?: OutcomeReceiptTone
}

type SceneClockView = {
  label: string
  value: string
}

function buildSceneClocks({
  turnsCompleted,
  turnsRemaining,
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

function SceneReadStrip({
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
    <div style={ppStyles.sceneReadStrip} aria-label={t("play.scene_read_label")}>
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

function ResolvingTurnPanel({
  moveTag,
  moveText,
  privateIntent,
  target,
}: {
  moveTag?: string
  moveText: string
  privateIntent?: string
  target?: string
}) {
  const t = useT()
  const privateIntentCopy = privateIntent?.trim()
  const moveMeta = moveTag?.trim()
  const resolveStatus = target
    ? t("play.resolve_status_target", { target })
    : t("play.resolve_status_room")
  const moveCopy = moveText || t("play.resolve_custom_move")
  const resolvingAriaLabel = [t("play.resolve_title"), moveMeta, moveCopy, resolveStatus, t("play.resolve_progress")]
    .filter(Boolean)
    .join(". ")
  return (
    <motion.div
      key="turn-resolving"
      style={ppStyles.resolvingPanel}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={transitions.snap}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label={resolvingAriaLabel}
    >
      <div style={ppStyles.resolvingLine}>
        <span style={ppStyles.resolvingTitle}>{t("play.resolve_title")}</span>
        {moveMeta ? <span style={ppStyles.resolvingReceiptMeta}>{moveMeta}</span> : null}
        <strong style={ppStyles.resolvingMoveText} title={moveCopy}>
          {moveCopy}
        </strong>
        <span style={ppStyles.resolvingInlineStatus}>
          <span style={ppStyles.resolvingStatus}>{resolveStatus}</span>
          <span style={ppStyles.resolvingProgressText}>{t("play.resolve_progress")}</span>
          <span style={ppStyles.resolvingDots} aria-hidden>
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                style={ppStyles.resolvingDot}
                animate={{ opacity: [0.24, 1, 0.24] }}
                transition={{
                  duration: 1.1,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: i * 0.14,
                }}
              />
            ))}
          </span>
        </span>
      </div>
      {privateIntentCopy ? (
        <span style={ppStyles.resolvingPrivateLine}>
          <span style={ppStyles.resolvingPrivateLabel}>{t("play.move_packet_private_label")}</span>
          <span style={ppStyles.resolvingPrivateCopy} title={privateIntentCopy}>{privateIntentCopy}</span>
        </span>
      ) : null}
    </motion.div>
  )
}

function findActionTarget(
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

// ---------------------------------------------------------------------------
// Action area — options + free input
// ---------------------------------------------------------------------------

function ActionArea({
  options,
  leverageCards,
  latestNpcPulses,
  castNameById,
  turnsCompleted,
  turnsRemaining,
  turnBudget,
  showFreeInput,
  freeInput,
  setFreeInput,
  setShowFreeInput,
  diary,
  setDiary,
  showDiary,
  setShowDiary,
  busy,
  onCommitmentActiveChange,
  onCommitmentSummaryChange,
  onOpenAdvisor,
  onPickOption,
  onPlayLeverage,
  onSubmitFree,
}: {
  options: NarrativeStoryMessage["options"]
  leverageCards: LeverageCardView[]
  latestNpcPulses: NarrativeNPCPulse[]
  castNameById: Record<string, string>
  turnsCompleted: number
  turnsRemaining: number
  turnBudget: number
  showFreeInput: boolean
  freeInput: string
  setFreeInput: (v: string) => void
  setShowFreeInput: (v: boolean) => void
  diary: string
  setDiary: (v: string) => void
  showDiary: boolean
  setShowDiary: (v: boolean) => void
  busy: boolean
  onCommitmentActiveChange: (active: boolean) => void
  onCommitmentSummaryChange: (summary: ActionCommitmentSummary | null) => void
  onOpenAdvisor: () => void
  onPickOption: (idx: number, diaryOverride?: string) => void
  onPlayLeverage: (card: LeverageCardView, diaryOverride?: string) => void
  onSubmitFree: (diaryOverride?: string) => void
}) {
  const t = useT()
  // Local "I picked option N this turn" so we can immediately reflect
  // the choice — instead of just dimming everything to 50% opacity
  // and waiting 5-8s for the LLM. State resets every turn because
  // the parent gives us key={beat.ord}, remounting ActionArea.
  const [pickedIndex, setPickedIndex] = useState<number | null>(null)
  const [selectedOptionIndex, setSelectedOptionIndex] = useState<number | null>(null)
  const [submittedFree, setSubmittedFree] = useState(false)
  const [submittedLeverageLabel, setSubmittedLeverageLabel] = useState<string | null>(null)
  const [submittedLeverageTarget, setSubmittedLeverageTarget] = useState<string | null>(null)
  const [leverageExpanded, setLeverageExpanded] = useState(false)
  const [revealingLeverageCardId, setRevealingLeverageCardId] = useState<string | null>(null)
  const leverageRevealTimerRef = useRef<number | null>(null)
  const actionSubmitLockedRef = useRef(false)
  const commitFocusRef = useRef<HTMLElement | null>(null)
  const freeActionRef = useRef<HTMLDivElement | null>(null)
  const freeTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const diaryTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const diaryScopeRef = useRef("idle")
  const setCommitFocusNode = useCallback((node: HTMLElement | null) => {
    commitFocusRef.current = node
  }, [])
  const setFreeActionNode = useCallback((node: HTMLDivElement | null) => {
    freeActionRef.current = node
  }, [])
  const compactLeverage = useCompactLayout()
  const compactActionChrome = useCompactLayout("(max-width: 680px)")
  const playableLeverageCards = useMemo(
    () => leverageCards.filter((card) => !card.used),
    [leverageCards],
  )
  const spentLeverageCards = useMemo(
    () => leverageCards.filter((card) => card.used),
    [leverageCards],
  )
  const [armedCardId, setArmedCardId] = useState<string | null>(null)
  const sceneClocks = buildSceneClocks({
    turnsCompleted,
    turnsRemaining,
    turnBudget,
    latestNpcPulses,
    leverageCards,
    t,
  })
  const armedCard = playableLeverageCards.find((card) => card.card_id === armedCardId) ?? null
  const armedCardTargetName = armedCard?.target_name ?? ""
  const armedCardLeverage = armedCard?.leverage ?? ""
  const isRevealingLeverage = revealingLeverageCardId !== null
  const showLeverageCards = leverageExpanded || !!armedCard
  const hasSinglePlayableLeverage = playableLeverageCards.length === 1
  const primaryLeverageCard = armedCard ?? playableLeverageCards[0] ?? null
  const playableLeverageTargetText = (() => {
    const names = playableLeverageCards.map((card) => card.target_name)
    const visibleNames = names.slice(0, 2).join(" · ")
    const remaining = Math.max(0, names.length - 2)
    return remaining > 0 ? `${visibleNames} · +${remaining}` : visibleNames
  })()
  const leverageSummaryText = armedCard
    ? t("play.leverage_summary_prepared", { target: armedCard.target_name })
    : hasSinglePlayableLeverage && primaryLeverageCard
      ? primaryLeverageCard.target_name
      : playableLeverageTargetText || t("play.leverage_summary_count", { count: playableLeverageCards.length })
  const leverageSummaryMetaText = armedCard
    ? t("play.leverage_summary_meta_target", { target: armedCard.target_name })
    : hasSinglePlayableLeverage && primaryLeverageCard
      ? primaryLeverageCard.leverage
      : `${t("play.leverage_summary_count", { count: playableLeverageCards.length })} · ${t("play.leverage_rail_hint")}`
  const leverageSummaryToggleText = leverageExpanded
    ? t("play.leverage_collapse")
    : armedCard
      ? t("play.leverage_change")
      : hasSinglePlayableLeverage
        ? t("play.leverage_summary_prepare")
        : t("play.leverage_expand")
  const spentLeverageTargets = spentLeverageCards.map((card) => card.target_name).join(" · ")
  const leverageEmptyMetaText = spentLeverageTargets
    ? t("play.leverage_empty_meta", { targets: spentLeverageTargets })
    : t("play.leverage_summary_meta_empty")
  const commitmentSurfaceOpen =
    selectedOptionIndex !== null ||
    armedCardId !== null ||
    showFreeInput ||
    options.length === 0
  const handleLeverageSummaryActivate = () => {
    if (!primaryLeverageCard || busy || actionSubmitLockedRef.current || isRevealingLeverage) return
    if (hasSinglePlayableLeverage) {
      setSelectedOptionIndex(null)
      setShowFreeInput(false)
      setLeverageExpanded(false)
      setArmedCardId(primaryLeverageCard.card_id)
      return
    }
    setLeverageExpanded((value) => !value)
  }
  const handleOptionSelect = (i: number) => {
    if (busy || actionSubmitLockedRef.current || isRevealingLeverage) return
    setArmedCardId(null)
    setShowFreeInput(false)
    setSelectedOptionIndex(i)
  }

  const handleOptionCommit = (i: number, diaryOverride?: string) => {
    if (busy || actionSubmitLockedRef.current || isRevealingLeverage) return
    actionSubmitLockedRef.current = true
    setPickedIndex(i)
    setSelectedOptionIndex(i)
    onPickOption(i, diaryOverride)
  }

  const handleSubmitFreeWithReflect = (diaryOverride?: string) => {
    if (!freeInput.trim() || busy || actionSubmitLockedRef.current) return
    actionSubmitLockedRef.current = true
    setSelectedOptionIndex(null)
    setArmedCardId(null)
    setSubmittedFree(true)
    onSubmitFree(diaryOverride)
  }

  const handleLeverageReveal = (card: LeverageCardView, diaryOverride?: string) => {
    if (busy || actionSubmitLockedRef.current || card.used || isRevealingLeverage) return
    actionSubmitLockedRef.current = true
    setSubmittedFree(true)
    setSubmittedLeverageLabel(t("play.leverage_submit_echo", { target: card.target_name }))
    setSubmittedLeverageTarget(card.target_name)
    setRevealingLeverageCardId(card.card_id)
    leverageRevealTimerRef.current = window.setTimeout(() => {
      onPlayLeverage(card, diaryOverride)
      leverageRevealTimerRef.current = null
    }, 360)
  }

  useEffect(() => () => {
    if (leverageRevealTimerRef.current !== null) {
      window.clearTimeout(leverageRevealTimerRef.current)
    }
    onCommitmentActiveChange(false)
    onCommitmentSummaryChange(null)
  }, [onCommitmentActiveChange, onCommitmentSummaryChange])

  useEffect(() => {
    onCommitmentActiveChange(commitmentSurfaceOpen)
  }, [commitmentSurfaceOpen, onCommitmentActiveChange])

  useEffect(() => {
    if (busy) return
    setShowDiary(false)
  }, [armedCardId, busy, options.length, selectedOptionIndex, setShowDiary, showFreeInput])

  useEffect(() => {
    if (busy) return
    if (!commitmentSurfaceOpen) return
    const frame = window.requestAnimationFrame(() => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      commitFocusRef.current?.scrollIntoView({
        block: "center",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [busy, commitmentSurfaceOpen])

  useEffect(() => {
    if (armedCardId && !playableLeverageCards.some((card) => card.card_id === armedCardId)) {
      setArmedCardId(null)
    }
  }, [armedCardId, playableLeverageCards])

  // Once the parent flips busy=false (turn settled, narrator beat
  // arrived), the parent will remount us via key change anyway. But
  // if the request fails and busy goes false without remount, clear
  // the picked state so the user can retry.
  useEffect(() => {
    if (!busy) {
      actionSubmitLockedRef.current = false
      setPickedIndex(null)
      setSelectedOptionIndex(null)
      setSubmittedFree(false)
      setSubmittedLeverageLabel(null)
      setSubmittedLeverageTarget(null)
      setRevealingLeverageCardId(null)
    }
  }, [busy])

  // Keyboard shortcuts:
  //   1 / 2 / 3 ... pick the corresponding option (when not focused
  //   in a text input / textarea — otherwise the digit just types).
  // The hint chips on each option button reflect this.
  useEffect(() => {
    if (busy) return
    const handler = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement | null
      if (!tgt) return
      const inEditable =
        tgt.tagName === "TEXTAREA" ||
        tgt.tagName === "INPUT" ||
        tgt.isContentEditable
      if (inEditable) return
      if (actionSubmitLockedRef.current) {
        if (e.key === "Enter" || e.key === "Escape") {
          e.preventDefault()
        }
        return
      }
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return
      if (e.key >= "1" && e.key <= "9") {
        const idx = parseInt(e.key, 10) - 1
        if (idx >= 0 && idx < options.length) {
          e.preventDefault()
          if (selectedOptionIndex === idx) {
            handleOptionCommit(idx)
          } else {
            handleOptionSelect(idx)
          }
        }
      }
      if (
        e.key.toLowerCase() === "t" &&
        playableLeverageCards.length > 0 &&
        !armedCard &&
        selectedOptionIndex === null &&
        !showFreeInput
      ) {
        e.preventDefault()
        handleLeverageSummaryActivate()
      }
      if (e.key === "Enter" && selectedOptionIndex !== null) {
        e.preventDefault()
        handleOptionCommit(selectedOptionIndex)
      } else if (e.key === "Enter" && armedCard) {
        e.preventDefault()
        handleLeverageReveal(armedCard)
      } else if (e.key === "Escape") {
        e.preventDefault()
        setSelectedOptionIndex(null)
        setArmedCardId(null)
        if (showFreeInput && options.length > 0) {
          setShowFreeInput(false)
          if (!freeInput.trim()) {
            setFreeInput("")
          }
        }
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy, options.length, selectedOptionIndex, armedCardId, isRevealingLeverage, showFreeInput, freeInput])

  const actionSubmissionInFlight = pickedIndex !== null || submittedFree || isRevealingLeverage
  const actionControlsDisabled = busy || actionSubmissionInFlight
  const inlineActionDisabledStyle = actionControlsDisabled ? ppStyles.inlineActionDisabled : null
  const showPickedReflection = actionSubmissionInFlight
  const pickedOption = pickedIndex !== null ? options[pickedIndex] : null
  const pickedOptionParsed = pickedOption ? parseOptionLabel(pickedOption.label) : null
  const selectedOption = selectedOptionIndex !== null ? options[selectedOptionIndex] : null
  const selectedOptionParsed = selectedOption ? parseOptionLabel(selectedOption.label) : null
  const focusedOptionIndex = selectedOptionIndex ?? pickedIndex
  const visibleOptionEntries = options
    .map((opt, i) => ({ opt, i }))
    .filter(({ i }) => focusedOptionIndex === null || i === focusedOptionIndex)
  const freeActionDraft = freeInput.trim()
  const freeActionReady = freeActionDraft.length > 0
  const freeActionTarget = freeActionDraft
    ? findActionTarget(freeActionDraft, undefined, castNameById, latestNpcPulses)
    : null
  const freeActionTargetName = freeActionTarget?.name ?? ""
  const freeComposerOpen = showFreeInput || options.length === 0
  const selectedOptionGuideTitle = selectedOptionParsed?.tag
    ? t("play.turn_guide_selected_named_title", { tag: selectedOptionParsed.tag })
    : t("play.turn_guide_selected_title")
  const selectedOptionGuideDetail = selectedOptionParsed?.body
    ? t("play.turn_guide_selected_named_detail", {
        action: truncateRecoveryText(selectedOptionParsed.body, 72),
      })
    : t("play.turn_guide_selected_detail")

  useEffect(() => {
    if (busy || !freeComposerOpen || !freeActionReady) return
    const frame = window.requestAnimationFrame(() => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      freeActionRef.current?.scrollIntoView({
        block: "center",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [busy, freeActionReady, freeComposerOpen])

  useEffect(() => {
    if (busy || !freeComposerOpen) return
    const focusFreeTextarea = () => {
      const node = freeTextareaRef.current
      if (!node || node.disabled) return
      node.focus({ preventScroll: true })
      const cursor = node.value.length
      node.setSelectionRange(cursor, cursor)
    }
    const frame = window.requestAnimationFrame(() => {
      focusFreeTextarea()
    })
    const timers = [90, 240, 420].map((delay) => window.setTimeout(focusFreeTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, freeComposerOpen])

  const isFinalTurn = turnsRemaining <= 1
  const isEndgameTurn = turnsRemaining <= 2
  const turnGuide =
    armedCard
      ? {
          title: t("play.turn_guide_leverage_title", { target: armedCard.target_name }),
          detail: t("play.turn_guide_leverage_detail"),
          tone: ppStyles.turnGuideLeverage,
        }
      : selectedOptionParsed
        ? {
            title: selectedOptionGuideTitle,
            detail: selectedOptionGuideDetail,
            tone: ppStyles.turnGuideSelected,
          }
        : showFreeInput && freeActionReady
          ? {
              title: t("play.turn_guide_free_ready_title"),
              detail: t("play.turn_guide_free_ready_detail"),
              tone: ppStyles.turnGuideSelected,
            }
        : showFreeInput
          ? {
              title: t("play.turn_guide_free_title"),
              detail: t("play.turn_guide_free_detail"),
              tone: ppStyles.turnGuideFree,
            }
          : options.length === 0
            ? {
                title: t("play.turn_guide_free_title"),
                detail: t("play.turn_guide_no_options_detail"),
                tone: ppStyles.turnGuideFree,
              }
          : isFinalTurn
            ? {
                title: t("play.turn_guide_final_title"),
                detail: t("play.turn_guide_final_detail"),
                tone: ppStyles.turnGuideFinal,
              }
            : isEndgameTurn
              ? {
                  title: t("play.turn_guide_endgame_title"),
                  detail: t("play.turn_guide_endgame_detail", { count: turnsRemaining }),
                  tone: ppStyles.turnGuideEndgame,
                }
              : {
                  title: t("play.turn_guide_idle_title"),
                  detail: playableLeverageCards.length > 0
                    ? t("play.turn_guide_idle_detail_with_leverage")
                    : t("play.turn_guide_idle_detail"),
                  tone: null,
                }
  const showActionTelemetry = !commitmentSurfaceOpen && !showPickedReflection && options.length === 0
  const showLeverageCardPicker =
    showLeverageCards && playableLeverageCards.length > 0 && !armedCard && !hasSinglePlayableLeverage
  const showFreeActionSurface = !armedCard && selectedOptionIndex === null && !showPickedReflection
  const showFreeComposer = showFreeActionSurface && freeComposerOpen
  const showStandardOptions = !armedCard && !showFreeComposer
  const showLeverageRail = leverageCards.length > 0 && !commitmentSurfaceOpen
  const showFreeActionToggle =
    showFreeActionSurface &&
    !showFreeInput &&
    options.length > 0
  const showIdleAdvisorLine =
    !commitmentSurfaceOpen &&
    !showPickedReflection &&
    !actionControlsDisabled &&
    options.length > 0
  const freeActionToggleText = freeInput.trim()
    ? t("play.action_resume_free")
    : t("play.action_open_free")
  const freeActionToggleHint = freeInput.trim()
    ? t("play.action_resume_free_hint")
    : t("play.action_open_free_hint")
  const freeActionToggleTitle = freeInput.trim()
    ? t("play.action_resume_free_title")
    : t("play.action_open_free_title")
  const freeTextareaCanClose = options.length > 0
  const freeTextareaKeyShortcuts = freeTextareaCanClose
    ? "Meta+Enter Control+Enter Escape"
    : "Meta+Enter Control+Enter"
  const freeTextareaTitle = freeTextareaCanClose
    ? `${t("play.shortcut_mod_enter_submit")} · ${t("play.shortcut_escape_cancel")}`
    : t("play.shortcut_mod_enter_submit")
  const resolvingMoveTag =
    pickedOptionParsed?.tag ??
    (submittedLeverageLabel ? t("play.leverage_option_tag") : submittedFree ? t("play.preview_approach_custom") : "")
  const resolvingMoveText =
    pickedOptionParsed?.body ??
    submittedLeverageLabel ??
    (submittedFree ? freeActionDraft || t("play.resolve_custom_move") : "")
  const resolvingTarget =
    pickedOption && pickedOptionParsed
      ? findActionTarget(pickedOptionParsed.body, pickedOption.hint, castNameById, latestNpcPulses)?.name
      : submittedLeverageLabel
        ? submittedLeverageTarget ?? undefined
        : freeActionTarget?.name
  const diaryDraft = diary.trim()
  const diaryPreview =
    diaryDraft.length > 130 ? `${diaryDraft.slice(0, 127)}...` : diaryDraft
  const selectedOptionBody = selectedOptionParsed?.body ?? ""
  const selectedOptionHint = selectedOption?.hint ?? ""
  const actionCommitmentSummary = useMemo<ActionCommitmentSummary | null>(() => {
    const motive = diaryDraft || undefined
    if (armedCardId && armedCardTargetName) {
      return {
        kind: "leverage",
        kicker: t("play.advisor_commitment_kind_leverage"),
        title: t("play.leverage_confirm_title", { target: armedCardTargetName }),
        detail: armedCardLeverage,
        motive,
      }
    }
    if (selectedOptionIndex !== null && selectedOptionBody && pickedIndex === null && !busy) {
      return {
        kind: "option",
        kicker: t("play.advisor_commitment_kind_option"),
        title: selectedOptionBody,
        detail: selectedOptionHint || undefined,
        motive,
      }
    }
    if (freeComposerOpen && freeActionDraft) {
      return {
        kind: "free",
        kicker: t("play.advisor_commitment_kind_free"),
        title: freeActionDraft,
        detail: freeActionTargetName
          ? t("play.preview_action_target_value", { target: freeActionTargetName })
          : t("play.preview_action_read_room"),
        motive,
      }
    }
    if (freeComposerOpen) {
      return {
        kind: "free",
        kicker: t("play.advisor_commitment_kind_free"),
        title: t("play.advisor_commitment_free_empty_title"),
        detail: t("play.advisor_commitment_free_empty_detail"),
        motive,
      }
    }
    return null
  }, [
    armedCardId,
    armedCardLeverage,
    armedCardTargetName,
    busy,
    diaryDraft,
    freeActionDraft,
    freeActionTargetName,
    pickedIndex,
    selectedOptionBody,
    selectedOptionHint,
    selectedOptionIndex,
    freeComposerOpen,
    t,
  ])
  useEffect(() => {
    onCommitmentSummaryChange(actionCommitmentSummary)
  }, [actionCommitmentSummary, onCommitmentSummaryChange])
  const diaryContext = armedCard
    ? "leverage"
    : selectedOption && selectedOptionParsed && pickedIndex === null && !busy
      ? "option"
      : freeComposerOpen
        ? "free"
        : "idle"
  const isWritingOptionDiary = showDiary && diaryContext === "option"
  const isWritingLeverageDiary = showDiary && diaryContext === "leverage"
  const isWritingFreeDiary = showDiary && diaryContext === "free"
  const diaryScopeKey = armedCard
    ? `leverage:${armedCard.card_id}`
    : selectedOptionIndex !== null && pickedIndex === null && !busy
      ? `option:${selectedOptionIndex}`
      : freeComposerOpen
        ? "free"
        : "idle"
  const showTurnGuide = !showPickedReflection

  useEffect(() => {
    if (actionSubmissionInFlight) return

    const previousScope = diaryScopeRef.current
    if (diaryScopeKey === "idle") {
      if (previousScope !== "idle") {
        if (diary.trim()) setDiary("")
        if (showDiary) setShowDiary(false)
      }
      diaryScopeRef.current = "idle"
      return
    }

    if (previousScope !== "idle" && previousScope !== diaryScopeKey) {
      if (diary.trim()) setDiary("")
      if (showDiary) setShowDiary(false)
    }
    diaryScopeRef.current = diaryScopeKey
  }, [actionSubmissionInFlight, diary, diaryScopeKey, setDiary, setShowDiary, showDiary])

  useEffect(() => {
    if (!showDiary || diaryContext === "idle" || busy) return
    const focusDiaryTextarea = () => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      const node = diaryTextareaRef.current
      if (!node || node.disabled) return
      node.focus({ preventScroll: true })
      const cursor = node.value.length
      node.setSelectionRange(cursor, cursor)
      node.scrollIntoView({
        block: "center",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      })
    }
    const frame = window.requestAnimationFrame(focusDiaryTextarea)
    const timers = [90, 220].map((delay) => window.setTimeout(focusDiaryTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, diaryContext, showDiary])

  const renderDiaryAttachPreview = (context: "leverage" | "option" | "free") => {
    const isEditingThisContext = showDiary && diaryContext === context
    if (isEditingThisContext) {
      return null
    }
    const diaryAttachTitle = diaryDraft
      ? t("play.diary_attach_edit_title", { motive: diaryDraft })
      : t("play.diary_attach_add_title")

    if (!diaryDraft) {
      return (
        <button
          type="button"
          aria-label={diaryAttachTitle}
          title={diaryAttachTitle}
          style={{
            ...ppStyles.diaryAttachPreview,
            ...ppStyles.diaryAttachPreviewEmpty,
            ...inlineActionDisabledStyle,
          }}
          onClick={() => setShowDiary(true)}
          disabled={actionControlsDisabled}
        >
          <span style={ppStyles.diaryAttachEmptyCopy}>
            <span style={ppStyles.diaryAttachEmptyText}>{t("play.diary_attach_empty")}</span>
            <span style={ppStyles.diaryAttachEmptyHint}>{t("play.diary_attach_empty_hint")}</span>
          </span>
        </button>
      )
    }

    return (
      <button
        type="button"
        aria-label={diaryAttachTitle}
        title={diaryAttachTitle}
        style={{
          ...ppStyles.diaryAttachPreview,
          ...ppStyles.diaryAttachPreviewFilled,
          ...inlineActionDisabledStyle,
        }}
        onClick={() => setShowDiary(true)}
        disabled={actionControlsDisabled}
      >
        <span style={ppStyles.diaryAttachTag}>{t("play.diary_attached_label")}</span>
        <span style={ppStyles.diaryAttachText} title={diaryDraft}>{diaryPreview}</span>
        <span style={ppStyles.diaryAttachEdit}>
          {t("play.diary_lane_edit")}
        </span>
      </button>
    )
  }
  const renderDiaryEditor = (context: "leverage" | "option" | "free") => {
    const diarySubmitDisabled =
      actionControlsDisabled ||
      (context === "option" && selectedOptionIndex === null) ||
      (context === "leverage" && !armedCard) ||
      (context === "free" && !freeInput.trim())

    return showDiary && diaryContext === context ? (
      <div style={ppStyles.diaryBox}>
        <div style={ppStyles.diaryHeader}>
          <span style={ppStyles.diaryKicker}>{t("play.diary_inner_label")}</span>
          <span style={ppStyles.diaryMeta}>{t("play.private_intent_hint")}</span>
        </div>
        <textarea
          className="play-diary-textarea"
          ref={diaryTextareaRef}
          style={ppStyles.diaryTextarea}
          value={diary}
          placeholder={t("play.diary_placeholder")}
          aria-label={t("play.diary_inner_label")}
          aria-keyshortcuts="Meta+Enter Control+Enter Escape"
          title={`${t("play.shortcut_mod_enter_submit")} · ${t("play.shortcut_escape_cancel")}`}
          onChange={(e) => setDiary(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault()
              if (actionControlsDisabled) return
              const currentDiary = e.currentTarget.value
              setDiary(currentDiary)
              if (context === "option" && selectedOptionIndex !== null) {
                handleOptionCommit(selectedOptionIndex, currentDiary)
              } else if (context === "leverage" && armedCard) {
                handleLeverageReveal(armedCard, currentDiary)
              } else if (context === "free" && freeInput.trim()) {
                handleSubmitFreeWithReflect(currentDiary)
              }
            } else if (e.key === "Escape") {
              e.preventDefault()
              setShowDiary(false)
            }
          }}
          disabled={actionControlsDisabled}
          spellCheck={false}
          rows={2}
          maxLength={600}
        />
        <div style={ppStyles.diaryActions}>
          <button
            style={{
              ...ppStyles.actionPrimaryLine,
              ...(compactActionChrome ? ppStyles.actionPrimaryLineCompact : null),
              ...ppStyles.inlineCommitPrimaryActions,
              ...(diarySubmitDisabled ? ppStyles.actionPrimaryLineDisabled : null),
            }}
            onClick={() => {
              const currentDiary = diary.trim()
              if (context === "option" && selectedOptionIndex !== null) {
                handleOptionCommit(selectedOptionIndex, currentDiary)
              } else if (context === "leverage" && armedCard) {
                handleLeverageReveal(armedCard, currentDiary)
              } else if (context === "free" && freeInput.trim()) {
                handleSubmitFreeWithReflect(currentDiary)
              }
            }}
            disabled={diarySubmitDisabled}
            aria-keyshortcuts="Meta+Enter Control+Enter"
            title={t("play.shortcut_mod_enter_submit")}
            type="button"
          >
            {context === "leverage"
              ? t("play.leverage_confirm_cta")
              : t("play.action_submit")}
          </button>
          <button
            onClick={() => setShowDiary(false)}
            disabled={actionControlsDisabled}
            type="button"
            aria-keyshortcuts="Escape"
            title={t("play.shortcut_escape_cancel")}
            style={{
              ...ppStyles.diaryTextButton,
              ...inlineActionDisabledStyle,
            }}
          >
            {t("play.diary_keep")}
          </button>
          {diaryDraft ? (
            <button
              onClick={() => {
                setShowDiary(false)
                setDiary("")
              }}
              disabled={actionControlsDisabled}
              type="button"
              style={{
                ...ppStyles.diaryTextButton,
                ...inlineActionDisabledStyle,
              }}
            >
              {t("play.diary_remove")}
            </button>
          ) : null}
        </div>
      </div>
    ) : null
  }
  const renderSelectedOptionConfirm = () =>
    selectedOption && selectedOptionParsed && selectedOptionIndex !== null && pickedIndex === null && !actionControlsDisabled ? (
      <div
        ref={setCommitFocusNode}
        style={{
          ...ppStyles.optionConfirmPanel,
          ...(isWritingOptionDiary ? ppStyles.optionConfirmPanelWriting : null),
        }}
      >
        {isWritingOptionDiary ? null : (
          <div
            style={{
              ...ppStyles.optionConfirmActions,
              ...(compactActionChrome ? ppStyles.optionConfirmActionsCompact : null),
            }}
          >
            <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
              <button
                style={{
                  ...ppStyles.actionPrimaryLine,
                  ...(compactActionChrome ? ppStyles.actionPrimaryLineCompact : null),
                  ...(actionControlsDisabled ? ppStyles.actionPrimaryLineDisabled : null),
                }}
                type="button"
                aria-keyshortcuts="Enter"
                title={t("play.shortcut_enter_submit")}
                onClick={() => {
                  if (selectedOptionIndex !== null) {
                    handleOptionCommit(selectedOptionIndex)
                  }
                }}
                disabled={actionControlsDisabled}
              >
                {t("play.option_confirm_cta")}
              </button>
              {renderDiaryAttachPreview("option")}
            </div>
            <div
              style={{
                ...ppStyles.commitSecondaryActions,
                ...ppStyles.inlineCommitSecondaryActions,
                ...(compactActionChrome ? ppStyles.commitSecondaryActionsCompact : null),
              }}
            >
              <button
                type="button"
                style={{
                  ...ppStyles.advisorInlineAction,
                  ...inlineActionDisabledStyle,
                }}
                onClick={onOpenAdvisor}
                disabled={actionControlsDisabled}
                aria-haspopup="dialog"
                aria-label={t("play.ask_friend_open_title")}
                title={t("play.ask_friend_open_title")}
              >
                {t("play.ask_friend_inline")}
              </button>
              <button
                type="button"
                style={{
                  ...ppStyles.commitTextButton,
                  ...inlineActionDisabledStyle,
                }}
                onClick={() => setSelectedOptionIndex(null)}
                disabled={actionControlsDisabled}
                aria-keyshortcuts="Escape"
                title={t("play.shortcut_escape_cancel")}
              >
                {t("play.option_change_cta")}
              </button>
            </div>
          </div>
        )}
        {renderDiaryEditor("option")}
      </div>
    ) : null

  return (
    <motion.div
      data-play-action-area="true"
      style={ppStyles.actionArea}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.08, ...itemTransition }}
    >
      {showTurnGuide ? (
        <div
          style={{
            ...ppStyles.turnGuide,
            ...(turnGuide.tone ?? {}),
            ...(compactActionChrome ? ppStyles.turnGuideCompact : null),
          }}
          aria-label={t("play.turn_guide_kicker")}
        >
          <div style={ppStyles.turnGuideCopy}>
            <strong style={ppStyles.turnGuideTitle}>{turnGuide.title}</strong>
            <span style={ppStyles.turnGuideDetail}>{turnGuide.detail}</span>
          </div>
        </div>
      ) : null}

      {showLeverageRail ? (
        <section
          id={ACTION_LEVERAGE_RAIL_ID}
          style={{
            ...ppStyles.leverageRail,
            ...(compactActionChrome ? ppStyles.leverageRailCompact : null),
          }}
          aria-label={t("play.leverage_rail_label")}
        >
          {playableLeverageCards.length === 0 ? (
            <div style={ppStyles.leverageEmptySummary}>
              <span style={ppStyles.leverageSummaryMain}>
                <span style={ppStyles.leverageSummaryEyebrow}>{t("play.leverage_resource_label")}</span>
                <strong style={ppStyles.leverageSummaryText}>{t("play.leverage_empty_title")}</strong>
                <span style={ppStyles.leverageSummaryMeta} title={leverageEmptyMetaText}>
                  {leverageEmptyMetaText}
                </span>
              </span>
              <span style={ppStyles.leverageEmptyBadge}>{t("play.leverage_spent")}</span>
            </div>
          ) : (
            <button
              type="button"
              style={{
                ...ppStyles.leverageSummaryButton,
                ...(showLeverageCards ? ppStyles.leverageSummaryButtonOpen : null),
                ...(compactActionChrome ? ppStyles.leverageSummaryButtonCompact : null),
              }}
              onClick={handleLeverageSummaryActivate}
              disabled={actionControlsDisabled}
              aria-expanded={showLeverageCards}
              aria-keyshortcuts="T"
              title={t("play.leverage_shortcut_title")}
            >
              <span style={ppStyles.leverageSummaryMain}>
                <span style={ppStyles.leverageSummaryEyebrow}>{t("play.leverage_resource_label")}</span>
                <strong style={ppStyles.leverageSummaryText}>{leverageSummaryText}</strong>
                <span style={ppStyles.leverageSummaryMeta} title={leverageSummaryMetaText}>{leverageSummaryMetaText}</span>
              </span>
              <span
                style={{
                  ...ppStyles.leverageSummaryToggle,
                  ...(compactActionChrome ? ppStyles.leverageSummaryToggleCompact : null),
                }}
              >
                {leverageSummaryToggleText}
              </span>
            </button>
          )}
          {showLeverageCardPicker ? (
            <div
              style={{
                ...ppStyles.leverageCardsRow,
                ...(compactLeverage ? ppStyles.leverageCardsRowCompact : null),
              }}
            >
              {playableLeverageCards.map((card) => {
                const isPrepared = armedCardId === card.card_id && !card.used
                const leverageCardTitle = `${t("play.leverage_card_target", { target: card.target_name })}: ${card.leverage}`
                return (
                  <button
                    key={card.card_id}
                    type="button"
                    style={{
                      ...ppStyles.leverageMiniCard,
                      ...(isPrepared ? ppStyles.leverageMiniCardArmed : null),
                      ...(card.used ? ppStyles.leverageMiniCardUsed : null),
                    }}
                    onClick={() => {
                      if (card.used || actionControlsDisabled) return
                      setSelectedOptionIndex(null)
                      setShowFreeInput(false)
                      setArmedCardId(isPrepared ? null : card.card_id)
                      if (compactLeverage && !isPrepared) {
                        setLeverageExpanded(false)
                      }
                    }}
                    disabled={actionControlsDisabled || card.used}
                    aria-pressed={isPrepared}
                    aria-label={leverageCardTitle}
                    title={leverageCardTitle}
                  >
                    <strong style={ppStyles.leverageMiniTarget} title={card.target_name}>{card.target_name}</strong>
                    <span style={ppStyles.leverageMiniActionHint}>
                      {isPrepared ? t("play.leverage_mini_prepared_hint") : t("play.leverage_mini_cta")}
                    </span>
                    <span
                      style={{
                        ...ppStyles.leverageMiniText,
                        ...(compactLeverage ? ppStyles.leverageMiniTextCompact : null),
                      }}
                      title={card.leverage}
                    >
                      {card.leverage}
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}
          {spentLeverageCards.length > 0 && playableLeverageCards.length > 0 ? (
            <div style={ppStyles.leverageSpentRow} aria-label={t("play.leverage_spent_group")}>
              <span style={ppStyles.leverageSpentLabel}>{t("play.leverage_spent_group")}</span>
              <span style={ppStyles.leverageSpentTargets} title={spentLeverageTargets}>
                {spentLeverageTargets}
              </span>
            </div>
          ) : null}
        </section>
      ) : null}

      {armedCard ? (
          <section
            ref={setCommitFocusNode}
            style={{
              ...ppStyles.leverageRevealPanel,
              ...(isRevealingLeverage ? ppStyles.leverageRevealPanelActive : null),
            }}
            aria-label={t("play.leverage_confirm_label")}
          >
            <div style={ppStyles.leverageRevealHeader}>
              <strong style={ppStyles.leverageRevealTitle}>
                {t("play.leverage_confirm_title", { target: armedCard.target_name })}
              </strong>
              <span style={ppStyles.leverageRevealHint}>
                {t("play.leverage_confirm_hint", { target: armedCard.target_name })}
              </span>
            </div>
            <div style={ppStyles.leverageRevealStatement}>
              <span style={ppStyles.leverageRevealEvidenceLabel}>
                {t("play.leverage_evidence_label")}
              </span>
              <div style={ppStyles.leverageRevealEvidence}>{armedCard.leverage}</div>
            </div>
            {isRevealingLeverage ? (
              <motion.div
                style={ppStyles.leverageRevealCeremony}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={transitions.snap}
                aria-live="polite"
              >
                {[
                  t("play.leverage_ceremony_exposed"),
                  t("play.leverage_ceremony_target", { target: armedCard.target_name }),
                  t("play.leverage_ceremony_room"),
                ].map((step, index) => (
                  <motion.span
                    key={step}
                    style={ppStyles.leverageRevealCeremonyStep}
                    initial={{ opacity: 0.35, y: 4 }}
                    animate={{ opacity: [0.42, 1, 0.78], y: [4, 0, 0] }}
                    transition={{
                      duration: 0.9,
                      delay: index * 0.12,
                      repeat: Infinity,
                      repeatDelay: 0.6,
                    }}
                  >
                    {index > 0 ? <span style={ppStyles.leverageRevealCeremonyDivider} aria-hidden>·</span> : null}
                    <span style={ppStyles.leverageRevealCeremonyText}>{step}</span>
                  </motion.span>
                ))}
              </motion.div>
            ) : null}
            {isWritingLeverageDiary ? null : (
              <div style={ppStyles.leverageRevealActions}>
                <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
                  <button
                    style={{
                      ...ppStyles.actionPrimaryLine,
                      ...(compactActionChrome ? ppStyles.actionPrimaryLineCompact : null),
                      ...(actionControlsDisabled ? ppStyles.actionPrimaryLineDisabled : null),
                    }}
                    type="button"
                    aria-keyshortcuts="Enter"
                    title={t("play.shortcut_enter_submit")}
                    onClick={() => handleLeverageReveal(armedCard)}
                    disabled={actionControlsDisabled}
                  >
                    {isRevealingLeverage ? t("play.leverage_revealing") : t("play.leverage_confirm_cta")}
                  </button>
                  {renderDiaryAttachPreview("leverage")}
                </div>
                <div
                  style={{
                    ...ppStyles.commitSecondaryActions,
                    ...ppStyles.inlineCommitSecondaryActions,
                    ...(compactActionChrome ? ppStyles.commitSecondaryActionsCompact : null),
                  }}
                >
                  <button
                    type="button"
                    style={{
                      ...ppStyles.advisorInlineAction,
                      ...inlineActionDisabledStyle,
                    }}
                    onClick={onOpenAdvisor}
                    disabled={actionControlsDisabled}
                    aria-haspopup="dialog"
                    aria-label={t("play.ask_friend_open_title")}
                    title={t("play.ask_friend_open_title")}
                  >
                    {t("play.ask_friend_inline")}
                  </button>
                  <button
                    type="button"
                    style={{
                      ...ppStyles.commitTextButton,
                      ...inlineActionDisabledStyle,
                    }}
                    onClick={() => {
                      setArmedCardId(null)
                      setLeverageExpanded(false)
                    }}
                    disabled={actionControlsDisabled}
                    aria-keyshortcuts="Escape"
                    title={t("play.shortcut_escape_cancel")}
                  >
                    {t("play.leverage_confirm_cancel")}
                  </button>
                </div>
              </div>
            )}
            {renderDiaryEditor("leverage")}
          </section>
        ) : null}

      {showStandardOptions ? (
        <>
          <div
            style={{
              ...ppStyles.optionsList,
              ...(compactActionChrome ? ppStyles.optionsListCompact : null),
            }}
          >
            {options.length === 0 ? (
              <div style={ppStyles.noOptions}>
                {t("play.action_no_options")}
              </div>
            ) : (
              visibleOptionEntries.map(({ opt, i }) => {
                const parsed = parseOptionLabel(opt.label)
                const isSelected = selectedOptionIndex === i
                const isPicked = pickedIndex === i
                const isUnpicked = pickedIndex !== null && pickedIndex !== i
                const optionShortcutKey = i < 9 ? String(i + 1) : null
                const isChoiceDimmed =
                  selectedOptionIndex !== null && !isSelected && pickedIndex === null
                return (
                  <div key={i} style={ppStyles.optionChoiceShell}>
                    <button
                      style={{
                        ...ppStyles.optionBtn,
                        ...(compactActionChrome ? ppStyles.optionBtnCompact : null),
                        // While picked: highlight the chosen one (gold border),
                        // fade the unchosen ones harder than busy default.
                        ...(isSelected && pickedIndex === null ? ppStyles.optionBtnSelected : null),
                        ...(isSelected && pickedIndex === null ? ppStyles.optionBtnExpanded : null),
                        ...(isChoiceDimmed ? ppStyles.optionBtnDeemphasized : null),
                        ...(isPicked ? ppStyles.optionBtnPicked : null),
                        opacity: isUnpicked ? 0.28 : actionControlsDisabled && !isPicked ? 0.5 : isChoiceDimmed ? 0.54 : 1,
                        pointerEvents: actionControlsDisabled ? "none" : "auto",
                      }}
                      onClick={() => handleOptionSelect(i)}
                      disabled={actionControlsDisabled}
                      type="button"
                      aria-pressed={isSelected}
                      aria-keyshortcuts={optionShortcutKey ?? undefined}
                      title={
                        optionShortcutKey
                          ? t("play.option_shortcut_title", { key: optionShortcutKey })
                          : undefined
                      }
                    >
                      <div
                        style={{
                          ...ppStyles.optionLabel,
                          ...(compactActionChrome ? ppStyles.optionLabelCompact : null),
                        }}
                      >
                        {/* Number key hint — visual cue that pressing the
                            digit picks this option. Lives on the leading
                            edge so it reads as "shortcut: 1, then this
                            action." Hidden on the small handful of options
                            beyond 9 (we cap at the first 9 for sanity). */}
                        {optionShortcutKey ? (
                          <kbd
                            style={ppStyles.optionKbd}
                            aria-label={t("play.option_shortcut_title", { key: optionShortcutKey })}
                          >
                            {optionShortcutKey}
                          </kbd>
                        ) : null}
                        {parsed.tag ? (
                          <span
                            style={{
                              ...ppStyles.optionTagChip,
                              ...optionTagStyle(parsed.tag),
                            }}
                          >
                            {parsed.tag}
                          </span>
                        ) : null}
                        <span>{parsed.body}</span>
                        {opt.hint ? (
                          <span
                            style={{
                              ...ppStyles.optionHintInline,
                              ...(compactActionChrome ? ppStyles.optionHintInlineCompact : null),
                            }}
                            title={opt.hint}
                          >
                            {opt.hint}
                          </span>
                        ) : null}
                      </div>
                    </button>
                    {isSelected && pickedIndex === null ? renderSelectedOptionConfirm() : null}
                  </div>
                )
              })
            )}
          </div>
        </>
      ) : null}

      {/* Turn resolving echo — confirms the just-submitted move while
          the LLM composes the next beat. It stays typographic so the
          wait reads as narration, not another panel inside the story. */}
      <AnimatePresence>
        {showPickedReflection && busy ? (
          <ResolvingTurnPanel
            moveTag={resolvingMoveTag}
            moveText={resolvingMoveText}
            privateIntent={diaryDraft}
            target={resolvingTarget}
          />
        ) : null}
      </AnimatePresence>

      {showFreeActionSurface ? (
        showFreeComposer ? (
          <div
            ref={setCommitFocusNode}
            style={ppStyles.freeInputBox}
          >
            <textarea
              className="play-free-textarea"
              ref={freeTextareaRef}
              style={ppStyles.freeTextarea}
              value={freeInput}
              placeholder={t("play.action_free_placeholder")}
              aria-label={t("play.free_action_title")}
              aria-keyshortcuts={freeTextareaKeyShortcuts}
              title={freeTextareaTitle}
              onChange={(e) => setFreeInput(e.target.value)}
              onKeyDown={(e) => {
                // Cmd/Ctrl + Enter submits — the standard "send" pattern
                // for any modern textarea input. Plain Enter still
                // line-breaks because the input is multi-line drama.
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  if (!freeInput.trim() || actionControlsDisabled) return
                  e.preventDefault()
                  handleSubmitFreeWithReflect()
                } else if (e.key === "Escape" && options.length > 0) {
                  e.preventDefault()
                  setShowFreeInput(false)
                  if (!freeInput.trim()) {
                    setFreeInput("")
                  }
                }
              }}
              disabled={actionControlsDisabled}
              spellCheck={false}
              autoFocus
              rows={2}
            />
            {isWritingFreeDiary ? null : (
              <div
                style={{
                  ...ppStyles.freeCommitDock,
                  ...(compactActionChrome ? ppStyles.freeCommitDockCompact : null),
                }}
              >
                <div ref={setFreeActionNode} style={ppStyles.freeInputActions}>
                  {freeActionDraft ? (
                    <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
                      <button
                        style={{
                          ...ppStyles.actionPrimaryLine,
                          ...(compactActionChrome ? ppStyles.actionPrimaryLineCompact : null),
                          ...(actionControlsDisabled ? ppStyles.actionPrimaryLineDisabled : null),
                        }}
                        onClick={() => handleSubmitFreeWithReflect()}
                        disabled={actionControlsDisabled}
                        aria-keyshortcuts="Meta+Enter Control+Enter"
                        title={t("play.shortcut_mod_enter_submit")}
                        type="button"
                      >
                        {actionControlsDisabled ? t("play.action_busy") : t("play.action_submit")}
                      </button>
                      {renderDiaryAttachPreview("free")}
                    </div>
                  ) : (
                    <div style={{ ...ppStyles.commitPrimaryActions, ...ppStyles.inlineCommitPrimaryActions }}>
                      <span style={ppStyles.freeEmptyHint}>{t("play.free_empty_hint")}</span>
                    </div>
                  )}
                  <div
                    style={{
                      ...ppStyles.commitSecondaryActions,
                      ...ppStyles.inlineCommitSecondaryActions,
                      ...(compactActionChrome ? ppStyles.commitSecondaryActionsCompact : null),
                    }}
                  >
                    <button
                      type="button"
                      style={{
                        ...ppStyles.advisorInlineAction,
                        ...inlineActionDisabledStyle,
                      }}
                      onClick={onOpenAdvisor}
                      disabled={actionControlsDisabled}
                      aria-haspopup="dialog"
                      aria-label={t("play.ask_friend_open_title")}
                      title={t("play.ask_friend_open_title")}
                    >
                      {t("play.ask_friend_inline")}
                    </button>
                    {options.length > 0 ? (
                      <button
                        style={{
                          ...ppStyles.commitTextButton,
                          ...inlineActionDisabledStyle,
                        }}
                        onClick={() => {
                          setShowFreeInput(false)
                          if (!freeActionDraft) {
                            setFreeInput("")
                          }
                        }}
                        disabled={actionControlsDisabled}
                        type="button"
                        aria-keyshortcuts="Escape"
                        title={t("play.shortcut_escape_cancel")}
                      >
                        {freeActionDraft ? t("play.action_hide_free") : t("play.action_cancel")}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            )}
            {freeActionDraft ? renderDiaryEditor("free") : null}
          </div>
        ) : null
      ) : null}

      {showFreeActionToggle || showIdleAdvisorLine ? (
        <div style={ppStyles.alternateActionRow}>
          {showFreeActionToggle ? (
            <button
              style={{
                ...ppStyles.alternateActionButton,
                ...inlineActionDisabledStyle,
              }}
              onClick={() => {
                setSelectedOptionIndex(null)
                setArmedCardId(null)
                setShowFreeInput(true)
              }}
              disabled={actionControlsDisabled}
              aria-label={freeActionToggleTitle}
              title={freeActionToggleTitle}
              type="button"
            >
              <span style={ppStyles.alternateActionLabel}>{freeActionToggleText}</span>
              <span style={ppStyles.alternateActionHint}>{freeActionToggleHint}</span>
            </button>
          ) : null}
          {showIdleAdvisorLine ? (
            <button
              type="button"
              style={{
                ...ppStyles.alternateActionButton,
                ...inlineActionDisabledStyle,
              }}
              onClick={onOpenAdvisor}
              disabled={actionControlsDisabled}
              aria-haspopup="dialog"
              aria-label={t("play.ask_friend_open_title")}
              title={t("play.ask_friend_open_title")}
            >
              <span style={ppStyles.alternateActionLabel}>{t("play.ask_friend_inline")}</span>
              <span style={ppStyles.alternateActionHint}>{t("play.ask_friend_inline_hint")}</span>
            </button>
          ) : null}
        </div>
      ) : null}

      {showActionTelemetry ? (
        <SceneReadStrip
          clocks={sceneClocks}
          pulses={latestNpcPulses}
          castNameById={castNameById}
        />
      ) : null}
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Floating Advisor button
// ---------------------------------------------------------------------------

function AdvisorFab({
  onOpen,
  avatarUrl,
  persona,
}: {
  onOpen: () => void
  avatarUrl: string
  persona: string
}) {
  const t = useT()
  const compactFab = useCompactLayout("(max-width: 680px)")
  return (
    <button
      className="advisor-fab"
      style={{
        ...ppStyles.fab,
        ...(compactFab ? ppStyles.fabCompact : null),
      }}
      onClick={onOpen}
      title={t("play.fab_title", { persona })}
      aria-label={t("play.fab_label")}
      aria-haspopup="dialog"
      type="button"
    >
      <span className="advisor-fab__label" style={ppStyles.fabLabel}>
        {t("play.fab_label")}
      </span>
      <img className="advisor-fab__avatar" src={avatarUrl} alt="" style={ppStyles.fabAvatarImg} loading="lazy" />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Advisor sidechat panel
// ---------------------------------------------------------------------------

function AdvisorSidechat({
  sessionId,
  persona,
  avatarUrl,
  turnsRemaining,
  isComplete,
  isCommitmentActive,
  commitmentSummary,
  suggestions,
  onClose,
  onOracleConsumed,
}: {
  sessionId: string
  persona: string
  avatarUrl: string
  turnsRemaining: number
  isComplete: boolean
  isCommitmentActive: boolean
  commitmentSummary: ActionCommitmentSummary | null
  suggestions: string[]
  onClose: () => void
  onOracleConsumed: (newBudget: number) => void
}) {
  const api = useApi()
  const t = useT()
  const [messages, setMessages] = useState<NarrativeAdvisorMessage[]>([])
  const [oracleOrds, setOracleOrds] = useState<Set<number>>(new Set())
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingOracleQuestion, setPendingOracleQuestion] = useState<string | null>(null)
  const [draftFocusToken, setDraftFocusToken] = useState(0)
  const panelRef = useRef<HTMLElement | null>(null)
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const oracleConfirmRef = useRef<HTMLButtonElement | null>(null)
  const initialFocusDoneRef = useRef(false)
  const compactAdvisor = useCompactLayout("(max-width: 520px)")
  const isEmptyAdvisor = messages.length === 0 && !busy
  const hasAdvisorDraft = draft.trim().length > 0
  const canUseOracle = !isComplete && turnsRemaining > 1
  const oracleBudgetAfter = Math.max(1, turnsRemaining - 1)
  const visibleSuggestions = useMemo(() => {
    const contextual =
      commitmentSummary?.kind === "option"
        ? [t("play.advisor_suggest_option_backfire"), t("play.advisor_suggest_option_improve")]
        : commitmentSummary?.kind === "leverage"
          ? [t("play.advisor_suggest_leverage_timing"), t("play.advisor_suggest_leverage_value")]
          : commitmentSummary?.kind === "free"
            ? [t("play.advisor_suggest_free_target"), t("play.advisor_suggest_free_wording")]
            : []
    const deduped = [...contextual]
    for (const suggestion of suggestions) {
      if (!deduped.includes(suggestion)) {
        deduped.push(suggestion)
      }
    }
    return deduped.slice(0, 4)
  }, [commitmentSummary?.kind, suggestions, t])
  const advisorPanelVariants = compactAdvisor
    ? {
        initial: { opacity: 0, x: 0, y: 24 },
        animate: { opacity: 1, x: 0, y: 0 },
        exit: { opacity: 0, x: 0, y: 18 },
      }
    : slideInRightVariants

  const cancelPendingOracle = useCallback(() => {
    setPendingOracleQuestion(null)
    setDraftFocusToken((token) => token + 1)
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .getNarrativeAdvisorHistory(sessionId)
      .then((res) => {
        if (cancelled) return
        setMessages(res.messages)
      })
      .catch((err) => {
        if (cancelled) return
        setError(friendlyError(err, t("play.advisor_history_failed")))
      })
    return () => {
      cancelled = true
    }
  }, [api, sessionId])

  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [messages.length])

  useEffect(() => {
    if (!pendingOracleQuestion || busy) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      e.preventDefault()
      cancelPendingOracle()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [busy, cancelPendingOracle, pendingOracleQuestion])

  useEffect(() => {
    if (pendingOracleQuestion || busy) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return
      const target = e.target as HTMLElement | null
      const inEditable =
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "INPUT" ||
        !!target?.isContentEditable
      if (inEditable && draft.trim()) {
        e.preventDefault()
        return
      }
      e.preventDefault()
      onClose()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [busy, draft, onClose, pendingOracleQuestion])

  const focusAdvisorTextarea = useCallback(() => {
    const node = textareaRef.current
    if (!node || node.disabled) return
    node.focus({ preventScroll: true })
    const cursor = node.value.length
    node.setSelectionRange(cursor, cursor)
  }, [])

  useEffect(() => {
    if (initialFocusDoneRef.current || busy || pendingOracleQuestion) return
    initialFocusDoneRef.current = true
    const frame = window.requestAnimationFrame(focusAdvisorTextarea)
    const timers = [90, 220].map((delay) => window.setTimeout(focusAdvisorTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, focusAdvisorTextarea, pendingOracleQuestion])

  useEffect(() => {
    if (!draftFocusToken || busy || pendingOracleQuestion) return
    const frame = window.requestAnimationFrame(focusAdvisorTextarea)
    const timers = [90, 220].map((delay) => window.setTimeout(focusAdvisorTextarea, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, draftFocusToken, focusAdvisorTextarea, pendingOracleQuestion])

  useEffect(() => {
    if (!pendingOracleQuestion || busy) return
    const focusConfirm = () => {
      const node = oracleConfirmRef.current
      if (!node || node.disabled) return
      node.focus({ preventScroll: true })
    }
    const frame = window.requestAnimationFrame(focusConfirm)
    const timers = [90, 220].map((delay) => window.setTimeout(focusConfirm, delay))
    return () => {
      window.cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [busy, pendingOracleQuestion])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return
      const panel = panelRef.current
      if (!panel) return
      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>(
          [
            "button:not([disabled])",
            "textarea:not([disabled])",
            "input:not([disabled])",
            "select:not([disabled])",
            "a[href]",
            "[tabindex]:not([tabindex='-1'])",
          ].join(","),
        ),
      ).filter((node) => node.offsetParent !== null)
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus({ preventScroll: true })
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus({ preventScroll: true })
      } else if (active instanceof Node && !panel.contains(active)) {
        e.preventDefault()
        first.focus({ preventScroll: true })
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  const submitAsk = async (question: string, oracle: boolean) => {
    setBusy(true)
    setError(null)
    setDraft("")
    setPendingOracleQuestion(null)
    try {
      const res = await api.askNarrativeAdvisor(sessionId, {
        question,
        ...(oracle ? { oracle_mode: true } : {}),
      })
      setMessages((prev) => [...prev, res.player_message, res.advisor_message])
      if (res.oracle_used) {
        setOracleOrds((prev) => {
          const next = new Set(prev)
          next.add(res.advisor_message.ord)
          return next
        })
        if (typeof res.turn_budget_after === "number") {
          onOracleConsumed(res.turn_budget_after)
        }
      }
    } catch (err) {
      setError(friendlyError(err, t("play.advisor_ask_failed")))
      setDraft(question)
      setDraftFocusToken((token) => token + 1)
    } finally {
      setBusy(false)
    }
  }

  const handleAsk = (oracle: boolean) => {
    const question = draft.trim()
    if (!question || busy) return
    if (oracle && isComplete) {
      setError(t("play.oracle_completed_error"))
      return
    }
    if (oracle) {
      setPendingOracleQuestion(question)
      return
    }
    void submitAsk(question, false)
  }
  const applySuggestion = (suggestion: string) => {
    setDraft(suggestion)
    setDraftFocusToken((token) => token + 1)
  }

  const renderSuggestionBlock = (variant: "empty" | "composer") =>
    visibleSuggestions.length > 0 ? (
      <div
        style={{
          ...ppStyles.advisorSuggestionBlock,
          ...(variant === "empty" ? ppStyles.advisorSuggestionBlockEmpty : null),
        }}
      >
        <span style={ppStyles.advisorSuggestionLabel}>
          {t("play.advisor_suggestions_label")}
        </span>
        <div
          style={{
            ...ppStyles.advisorSuggestionRow,
            ...(variant === "empty" ? ppStyles.advisorSuggestionRowEmpty : null),
          }}
        >
          {visibleSuggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              aria-label={t("play.advisor_suggestion_apply_title", { question: suggestion })}
              title={t("play.advisor_suggestion_apply_title", { question: suggestion })}
              style={{
                ...ppStyles.advisorSuggestionChip,
                ...(variant === "empty" ? ppStyles.advisorSuggestionChipEmpty : null),
              }}
              onClick={() => applySuggestion(suggestion)}
              disabled={busy || !!pendingOracleQuestion}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    ) : null

  return (
    <>
      <motion.div
        style={{
          ...ppStyles.advisorBackdrop,
          ...(compactAdvisor ? ppStyles.advisorBackdropCompact : null),
        }}
        onClick={onClose}
        variants={fadeVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={fadeTransition}
      />
      <motion.aside
        ref={panelRef}
        style={{
          ...ppStyles.advisorPanel,
          ...(compactAdvisor ? ppStyles.advisorPanelCompact : null),
        }}
        variants={advisorPanelVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={compactAdvisor ? transitions.snap : slideInRightTransition}
        role="dialog"
        aria-modal="true"
        aria-label={t("play.advisor_title")}
      >
        <header
          style={{
            ...ppStyles.advisorHeader,
            ...(compactAdvisor ? ppStyles.advisorHeaderCompact : null),
          }}
        >
          <img
            src={avatarUrl}
            alt=""
            style={{
              ...ppStyles.advisorHeaderAvatar,
              ...(compactAdvisor ? ppStyles.advisorHeaderAvatarCompact : null),
            }}
            loading="lazy"
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={ppStyles.advisorTitle}>{t("play.advisor_title")}</div>
            <div style={{ ...ppStyles.advisorPersona, ...(compactAdvisor ? ppStyles.advisorPersonaCompact : null) }}>
              {persona}
            </div>
          </div>
          <button
            style={ppStyles.advisorClose}
            onClick={onClose}
            type="button"
            aria-label={t("play.advisor_close")}
            aria-keyshortcuts="Escape"
            title={t("play.shortcut_escape_cancel")}
          >
            ✕
          </button>
        </header>

        {isCommitmentActive ? (
          <div
            style={{
              ...ppStyles.advisorContextLine,
              ...(compactAdvisor ? ppStyles.advisorContextLineCompact : null),
            }}
          >
            <span style={ppStyles.advisorContextKicker}>
              {commitmentSummary?.kicker ?? t("play.advisor_commitment_notice_kicker")}
            </span>
            <span
              style={{
                ...ppStyles.advisorContextText,
                ...(compactAdvisor ? ppStyles.advisorContextTextCompact : null),
              }}
            >
              {commitmentSummary
                ? [
                    commitmentSummary.title,
                    commitmentSummary.detail,
                    commitmentSummary.motive
                      ? t("play.advisor_commitment_motive", { motive: commitmentSummary.motive })
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : t("play.advisor_commitment_notice_body")}
            </span>
          </div>
        ) : null}

        <div
          style={{
            ...ppStyles.advisorMessages,
            ...(compactAdvisor ? ppStyles.advisorMessagesCompact : null),
            ...(isEmptyAdvisor ? ppStyles.advisorMessagesEmpty : null),
          }}
          ref={scrollerRef}
        >
          {messages.length === 0 ? (
            hasAdvisorDraft ? null : renderSuggestionBlock("empty")
          ) : (
            messages.map((m) => {
              const isOracle = m.role === "advisor" && oracleOrds.has(m.ord)
              return (
                <motion.div
                  key={`${m.role}-${m.ord}`}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={itemTransition}
                  style={m.role === "player" ? ppStyles.advisorRowPlayer : ppStyles.advisorRowAdvisor}
                >
                  {isOracle ? (
                    <div style={ppStyles.oracleBadge}>{t("play.oracle_badge")}</div>
                  ) : null}
                  {isOracle ? (
                    <div style={{ ...ppStyles.advisorTranscriptLine, ...ppStyles.advisorTranscriptLineOracle }}>
                      <span style={{ ...ppStyles.advisorTranscriptSpeaker, ...ppStyles.oracleBadge }}>
                        {t("play.oracle_badge")}
                      </span>
                      <span style={ppStyles.advisorBubbleOracle}>{m.content}</span>
                    </div>
                  ) : (
                    <div style={ppStyles.advisorTranscriptLine}>
                      <span
                        style={{
                          ...ppStyles.advisorTranscriptSpeaker,
                          ...(m.role === "player" ? ppStyles.advisorTranscriptSpeakerPlayer : null),
                        }}
                      >
                        {m.role === "player" ? t("play.advisor_speaker_player") : t("play.advisor_speaker_friend")}
                      </span>
                      <span
                        style={
                          m.role === "player"
                            ? ppStyles.advisorBubblePlayer
                            : ppStyles.advisorBubbleAdvisor
                        }
                      >
                        {m.content}
                      </span>
                    </div>
                  )}
                </motion.div>
              )
            })
          )}
          {busy ? <TypingDots /> : null}
        </div>

        {error ? <div style={ppStyles.advisorError}>{error}</div> : null}

        <div
          style={{
            ...ppStyles.advisorInput,
            ...(compactAdvisor ? ppStyles.advisorInputCompact : null),
            ...(isEmptyAdvisor ? ppStyles.advisorInputEmpty : null),
          }}
        >
          <div
            style={{
              ...ppStyles.advisorComposer,
              ...(compactAdvisor ? ppStyles.advisorComposerCompact : null),
              ...(isEmptyAdvisor ? ppStyles.advisorComposerEmpty : null),
              ...(pendingOracleQuestion ? ppStyles.advisorComposerOracleArmed : null),
            }}
          >
            <textarea
              ref={textareaRef}
              style={ppStyles.advisorTextarea}
              value={draft}
              placeholder={t("play.advisor_textarea_placeholder")}
              aria-label={t("play.advisor_textarea_placeholder")}
              aria-keyshortcuts="Meta+Enter Control+Enter"
              title={t("play.shortcut_mod_enter_submit")}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault()
                  if (pendingOracleQuestion) {
                    void submitAsk(pendingOracleQuestion, true)
                    return
                  }
                  handleAsk(false)
                }
              }}
              disabled={busy || !!pendingOracleQuestion}
              rows={2}
            />
            {pendingOracleQuestion ? (
              <div style={ppStyles.oracleInlineLine}>
                <span style={ppStyles.oracleInlineCopy}>
                  {t("play.oracle_inline_summary", {
                    before: turnsRemaining,
                    after: oracleBudgetAfter,
                  })}
                </span>
                <div style={ppStyles.oracleInlineActions}>
                  <button
                    ref={oracleConfirmRef}
                    style={ppStyles.advisorSendBtn}
                    type="button"
                    onClick={() => void submitAsk(pendingOracleQuestion, true)}
                    disabled={busy}
                  >
                    {t("play.oracle_inline_confirm")}
                  </button>
                  <button
                    style={ppStyles.oracleInlineCancelBtn}
                    type="button"
                    onClick={cancelPendingOracle}
                    disabled={busy}
                    aria-keyshortcuts="Escape"
                    title={t("play.shortcut_escape_cancel")}
                  >
                    {t("play.oracle_inline_cancel")}
                  </button>
                </div>
              </div>
            ) : (
              <>
                {isEmptyAdvisor || hasAdvisorDraft ? null : renderSuggestionBlock("composer")}
                {hasAdvisorDraft ? (
                  <div
                    style={{
                      ...ppStyles.advisorBtnRow,
                      ...(compactAdvisor ? ppStyles.advisorBtnRowCompact : null),
                    }}
                  >
                    <button
                      style={{
                        ...ppStyles.advisorSendBtn,
                        ...(compactAdvisor ? ppStyles.advisorActionBtnCompact : null),
                        ...(busy ? ppStyles.advisorActionDisabled : null),
                      }}
                      onClick={() => handleAsk(false)}
                      disabled={busy}
                      type="button"
                      aria-keyshortcuts="Meta+Enter Control+Enter"
                      title={t("play.shortcut_mod_enter_submit")}
                    >
                      {t("play.advisor_send")}
                    </button>
                    <button
                      style={{
                        ...ppStyles.oracleBtn,
                        ...(compactAdvisor ? ppStyles.advisorActionBtnCompact : null),
                        ...(busy || !canUseOracle ? ppStyles.advisorActionDisabled : null),
                      }}
                      onClick={() => handleAsk(true)}
                      disabled={busy || !canUseOracle}
                      type="button"
                      title={
                        isComplete
                          ? t("play.oracle_tip_complete")
                          : turnsRemaining <= 1
                            ? t("play.oracle_tip_no_turns")
                            : t("play.oracle_tip_active", { turns: turnsRemaining })
                    }
                  >
                      {canUseOracle
                        ? t("play.oracle_button_with_cost")
                        : t("play.oracle_button")}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      </motion.aside>
    </>
  )
}

// Bouncing 3-dot typing indicator. Used in advisor sidechat while waiting
// for the LLM response. Pure CSS keyframes via inline animation.
function TypingDots() {
  const t = useT()
  return (
    <div
      style={ppStyles.typingRow}
      role="status"
      aria-live="polite"
      aria-label={t("play.advisor_typing_status")}
    >
      <div style={ppStyles.typingBubble} aria-hidden>
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            style={ppStyles.typingDot}
            animate={{ y: [0, -4, 0] }}
            transition={{
              duration: 0.9,
              repeat: Infinity,
              delay: i * 0.15,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const ppStyles: Record<string, CSSProperties> = {
  page: { minHeight: "100%", background: "var(--bg)", display: "flex", flexDirection: "column" },
  centerNote: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--text-muted)",
    fontSize: 14,
  },

  header: {
    padding: "0",
    borderBottom: "1px solid var(--line)",
    display: "flex",
    flexDirection: "column",
    background: "var(--bg)",
    position: "sticky",
    top: 0,
    zIndex: 5,
  },
  headerCompact: {
    background: "rgba(12,12,16,0.94)",
    backdropFilter: "blur(12px)",
  },
  headerRow: {
    padding: "16px 32px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
  },
  headerRowCompact: {
    padding: "10px 16px 9px",
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    gap: 10,
  },
  headerWithCover: {
    backgroundSize: "cover",
    backgroundPosition: "center 35%",
    borderBottom: "1px solid rgba(255,255,255,0.1)",
  },
  progressTrack: {
    height: 3,
    background: "rgba(255,255,255,0.08)",
    position: "relative",
  },
  progressFill: {
    height: "100%",
    background: "var(--accent)",
    transition: "width 480ms ease-out",
  },
  backBtnOnCover: {
    color: "white",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.30)",
    borderRadius: 0,
    padding: "0 0 4px",
    backdropFilter: "none",
    width: "auto",
  },
  backBtn: {
    fontSize: 13,
    color: "var(--text-muted)",
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: 4,
    width: 90,
    textAlign: "left",
  },
  backBtnCompact: {
    width: "auto",
    padding: "0 0 3px",
    borderBottom: "1px solid rgba(255,255,255,0.16)",
    color: "rgba(244,239,230,0.82)",
    whiteSpace: "nowrap" as const,
  },
  headerTitle: { flex: 1, textAlign: "center", minWidth: 0 },
  headerTitleLine: {
    fontFamily: "var(--font-narrative)",
    fontSize: 17,
    color: "var(--text)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  headerTitleLineCompact: {
    fontSize: 15,
    color: "rgba(255,255,255,0.90)",
  },
  headerCast: {
    fontSize: 12,
    color: "var(--text-faint)",
    marginTop: 4,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  headerTurns: { marginLeft: 8 },
  headerTurnsCompact: {
    color: "rgba(245,200,120,0.82)",
    fontSize: 12,
    fontWeight: 720,
    whiteSpace: "nowrap" as const,
    letterSpacing: 0,
  },
  headerSpacer: { width: 90 },

  main: { flex: 1, display: "flex", justifyContent: "center", overflow: "visible" },
  storyColumn: { width: "100%", maxWidth: 840, padding: "28px 32px 120px", overflowY: "visible" },

  runContextPanel: {
    margin: "0 0 16px",
    paddingTop: 10,
    paddingRight: 0,
    paddingBottom: 7,
    paddingLeft: 0,
    borderBottom: "none",
    backgroundSize: "auto",
    backgroundPosition: "initial",
    boxShadow: "none",
    overflow: "hidden",
  },
  runContextPanelCompact: {
    margin: "0 0 12px",
    paddingTop: 6,
    paddingRight: 0,
    paddingBottom: 8,
    paddingLeft: 0,
    borderTop: "none",
    borderBottom: "none",
  },
  runCompactHeader: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 3,
  },
  runCompactRoleTag: {
    color: "rgba(205,180,245,0.62)",
    fontSize: 11.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  runCompactRoleTitle: {
    minWidth: 0,
    color: "rgba(255,245,230,0.96)",
    fontFamily: "var(--font-narrative)",
    fontSize: 19,
    lineHeight: 1.15,
    fontWeight: 500,
  },
  runCompactMeta: {
    gridColumn: "1 / -1",
    color: "var(--text-faint)",
    fontSize: 10.5,
    lineHeight: 1.2,
    fontWeight: 650,
    maxWidth: "100%",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  runCompactObjective: {
    marginTop: 6,
    maxWidth: 560,
  },
  runCompactObjectiveLabel: {
    color: "rgba(205,180,245,0.58)",
    fontSize: 9.5,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  runCompactObjectiveText: {
    color: "rgba(244,239,230,0.72)",
    fontFamily: "var(--font-narrative)",
    fontSize: 13.5,
    lineHeight: 1.38,
    fontWeight: 500,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
  },
  runContextHeader: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 5,
  },
  runContextMeta: {
    color: "var(--text-faint)",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 650,
    maxWidth: 260,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  runContextObjectiveLine: {
    marginTop: 7,
    maxWidth: 680,
    minWidth: 0,
  },
  runContextObjectiveLabel: {
    color: "rgba(205,180,245,0.62)",
    fontSize: 10,
    lineHeight: 1.1,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  runContextObjectiveText: {
    minWidth: 0,
    color: "rgba(255,245,230,0.76)",
    fontFamily: "var(--font-narrative)",
    fontSize: 14,
    lineHeight: 1.42,
    fontWeight: 500,
  },
  runContextGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1.35fr) minmax(230px, 0.65fr)",
    gap: 28,
    alignItems: "start",
  },
  runContextGridCompact: {
    gridTemplateColumns: "1fr",
    gap: 10,
  },
  runIdentity: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 7,
  },
  runIdentityCompact: {
    gap: 5,
  },
  runKicker: {
    fontSize: 11.5,
    color: "rgba(205,180,245,0.62)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 720,
  },
  runRoleLine: {
    display: "flex",
    alignItems: "baseline",
    gap: 0,
    minWidth: 0,
    flexWrap: "wrap" as const,
  },
  runRoleBadge: {
    padding: 0,
    background: "transparent",
    color: "rgba(205,180,245,0.96)",
    borderRadius: 0,
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 0,
    flexShrink: 0,
    textTransform: "none" as const,
  },
  runRoleTitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 27,
    lineHeight: 1.1,
    color: "white",
    fontWeight: 500,
    textShadow: "none",
  },
  runRoleTitleCompact: {
    fontSize: 21,
    textShadow: "none",
  },
  runPersona: {
    maxWidth: 520,
    margin: 0,
    fontSize: 13,
    lineHeight: 1.5,
    color: "rgba(244,239,230,0.64)",
  },
  runObjective: {
    maxWidth: 580,
    display: "grid",
    gap: 3,
    paddingTop: 5,
    paddingRight: 0,
    paddingBottom: 0,
    paddingLeft: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  runObjectiveCompact: {
    paddingTop: 3,
    paddingRight: 0,
    paddingBottom: 0,
    paddingLeft: 0,
    gap: 2,
  },
  runStatus: {
    minWidth: 0,
    paddingTop: 2,
    paddingRight: 0,
    paddingBottom: 0,
    paddingLeft: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  runStatusCompact: {
    paddingTop: 3,
    paddingRight: 0,
    paddingBottom: 0,
    paddingLeft: 0,
  },
  runMetricRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    columnGap: 14,
    rowGap: 6,
    marginBottom: 8,
  },
  runMetricRowCompact: {
    gap: 12,
    marginBottom: 7,
  },
  runMetric: {
    minWidth: 0,
    padding: "0 0 4px",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "flex",
    flexDirection: "row" as const,
    alignItems: "baseline",
    gap: 6,
  },
  runProgressTrack: {
    position: "relative" as const,
    display: "block",
    marginTop: 10,
    width: "100%",
    maxWidth: 680,
    height: 2,
    background: "rgba(255,255,255,0.12)",
    overflow: "hidden",
  },
  runProgressFill: {
    position: "absolute" as const,
    inset: "0 auto 0 0",
    display: "block",
    background: "rgba(212,168,83,0.76)",
  },
  runPrivateSummary: {
    marginTop: 9,
    paddingTop: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 3,
    flexWrap: "wrap" as const,
    minWidth: 0,
  },
  runPrivateSummaryCompact: {
    marginTop: 6,
    paddingTop: 0,
    borderTop: "none",
    display: "flex",
    alignItems: "baseline",
    gap: 7,
  },
  runPrivateSummaryLabel: {
    color: "rgba(205,180,245,0.60)",
    fontSize: 10,
    lineHeight: 1.1,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  runPrivateSummaryText: {
    color: "rgba(244,239,230,0.58)",
    fontSize: 11.5,
    lineHeight: 1.4,
  },
  runCastLine: {
    marginTop: 10,
    paddingTop: 8,
    borderTop: "1px solid rgba(255,255,255,0.045)",
    display: "flex",
    alignItems: "baseline",
    gap: 8,
    minWidth: 0,
  },
  runCastLineLabel: {
    color: "rgba(232,218,205,0.46)",
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
    flexShrink: 0,
  },
  runCastLineText: {
    minWidth: 0,
    color: "rgba(244,239,230,0.64)",
    fontSize: 12,
    lineHeight: 1.25,
  },
  runCastStrip: {
    display: "flex",
    gap: 16,
    overflowX: "auto",
    marginTop: 11,
    paddingTop: 8,
  },
  runCastChip: {
    flex: "0 0 auto",
    display: "flex",
    alignItems: "center",
    gap: 8,
    minWidth: 0,
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
  },
  runCastAvatar: {
    width: 24,
    height: 24,
    borderRadius: "50%",
    objectFit: "cover",
    border: "1px solid rgba(255,255,255,0.18)",
  },
  runCastText: {
    display: "flex",
    flexDirection: "column" as const,
    maxWidth: 150,
    minWidth: 0,
    lineHeight: 1.15,
  },
  runCastName: { fontSize: 12, color: "white", fontWeight: 600 },
  runCastRole: { fontSize: 10, color: "rgba(244,239,230,0.50)", marginTop: 1 },
  runtimeInspector: {
    margin: "0 0 24px",
    padding: "10px 0 12px",
    background: "transparent",
    border: "none",
    borderTop: "1px solid rgba(212,168,83,0.20)",
    borderBottom: "none",
    borderRadius: 0,
    boxShadow: "none",
  },
  runtimeInspectorHeader: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 10,
  },
  runtimeInspectorKicker: {
    fontSize: 10.5,
    letterSpacing: 0,
    textTransform: "none" as const,
    color: "var(--accent)",
    fontWeight: 700,
  },
  runtimeInspectorGrid: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 18,
    rowGap: 7,
    flexWrap: "wrap" as const,
  },
  runtimeInspectorRow: {
    minWidth: 0,
    padding: 0,
    border: "none",
    borderRadius: 0,
    background: "transparent",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
  },
  runtimeInspectorRowLabel: {
    color: "rgba(232,218,205,0.46)",
    fontSize: 10.5,
    lineHeight: 1.2,
    fontWeight: 700,
    whiteSpace: "nowrap" as const,
  },
  runtimeInspectorRowValue: {
    minWidth: 0,
    color: "rgba(255,245,230,0.82)",
    fontSize: 12,
    lineHeight: 1.25,
    fontWeight: 760,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  runtimeInspectorDetails: {
    marginTop: 10,
    borderTop: "none",
  },
  runtimeInspectorDetailsSummary: {
    paddingTop: 4,
    cursor: "pointer",
    fontSize: 12.5,
    color: "var(--text-muted)",
    lineHeight: 1.5,
  },
  runtimeInspectorDetailGrid: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 18,
    rowGap: 7,
    flexWrap: "wrap" as const,
    paddingTop: 8,
  },
  runtimeInspectorDetailRow: {
    minWidth: 0,
    padding: 0,
    border: "none",
    borderRadius: 0,
    background: "transparent",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
  },

  roleInvAcquired: {
    color: "rgba(245,200,120,0.92)",
    fontWeight: 500,
  },

  // Inventory delta toast — sits above pulse chips on a narrator beat
  // Gauntlet-mode goals line
  goalsCard: {
    margin: "0 0 16px",
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  gauntletBadge: {
    padding: 0,
    background: "transparent",
    color: "rgba(245,150,120,0.78)",
    borderRadius: 0,
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 0,
  },
  goalsTitle: {
    fontSize: 11.5,
    color: "rgba(232,218,205,0.50)",
    letterSpacing: 0,
  },
  goalRow: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
    maxWidth: "100%",
  },
  goalDivider: {
    color: "rgba(255,255,255,0.18)",
    fontSize: 11,
    fontWeight: 900,
    flexShrink: 0,
  },
  goalText: {
    minWidth: 0,
    fontSize: 12.5,
    color: "rgba(255,245,230,0.82)",
    fontFamily: "var(--font-narrative)",
    lineHeight: 1.35,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  goalStakes: {
    fontSize: 11,
    color: "rgba(232,218,205,0.42)",
    marginTop: 0,
    paddingLeft: 0,
    fontStyle: "italic",
    lineHeight: 1.35,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },

  // A compact receipt that lands before detailed pulse cards. It gives
  // the player the "what changed because of me" read in one glance.
  outcomeReceipt: {
    marginTop: 10,
    padding: 0,
    borderTop: "none",
    display: "flex",
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 6,
    flexWrap: "wrap" as const,
  },
  outcomeReceiptInline: {
    marginTop: 6,
    paddingTop: 0,
    borderTop: "none",
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  outcomeReceiptKicker: {
    color: "rgba(245,210,140,0.84)",
    fontSize: 10.5,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  outcomeReceiptInlineLabel: {
    color: "rgba(232,218,205,0.48)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  outcomeReceiptSentence: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 4,
    flexWrap: "wrap" as const,
    color: "rgba(255,245,230,0.84)",
  },
  outcomeReceiptSentenceCompact: {
    columnGap: 7,
  },
  outcomeReceiptPhrase: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "baseline",
    gap: 5,
    maxWidth: "100%",
  },
  outcomeReceiptItemLabel: {
    flexShrink: 0,
    color: "rgba(232,218,205,0.44)",
    fontSize: 10.2,
    lineHeight: 1.15,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  outcomeReceiptValue: {
    minWidth: 0,
    color: "rgba(255,245,230,0.88)",
    fontSize: 11.8,
    fontWeight: 850,
    lineHeight: 1.25,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  outcomeReceiptChipSafe: {
    color: "rgba(190,235,210,0.92)",
  },
  outcomeReceiptChipTense: {
    color: "rgba(246,221,176,0.94)",
  },
  outcomeReceiptChipDanger: {
    color: "rgba(255,190,170,0.94)",
  },
  outcomeReceiptChipGold: {
    color: "rgba(246,221,176,0.94)",
  },
  leveragePayoff: {
    marginTop: 12,
    marginBottom: 6,
    padding: 0,
    border: "none",
    overflow: "hidden",
    position: "relative" as const,
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  leveragePayoff_warmer: {
    color: "rgba(180,230,205,0.96)",
  },
  leveragePayoff_colder: {
    color: "rgba(195,208,245,0.96)",
  },
  leveragePayoff_wary: {
    color: "rgba(245,218,160,0.96)",
  },
  leveragePayoff_broken: {
    color: "rgba(255,188,165,0.96)",
  },
  leveragePayoffKicker: {
    color: "rgba(255,224,156,0.88)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  leveragePayoffSentence: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "baseline",
    columnGap: 7,
    rowGap: 4,
    flexWrap: "wrap" as const,
    maxWidth: "100%",
  },
  leveragePayoffEvidence: {
    color: "rgba(255,245,230,0.90)",
    fontFamily: "var(--font-narrative)",
    fontSize: 12.5,
    lineHeight: 1.28,
    minWidth: 0,
    maxWidth: "min(100%, 360px)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leveragePayoffMetaValue: {
    color: "rgba(255,245,230,0.84)",
    fontSize: 11.5,
    lineHeight: 1.28,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leveragePayoffMetaDivider: {
    color: "rgba(255,255,255,0.20)",
    fontWeight: 900,
  },
  leveragePayoffReasonText: {
    minWidth: 0,
    color: "rgba(235,226,216,0.48)",
    fontSize: 11.5,
    lineHeight: 1.28,
    fontStyle: "italic" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  intentReadReceipt: {
    marginTop: 8,
    padding: "4px 0 0",
    borderTop: "none",
    display: "flex",
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 6,
    flexWrap: "wrap" as const,
  },
  intentReadKicker: {
    color: "rgba(205,180,255,0.78)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  intentReadSentence: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 5,
    flexWrap: "wrap" as const,
  },
  intentReadPhrase: {
    minWidth: 0,
    maxWidth: "min(100%, 320px)",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 5,
  },
  intentReadDivider: {
    color: "rgba(255,255,255,0.16)",
    fontSize: 11,
    fontWeight: 900,
    flexShrink: 0,
  },
  intentReadLaneValue: {
    minWidth: 0,
    color: "rgba(255,245,230,0.78)",
    fontSize: 11.5,
    lineHeight: 1.25,
    fontWeight: 750,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
    flex: "1 1 auto",
  },

  // Per-turn NPC pulse strip
  pulseImpactPanel: {
    marginTop: 6,
    padding: "2px 0 0",
    borderTop: "none",
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 5,
    flexWrap: "wrap" as const,
  },
  pulseImpactSummary: {
    display: "flex",
    alignItems: "baseline",
    gap: 8,
    flexShrink: 0,
  },
  pulseImpactSummaryCopy: {
    minWidth: 0,
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap" as const,
  },
  pulseImpactTitle: {
    color: "rgba(255,245,230,0.58)",
    fontSize: 11,
    fontWeight: 750,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  pulseImpactCount: {
    color: "rgba(244,239,230,0.42)",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0,
  },
  pulseImpactGrid: {
    minWidth: 0,
    marginTop: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 5,
    flexWrap: "wrap" as const,
    borderTop: "none",
  },
  pulseImpactCard: {
    minWidth: 0,
    maxWidth: "min(100%, 320px)",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
    padding: 0,
    borderLeft: "none",
    borderBottom: "none",
  },
  pulseImpactMark: {
    display: "flex",
    alignItems: "baseline",
    gap: 5,
    minWidth: 0,
    flexShrink: 0,
  },
  pulseImpactArrow: {
    width: "auto",
    height: "auto",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    color: "rgba(255,245,230,0.78)",
    fontSize: 11,
    fontWeight: 900,
  },
  pulseImpactDelta: {
    color: "rgba(255,245,230,0.76)",
    fontSize: 10,
    lineHeight: 1.1,
    fontWeight: 780,
    letterSpacing: 0,
    whiteSpace: "nowrap" as const,
  },
  pulseImpactBody: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
    flexWrap: "wrap" as const,
  },
  pulseImpactName: {
    color: "rgba(255,245,230,0.96)",
    fontSize: 12.5,
    lineHeight: 1.2,
  },
  pulseImpactShift: {
    color: "var(--text-muted)",
    fontSize: 11.5,
    fontWeight: 700,
    lineHeight: 1.25,
  },
  pulseImpactReason: {
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.35,
    fontStyle: "italic" as const,
    display: "inline",
    maxWidth: "min(100%, 210px)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  pulseImpactInline: {
    marginTop: 8,
    paddingTop: 6,
    borderTop: "1px solid rgba(255,255,255,0.055)",
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  pulseImpactInlineLabel: {
    color: "var(--text-faint)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  pulseImpactInlineItems: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  pulseImpactInlineItem: {
    minWidth: 0,
    maxWidth: "min(100%, 220px)",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 5,
  },
  pulseImpactInlineName: {
    minWidth: 0,
    color: "rgba(232,218,205,0.58)",
    fontSize: 10.5,
    lineHeight: 1.18,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  pulseImpactInlineDelta: {
    color: "rgba(255,245,230,0.76)",
    fontSize: 10.5,
    lineHeight: 1.18,
    whiteSpace: "nowrap" as const,
  },
  pulseShift_warmer: { color: "rgba(174,224,194,0.88)" },
  pulseShift_colder: { color: "rgba(175,192,230,0.86)" },
  pulseShift_wary: { color: "rgba(230,198,132,0.88)" },
  pulseShift_broken: { color: "rgba(255,188,168,0.92)" },
  pulseShift_steady: {},

  // Ending tier badge over banner image
  endingTierBadge: {
    position: "absolute",
    top: 16,
    left: 16,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: 0,
    background: "transparent",
    backdropFilter: "none",
    borderRadius: 4,
    border: "none",
    textShadow: "0 2px 12px rgba(0,0,0,0.75)",
  },
  endingTierBadgeText: {
    fontSize: 11,
    color: "white",
    fontWeight: 700,
    letterSpacing: 0,
  },
  endingTierTrigger: {
    fontSize: 11,
    color: "rgba(255,255,255,0.78)",
  },

  narratorBeat: { marginBottom: 32, position: "relative" as const, paddingRight: 36 },
  // Bookmarked beat — soft accent ring on the left edge, signals
  // "you marked this" without competing with the rising/peak intensity
  // ramp.
  narratorBeatBookmarked: {
    background: "linear-gradient(90deg, var(--accent-soft) 0%, transparent 16%)",
    borderRadius: 0,
  },
  beatBookmarkBtn: {
    position: "absolute" as const,
    top: 0,
    right: 0,
    width: 28,
    height: 28,
    padding: 0,
    background: "transparent",
    border: "none",
    color: "var(--text-faint)",
    fontSize: 18,
    lineHeight: 1,
    cursor: "pointer",
    transition: "color 160ms, transform 160ms",
    borderRadius: 0,
  },
  beatBookmarkBtnActive: {
    color: "var(--accent)",
  },
  narratorBeatRising: {
    marginBottom: 38,
    paddingLeft: 0,
    paddingTop: 8,
  },
  narratorBeatPeak: {
    marginBottom: 48,
    paddingLeft: 0,
    paddingTop: 12,
    paddingRight: 4,
    background: "transparent",
  },
  narratorText: {
    fontFamily: "var(--font-narrative)",
    fontSize: 16.5,
    lineHeight: 1.85,
    color: "var(--text)",
    whiteSpace: "pre-wrap",
  },
  narratorTextRising: {
    fontSize: 17.5,
    lineHeight: 1.9,
    letterSpacing: 0,
  },
  narratorTextPeak: {
    fontSize: 19,
    lineHeight: 1.95,
    letterSpacing: 0,
    color: "rgba(255,235,210,0.96)",
  },
  beatSceneBanner: {
    height: 140,
    backgroundSize: "cover",
    backgroundPosition: "center",
    marginLeft: 0,
    marginRight: -4,
    marginTop: -12,
    marginBottom: 18,
    borderRadius: 0,
  },
  beatDecorRising: {
    width: 36,
    height: 1,
    background: "rgba(140,100,200,0.55)",
    marginBottom: 12,
  },
  beatDecorPeak: {
    width: 56,
    height: 2,
    background: "linear-gradient(90deg, rgba(245,200,120,0.85), rgba(245,200,120,0))",
    marginBottom: 14,
  },
  beatSignal: {
    margin: "0 0 12px",
    padding: 0,
    display: "flex",
    alignItems: "baseline",
    gap: 8,
    width: "fit-content",
    maxWidth: "100%",
    borderRadius: 0,
    border: "none",
    background: "transparent",
  },
  beatSignalPeak: {
    color: "rgba(245,210,140,0.96)",
    background: "transparent",
  },
  beatSignalRising: {
    color: "rgba(205,190,255,0.88)",
    background: "transparent",
  },
  beatSignalMark: {
    width: 8,
    height: 8,
    borderRadius: 999,
    background: "var(--accent)",
    boxShadow: "none",
  },
  beatSignalCopy: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    gap: 8,
    flexWrap: "wrap" as const,
  },
  beatSignalTitle: {
    color: "rgba(255,245,230,0.96)",
    fontSize: 11,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  beatSignalDetail: {
    color: "var(--text-muted)",
    fontSize: 12,
    lineHeight: 1.3,
  },
  chosenChip: {
    marginTop: 14,
    fontSize: 12,
    color: "var(--text-faint)",
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "0 0 4px",
    border: "none",
    borderBottom: "1px solid var(--line)",
    borderRadius: 0,
    background: "transparent",
  },
  chosenLabel: { letterSpacing: 0, fontWeight: 650 },
  chosenText: { color: "var(--text-muted)" },

  playerBeat: {
    marginBottom: 28,
    paddingLeft: 0,
    border: "none",
  },
  playerBeatLeverageMove: {
    paddingLeft: 0,
    border: "none",
    borderRadius: 0,
    background: "transparent",
  },
  playerHandleText: {
    fontSize: 11.5,
    fontFamily: "var(--font-narrative)",
    fontWeight: 600,
    color: "rgba(232,218,205,0.66)",
    background: "transparent",
    padding: 0,
    border: "none",
    borderRadius: 0,
    letterSpacing: 0,
    textTransform: "none" as const,
    fontStyle: "normal" as const,
  },
  playerLabelSeparator: {
    margin: "0 6px",
    color: "var(--text-faint)",
    letterSpacing: 0,
  },
  playerLabel: {
    fontSize: 11,
    color: "rgba(212,168,83,0.72)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 720,
    marginBottom: 4,
  },
  playerText: { fontSize: 14.5, lineHeight: 1.6, color: "var(--text-muted)", fontStyle: "italic" },
  playerMetaLine: {
    marginTop: 7,
    display: "flex",
    alignItems: "baseline",
    columnGap: 14,
    rowGap: 4,
    flexWrap: "wrap" as const,
    color: "var(--text-faint)",
  },
  playerMetaItem: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
    maxWidth: "100%",
  },
  playerLeverageTag: {
    fontSize: 10.5,
    color: "rgba(212,168,83,0.92)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 720,
  },
  playerLeverageText: {
    minWidth: 0,
    fontSize: 12,
    lineHeight: 1.35,
    color: "rgba(255,235,200,0.90)",
    fontFamily: "var(--font-narrative)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  playerDiaryTag: {
    fontSize: 10.5,
    color: "rgba(180,150,230,0.85)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 700,
  },
  playerDiaryText: {
    minWidth: 0,
    fontSize: 12,
    lineHeight: 1.35,
    color: "rgba(220,210,240,0.92)",
    fontFamily: "var(--font-narrative)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },

  actionArea: {
    marginTop: 18,
    paddingTop: 4,
    paddingBottom: 10,
    borderTop: "none",
    position: "relative" as const,
    background: "transparent",
    backdropFilter: "none",
    zIndex: 1,
  },
  turnGuide: {
    marginBottom: 8,
    paddingTop: 0,
    paddingRight: 0,
    paddingBottom: 4,
    paddingLeft: 0,
    display: "block",
    borderRadius: 0,
    border: "none",
    background: "transparent",
  },
  turnGuideCompact: {
    marginBottom: 7,
    paddingBottom: 3,
  },
  turnGuideSelected: {
    background: "transparent",
  },
  turnGuideLeverage: {
    background: "transparent",
  },
  turnGuideFree: {
    background: "transparent",
  },
  turnGuideEndgame: {
    background: "transparent",
    boxShadow: "none",
  },
  turnGuideFinal: {
    background: "transparent",
    boxShadow: "none",
  },
  turnGuideCopy: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 3,
    flexWrap: "wrap" as const,
  },
  turnGuideTitle: {
    color: "rgba(255,245,230,0.95)",
    fontSize: 13,
    lineHeight: 1.2,
    flexShrink: 0,
  },
  turnGuideDetail: {
    color: "var(--text-muted)",
    fontSize: 12,
    lineHeight: 1.35,
    minWidth: "min(100%, 240px)",
    whiteSpace: "normal" as const,
    flex: "1 1 260px",
  },
  sceneReadStrip: {
    marginBottom: 10,
    padding: "2px 0 4px",
    borderTop: "none",
    borderBottom: "none",
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 5,
    flexWrap: "wrap" as const,
  },
  sceneReadLabel: {
    color: "var(--text-faint)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  sceneReadItems: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 5,
    flexWrap: "wrap" as const,
    flex: "1 1 260px",
  },
  sceneReadItem: {
    minWidth: 0,
    maxWidth: "min(100%, 210px)",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 4,
  },
  sceneReadName: {
    color: "var(--text-faint)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  sceneReadJoiner: {
    color: "rgba(255,255,255,0.18)",
    fontSize: 9.5,
    fontWeight: 900,
    flexShrink: 0,
  },
  sceneReadValue: {
    minWidth: 0,
    color: "rgba(255,245,230,0.88)",
    fontSize: 11.5,
    lineHeight: 1.2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leverageRail: {
    marginBottom: 0,
    padding: "0",
  },
  leverageRailCompact: {
    marginBottom: 0,
    padding: "0",
  },
  leverageSummaryButton: {
    width: "100%",
    maxWidth: "100%",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 4,
    padding: "7px 0 8px",
    background: "transparent",
    border: "none",
    color: "var(--text)",
    textAlign: "left" as const,
    cursor: "pointer",
    fontFamily: "inherit",
    outline: "none",
  },
  leverageSummaryButtonCompact: {
    gridTemplateColumns: "1fr",
    padding: "7px 0 9px",
  },
  leverageSummaryButtonOpen: {
    color: "rgba(255,236,198,0.96)",
  },
  leverageEmptySummary: {
    width: "100%",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: 8,
    padding: "7px 0 8px",
    borderBottom: "none",
    color: "var(--text)",
  },
  leverageEmptyBadge: {
    color: "rgba(232,218,205,0.58)",
    fontSize: 10.5,
    lineHeight: 1.1,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  leverageSummaryMain: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    alignItems: "baseline",
    columnGap: 7,
    rowGap: 3,
  },
  leverageSummaryEyebrow: {
    color: "rgba(212,168,83,0.82)",
    fontSize: 10.8,
    lineHeight: 1.1,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  leverageSummaryText: {
    minWidth: 0,
    color: "rgba(255,245,230,0.95)",
    fontSize: 13.5,
    lineHeight: 1.18,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leverageSummaryMeta: {
    minWidth: 0,
    gridColumn: "1 / -1",
    color: "rgba(232,218,205,0.60)",
    fontSize: 11.5,
    lineHeight: 1.28,
    fontWeight: 600,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
  },
  leverageSummaryToggle: {
    justifySelf: "end",
    color: "rgba(255,222,160,0.94)",
    fontSize: 11.5,
    fontWeight: 820,
    letterSpacing: 0,
    whiteSpace: "nowrap" as const,
  },
  leverageSummaryToggleCompact: {
    justifySelf: "start",
    marginTop: 1,
    whiteSpace: "nowrap" as const,
  },
  leverageCardsRow: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 4,
    marginTop: 0,
  },
  leverageCardsRowCompact: {
    gridTemplateColumns: "1fr",
  },
  leverageMiniCard: {
    minWidth: 0,
    textAlign: "left" as const,
    width: "100%",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 4,
    padding: "8px 0 9px",
    background: "transparent",
    border: "none",
    color: "var(--text)",
    cursor: "pointer",
    outline: "none",
  },
  leverageMiniCardArmed: {
    paddingLeft: 0,
    boxShadow: "none",
    color: "rgba(255,236,198,0.96)",
  },
  leverageMiniCardUsed: {
    opacity: 0.34,
    cursor: "default",
    filter: "grayscale(0.45)",
  },
  leverageMiniTarget: {
    color: "rgba(255,245,230,0.96)",
    fontSize: 12.5,
    lineHeight: 1.25,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leverageMiniDivider: {
    color: "rgba(255,255,255,0.18)",
    fontSize: 11,
    fontWeight: 900,
    flexShrink: 0,
  },
  leverageMiniText: {
    gridColumn: "1 / -1",
    minWidth: 0,
    color: "rgba(232,218,205,0.72)",
    fontSize: 12,
    lineHeight: 1.38,
    overflow: "hidden",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical" as const,
  },
  leverageMiniActionHint: {
    justifySelf: "end",
    color: "rgba(212,168,83,0.80)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    whiteSpace: "nowrap" as const,
  },
  leverageMiniTextCompact: {
    fontSize: 11.5,
    lineHeight: 1.42,
  },
  leverageSpentRow: {
    marginTop: 0,
    padding: "7px 0 8px",
    borderTop: "none",
    borderBottom: "1px solid rgba(255,255,255,0.045)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  leverageSpentLabel: {
    color: "rgba(232,218,205,0.32)",
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
    flexShrink: 0,
  },
  leverageSpentTargets: {
    minWidth: 0,
    color: "rgba(232,218,205,0.50)",
    fontSize: 11,
    lineHeight: 1.25,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leverageRevealPanel: {
    position: "relative" as const,
    marginTop: 4,
    marginBottom: 14,
    padding: "12px 0 0",
    border: "none",
    borderTop: "1px solid rgba(245,200,120,0.20)",
    borderRadius: 0,
    background: "transparent",
    boxShadow: "none",
    overflow: "hidden",
  },
  leverageRevealPanelActive: {
    background: "transparent",
  },
  leverageRevealEyebrow: {
    color: "var(--accent)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  leverageRevealHeader: {
    margin: "0 0 8px",
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 3,
    flexWrap: "wrap" as const,
  },
  leverageRevealTitle: {
    minWidth: 0,
    color: "rgba(255,245,230,0.95)",
    fontFamily: "var(--font-narrative)",
    fontSize: 17,
    lineHeight: 1.25,
    fontWeight: 520,
  },
  leverageRevealHint: {
    color: "rgba(232,218,205,0.54)",
    fontSize: 11.5,
    lineHeight: 1.35,
  },
  leverageRevealStatement: {
    position: "relative" as const,
    marginTop: 3,
    padding: "0",
    border: "none",
    borderRadius: 0,
    background: "transparent",
    overflow: "hidden",
  },
  leverageRevealEvidenceLabel: {
    display: "block",
    marginBottom: 3,
    color: "rgba(245,200,120,0.78)",
    fontSize: 10.5,
    lineHeight: 1.2,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  leverageRevealEvidence: {
    color: "rgba(255,238,210,0.88)",
    fontSize: 14,
    lineHeight: 1.48,
    fontFamily: "var(--font-narrative)",
  },
  leverageRevealCeremony: {
    marginTop: 9,
    padding: 0,
    borderRadius: 0,
    border: "none",
    background: "transparent",
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 7,
  },
  leverageRevealCeremonyStep: {
    minWidth: 0,
    padding: 0,
    borderRadius: 0,
    border: "none",
    background: "transparent",
    display: "flex",
    alignItems: "center",
    gap: 7,
  },
  leverageRevealCeremonyDivider: {
    color: "rgba(245,215,150,0.42)",
    fontSize: 11,
    lineHeight: 1.22,
  },
  leverageRevealCeremonyText: {
    minWidth: 0,
    color: "rgba(255,245,230,0.90)",
    fontSize: 11.5,
    lineHeight: 1.22,
    fontWeight: 800,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  leverageRevealActions: {
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "baseline",
    justifyContent: "flex-start",
    columnGap: 14,
    rowGap: 5,
    marginTop: 10,
  },
  actionPrimaryLine: {
    width: "fit-content",
    minHeight: 34,
    padding: "4px 0",
    border: "none",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,222,160,0.96)",
    fontSize: 13,
    fontWeight: 850,
    lineHeight: 1.25,
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left" as const,
  },
  actionPrimaryLineCompact: {
    flexBasis: "100%",
    minHeight: 28,
    padding: "2px 0 1px",
    fontSize: 14,
  },
  actionPrimaryLineDisabled: {
    color: "rgba(232,218,205,0.46)",
    opacity: 0.58,
    cursor: "default",
  },
  inlineActionDisabled: {
    opacity: 0.52,
    cursor: "default",
    borderBottomColor: "rgba(232,218,205,0.12)",
  },
  commitTextButton: {
    height: "auto",
    minHeight: 26,
    padding: "2px 0",
    border: "none",
    borderRadius: 0,
    background: "transparent",
    color: "var(--text-muted)",
    display: "inline-flex",
    alignItems: "center",
    fontSize: 12.5,
    fontWeight: 700,
    lineHeight: 1.35,
    cursor: "pointer",
    fontFamily: "inherit",
    textAlign: "left" as const,
  },
  advisorInlineAction: {
    height: "auto",
    minHeight: 26,
    padding: "2px 0",
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    borderRadius: 0,
    borderBottom: "1px solid rgba(212,168,83,0.24)",
    background: "transparent",
    color: "rgba(246,221,176,0.88)",
    display: "inline-flex",
    alignItems: "center",
    fontSize: 12.5,
    fontWeight: 800,
    lineHeight: 1.35,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  optionsList: { display: "flex", flexDirection: "column", gap: 8, marginBottom: 4 },
  optionsListCompact: { gap: 7, marginBottom: 4 },
  optionChoiceShell: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 3,
  },
  optionBtn: {
    textAlign: "left",
    padding: "8px 0 9px 10px",
    background: "transparent",
    borderTop: "none",
    borderRight: "none",
    borderBottom: "none",
    borderLeftWidth: 2,
    borderLeftStyle: "solid",
    borderLeftColor: "transparent",
    borderRadius: 0,
    color: "var(--text)",
    cursor: "pointer",
    transition: "all 160ms",
    fontFamily: "inherit",
    outline: "none",
  },
  optionBtnCompact: {
    padding: "8px 0 9px 9px",
  },
  // Picked state stays typographic so the action list does not read as
  // boxed UI stacked inside the story.
  optionBtnSelected: {
    background: "transparent",
    color: "rgba(255,238,205,0.98)",
    borderLeftColor: "rgba(245,200,120,0.58)",
  },
  optionBtnExpanded: {
    color: "rgba(255,238,205,0.98)",
  },
  optionBtnDeemphasized: {
    background: "transparent",
    boxShadow: "none",
  },
  optionBtnPicked: {
    background: "transparent",
    color: "rgba(255,238,205,0.98)",
  },
  optionConfirmPanel: {
    marginTop: -1,
    marginBottom: 3,
    paddingTop: 0,
    paddingRight: 0,
    paddingBottom: 0,
    paddingLeft: 28,
    borderTop: "none",
    background: "transparent",
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  optionConfirmPanelWriting: {
    marginBottom: 6,
    paddingTop: 0,
    gap: 4,
  },
  optionConfirmActions: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "flex-start",
    flexWrap: "wrap" as const,
    columnGap: 14,
    rowGap: 5,
  },
  optionConfirmActionsCompact: {
    display: "flex",
    gridTemplateColumns: "none",
    alignItems: "baseline",
    flexWrap: "wrap" as const,
    columnGap: 11,
    rowGap: 5,
  },
  commitPrimaryActions: {
    minWidth: 0,
    flex: "1 1 260px",
    display: "flex",
    alignItems: "baseline",
    flexWrap: "wrap" as const,
    columnGap: 13,
    rowGap: 4,
  },
  inlineCommitPrimaryActions: {
    flex: "0 1 auto",
  },
  commitSecondaryActions: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    justifyContent: "flex-end",
    flexWrap: "wrap" as const,
    columnGap: 13,
    rowGap: 4,
    marginLeft: "auto",
  },
  inlineCommitSecondaryActions: {
    marginLeft: 0,
    justifyContent: "flex-start",
  },
  commitSecondaryActionsCompact: {
    flexBasis: "100%",
    justifyContent: "flex-start",
    marginLeft: 0,
  },
  diaryAttachPreview: {
    width: "fit-content",
    maxWidth: "100%",
    minHeight: 26,
    padding: 0,
    border: "none",
    background: "transparent",
    color: "rgba(220,210,240,0.82)",
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    alignItems: "center",
    gap: 8,
    textAlign: "left" as const,
    cursor: "pointer",
    fontFamily: "inherit",
    outline: "none",
  },
  diaryAttachPreviewFilled: {
    color: "rgba(246,221,176,0.92)",
  },
  diaryAttachPreviewEmpty: {
    width: "fit-content",
    display: "inline-flex",
    gridTemplateColumns: "none",
    alignItems: "baseline",
    gap: 0,
  },
  diaryAttachEmptyCopy: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "baseline",
    columnGap: 6,
    rowGap: 2,
    flexWrap: "wrap" as const,
  },
  diaryAttachTag: {
    color: "rgba(222,202,255,0.94)",
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
    whiteSpace: "nowrap" as const,
  },
  diaryAttachText: {
    minWidth: 0,
    color: "rgba(232,222,245,0.82)",
    fontSize: 12.5,
    lineHeight: 1.4,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  diaryAttachEdit: {
    color: "rgba(244,214,164,0.94)",
    fontSize: 11,
    fontWeight: 700,
    whiteSpace: "nowrap" as const,
  },
  diaryAttachEmptyText: {
    color: "rgba(222,202,255,0.86)",
    fontSize: 12.5,
    fontWeight: 750,
    lineHeight: 1.35,
    whiteSpace: "nowrap" as const,
  },
  diaryAttachEmptyHint: {
    color: "rgba(232,222,245,0.44)",
    fontSize: 11.5,
    lineHeight: 1.35,
    fontWeight: 620,
  },
  // Reflective banner shown right under the options after the user
  // picks one — bridges the 5-8s LLM wait with a "yes, we got it"
  // visual signal.
  pickedReflect: {
    marginTop: 12,
    padding: "9px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    color: "var(--accent)",
    letterSpacing: 0,
    fontStyle: "italic" as const,
  },
  pickedReflectIcon: {
    fontSize: 14,
    fontWeight: 600,
    fontStyle: "normal" as const,
  },
  // Memory-handle echo on the picked-reflect banner. Visually
  // distinct from the "submitting…" copy via heavier weight + the
  // accent color. Anchors the moment as "this is what I picked."
  pickedReflectHandle: {
    fontWeight: 600,
    color: "var(--accent)",
    fontStyle: "normal" as const,
    letterSpacing: 0,
    marginLeft: 2,
  },
  resolvingPanel: {
    marginTop: 8,
    padding: "2px 0 4px",
    borderRadius: 0,
    border: "none",
    background: "transparent",
    boxShadow: "none",
    display: "grid",
    gap: 2,
  },
  resolvingTitle: {
    flexShrink: 0,
    color: "rgba(255,232,190,0.60)",
    fontSize: 10.5,
    lineHeight: 1.15,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  resolvingLine: {
    minWidth: 0,
    display: "flex",
    alignItems: "center",
    columnGap: 8,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  resolvingReceiptMeta: {
    flexShrink: 0,
    color: "rgba(246,221,176,0.50)",
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  resolvingMoveText: {
    minWidth: 0,
    flex: "1 1 180px",
    color: "rgba(255,245,230,0.80)",
    fontFamily: "var(--font-narrative)",
    fontSize: 13,
    lineHeight: 1.35,
    display: "-webkit-box",
    WebkitLineClamp: 1,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
  },
  resolvingInlineStatus: {
    minWidth: 0,
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    flex: "0 1 auto",
    color: "rgba(246,221,176,0.64)",
  },
  resolvingStatus: {
    flexShrink: 0,
    color: "rgba(232,218,205,0.50)",
    fontSize: 11,
    lineHeight: 1.25,
    fontWeight: 700,
    fontStyle: "italic" as const,
  },
  resolvingProgressText: {
    color: "rgba(246,221,176,0.66)",
    fontSize: 11.5,
    lineHeight: 1.25,
    fontWeight: 760,
  },
  resolvingDots: {
    display: "inline-flex",
    alignItems: "center",
    gap: 3,
  },
  resolvingDot: {
    width: 3.5,
    height: 3.5,
    borderRadius: "50%",
    background: "rgba(245,210,140,0.70)",
    display: "inline-block",
  },
  resolvingPrivateLine: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    gap: 6,
    color: "rgba(228,214,255,0.66)",
  },
  resolvingPrivateLabel: {
    flexShrink: 0,
    color: "rgba(222,202,255,0.66)",
    fontSize: 10.5,
    fontWeight: 700,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  resolvingPrivateCopy: {
    minWidth: 0,
    color: "rgba(232,222,245,0.64)",
    fontSize: 11.5,
    lineHeight: 1.35,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  optionLabel: {
    fontSize: 14.5,
    fontWeight: 500,
    lineHeight: 1.34,
    display: "flex",
    alignItems: "baseline",
    gap: 8,
    flexWrap: "wrap" as const,
  },
  optionLabelCompact: {
    fontSize: 14,
    lineHeight: 1.3,
  },
  optionTagChip: {
    fontSize: 11,
    fontWeight: 850,
    padding: 0,
    letterSpacing: 0,
    flexShrink: 0,
    fontFamily: "var(--font-narrative)",
  },
  // Number-key shortcut hint chip on the leading edge of each option.
  // Shares look-and-feel with global `kbd` but is a touch larger so
  // it's clearly a hit target hint, not just a label.
  optionKbd: {
    flexShrink: 0,
    minWidth: 16,
    height: "auto",
    fontSize: 11.5,
    color: "rgba(212,168,83,0.70)",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "var(--font-ui)",
    fontWeight: 850,
  },
  optionHintInline: {
    color: "rgba(232,218,205,0.54)",
    fontSize: 12,
    lineHeight: 1.3,
    fontWeight: 560,
    display: "inline-flex",
    alignItems: "baseline",
    gap: 6,
  },
  optionHintInlineCompact: {
    flexBasis: "100%",
    paddingLeft: 0,
    fontSize: 11.8,
  },
  noOptions: { fontSize: 13, color: "var(--text-faint)", fontStyle: "italic" },

  freeInputBox: {
    background: "transparent",
    border: "none",
    borderRadius: 0,
    marginTop: 5,
    padding: "2px 0 0",
  },
  freeTextarea: {
    width: "100%",
    background: "transparent",
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 0,
    fontFamily: "var(--font-narrative)",
    fontSize: 15,
    lineHeight: 1.6,
    color: "var(--text)",
    resize: "none" as const,
    outline: "none",
    minHeight: 42,
    padding: "3px 0 7px",
  },
  freeCommitDock: {
    marginTop: 6,
    paddingTop: 0,
    borderTop: "none",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr)",
    alignItems: "start",
    rowGap: 8,
  },
  freeCommitDockCompact: {
    gridTemplateColumns: "minmax(0, 1fr)",
    alignItems: "start",
  },
  freeCommitHint: {
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.35,
    fontWeight: 700,
  },
  freeEmptyHint: {
    color: "rgba(232,218,205,0.48)",
    fontSize: 12.5,
    lineHeight: 1.35,
    fontWeight: 700,
  },
  freeInputActions: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "flex-start",
    columnGap: 14,
    rowGap: 5,
    flexWrap: "wrap" as const,
  },
  alternateActionRow: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 20,
    rowGap: 4,
    flexWrap: "wrap" as const,
    paddingTop: 4,
  },
  alternateActionButton: {
    display: "inline-flex",
    alignItems: "center",
    columnGap: 7,
    rowGap: 2,
    flexWrap: "wrap" as const,
    minWidth: 0,
    minHeight: 26,
    background: "none",
    border: "none",
    color: "rgba(246,221,176,0.82)",
    padding: 0,
    cursor: "pointer",
    textAlign: "left",
    outline: "none",
    fontFamily: "inherit",
  },
  alternateActionLabel: {
    color: "rgba(246,221,176,0.76)",
    fontSize: 12.5,
    lineHeight: 1.25,
    fontWeight: 780,
  },
  alternateActionHint: {
    color: "rgba(232,218,205,0.44)",
    fontSize: 11.5,
    lineHeight: 1.35,
  },

  diaryLaneEdit: {
    color: "rgba(180,150,230,0.90)",
    fontSize: 11,
    fontWeight: 700,
  },
  diaryBox: {
    marginTop: 3,
    padding: "1px 0 0",
    background: "transparent",
    borderLeft: "none",
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  diaryHeader: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 10,
    rowGap: 3,
    flexWrap: "wrap" as const,
  },
  diaryKicker: {
    color: "rgba(222,202,255,0.82)",
    fontSize: 11.5,
    lineHeight: 1.2,
    fontWeight: 760,
  },
  diaryMeta: {
    color: "rgba(226,214,246,0.58)",
    fontSize: 11.2,
    lineHeight: 1.25,
    fontWeight: 620,
  },
  diaryTextarea: {
    width: "100%",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(222,202,255,0.22)",
    borderRadius: 0,
    fontSize: 13.5,
    lineHeight: 1.45,
    color: "rgba(238,228,252,0.97)",
    padding: "2px 0 6px",
    resize: "none" as const,
    outline: "none",
    fontFamily: "var(--font-narrative)",
    minHeight: 42,
  },
  diaryActions: {
    display: "flex",
    alignItems: "baseline",
    gap: 10,
    flexWrap: "wrap" as const,
  },
  diaryTextButton: {
    height: "auto",
    minHeight: 26,
    padding: "2px 0",
    border: "none",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(226,214,246,0.76)",
    display: "inline-flex",
    alignItems: "center",
    fontSize: 12,
    fontWeight: 750,
    lineHeight: 1.35,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  busyShim: {
    marginTop: 24,
    paddingTop: 20,
    borderTop: "1px solid rgba(255,255,255,0.065)",
    color: "var(--text-faint)",
    fontSize: 13,
    fontStyle: "italic",
  },

  errorInline: {
    margin: "8px 0",
    padding: "12px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    fontSize: 13,
    color: "rgba(255,226,214,0.94)",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "start",
    gap: 12,
    boxShadow: "none",
  },
  errorInlineCompact: {
    gridTemplateColumns: "minmax(0, 1fr)",
  },
  errorInlineCopy: {
    minWidth: 0,
    display: "grid",
    gap: 5,
  },
  errorInlineKicker: {
    color: "rgba(255,205,190,0.86)",
    fontSize: 10.5,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  errorInlineTitle: {
    color: "rgba(255,245,230,0.96)",
    fontSize: 14,
    lineHeight: 1.25,
  },
  errorInlineText: { minWidth: 0, color: "rgba(255,226,214,0.82)", lineHeight: 1.4 },
  errorInlineSignal: {
    minWidth: 0,
    color: "rgba(255,226,214,0.66)",
    fontSize: 11.5,
    lineHeight: 1.35,
  },
  errorInlineSignalLabel: {
    marginRight: 6,
    color: "rgba(255,205,190,0.78)",
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  errorInlineChips: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap" as const,
    marginTop: 2,
  },
  errorInlineChip: {
    maxWidth: "100%",
    padding: "0 0 2px",
    borderRadius: 0,
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
    background: "transparent",
    color: "rgba(255,245,230,0.82)",
    fontSize: 11,
    lineHeight: 1.2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  errorInlineRetry: {
    flexShrink: 0,
    fontSize: 12,
    padding: "6px 0 5px",
    minHeight: 32,
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    color: "rgba(255,226,178,0.96)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 800,
  },

  approachingFinaleBanner: {
    marginTop: 12,
    marginBottom: 20,
    padding: "9px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    fontSize: 13,
    color: "var(--accent)",
    fontStyle: "italic",
    textAlign: "center",
    letterSpacing: 0,
  },

  endingSection: { marginTop: 40 },
  endingDivider: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "0 0 28px",
    position: "relative",
  },
  endingDividerLabel: {
    background: "transparent",
    padding: 0,
    fontSize: 12.5,
    color: "var(--text-muted)",
    letterSpacing: 0,
    fontWeight: 650,
    textTransform: "none" as const,
    position: "relative",
    zIndex: 1,
  },
  endingCard: {
    background: "transparent",
    border: "none",
    borderRadius: 0,
    boxShadow: "none",
    overflow: "visible",
  },
  endingHero: {
    width: "100%",
    height: 210,
    backgroundSize: "cover",
    backgroundPosition: "center",
    marginBottom: -1,
    position: "relative",
    overflow: "hidden",
  },
  endingSplashOverlay: {
    position: "absolute",
    inset: 0,
    backgroundSize: "cover",
    backgroundPosition: "center",
    mixBlendMode: "screen",
    pointerEvents: "none",
  },
  endingCardInner: { padding: "22px 0 28px" },
  endingLabelChip: {
    display: "inline-block",
    padding: "0 0 4px",
    background: "transparent",
    borderRadius: 0,
    borderBottom: "1px solid rgba(212,168,83,0.30)",
    fontSize: 13,
    fontWeight: 650,
    letterSpacing: 0,
    marginBottom: 16,
  },
  endingSubtitle: {
    fontFamily: "var(--font-narrative)",
    fontSize: 26,
    lineHeight: 1.35,
    fontWeight: 400,
    margin: "0 0 24px",
    color: "var(--text)",
  },
  endingPassage: {
    fontFamily: "var(--font-narrative)",
    fontSize: 16,
    lineHeight: 1.85,
    color: "var(--text)",
    whiteSpace: "pre-wrap",
    paddingBottom: 0,
    borderBottom: "none",
    marginBottom: 28,
  },
  // Highlight reel below ending passage — chronological pivotal moments
  highlightReel: {
    marginTop: 28,
    marginBottom: 28,
    paddingTop: 14,
    paddingBottom: 0,
    borderTop: "1px solid rgba(255,255,255,0.08)",
    borderBottom: "none",
  },
  highlightReelLabel: {
    fontSize: 12.5,
    color: "rgba(245,200,120,0.92)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 650,
    marginBottom: 16,
  },
  highlightList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 0,
  },
  highlightCard: {
    padding: "11px 0 12px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.055)",
    borderRadius: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  highlightCardUserMarked: {
    boxShadow: "none",
  },
  highlightUserMark: {
    color: "var(--accent)",
    fontSize: 13,
    lineHeight: 1,
  },
  highlightHeader: {
    display: "flex",
    alignItems: "baseline",
    gap: 8,
  },
  highlightIndex: {
    fontSize: 12,
    color: "rgba(245,200,120,0.85)",
    fontWeight: 700,
    minWidth: 18,
    fontFamily: "var(--font-narrative)",
  },
  highlightHeadline: {
    fontFamily: "var(--font-narrative)",
    fontSize: 16,
    fontWeight: 500,
    color: "rgba(255,235,210,0.96)",
    lineHeight: 1.35,
  },
  highlightBody: {
    fontSize: 13.5,
    lineHeight: 1.7,
    color: "var(--text)",
    paddingLeft: 26,
    fontFamily: "var(--font-narrative)",
  },
  highlightWhy: {
    fontSize: 12,
    color: "var(--text-muted)",
    lineHeight: 1.55,
    paddingLeft: 28,
    fontStyle: "italic" as const,
  },

  // Branches section — alternate paths the player didn't take
  branchesSection: {
    marginTop: 28,
    marginBottom: 28,
    paddingTop: 14,
    paddingBottom: 0,
    borderTop: "1px solid rgba(255,255,255,0.08)",
    borderBottom: "none",
  },
  branchesLabel: {
    fontSize: 12.5,
    color: "rgba(180,150,230,0.92)",
    letterSpacing: 0,
    textTransform: "none" as const,
    fontWeight: 650,
    marginBottom: 8,
  },
  branchesHint: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    lineHeight: 1.55,
    margin: "0 0 16px",
    fontStyle: "italic" as const,
  },
  branchList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 0,
  },
  branchCard: {
    position: "relative" as const,
    padding: "12px 0 14px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.055)",
    borderRadius: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  branchTurnBadge: {
    position: "static" as const,
    alignSelf: "flex-start",
    fontSize: 10,
    color: "rgba(180,150,230,0.9)",
    background: "transparent",
    border: "none",
    padding: 0,
    borderRadius: 0,
    letterSpacing: 0,
    fontWeight: 600,
  },
  branchPaths: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  branchChosen: {
    fontSize: 13,
    lineHeight: 1.55,
    color: "var(--text-muted)",
    display: "flex",
    flexDirection: "column" as const,
  },
  branchAlternate: {
    fontSize: 13,
    lineHeight: 1.55,
    color: "var(--text)",
    display: "flex",
    flexDirection: "column" as const,
  },
  branchPathTag: {
    fontSize: 10.5,
    color: "var(--text-faint)",
    letterSpacing: 0,
    textTransform: "none" as const,
    marginBottom: 2,
  },
  branchPathText: {
    fontFamily: "var(--font-narrative)",
    fontSize: 14,
  },
  branchArrow: {
    fontSize: 10.5,
    color: "rgba(180,150,230,0.8)",
    letterSpacing: 0,
    textAlign: "center" as const,
    padding: "2px 0",
  },
  branchOutcome: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    paddingTop: 2,
    borderTop: "none",
  },
  branchEndingChip: {
    fontFamily: "var(--font-narrative)",
    fontSize: 13,
    fontWeight: 600,
    padding: 0,
    borderRadius: 0,
    flexShrink: 0,
    letterSpacing: 0,
  },
  branchTierVictory: {
    background: "transparent",
    color: "rgba(245,210,140,0.96)",
    border: "none",
  },
  branchTierCompromised: {
    background: "transparent",
    color: "var(--text)",
    border: "none",
  },
  branchTierCollapsed: {
    background: "transparent",
    color: "rgba(245,180,170,0.96)",
    border: "none",
  },
  branchRationale: {
    fontSize: 12,
    color: "var(--text-muted)",
    lineHeight: 1.6,
    fontStyle: "italic" as const,
    flex: 1,
  },

  endingActions: { display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 12 },
  endingActionsRow: {
    display: "flex",
    alignItems: "center",
    gap: 24,
    flexWrap: "wrap" as const,
  },
  endingPrimaryAction: {
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.42)",
    borderRadius: 0,
    color: "rgba(255,226,178,0.96)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 850,
    padding: "5px 0",
  },
  endingTextAction: {
    background: "transparent",
    border: "none",
    borderRadius: 0,
    color: "var(--text)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 700,
    padding: "5px 0",
    borderBottom: "1px solid rgba(245,245,245,0.18)",
  },
  endingTextActionMuted: {
    background: "transparent",
    border: "none",
    borderRadius: 0,
    color: "var(--text-muted)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 650,
    padding: "5px 0",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
  },
  endingShareHint: {
    fontSize: 12.5,
    color: "var(--text-muted)",
    margin: 0,
    lineHeight: 1.5,
  },

  fab: {
    position: "fixed",
    bottom: 24,
    right: 24,
    width: "auto",
    height: 34,
    background: "transparent",
    color: "rgba(255,245,230,0.84)",
    border: "none",
    borderRadius: 0,
    padding: 0,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
    cursor: "pointer",
    boxShadow: "none",
    zIndex: 20,
    textAlign: "center" as const,
    backdropFilter: "none",
    fontFamily: "inherit",
  },
  fabCompact: {
    right: 12,
    bottom: 14,
    left: "auto",
    width: "auto",
    height: 34,
    padding: 0,
  },
  fabLabel: {
    color: "rgba(255,226,178,0.92)",
    fontSize: 13,
    lineHeight: 1.2,
    fontWeight: 800,
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    paddingBottom: 3,
    whiteSpace: "nowrap" as const,
  },
  fabAvatarImg: {
    width: 32,
    height: 32,
    borderRadius: "50%",
    objectFit: "cover",
    border: "1px solid rgba(212,168,83,0.28)",
    boxShadow: "none",
    flexShrink: 0,
  },
  advisorBackdrop: {
    position: "fixed",
    inset: 0,
    background:
      "linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.08) 58%, rgba(0,0,0,0.30) 100%)",
    zIndex: 30,
  },
  advisorBackdropCompact: {
    background: "linear-gradient(180deg, rgba(0,0,0,0.08) 0%, rgba(0,0,0,0.42) 100%)",
  },
  advisorPanel: {
    position: "fixed",
    top: 0,
    right: 0,
    bottom: 0,
    width: "min(380px, 92vw)",
    paddingLeft: 0,
    boxSizing: "border-box",
    background:
      "linear-gradient(90deg, rgba(10,9,9,0.34) 0%, rgba(10,9,9,0.84) 22%, rgba(10,9,9,0.97) 100%)",
    backdropFilter: "none",
    WebkitBackdropFilter: "none",
    borderLeft: "none",
    display: "flex",
    flexDirection: "column",
    zIndex: 31,
    boxShadow: "-30px 0 72px rgba(0,0,0,0.26)",
    overflow: "hidden",
  },
  advisorPanelCompact: {
    top: "auto",
    left: 0,
    right: 0,
    bottom: 0,
    width: "auto",
    maxHeight: "44dvh",
    paddingLeft: 0,
    borderLeft: "none",
    borderTop: "none",
    background: "linear-gradient(180deg, rgba(10,9,9,0.995) 0%, rgba(8,7,7,0.995) 100%)",
    boxShadow: "0 -32px 72px rgba(0,0,0,0.48)",
  },
  advisorHeader: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "20px 20px 5px 20px",
    borderBottom: "none",
  },
  advisorHeaderCompact: {
    padding: "10px 16px 4px",
    borderBottom: "none",
    gap: 8,
  },
  advisorHeaderAvatar: {
    width: 30,
    height: 30,
    borderRadius: "50%",
    objectFit: "cover",
    border: "1px solid rgba(212,168,83,0.24)",
    flexShrink: 0,
    opacity: 0.86,
  },
  advisorHeaderAvatarCompact: {
    width: 26,
    height: 26,
    border: "none",
    opacity: 0.78,
  },
  advisorTitle: { fontFamily: "var(--font-narrative)", fontSize: 14.5, color: "var(--text)" },
  advisorPersona: {
    fontSize: 11,
    color: "rgba(232,218,205,0.48)",
    lineHeight: 1.35,
    marginTop: 3,
    maxWidth: 268,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical" as const,
    overflow: "hidden",
  },
  advisorPersonaCompact: {
    display: "none",
  },
  advisorClose: {
    background: "none",
    border: "none",
    color: "var(--text-muted)",
    fontSize: 17,
    cursor: "pointer",
    padding: 4,
  },
  advisorContextLine: {
    margin: "4px 22px 0 42px",
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 2,
    flexWrap: "wrap" as const,
  },
  advisorContextLineCompact: {
    margin: "2px 16px 0",
    display: "grid",
    gridTemplateColumns: "1fr",
    rowGap: 3,
  },
  advisorContextKicker: {
    flexShrink: 0,
    color: "rgba(245,210,140,0.78)",
    fontSize: 10.5,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  advisorContextText: {
    minWidth: 0,
    flex: "1 1 0",
    color: "rgba(245,235,224,0.58)",
    fontSize: 11.5,
    lineHeight: 1.35,
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  advisorContextTextCompact: {
    flex: "unset",
    whiteSpace: "normal" as const,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical" as const,
    color: "rgba(245,235,224,0.66)",
    lineHeight: 1.42,
  },
  advisorMessages: {
    flex: 1,
    overflowY: "auto",
    paddingTop: 18,
    paddingRight: 22,
    paddingBottom: 20,
    paddingLeft: 42,
  },
  advisorMessagesCompact: {
    paddingTop: 5,
    paddingRight: 16,
    paddingBottom: 12,
    paddingLeft: 16,
  },
  advisorMessagesEmpty: {
    flex: "0 0 auto",
    paddingBottom: 14,
  },
  advisorRowPlayer: {
    display: "flex",
    justifyContent: "flex-start",
    marginBottom: 12,
  },
  advisorRowAdvisor: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-start",
    marginBottom: 12,
    gap: 4,
  },
  advisorTranscriptLine: {
    width: "100%",
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    columnGap: 8,
    rowGap: 4,
    flexWrap: "wrap" as const,
  },
  advisorTranscriptLineOracle: {
    color: "rgba(255,235,200,0.96)",
  },
  advisorTranscriptSpeaker: {
    flexShrink: 0,
    color: "rgba(232,218,205,0.48)",
    fontSize: 10,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  advisorTranscriptSpeakerPlayer: {
    color: "rgba(212,168,83,0.72)",
  },
  advisorBubblePlayer: {
    background: "transparent",
    color: "rgba(255,245,230,0.94)",
    padding: "0",
    borderRadius: 0,
    fontSize: 14,
    lineHeight: 1.55,
    maxWidth: "100%",
    border: "none",
    textAlign: "left" as const,
    flex: "1 1 220px",
  },
  advisorBubbleAdvisor: {
    background: "transparent",
    color: "var(--text)",
    padding: "0",
    borderRadius: 0,
    fontSize: 14,
    lineHeight: 1.6,
    maxWidth: "100%",
    border: "none",
    flex: "1 1 220px",
  },
  advisorBubbleOracle: {
    background: "transparent",
    color: "rgba(255,235,200,0.96)",
    padding: 0,
    borderRadius: 0,
    fontSize: 14,
    lineHeight: 1.6,
    maxWidth: "100%",
    border: "none",
    boxShadow: "none",
    flex: "1 1 220px",
  },
  oracleBadge: {
    fontSize: 10.5,
    color: "rgba(245,210,140,0.92)",
    letterSpacing: 0,
    fontWeight: 720,
    marginBottom: 0,
    background: "transparent",
    border: "none",
    padding: 0,
    borderRadius: 0,
    alignSelf: "flex-start" as const,
  },
  advisorTyping: { fontSize: 12, color: "var(--text-faint)", fontStyle: "italic", padding: "6px 14px" },
  typingRow: { display: "flex", justifyContent: "flex-start", marginBottom: 12 },
  typingBubble: {
    background: "transparent",
    border: "none",
    borderRadius: 0,
    padding: "8px 0",
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
  },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "var(--text-faint)",
    display: "inline-block",
  },
  advisorError: {
    margin: "0 22px 8px 20px",
    padding: "7px 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    fontSize: 12,
    color: "var(--warn)",
  },
  advisorInput: {
    paddingTop: 10,
    paddingRight: 22,
    paddingBottom: 16,
    paddingLeft: 42,
    borderTop: "none",
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
    alignItems: "stretch",
  },
  advisorInputEmpty: {
    paddingTop: 6,
    paddingBottom: 20,
  },
  advisorInputCompact: {
    paddingTop: 6,
    paddingRight: 16,
    paddingBottom: "max(14px, env(safe-area-inset-bottom))",
    paddingLeft: 16,
    borderTop: "none",
    gap: 8,
  },
  advisorSuggestionBlock: {
    display: "flex",
    alignItems: "baseline",
    gap: 9,
    minWidth: 0,
  },
  advisorSuggestionBlockEmpty: {
    display: "grid",
    gap: 9,
    alignItems: "stretch",
  },
  advisorSuggestionLabel: {
    color: "rgba(232,218,205,0.48)",
    fontSize: 11,
    fontWeight: 650,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  advisorSuggestionRow: {
    minWidth: 0,
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "5px 12px",
  },
  advisorSuggestionRowEmpty: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 9,
    borderTop: "none",
  },
  advisorSuggestionChip: {
    width: "auto",
    padding: 0,
    borderRadius: 0,
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    borderBottom: "none",
    background: "transparent",
    color: "rgba(255,235,205,0.74)",
    fontSize: 11.5,
    lineHeight: 1.35,
    fontFamily: "inherit",
    textAlign: "left" as const,
    cursor: "pointer",
  },
  advisorSuggestionChipEmpty: {
    width: "100%",
    padding: "6px 0 8px",
    borderBottom: "none",
    color: "rgba(255,238,214,0.82)",
    fontFamily: "var(--font-narrative)",
    fontSize: 13,
    lineHeight: 1.42,
  },
  advisorComposer: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 10,
    alignItems: "stretch",
  },
  advisorComposerEmpty: {
    gap: 8,
  },
  advisorComposerOracleArmed: {
    flexDirection: "column" as const,
    alignItems: "stretch",
  },
  advisorComposerCompact: {
    flexDirection: "column" as const,
    alignItems: "stretch",
  },
  advisorTextarea: {
    flex: 1,
    background: "transparent",
    borderTop: "none",
    borderRight: "none",
    borderLeft: "none",
    borderBottom: "1px solid rgba(255,255,255,0.075)",
    borderRadius: 0,
    fontSize: 14,
    lineHeight: 1.5,
    color: "var(--text)",
    padding: "4px 0 9px",
    resize: "none",
    outline: "none",
    fontFamily: "inherit",
  },
  advisorBtnRow: {
    display: "flex",
    flexDirection: "row" as const,
    gap: 22,
    alignItems: "center",
    justifyContent: "flex-start",
  },
  advisorBtnRowCompact: {
    flexDirection: "row" as const,
    justifyContent: "space-between",
  },
  advisorActionBtnCompact: {
    flex: "0 0 auto",
    minWidth: 0,
    justifyContent: "flex-start",
  },
  advisorSendBtn: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "8px 0 4px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    color: "rgba(255,226,178,0.96)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 13,
    fontWeight: 850,
    lineHeight: 1.2,
    whiteSpace: "nowrap" as const,
  },
  advisorActionDisabled: {
    opacity: 0.42,
    cursor: "default",
    borderBottomColor: "transparent",
  },
  oracleBtn: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    fontSize: 12.5,
    padding: "8px 0 4px",
    background: "transparent",
    color: "rgba(255,235,200,0.72)",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 0,
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 700,
    whiteSpace: "nowrap" as const,
    transition: "filter 0.15s",
  },
  oracleInlineLine: {
    width: "100%",
    padding: "4px 0 0",
    color: "rgba(255,239,214,0.96)",
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    columnGap: 14,
    rowGap: 6,
    flexWrap: "wrap" as const,
  },
  oracleInlineCopy: {
    minWidth: 0,
    flex: "1 1 220px",
    color: "rgba(255,244,226,0.72)",
    fontSize: 11.5,
    lineHeight: 1.35,
    fontWeight: 600,
  },
  oracleInlineActions: {
    marginTop: 0,
    display: "flex",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap" as const,
  },
  oracleInlineCancelBtn: {
    border: "none",
    background: "transparent",
    color: "var(--text-muted)",
    padding: "7px 0",
    fontSize: 12,
    fontFamily: "inherit",
    cursor: "pointer",
  },
}
