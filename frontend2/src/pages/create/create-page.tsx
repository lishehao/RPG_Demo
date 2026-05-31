import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import type {
  NarrativeDifficulty,
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
  const [visibility, setVisibility] = useState<NarrativeTemplateVisibility>("private")
  const [turnBudget, setTurnBudget] = useState<number>(12)
  const [difficulty, setDifficulty] = useState<NarrativeDifficulty>("story")
  const [settingsOpen, setSettingsOpen] = useState(false)
  // Default the story language to whatever the UI is in. The user can
  // override — the field is independent of UI language once chosen
  // (you can browse in English but write a Chinese story, etc.).
  const [storyLanguage, setStoryLanguage] = useState<NarrativeTemplateLanguage>(uiLang)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Synchronous lock to prevent duplicate creates if the user manages to
  // double-click before React flushes setBusy(true). useState alone doesn't
  // guarantee that — React batches state updates, so two clicks within
  // ~16ms can both pass the `busy` check and fire two requests.
  const inflightRef = useRef(false)

  const seedExamples = useMemo(() => SEED_EXAMPLE_KEYS.map((k) => t(k)), [t])
  const visibleSeedExamples = compactLayout ? seedExamples.slice(0, 3) : seedExamples
  const hasSeed = Boolean(seed.trim())
  const showCreateAction = hasSeed || busy
  const showBackAction = hasSeed || busy
  const showSeedExamples = !hasSeed && !busy
  const selectedBudget = BUDGET_OPTIONS.find((o) => o.budget === turnBudget) ?? BUDGET_OPTIONS[1]
  const selectedDifficulty = DIFFICULTY_OPTIONS.find((o) => o.id === difficulty) ?? DIFFICULTY_OPTIONS[0]
  const selectedLanguage =
    STORY_LANGUAGE_OPTIONS[uiLang].find((o) => o.id === storyLanguage) ?? STORY_LANGUAGE_OPTIONS[uiLang][0]
  const selectedVisibility = VISIBILITY_KEY_MAP[visibility]
  const settingsSummary = [
    t(selectedBudget.labelKey),
    t(selectedDifficulty.labelKey),
    selectedLanguage.label,
    t(selectedVisibility.labelKey),
  ].join(" · ")
  const submitModKey = useMemo(() => {
    if (typeof navigator === "undefined") return "Ctrl"
    return /Mac|iPhone|iPad/i.test(navigator.platform) ? "⌘" : "Ctrl"
  }, [])

  // Author flow requires a real account.
  useEffect(() => {
    if (auth.loading) return
    if (auth.isAnonymous) {
      window.location.hash = "#/login?next=create"
    }
  }, [auth.loading, auth.isAnonymous])

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

  return (
    <div style={cpStyles.page}>
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

          <div style={cpStyles.textareaWrap}>
            <textarea
              style={{
                ...cpStyles.textarea,
                ...(compactLayout ? cpStyles.textareaCompact : {}),
              }}
              placeholder={compactLayout ? t("create.placeholder_short") : t("create.placeholder")}
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault()
                  void handleCreate()
                }
              }}
              spellCheck={false}
              disabled={busy}
            />
          </div>
          <div style={cpStyles.editorMeta}>
            <span style={cpStyles.count}>{t("create.char_count", { n: seed.length })}</span>
            {showCreateAction && !compactLayout ? (
              <span style={cpStyles.shortcutHint}>
                {t("create.submit_shortcut", { mod: submitModKey })}
              </span>
            ) : null}
          </div>

          {error ? <div style={cpStyles.error}>{error}</div> : null}

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
                    opacity: !hasSeed || busy ? 0.5 : 1,
                    pointerEvents: !hasSeed || busy ? "none" : "auto",
                    ...(compactLayout ? cpStyles.primaryCtaCompact : null),
                  }}
                  disabled={!hasSeed || busy}
                  onClick={() => void handleCreate()}
                  type="button"
                  initial={{ opacity: 0, y: -4, height: 0, marginTop: 0 }}
                  animate={{ opacity: !hasSeed || busy ? 0.5 : 1, y: 0, height: "auto", marginTop: 0 }}
                  exit={{ opacity: 0, y: -4, height: 0, marginTop: 0 }}
                  transition={itemTransition}
                >
                  {busy ? t("create.cta_busy") : hasSeed ? t("create.cta_idle") : t("create.cta_empty")}
                </motion.button>
              ) : null}
            </AnimatePresence>
            {!compactLayout && showBackAction ? (
              <button style={cpStyles.backAction} onClick={onBackHome} disabled={busy} type="button">
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
                      onClick={() => setSeed(example)}
                      disabled={busy}
                      type="button"
                    >
                      <span style={cpStyles.exampleLineIndex}>{index + 1}.</span>
                      <span style={cpStyles.exampleLineText}>{example}</span>
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
                      disabled={busy}
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
                  <span style={cpStyles.busyLabel}>{t("create.building_label")}</span>
                  <div style={cpStyles.busyDots} aria-hidden>
                    {[0, 1, 2, 3].map((i) => (
                      <motion.span
                        key={i}
                        style={cpStyles.busyDot}
                        animate={{
                          opacity: [0.25, 1, 0.25],
                          scale: [0.85, 1.1, 0.85],
                        }}
                        transition={{
                          duration: 1.4,
                          repeat: Infinity,
                          ease: "easeInOut",
                          delay: i * 0.16,
                        }}
                      />
                    ))}
                  </div>
                </div>
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

const cpStyles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100%",
    background: `linear-gradient(180deg, rgba(20,16,12,0.55) 0%, rgba(20,16,12,0.92) 60%, var(--bg) 100%), url(${PAGE_BG.create})`,
    backgroundSize: "cover",
    backgroundPosition: "center top",
    backgroundAttachment: "fixed",
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
    marginBottom: 40,
    marginLeft: 0,
  },
  subCompact: {
    fontSize: 15.5,
    lineHeight: 1.52,
    marginBottom: 30,
  },

  textareaWrap: {
    position: "relative",
    marginBottom: 7,
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
    gridTemplateColumns: "20px minmax(0, 1fr)",
    alignItems: "baseline",
    gap: 7,
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
  textarea: {
    width: "100%",
    minHeight: 200,
    padding: "12px 0 14px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid rgba(245,200,120,0.28)",
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
    minHeight: 118,
    padding: "10px 0 12px",
    fontSize: 15,
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
  },
  busyLabel: {
    fontSize: 11.5,
    lineHeight: 1.2,
    fontWeight: 720,
    letterSpacing: 0,
    textTransform: "none" as const,
  },
  busyDots: {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
  },
  busyDot: {
    width: 4,
    height: 4,
    borderRadius: "50%",
    background: "rgba(245,210,140,0.68)",
    display: "inline-block",
  },
}
