import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react"
import { EndingSummary } from "../../entities/play/ui/ending-summary"
import { StateBarList } from "../../entities/play/ui/state-bar-list"
import { SuggestedActions } from "../../entities/play/ui/suggested-actions"
import { TranscriptView } from "../../entities/play/ui/transcript-view"
import { usePlaySession } from "../../features/play/session/model/use-play-session"
import type { PlayEnding, StoryLanguage } from "../../index"
import { formatPlayLedgerLabel, formatSupportSurfaceDisabledReason } from "../../shared/lib/play-formatting"
import { formatStoryLanguageLabel } from "../../shared/lib/story-language"
import { isDistinctSupportCopy, pickHealthyText } from "../../shared/lib/story-content-quality"
import { getLanguageMismatchCopy } from "../../shared/lib/story-surface-copy"
import { prefersReducedMotionNow } from "../../shared/lib/motion"
import { EditorialMedia } from "../../shared/ui/editorial-media"
import { StudioIcon } from "../../shared/ui/studio-icon"
import { useReadingSection } from "../../shared/lib/use-reading-section"
import { useCompactDesktop } from "../../shared/lib/use-compact-desktop"
import { PlayDomainSidebar } from "../../widgets/chrome/play-domain-sidebar"
import { StudioFooter } from "../../widgets/chrome/studio-footer"
import { progressWidth } from "../../shared/lib/formatting"

type PlayNavSection = "transcript" | "chapters" | "research" | "settings" | "outcome" | "state" | "archive"
type CompactInspectorTab = "session" | "state" | "consequences" | "support"

type OutcomeStat = {
  label: string
  value: string
}

function formatDelta(value: number): string {
  return value > 0 ? `+${value}` : String(value)
}

function formatExpressionLabel(value: "negative" | "neutral" | "positive", language: "en" | "zh") {
  switch (value) {
    case "negative":
      return language === "zh" ? "紧张" : "Guarded"
    case "positive":
      return language === "zh" ? "更信任" : "Open"
    default:
      return language === "zh" ? "中性" : "Neutral"
  }
}

function surfaceState(snapshot: ReturnType<typeof usePlaySession>["snapshot"], key: "inventory" | "map", language: "en" | "zh") {
  const surface = snapshot?.support_surfaces?.[key]
  if (surface) {
    return surface
      ? {
          ...surface,
          disabled_reason: formatSupportSurfaceDisabledReason(key, surface.disabled_reason, language),
        }
      : surface
  }
  return {
    enabled: false,
    disabled_reason: formatSupportSurfaceDisabledReason(key, null, language),
  }
}

function outcomeAftertaste(ending: PlayEnding, language: "en" | "zh") {
  switch (ending.ending_id) {
    case "pyrrhic":
      return language === "zh"
        ? "城市勉强撑住了，但这份结果也把代价永久留在了记录里。"
        : "The city holds together, but the record keeps the cost visible."
    case "collapse":
      return language === "zh"
        ? "这不是一句失败判词，而是公共协调真正崩断的时刻。"
        : "This is not just failure. It is the point where public coordination gives way."
    default:
      return language === "zh"
        ? "系统给出了答案，但它没有抹平这个结局留下的模糊和余震。"
        : "The system finds an answer, but it does not erase the ambiguity left behind."
  }
}

function PlayMetaPanel({
  title,
  sectionId,
  defaultOpen = false,
  className = "",
  children,
}: {
  title: string
  sectionId?: string
  defaultOpen?: boolean
  className?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section className={`play-session-meta__card play-meta-panel play-anchor-target ${className} ${open ? "is-open" : "is-collapsed"}`} id={sectionId}>
      <button
        aria-expanded={open}
        className="play-meta-panel__toggle"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className="editorial-metadata-label">{title}</span>
        <StudioIcon className="play-meta-panel__icon" name={open ? "remove" : "add"} />
      </button>

      <div className="play-meta-panel__body-wrap" aria-hidden={!open}>
        <div className="play-meta-panel__body">
          {children}
        </div>
      </div>
    </section>
  )
}

