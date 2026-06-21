import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { motion } from "motion/react"
import type {
  NarrativeAdvisorMessage,
  NarrativeStoryHistoryResponse,
  NarrativeStoryMessage,
} from "../../../api/contracts"
import type { FrontendApiClient } from "../../../api/client"
import { useApi } from "../../../app/api-context"
import { useT } from "../../../shared/lib/i18n"
import {
  fadeTransition,
  fadeVariants,
  itemTransition,
  slideInRightTransition,
  slideInRightVariants,
  transitions,
} from "../../../shared/lib/motion-presets"
import { ppStyles } from "../play-styles"
import type { ActionCommitmentSummary, LeverageCardView } from "../play-types"
import { useCompactLayout } from "../hooks/use-compact-layout"

export type AdvisorSidechatApiClient = Pick<
  FrontendApiClient,
  "getNarrativeAdvisorHistory" | "askNarrativeAdvisor"
>

export function buildAdvisorSuggestions({
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
  const openLeverage = leverageCards.find((card) => !card.used)
  const fallbackName = language === "zh" ? "对方" : "the other side"
  const castById = new Map(cast.map((member) => [member.character_id, member.display_name]))
  const playerRole = story.session.player_role
  const isLikelyPlayerCast = (member: NarrativeStoryHistoryResponse["template"]["cast"][number]): boolean => {
    const relation = member.relation_to_protagonist.toLowerCase()
    const roleText = `${playerRole?.label ?? ""} ${playerRole?.public_persona ?? ""}`.toLowerCase()
    if (relation.includes("you are") || relation.includes("主角") || relation.includes("玩家")) return true
    return Boolean(roleText && `${member.role} ${member.relation_to_protagonist}`.toLowerCase().includes(roleText))
  }
  const pulseTarget = (lastNarrator?.npc_pulse ?? [])
    .map((pulse) => {
      const member = cast.find((item) => item.character_id === pulse.npc_id)
      return member && !isLikelyPlayerCast(member) ? castById.get(pulse.npc_id) : null
    })
    .find((name): name is string => Boolean(name))
  const focalNpc =
    pulseTarget ??
    openLeverage?.target_name ??
    cast.find((member) => !isLikelyPlayerCast(member))?.display_name ??
    cast[1]?.display_name ??
    cast[0]?.display_name ??
    fallbackName
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

export function AdvisorFab({
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

export function AdvisorSidechat({
  sessionId,
  persona,
  avatarUrl,
  turnsRemaining,
  isComplete,
  isCommitmentActive,
  commitmentSummary,
  suggestions,
  apiClient,
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
  apiClient?: AdvisorSidechatApiClient
  onClose: () => void
  onOracleConsumed: (newBudget: number) => void
}) {
  const defaultApi = useApi()
  const api = apiClient ?? defaultApi
  const t = useT()
  const [messages, setMessages] = useState<NarrativeAdvisorMessage[]>([])
  const [oracleOrds, setOracleOrds] = useState<Set<number>>(new Set())
  const [draft, setDraft] = useState("")
  const [draftSuggestion, setDraftSuggestion] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingOracleQuestion, setPendingOracleQuestion] = useState<string | null>(null)
  const [draftFocusToken, setDraftFocusToken] = useState(0)
  const panelRef = useRef<HTMLElement | null>(null)
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  const latestMessageRef = useRef<HTMLDivElement | null>(null)
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
      .catch(() => {
        if (cancelled) return
        setError(t("play.advisor_history_failed"))
      })
    return () => {
      cancelled = true
    }
  }, [api, sessionId])

  useEffect(() => {
    const el = scrollerRef.current
    const latest = latestMessageRef.current
    if (!el || !latest) return
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const top = Math.max(0, latest.offsetTop - el.offsetTop)
    const frame = window.requestAnimationFrame(() => {
      el.scrollTo({ top, behavior: prefersReducedMotion ? "auto" : "smooth" })
    })
    return () => window.cancelAnimationFrame(frame)
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
    setDraftSuggestion(null)
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
    } catch {
      setError(t(oracle ? "play.oracle_ask_failed" : "play.advisor_ask_failed"))
      setDraft(question)
      setDraftSuggestion(null)
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
    setDraftSuggestion(suggestion)
    setDraftFocusToken((token) => token + 1)
  }

  const renderSuggestionBlock = (variant: "empty" | "composer") =>
    visibleSuggestions.length > 0 ? (
      <div
        style={{
          ...ppStyles.advisorSuggestionBlock,
          ...(variant === "empty" ? ppStyles.advisorSuggestionBlockEmpty : null),
          ...(variant === "composer" && compactAdvisor ? ppStyles.advisorSuggestionBlockComposerCompact : null),
        }}
      >
        <span style={ppStyles.advisorSuggestionLabel}>
          {t("play.advisor_suggestions_label")}
        </span>
        <span
          style={ppStyles.advisorSuggestionInstruction}
          data-play-advisor-suggestion-instruction="true"
        >
          {t("play.advisor_suggestions_instruction")}
        </span>
        <div
          style={{
            ...ppStyles.advisorSuggestionRow,
            ...(variant === "empty" ? ppStyles.advisorSuggestionRowEmpty : null),
            ...(variant === "composer" && compactAdvisor ? ppStyles.advisorSuggestionRowComposerCompact : null),
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
                ...(variant === "composer" && compactAdvisor ? ppStyles.advisorSuggestionChipComposerCompact : null),
              }}
              onClick={() => applySuggestion(suggestion)}
              disabled={busy || !!pendingOracleQuestion}
            >
              <span style={ppStyles.advisorSuggestionText}>{suggestion}</span>
              <span aria-hidden="true" style={ppStyles.advisorSuggestionArrow}>
                {t("play.advisor_suggestion_insert")}
              </span>
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
          ...(compactAdvisor && (messages.length > 0 || busy) ? ppStyles.advisorPanelCompactReading : null),
        }}
        variants={advisorPanelVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={compactAdvisor ? transitions.snap : slideInRightTransition}
        onAnimationComplete={() => {
          if (!busy && !pendingOracleQuestion) {
            focusAdvisorTextarea()
          }
        }}
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
            hasAdvisorDraft ? null : (
              <>
                <div
                  style={ppStyles.advisorEmptyPrimer}
                  data-play-advisor-empty-primer="true"
                >
                  <strong style={ppStyles.advisorEmptyPrimerTitle}>
                    {t("play.advisor_empty_primer_title")}
                  </strong>
                  <span style={ppStyles.advisorEmptyPrimerBody}>
                    {t("play.advisor_empty_primer_body")}
                  </span>
                </div>
                {renderSuggestionBlock("empty")}
              </>
            )
          ) : (
            messages.map((m, index) => {
              const isOracle = m.role === "advisor" && oracleOrds.has(m.ord)
              const isLatestMessage = index === messages.length - 1
              return (
                <motion.div
                  ref={isLatestMessage ? latestMessageRef : undefined}
                  key={`${m.role}-${m.ord}`}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={itemTransition}
                  style={m.role === "player" ? ppStyles.advisorRowPlayer : ppStyles.advisorRowAdvisor}
                >
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

        {error ? (
          <div
            style={ppStyles.advisorError}
            data-play-advisor-error="true"
            role="status"
            aria-live="polite"
          >
            {error}
          </div>
        ) : null}

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
              onChange={(e) => {
                setDraft(e.target.value)
                if (!e.target.value.trim()) {
                  setDraftSuggestion(null)
                }
              }}
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
                {isCommitmentActive ? (
                  <span style={ppStyles.oracleInlineKeepMove}>
                    {t("play.oracle_inline_keep_move")}
                  </span>
                ) : null}
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
                {hasAdvisorDraft && draftSuggestion ? (
                  <span
                    style={ppStyles.advisorDraftHint}
                    data-play-advisor-draft-hint="true"
                  >
                    {t("play.advisor_draft_hint")}
                  </span>
                ) : null}
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
