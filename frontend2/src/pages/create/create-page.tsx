import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import type {
  NarrativeDifficulty,
  NarrativeStoryBrief,
  NarrativeStoryBriefAdvisorResponse,
  NarrativeTensionProfile,
  NarrativeTemplateLanguage,
  NarrativeTemplateVisibility,
} from "../../api/contracts"
import { useApi } from "../../app/api-context"
import { useAuth } from "../../app/auth-context"
import { friendlyError } from "../../shared/lib/friendly-error"
import { useLanguage, useT, type Lang, type StringKey } from "../../shared/lib/i18n"
import { itemTransition, transitions } from "../../shared/lib/motion-presets"
import { PAGE_BG } from "../../shared/lib/webtoon-assets"

const SEED_EXAMPLE_KEYS: StringKey[] = [
  "create.example_seed_1",
  "create.example_seed_2",
  "create.example_seed_3",
  "create.example_seed_4",
]

const VISIBILITY_OPTION_IDS: NarrativeTemplateVisibility[] = ["private", "unlisted", "public"]

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

type TensionProfileChoice = "auto" | NarrativeTensionProfile

type GuideMessage = {
  id: string
  speaker: "guide" | "user"
  text: string
}

type TensionProfileOptionMeta = {
  id: TensionProfileChoice
  labelKey: StringKey
  descKey: StringKey
}

const TENSION_PROFILE_OPTIONS: TensionProfileOptionMeta[] = [
  {
    id: "auto",
    labelKey: "create.tension_auto_label",
    descKey: "create.tension_auto_desc",
  },
  {
    id: "high_drama",
    labelKey: "create.tension_high_drama_label",
    descKey: "create.tension_high_drama_desc",
  },
  {
    id: "cozy_mystery",
    labelKey: "create.tension_cozy_mystery_label",
    descKey: "create.tension_cozy_mystery_desc",
  },
  {
    id: "comedy",
    labelKey: "create.tension_comedy_label",
    descKey: "create.tension_comedy_desc",
  },
  {
    id: "fantasy_sci_fi",
    labelKey: "create.tension_fantasy_sci_fi_label",
    descKey: "create.tension_fantasy_sci_fi_desc",
  },
  {
    id: "family_social",
    labelKey: "create.tension_family_social_label",
    descKey: "create.tension_family_social_desc",
  },
]

function briefKey(seed: string, language: NarrativeTemplateLanguage, tensionProfile: TensionProfileChoice): string {
  return `${seed.trim()}\n${language}\n${tensionProfile}`
}

function makeGuestHandle(): string {
  return `guest_${Math.random().toString(36).slice(2, 8)}`
}

type BudgetOptionMeta = {
  budget: number
  labelKey: StringKey
  timeKey: StringKey
  descKey: StringKey
}

const BUDGET_OPTIONS: BudgetOptionMeta[] = [
  {
    budget: 8,
    labelKey: "create.budget_short_label",
    timeKey: "create.budget_short_time",
    descKey: "create.budget_short_desc",
  },
  {
    budget: 12,
    labelKey: "create.budget_medium_label",
    timeKey: "create.budget_medium_time",
    descKey: "create.budget_medium_desc",
  },
  {
    budget: 20,
    labelKey: "create.budget_long_label",
    timeKey: "create.budget_long_time",
    descKey: "create.budget_long_desc",
  },
]

type DifficultyOptionMeta = {
  id: NarrativeDifficulty
  labelKey: StringKey
  taglineKey: StringKey
  descKey: StringKey
}

const DIFFICULTY_OPTIONS: DifficultyOptionMeta[] = [
  {
    id: "story",
    labelKey: "create.difficulty_story_label",
    taglineKey: "create.difficulty_story_tagline",
    descKey: "create.difficulty_story_desc",
  },
  {
    id: "gauntlet",
    labelKey: "create.difficulty_gauntlet_label",
    taglineKey: "create.difficulty_gauntlet_tagline",
    descKey: "create.difficulty_gauntlet_desc",
  },
]

// Story-language options — controls the locale of generated narration
// and NPC dialogue. Immutable per template once created.
const STORY_LANGUAGE_OPTIONS: Record<Lang, Array<{
  id: NarrativeTemplateLanguage
  label: string
  desc: string
}>> = {
  zh: [
    { id: "zh", label: "中文", desc: "NPC 对白和叙述都用简体中文" },
    { id: "en", label: "英文", desc: "Narration and NPC dialogue in English" },
  ],
  en: [
    { id: "zh", label: "Chinese", desc: "Narration and NPC dialogue in Simplified Chinese" },
    { id: "en", label: "English", desc: "Narration and NPC dialogue in English" },
  ],
}

const VISIBILITY_KEY_MAP: Record<
  NarrativeTemplateVisibility,
  { labelKey: StringKey; descKey: StringKey }
> = {
  private: {
    labelKey: "create.visibility_private_label",
    descKey: "create.visibility_private_desc",
  },
  unlisted: {
    labelKey: "create.visibility_unlisted_label",
    descKey: "create.visibility_unlisted_desc",
  },
  public: {
    labelKey: "create.visibility_public_label",
    descKey: "create.visibility_public_desc",
  },
}

