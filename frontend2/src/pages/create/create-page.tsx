import { type CSSProperties, type ReactNode, useEffect, useMemo, useRef, useState } from "react"
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
import { getStoryStartIntent, type StoryStartIntentId } from "../../shared/lib/story-start-intents"
import { GENERATED_ASSETS, PAGE_BG } from "../../shared/lib/webtoon-assets"

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

type LocalFitBlocker = {
  rationale: string
  actions: Array<{
    actionId: string
    label: string
    description: string
    seedAppend: string
  }>
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
  startIntentId,
}: {
  onBackHome: () => void
  onSessionStarted: (sessionId: string) => void
  startIntentId?: StoryStartIntentId
}) {
  const api = useApi()
  const auth = useAuth()
  const { lang: uiLang } = useLanguage()
  const t = useT()
  const compactLayout = useCompactLayout()
  const [seed, setSeed] = useState("")
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
  const [submittedSeed, setSubmittedSeed] = useState<string | null>(null)
  const [localFitBlocker, setLocalFitBlocker] = useState<LocalFitBlocker | null>(null)
  const seedTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const appliedStartIntentRef = useRef<StoryStartIntentId | null>(null)
  // Synchronous lock to prevent duplicate creates if the user manages to
  // double-click before React flushes setBusy(true). useState alone doesn't
  // guarantee that — React batches state updates, so two clicks within
  // ~16ms can both pass the `busy` check and fire two requests.
  const inflightRef = useRef(false)

  const seedExamples = useMemo(() => SEED_EXAMPLE_KEYS.map((k) => t(k)), [t])
  const selectedStartIntent = useMemo(() => getStoryStartIntent(startIntentId), [startIntentId])
  const visibleSeedExamples = compactLayout ? seedExamples.slice(0, 3) : seedExamples
  const hasSeed = Boolean(seed.trim())
  const currentBriefKey = briefKey(seed, storyLanguage, desiredTensionProfile)
  const activeBriefResponse =
    briefResponse && briefResponseKey === currentBriefKey ? briefResponse : null
  const activeBrief = activeBriefResponse?.brief ?? null
  const activeRevisionDirection =
    activeBriefResponse?.brief.revision_actions[0]?.description ??
    activeBriefResponse?.next_step ??
    null
  const localRevisionDirection =
    localFitBlocker?.actions[0]?.description ?? t("create.guide_not_fit_revision_fallback")
  const canGenerateFromBrief = Boolean(activeBriefResponse?.can_generate)
  const showBackAction = hasSeed || busy || briefBusy
  const showSeedExamples = !hasSeed && !busy && !briefBusy
  const showComposerPrimary = !activeBriefResponse && !localFitBlocker
  const selectedBudget = BUDGET_OPTIONS.find((o) => o.budget === turnBudget) ?? BUDGET_OPTIONS[1]
  const selectedDifficulty = DIFFICULTY_OPTIONS.find((o) => o.id === difficulty) ?? DIFFICULTY_OPTIONS[0]
  const selectedLanguage =
    STORY_LANGUAGE_OPTIONS[uiLang].find((o) => o.id === storyLanguage) ?? STORY_LANGUAGE_OPTIONS[uiLang][0]
  const selectedVisibility = VISIBILITY_KEY_MAP[visibility]
  const selectedTension =
    TENSION_PROFILE_OPTIONS.find((o) => o.id === desiredTensionProfile) ?? TENSION_PROFILE_OPTIONS[0]
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
  const busyPhase = busyElapsedSeconds >= 36
    ? "reliable"
    : busyElapsedSeconds >= 18
      ? "checking"
      : busyElapsedSeconds > 0
        ? "drafting"
        : "starting"
  const busyLabel = busyPhase === "reliable"
    ? t("create.building_reliable_elapsed", { seconds: busyElapsedSeconds })
    : busyPhase === "checking"
      ? t("create.building_checking_elapsed", { seconds: busyElapsedSeconds })
      : busyPhase === "drafting"
        ? t("create.building_elapsed", { seconds: busyElapsedSeconds })
        : t("create.building_label")
  const busyStageIndex = busyElapsedSeconds >= 48
    ? 3
    : busyElapsedSeconds >= 36
      ? 2
      : busyElapsedSeconds >= 18
        ? 1
        : 0
  const primaryCtaLabel = busy
    ? t("create.cta_busy")
    : briefBusy
      ? t("create.brief_cta_busy")
      : localFitBlocker
        ? t("create.brief_cta_blocked")
      : activeBrief
        ? canGenerateFromBrief
          ? t("create.brief_cta_generate")
          : t("create.brief_cta_blocked")
        : hasSeed
          ? t("create.brief_cta_idle")
          : t("create.cta_empty")

  const resetGuideResult = () => {
    setBriefResponse(null)
    setBriefResponseKey(null)
    setBriefError(null)
    setSubmittedSeed(null)
    setLocalFitBlocker(null)
  }

  const detectLocalFitBlocker = (rawSeed: string): LocalFitBlocker | null => {
    const lower = rawSeed.toLowerCase()
    const utilitySignals = [
      "meal plan",
      "grocery",
      "macro",
      "recipe",
      "workout",
      "itinerary",
      "study plan",
      "budget spreadsheet",
      "translate",
      "summarize",
      "explain",
      "debug",
      "resume",
      "cover letter",
      "weekly plan",
      "购物清单",
      "菜单",
      "食谱",
      "健身计划",
      "旅行计划",
      "翻译",
      "总结",
      "解释",
      "简历",
    ]
    const storySignals = [
      "ex",
      "rival",
      "family",
      "parent",
      "parents",
      "friend",
      "witness",
      "volunteer",
      "deadline",
      "secret",
      "vote",
      "gala",
      "wedding",
      "board",
      "betray",
      "recording",
      "contract",
      "conflict",
      "bake sale",
      "judging",
      "judge",
      "disappeared",
      "disappear",
      "missing",
      "need to figure out",
      "前任",
      "家人",
      "朋友",
      "秘密",
      "投票",
      "婚礼",
      "合同",
      "冲突",
    ]
    const utilityHit = utilitySignals.some((signal) => lower.includes(signal))
    const storySignalCount = storySignals.reduce((count, signal) => count + (lower.includes(signal) ? 1 : 0), 0)
    if (!utilityHit || storySignalCount >= 2) return null
    return {
      rationale: t("create.local_blocker_utility"),
      actions: [
        {
          actionId: "add_cast_deadline",
          label: t("create.local_action_cast_deadline_label"),
          description: t("create.local_action_cast_deadline_desc"),
          seedAppend: t("create.local_action_cast_deadline_append"),
        },
        {
          actionId: "add_public_conflict",
          label: t("create.local_action_conflict_label"),
          description: t("create.local_action_conflict_desc"),
          seedAppend: t("create.local_action_conflict_append"),
        },
      ],
    }
  }

  // Author flow requires a real account.
  useEffect(() => {
    if (auth.loading) return
    if (auth.isAnonymous) {
      const next = selectedStartIntent ? `create?intent=${selectedStartIntent.id}` : "create"
      const params = new URLSearchParams({ next })
      window.location.hash = `#/login?${params.toString()}`
    }
  }, [auth.loading, auth.isAnonymous, selectedStartIntent])

  useEffect(() => {
    if (!selectedStartIntent) return
    if (appliedStartIntentRef.current === selectedStartIntent.id) return
    appliedStartIntentRef.current = selectedStartIntent.id
    const presetSeed = selectedStartIntent.seedDraft[uiLang] ?? selectedStartIntent.seedDraft.en
    setSeed(presetSeed)
    setStoryLanguage(uiLang)
    setDesiredTensionProfile(selectedStartIntent.tensionProfile)
    setError(null)
    resetGuideResult()
  }, [selectedStartIntent, uiLang])

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
    const localBlocker = detectLocalFitBlocker(trimmed)
    if (localBlocker) {
      setSubmittedSeed(trimmed)
      setLocalFitBlocker(localBlocker)
      setBriefResponse(null)
      setBriefResponseKey(null)
      setBriefError(null)
      setError(null)
      return
    }
    setBriefBusy(true)
    setSubmittedSeed(trimmed)
    setBriefError(null)
    setError(null)
    try {
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
    resetGuideResult()
    window.requestAnimationFrame(() => seedTextareaRef.current?.focus())
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
    <div style={cpStyles.page}>
      <header style={{ ...cpStyles.header, ...(compactLayout ? cpStyles.headerCompact : null) }}>
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
          <section style={{ ...cpStyles.agentHero, ...(compactLayout ? cpStyles.agentHeroCompact : null) }}>
            <div style={{ ...cpStyles.heroCopy, ...(compactLayout ? cpStyles.heroCopyCompact : null) }}>
              <span className="ts-tag" style={cpStyles.kicker}>{t("create.tag_new")}</span>
              <h1 style={{ ...cpStyles.title, ...(compactLayout ? cpStyles.titleCompact : null) }}>
                {t("create.heading_l1")}
                <br />
                {t("create.heading_l2")}
              </h1>
              <p style={{ ...cpStyles.sub, ...(compactLayout ? cpStyles.subCompact : null) }}>
                {t("create.subhead")}
              </p>
            </div>
            <div style={{ ...cpStyles.agentSignalPanel, ...(compactLayout ? cpStyles.agentSignalPanelCompact : null) }}>
              <span style={cpStyles.agentSignalKicker}>{t("create.brief_card_label")}</span>
              <strong style={cpStyles.agentSignalTitle}>
                {activeBrief
                  ? t(canGenerateFromBrief ? "create.brief_footer_ready" : "create.brief_revise_first")
                  : localFitBlocker
                    ? t("create.brief_revise_first")
                  : briefBusy
                    ? t("create.brief_cta_busy")
                    : t("create.brief_cta_idle")}
              </strong>
              <span style={cpStyles.agentSignalLine}>{settingsSummary}</span>
              <div style={cpStyles.agentSignalMetaGrid}>
                <span style={cpStyles.agentSignalMetaItem}>
                  <span style={cpStyles.agentSignalMetaLabel}>{t("create.field_budget")}</span>
                  <strong>{t(selectedBudget.labelKey)}</strong>
                </span>
                <span style={cpStyles.agentSignalMetaItem}>
                  <span style={cpStyles.agentSignalMetaLabel}>{t("create.field_difficulty")}</span>
                  <strong>{t(selectedDifficulty.labelKey)}</strong>
                </span>
                <span style={cpStyles.agentSignalMetaItem}>
                  <span style={cpStyles.agentSignalMetaLabel}>{t("create.field_story_lang")}</span>
                  <strong>{selectedLanguage.label}</strong>
                </span>
              </div>
            </div>
          </section>

          <section style={{ ...cpStyles.workspace, ...(compactLayout ? cpStyles.workspaceCompact : null) }}>
            <div style={{ ...cpStyles.conversationPanel, ...(compactLayout ? cpStyles.conversationPanelCompact : null) }}>
              <div style={cpStyles.guideWorkbenchStrip} aria-hidden>
                <span style={cpStyles.guideWorkbenchTrack} />
                <span style={cpStyles.guideWorkbenchMeter} />
                <span style={cpStyles.guideWorkbenchMeterAlt} />
              </div>
              <div style={cpStyles.threadTop}>
                <span style={cpStyles.threadEyebrow}>{t("create.prompt_fit_hint")}</span>
                <span style={cpStyles.threadState}>
                  {briefBusy
                    ? t("create.brief_cta_busy")
                    : localFitBlocker
                      ? t("create.brief_not_fit")
                      : activeBrief
                        ? t(FIT_STATUS_LABEL_KEYS[activeBrief.runtime_fit_status])
                  : t("create.brief_cta_idle")}
                </span>
              </div>

              {selectedStartIntent ? (
                <div
                  style={{ ...cpStyles.presetPanel, ...(compactLayout ? cpStyles.presetPanelCompact : null) }}
                  data-story-start-intent={selectedStartIntent.id}
                >
                  <div
                    style={{
                      ...cpStyles.presetArt,
                      backgroundImage: `linear-gradient(180deg, rgba(6,7,10,0.04) 0%, rgba(6,7,10,0.78) 92%), url(${selectedStartIntent.image})`,
                    }}
                    aria-hidden
                  />
                  <div style={cpStyles.presetBody}>
                    <span style={cpStyles.presetKicker}>{t("create.preset_kicker")}</span>
                    <strong style={cpStyles.presetTitle}>{t(selectedStartIntent.titleKey)}</strong>
                    <div style={cpStyles.presetMetaGrid}>
                      <span style={cpStyles.presetMetaItem}>
                        <span>{t("create.preset_mood_label")}</span>
                        <strong>{t(selectedStartIntent.moodKey)}</strong>
                      </span>
                      <span style={cpStyles.presetMetaItem}>
                        <span>{t("create.preset_pressure_label")}</span>
                        <strong>{t(selectedStartIntent.pressureKey)}</strong>
                      </span>
                    </div>
                    <span style={cpStyles.presetRule}>{t(selectedStartIntent.ruleKey)}</span>
                    <span style={cpStyles.presetHook}>{t("create.preset_hook_label")} · {t(selectedStartIntent.hookKey)}</span>
                    <button
                      type="button"
                      style={cpStyles.presetAction}
                      disabled={briefBusy || busy || !hasSeed}
                      onClick={() => void handlePlanStory()}
                    >
                      {t("create.preset_shape_cta")}
                    </button>
                  </div>
                </div>
              ) : null}

              <div style={cpStyles.messageStack}>
                <div style={cpStyles.guideMessage}>
                  <span style={cpStyles.messageSpeaker}>{t("create.tag_new")}</span>
                  <strong style={cpStyles.messageTitle}>{t("create.guide_initial_title")}</strong>
                  <p style={cpStyles.messageText}>{t("create.guide_initial_body")}</p>
                </div>
                {submittedSeed ? (
                  <div style={cpStyles.userMessage}>
                    <span style={cpStyles.messageSpeaker}>{t("create.user_message_label")}</span>
                    <p style={cpStyles.messageText}>{submittedSeed}</p>
                  </div>
                ) : null}
              </div>

              <div style={cpStyles.composerDock}>
                <div style={cpStyles.textareaWrap}>
                  <textarea
                    ref={seedTextareaRef}
                    style={{
                      ...cpStyles.textarea,
                      ...(compactLayout ? cpStyles.textareaCompact : {}),
                    }}
                    placeholder={compactLayout ? t("create.placeholder_short") : t("create.placeholder")}
                    value={seed}
                    onChange={(e) => {
                      setSeed(e.target.value)
                      setError(null)
                      resetGuideResult()
                    }}
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                        e.preventDefault()
                        void handlePrimaryAction()
                      }
                    }}
                    spellCheck={false}
                    disabled={busy || briefBusy}
                  />
                </div>
                <div style={cpStyles.editorMeta}>
                  <span style={cpStyles.count}>{t("create.char_count", { n: seed.length })}</span>
                  {showComposerPrimary && !compactLayout ? (
                    <span style={cpStyles.shortcutHint}>
                      {t("create.submit_shortcut", { mod: submitModKey })}
                    </span>
                  ) : null}
                </div>
              </div>

              {error ? <div style={cpStyles.error}>{error}</div> : null}
              {briefError ? (
                <div style={{ ...cpStyles.guideMessage, ...cpStyles.guideMessageBlocked }}>
                  <span style={cpStyles.messageSpeaker}>{t("create.tag_new")}</span>
                  <strong style={cpStyles.messageTitle}>{t("create.guide_error_title")}</strong>
                  <p style={cpStyles.messageText}>{briefError}</p>
                </div>
              ) : null}

              {localFitBlocker ? (
                <div style={{ ...cpStyles.guideMessage, ...cpStyles.guideMessageResult, ...cpStyles.guideMessageRevise }}>
                  <span style={cpStyles.messageSpeaker}>{t("create.tag_new")}</span>
                  <strong style={cpStyles.messageTitle}>{t("create.guide_not_fit_title")}</strong>
                  <div style={cpStyles.notFitPanel}>
                    <p style={cpStyles.messageText}>
                      <strong>{t("create.guide_not_fit_unsupported_label")}</strong>{" "}
                      {localFitBlocker.rationale}
                    </p>
                    <p style={cpStyles.messageText}>
                      <strong>{t("create.guide_not_fit_supported_label")}</strong>{" "}
                      {t("create.guide_not_fit_supported_shape")}
                    </p>
                    <p style={cpStyles.messageText}>
                      <strong>{t("create.guide_not_fit_revision_label")}</strong>{" "}
                      {localRevisionDirection}
                    </p>
                    <p style={cpStyles.messageText}>{t("create.guide_not_fit_next_step")}</p>
                  </div>
                  <div style={cpStyles.briefRevisionActions} aria-label={t("create.brief_revision_actions")}>
                    <span style={cpStyles.briefFieldLabel}>{t("create.brief_revision_actions")}</span>
                    <div style={cpStyles.briefRevisionActionRow}>
                      {localFitBlocker.actions.map((action) => (
                        <button
                          key={action.actionId}
                          type="button"
                          style={cpStyles.briefRevisionAction}
                          title={action.description}
                          onClick={() => handleApplyRevisionAction(action.seedAppend)}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}

              <AnimatePresence initial={false}>
                {briefBusy ? (
                  <motion.div
                    key="guide-thinking"
                    style={cpStyles.guideThinking}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={itemTransition}
                  >
                    <span style={cpStyles.messageSpeaker}>{t("create.tag_new")}</span>
                    <strong style={cpStyles.messageTitle}>{t("create.guide_planning_title")}</strong>
                    <span style={cpStyles.thinkingPulse}>{t("create.guide_planning_body")}</span>
                  </motion.div>
                ) : null}
              </AnimatePresence>

              {activeBriefResponse ? (
                <div
                  style={{
                    ...cpStyles.guideMessage,
                    ...cpStyles.guideMessageResult,
                    ...(activeBriefResponse.can_generate ? cpStyles.guideMessageSuccess : cpStyles.guideMessageRevise),
                  }}
                >
                  <span style={cpStyles.messageSpeaker}>{t("create.tag_new")}</span>
                  <strong style={cpStyles.messageTitle}>
                    {t(activeBriefResponse.can_generate ? "create.guide_supported_title" : "create.guide_not_fit_title")}
                  </strong>
                  {activeBriefResponse.can_generate ? (
                    <p style={cpStyles.messageText}>{t("create.guide_supported_body")}</p>
                  ) : (
                    <div style={cpStyles.notFitPanel}>
                      <p style={cpStyles.messageText}>
                        <strong>{t("create.guide_not_fit_unsupported_label")}</strong>{" "}
                        {activeBriefResponse.brief.runtime_fit_rationale}
                      </p>
                      <p style={cpStyles.messageText}>
                        <strong>{t("create.guide_not_fit_supported_label")}</strong>{" "}
                        {t("create.guide_not_fit_supported_shape")}
                      </p>
                      <p style={cpStyles.messageText}>
                        <strong>{t("create.guide_not_fit_revision_label")}</strong>{" "}
                        {activeRevisionDirection}
                      </p>
                      <p style={cpStyles.messageText}>{t("create.guide_not_fit_next_step")}</p>
                    </div>
                  )}
                  <StoryBriefCard
                    brief={activeBriefResponse.brief}
                    canGenerate={activeBriefResponse.can_generate}
                    compact={compactLayout}
                    onGenerate={() => void handleCreate()}
                    onApplyRevisionAction={handleApplyRevisionAction}
                  />
                </div>
              ) : null}

              <div
                style={{
                  ...cpStyles.actions,
                  ...(compactLayout ? cpStyles.actionsCompact : null),
                }}
              >
                <AnimatePresence initial={false}>
                  {showComposerPrimary ? (
                    <motion.button
                      key="create-submit"
                      style={{
                        ...cpStyles.primaryAction,
                        opacity: !hasSeed || busy || briefBusy ? 0.5 : 1,
                        pointerEvents: !hasSeed || busy || briefBusy ? "none" : "auto",
                        ...(compactLayout ? cpStyles.primaryCtaCompact : null),
                      }}
                      disabled={!hasSeed || busy || briefBusy}
                      onClick={() => void handlePrimaryAction()}
                      type="button"
                      initial={{ opacity: 0, y: -4, height: 0, marginTop: 0 }}
                      animate={{ opacity: !hasSeed || busy || briefBusy ? 0.5 : 1, y: 0, height: "auto", marginTop: 0 }}
                      exit={{ opacity: 0, y: -4, height: 0, marginTop: 0 }}
                      transition={itemTransition}
                    >
                      {primaryCtaLabel}
                    </motion.button>
                  ) : null}
                </AnimatePresence>
                {activeBrief && !busy && !briefBusy ? (
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
                    animate={{ opacity: 1, y: 0, height: "auto", marginBottom: 0 }}
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
                            setSeed(example)
                            resetGuideResult()
                            window.requestAnimationFrame(() => {
                              const node = seedTextareaRef.current
                              if (!node) return
                              node.focus({ preventScroll: true })
                              node.setSelectionRange(example.length, example.length)
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
            </div>

            <aside style={{ ...cpStyles.controlPanel, ...(compactLayout ? cpStyles.controlPanelCompact : null) }}>
              <div style={cpStyles.controlArt} aria-hidden />
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
                      onClick={() => {
                        setStoryLanguage(o.id)
                        resetGuideResult()
                      }}
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
                      onClick={() => {
                        setDesiredTensionProfile(o.id)
                        resetGuideResult()
                      }}
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

              <div style={cpStyles.contractPanel}>
                <span style={cpStyles.contractKicker}>{t("create.brief_profile")}</span>
                <strong style={cpStyles.contractTitle}>{t(selectedTension.labelKey)}</strong>
                <span style={cpStyles.contractLine}>{t(selectedDifficulty.taglineKey)}</span>
                <span style={cpStyles.contractLine}>{t(selectedVisibility.descKey)}</span>
              </div>

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
            </aside>
          </section>
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
  "create.busy_stage_drafting",
  "create.busy_stage_checking",
  "create.busy_stage_reliable",
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
  compact,
  onGenerate,
  onApplyRevisionAction,
}: {
  brief: NarrativeStoryBrief
  canGenerate: boolean
  compact: boolean
  onGenerate: () => void
  onApplyRevisionAction: (seedAppend: string) => void
}) {
  const t = useT()
  const primary = brief.cast_plan.primary_active_entities
  const secondary = brief.cast_plan.secondary_background_entities
  const omitted = brief.cast_plan.omitted_entities
  const decisions = brief.constraint_dispositions.slice(0, 8)
  const collapseSupportedDetails = canGenerate && !compact
  const collapseNotFitDetails = brief.runtime_fit_status === "not_fit" && !compact
  const primaryCast = (
    <BriefEntityList
      label={t("create.brief_primary_cast")}
      items={primary.map((entity) => ({ label: entity.display_name, detail: entity.rationale }))}
      empty={t("create.brief_empty")}
    />
  )
  const metaFields = (
    <div style={{ ...cpStyles.briefMetaGrid, ...(compact ? cpStyles.briefMetaGridCompact : null) }}>
      <BriefField label={t("create.brief_profile")} value={t(TENSION_PROFILE_LABEL_KEYS[brief.tension_profile])} />
      <BriefField label={t("create.brief_kernel")} value={brief.story_kernel} />
      <BriefField label={t("create.brief_card_mechanic")} value={brief.intervention_card_label} />
    </div>
  )
  const secondaryCast = (
    <BriefEntityList
      label={t("create.brief_secondary_cast")}
      items={secondary.map((entity) => ({ label: entity.display_name, detail: entity.rationale }))}
      empty={t("create.brief_empty")}
    />
  )
  const omittedCast = omitted.length > 0 ? (
    <BriefPlanSection
      label={t("create.brief_omitted_cast")}
      items={omitted.map((entity) => ({ label: entity.display_name, rationale: entity.rationale }))}
      empty={t("create.brief_empty")}
    />
  ) : null
  const planDetails = (
    <>
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
    </>
  )
  const warningBlock = brief.warnings.length > 0 || brief.revision_suggestions.length > 0 ? (
    <div style={cpStyles.briefWarningBlock}>
      {brief.warnings.slice(0, 3).map((warning) => (
        <div key={warning} style={cpStyles.briefWarningLine}>{warning}</div>
      ))}
      {brief.revision_suggestions.slice(0, 2).map((suggestion) => (
        <div key={suggestion} style={cpStyles.briefSuggestionLine}>{suggestion}</div>
      ))}
    </div>
  ) : null
  const revisionActions = brief.revision_actions.length > 0 ? (
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
  ) : null

  return (
    <section style={{ ...cpStyles.briefRail, ...(compact ? cpStyles.briefRailCompact : null) }}>
      <span style={cpStyles.briefTape} aria-hidden />
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
      {canGenerate ? (
        <div style={{ ...cpStyles.briefReadyDock, ...(compact ? cpStyles.briefReadyDockCompact : null) }}>
          <div style={cpStyles.briefReadyCopy}>
            <strong style={cpStyles.briefReadyTitle}>{t("create.brief_ready_title")}</strong>
            <span style={cpStyles.briefReadyHint}>{t("create.brief_ready_hint")}</span>
          </div>
          <button
            type="button"
            style={{ ...cpStyles.briefInlineGenerate, ...(compact ? cpStyles.briefInlineGenerateCompact : null) }}
            onClick={onGenerate}
          >
            {t("create.brief_cta_generate")}
          </button>
        </div>
      ) : null}
      <div style={cpStyles.briefLeadPanel}>
        <p style={cpStyles.briefIntro}>
          {t(canGenerate ? "create.brief_card_intro_ready" : "create.brief_card_intro_blocked")}
        </p>
        <p style={cpStyles.briefPremise}>{brief.premise_summary}</p>
        <div style={cpStyles.briefBetaNote}>{brief.adaptation_note}</div>
      </div>
      {compact ? (
        <>
          <div style={cpStyles.briefPrimaryCompact}>
            {primaryCast}
          </div>
          <BriefDetailsDisclosure label={t("create.brief_details_toggle")}>
            {metaFields}
            {secondaryCast}
            {omittedCast}
            {planDetails}
          </BriefDetailsDisclosure>
        </>
      ) : (
        <>
          {collapseNotFitDetails ? null : metaFields}
          {collapseSupportedDetails ? (
            <>
              <div style={cpStyles.briefPrimaryCompact}>
                {primaryCast}
              </div>
              <BriefDetailsDisclosure label={t("create.brief_details_toggle")}>
                {secondaryCast}
                {omittedCast}
                {planDetails}
                {warningBlock}
                {revisionActions}
              </BriefDetailsDisclosure>
            </>
          ) : collapseNotFitDetails ? (
            <>
              <div style={cpStyles.briefPrimaryCompact}>
                {primaryCast}
              </div>
              {warningBlock}
              {revisionActions}
              <BriefDetailsDisclosure label={t("create.brief_details_toggle")}>
                {metaFields}
                {secondaryCast}
                {omittedCast}
                {planDetails}
              </BriefDetailsDisclosure>
            </>
          ) : (
            <>
              <div style={cpStyles.briefCastGrid}>
                {primaryCast}
                {secondaryCast}
              </div>
              {omittedCast}
              {planDetails}
            </>
          )}
        </>
      )}
      {collapseSupportedDetails || collapseNotFitDetails ? null : warningBlock}
      {collapseSupportedDetails || collapseNotFitDetails ? null : revisionActions}
      <div style={cpStyles.briefFooter}>
        <span>{canGenerate ? t("create.brief_footer_ready_hint") : brief.runtime_fit_rationale}</span>
        <strong>{canGenerate ? t("create.brief_footer_ready") : t("create.brief_revise_first")}</strong>
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

function BriefDetailsDisclosure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details style={cpStyles.briefDetailDisclosure}>
      <summary style={cpStyles.briefDetailSummary}>{label}</summary>
      <div style={cpStyles.briefDetailBody}>{children}</div>
    </details>
  )
}

const busyTipStyles: Record<string, CSSProperties> = {
  tip: {
    fontSize: 13,
    color: "var(--text-muted)",
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
    borderTop: "1px solid var(--line)",
    borderBottom: "1px solid var(--line)",
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
    color: "var(--text-faint)",
    borderTop: "1px solid transparent",
    transform: "translateY(-1px)",
  },
  stageCompact: {
    padding: "7px 8px 7px 0",
  },
  stageActive: {
    color: "var(--text)",
    borderTop: "1px solid rgba(208,138,79,0.68)",
  },
  stageComplete: {
    color: "var(--text-muted)",
  },
  stageMark: {
    flex: "0 0 auto",
    width: 13,
    fontSize: 10,
    lineHeight: 1,
    fontWeight: 820,
    color: "rgba(208,138,79,0.8)",
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
    background:
      `radial-gradient(circle at 74% 16%, rgba(208,138,79,0.18), transparent 30%), radial-gradient(circle at 14% 88%, rgba(148,164,109,0.12), transparent 28%), linear-gradient(90deg, rgba(7,8,12,0.98) 0%, rgba(7,8,12,0.86) 45%, rgba(7,8,12,0.58) 100%), linear-gradient(180deg, rgba(7,8,12,0.02) 0%, var(--bg) 88%), url(${PAGE_BG.create})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
    backgroundAttachment: "fixed",
  },
  header: {
    padding: "18px 40px",
    borderBottom: "1px solid rgba(245,200,120,0.14)",
    color: "var(--text)",
    background: "rgba(7,8,12,0.78)",
    backdropFilter: "blur(16px)",
  },
  headerCompact: {
    padding: "16px 18px",
  },
  brandLink: { display: "inline-flex", alignItems: "center", gap: 8 },
  brandName: { fontFamily: "var(--font-narrative)", fontSize: 17 },

  main: { padding: "34px 40px 86px", display: "flex", justifyContent: "center" },
  mainCompact: {
    padding: "18px 12px 54px",
  },
  inner: {
    width: "100%",
    maxWidth: 1220,
    padding: "0",
    color: "var(--text)",
    background: "transparent",
    border: "none",
    borderRadius: 0,
    boxShadow: "none",
    transform: "none",
    overflow: "visible",
  },
  innerCompact: {
    maxWidth: 520,
    padding: "0",
    transform: "none",
  },
  agentHero: {
    minHeight: 332,
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(330px, 0.42fr)",
    gap: 0,
    position: "relative" as const,
    overflow: "hidden",
    background:
      `linear-gradient(90deg, rgba(6,7,10,0.98) 0%, rgba(6,7,10,0.86) 48%, rgba(6,7,10,0.34) 100%), linear-gradient(180deg, rgba(6,7,10,0.03), rgba(6,7,10,0.82)), url(${PAGE_BG.create})`,
    backgroundSize: "cover",
    backgroundPosition: "center 42%",
    border: "1px solid rgba(245,200,120,0.18)",
    borderRadius: "var(--radius-scene)",
    boxShadow: "0 40px 120px rgba(0,0,0,0.52), inset 0 1px 0 rgba(255,255,255,0.08)",
  },
  agentHeroCompact: {
    gridTemplateColumns: "1fr",
    minHeight: 0,
    borderRadius: "var(--radius-scene-mobile)",
  },
  heroCopy: {
    padding: "58px 52px 70px",
    maxWidth: 700,
  },
  heroCopyCompact: {
    padding: "34px 20px 30px",
  },
  agentSignalPanel: {
    alignSelf: "stretch",
    minWidth: 0,
    display: "grid",
    alignContent: "end",
    gap: 11,
    padding: "42px 34px 40px",
    borderLeft: "1px solid rgba(245,200,120,0.14)",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.014)), rgba(7,8,12,0.68)",
    backdropFilter: "blur(14px)",
    borderRadius: "0 var(--radius-scene) var(--radius-scene) 0",
  },
  agentSignalPanelCompact: {
    borderLeft: "none",
    borderTop: "1px solid rgba(245,200,120,0.12)",
    padding: "18px 20px 20px",
    borderRadius: "0 0 var(--radius-scene-mobile) var(--radius-scene-mobile)",
  },
  agentSignalKicker: {
    color: "rgba(245,200,120,0.82)",
    fontFamily: "var(--font-mono)",
    fontSize: 10.5,
    lineHeight: 1.25,
    fontWeight: 780,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
  },
  agentSignalTitle: {
    color: "rgba(255,250,242,0.96)",
    fontSize: 19,
    lineHeight: 1.26,
    fontWeight: 720,
  },
  agentSignalLine: {
    color: "rgba(244,239,230,0.58)",
    fontSize: 12.5,
    lineHeight: 1.45,
  },
  agentSignalMetaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 0,
    marginTop: 6,
    borderTop: "1px solid rgba(245,200,120,0.14)",
    borderBottom: "1px solid rgba(245,200,120,0.10)",
  },
  agentSignalMetaItem: {
    minWidth: 0,
    display: "grid",
    gap: 4,
    padding: "11px 10px 12px",
    borderRight: "1px solid rgba(245,200,120,0.10)",
  },
  agentSignalMetaLabel: {
    color: "rgba(244,239,230,0.44)",
    fontSize: 10.5,
    lineHeight: 1.15,
    fontWeight: 700,
  },
  workspace: {
    position: "relative" as const,
    zIndex: 2,
    marginTop: -46,
    padding: "0 24px",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(300px, 360px)",
    gap: 18,
    alignItems: "start",
  },
  workspaceCompact: {
    gridTemplateColumns: "1fr",
    marginTop: 12,
    padding: 0,
    gap: 12,
  },
  conversationPanel: {
    minWidth: 0,
    padding: "26px 28px 30px",
    display: "grid",
    gap: 17,
    position: "relative" as const,
    overflow: "hidden",
    background:
      "linear-gradient(180deg, rgba(9,10,14,0.94), rgba(7,8,12,0.97)), radial-gradient(circle at 86% 0%, rgba(208,138,79,0.16), transparent 30%), linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0) 40%)",
    backgroundSize: "cover",
    backgroundPosition: "center",
    border: "1px solid rgba(245,200,120,0.17)",
    borderLeft: "3px solid rgba(208,138,79,0.62)",
    borderRadius: "var(--radius-panel)",
    boxShadow: "0 30px 90px rgba(0,0,0,0.44), inset 0 1px 0 rgba(255,255,255,0.07)",
  },
  conversationPanelCompact: {
    padding: "18px 14px 22px",
  },
  controlPanel: {
    minWidth: 0,
    padding: "24px 22px 26px",
    border: "1px solid rgba(245,200,120,0.15)",
    borderTop: "3px solid rgba(148,164,109,0.40)",
    borderRadius: "var(--radius-panel)",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.018)), rgba(8,9,13,0.78)",
    boxShadow: "0 24px 76px rgba(0,0,0,0.36), inset 0 1px 0 rgba(255,255,255,0.06)",
  },
  controlPanelCompact: {
    padding: "18px 14px 22px",
  },
  controlArt: {
    minHeight: 148,
    marginBottom: 22,
    backgroundImage:
      `linear-gradient(180deg, rgba(8,9,13,0.04), rgba(8,9,13,0.76)), url(${GENERATED_ASSETS.createWorkspace})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
    border: "1px solid rgba(245,200,120,0.14)",
    borderRadius: "var(--radius-panel)",
    boxShadow: "0 18px 54px rgba(0,0,0,0.32)",
  },
  threadTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    gap: 14,
    paddingBottom: 12,
    borderBottom: "1px solid rgba(245,200,120,0.10)",
  },
  guideWorkbenchStrip: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) 80px 46px",
    alignItems: "center",
    gap: 10,
    padding: "0 0 11px",
    borderBottom: "1px solid rgba(245,200,120,0.08)",
  },
  guideWorkbenchTrack: {
    height: 2,
    background: "linear-gradient(90deg, rgba(245,200,120,0.48), rgba(245,200,120,0.07))",
  },
  guideWorkbenchMeter: {
    height: 6,
    background: "linear-gradient(90deg, rgba(148,164,109,0.86) 0 54%, rgba(255,255,255,0.12) 54% 100%)",
  },
  guideWorkbenchMeterAlt: {
    height: 6,
    background: "linear-gradient(90deg, rgba(208,138,79,0.82) 0 72%, rgba(255,255,255,0.12) 72% 100%)",
  },
  threadEyebrow: {
    color: "rgba(245,200,120,0.82)",
    fontSize: 12,
    lineHeight: 1.45,
    fontWeight: 700,
  },
  threadState: {
    color: "var(--text-faint)",
    fontFamily: "var(--font-mono)",
    fontSize: 10.5,
    lineHeight: 1.25,
    fontWeight: 760,
    letterSpacing: "0.05em",
    textTransform: "uppercase" as const,
    whiteSpace: "nowrap" as const,
  },
  presetPanel: {
    display: "grid",
    gridTemplateColumns: "minmax(170px, 0.34fr) minmax(0, 1fr)",
    minHeight: 206,
    border: "1px solid rgba(245,200,120,0.16)",
    borderLeft: "3px solid rgba(208,138,79,0.64)",
    borderRadius: "var(--radius-door)",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.07), rgba(255,255,255,0) 46%), rgba(5,6,10,0.40)",
    boxShadow: "0 18px 56px rgba(0,0,0,0.28)",
    overflow: "hidden",
  },
  presetPanelCompact: {
    gridTemplateColumns: "1fr",
    minHeight: 0,
  },
  presetArt: {
    minHeight: 206,
    backgroundSize: "cover",
    backgroundPosition: "center",
  },
  presetBody: {
    minWidth: 0,
    display: "grid",
    alignContent: "center",
    gap: 9,
    padding: "20px 20px 21px",
  },
  presetKicker: {
    color: "rgba(245,200,120,0.82)",
    fontFamily: "var(--font-mono)",
    fontSize: 10.5,
    lineHeight: 1.2,
    fontWeight: 800,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
  },
  presetTitle: {
    color: "rgba(255,250,242,0.97)",
    fontFamily: "var(--font-narrative)",
    fontSize: 22,
    lineHeight: 1.18,
    fontWeight: 520,
  },
  presetMetaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: 10,
    marginTop: 1,
  },
  presetMetaItem: {
    display: "grid",
    gap: 3,
    paddingTop: 8,
    borderTop: "1px solid rgba(245,200,120,0.12)",
    color: "var(--text-faint)",
    fontSize: 10.5,
    lineHeight: 1.25,
  },
  presetRule: {
    color: "rgba(148,164,109,0.90)",
    fontSize: 12.4,
    lineHeight: 1.42,
  },
  presetHook: {
    color: "var(--text-muted)",
    fontSize: 12.4,
    lineHeight: 1.42,
  },
  presetAction: {
    justifySelf: "start",
    marginTop: 2,
    minHeight: 32,
    padding: "3px 0",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.50)",
    background: "transparent",
    color: "rgba(245,205,150,0.96)",
    fontFamily: "inherit",
    fontSize: 13.2,
    lineHeight: 1.25,
    fontWeight: 880,
    cursor: "pointer",
  },
  messageStack: {
    display: "grid",
    gap: 12,
  },
  guideMessage: {
    maxWidth: 690,
    minWidth: 0,
    padding: "16px 18px 17px",
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.07), rgba(255,255,255,0) 48%), rgba(255,255,255,0.045)",
    border: "1px solid rgba(245,200,120,0.14)",
    borderLeft: "3px solid rgba(148,164,109,0.62)",
    borderRadius: "var(--radius-panel)",
    boxShadow: "0 16px 42px rgba(0,0,0,0.20)",
  },
  guideMessageResult: {
    maxWidth: "100%",
    display: "grid",
    gap: 12,
    padding: "17px",
  },
  guideMessageSuccess: {
    borderLeft: "3px solid rgba(148,164,109,0.72)",
    background: "rgba(148,164,109,0.075)",
  },
  guideMessageBlocked: {
    borderLeft: "3px solid rgba(211,108,88,0.76)",
    background: "rgba(211,108,88,0.09)",
  },
  guideMessageRevise: {
    borderLeft: "3px solid rgba(208,138,79,0.72)",
    background: "rgba(208,138,79,0.075)",
  },
  userMessage: {
    maxWidth: 680,
    minWidth: 0,
    justifySelf: "end",
    padding: "14px 16px 15px",
    background:
      "linear-gradient(135deg, rgba(208,138,79,0.22), rgba(208,138,79,0.08))",
    border: "1px solid rgba(208,138,79,0.32)",
    borderRight: "3px solid rgba(208,138,79,0.70)",
    borderRadius: "var(--radius-panel)",
    boxShadow: "0 18px 46px rgba(0,0,0,0.22)",
  },
  messageSpeaker: {
    display: "block",
    marginBottom: 6,
    color: "rgba(245,200,120,0.78)",
    fontFamily: "var(--font-mono)",
    fontSize: 10.5,
    lineHeight: 1.2,
    fontWeight: 780,
    letterSpacing: "0.05em",
    textTransform: "uppercase" as const,
  },
  messageTitle: {
    display: "block",
    marginBottom: 5,
    color: "rgba(255,250,242,0.96)",
    fontSize: 15,
    lineHeight: 1.35,
    fontWeight: 780,
  },
  messageText: {
    minWidth: 0,
    margin: 0,
    color: "var(--text)",
    fontSize: 13.5,
    lineHeight: 1.62,
    whiteSpace: "pre-wrap" as const,
    overflowWrap: "anywhere" as const,
  },
  notFitPanel: {
    display: "grid",
    gap: 6,
    padding: "10px 11px",
    border: "1px solid rgba(208,138,79,0.18)",
    borderLeft: "3px solid rgba(208,138,79,0.66)",
    borderRadius: "var(--radius-panel)",
    background: "rgba(208,138,79,0.07)",
  },
  composerDock: {
    display: "grid",
    gap: 8,
    marginTop: 1,
    padding: "12px",
    background: "rgba(0,0,0,0.20)",
    border: "1px solid rgba(245,200,120,0.10)",
    borderRadius: "var(--radius-control)",
  },
  guideThinking: {
    maxWidth: 420,
    padding: "13px 15px",
    border: "1px solid rgba(148,164,109,0.22)",
    borderLeft: "3px solid rgba(148,164,109,0.62)",
    background: "rgba(148,164,109,0.08)",
    borderRadius: "var(--radius-panel)",
  },
  thinkingPulse: {
    color: "var(--text-muted)",
    fontSize: 13,
    lineHeight: 1.4,
  },

  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 46,
    lineHeight: 1.08,
    letterSpacing: 0,
    fontWeight: 400,
    marginTop: 0,
    marginRight: 0,
    marginBottom: 16,
    marginLeft: 0,
    color: "rgba(255,250,242,0.98)",
    textShadow: "0 2px 24px rgba(0,0,0,0.62)",
  },
  titleCompact: {
    fontSize: 34,
    lineHeight: 1.08,
    marginBottom: 14,
  },
  kicker: {
    display: "inline-block",
    marginBottom: 20,
    padding: "0 0 6px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(208,138,79,0.36)",
    borderRadius: 0,
    fontFamily: "var(--font-mono)",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "rgba(245,200,120,0.88)",
    transform: "none",
  },
  sub: {
    fontSize: 16,
    lineHeight: 1.55,
    color: "rgba(244,239,230,0.78)",
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
    color: "rgba(208,138,79,0.88)",
    fontSize: 13,
    lineHeight: 1.45,
    fontWeight: 650,
  },
  promptFitHintCompact: {
    marginBottom: 24,
    fontSize: 12.5,
    lineHeight: 1.42,
  },

  textareaWrap: {
    position: "relative",
    padding: "0",
    marginBottom: 0,
    background: "rgba(5,6,10,0.64)",
    border: "1px solid rgba(245,200,120,0.20)",
    borderLeft: "3px solid rgba(208,138,79,0.58)",
    borderRadius: "var(--radius-control)",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.07), 0 16px 46px rgba(0,0,0,0.20)",
  },
  editorMeta: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 0,
    color: "var(--text-faint)",
    fontSize: 11,
    lineHeight: 1.25,
    letterSpacing: 0,
  },
  examplesBlock: {
    display: "grid",
    gridTemplateColumns: "96px minmax(0, 1fr)",
    alignItems: "start",
    columnGap: 18,
    rowGap: 10,
    marginBottom: 0,
  },
  examplesBlockCompact: {
    gridTemplateColumns: "1fr",
    rowGap: 8,
  },
  examplesLabel: {
    fontSize: 12,
    color: "var(--text-faint)",
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
    padding: "9px 10px 10px",
    background: "rgba(255,255,255,0.035)",
    border: "1px solid rgba(245,200,120,0.10)",
    borderLeft: "2px solid rgba(208,138,79,0.48)",
    borderRadius: "var(--radius-control)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontFamily: "var(--font-ui)",
    textAlign: "left" as const,
    boxShadow: "none",
  },
  exampleLineIndex: {
    color: "var(--accent)",
    fontFamily: "var(--font-ui)",
    fontSize: 11,
    lineHeight: 1.25,
    fontWeight: 780,
  },
  exampleLineText: {
    minWidth: 0,
    color: "var(--text-muted)",
    fontSize: 12.6,
    lineHeight: 1.42,
  },
  exampleLineUse: {
    color: "rgba(208,138,79,0.82)",
    fontFamily: "var(--font-ui)",
    fontSize: 10.5,
    lineHeight: 1.25,
    fontWeight: 780,
    whiteSpace: "nowrap" as const,
  },
  textarea: {
    width: "100%",
    minHeight: 142,
    padding: "20px 21px",
    background: "transparent",
    border: "none",
    borderBottom: "none",
    borderRadius: 0,
    fontFamily: "var(--font-ui)",
    fontSize: 15.5,
    lineHeight: 1.62,
    color: "var(--text)",
    resize: "vertical",
    outline: "none",
    transition: "border-color 200ms",
  },
  textareaCompact: {
    minHeight: 112,
    padding: "16px 14px",
    fontSize: 15,
  },
  count: {
    fontSize: 11,
    color: "var(--text-faint)",
    letterSpacing: 0,
  },
  shortcutHint: {
    color: "rgba(208,138,79,0.78)",
    fontSize: 11,
    fontWeight: 720,
    whiteSpace: "nowrap" as const,
  },

  settingsStrip: {
    display: "grid",
    gridTemplateColumns: "1fr",
    rowGap: 14,
    padding: "14px 0 2px",
    marginBottom: 0,
  },
  settingsStripCompact: {
    gridTemplateColumns: "1fr",
    rowGap: 13,
  },
  settingGroup: {
    minWidth: 0,
    display: "grid",
    gridTemplateColumns: "1fr",
    alignItems: "start",
    columnGap: 0,
    rowGap: 8,
  },
  settingGroupCompact: {
    gridTemplateColumns: "minmax(0, 1fr)",
    rowGap: 6,
  },
  settingLabel: {
    color: "var(--text-faint)",
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
    alignItems: "stretch",
    columnGap: 8,
    rowGap: 8,
  },
  segmentBtn: {
    minWidth: 0,
    padding: "8px 9px 9px",
    background: "rgba(255,255,255,0.035)",
    border: "1px solid rgba(245,200,120,0.10)",
    borderRadius: "var(--radius-control)",
    color: "var(--text-muted)",
    display: "inline-flex",
    alignItems: "baseline",
    gap: 5,
    fontFamily: "inherit",
    textAlign: "left" as const,
    cursor: "pointer",
  },
  segmentBtnActive: {
    color: "var(--text)",
    background: "rgba(208,138,79,0.14)",
    border: "1px solid rgba(208,138,79,0.56)",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06)",
  },
  segmentBtnWarn: {
    border: "1px solid rgba(160,71,45,0.46)",
  },
  segmentMain: {
    fontSize: 13,
    lineHeight: 1.25,
    fontWeight: 750,
    whiteSpace: "nowrap" as const,
  },
  segmentMeta: {
    color: "rgba(208,138,79,0.78)",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 650,
    whiteSpace: "nowrap" as const,
  },

  settingsDetails: {
    marginTop: 0,
    padding: "14px 14px 15px",
    border: "1px solid rgba(245,200,120,0.14)",
    borderRadius: 2,
    background:
      "linear-gradient(135deg, rgba(255,255,255,0.045), rgba(255,255,255,0) 42%), rgba(5,6,10,0.44)",
  },
  settingsDetailsFocused: {
    marginTop: 0,
  },
  settingsSummary: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: 16,
    padding: 0,
    cursor: "pointer",
    listStyle: "none",
    color: "var(--text-muted)",
  },
  settingsSummaryMain: {
    minWidth: 0,
    display: "flex",
    alignItems: "baseline",
    gap: 10,
    flexWrap: "wrap" as const,
  },
  settingsSummaryLabel: {
    color: "var(--text-faint)",
    fontSize: 11.5,
    fontWeight: 680,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  settingsSummaryValue: {
    minWidth: 0,
    color: "var(--text-muted)",
    fontSize: 12.5,
    lineHeight: 1.35,
  },
  settingsToggleHint: {
    color: "rgba(208,138,79,0.84)",
    fontSize: 11,
    fontWeight: 760,
    letterSpacing: 0,
    textTransform: "none" as const,
  },

  fieldLabel: {
    fontSize: 12,
    color: "var(--text-faint)",
    letterSpacing: 0,
    textTransform: "none",
    marginBottom: 12,
  },

  visibility: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
    gap: "0 24px",
    marginBottom: 32,
    borderTop: "1px solid var(--line)",
  },
  optionGridCompact: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 0,
    marginBottom: 28,
    borderTop: "1px solid var(--line)",
  },
  visBtn: {
    textAlign: "left",
    padding: "16px 18px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid var(--line)",
    borderRadius: 0,
    color: "var(--text-muted)",
    cursor: "pointer",
    transition: "border-color 180ms, color 180ms",
  },
  visBtnActive: {
    background: "transparent",
    borderBottom: "1px solid rgba(208,138,79,0.72)",
    color: "var(--text)",
  },
  visBtnLabel: { fontSize: 15, fontWeight: 600, marginBottom: 6 },
  visBtnDesc: { fontSize: 12, color: "var(--text-faint)", lineHeight: 1.4 },
  budgetTime: {
    fontSize: 12,
    color: "rgba(208,138,79,0.84)",
    fontWeight: 500,
  },

  difficultyRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "0 24px",
    marginBottom: 32,
    borderTop: "1px solid var(--line)",
  },
  difficultyBtn: {
    textAlign: "left",
    padding: "16px 18px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid var(--line)",
    borderRadius: 0,
    color: "var(--text-muted)",
    cursor: "pointer",
    transition: "border-color 180ms, color 180ms",
  },
  difficultyBtnActive: {
    background: "transparent",
    borderBottom: "1px solid rgba(208,138,79,0.72)",
    color: "var(--text)",
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
    color: "rgba(208,138,79,0.84)",
    fontWeight: 500,
  },
  difficultyBtnDesc: {
    fontSize: 12,
    color: "var(--text-faint)",
    lineHeight: 1.45,
  },

  error: {
    marginBottom: 0,
    padding: "11px 12px",
    fontSize: 13,
    color: "rgba(255,224,216,0.96)",
    background: "rgba(211,108,88,0.12)",
    border: "1px solid rgba(211,108,88,0.34)",
    borderLeft: "3px solid rgba(211,108,88,0.72)",
    borderRadius: 2,
  },
  briefRail: {
    position: "relative" as const,
    marginTop: 0,
    marginBottom: 0,
    padding: "18px",
    border: "1px solid rgba(245,200,120,0.18)",
    borderTop: "3px solid rgba(208,138,79,0.66)",
    borderLeft: "1px solid rgba(245,200,120,0.18)",
    borderRadius: "var(--radius-panel)",
    background:
      `linear-gradient(145deg, rgba(255,255,255,0.085), rgba(255,255,255,0) 40%), linear-gradient(180deg, rgba(13,15,20,0.94), rgba(8,9,13,0.86)), url(${GENERATED_ASSETS.objectCardSheet})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
    color: "var(--text-muted)",
    boxShadow: "0 24px 76px rgba(0,0,0,0.36), inset 0 1px 0 rgba(255,255,255,0.07)",
  },
  briefRailCompact: {
    marginBottom: 18,
    padding: "15px 12px 14px",
  },
  briefTape: {
    display: "none",
  },
  briefHeader: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 8,
  },
  briefReadyDock: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: 14,
    margin: "2px 0 12px",
    padding: "10px 12px",
    border: "1px solid rgba(148,164,109,0.22)",
    borderLeft: "3px solid rgba(148,164,109,0.62)",
    background: "rgba(148,164,109,0.08)",
    borderRadius: "var(--radius-panel)",
  },
  briefReadyDockCompact: {
    gridTemplateColumns: "1fr",
    gap: 9,
  },
  briefReadyCopy: {
    minWidth: 0,
    display: "grid",
    gap: 2,
  },
  briefReadyTitle: {
    color: "rgba(255,250,242,0.96)",
    fontSize: 12.5,
    lineHeight: 1.25,
    fontWeight: 820,
  },
  briefReadyHint: {
    color: "var(--text-muted)",
    fontSize: 11.5,
    lineHeight: 1.35,
  },
  briefInlineGenerate: {
    justifySelf: "end",
    minHeight: 32,
    padding: "0 0 4px",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.48)",
    background: "transparent",
    color: "rgba(245,205,150,0.96)",
    fontFamily: "inherit",
    fontSize: 13,
    lineHeight: 1.25,
    fontWeight: 880,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
  },
  briefInlineGenerateCompact: {
    justifySelf: "start",
    whiteSpace: "normal" as const,
  },
  briefEyebrow: {
    color: "rgba(208,138,79,0.88)",
    fontSize: 11.5,
    lineHeight: 1.2,
    fontWeight: 820,
    letterSpacing: 0,
  },
  briefFitPill: {
    color: "rgba(148,164,109,0.92)",
    fontSize: 11,
    lineHeight: 1.2,
    fontWeight: 780,
    whiteSpace: "nowrap" as const,
  },
  briefIntro: {
    marginTop: 0,
    marginRight: 0,
    marginBottom: 8,
    marginLeft: 0,
    color: "var(--text)",
    fontSize: 13,
    lineHeight: 1.45,
    fontWeight: 720,
  },
  briefBetaNote: {
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.42,
    marginBottom: 0,
  },
  briefFitPillWarn: {
    color: "rgba(255,170,150,0.96)",
  },
  briefPremise: {
    marginTop: 0,
    marginRight: 0,
    marginBottom: 10,
    marginLeft: 0,
    color: "var(--text)",
    fontSize: 17,
    lineHeight: 1.48,
    fontFamily: "var(--font-narrative)",
  },
  briefLeadPanel: {
    margin: "10px 0 14px",
    padding: "14px 14px 13px",
    background: "rgba(0,0,0,0.20)",
    border: "1px solid rgba(245,200,120,0.12)",
    borderLeft: "3px solid rgba(208,138,79,0.58)",
    borderRadius: "var(--radius-panel)",
  },
  briefMetaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: "12px 18px",
    marginBottom: 14,
  },
  briefMetaGridCompact: {
    gridTemplateColumns: "1fr",
    gap: "8px 0",
  },
  briefField: {
    minWidth: 0,
    display: "grid",
    gap: 3,
    padding: "10px 11px",
    background: "rgba(255,255,255,0.035)",
    border: "1px solid rgba(245,200,120,0.09)",
    borderRadius: "var(--radius-control)",
  },
  briefFieldLabel: {
    color: "var(--text-faint)",
    fontSize: 10.5,
    lineHeight: 1.15,
    fontWeight: 760,
    letterSpacing: 0,
  },
  briefFieldValue: {
    color: "var(--text-muted)",
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
  briefPrimaryCompact: {
    marginBottom: 10,
    padding: "11px 12px",
    borderLeft: "2px solid rgba(148,164,109,0.56)",
    borderRadius: "var(--radius-panel)",
    background: "rgba(148,164,109,0.07)",
  },
  briefList: {
    minWidth: 0,
    display: "grid",
    gap: 3,
  },
  briefListValue: {
    color: "var(--text-muted)",
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
    color: "var(--text-faint)",
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
    color: "var(--text-faint)",
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
    color: "var(--text-muted)",
    fontSize: 11.5,
    lineHeight: 1.25,
    borderBottom: "1px solid var(--line)",
    paddingBottom: 3,
  },
  briefConstraintKind: {
    color: "rgba(208,138,79,0.76)",
    fontSize: 10,
    fontWeight: 800,
  },
  briefWarningBlock: {
    display: "grid",
    gap: 6,
    marginBottom: 12,
    padding: "10px 11px",
    border: "1px solid rgba(208,138,79,0.20)",
    borderLeft: "3px solid rgba(208,138,79,0.68)",
    background: "rgba(208,138,79,0.08)",
    borderRadius: "var(--radius-panel)",
  },
  briefWarningLine: {
    color: "rgba(255,218,210,0.94)",
    fontSize: 12,
    lineHeight: 1.38,
  },
  briefSuggestionLine: {
    color: "rgba(208,138,79,0.84)",
    fontSize: 12,
    lineHeight: 1.38,
  },
  briefDetailDisclosure: {
    marginBottom: 11,
    borderTop: "1px solid rgba(245,200,120,0.12)",
    borderBottom: "1px solid rgba(245,200,120,0.10)",
    padding: "7px 0",
  },
  briefDetailSummary: {
    cursor: "pointer",
    color: "var(--text-muted)",
    fontSize: 11.5,
    lineHeight: 1.3,
    fontWeight: 820,
  },
  briefDetailBody: {
    display: "grid",
    gap: 8,
    paddingTop: 9,
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
    border: "1px solid rgba(208,138,79,0.42)",
    borderRadius: "var(--radius-control)",
    background: "rgba(208,138,79,0.14)",
    color: "var(--text)",
    fontSize: 11.5,
    fontWeight: 760,
    lineHeight: 1.2,
    padding: "6px 8px",
    cursor: "pointer",
  },
  briefFooter: {
    display: "grid",
    gap: 3,
    color: "var(--text-faint)",
    fontSize: 11.5,
    lineHeight: 1.42,
    paddingTop: 10,
    borderTop: "1px solid rgba(245,200,120,0.10)",
  },
  contractPanel: {
    marginTop: 14,
    padding: "14px 14px 15px",
    border: "1px solid rgba(245,200,120,0.14)",
    borderLeft: "3px solid rgba(148,164,109,0.54)",
    borderRadius: "var(--radius-panel)",
    background:
      "linear-gradient(135deg, rgba(148,164,109,0.12), rgba(255,255,255,0.02) 56%), rgba(255,255,255,0.035)",
    display: "grid",
    gap: 6,
  },
  contractKicker: {
    color: "rgba(245,200,120,0.72)",
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    fontWeight: 780,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
  },
  contractTitle: {
    color: "var(--text)",
    fontSize: 14,
    lineHeight: 1.3,
    fontWeight: 760,
  },
  contractLine: {
    color: "var(--text-muted)",
    fontSize: 11.5,
    lineHeight: 1.45,
  },
  actions: {
    display: "flex",
    alignItems: "baseline",
    columnGap: 18,
    rowGap: 8,
    flexWrap: "wrap",
    marginBottom: 0,
  },
  actionsCompact: {
    alignItems: "baseline",
    marginBottom: 0,
  },
  primaryAction: {
    width: "fit-content",
    minHeight: 34,
    padding: "4px 0",
    border: "none",
    borderBottom: "1px solid rgba(208,138,79,0.44)",
    borderRadius: 0,
    background: "transparent",
    color: "rgba(245,205,150,0.96)",
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
    color: "var(--text-faint)",
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
    marginTop: 14,
    padding: "14px 14px 15px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(245,200,120,0.14)",
    borderRadius: 2,
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
    color: "rgba(245,205,150,0.86)",
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
    background: "linear-gradient(90deg, rgba(208,138,79,0.48), rgba(208,138,79,0.04))",
    transform: "translateY(1px)",
  },
}
