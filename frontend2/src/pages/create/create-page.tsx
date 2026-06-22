import { useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import type {
  NarrativeDifficulty,
  NarrativeStoryBriefAdvisorResponse,
  NarrativeTemplateLanguage,
  NarrativeTemplateVisibility,
} from "../../api/contracts"
import { useApi } from "../../app/api-context"
import { useAuth } from "../../app/auth-context"
import { friendlyError } from "../../shared/lib/friendly-error"
import { useLanguage, useT, type StringKey } from "../../shared/lib/i18n"
import { itemTransition } from "../../shared/lib/motion-presets"
import {
  advanceStoryGuideLoop,
  buildStoryGuideLedger,
  canShapeStoryBrief,
  createInitialStoryGuideState,
  markStoryGuideAnalyzing,
  markStoryGuideBriefResult,
  type StoryGuideConversationState,
  type StoryGuideLoopState,
  type StoryGuideNodeName,
  type StoryGuideSettingDeltas,
} from "../../shared/lib/story-guide-loop"
import { takeCreateDraftHandoff } from "../../shared/lib/create-draft-handoff"

import { BUSY_STAGE_COUNT, BusyBuildPreview, BusyStages, BusyTip, StoryBriefCard } from "./components/create-flow-panels"
import { BUDGET_OPTIONS, DIFFICULTY_OPTIONS, LONG_GENERATE_HANDOFF_MIN_MS, LONG_GENERATE_HANDOFF_THRESHOLD_MS, SEED_EXAMPLE_KEYS, STORY_BUTLER_AVATAR, STORY_LANGUAGE_OPTIONS, TENSION_PROFILE_OPTIONS, VISIBILITY_KEY_MAP, VISIBILITY_OPTION_IDS, briefKey, makeGuestHandle } from "./create-options"
import { cpStyles } from "./create-styles"
import type { GuideMessage, StoryShapeRead, TensionProfileChoice } from "./create-types"
import { useCompactLayout } from "./hooks/use-compact-layout"

type GuideTurnLike = {
  state: StoryGuideLoopState
  node: StoryGuideNodeName
  status: StoryGuideConversationState
  reply: string
  acceptedText: boolean
  blocked: boolean
  canShapeBrief: boolean
  settings?: {
    turnBudget?: StoryGuideSettingDeltas["turnBudget"] | null
    difficulty?: StoryGuideSettingDeltas["difficulty"] | null
    language?: StoryGuideSettingDeltas["language"] | null
    tensionProfile?: StoryGuideSettingDeltas["tensionProfile"] | null
    privacyIntent?: StoryGuideSettingDeltas["privacyIntent"] | null
  } | null
  ledger?: GuideMessage["ledger"] | null
}

function normalizeGuideReplyText(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return raw
  try {
    const parsed = JSON.parse(trimmed) as unknown
    if (parsed && typeof parsed === "object" && "reply" in parsed) {
      const reply = (parsed as { reply?: unknown }).reply
      if (typeof reply === "string" && reply.trim()) {
        return normalizeGuideReplyText(reply)
      }
    }
  } catch {
    const match = trimmed.match(/"reply"\s*:\s*("(?:(?:\\.)|[^"\\])*")/s)
    if (match?.[1]) {
      try {
        const reply = JSON.parse(match[1]) as unknown
        if (typeof reply === "string" && reply.trim()) return reply.trim()
      } catch {
        return match[1].replace(/^"|"$/g, "").trim()
      }
    }
  }
  if (/^\s*\{/.test(trimmed) || /"reply"\s*:/.test(trimmed)) {
    return ""
  }
  return trimmed
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
  const [guideLoopState, setGuideLoopState] = useState(() => createInitialStoryGuideState(uiLang))
  const [chatMessages, setChatMessages] = useState<GuideMessage[]>([])
  const [guideBusy, setGuideBusy] = useState(false)
  const [correctionCount, setCorrectionCount] = useState(0)
  const [visibility, setVisibility] = useState<NarrativeTemplateVisibility>("private")
  const [privacySetupVisible, setPrivacySetupVisible] = useState(false)
  const [privacyPromptVisible, setPrivacyPromptVisible] = useState(false)
  const [privacyRecordedVisibility, setPrivacyRecordedVisibility] =
    useState<NarrativeTemplateVisibility | null>("private")
  const [turnBudget, setTurnBudget] = useState<number>(12)
  const [difficulty, setDifficulty] = useState<NarrativeDifficulty>("story")
  // Default the story language to whatever the UI is in. The user can
  // override — the field is independent of UI language once chosen
  // (you can browse in English but write a Chinese story, etc.).
  const [storyLanguage, setStoryLanguage] = useState<NarrativeTemplateLanguage>(uiLang)
  const [desiredTensionProfile, setDesiredTensionProfile] = useState<TensionProfileChoice>("auto")
  const [busy, setBusy] = useState(false)
  const [briefBusy, setBriefBusy] = useState(false)
  const [openingHandoffLabelKey, setOpeningHandoffLabelKey] = useState<StringKey | null>(null)
  const [busyElapsedSeconds, setBusyElapsedSeconds] = useState(0)
  const [briefBusyElapsedSeconds, setBriefBusyElapsedSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [generationError, setGenerationError] = useState(false)
  const [briefError, setBriefError] = useState<string | null>(null)
  const [briefResponse, setBriefResponse] = useState<NarrativeStoryBriefAdvisorResponse | null>(null)
  const [briefResponseKey, setBriefResponseKey] = useState<string | null>(null)
  const seedTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const transcriptScrollRef = useRef<HTMLDivElement | null>(null)
  const briefMessageRef = useRef<HTMLDivElement | null>(null)
  const briefErrorRef = useRef<HTMLDivElement | null>(null)
  const generationErrorRef = useRef<HTMLDivElement | null>(null)
  const generationHandoffRef = useRef<HTMLDivElement | null>(null)
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)
  const guestHandleRef = useRef<string | null>(null)
  const autoBriefKeyRef = useRef<string | null>(null)
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
  const guideReadyToBrief = guideLoopState.status === "ready_to_brief" && canShapeStoryBrief(guideLoopState)
  const canRetryBrief =
    Boolean(briefError) && guideReadyToBrief && hasSeed && !busy && !briefBusy && !guideBusy
  const privacyIntroComplete = Boolean(privacyRecordedVisibility)
  const showSeedExamples = privacyIntroComplete && !hasSeed && !busy && !briefBusy && !guideBusy
  const selectedBudget = BUDGET_OPTIONS.find((o) => o.budget === turnBudget) ?? BUDGET_OPTIONS[1]
  const selectedDifficulty = DIFFICULTY_OPTIONS.find((o) => o.id === difficulty) ?? DIFFICULTY_OPTIONS[0]
  const selectedLanguage =
    STORY_LANGUAGE_OPTIONS[uiLang].find((o) => o.id === storyLanguage) ?? STORY_LANGUAGE_OPTIONS[uiLang][0]
  const selectedVisibility = VISIBILITY_KEY_MAP[visibility]
  const selectedTension =
    TENSION_PROFILE_OPTIONS.find((o) => o.id === desiredTensionProfile) ?? TENSION_PROFILE_OPTIONS[0]
  const storyShapeRead: StoryShapeRead = {
    runLength: `${t(selectedBudget.labelKey)} · ${t(selectedBudget.timeKey)}`,
    runLengthDetail: t(selectedBudget.descKey),
    pressureMode: t(selectedDifficulty.labelKey),
    pressureModeDetail: t(selectedDifficulty.descKey),
    storyLanguage: selectedLanguage.label,
    storyLanguageDetail: selectedLanguage.desc,
    tone: t(selectedTension.labelKey),
    toneDetail: t(selectedTension.descKey),
  }
  const guideMessages = useMemo<GuideMessage[]>(
    () => {
      if (!privacyIntroComplete) {
        return [
          {
            id: "guide-privacy-open",
            speaker: "guide",
            text: t("create.privacy_intro_question"),
          },
          ...chatMessages,
        ]
      }
      if (chatMessages.length === 0) {
        return [
          {
            id: "guide-opening",
            speaker: "guide",
            text: t("create.guide_greeting"),
            node: "ask_missing_slot",
            state: "collecting",
          },
        ]
      }
      return chatMessages
    },
    [chatMessages, privacyIntroComplete, t],
  )
  const busyLabel = openingHandoffLabelKey
    ? t(openingHandoffLabelKey)
    : busyElapsedSeconds >= 45
      ? t("create.building_recovering_elapsed", { seconds: busyElapsedSeconds })
      : busyElapsedSeconds >= 30
      ? t("create.building_long_elapsed", { seconds: busyElapsedSeconds })
      : busyElapsedSeconds >= 15
      ? t("create.building_honoring_elapsed", { seconds: busyElapsedSeconds })
      : busyElapsedSeconds >= 8
      ? t("create.building_slow_elapsed", { seconds: busyElapsedSeconds })
      : busyElapsedSeconds > 0
      ? t("create.building_elapsed", { seconds: busyElapsedSeconds })
      : t("create.building_label")
  const busyStageIndex = Math.min(
    BUSY_STAGE_COUNT - 1,
    Math.max(0, Math.floor(busyElapsedSeconds / 3)),
  )
  const briefPlanningCopy =
    briefBusyElapsedSeconds >= 10
      ? t("create.guide_planning_slow")
      : t("create.guide_planning_now")
  const guideThinkingCopy = t("create.guide_thinking")
  const composerProgressHint =
    hasSeed && !activeBrief && !compactLayout
      ? guideReadyToBrief
        ? t("create.guide_ready_brief_hint")
        : t("create.guide_next_prompt_hint")
      : null
  const composerActionLabel = !hasSeed
    ? t("create.guide_add_opening")
    : activeBrief || guideReadyToBrief
      ? t("create.guide_add_correction")
      : t("create.guide_add_answer")

  const applyStoryGuideSettings = (settings?: StoryGuideSettingDeltas) => {
    if (!settings) return
    if (settings.turnBudget) setTurnBudget(settings.turnBudget)
    if (settings.difficulty) setDifficulty(settings.difficulty)
    if (settings.language) setStoryLanguage(settings.language)
    if (settings.tensionProfile) setDesiredTensionProfile(settings.tensionProfile)
  }

  const ensureAuthorSession = async (): Promise<boolean> => {
    if (!auth.isAnonymous) return true
    if (auth.loading) {
      setError(t("create.error_guest_loading"))
      setGenerationError(false)
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
      setGenerationError(false)
      return false
    }
  }

  const appendPrivacyRecordedTurn = (
    nextVisibility: NarrativeTemplateVisibility,
    mode: "initial" | "confirmation",
  ) => {
    const label = t(VISIBILITY_KEY_MAP[nextVisibility].labelKey)
    const time = Date.now()
    setChatMessages((current) => {
      const nextMessages = [...current]
      const hadNoStoryPrompt = current.length === 0
      if (mode === "initial") {
        nextMessages.push({
          id: `user-privacy-${time}`,
          speaker: "user",
          text: t("create.privacy_recorded_user", { value: label }),
        })
      }
      nextMessages.push({
        id: `guide-privacy-recorded-${time}`,
        speaker: "guide",
        text: t("create.privacy_recorded_reply", { value: label }),
        node: "parse_message",
        state: "collecting",
      })
      if (mode === "initial") {
        nextMessages.push({
          id: `guide-privacy-greeting-${time}`,
          speaker: "guide",
          text: t("create.guide_greeting"),
          node: "ask_missing_slot",
          state: "collecting",
        })
      } else if (hadNoStoryPrompt) {
        nextMessages.push({
          id: `guide-privacy-greeting-${time}`,
          speaker: "guide",
          text: t("create.guide_greeting"),
          node: "ask_missing_slot",
          state: "collecting",
        })
      }
      return nextMessages
    })
  }

  const handleVisibilityChoice = (nextVisibility: NarrativeTemplateVisibility) => {
    const mode: "initial" | "confirmation" =
      privacyPromptVisible || privacyRecordedVisibility ? "confirmation" : "initial"
    setVisibility(nextVisibility)
    setPrivacyRecordedVisibility(nextVisibility)
    setPrivacySetupVisible(false)
    setPrivacyPromptVisible(false)
    appendPrivacyRecordedTurn(nextVisibility, mode)
    window.requestAnimationFrame(() => seedTextareaRef.current?.focus())
  }

  const hidePrivacySetup = () => {
    if (privacyRecordedVisibility && !privacyPromptVisible) {
      setPrivacySetupVisible(false)
      window.requestAnimationFrame(() => seedTextareaRef.current?.focus())
      return
    }
    handleVisibilityChoice(visibility)
  }

  useEffect(() => {
    if (!busy) {
      setBusyElapsedSeconds(0)
      setOpeningHandoffLabelKey(null)
      return
    }
    setBusyElapsedSeconds(0)
    setOpeningHandoffLabelKey(null)
    const startedAt = Date.now()
    const id = window.setInterval(() => {
      setBusyElapsedSeconds(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => window.clearInterval(id)
  }, [busy])

  useEffect(() => {
    if (!briefBusy) {
      setBriefBusyElapsedSeconds(0)
      return
    }
    setBriefBusyElapsedSeconds(0)
    const startedAt = Date.now()
    const id = window.setInterval(() => {
      setBriefBusyElapsedSeconds(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => window.clearInterval(id)
  }, [briefBusy])

  useEffect(() => {
    if (!activeBriefResponse) return
    const id = window.setTimeout(() => {
      const transcript = transcriptScrollRef.current
      if (transcript) {
        transcript.scrollTo({ top: transcript.scrollHeight, behavior: "auto" })
        return
      }
      briefMessageRef.current?.scrollIntoView({ block: "end", behavior: "smooth" })
    }, 40)
    return () => window.clearTimeout(id)
  }, [activeBriefResponse])

  useEffect(() => {
    if (chatMessages.length === 0 && !briefBusy) return
    const id = window.setTimeout(() => {
      const transcript = transcriptScrollRef.current
      if (transcript) {
        transcript.scrollTo({ top: transcript.scrollHeight, behavior: "auto" })
        return
      }
      transcriptEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" })
    }, 40)
    return () => window.clearTimeout(id)
  }, [chatMessages.length, briefBusy])

  useEffect(() => {
    if (!briefError) return
    const id = window.setTimeout(() => {
      briefErrorRef.current?.scrollIntoView({ block: "center", behavior: "auto" })
    }, 40)
    return () => window.clearTimeout(id)
  }, [briefError])

  useEffect(() => {
    if (!generationError || !error || busy) return
    const id = window.setTimeout(() => {
      generationErrorRef.current?.scrollIntoView({ block: "center", behavior: "auto" })
    }, 40)
    return () => window.clearTimeout(id)
  }, [busy, error, generationError])

  useEffect(() => {
    if (!busy) return
    const id = window.setTimeout(() => {
      generationHandoffRef.current?.scrollIntoView({ block: "center", behavior: "auto" })
    }, 40)
    return () => window.clearTimeout(id)
  }, [busy])

  const handleCreate = async () => {
    const trimmed = seed.trim()
    if (!trimmed) {
      setError(t("create.error_seed_required"))
      setGenerationError(false)
      return
    }
    if (inflightRef.current) return
    inflightRef.current = true
    setBusy(true)
    setOpeningHandoffLabelKey(null)
    setError(null)
    setGenerationError(false)
    try {
      const startedAt = Date.now()
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
      const openingElapsedMs = Date.now() - startedAt
      const handoffLabelKey: StringKey | null =
        response.opening_recovery === "tightened_from_brief"
          ? "create.building_handoff_recovered"
          : openingElapsedMs >= LONG_GENERATE_HANDOFF_THRESHOLD_MS
          ? "create.building_handoff_ready_long"
          : null
      if (handoffLabelKey) {
        setOpeningHandoffLabelKey(handoffLabelKey)
        await new Promise((resolve) => window.setTimeout(resolve, LONG_GENERATE_HANDOFF_MIN_MS))
      }
      onSessionStarted(response.session.session_id)
    } catch (err) {
      if (canGenerateFromBrief) {
        setError(t("create.generation_error_failed"))
        setGenerationError(true)
      } else {
        setError(friendlyError(err, t("create.error_create_failed")))
        setGenerationError(false)
      }
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
      setGenerationError(false)
      return
    }
    if (briefBusy || busy) return
    if (!guideReadyToBrief) {
      const ledger = buildStoryGuideLedger(guideLoopState, uiLang)
      setGuideLoopState((current) => ({
        ...current,
        status: "needs_field",
        lastNode: "ask_missing_slot",
      }))
      setChatMessages((current) => [
        ...current,
        {
          id: `guide-missing-${Date.now()}-${current.length}`,
          speaker: "guide",
          text: ledger.nextQuestion,
          node: "ask_missing_slot",
          state: "needs_field",
          ledger,
        },
      ])
      focusComposer()
      return
    }
    setBriefBusy(true)
    setBriefError(null)
    setError(null)
    setGenerationError(false)
    setGuideLoopState((current) => markStoryGuideAnalyzing(current, uiLang))
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
      setGuideLoopState((current) => markStoryGuideBriefResult(current, response.can_generate, uiLang))
    } catch (err) {
      setBriefError(friendlyError(err, t("create.brief_error_failed")))
      setGuideLoopState((current) =>
        canShapeStoryBrief(current)
          ? {
              ...current,
              status: "ready_to_brief",
              lastNode: "ready_to_shape",
            }
          : current,
      )
    } finally {
      setBriefBusy(false)
    }
  }

  useEffect(() => {
    if (
      !guideReadyToBrief ||
      !hasSeed ||
      privacyPromptVisible ||
      activeBriefResponse ||
      guideBusy ||
      briefBusy ||
      busy
    ) return
    if (autoBriefKeyRef.current === currentBriefKey) return
    autoBriefKeyRef.current = currentBriefKey
    void handlePlanStory()
  }, [
    activeBriefResponse,
    briefBusy,
    busy,
    currentBriefKey,
    guideBusy,
    guideReadyToBrief,
    hasSeed,
    privacyPromptVisible,
  ])

  const handleApplyRevisionAction = (seedAppend: string) => {
    const decision = advanceStoryGuideLoop(guideLoopState, seedAppend, uiLang)
    applyStoryGuideSettings(decision.settings)
    setSeed((current) => {
      const trimmed = current.trim()
      if (trimmed.toLowerCase().includes(seedAppend.toLowerCase())) return current
      return `${trimmed}${trimmed ? "\n\n" : ""}${seedAppend}`
    })
    setGuideLoopState(decision.state)
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
        text: decision.reply,
        node: decision.node,
        state: decision.status,
        ledger: decision.ledger,
      },
    ])
    setBriefResponse(null)
    setBriefResponseKey(null)
    setBriefError(null)
    window.requestAnimationFrame(() => seedTextareaRef.current?.focus())
  }

  const appendGuideTurn = async (rawText: string) => {
    const trimmed = rawText.trim()
    if (!trimmed) {
      setError(t("create.error_seed_required"))
      setGenerationError(false)
      return
    }
    if (guideBusy || briefBusy || busy) return
    const previousState = guideLoopState
    const previousSeed = seed
    const previousAssistantReply =
      [...chatMessages].reverse().find((message) => message.speaker === "guide")?.text ?? ""
    const time = Date.now()
    setDraftTurn("")
    setPrivacySetupVisible(false)
    setError(null)
    setGenerationError(false)
    setBriefResponse(null)
    setBriefResponseKey(null)
    setBriefError(null)
    setGuideBusy(true)
    setChatMessages((current) => [
      ...current,
      {
        id: `user-${time}-${current.length}`,
        speaker: "user",
        text: trimmed,
      },
    ])
    const applyGuideResponse = (response: GuideTurnLike) => {
      const normalizedSettings: StoryGuideSettingDeltas | undefined = response.settings
        ? {
            turnBudget: response.settings.turnBudget ?? undefined,
            difficulty: response.settings.difficulty ?? undefined,
            language: response.settings.language ?? undefined,
            tensionProfile: response.settings.tensionProfile ?? undefined,
            privacyIntent: response.settings.privacyIntent ?? undefined,
          }
        : undefined
      applyStoryGuideSettings(normalizedSettings)
      if (normalizedSettings?.privacyIntent) setPrivacyPromptVisible(true)
      const hadSeed = Boolean(previousSeed.trim())
      if (response.acceptedText) {
        const nextSeed = `${previousSeed.trim()}${hadSeed ? "\n\n" : ""}${trimmed}`
        setSeed(nextSeed)
        if (hadSeed) setCorrectionCount((current) => current + 1)
      }
      setGuideLoopState(response.state)
      setChatMessages((current) => [
        ...current,
        {
          id: `guide-${time}-${current.length}`,
          speaker: "guide",
          text: normalizeGuideReplyText(response.reply) || t("create.guide_fallback_reply"),
          node: response.node,
          state: response.status,
          ledger: response.ledger ?? undefined,
        },
      ])
      if (!response.acceptedText) focusComposer()
    }
    try {
      const authorReady = await ensureAuthorSession()
      if (!authorReady) return
      const response = await api.createNarrativeStoryGuideTurn({
        message: trimmed,
        language: storyLanguage,
        current_seed: previousSeed,
        previous_assistant_reply: previousAssistantReply,
        state: previousState,
      })
      applyGuideResponse(response)
    } catch (_err) {
      const decision = advanceStoryGuideLoop(previousState, trimmed, uiLang)
      applyGuideResponse(decision)
    } finally {
      setGuideBusy(false)
    }
  }

  const focusComposer = () => {
    window.requestAnimationFrame(() => seedTextareaRef.current?.focus())
  }

  useEffect(() => {
    const handoff = takeCreateDraftHandoff()
    if (!handoff) return
    const trimmed = handoff.seed.trim()
    if (!trimmed) return
    const decision = advanceStoryGuideLoop(createInitialStoryGuideState(uiLang), trimmed, uiLang)
    const time = Date.now()
    applyStoryGuideSettings(decision.settings)
    if (handoff.language) setStoryLanguage(handoff.language)
    if (handoff.tensionProfile) setDesiredTensionProfile(handoff.tensionProfile)
    setSeed(trimmed)
    setDraftTurn("")
    setGuideLoopState(decision.state)
    setBriefResponse(null)
    setBriefResponseKey(null)
    setBriefError(null)
    setError(null)
    setGenerationError(false)
    setPrivacySetupVisible(false)
    setPrivacyPromptVisible(false)
    setPrivacyRecordedVisibility("private")
    setChatMessages([
      {
        id: `user-handoff-${time}`,
        speaker: "user",
        text: trimmed,
      },
      {
        id: `guide-handoff-${time}`,
        speaker: "guide",
        text: decision.reply,
        node: decision.node,
        state: decision.status,
        ledger: decision.ledger,
      },
    ])
  }, [uiLang])

  return (
    <div
      style={{ ...cpStyles.page, ...(compactLayout ? cpStyles.pageCompact : null) }}
      data-guide-loop-state={guideLoopState.status}
      data-guide-loop-node={guideLoopState.lastNode}
    >
      <header style={{ ...cpStyles.header, ...(compactLayout ? cpStyles.headerCompact : null) }}>
        <div style={cpStyles.headerNav}>
          <button style={{ ...cpStyles.topBackButton, ...(compactLayout ? cpStyles.topBackButtonCompact : null) }} onClick={onBackHome} type="button">
            {t("create.cta_back")}
          </button>
          <button style={{ ...cpStyles.brandLink, ...(compactLayout ? cpStyles.brandLinkCompact : null) }} onClick={onBackHome} type="button">
            <span style={{ ...cpStyles.brandMark, ...(compactLayout ? cpStyles.brandMarkCompact : null) }} aria-hidden>✦</span>
            <span style={{ ...cpStyles.brandName, ...(compactLayout ? cpStyles.brandNameCompact : null) }}>Tiny Stories</span>
          </button>
        </div>
        <div style={{ ...cpStyles.headerTools, ...(compactLayout ? cpStyles.headerToolsCompact : null) }} aria-hidden>
          <span style={cpStyles.headerTool}>☼</span>
          <span style={cpStyles.headerTool}>?</span>
          <span style={cpStyles.headerTool}>☰</span>
        </div>
      </header>

      <main style={{ ...cpStyles.main, ...(compactLayout ? cpStyles.mainCompact : null) }}>
        <motion.div
          style={{ ...cpStyles.inner, ...(compactLayout ? cpStyles.innerCompact : null) }}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={itemTransition}
        >
          <div
            ref={transcriptScrollRef}
            style={{ ...cpStyles.guideTranscript, ...(compactLayout ? cpStyles.guideTranscriptCompact : null) }}
          >
            {guideMessages.map((message) => {
              const isUser = message.speaker === "user"
              const isIntro = message.id === "guide-privacy-open" || message.id === "guide-privacy-greeting"
              const isIntroFollow = false
              return (
                <div
                  key={message.id}
                  data-guide-node={message.node ?? "static_opening"}
                  data-guide-state={message.state ?? (isUser ? "collecting" : "empty")}
                  style={{
                    ...cpStyles.guideMessage,
                    ...(isUser ? cpStyles.guideMessageUser : cpStyles.guideMessageGuide),
                    ...(isIntro ? cpStyles.guideMessageIntro : null),
                    ...(isIntroFollow ? cpStyles.guideMessageIntroFollow : null),
                    ...(compactLayout ? cpStyles.guideMessageCompact : null),
                    ...(compactLayout && isUser ? cpStyles.guideMessageUserCompact : null),
                    ...(compactLayout && isIntroFollow ? cpStyles.guideMessageIntroFollowCompact : null),
                  }}
                >
                  {!isUser && !isIntroFollow ? (
                    <img
                      src={STORY_BUTLER_AVATAR}
                      alt=""
                      style={{
                        ...cpStyles.guideAvatar,
                        ...(isIntro ? cpStyles.guideAvatarIntro : null),
                        ...(compactLayout ? cpStyles.guideAvatarCompact : null),
                      }}
                    />
                  ) : !isUser ? (
                    <span
                      aria-hidden
                      style={{ ...cpStyles.guideAvatarSpacer, ...(compactLayout ? cpStyles.guideAvatarSpacerCompact : null) }}
                    />
                  ) : null}
                  <div
                    style={{
                      ...cpStyles.guideMessageContent,
                      ...(isUser ? cpStyles.guideMessageContentUser : null),
                      ...(isIntroFollow ? cpStyles.guideMessageContentIntroFollow : null),
                      ...(message.state === "redirect" ? cpStyles.guideMessageContentRedirect : null),
                      ...(message.state === "needs_field" ? cpStyles.guideMessageContentNeedsField : null),
                      ...(message.state === "ready_to_brief" ? cpStyles.guideMessageContentReady : null),
                    }}
                  >
                    {!isIntroFollow ? (
                      <span style={cpStyles.guideSpeaker}>
                        {isUser ? t("create.guide_user_label") : t("create.guide_agent_label")}
                      </span>
                    ) : null}
                    <span
                      style={{
                        ...cpStyles.guideMessageText,
                        ...(isIntro ? cpStyles.guideMessageIntroText : null),
                        ...(isIntro && compactLayout ? cpStyles.guideMessageIntroTextCompact : null),
                        ...(isIntroFollow ? cpStyles.guideMessageIntroFollowText : null),
                        ...(isUser ? cpStyles.guideMessageUserText : null),
                      }}
                    >
                      {message.text}
                    </span>
                  </div>
                </div>
              )
            })}
            {(privacySetupVisible || privacyPromptVisible) && !activeBriefResponse ? (
              <div
                data-create-privacy-settings="true"
                data-create-privacy-mode={privacyPromptVisible ? "confirmation" : "setup"}
                style={{
                  ...cpStyles.privacySetupCard,
                  ...(compactLayout ? cpStyles.privacySetupCardCompact : null),
                }}
              >
                <div style={cpStyles.privacySetupHeader}>
                  <span style={cpStyles.privacySetupTitle}>{t("create.privacy_setup_title")}</span>
                  <button
                    type="button"
                    style={cpStyles.privacySetupDismiss}
                    onClick={hidePrivacySetup}
                  >
                    {t("create.privacy_setup_keep", { value: t(selectedVisibility.labelKey) })}
                  </button>
                </div>
                <p style={cpStyles.privacySetupCopy}>
                  {privacyPromptVisible
                    ? t("create.privacy_setup_prompt_desc")
                    : t("create.privacy_setup_desc", { value: t(selectedVisibility.labelKey) })}
                </p>
                <div style={cpStyles.privacySetupChoices} aria-label={t("create.field_visibility")}>
                  {VISIBILITY_OPTION_IDS.map((id) => {
                    const meta = VISIBILITY_KEY_MAP[id]
                    return (
                      <button
                        key={id}
                        type="button"
                        style={{
                          ...cpStyles.privacySetupChoice,
                          ...(visibility === id ? cpStyles.privacySetupChoiceActive : null),
                        }}
                        onClick={() => handleVisibilityChoice(id)}
                        disabled={busy || briefBusy || guideBusy}
                        title={t(meta.descKey)}
                        aria-pressed={visibility === id}
                        data-create-privacy-choice={id}
                      >
                        <span style={cpStyles.privacySetupChoiceLabel}>{t(meta.labelKey)}</span>
                        <span
                          data-create-privacy-choice-desc="true"
                          style={cpStyles.privacySetupChoiceDesc}
                        >
                          {t(meta.descKey)}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ) : null}
            {!privacySetupVisible && !privacyPromptVisible && !activeBriefResponse ? (
              <div
                data-create-privacy-summary="true"
                style={{
                  ...cpStyles.privacySummary,
                  ...(compactLayout ? cpStyles.privacySummaryCompact : null),
                }}
              >
                <span style={cpStyles.privacySummaryCopy}>
                  <span style={cpStyles.privacySummaryLabel}>{t("create.privacy_summary_label")}</span>
                  <strong style={cpStyles.privacySummaryValue}>{t(selectedVisibility.labelKey)}</strong>
                </span>
                <button
                  type="button"
                  style={cpStyles.privacySummaryChange}
                  onClick={() => setPrivacySetupVisible(true)}
                  disabled={busy || briefBusy || guideBusy}
                  data-create-privacy-change="true"
                >
                  {t("create.privacy_summary_change")}
                </button>
              </div>
            ) : null}
            {briefBusy ? (
              <div
                data-guide-node="shape_story_brief"
                data-guide-state="analyzing"
                style={{
                  ...cpStyles.guideMessage,
                  ...cpStyles.guideMessageGuide,
                  ...(compactLayout ? cpStyles.guideMessageCompact : null),
                }}
              >
                <img
                  src={STORY_BUTLER_AVATAR}
                  alt=""
                  style={{
                    ...cpStyles.guideAvatar,
                    ...cpStyles.guideAvatarAnalyzing,
                    ...(compactLayout ? cpStyles.guideAvatarCompact : null),
                  }}
                />
                <div style={{ ...cpStyles.guideMessageContent, ...cpStyles.guideMessageBody }}>
                  <span style={cpStyles.guideSpeaker}>{t("create.guide_agent_label")}</span>
                  <span style={cpStyles.guideMessageText} aria-live="polite">{briefPlanningCopy}</span>
                  <span style={cpStyles.guideScanStages} aria-hidden>
                    <span>Lining up cast</span>
                    <span>Locking pressure</span>
                    <span>Checking boundaries</span>
                    <span>Writing plan</span>
                  </span>
                  <span style={cpStyles.guideScanRail} aria-hidden>
                    <motion.span
                      style={cpStyles.guideScanPulse}
                      animate={{ x: ["-120%", "260%"] }}
                      transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut" }}
                    />
                  </span>
                </div>
              </div>
            ) : null}
            {guideBusy ? (
              <div
                data-guide-node="story_butler_turn"
                data-guide-state="analyzing"
                data-guide-process="story_guide.live"
                data-guide-stage="slot_focus"
                style={{
                  ...cpStyles.guideMessage,
                  ...cpStyles.guideMessageGuide,
                  ...(compactLayout ? cpStyles.guideMessageCompact : null),
                }}
              >
                <img
                  src={STORY_BUTLER_AVATAR}
                  alt=""
                  style={{
                    ...cpStyles.guideAvatar,
                    ...cpStyles.guideAvatarAnalyzing,
                    ...(compactLayout ? cpStyles.guideAvatarCompact : null),
                  }}
                />
                <div style={{ ...cpStyles.guideMessageContent, ...cpStyles.guideMessageBody }}>
                  <span style={cpStyles.guideSpeaker}>{t("create.guide_agent_label")}</span>
                  <span style={cpStyles.guideMessageText} aria-live="polite">{guideThinkingCopy}</span>
                </div>
              </div>
            ) : null}
            {activeBriefResponse ? (
              <>
                <div
                  ref={briefMessageRef}
                  data-guide-node={activeBriefResponse.can_generate ? "brief_ready" : "brief_not_fit"}
                  data-guide-state={activeBriefResponse.can_generate ? "brief_ready" : "brief_not_fit"}
                  style={{
                    ...cpStyles.guideMessage,
                    ...cpStyles.guideMessageGuide,
                    ...(compactLayout ? cpStyles.guideMessageCompact : null),
                  }}
                >
                  <img
                    src={STORY_BUTLER_AVATAR}
                    alt=""
                    style={{ ...cpStyles.guideAvatar, ...(compactLayout ? cpStyles.guideAvatarCompact : null) }}
                  />
                  <div style={{ ...cpStyles.guideMessageContent, ...cpStyles.guideMessageBody }}>
                    <span style={cpStyles.guideSpeaker}>{t("create.guide_agent_label")}</span>
                    <StoryBriefCard
                      brief={activeBriefResponse.brief}
                      canGenerate={activeBriefResponse.can_generate}
                      nextStep={activeBriefResponse.next_step}
                      compact={compactLayout}
                      busy={busy}
                      shapeRead={storyShapeRead}
                      onGenerate={() => void handleCreate()}
                      onKeepCorrecting={focusComposer}
                      onApplyRevisionAction={handleApplyRevisionAction}
                    />
                  </div>
                </div>
                <div
                  data-guide-node={activeBriefResponse.can_generate ? "brief_ready" : "brief_not_fit"}
                  data-guide-state={activeBriefResponse.can_generate ? "brief_ready" : "brief_not_fit"}
                  style={{
                    ...cpStyles.guideMessage,
                    ...cpStyles.guideMessageGuide,
                    ...(compactLayout ? cpStyles.guideMessageCompact : null),
                  }}
                >
                  <img
                    src={STORY_BUTLER_AVATAR}
                    alt=""
                    style={{ ...cpStyles.guideAvatarSmall, ...(compactLayout ? cpStyles.guideAvatarSmallCompact : null) }}
                  />
                  <div style={cpStyles.guideMessageContent}>
                    <span style={cpStyles.guideSpeaker}>{t("create.guide_agent_label")}</span>
                    <span style={cpStyles.guideMessageText}>
                    {activeBriefResponse.can_generate
                      ? t("create.guide_brief_ready")
                      : t("create.guide_brief_not_fit")}
                    </span>
                  </div>
                </div>
              </>
            ) : null}
            <div ref={transcriptEndRef} aria-hidden />
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
                animate={{ opacity: 1, y: 0, height: "auto", marginBottom: 14 }}
                exit={{ opacity: 0, y: -4, height: 0, marginBottom: 0 }}
                transition={itemTransition}
              >
                <div style={cpStyles.seedRecipe} data-create-seed-recipe="true">
                  <span style={cpStyles.examplesLabel}>{t("create.seed_recipe_label")}</span>
                  <span style={cpStyles.seedRecipeLine}>
                    <strong>{t("create.seed_recipe_people_label")}</strong>
                    <span>{t("create.seed_recipe_people_detail")}</span>
                  </span>
                  <span style={cpStyles.seedRecipeLine}>
                    <strong>{t("create.seed_recipe_pressure_label")}</strong>
                    <span>{t("create.seed_recipe_pressure_detail")}</span>
                  </span>
                  <span style={cpStyles.seedRecipeLine}>
                    <strong>{t("create.seed_recipe_secret_label")}</strong>
                    <span>{t("create.seed_recipe_secret_detail")}</span>
                  </span>
                </div>
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
                        setDraftTurn(example)
                        window.requestAnimationFrame(() => {
                          const node = seedTextareaRef.current
                          if (!node) return
                          node.focus({ preventScroll: true })
                        })
                      }}
                      disabled={busy || briefBusy || guideBusy}
                      type="button"
                      aria-label={t("create.example_aria", { n: index + 1, example })}
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

          {privacyIntroComplete ? (
            <>
              <div
                style={{
                  ...cpStyles.textareaWrap,
                  ...(compactLayout ? cpStyles.textareaWrapCompact : null),
                  ...(activeBrief ? cpStyles.textareaWrapAfterBrief : null),
                }}
              >
                <textarea
                  ref={seedTextareaRef}
                  rows={1}
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
                      if (draftTurn.trim()) {
                        void appendGuideTurn(draftTurn)
                        return
                      }
                      return
                    }
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      void appendGuideTurn(draftTurn)
                    }
                  }}
                  spellCheck={false}
                  disabled={busy || briefBusy || guideBusy}
                />
                <div style={{ ...cpStyles.composerBar, ...(compactLayout ? cpStyles.composerBarCompact : null) }}>
                  <span style={cpStyles.composerHint}>{t("create.guide_input_hint")}</span>
                  <div style={{ ...cpStyles.composerCommands, ...(compactLayout ? cpStyles.composerCommandsCompact : null) }}>
                    <button
                      type="button"
                      style={cpStyles.composerAction}
                      disabled={!draftTurn.trim() || busy || briefBusy || guideBusy}
                      onClick={() => void appendGuideTurn(draftTurn)}
                    >
                      {composerActionLabel}
                    </button>
                  </div>
                </div>
              </div>
              <div style={cpStyles.editorMeta}>
                <span style={cpStyles.count}>{t("create.char_count", { n: draftTurn.length })}</span>
                {correctionCount > 0 ? (
                  <span style={cpStyles.count}>{t("create.guide_revision_count", { n: correctionCount })}</span>
                ) : null}
                {composerProgressHint ? (
                  <span style={cpStyles.shortcutHint}>
                    {composerProgressHint}
                  </span>
                ) : null}
              </div>
            </>
          ) : null}

          {error ? (
            generationError ? (
              <div
                ref={generationErrorRef}
                style={cpStyles.briefErrorPanel}
                data-create-generation-error="true"
              >
                <span style={cpStyles.briefErrorText}>{error}</span>
                <span style={cpStyles.briefErrorHint}>{t("create.generation_error_recovery_hint")}</span>
              </div>
            ) : (
              <div style={cpStyles.error}>{error}</div>
            )
          ) : null}
          {briefError ? (
            <div ref={briefErrorRef} style={cpStyles.briefErrorPanel} data-create-brief-error="true">
              <span style={cpStyles.briefErrorText}>{briefError}</span>
              <span style={cpStyles.briefErrorHint}>{t("create.brief_error_recovery_hint")}</span>
              {canRetryBrief ? (
                <button
                  type="button"
                  style={cpStyles.briefErrorAction}
                  onClick={() => void handlePlanStory()}
                >
                  {t("create.brief_retry_cta")}
                </button>
              ) : null}
            </div>
          ) : null}

          <AnimatePresence>
            {busy ? (
              <motion.div
                ref={generationHandoffRef}
                data-create-generation-handoff="true"
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
                <BusyBuildPreview activeIndex={busyStageIndex} compact={compactLayout} />
                <BusyTip />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </motion.div>
      </main>
    </div>
  )
}