export function CreatePage({
  onBackHome,
  onSessionStarted,
}: {
  onBackHome: () => void
  onSessionStarted: (sessionId: string) => void
}) {
  const api = useApi()
  const auth = useAuth()
  const { lang: uiLang } = useLanguage()
  const t = useT()
  const compactLayout = useCompactLayout()
  const [seed, setSeed] = useState("")
  const [draftTurn, setDraftTurn] = useState("")
  const [chatMessages, setChatMessages] = useState<GuideMessage[]>([])
  const [correctionCount, setCorrectionCount] = useState(0)
  const [visibility, setVisibility] = useState<NarrativeTemplateVisibility>("private")
  const [turnBudget, setTurnBudget] = useState<number>(12)
  const [difficulty, setDifficulty] = useState<NarrativeDifficulty>("story")
  const [settingsOpen, setSettingsOpen] = useState(false)
  // Default the story language to whatever the UI is in. The user can
  // override — the field is independent of UI language once chosen
  // (you can browse in English but write a Chinese story, etc.).
  const [storyLanguage, setStoryLanguage] = useState<NarrativeTemplateLanguage>(uiLang)
  const [desiredTensionProfile, setDesiredTensionProfile] = useState<TensionProfileChoice>("auto")
  const [busy, setBusy] = useState(false)
  const [briefBusy, setBriefBusy] = useState(false)
  const [busyElapsedSeconds, setBusyElapsedSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [briefError, setBriefError] = useState<string | null>(null)
  const [briefResponse, setBriefResponse] = useState<NarrativeStoryBriefAdvisorResponse | null>(null)
  const [briefResponseKey, setBriefResponseKey] = useState<string | null>(null)
  const seedTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const guestHandleRef = useRef<string | null>(null)
  // Synchronous lock to prevent duplicate creates if the user manages to
  // double-click before React flushes setBusy(true). useState alone doesn't
  // guarantee that — React batches state updates, so two clicks within
  // ~16ms can both pass the `busy` check and fire two requests.
  const inflightRef = useRef(false)

  const seedExamples = useMemo(() => SEED_EXAMPLE_KEYS.map((k) => t(k)), [t])
  const visibleSeedExamples = compactLayout ? seedExamples.slice(0, 3) : seedExamples
  const hasSeed = Boolean(seed.trim())
  const currentBriefKey = briefKey(seed, storyLanguage, desiredTensionProfile)
  const activeBriefResponse =
    briefResponse && briefResponseKey === currentBriefKey ? briefResponse : null
  const activeBrief = activeBriefResponse?.brief ?? null
  const canGenerateFromBrief = Boolean(activeBriefResponse?.can_generate)
  const showCreateAction = true
  const showBackAction = hasSeed || busy || briefBusy
  const showSeedExamples = !hasSeed && !busy && !briefBusy
  const selectedBudget = BUDGET_OPTIONS.find((o) => o.budget === turnBudget) ?? BUDGET_OPTIONS[1]
  const selectedDifficulty = DIFFICULTY_OPTIONS.find((o) => o.id === difficulty) ?? DIFFICULTY_OPTIONS[0]
  const selectedLanguage =
    STORY_LANGUAGE_OPTIONS[uiLang].find((o) => o.id === storyLanguage) ?? STORY_LANGUAGE_OPTIONS[uiLang][0]
  const selectedVisibility = VISIBILITY_KEY_MAP[visibility]
  const selectedTension =
    TENSION_PROFILE_OPTIONS.find((o) => o.id === desiredTensionProfile) ?? TENSION_PROFILE_OPTIONS[0]
  const guideMessages = useMemo<GuideMessage[]>(
    () => [
      {
        id: "guide-open",
        speaker: "guide",
        text: t("create.guide_greeting"),
      },
      {
        id: "guide-open-2",
        speaker: "guide",
        text: t("create.guide_greeting_2"),
      },
      ...chatMessages,
    ],
    [chatMessages, t],
  )
  const settingsSummary = [
    t(selectedBudget.labelKey),
    t(selectedDifficulty.labelKey),
    selectedLanguage.label,
    t(selectedTension.labelKey),
    t(selectedVisibility.labelKey),
  ].join(" · ")
  const submitModKey = useMemo(() => {
    if (typeof navigator === "undefined") return "Ctrl"
    return /Mac|iPhone|iPad/i.test(navigator.platform) ? "⌘" : "Ctrl"
  }, [])
  const busyLabel =
    busyElapsedSeconds >= 18
      ? t("create.building_checking_elapsed", { seconds: busyElapsedSeconds })
      : busyElapsedSeconds > 0
      ? t("create.building_elapsed", { seconds: busyElapsedSeconds })
      : t("create.building_label")
  const busyStageIndex = Math.min(
    BUSY_STAGE_KEYS.length - 1,
    Math.max(0, Math.floor(busyElapsedSeconds / 3)),
  )
  const primaryCtaLabel = busy
    ? t("create.cta_busy")
    : briefBusy
      ? t("create.brief_cta_busy")
      : activeBrief
        ? canGenerateFromBrief
          ? t("create.brief_cta_generate")
          : t("create.brief_cta_blocked")
        : hasSeed
          ? t("create.brief_cta_idle")
          : t("create.cta_empty")

  const ensureAuthorSession = async (): Promise<boolean> => {
    if (!auth.isAnonymous) return true
    if (auth.loading) {
      setError(t("create.error_guest_loading"))
      return false
    }
    if (!guestHandleRef.current) {
      guestHandleRef.current = makeGuestHandle()
    }
    try {
      await auth.login(guestHandleRef.current)
      return true
    } catch (err) {
      setError(friendlyError(err, t("create.error_guest_failed")))
      return false
    }
  }

  useEffect(() => {
    if (!busy) {
      setBusyElapsedSeconds(0)
      return
    }
    setBusyElapsedSeconds(0)
    const startedAt = Date.now()
    const id = window.setInterval(() => {
      setBusyElapsedSeconds(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => window.clearInterval(id)
  }, [busy])

  const handleCreate = async () => {
    const trimmed = seed.trim()
    if (!trimmed) {
      setError(t("create.error_seed_required"))
      return
    }
    if (inflightRef.current) return
    inflightRef.current = true
    setBusy(true)
    setError(null)
    try {
      const authorReady = await ensureAuthorSession()
      if (!authorReady) {
        setBusy(false)
        inflightRef.current = false
        return
      }
      const response = await api.createNarrativeTemplate({
        seed: trimmed,
        visibility,
        turn_budget: turnBudget,
        difficulty,
        language: storyLanguage,
        story_brief: activeBriefResponse?.can_generate ? activeBriefResponse.brief : null,
      })
      onSessionStarted(response.session.session_id)
    } catch (err) {
      setError(friendlyError(err, t("create.error_create_failed")))
      setBusy(false)
      inflightRef.current = false
    }
    // Note: on success we deliberately leave inflightRef=true; the navigate
    // unmounts this component anyway, and locking it prevents any late
    // re-render race.
  }

  const handlePlanStory = async () => {
    const trimmed = seed.trim()
    if (!trimmed) {
      setError(t("create.error_seed_required"))
      return
    }
    if (briefBusy || busy) return
    setBriefBusy(true)
    setBriefError(null)
    setError(null)
    try {
      const authorReady = await ensureAuthorSession()
      if (!authorReady) return
      const response = await api.createNarrativeStoryBrief({
        seed: trimmed,
        language: storyLanguage,
        desired_tension_profile:
          desiredTensionProfile === "auto" ? null : desiredTensionProfile,
      })
      setBriefResponse(response)
      setBriefResponseKey(briefKey(trimmed, storyLanguage, desiredTensionProfile))
    } catch (err) {
      setBriefError(friendlyError(err, t("create.brief_error_failed")))
    } finally {
      setBriefBusy(false)
    }
  }

  const handleApplyRevisionAction = (seedAppend: string) => {
    setSeed((current) => {
      const trimmed = current.trim()
      if (trimmed.toLowerCase().includes(seedAppend.toLowerCase())) return current
      return `${trimmed}${trimmed ? "\n\n" : ""}${seedAppend}`
    })
    setCorrectionCount((current) => current + 1)
    setChatMessages((current) => [
      ...current,
      {
        id: `user-revision-action-${Date.now()}`,
        speaker: "user",
        text: seedAppend,
      },
      {
        id: `guide-revision-action-${Date.now()}`,
        speaker: "guide",
        text: t("create.guide_reply_revision"),
      },
    ])
    setBriefResponse(null)
    setBriefResponseKey(null)
    setBriefError(null)
    window.requestAnimationFrame(() => seedTextareaRef.current?.focus())
  }

  const appendGuideTurn = (rawText: string) => {
    const trimmed = rawText.trim()
    if (!trimmed) {
      setError(t("create.error_seed_required"))
      return
    }
    const hadSeed = Boolean(seed.trim())
    const nextCorrectionCount = hadSeed ? correctionCount + 1 : correctionCount
    const nextSeed = `${seed.trim()}${hadSeed ? "\n\n" : ""}${trimmed}`
    setSeed(nextSeed)
    if (hadSeed) setCorrectionCount(nextCorrectionCount)
    setDraftTurn("")
    setError(null)
    setBriefResponse(null)
    setBriefResponseKey(null)
    setBriefError(null)
    setChatMessages((current) => [
      ...current,
      {
        id: `user-${Date.now()}-${current.length}`,
        speaker: "user",
        text: trimmed,
      },
      {
        id: `guide-${Date.now()}-${current.length}`,
        speaker: "guide",
        text: hadSeed ? t("create.guide_reply_revision") : t("create.guide_reply_seed"),
      },
    ])
  }

  const handlePrimaryAction = async () => {
    if (activeBrief) {
      if (!canGenerateFromBrief) return
      await handleCreate()
      return
    }
    await handlePlanStory()
  }

  return (
    <div style={{ ...cpStyles.page, ...(compactLayout ? cpStyles.pageCompact : null) }}>
      <header style={cpStyles.header}>
        <button style={cpStyles.brandLink} onClick={onBackHome}>
          <span
            style={{
              color: "var(--accent)",
              fontSize: 22,
              lineHeight: 1,
              transform: "translateY(-2px)",
              display: "inline-block",
            }}
          >
            ·
          </span>
          <span style={cpStyles.brandName}>Tiny Stories</span>
        </button>
      </header>

      <main style={{ ...cpStyles.main, ...(compactLayout ? cpStyles.mainCompact : null) }}>
        <motion.div
          style={{ ...cpStyles.inner, ...(compactLayout ? cpStyles.innerCompact : null) }}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={itemTransition}
        >
          <span className="ts-tag" style={cpStyles.kicker}>{t("create.tag_new")}</span>
          <h1 style={{ ...cpStyles.title, ...(compactLayout ? cpStyles.titleCompact : null) }}>
            {t("create.heading_l1")}
            <br />
            {t("create.heading_l2")}
          </h1>
          <p style={{ ...cpStyles.sub, ...(compactLayout ? cpStyles.subCompact : null) }}>
            {t("create.subhead")}
          </p>
          <p style={{ ...cpStyles.promptFitHint, ...(compactLayout ? cpStyles.promptFitHintCompact : null) }}>
            {t("create.prompt_fit_hint")}
          </p>

          <div style={{ ...cpStyles.guideTranscript, ...(compactLayout ? cpStyles.guideTranscriptCompact : null) }}>
            {guideMessages.map((message) => (
              <div
                key={message.id}
                style={{
                  ...cpStyles.guideMessage,
                  ...(message.speaker === "user" ? cpStyles.guideMessageUser : cpStyles.guideMessageGuide),
                }}
              >
                <span style={cpStyles.guideSpeaker}>
                  {message.speaker === "user" ? t("create.guide_user_label") : t("create.guide_agent_label")}
                </span>
                <span style={cpStyles.guideMessageText}>{message.text}</span>
              </div>
            ))}
          </div>

          <div style={cpStyles.textareaWrap}>
            <textarea
              ref={seedTextareaRef}
              style={{
                ...cpStyles.textarea,
                ...(compactLayout ? cpStyles.textareaCompact : {}),
              }}
              placeholder={compactLayout ? t("create.guide_input_placeholder_short") : t("create.guide_input_placeholder")}
              value={draftTurn}
              onChange={(e) => {
                setDraftTurn(e.target.value)
                setError(null)
              }}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault()
                  void handlePrimaryAction()
                  return
                }
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  appendGuideTurn(draftTurn)
                }
              }}
              spellCheck={false}
              disabled={busy || briefBusy}
            />
            <div style={{ ...cpStyles.composerBar, ...(compactLayout ? cpStyles.composerBarCompact : null) }}>
              <span style={cpStyles.composerHint}>{t("create.guide_input_hint")}</span>
              <button
                type="button"
                style={cpStyles.composerAction}
                disabled={!draftTurn.trim() || busy || briefBusy}
                onClick={() => appendGuideTurn(draftTurn)}
              >
                {hasSeed ? t("create.guide_add_correction") : t("create.guide_add_opening")}
              </button>
            </div>
          </div>
          <div style={cpStyles.editorMeta}>
            <span style={cpStyles.count}>{t("create.char_count", { n: seed.length })}</span>
            {correctionCount > 0 ? (
              <span style={cpStyles.count}>{t("create.guide_revision_count", { n: correctionCount })}</span>
            ) : null}
            {showCreateAction && !compactLayout ? (
              <span style={cpStyles.shortcutHint}>
                {t("create.submit_shortcut", { mod: submitModKey })}
              </span>
            ) : null}
          </div>

          <div style={{ ...cpStyles.draftLedger, ...(compactLayout ? cpStyles.draftLedgerCompact : null) }}>
            <span style={cpStyles.draftLedgerLabel}>{t("create.guide_draft_label")}</span>
            {hasSeed ? (
              <p style={cpStyles.draftLedgerText}>{seed}</p>
            ) : (
              <p style={cpStyles.draftLedgerEmpty}>{t("create.guide_draft_empty")}</p>
            )}
          </div>

          {error ? <div style={cpStyles.error}>{error}</div> : null}
          {briefError ? <div style={cpStyles.error}>{briefError}</div> : null}
          {activeBriefResponse ? (
            <StoryBriefCard
              brief={activeBriefResponse.brief}
              canGenerate={activeBriefResponse.can_generate}
              nextStep={activeBriefResponse.next_step}
              compact={compactLayout}
              onApplyRevisionAction={handleApplyRevisionAction}
            />
          ) : null}

          <div
            style={{
              ...cpStyles.actions,
              ...(compactLayout ? cpStyles.actionsCompact : null),
            }}
          >
            <AnimatePresence initial={false}>
              {showCreateAction ? (
                <motion.button
                  key="create-submit"
                  style={{
                    ...cpStyles.primaryAction,
                    opacity: !hasSeed || busy || briefBusy || (activeBrief !== null && !canGenerateFromBrief) ? 0.5 : 1,
                    pointerEvents: !hasSeed || busy || briefBusy || (activeBrief !== null && !canGenerateFromBrief) ? "none" : "auto",
                    ...(compactLayout ? cpStyles.primaryCtaCompact : null),
                  }}
                  disabled={!hasSeed || busy || briefBusy || (activeBrief !== null && !canGenerateFromBrief)}
                  onClick={() => void handlePrimaryAction()}
                  type="button"
                  initial={{ opacity: 0, y: -4, height: 0, marginTop: 0 }}
                  animate={{ opacity: !hasSeed || busy || briefBusy || (activeBrief !== null && !canGenerateFromBrief) ? 0.5 : 1, y: 0, height: "auto", marginTop: 0 }}
                  exit={{ opacity: 0, y: -4, height: 0, marginTop: 0 }}
                  transition={itemTransition}
                >
                  {primaryCtaLabel}
                </motion.button>
              ) : null}
            </AnimatePresence>
            {!compactLayout && activeBrief && !busy && !briefBusy ? (
              <button
                style={cpStyles.backAction}
                onClick={() => void handlePlanStory()}
                type="button"
              >
                {t("create.brief_replan")}
              </button>
            ) : null}
            {!compactLayout && showBackAction ? (
              <button style={cpStyles.backAction} onClick={onBackHome} disabled={busy || briefBusy} type="button">
                {t("create.cta_back")}
              </button>
            ) : null}
          </div>

          <AnimatePresence initial={false}>
            {showSeedExamples ? (
              <motion.div
                key="seed-examples"
                style={{
                  ...cpStyles.examplesBlock,
                  ...(compactLayout ? cpStyles.examplesBlockCompact : null),
                }}
                initial={{ opacity: 0, y: -4, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, y: 0, height: "auto", marginBottom: 24 }}
                exit={{ opacity: 0, y: -4, height: 0, marginBottom: 0 }}
                transition={itemTransition}
              >
                <span style={cpStyles.examplesLabel}>{t("create.examples_label")}</span>
                <div
                  style={{
                    ...cpStyles.examplesList,
                    ...(compactLayout ? cpStyles.examplesListCompact : null),
                  }}
                >
                  {visibleSeedExamples.map((example, index) => (
                    <button
                      key={example}
                      style={cpStyles.exampleLine}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        appendGuideTurn(example)
                        window.requestAnimationFrame(() => {
                          const node = seedTextareaRef.current
                          if (!node) return
                          node.focus({ preventScroll: true })
                        })
                      }}
                      disabled={busy}
                      type="button"
                    >
                      <span style={cpStyles.exampleLineIndex}>{index + 1}.</span>
                      <span style={cpStyles.exampleLineText}>{example}</span>
                      <span style={cpStyles.exampleLineUse}>{t("create.example_use")}</span>
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <details
            style={{
              ...cpStyles.settingsDetails,
              ...(!showSeedExamples ? cpStyles.settingsDetailsFocused : null),
            }}
            open={settingsOpen}
            onToggle={(event) => setSettingsOpen(event.currentTarget.open)}
          >
            <summary style={cpStyles.settingsSummary}>
              <span style={cpStyles.settingsSummaryMain}>
                <span style={cpStyles.settingsSummaryLabel}>{t("create.settings_label")}</span>
                <span style={cpStyles.settingsSummaryValue}>{settingsSummary}</span>
              </span>
              <span style={cpStyles.settingsToggleHint}>
                {settingsOpen ? t("create.settings_done") : t("create.settings_edit")}
              </span>
            </summary>
            <div
              style={{
                ...cpStyles.settingsStrip,
                ...(compactLayout ? cpStyles.settingsStripCompact : null),
              }}
              aria-label={t("create.settings_label")}
            >
              <div
                style={{
                  ...cpStyles.settingGroup,
                  ...(compactLayout ? cpStyles.settingGroupCompact : null),
                }}
              >
                <span style={cpStyles.settingLabel}>{t("create.field_budget")}</span>
                <div style={cpStyles.segmentRow}>
                  {BUDGET_OPTIONS.map((o) => (
                    <button
                      key={o.budget}
                      style={{
                        ...cpStyles.segmentBtn,
                        ...(turnBudget === o.budget ? cpStyles.segmentBtnActive : null),
                      }}
                      onClick={() => setTurnBudget(o.budget)}
                      disabled={busy}
                      type="button"
                      title={t(o.descKey)}
                      aria-pressed={turnBudget === o.budget}
                    >
                      <span style={cpStyles.segmentMain}>{t(o.labelKey)}</span>
                      <span style={cpStyles.segmentMeta}>{t(o.timeKey)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div
                style={{
                  ...cpStyles.settingGroup,
                  ...(compactLayout ? cpStyles.settingGroupCompact : null),
                }}
              >
                <span style={cpStyles.settingLabel}>{t("create.field_difficulty")}</span>
                <div style={cpStyles.segmentRow}>
                  {DIFFICULTY_OPTIONS.map((o) => (
                    <button
                      key={o.id}
                      style={{
                        ...cpStyles.segmentBtn,
                        ...(difficulty === o.id ? cpStyles.segmentBtnActive : null),
                        ...(o.id === "gauntlet" && difficulty === o.id ? cpStyles.segmentBtnWarn : null),
                      }}
                      onClick={() => setDifficulty(o.id)}
                      disabled={busy}
                      type="button"
                      title={t(o.descKey)}
                      aria-pressed={difficulty === o.id}
                    >
                      <span style={cpStyles.segmentMain}>{t(o.labelKey)}</span>
                      <span style={cpStyles.segmentMeta}>{t(o.taglineKey)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div
                style={{
                  ...cpStyles.settingGroup,
                  ...(compactLayout ? cpStyles.settingGroupCompact : null),
                }}
              >
                <span style={cpStyles.settingLabel}>{t("create.field_story_lang")}</span>
                <div style={cpStyles.segmentRow}>
                  {STORY_LANGUAGE_OPTIONS[uiLang].map((o) => (
                    <button
                      key={o.id}
                      style={{
                        ...cpStyles.segmentBtn,
                        ...(storyLanguage === o.id ? cpStyles.segmentBtnActive : null),
                      }}
                      onClick={() => setStoryLanguage(o.id)}
                      disabled={busy || briefBusy}
                      type="button"
                      title={o.desc}
                      aria-pressed={storyLanguage === o.id}
                    >
                      <span style={cpStyles.segmentMain}>{o.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div
                style={{
                  ...cpStyles.settingGroup,
                  ...(compactLayout ? cpStyles.settingGroupCompact : null),
                }}
              >
                <span style={cpStyles.settingLabel}>{t("create.field_tension_profile")}</span>
                <div style={cpStyles.segmentRow}>
                  {TENSION_PROFILE_OPTIONS.map((o) => (
                    <button
                      key={o.id}
                      style={{
                        ...cpStyles.segmentBtn,
                        ...(desiredTensionProfile === o.id ? cpStyles.segmentBtnActive : null),
                      }}
                      onClick={() => setDesiredTensionProfile(o.id)}
                      disabled={busy || briefBusy}
                      type="button"
                      title={t(o.descKey)}
                      aria-pressed={desiredTensionProfile === o.id}
                    >
                      <span style={cpStyles.segmentMain}>{t(o.labelKey)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div
                style={{
                  ...cpStyles.settingGroup,
                  ...(compactLayout ? cpStyles.settingGroupCompact : null),
                }}
              >
                <span style={cpStyles.settingLabel}>{t("create.field_visibility")}</span>
                <div style={cpStyles.segmentRow}>
                  {VISIBILITY_OPTION_IDS.map((id) => {
                    const meta = VISIBILITY_KEY_MAP[id]
                    return (
                      <button
                        key={id}
                        style={{
                          ...cpStyles.segmentBtn,
                          ...(visibility === id ? cpStyles.segmentBtnActive : null),
                        }}
                        onClick={() => setVisibility(id)}
                        disabled={busy}
                        type="button"
                        title={t(meta.descKey)}
                        aria-pressed={visibility === id}
                      >
                        <span style={cpStyles.segmentMain}>{t(meta.labelKey)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          </details>

          <AnimatePresence>
            {busy ? (
              <motion.div
                key="busy"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={itemTransition}
                style={cpStyles.busyCard}
              >
                <div style={cpStyles.busySignal}>
                  <span style={cpStyles.busyLabel}>{busyLabel}</span>
                  <span style={cpStyles.busySignalLine} aria-hidden />
                </div>
                <BusyStages activeIndex={busyStageIndex} compact={compactLayout} />
                <BusyTip />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </motion.div>
      </main>
    </div>
  )
}

function useCompactLayout(query = "(max-width: 720px)") {
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

function BusyStages({ activeIndex, compact }: { activeIndex: number; compact: boolean }) {
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

function BusyTip() {
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

function StoryBriefCard({
  brief,
  canGenerate,
  nextStep,
  compact,
  onApplyRevisionAction,
}: {
  brief: NarrativeStoryBrief
  canGenerate: boolean
  nextStep: string
  compact: boolean
  onApplyRevisionAction: (seedAppend: string) => void
}) {
  const t = useT()
  const primary = brief.cast_plan.primary_active_entities
  const secondary = brief.cast_plan.secondary_background_entities
  const omitted = brief.cast_plan.omitted_entities
  const decisions = brief.constraint_dispositions.slice(0, 8)
  const surfacedConstraints = brief.constraints
    .map((item) => item.label)
    .filter((label) => label.toLowerCase() !== "core premise")
    .slice(0, 4)

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
      <div style={{ ...cpStyles.briefMetaGrid, ...(compact ? cpStyles.briefMetaGridCompact : null) }}>
        <BriefField label={t("create.brief_profile")} value={t(TENSION_PROFILE_LABEL_KEYS[brief.tension_profile])} />
        <BriefField label={t("create.brief_kernel")} value={brief.story_kernel} />
        <BriefField label={t("create.brief_card_mechanic")} value={brief.intervention_card_label} />
      </div>
      <BriefEntityList
        label={t("create.brief_primary_cast")}
        items={primary.map((entity) => ({ label: entity.display_name, detail: entity.rationale }))}
        empty={t("create.brief_empty")}
      />
      {surfacedConstraints.length > 0 ? (
        <BriefList
          label={t("create.brief_key_details")}
          items={surfacedConstraints}
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
}: {
  label: string
  items: { label: string; detail: string }[]
  empty: string
}) {
  return (
    <div style={cpStyles.briefList}>
      <span style={cpStyles.briefFieldLabel}>{label}</span>
      <div style={cpStyles.briefStackedList}>
        {items.length > 0 ? items.map((item) => (
          <span key={item.label} style={cpStyles.briefStackedItem}>
            <strong>{item.label}</strong>
            <span>{item.detail}</span>
          </span>
        )) : <span style={cpStyles.briefListValue}>{empty}</span>}
      </div>
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

const busyTipStyles: Record<string, CSSProperties> = {
  tip: {
    fontSize: 13,
    color: "rgba(245,210,140,0.92)",
    lineHeight: 1.55,
    fontStyle: "italic" as const,
    textAlign: "left" as const,
    fontFamily: "var(--font-narrative)",
  },
}

const busyStageStyles: Record<string, CSSProperties> = {
  rail: {
    width: "100%",
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 0,
    borderTop: "1px solid rgba(255,255,255,0.12)",
    borderBottom: "1px solid rgba(255,255,255,0.09)",
  },
  railCompact: {
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  },
  stage: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    gap: 6,
    padding: "8px 10px 8px 0",
    color: "rgba(255,255,255,0.42)",
    borderTop: "1px solid transparent",
    transform: "translateY(-1px)",
  },
  stageCompact: {
    padding: "7px 8px 7px 0",
  },
  stageActive: {
    color: "rgba(255,226,178,0.96)",
    borderTop: "1px solid rgba(245,200,120,0.76)",
  },
  stageComplete: {
    color: "rgba(255,255,255,0.68)",
  },
  stageMark: {
    flex: "0 0 auto",
    width: 13,
    fontSize: 10,
    lineHeight: 1,
    fontWeight: 820,
    color: "rgba(245,200,120,0.72)",
    fontFamily: "var(--font-ui)",
  },
  stageText: {
    minWidth: 0,
    fontSize: 11,
    lineHeight: 1.25,
    fontWeight: 720,
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
}

const cpStyles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100%",
    background: `linear-gradient(90deg, rgba(4,4,7,0.98) 0%, rgba(8,6,9,0.94) 48%, rgba(22,5,8,0.78) 100%), radial-gradient(circle at 82% 18%, rgba(201,44,32,0.24) 0%, rgba(201,44,32,0.08) 28%, transparent 52%), linear-gradient(180deg, rgba(5,5,8,0.26) 0%, rgba(8,6,8,0.88) 68%, var(--bg) 100%), url(${PAGE_BG.create})`,
    backgroundSize: "cover",
    backgroundPosition: "58% center",
    backgroundAttachment: "fixed",
  },
  pageCompact: {
    backgroundPosition: "64% top",
    backgroundAttachment: "scroll",
  },
  header: {
    padding: "18px 40px",
    borderBottom: "1px solid rgba(255,255,255,0.1)",
    color: "white",
  },
  brandLink: { display: "inline-flex", alignItems: "center", gap: 8 },
  brandName: { fontFamily: "var(--font-narrative)", fontSize: 17 },

  main: { padding: "72px 40px 80px", display: "flex", justifyContent: "center" },
  mainCompact: {
    padding: "48px 40px 72px",
  },
  inner: { width: "100%", maxWidth: 720 },
  innerCompact: {
    maxWidth: 520,
  },

  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 40,
    lineHeight: 1.15,
    letterSpacing: 0,
    fontWeight: 400,
    marginTop: 0,
    marginRight: 0,
    marginBottom: 16,
    marginLeft: 0,
    color: "white",
    textShadow: "0 2px 18px rgba(0,0,0,0.5)",
  },
  titleCompact: {
    fontSize: 36,
    lineHeight: 1.13,
    marginBottom: 14,
  },
  kicker: {
    display: "inline-block",
    marginBottom: 28,
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: 0,
    letterSpacing: 0,
    textTransform: "none",
  },
  sub: {
    fontSize: 16,
    lineHeight: 1.55,
    color: "rgba(255,255,255,0.78)",
    marginTop: 0,
    marginRight: 0,
    marginBottom: 10,
    marginLeft: 0,
  },
  subCompact: {
    fontSize: 15.5,
    lineHeight: 1.52,
    marginBottom: 10,
  },
  promptFitHint: {
    maxWidth: 620,
    marginTop: 0,
    marginRight: 0,
    marginBottom: 30,
    marginLeft: 0,
    color: "rgba(245,210,140,0.92)",
    fontSize: 13,
    lineHeight: 1.45,
    fontWeight: 650,
  },
  promptFitHintCompact: {
    marginBottom: 24,
    fontSize: 12.5,
    lineHeight: 1.42,
  },
  guideTranscript: {
    display: "grid",
    gap: 0,
    marginBottom: 16,
    borderTop: "1px solid rgba(245,200,120,0.28)",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
    background: "linear-gradient(180deg, rgba(12,12,16,0.58), rgba(12,12,16,0.18))",
    backdropFilter: "blur(10px)",
  },
  guideTranscriptCompact: {
    marginBottom: 14,
  },
  guideMessage: {
    display: "grid",
    gridTemplateColumns: "96px minmax(0, 1fr)",
    gap: 14,
    padding: "12px 0",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
  },
  guideMessageGuide: {
    color: "rgba(255,245,230,0.88)",
  },
  guideMessageUser: {
    color: "rgba(255,226,178,0.96)",
  },
  guideSpeaker: {
    color: "rgba(245,200,120,0.72)",
    fontSize: 11,
    lineHeight: 1.35,
    fontWeight: 820,
    textTransform: "uppercase" as const,
    letterSpacing: 0.03,
  },
  guideMessageText: {
    minWidth: 0,
    fontFamily: "var(--font-narrative)",
    fontSize: 14,
    lineHeight: 1.52,
    whiteSpace: "pre-wrap" as const,
  },

  textareaWrap: {
    position: "relative",
    marginBottom: 7,
    borderTop: "1px solid rgba(255,255,255,0.13)",
    borderBottom: "1px solid rgba(245,200,120,0.28)",
    background: "rgba(12,12,16,0.46)",
    backdropFilter: "blur(12px)",
  },
  editorMeta: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 18,
    color: "rgba(255,255,255,0.44)",
    fontSize: 11,
    lineHeight: 1.25,
    letterSpacing: 0,
  },
  examplesBlock: {
    display: "grid",
    gridTemplateColumns: "104px minmax(0, 1fr)",
    alignItems: "start",
    columnGap: 18,
    rowGap: 10,
    marginBottom: 24,
  },
  examplesBlockCompact: {
    gridTemplateColumns: "1fr",
    rowGap: 8,
  },
  examplesLabel: {
    fontSize: 12,
    color: "rgba(255,255,255,0.62)",
    letterSpacing: 0,
    lineHeight: 1.45,
  },
  examplesList: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    columnGap: 18,
    rowGap: 6,
  },
  examplesListCompact: {
    gridTemplateColumns: "1fr",
  },
  exampleLine: {
    width: "100%",
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "20px minmax(0, 1fr) auto",
    alignItems: "baseline",
    columnGap: 7,
    rowGap: 2,
    padding: "5px 0 6px",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    color: "rgba(255,255,255,0.76)",
    cursor: "pointer",
    fontFamily: "var(--font-narrative)",
    textAlign: "left" as const,
  },
  exampleLineIndex: {
    color: "rgba(245,200,120,0.68)",
    fontFamily: "var(--font-ui)",
    fontSize: 11,
    lineHeight: 1.25,
    fontWeight: 780,
  },
  exampleLineText: {
    minWidth: 0,
    color: "rgba(255,255,255,0.78)",
    fontSize: 12.6,
    lineHeight: 1.42,
  },
  exampleLineUse: {
    color: "rgba(245,200,120,0.76)",
    fontFamily: "var(--font-ui)",
    fontSize: 10.5,
    lineHeight: 1.25,
    fontWeight: 780,
    whiteSpace: "nowrap" as const,
  },
  textarea: {
    width: "100%",
    minHeight: 94,
    padding: "13px 0 10px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 0,
    fontFamily: "var(--font-narrative)",
    fontSize: 16,
    lineHeight: 1.65,
    color: "var(--text)",
    resize: "vertical",
    outline: "none",
    transition: "border-color 200ms",
  },
  textareaCompact: {
    minHeight: 86,
    padding: "10px 0 12px",
    fontSize: 15,
  },
  composerBar: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 14,
    padding: "8px 0 11px",
  },
  composerBarCompact: {
    alignItems: "flex-start",
    flexDirection: "column" as const,
    gap: 8,
  },
  composerHint: {
    color: "rgba(255,255,255,0.46)",
    fontSize: 11.5,
    lineHeight: 1.35,
  },
  composerAction: {
    flex: "0 0 auto",
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.38)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,226,178,0.96)",
    fontSize: 12.5,
    fontWeight: 850,
    lineHeight: 1.25,
    cursor: "pointer",
  },
  count: {
    fontSize: 11,
    color: "rgba(255,255,255,0.44)",
    letterSpacing: 0,
  },
  shortcutHint: {
    color: "rgba(245,200,120,0.66)",
    fontSize: 11,
    fontWeight: 720,
    whiteSpace: "nowrap" as const,
  },
  draftLedger: {
    display: "grid",
    gap: 6,
    marginBottom: 18,
    padding: "11px 0 12px",
    borderTop: "1px solid rgba(255,255,255,0.10)",
    borderBottom: "1px solid rgba(255,255,255,0.10)",
  },
  draftLedgerCompact: {
    marginBottom: 16,
  },
  draftLedgerLabel: {
    color: "rgba(245,200,120,0.78)",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 820,
  },
  draftLedgerText: {
    margin: 0,
    color: "rgba(255,245,230,0.84)",
    fontFamily: "var(--font-narrative)",
    fontSize: 13.4,
    lineHeight: 1.5,
    whiteSpace: "pre-wrap" as const,
  },
  draftLedgerEmpty: {
    margin: 0,
    color: "rgba(255,255,255,0.48)",
    fontSize: 12.5,
    lineHeight: 1.45,
  },

  settingsStrip: {
    display: "grid",
    gridTemplateColumns: "1fr",
    rowGap: 12,
    padding: "12px 0 2px",
    marginBottom: 0,
  },
  settingsStripCompact: {
    gridTemplateColumns: "1fr",
    rowGap: 13,
  },
  settingGroup: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "116px minmax(0, 1fr)",
    alignItems: "baseline",
    columnGap: 14,
    rowGap: 8,
  },
  settingGroupCompact: {
    gridTemplateColumns: "minmax(0, 1fr)",
    rowGap: 6,
  },
  settingLabel: {
    color: "rgba(255,255,255,0.54)",
    fontSize: 11.5,
    lineHeight: 1.1,
    fontWeight: 680,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  segmentRow: {
    minWidth: 0,
    display: "flex",
    flexWrap: "wrap" as const,
    alignItems: "baseline",
    columnGap: 12,
    rowGap: 8,
  },
  segmentBtn: {
    minWidth: 0,
    padding: "0 0 5px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.16)",
    borderRadius: 0,
    color: "rgba(255,255,255,0.72)",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 5,
    fontFamily: "inherit",
    textAlign: "left" as const,
    cursor: "pointer",
  },
  segmentBtnActive: {
    color: "white",
    borderBottom: "1px solid rgba(245,200,120,0.72)",
  },
  segmentBtnWarn: {
    borderBottom: "1px solid rgba(220,108,74,0.72)",
  },
  segmentMain: {
    fontSize: 13,
    lineHeight: 1.25,
    fontWeight: 750,
    whiteSpace: "nowrap" as const,
  },
  segmentMeta: {
    color: "rgba(245,200,120,0.82)",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 650,
    whiteSpace: "nowrap" as const,
  },

  settingsDetails: {
    marginTop: 16,
    borderTop: "none",
  },
  settingsDetailsFocused: {
    marginTop: 4,
  },
  settingsSummary: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: 16,
    padding: "8px 0",
    cursor: "pointer",
    listStyle: "none",
    color: "rgba(255,255,255,0.86)",
  },
  settingsSummaryMain: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    gap: 10,
    flexWrap: "wrap" as const,
  },
  settingsSummaryLabel: {
    color: "rgba(255,255,255,0.52)",
    fontSize: 11.5,
    fontWeight: 680,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  settingsSummaryValue: {
    minWidth: 0,
    color: "rgba(255,245,230,0.82)",
    fontSize: 12.5,
    lineHeight: 1.35,
  },
  settingsToggleHint: {
    color: "rgba(245,200,120,0.84)",
    fontSize: 11,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none" as const,
  },

  fieldLabel: {
    fontSize: 12,
    color: "var(--text-muted)",
    letterSpacing: 0,
    textTransform: "none",
    marginBottom: 12,
  },

  visibility: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
    gap: "0 24px",
    marginBottom: 32,
    borderTop: "1px solid rgba(255,255,255,0.14)",
  },
  optionGridCompact: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 0,
    marginBottom: 28,
    borderTop: "1px solid rgba(255,255,255,0.14)",
  },
  visBtn: {
    textAlign: "left",
    padding: "16px 18px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.14)",
    borderRadius: 0,
    color: "var(--text)",
    cursor: "pointer",
    transition: "border-color 180ms, color 180ms",
  },
  visBtnActive: {
    background: "transparent",
    borderBottom: "1px solid rgba(245,200,120,0.72)",
    color: "white",
  },
  visBtnLabel: { fontSize: 15, fontWeight: 600, marginBottom: 6 },
  visBtnDesc: { fontSize: 12, color: "var(--text-muted)", lineHeight: 1.4 },
  budgetTime: {
    fontSize: 12,
    color: "var(--accent)",
    fontWeight: 500,
  },

  difficultyRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "0 24px",
    marginBottom: 32,
    borderTop: "1px solid rgba(255,255,255,0.14)",
  },
  difficultyBtn: {
    textAlign: "left",
    padding: "16px 18px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(255,255,255,0.14)",
    borderRadius: 0,
    color: "rgba(255,255,255,0.86)",
    cursor: "pointer",
    transition: "border-color 180ms, color 180ms",
  },
  difficultyBtnActive: {
    background: "transparent",
    borderBottom: "1px solid rgba(245,200,120,0.72)",
    color: "white",
  },
  difficultyBtnGauntlet: {
    borderBottom: "1px solid #dc6b4a",
  },
  difficultyBtnLabel: {
    fontSize: 15,
    fontWeight: 600,
    marginBottom: 6,
  },
  difficultyBtnTagline: {
    fontSize: 12,
    color: "var(--accent)",
    fontWeight: 500,
  },
  difficultyBtnDesc: {
    fontSize: 12,
    color: "rgba(255,255,255,0.62)",
    lineHeight: 1.45,
  },

  error: { marginBottom: 16, fontSize: 13, color: "var(--warn)" },
  briefRail: {
    marginTop: 6,
    marginBottom: 20,
    padding: "14px 0 12px",
    borderTop: "1px solid rgba(245,200,120,0.28)",
    borderBottom: "1px solid rgba(255,255,255,0.12)",
    color: "rgba(255,255,255,0.82)",
  },
  briefRailCompact: {
    marginBottom: 18,
  },
  briefHeader: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 8,
  },
  briefEyebrow: {
    color: "rgba(245,200,120,0.82)",
    fontSize: 11.5,
    lineHeight: 1.2,
    fontWeight: 820,
    letterSpacing: 0,
  },
  briefFitPill: {
    color: "rgba(194,255,212,0.86)",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 780,
    whiteSpace: "nowrap" as const,
  },
  briefBetaNote: {
    color: "rgba(245,210,140,0.78)",
    fontSize: 11.5,
    lineHeight: 1.42,
    marginBottom: 8,
  },
  briefFitPillWarn: {
    color: "rgba(255,170,132,0.92)",
  },
  briefPremise: {
    marginTop: 0,
    marginRight: 0,
    marginBottom: 12,
    marginLeft: 0,
    color: "rgba(255,245,230,0.9)",
    fontSize: 14,
    lineHeight: 1.52,
    fontFamily: "var(--font-narrative)",
  },
  briefMetaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: "12px 18px",
    marginBottom: 13,
  },
  briefMetaGridCompact: {
    gridTemplateColumns: "1fr",
    gap: "8px 0",
  },
  briefField: {
    minWidth: 0,
    display: "grid",
    gap: 3,
  },
  briefFieldLabel: {
    color: "rgba(255,255,255,0.48)",
    fontSize: 10.5,
    lineHeight: 1.15,
    fontWeight: 760,
    letterSpacing: 0,
  },
  briefFieldValue: {
    color: "rgba(255,255,255,0.82)",
    fontSize: 12,
    lineHeight: 1.36,
  },
  briefCastGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "10px 20px",
    marginBottom: 12,
  },
  briefCastGridCompact: {
    gridTemplateColumns: "1fr",
  },
  briefDetails: {
    marginTop: 11,
    marginBottom: 12,
    paddingTop: 9,
    borderTop: "1px solid rgba(255,255,255,0.10)",
  },
  briefDetailsSummary: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 12,
    color: "rgba(245,200,120,0.84)",
    fontSize: 11.5,
    lineHeight: 1.3,
    fontWeight: 780,
    cursor: "pointer",
    listStyle: "none",
    padding: "2px 0 9px",
  },
  briefDetailsTitle: {
    color: "rgba(255,255,255,0.44)",
    fontWeight: 650,
  },
  briefList: {
    minWidth: 0,
    display: "grid",
    gap: 3,
  },
  briefListValue: {
    color: "rgba(255,255,255,0.76)",
    fontSize: 12.5,
    lineHeight: 1.38,
  },
  briefStackedList: {
    display: "grid",
    gap: 6,
  },
  briefStackedItem: {
    display: "grid",
    gap: 2,
    color: "rgba(255,255,255,0.62)",
    fontSize: 11.4,
    lineHeight: 1.32,
  },
  briefPlanSection: {
    display: "grid",
    gap: 5,
    marginBottom: 10,
  },
  briefPlanItems: {
    display: "grid",
    gap: 5,
  },
  briefPlanItem: {
    display: "grid",
    gap: 2,
    color: "rgba(255,255,255,0.62)",
    fontSize: 11.4,
    lineHeight: 1.32,
  },
  briefConstraintRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "6px 8px",
    marginBottom: 11,
  },
  briefConstraintChip: {
    display: "inline-flex",
    alignItems: "baseline",
    gap: 5,
    maxWidth: "100%",
    color: "rgba(255,255,255,0.74)",
    fontSize: 11.5,
    lineHeight: 1.25,
    borderBottom: "1px solid rgba(255,255,255,0.13)",
    paddingBottom: 3,
  },
  briefConstraintKind: {
    color: "rgba(245,200,120,0.72)",
    fontSize: 10,
    fontWeight: 800,
  },
  briefWarningBlock: {
    display: "grid",
    gap: 4,
    marginBottom: 11,
  },
  briefWarningLine: {
    color: "rgba(255,170,132,0.95)",
    fontSize: 12,
    lineHeight: 1.38,
  },
  briefSuggestionLine: {
    color: "rgba(245,210,140,0.86)",
    fontSize: 12,
    lineHeight: 1.38,
  },
  briefRevisionActions: {
    display: "grid",
    gap: 7,
    marginBottom: 11,
  },
  briefRevisionActionRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 7,
  },
  briefRevisionAction: {
    border: "1px solid rgba(245,200,120,0.32)",
    borderRadius: 6,
    background: "rgba(245,200,120,0.07)",
    color: "rgba(255,238,210,0.88)",
    fontSize: 11.5,
    fontWeight: 760,
    lineHeight: 1.2,
    padding: "6px 8px",
    cursor: "pointer",
  },
  briefFooter: {
    display: "grid",
    gap: 3,
    color: "rgba(255,255,255,0.58)",
    fontSize: 11.5,
    lineHeight: 1.42,
  },
  actions: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 18,
    rowGap: 8,
    flexWrap: "wrap",
    marginBottom: 24,
  },
  actionsCompact: {
    alignItems: "baseline",
    marginBottom: 20,
  },
  primaryAction: {
    width: "fit-content",
    minHeight: 34,
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.34)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,226,178,0.96)",
    fontSize: 14,
    fontWeight: 880,
    lineHeight: 1.25,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  backAction: {
    height: "auto",
    padding: "3px 0",
    border: "none",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(255,255,255,0.56)",
    fontSize: 13,
    fontWeight: 700,
    lineHeight: 1.3,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  primaryCtaCompact: {
    width: "fit-content",
    minWidth: 0,
  },
  busyHint: {
    marginTop: 24,
    fontSize: 13,
    color: "var(--text-faint)",
    lineHeight: 1.5,
  },
  busyCard: {
    marginTop: 24,
    padding: "12px 0 0",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-start",
    gap: 8,
    minHeight: 0,
  },
  busySignal: {
    display: "inline-flex",
    alignItems: "center",
    gap: 10,
    color: "rgba(255,226,178,0.92)",
    width: "100%",
  },
  busyLabel: {
    fontSize: 11.5,
    lineHeight: 1.2,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  busySignalLine: {
    height: 1,
    flex: "1 1 auto",
    background: "linear-gradient(90deg, rgba(245,200,120,0.56), rgba(245,200,120,0.04))",
    transform: "translateY(1px)",
  },
}