export function PlaySessionPage({
  sessionId,
  uiLanguage,
  onUiLanguageChange,
  onOpenLibrary,
}: {
  sessionId: string
  uiLanguage: StoryLanguage
  onUiLanguageChange: (language: StoryLanguage) => void
  onOpenLibrary: () => void
}) {
  const playSession = usePlaySession(sessionId, uiLanguage)
  const snapshot = playSession.snapshot
  const compactDesktop = useCompactDesktop()
  const [compactInspectorTab, setCompactInspectorTab] = useState<CompactInspectorTab>("session")
  const [suggestionsDrawerOpen, setSuggestionsDrawerOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return true
    }
    const stored = window.localStorage.getItem("rpg-demo:play-suggestions-drawer-open")
    if (stored === "false") {
      return false
    }
    if (stored === "true") {
      return true
    }
    return true
  })
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null)
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)
  const previousSessionIdRef = useRef<string | null>(null)
  const storyLanguage = snapshot?.language === "zh" ? "zh" : "en"
  const languageMismatch = Boolean(snapshot && snapshot.language !== uiLanguage)
  const mismatchCopy = getLanguageMismatchCopy({
    storyLanguage: snapshot?.language,
    surface: "play",
    uiLanguage,
  })
  const localized = uiLanguage === "zh"
  const copy = localized
    ? {
        transcript: "故事进展",
        sessionState: "当前局势",
        turnImpact: "本回合影响",
        surfaces: "辅助界面",
        liveNav: "实时故事导航",
        loadingTitle: "正在载入试玩会话",
        loadingBody: "正在获取当前快照与文本记录。",
        unavailableTitle: "会话不可用",
        unavailableBody: "当前账号无法查看这个会话。",
        intentPlaceholder: "描述你的行动意图……",
        submitHint: "按 Alt + Enter 提交",
        leave: "离开会话",
        protagonist: "主角",
        sessionLanguage: "会话语言",
        progress: "进度",
        completedBeats: "已完成章节",
        currentBeat: "当前章节",
        turns: "回合",
        stateBars: "局势状态",
        recentConsequences: "最近影响",
        noConsequences: "这一回合还没有记录结果。",
        favor: "对你有利的变化",
        cost: "本回合代价",
        pressure: "压力变化",
        reactions: "人物立场",
        sceneTags: "场景标签",
        suggestedActions: "建议行动",
        supportSurfaces: "辅助界面",
        available: "可用",
        disabled: "不可用",
        player: "玩家",
        sessionUpdate: "系统推进",
        story: "故事",
        beat: "章节",
        outcome: "结局",
        finalState: "终局状态",
        archive: "完整记录",
        archiveHeading: "完整记录",
        archiveSupport: "结论已经锁定。下面保留的是本局完整的过程记录，而不是继续推进的主界面。",
        outcomeLedger: "结果账本",
        outcomeLedgerHeading: "留下了什么，付出了什么",
        finalVoices: "人物回响",
        finalVoicesHeading: "此刻他们会对你说什么",
        finalReactions: "终局人物",
        finalReactionsHeading: "谁在结局里改变了位置",
        finalStateHeading: "最后局势停在了哪里",
        finalBeat: "终局章节",
        turnsUsed: "使用回合",
        completion: "完成进度",
        outcomeSummary: "终局摘要",
        sessionCompleteLabel: "会话结束",
        sessionCompleteSummary: "本局已经结束，下面保留的是最终结局与完整记录。",
      }
    : {
        transcript: "Story So Far",
        sessionState: "Session State",
        turnImpact: "Recent Consequences",
        surfaces: "Support Surfaces",
        liveNav: "Live story navigation",
        loadingTitle: "Loading play session",
        loadingBody: "Fetching the current snapshot and transcript state.",
        unavailableTitle: "Session unavailable",
        unavailableBody: "This session is not visible to the current account.",
        intentPlaceholder: "Describe your intent...",
        submitHint: "Alt + Enter to submit",
        leave: "Leave Session",
        protagonist: "Protagonist",
        sessionLanguage: "Session Language",
        progress: "Progress",
        completedBeats: "Completed beats",
        currentBeat: "Current beat",
        turns: "Turns",
        stateBars: "Situation State",
        recentConsequences: "Recent Consequences",
        noConsequences: "No turn consequences recorded yet.",
        favor: "What moved in your favor",
        cost: "What it cost",
        pressure: "Pressure shifts",
        reactions: "Character Stances",
        sceneTags: "Scene tags",
        suggestedActions: "Suggested Actions",
        supportSurfaces: "Support Surfaces",
        available: "Available",
        disabled: "Disabled",
        player: "Player",
        sessionUpdate: "Session Update",
        story: "Story",
        beat: "Beat",
        outcome: "Outcome",
        finalState: "Final State",
        archive: "Session Archive",
        archiveHeading: "Full Transcript",
        archiveSupport: "The verdict is already locked. What follows is the full archive of the session rather than the primary live surface.",
        outcomeLedger: "Outcome Ledger",
        outcomeLedgerHeading: "What Held, What It Cost",
        finalVoices: "Final Voices",
        finalVoicesHeading: "What They Would Say To You Now",
        finalReactions: "Final Reactions",
        finalReactionsHeading: "Who Shifted By The End",
        finalStateHeading: "Where The System Settled",
        finalBeat: "Final Beat",
        turnsUsed: "Turns Used",
        completion: "Completion",
        outcomeSummary: "Outcome Summary",
        sessionCompleteLabel: "Session Complete",
        sessionCompleteSummary: "This session has ended. What follows is the final verdict and the full archive.",
      }

  const isCompleted = snapshot?.status === "completed"
  const inventorySurface = surfaceState(snapshot, "inventory", uiLanguage)
  const mapSurface = surfaceState(snapshot, "map", uiLanguage)
  const sessionSections = useMemo(
    () =>
      isCompleted
        ? [
            { id: "play-outcome", value: "outcome" as const },
            { id: "play-final-state", value: "state" as const },
            { id: "play-transcript", value: "archive" as const },
          ]
        : [
            { id: "play-transcript", value: "transcript" as const },
            { id: "play-session-meta", value: "chapters" as const },
            { id: "play-consequences", value: "research" as const },
            { id: "play-support-surfaces", value: "settings" as const },
          ],
    [isCompleted],
  )
  const sectionNavigation = useReadingSection<PlayNavSection>(sessionSections, isCompleted ? "outcome" : "transcript")
  const scrollToSection = (sectionId: string, navSection: PlayNavSection) => {
    sectionNavigation.jumpToSection(sectionId, navSection)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void playSession.submitTurn()
  }

  const compactNavItems = [
    { id: "session" as const, icon: "reorder" as const, label: copy.sessionState },
    { id: "state" as const, icon: "person" as const, label: copy.stateBars },
    { id: "consequences" as const, icon: "history_edu" as const, label: copy.turnImpact },
    { id: "support" as const, icon: "settings" as const, label: copy.supportSurfaces },
  ]
  const suggestionsCount = snapshot?.suggested_actions.length ?? 0

  const heroSupportCopy = playSession.snapshot ? copy.liveNav : copy.transcript

  const protagonistSummary = snapshot?.protagonist
    ? {
        title: snapshot.protagonist.title,
        mandate: pickHealthyText(storyLanguage, [snapshot.protagonist.mandate], ""),
        identity: isDistinctSupportCopy(
          snapshot.protagonist.identity_summary,
          snapshot.protagonist.mandate,
          storyLanguage,
        )
          ? pickHealthyText(storyLanguage, [snapshot.protagonist.identity_summary], "")
          : "",
      }
    : null
  const npcVisuals = snapshot?.npc_visuals ?? []
  const axisStateBars = (snapshot?.state_bars ?? []).filter((bar) => bar.category === "axis")
  const stanceBars = (snapshot?.state_bars ?? []).filter((bar) => bar.category === "stance")
  const stanceBarByNpcId = new Map(
    stanceBars.map((bar) => {
      const inferredNpcId = bar.bar_id.endsWith("_stance") ? bar.bar_id.slice(0, -"_stance".length) : bar.bar_id
      return [inferredNpcId, bar] as const
    }),
  )
  const sortedEpilogueReactions = [...(snapshot?.epilogue_reactions ?? [])].sort(
    (left, right) => right.stance_value - left.stance_value || left.name.localeCompare(right.name),
  )
  const hasFinalVoices = sortedEpilogueReactions.length > 0
  const resolvedEnding: PlayEnding | null = isCompleted
    ? snapshot?.ending ?? {
        ending_id: "mixed",
        label: copy.sessionCompleteLabel,
        summary: copy.sessionCompleteSummary,
      }
    : null
  const endingContextStats: OutcomeStat[] = snapshot
    ? [
        { label: copy.story, value: snapshot.story_title },
        { label: copy.finalBeat, value: snapshot.beat_title },
        ...(snapshot.progress
          ? [
              { label: copy.turnsUsed, value: `${snapshot.progress.turn_index}/${snapshot.progress.max_turns}` },
              { label: copy.completion, value: `${snapshot.progress.display_percent}%` },
            ]
          : []),
      ]
    : []
  const endingLedgerStats: OutcomeStat[] = snapshot?.feedback
    ? [
        { label: localized ? "证据推进" : "Proof", value: String(snapshot.feedback.ledgers.success.proof_progress) },
        { label: localized ? "结算推进" : "Settlement", value: String(snapshot.feedback.ledgers.success.settlement_progress) },
        { label: localized ? "公众代价" : "Public Cost", value: String(snapshot.feedback.ledgers.cost.public_cost) },
        { label: localized ? "程序代价" : "Procedural Cost", value: String(snapshot.feedback.ledgers.cost.procedural_cost) },
      ]
    : []
  const completedSidebarFacts: OutcomeStat[] = snapshot?.progress
    ? [
        { label: copy.completedBeats, value: `${snapshot.progress.completed_beats}/${snapshot.progress.total_beats}` },
        { label: copy.turns, value: `${snapshot.progress.turn_index}/${snapshot.progress.max_turns}` },
      ]
    : []
  const lastTranscriptEntryId = playSession.transcript[playSession.transcript.length - 1]?.id ?? null

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    window.localStorage.setItem("rpg-demo:play-suggestions-drawer-open", String(suggestionsDrawerOpen))
  }, [suggestionsDrawerOpen])

  useEffect(() => {
    const scrollNode = transcriptScrollRef.current
    const endNode = transcriptEndRef.current
    if (!scrollNode || !endNode) {
      return
    }
    const isSessionChange = previousSessionIdRef.current !== sessionId
    previousSessionIdRef.current = sessionId
    const behavior = prefersReducedMotionNow() || lastTranscriptEntryId === null || isSessionChange ? "auto" : "smooth"
    const frame = window.requestAnimationFrame(() => {
      endNode.scrollIntoView({ behavior, block: "end" })
    })
    return () => {
      window.cancelAnimationFrame(frame)
    }
  }, [sessionId, lastTranscriptEntryId, playSession.pendingTurnInput, playSession.submitting])

  return (
    <main className={`editorial-page editorial-page--play ${compactDesktop ? "is-compact-desktop" : ""}`}>
      <div className={`play-domain-layout ${compactDesktop ? "play-domain-layout--compact" : ""}`}>
        {!languageMismatch ? (
          <PlayDomainSidebar
            footer={
              snapshot ? (
                <div className="play-sidebar-stats">
                  <div>
                    <div className="play-sidebar-stats__row">
                      <span>{copy.progress}</span>
                      <span>{snapshot.progress?.display_percent ?? 0}%</span>
                    </div>
                    <div className="play-sidebar-stats__track">
                      <div className="play-sidebar-stats__fill" style={{ width: `${snapshot.progress?.display_percent ?? 0}%` }} />
                    </div>
                  </div>
                  <div className="play-sidebar-stats__meta">
                    <div>
                      <span className="editorial-metadata-label">{copy.story}</span>
                      <p>{snapshot.story_title}</p>
                    </div>
                    <div>
                      <span className="editorial-metadata-label">{isCompleted ? copy.outcome : copy.beat}</span>
                      <p>{isCompleted ? resolvedEnding?.label ?? snapshot.beat_title : snapshot.beat_title}</p>
                    </div>
                  </div>
                </div>
              ) : null
            }
            items={
              compactDesktop && !isCompleted
                ? compactNavItems.map((item) => ({
                    icon: item.icon,
                    label: item.label,
                    active: compactInspectorTab === item.id,
                    onSelect: () => setCompactInspectorTab(item.id),
                  }))
                : isCompleted
                  ? [
                      {
                        icon: "north_east",
                        label: copy.outcome,
                        active: sectionNavigation.activeSection === "outcome",
                        onSelect: () => scrollToSection("play-outcome", "outcome"),
                      },
                      {
                        icon: "reorder",
                        label: copy.finalState,
                        active: sectionNavigation.activeSection === "state",
                        onSelect: () => scrollToSection("play-final-state", "state"),
                      },
                      {
                        icon: "menu_book",
                        label: copy.archive,
                        active: sectionNavigation.activeSection === "archive",
                        onSelect: () => scrollToSection("play-transcript", "archive"),
                      },
                    ]
                  : [
                      {
                        icon: "menu_book",
                        label: copy.transcript,
                        active: sectionNavigation.activeSection === "transcript",
                        onSelect: () => scrollToSection("play-transcript", "transcript"),
                      },
                      {
                        icon: "reorder",
                        label: copy.sessionState,
                        active: sectionNavigation.activeSection === "chapters",
                        onSelect: () => scrollToSection("play-session-meta", "chapters"),
                      },
                      {
                        icon: "history_edu",
                        label: copy.turnImpact,
                        active: sectionNavigation.activeSection === "research",
                        onSelect: () => scrollToSection("play-consequences", "research"),
                      },
                      {
                        icon: "settings",
                        label: copy.surfaces,
                        active: sectionNavigation.activeSection === "settings",
                        onSelect: () => scrollToSection("play-support-surfaces", "settings"),
                      },
                    ]
            }
            subtitle={isCompleted ? resolvedEnding?.label ?? snapshot?.beat_title ?? copy.liveNav : snapshot?.beat_title ?? heroSupportCopy}
            title={snapshot?.story_title ?? (localized ? "试玩会话" : "Play Session")}
          />
        ) : null}

        <section className={`play-canvas ${compactDesktop ? "play-canvas--compact" : ""}`}>
          {playSession.loading ? (
            <div className="editorial-empty-state">
              <h3>{copy.loadingTitle}</h3>
              <p>{copy.loadingBody}</p>
            </div>
          ) : languageMismatch ? (
            <div className="editorial-empty-state">
              <h3>{mismatchCopy.title}</h3>
              <p>{mismatchCopy.body}</p>
              <button
                className="studio-button studio-button--primary"
                onClick={() => onUiLanguageChange(snapshot?.language === "zh" ? "zh" : "en")}
                type="button"
              >
                {mismatchCopy.switchAction}
              </button>
              <button className="studio-button studio-button--secondary" onClick={onOpenLibrary} type="button">
                {mismatchCopy.backAction}
              </button>
            </div>
          ) : !snapshot ? (
            <div className="editorial-empty-state">
              <h3>{copy.unavailableTitle}</h3>
              <p>{playSession.error ?? copy.unavailableBody}</p>
              <button className="studio-button studio-button--secondary" onClick={onOpenLibrary} type="button">
                {localized ? "返回故事库" : "Back to Library"}
              </button>
            </div>
          ) : isCompleted ? (
            <div className="play-content-grid play-content-grid--completed">
              <div className="play-story-column play-story-column--completed">
                <section className="play-completed-outcome play-anchor-target" id="play-outcome">
                  {resolvedEnding ? (
                    <EndingSummary
                      aftertaste={outcomeAftertaste(resolvedEnding, uiLanguage)}
                      contextStats={endingContextStats}
                      ending={resolvedEnding}
                      ledgerStats={endingLedgerStats}
                      uiLanguage={uiLanguage}
                    />
                  ) : null}
                </section>

                <section className="play-completed-modules play-anchor-target" id="play-final-state">
                  {snapshot.feedback ? (
                    <section className="play-completed-card play-completed-card--wide">
                      <div className="play-completed-card__header">
                        <p className="editorial-metadata-label">{copy.outcomeLedger}</p>
                        <h3>{copy.outcomeLedgerHeading}</h3>
                      </div>
                      <div className="play-feedback-summary">
                        {snapshot.feedback.last_turn_consequences.length > 0 ? (
                          <ul className="play-feedback-summary__list">
                            {snapshot.feedback.last_turn_consequences.map((consequence) => (
                              <li key={consequence}>{consequence}</li>
                            ))}
                          </ul>
                        ) : null}

                        <div className="play-feedback-ledgers">
                          <div>
                            <span className="editorial-metadata-label">{copy.favor}</span>
                            <ul className="play-feedback-ledgers__list">
                              {Object.entries(snapshot.feedback.ledgers.success).map(([key, value]) => (
                                <li key={key}>
                                  <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                  <strong>{value}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span className="editorial-metadata-label">{copy.cost}</span>
                            <ul className="play-feedback-ledgers__list">
                              {Object.entries(snapshot.feedback.ledgers.cost).map(([key, value]) => (
                                <li key={key}>
                                  <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                  <strong>{value}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    </section>
                  ) : null}

                  {!hasFinalVoices && npcVisuals.length > 0 ? (
                    <section className="play-completed-card">
                      <div className="play-completed-card__header">
                        <p className="editorial-metadata-label">{copy.finalReactions}</p>
                        <h3>{copy.finalReactionsHeading}</h3>
                      </div>
                      <div className="play-npc-panel">
                        {npcVisuals.map((item) => (
                          <article className={`play-npc-panel__card is-${item.current_expression}`} key={item.npc_id}>
                            <EditorialMedia
                              alt={item.name}
                              className="play-npc-panel__portrait"
                              overlay
                              ratio="4 / 5"
                              src={item.current_portrait_url ?? undefined}
                            />
                            <div className="play-npc-panel__copy">
                              <strong>{item.name}</strong>
                              <div className="play-npc-panel__chips">
                                <span className="editorial-chip">{formatExpressionLabel(item.current_expression, uiLanguage)}</span>
                                <span className="editorial-muted-chip">
                                  {uiLanguage === "zh"
                                    ? `立场 ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`
                                    : `Stance ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`}
                                </span>
                              </div>
                            </div>
                          </article>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  <section className="play-completed-card">
                    <div className="play-completed-card__header">
                      <p className="editorial-metadata-label">{copy.finalState}</p>
                      <h3>{copy.finalStateHeading}</h3>
                    </div>
                    <StateBarList bars={snapshot.state_bars} language={uiLanguage} />
                  </section>
                </section>

                <section className="play-transcript-column play-transcript-column--archive play-anchor-target" id="play-transcript">
                  <div className="play-transcript-column__header">
                    <p className="editorial-metadata-label">{copy.archive}</p>
                    <h2>{copy.archiveHeading}</h2>
                    <p className="editorial-support">{copy.archiveSupport}</p>
                  </div>
                  {hasFinalVoices ? (
                    <section className="play-completed-card play-completed-card--voices">
                      <div className="play-completed-card__header">
                        <p className="editorial-metadata-label">{copy.finalVoices}</p>
                        <h3>{copy.finalVoicesHeading}</h3>
                      </div>
                      <div className="play-epilogue-voices">
                        {sortedEpilogueReactions.map((item) => (
                          <article className={`play-epilogue-voice is-${item.current_expression}`} key={item.npc_id}>
                            <EditorialMedia
                              alt={item.name}
                              className="play-epilogue-voice__portrait"
                              overlay
                              ratio="4 / 5"
                              src={item.current_portrait_url ?? undefined}
                            />
                            <div className="play-epilogue-voice__body">
                              <div className="play-epilogue-voice__header">
                                <strong>{item.name}</strong>
                                <div className="play-npc-panel__chips">
                                  <span className="editorial-chip">{formatExpressionLabel(item.current_expression, uiLanguage)}</span>
                                  <span className="editorial-muted-chip">
                                    {uiLanguage === "zh"
                                      ? `立场 ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`
                                      : `Stance ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`}
                                  </span>
                                </div>
                              </div>
                              <blockquote className="play-epilogue-voice__line">{item.closing_line}</blockquote>
                            </div>
                          </article>
                        ))}
                      </div>
                    </section>
                  ) : null}
                  <TranscriptView
                    entries={playSession.transcript}
                    storyLanguage={storyLanguage}
                    submitting={false}
                    uiLanguage={uiLanguage}
                  />
                </section>
              </div>

              <aside className="play-session-meta play-session-meta--completed">
                {protagonistSummary ? (
                  <section className="play-session-meta__card play-completed-sidecard">
                    <p className="editorial-metadata-label">{copy.protagonist}</p>
                    <div className="play-session-meta__headline">
                      <strong>{protagonistSummary.title}</strong>
                      {protagonistSummary.mandate ? <p>{protagonistSummary.mandate}</p> : null}
                    </div>
                    {protagonistSummary.identity ? <p className="editorial-support">{protagonistSummary.identity}</p> : null}
                  </section>
                ) : null}

                <section className="play-session-meta__card play-completed-sidecard">
                  <p className="editorial-metadata-label">{copy.outcomeSummary}</p>
                  <div className="play-completed-sidecard__facts">
                    {completedSidebarFacts.map((item) => (
                      <div key={`${item.label}:${item.value}`}>
                        <span className="editorial-metadata-label">{item.label}</span>
                        <strong>{item.value}</strong>
                      </div>
                    ))}
                  </div>
                </section>
              </aside>
            </div>
          ) : (
            <div className={`play-content-grid ${compactDesktop ? "play-content-grid--compact" : ""}`}>
              <div className={`play-story-column ${compactDesktop ? "play-story-column--compact" : ""}`}>
                <div className={`play-chat-workbench ${compactDesktop ? "play-chat-workbench--compact" : ""}`}>
                  <section className={`play-transcript-column ${compactDesktop ? "play-transcript-column--compact" : ""} play-chat-history`} id="play-transcript">
                    <div className={`play-transcript-scroll ${compactDesktop ? "play-transcript-scroll--compact" : ""}`} ref={transcriptScrollRef}>
                      <TranscriptView
                        entries={playSession.transcript}
                        pendingPlayerText={playSession.pendingTurnInput}
                        storyLanguage={storyLanguage}
                        submitting={playSession.submitting}
                        uiLanguage={uiLanguage}
                      />
                      <div aria-hidden="true" className="play-transcript-scroll__sentinel" ref={transcriptEndRef} />
                    </div>
                  </section>

                  <form className={`play-input-dock ${playSession.submitting ? "is-submitting" : ""} ${compactDesktop ? "play-input-dock--compact" : ""}`} onSubmit={handleSubmit}>
                    {compactDesktop ? (
                      <section className={`play-action-drawer ${suggestionsDrawerOpen ? "is-open" : "is-collapsed"}`}>
                        <button
                          aria-expanded={suggestionsDrawerOpen}
                          className="play-action-drawer__toggle"
                          onClick={() => setSuggestionsDrawerOpen((current) => !current)}
                          type="button"
                        >
                          <div className="play-action-drawer__summary">
                            <span className="editorial-metadata-label">{copy.suggestedActions}</span>
                            <span className="play-action-drawer__count">{suggestionsCount}</span>
                          </div>
                          <StudioIcon name={suggestionsDrawerOpen ? "remove" : "add"} />
                        </button>
                        <div className="play-action-drawer__body-wrap" aria-hidden={!suggestionsDrawerOpen}>
                          <div className="play-action-drawer__body">
                            <SuggestedActions
                              actions={snapshot.suggested_actions}
                              onSelect={playSession.selectSuggestedAction}
                              selectedSuggestionId={playSession.selectedSuggestionId}
                              uiLanguage={uiLanguage}
                              variant="tray"
                            />
                          </div>
                        </div>
                      </section>
                    ) : null}

                    <div className="play-input-dock__field">
                      <textarea
                        className="play-input-dock__textarea"
                        disabled={playSession.submitting}
                        onChange={(event) => playSession.setInputText(event.target.value)}
                        placeholder={copy.intentPlaceholder}
                        rows={1}
                        value={playSession.inputText}
                      />
                      <button className="play-input-dock__submit" disabled={playSession.submitting} type="submit">
                        <StudioIcon name="north_east" />
                      </button>
                    </div>

                    <div className="play-input-dock__meta">
                      <div className="play-input-dock__tools">
                        <button
                          className={!inventorySurface.enabled ? "is-disabled" : ""}
                          disabled={!inventorySurface.enabled}
                          title={inventorySurface.disabled_reason ?? undefined}
                          type="button"
                        >
                          {formatPlayLedgerLabel("inventory", uiLanguage)}
                        </button>
                        <button
                          className={!mapSurface.enabled ? "is-disabled" : ""}
                          disabled={!mapSurface.enabled}
                          title={mapSurface.disabled_reason ?? undefined}
                          type="button"
                        >
                          {formatPlayLedgerLabel("map", uiLanguage)}
                        </button>
                      </div>

                      <div className="play-input-dock__actions">
                        <button className="studio-button studio-button--ghost" onClick={onOpenLibrary} type="button">
                          {copy.leave}
                        </button>
                        {playSession.submitting ? null : <span>{copy.submitHint}</span>}
                      </div>
                    </div>

                    {playSession.error ? <p className="editorial-error">{playSession.error}</p> : null}
                  </form>
                </div>
              </div>

              <aside className={`play-session-meta ${compactDesktop ? "play-session-meta--compact" : ""}`}>
                {protagonistSummary ? (
                  <section className="play-session-meta__card play-session-meta__card--primary">
                    <p className="editorial-metadata-label">{copy.protagonist}</p>
                    <div className="play-session-meta__headline">
                      <strong>{protagonistSummary.title}</strong>
                      {protagonistSummary.mandate ? <p>{protagonistSummary.mandate}</p> : null}
                    </div>
                    {protagonistSummary.identity ? <p className="editorial-support">{protagonistSummary.identity}</p> : null}
                  </section>
                ) : null}

                {compactDesktop ? (
                  <section className="play-session-meta__card play-session-meta__card--inspector">
                    <div className="play-inspector-tabs" role="tablist" aria-label={copy.sessionState}>
                      {compactNavItems.map((item) => (
                        <button
                          aria-selected={compactInspectorTab === item.id}
                          className={`play-inspector-tab ${compactInspectorTab === item.id ? "is-active" : ""}`}
                          key={item.id}
                          onClick={() => setCompactInspectorTab(item.id)}
                          role="tab"
                          type="button"
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                    <div className="play-inspector-panel" role="tabpanel">
                      <div className="play-inspector-scroll">
                        {compactInspectorTab === "session" ? (
                          <>
                            <div className="play-session-meta__headline">
                              <strong>{snapshot.story_title}</strong>
                              <p>{snapshot.beat_title}</p>
                            </div>
                            <div className="play-session-meta__fact">
                              <span className="editorial-metadata-label">{copy.sessionLanguage}</span>
                              <p>{formatStoryLanguageLabel(snapshot.language, uiLanguage)}</p>
                            </div>
                            {snapshot.progress ? (
                              <div className="play-feedback-ledgers">
                                <div>
                                  <span className="editorial-metadata-label">{copy.progress}</span>
                                  <ul className="play-feedback-ledgers__list">
                                    <li>
                                      <span>{copy.completedBeats}</span>
                                      <strong>
                                        {snapshot.progress.completed_beats}/{snapshot.progress.total_beats}
                                      </strong>
                                    </li>
                                    <li>
                                      <span>{copy.currentBeat}</span>
                                      <strong>
                                        {snapshot.progress.current_beat_progress}/{snapshot.progress.current_beat_goal}
                                      </strong>
                                    </li>
                                    <li>
                                      <span>{copy.turns}</span>
                                      <strong>
                                        {snapshot.progress.turn_index}/{snapshot.progress.max_turns}
                                      </strong>
                                    </li>
                                  </ul>
                                </div>
                              </div>
                            ) : null}
                          </>
                        ) : null}

                        {compactInspectorTab === "state" ? (
                          <>
                            <StateBarList bars={axisStateBars} language={uiLanguage} />
                            {npcVisuals.length > 0 ? (
                              <div className="play-npc-panel">
                                {npcVisuals.map((item) => {
                                  const stanceBar = stanceBarByNpcId.get(item.npc_id)
                                  return (
                                    <article className={`play-npc-panel__card is-${item.current_expression}`} key={item.npc_id}>
                                      <EditorialMedia
                                        alt={item.name}
                                        className="play-npc-panel__portrait"
                                        overlay
                                        ratio="4 / 5"
                                        src={item.current_portrait_url ?? undefined}
                                      />
                                      <div className="play-npc-panel__copy">
                                        <strong>{item.name}</strong>
                                        <div className="play-npc-panel__chips">
                                          <span className="editorial-chip">{formatExpressionLabel(item.current_expression, uiLanguage)}</span>
                                          <span className="editorial-muted-chip">
                                            {uiLanguage === "zh"
                                              ? `立场 ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`
                                              : `Stance ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`}
                                          </span>
                                        </div>
                                        {stanceBar ? (
                                          <div className="play-npc-panel__meter">
                                            <div className="play-state-row__track">
                                              <div className="play-state-row__fill" style={{ width: progressWidth(stanceBar.current_value, stanceBar.min_value, stanceBar.max_value) }} />
                                            </div>
                                          </div>
                                        ) : null}
                                      </div>
                                    </article>
                                  )
                                })}
                              </div>
                            ) : null}
                          </>
                        ) : null}

                        {compactInspectorTab === "consequences" ? (
                          snapshot.feedback ? (
                            <div className="play-feedback-summary">
                              {snapshot.feedback.last_turn_consequences.length > 0 ? (
                                <ul className="play-feedback-summary__list">
                                  {snapshot.feedback.last_turn_consequences.map((consequence) => (
                                    <li key={consequence}>{consequence}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="editorial-support">{copy.noConsequences}</p>
                              )}

                              <div className="play-feedback-ledgers">
                                <div>
                                  <span className="editorial-metadata-label">{copy.favor}</span>
                                  <ul className="play-feedback-ledgers__list">
                                    {Object.entries(snapshot.feedback.ledgers.success).map(([key, value]) => (
                                      <li key={key}>
                                        <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                        <strong>{value}</strong>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                                <div>
                                  <span className="editorial-metadata-label">{copy.cost}</span>
                                  <ul className="play-feedback-ledgers__list">
                                    {Object.entries(snapshot.feedback.ledgers.cost).map(([key, value]) => (
                                      <li key={key}>
                                        <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                        <strong>{value}</strong>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>

                              {Object.keys(snapshot.feedback.last_turn_axis_deltas).length > 0 ? (
                                <div>
                                  <span className="editorial-metadata-label">{copy.pressure}</span>
                                  <ul className="play-feedback-ledgers__list">
                                    {Object.entries(snapshot.feedback.last_turn_axis_deltas).map(([key, value]) => (
                                      <li key={key}>
                                        <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                        <strong>{formatDelta(value)}</strong>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}

                              {Object.keys(snapshot.feedback.last_turn_stance_deltas).length > 0 ? (
                                <div>
                                  <span className="editorial-metadata-label">{copy.reactions}</span>
                                  <ul className="play-feedback-ledgers__list">
                                    {Object.entries(snapshot.feedback.last_turn_stance_deltas).map(([key, value]) => (
                                      <li key={key}>
                                        <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                        <strong>{formatDelta(value)}</strong>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}

                              {snapshot.feedback.last_turn_tags.length > 0 ? (
                                <div>
                                  <span className="editorial-metadata-label">{copy.sceneTags}</span>
                                  <div className="detail-header__chips">
                                    {snapshot.feedback.last_turn_tags.map((tag) => (
                                      <span className="editorial-muted-chip" key={tag}>
                                        {formatPlayLedgerLabel(tag, uiLanguage)}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : (
                            <p className="editorial-support">{copy.noConsequences}</p>
                          )
                        ) : null}

                        {compactInspectorTab === "support" ? (
                          <>
                            <div className="play-support-surfaces">
                              <button className={`play-support-surface ${inventorySurface.enabled ? "is-enabled" : "is-disabled"}`} disabled={!inventorySurface.enabled} type="button">
                                <strong>{formatPlayLedgerLabel("inventory", uiLanguage)}</strong>
                                <span>{inventorySurface.enabled ? copy.available : copy.disabled}</span>
                              </button>
                              <button className={`play-support-surface ${mapSurface.enabled ? "is-enabled" : "is-disabled"}`} disabled={!mapSurface.enabled} type="button">
                                <strong>{formatPlayLedgerLabel("map", uiLanguage)}</strong>
                                <span>{mapSurface.enabled ? copy.available : copy.disabled}</span>
                              </button>
                            </div>
                            <div className="play-support-surfaces__notes">
                              {!inventorySurface.enabled && inventorySurface.disabled_reason ? <p>{inventorySurface.disabled_reason}</p> : null}
                              {!mapSurface.enabled && mapSurface.disabled_reason ? <p>{mapSurface.disabled_reason}</p> : null}
                            </div>
                          </>
                        ) : null}
                      </div>
                    </div>
                  </section>
                ) : (
                  <>
                    <PlayMetaPanel className="play-meta-panel--session" sectionId="play-session-meta" title={copy.sessionState}>
                      <div className="play-session-meta__headline">
                        <strong>{snapshot.story_title}</strong>
                        <p>{snapshot.beat_title}</p>
                      </div>
                      <div className="play-session-meta__fact">
                        <span className="editorial-metadata-label">{copy.sessionLanguage}</span>
                        <p>{formatStoryLanguageLabel(snapshot.language, uiLanguage)}</p>
                      </div>
                      {snapshot.progress ? (
                        <div className="play-feedback-ledgers">
                          <div>
                            <span className="editorial-metadata-label">{copy.progress}</span>
                            <ul className="play-feedback-ledgers__list">
                              <li>
                                <span>{copy.completedBeats}</span>
                                <strong>
                                  {snapshot.progress.completed_beats}/{snapshot.progress.total_beats}
                                </strong>
                              </li>
                              <li>
                                <span>{copy.currentBeat}</span>
                                <strong>
                                  {snapshot.progress.current_beat_progress}/{snapshot.progress.current_beat_goal}
                                </strong>
                              </li>
                              <li>
                                <span>{copy.turns}</span>
                                <strong>
                                  {snapshot.progress.turn_index}/{snapshot.progress.max_turns}
                                </strong>
                              </li>
                            </ul>
                          </div>
                        </div>
                      ) : null}
                    </PlayMetaPanel>

                    <PlayMetaPanel className="play-meta-panel--state" defaultOpen title={copy.stateBars}>
                      <StateBarList bars={axisStateBars} language={uiLanguage} />
                    </PlayMetaPanel>

                    {npcVisuals.length > 0 ? (
                      <PlayMetaPanel className="play-meta-panel--reactions" defaultOpen title={copy.reactions}>
                        <div className="play-npc-panel">
                          {npcVisuals.map((item) => {
                            const stanceBar = stanceBarByNpcId.get(item.npc_id)
                            return (
                              <article className={`play-npc-panel__card is-${item.current_expression}`} key={item.npc_id}>
                                <EditorialMedia
                                  alt={item.name}
                                  className="play-npc-panel__portrait"
                                  overlay
                                  ratio="4 / 5"
                                  src={item.current_portrait_url ?? undefined}
                                />
                                <div className="play-npc-panel__copy">
                                  <strong>{item.name}</strong>
                                  <div className="play-npc-panel__chips">
                                    <span className="editorial-chip">{formatExpressionLabel(item.current_expression, uiLanguage)}</span>
                                    <span className="editorial-muted-chip">
                                      {uiLanguage === "zh"
                                        ? `立场 ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`
                                        : `Stance ${item.stance_value > 0 ? `+${item.stance_value}` : item.stance_value}`}
                                    </span>
                                  </div>
                                  {stanceBar ? (
                                    <div className="play-npc-panel__meter">
                                      <div className="play-state-row__track">
                                        <div className="play-state-row__fill" style={{ width: progressWidth(stanceBar.current_value, stanceBar.min_value, stanceBar.max_value) }} />
                                      </div>
                                    </div>
                                  ) : null}
                                </div>
                              </article>
                            )
                          })}
                        </div>
                      </PlayMetaPanel>
                    ) : null}

                    {snapshot.feedback ? (
                      <PlayMetaPanel className="play-meta-panel--consequences" sectionId="play-consequences" title={copy.recentConsequences}>
                        <div className="play-feedback-summary">
                          {snapshot.feedback.last_turn_consequences.length > 0 ? (
                            <ul className="play-feedback-summary__list">
                              {snapshot.feedback.last_turn_consequences.map((consequence) => (
                                <li key={consequence}>{consequence}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="editorial-support">{copy.noConsequences}</p>
                          )}

                          <div className="play-feedback-ledgers">
                            <div>
                              <span className="editorial-metadata-label">{copy.favor}</span>
                              <ul className="play-feedback-ledgers__list">
                                {Object.entries(snapshot.feedback.ledgers.success).map(([key, value]) => (
                                  <li key={key}>
                                    <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                    <strong>{value}</strong>
                                  </li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <span className="editorial-metadata-label">{copy.cost}</span>
                              <ul className="play-feedback-ledgers__list">
                                {Object.entries(snapshot.feedback.ledgers.cost).map(([key, value]) => (
                                  <li key={key}>
                                    <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                    <strong>{value}</strong>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>

                          {Object.keys(snapshot.feedback.last_turn_axis_deltas).length > 0 ? (
                            <div>
                              <span className="editorial-metadata-label">{copy.pressure}</span>
                              <ul className="play-feedback-ledgers__list">
                                {Object.entries(snapshot.feedback.last_turn_axis_deltas).map(([key, value]) => (
                                  <li key={key}>
                                    <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                    <strong>{formatDelta(value)}</strong>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}

                          {Object.keys(snapshot.feedback.last_turn_stance_deltas).length > 0 ? (
                            <div>
                              <span className="editorial-metadata-label">{copy.reactions}</span>
                              <ul className="play-feedback-ledgers__list">
                                {Object.entries(snapshot.feedback.last_turn_stance_deltas).map(([key, value]) => (
                                  <li key={key}>
                                    <span>{formatPlayLedgerLabel(key, uiLanguage)}</span>
                                    <strong>{formatDelta(value)}</strong>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}

                          {snapshot.feedback.last_turn_tags.length > 0 ? (
                            <div>
                              <span className="editorial-metadata-label">{copy.sceneTags}</span>
                              <div className="detail-header__chips">
                                {snapshot.feedback.last_turn_tags.map((tag) => (
                                  <span className="editorial-muted-chip" key={tag}>
                                    {formatPlayLedgerLabel(tag, uiLanguage)}
                                  </span>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </PlayMetaPanel>
                    ) : null}

                    <PlayMetaPanel className="play-meta-panel--suggested" defaultOpen title={copy.suggestedActions}>
                      <SuggestedActions
                        actions={snapshot.suggested_actions}
                        onSelect={playSession.selectSuggestedAction}
                        selectedSuggestionId={playSession.selectedSuggestionId}
                        uiLanguage={uiLanguage}
                      />
                    </PlayMetaPanel>

                    <PlayMetaPanel className="play-meta-panel--support" sectionId="play-support-surfaces" title={copy.supportSurfaces}>
                      <div className="play-support-surfaces">
                        <button className={`play-support-surface ${inventorySurface.enabled ? "is-enabled" : "is-disabled"}`} disabled={!inventorySurface.enabled} type="button">
                          <strong>{formatPlayLedgerLabel("inventory", uiLanguage)}</strong>
                          <span>{inventorySurface.enabled ? copy.available : copy.disabled}</span>
                        </button>
                        <button className={`play-support-surface ${mapSurface.enabled ? "is-enabled" : "is-disabled"}`} disabled={!mapSurface.enabled} type="button">
                          <strong>{formatPlayLedgerLabel("map", uiLanguage)}</strong>
                          <span>{mapSurface.enabled ? copy.available : copy.disabled}</span>
                        </button>
                      </div>
                      <div className="play-support-surfaces__notes">
                        {!inventorySurface.enabled && inventorySurface.disabled_reason ? <p>{inventorySurface.disabled_reason}</p> : null}
                        {!mapSurface.enabled && mapSurface.disabled_reason ? <p>{mapSurface.disabled_reason}</p> : null}
                      </div>
                    </PlayMetaPanel>
                  </>
                )}
              </aside>
            </div>
          )}

          <StudioFooter uiLanguage={uiLanguage} />
        </section>
      </div>
    </main>
  )
}
