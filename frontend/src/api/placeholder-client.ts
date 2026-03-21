import {
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthSessionResponse,
  AuthUserResponse,
  AuthorJobCreateRequest,
  AuthorJobEvent,
  AuthorJobProgress,
  AuthorJobProgressSnapshot,
  AuthorJobResultResponse,
  AuthorJobStatusResponse,
  AuthorLoadingCard,
  AuthorPreviewRequest,
  AuthorPreviewResponse,
  AuthorPreviewFlashcard,
  AuthorStorySummary,
  CurrentActorResponse,
  DeleteStoryResponse,
  ListStoriesParams,
  PlayEnding,
  PlayFeedback,
  PlayProtagonist,
  PlaySessionHistoryEntry,
  PlaySessionHistoryResponse,
  PlaySessionProgress,
  PlaySessionCreateRequest,
  PlaySessionSnapshot,
  PlayStateBar,
  PlaySuggestedAction,
  PlaySupportSurfaces,
  PlayTurnRequest,
  PublishedStoryCard,
  PublishedStoryDetailResponse,
  PublishedStoryListResponse,
  PublishedStoryListSort,
  PublishedStoryListView,
  UpdateStoryVisibilityRequest,
} from "./contracts"

type PlaceholderActor = {
  user_id: string
  display_name: string
  email: string
  password: string
}

const AUTHOR_STAGE_FLOW = [
  "queued",
  "running",
  "brief_parsed",
  "brief_classified",
  "story_frame_ready",
  "theme_confirmed",
  "cast_planned",
  "cast_ready",
  "beat_plan_ready",
  "route_ready",
  "ending_ready",
  "completed",
] as const

const THEME_LABELS: Record<string, string> = {
  legitimacy_crisis: "Legitimacy crisis",
  logistics_quarantine_crisis: "Logistics quarantine crisis",
  truth_record_crisis: "Truth and record crisis",
  public_order_crisis: "Public order crisis",
  generic_civic_crisis: "Civic crisis",
}

const DEMO_STORIES: PublishedStoryCard[] = [
  {
    story_id: "demo-story-1",
    title: "Blind Capital",
    one_liner: "A royal archivist must prove a storm warning is real before the court buries it.",
    premise: "A royal archivist must prove a storm warning is real before the court buries it.",
    theme: "Legitimacy crisis",
    tone: "Procedural suspense",
    npc_count: 4,
    beat_count: 3,
    topology: "4-slot civic web",
    visibility: "public",
    viewer_can_manage: false,
    published_at: new Date().toISOString(),
  },
  {
    story_id: "demo-story-2",
    title: "Port of Strain",
    one_liner: "A harbor inspector must keep quarantine from turning into private rule.",
    premise: "A harbor inspector must keep quarantine from turning into private rule.",
    theme: "Logistics quarantine crisis",
    tone: "Tense civic fantasy",
    npc_count: 4,
    beat_count: 3,
    topology: "4-slot civic web",
    visibility: "public",
    viewer_can_manage: false,
    published_at: new Date().toISOString(),
  },
]

type PlaceholderAuthorJob = {
  jobId: string
  promptSeed: string
  preview: AuthorPreviewResponse
  createdAtMs: number
  publishedStoryId?: string
}

type PlaceholderPlaySession = {
  sessionId: string
  storyId: string
  storyTitle: string
  ownerUserId: string
  turnIndex: number
  beatIndex: number
  history: PlaySessionHistoryEntry[]
  protagonist: PlayProtagonist
  feedback: PlayFeedback
  stateBars: PlayStateBar[]
  suggestedActions: PlaySuggestedAction[]
  narration: string
  ending: PlayEnding | null
}

export type FrontendApiClient = {
  getAuthSession(): Promise<AuthSessionResponse>
  registerAuth(request: AuthRegisterRequest): Promise<AuthSessionResponse>
  loginAuth(request: AuthLoginRequest): Promise<AuthSessionResponse>
  logoutAuth(): Promise<void>
  getCurrentActor(): Promise<CurrentActorResponse>
  createStoryPreview(request: AuthorPreviewRequest): Promise<AuthorPreviewResponse>
  createAuthorJob(request: AuthorJobCreateRequest): Promise<AuthorJobStatusResponse>
  getAuthorJob(jobId: string): Promise<AuthorJobStatusResponse>
  streamAuthorJobEvents(jobId: string, lastEventId?: number): AsyncGenerator<AuthorJobEvent, void, void>
  getAuthorJobResult(jobId: string): Promise<AuthorJobResultResponse>
  publishAuthorJob(jobId: string, visibility?: "private" | "public"): Promise<PublishedStoryCard>
  listStories(params?: ListStoriesParams): Promise<PublishedStoryListResponse>
  getStory(storyId: string): Promise<PublishedStoryDetailResponse>
  updateStoryVisibility(storyId: string, request: UpdateStoryVisibilityRequest): Promise<PublishedStoryCard>
  deleteStory(storyId: string): Promise<DeleteStoryResponse>
  createPlaySession(request: PlaySessionCreateRequest): Promise<PlaySessionSnapshot>
  getPlaySession(sessionId: string): Promise<PlaySessionSnapshot>
  getPlaySessionHistory(sessionId: string): Promise<PlaySessionHistoryResponse>
  submitPlayTurn(sessionId: string, request: PlayTurnRequest): Promise<PlaySessionSnapshot>
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
}

function relevanceScore(story: PublishedStoryCard, query: string): number {
  const lowered = query.toLowerCase()
  const fields = [
    { value: story.title, weight: 6 },
    { value: story.one_liner, weight: 4 },
    { value: story.premise, weight: 3 },
    { value: story.theme, weight: 2 },
    { value: story.tone, weight: 1 },
  ]
  return fields.reduce((score, field) => {
    return score + (field.value.toLowerCase().includes(lowered) ? field.weight : 0)
  }, 0)
}

function listStoriesResponse(
  stories: PublishedStoryCard[],
  params: ListStoriesParams = {},
): PublishedStoryListResponse {
  const query = params.q?.trim() || null
  const theme = params.theme?.trim() || null
  const view: PublishedStoryListView = params.view ?? "accessible"
  const limit = params.limit ?? 20
  const sort: PublishedStoryListSort = params.sort ?? (query ? "relevance" : "published_at_desc")
  const offset = Number.parseInt(params.cursor ?? "0", 10)
  const normalizedOffset = Number.isFinite(offset) && offset > 0 ? offset : 0

  let filteredStories = [...stories]
  if (query) {
    filteredStories = filteredStories.filter((story) =>
      [story.title, story.one_liner, story.premise, story.theme, story.tone].some((value) =>
        value.toLowerCase().includes(query.toLowerCase()),
      ),
    )
  }

  const themeFacets = Array.from(
    filteredStories.reduce((counts, story) => {
      counts.set(story.theme, (counts.get(story.theme) ?? 0) + 1)
      return counts
    }, new Map<string, number>()),
  )
    .map(([facetTheme, count]) => ({ theme: facetTheme, count }))
    .sort((left, right) => right.count - left.count || left.theme.localeCompare(right.theme))

  if (theme) {
    filteredStories = filteredStories.filter((story) => story.theme.toLowerCase() === theme.toLowerCase())
  }

  filteredStories.sort((left, right) => {
    if (sort === "relevance" && query) {
      const scoreDelta = relevanceScore(right, query) - relevanceScore(left, query)
      if (scoreDelta !== 0) {
        return scoreDelta
      }
    }
    return new Date(right.published_at).getTime() - new Date(left.published_at).getTime()
  })

  const total = filteredStories.length
  const pageStories = filteredStories.slice(normalizedOffset, normalizedOffset + limit)
  const nextCursor = normalizedOffset + limit < total ? String(normalizedOffset + limit) : null

  return {
    stories: pageStories,
    meta: {
      query,
      theme,
      view,
      sort,
      limit,
      next_cursor: nextCursor,
      has_more: nextCursor !== null,
      total,
    },
    facets: {
      themes: themeFacets,
    },
  }
}

function classifyTheme(seed: string): { id: string; label: string } {
  const haystack = seed.toLowerCase()
  if (/(harbor|port|trade|quarantine|supply|bridge|flood|ration|ward|district)/.test(haystack)) {
    return { id: "logistics_quarantine_crisis", label: THEME_LABELS.logistics_quarantine_crisis }
  }
  if (/(archive|ledger|record|witness|testimony|evidence)/.test(haystack)) {
    return { id: "truth_record_crisis", label: THEME_LABELS.truth_record_crisis }
  }
  if (/(succession|election|vote|council|coalition|legitimacy|mandate)/.test(haystack)) {
    return { id: "legitimacy_crisis", label: THEME_LABELS.legitimacy_crisis }
  }
  if (/(blackout|panic|riot|curfew|martial law)/.test(haystack)) {
    return { id: "public_order_crisis", label: THEME_LABELS.public_order_crisis }
  }
  return { id: "generic_civic_crisis", label: THEME_LABELS.generic_civic_crisis }
}

function buildPreview(seed: string): AuthorPreviewResponse {
  const theme = classifyTheme(seed)
  const previewId = crypto.randomUUID()
  const title =
    theme.id === "logistics_quarantine_crisis"
      ? "Port of Strain"
      : theme.id === "truth_record_crisis"
        ? "Voting Ledger"
        : theme.id === "legitimacy_crisis"
          ? "Blind Capital"
          : "Civic Faultline"
  const premise =
    theme.id === "logistics_quarantine_crisis"
      ? "In a city under ration strain and infrastructure pressure, a public works lead must expose the staged convoy diversions before emergency command hardens into habit."
      : theme.id === "truth_record_crisis"
        ? "In a civic archive where public trust depends on verified records, an archivist must restore one binding record before rumor hardens into law."
        : theme.id === "legitimacy_crisis"
          ? "In a civic system where emergency authority is outrunning public legitimacy, one official must force the truth into the open before the mandate calcifies."
          : "In a city under blackout strain, a civic investigator must expose the hidden manipulation before panic becomes the governing logic."
  const tone =
    theme.id === "logistics_quarantine_crisis"
      ? "Tense civic fantasy"
      : theme.id === "truth_record_crisis"
        ? "Procedural civic suspense"
        : "Political civic drama"
  const flashcards: AuthorPreviewFlashcard[] = [
    { card_id: "theme", kind: "stable", label: "Theme", value: theme.label },
    { card_id: "tone", kind: "stable", label: "Tone", value: tone },
    { card_id: "npc_count", kind: "stable", label: "NPC Count", value: "4" },
    { card_id: "beat_count", kind: "stable", label: "Beat Count", value: "3" },
    { card_id: "cast_topology", kind: "stable", label: "Cast Structure", value: "4-slot civic web" },
    { card_id: "title", kind: "draft", label: "Working Title", value: title },
    { card_id: "conflict", kind: "draft", label: "Core Conflict", value: seed.slice(0, 140) },
  ]
  return {
    preview_id: previewId,
    prompt_seed: seed,
    focused_brief: {
      story_kernel: seed.slice(0, 120),
      setting_signal: seed.slice(0, 120),
      core_conflict: seed.slice(0, 180),
      tone_signal: tone,
      hard_constraints: [],
      forbidden_tones: [],
    },
    theme: {
      primary_theme: theme.id,
      modifiers: [],
      router_reason: "placeholder_theme_router",
    },
    strategies: {
      story_frame_strategy: "placeholder_story",
      cast_strategy: "placeholder_cast",
      beat_plan_strategy: "placeholder_beats",
    },
    structure: {
      cast_topology: "four_slot",
      expected_npc_count: 4,
      expected_beat_count: 3,
    },
    story: {
      title,
      premise,
      tone,
      stakes: "If the crisis is mishandled, public trust and civic order break at the same time.",
    },
    cast_slots: [
      { slot_label: "Mediator Anchor", public_role: "Lead civic actor" },
      { slot_label: "Institutional Guardian", public_role: "Procedural authority" },
      { slot_label: "Leverage Broker", public_role: "Political rival" },
      { slot_label: "Civic Witness", public_role: "Public pressure voice" },
    ],
    beats: [
      { title: "Opening Pressure", goal: "Figure out what is breaking first.", milestone_kind: "reveal" },
      { title: "Public Strain", goal: "Hold the coalition together in public.", milestone_kind: "containment" },
      { title: "Final Settlement", goal: "Force one visible ending to the crisis.", milestone_kind: "commitment" },
    ],
    flashcards,
    stage: "brief_parsed",
  }
}

function progressSnapshot(preview: AuthorPreviewResponse, stage: string, stageIndex: number): AuthorJobProgressSnapshot {
  const loadingCards: AuthorLoadingCard[] = [
    { card_id: "theme", emphasis: "stable", label: "Theme", value: THEME_LABELS[preview.theme.primary_theme] ?? preview.theme.primary_theme },
    { card_id: "structure", emphasis: "stable", label: "Story Shape", value: "4-slot civic web" },
  ]
  if (stageIndex >= 5) {
    loadingCards.push(
      { card_id: "working_title", emphasis: "draft", label: "Working Title", value: preview.story.title },
      { card_id: "tone", emphasis: "stable", label: "Tone", value: preview.story.tone },
      { card_id: "story_premise", emphasis: "draft", label: "Story Premise", value: preview.story.premise },
      { card_id: "story_stakes", emphasis: "draft", label: "Story Stakes", value: preview.story.stakes },
    )
  }
  if (stageIndex >= 7) {
    loadingCards.push(
      { card_id: "cast_count", emphasis: "stable", label: "NPC Count", value: "4 NPCs drafted" },
      { card_id: "cast_anchor", emphasis: "draft", label: "Cast Anchor", value: `${preview.cast_slots[0]?.slot_label ?? "Mediator Anchor"} · ${preview.cast_slots[0]?.public_role ?? "Lead civic actor"}` },
    )
  }
  if (stageIndex >= 9) {
    loadingCards.push(
      { card_id: "beat_count", emphasis: "stable", label: "Beat Count", value: "3 beats drafted" },
      { card_id: "opening_beat", emphasis: "draft", label: "Opening Beat", value: `${preview.beats[0]?.title ?? "Opening Pressure"}: ${preview.beats[0]?.goal ?? "Figure out what is breaking first."}` },
      { card_id: "final_beat", emphasis: "draft", label: "Final Beat", value: `${preview.beats[2]?.title ?? "Final Settlement"}: ${preview.beats[2]?.goal ?? "Force one visible ending to the crisis."}` },
    )
  }
  const totalTokens = 1200 + stageIndex * 420
  const estimatedUsd = (0.000141 * (totalTokens / 300)).toFixed(6)
  loadingCards.push(
    { card_id: "generation_status", emphasis: "live", label: "Generation Status", value: stage.replace(/_/g, " ") },
    { card_id: "token_budget", emphasis: "live", label: "Token Budget", value: `${totalTokens} total tokens · USD ${estimatedUsd} est.` },
  )
  return {
    stage,
    stage_label: stage.replace(/_/g, " "),
    stage_index: stageIndex,
    stage_total: AUTHOR_STAGE_FLOW.length,
    completion_ratio: Number((stageIndex / AUTHOR_STAGE_FLOW.length).toFixed(3)),
    primary_theme: preview.theme.primary_theme,
    cast_topology: preview.structure.cast_topology,
    expected_npc_count: preview.structure.expected_npc_count,
    expected_beat_count: preview.structure.expected_beat_count,
    preview_title: preview.story.title,
    preview_premise: preview.story.premise,
    flashcards: preview.flashcards,
    loading_cards: loadingCards,
  }
}

function stageForJob(createdAtMs: number): { status: AuthorJobStatusResponse["status"]; stage: string; stageIndex: number } {
  const elapsed = Date.now() - createdAtMs
  const index = Math.min(Math.floor(elapsed / 1200), AUTHOR_STAGE_FLOW.length - 1)
  const stage = AUTHOR_STAGE_FLOW[index]
  if (stage === "queued") return { status: "queued", stage, stageIndex: 1 }
  if (stage === "completed") return { status: "completed", stage, stageIndex: AUTHOR_STAGE_FLOW.length }
  return { status: "running", stage, stageIndex: index + 1 }
}

function summaryFromPreview(preview: AuthorPreviewResponse): AuthorStorySummary {
  return {
    title: preview.story.title,
    one_liner: preview.story.premise.slice(0, 220),
    premise: preview.story.premise,
    tone: preview.story.tone,
    theme: THEME_LABELS[preview.theme.primary_theme] ?? preview.theme.primary_theme,
    npc_count: preview.structure.expected_npc_count,
    beat_count: preview.structure.expected_beat_count,
  }
}

function buildPlaySnapshot(session: PlaceholderPlaySession): PlaySessionSnapshot {
  const progress: PlaySessionProgress = {
    completed_beats: Math.max(0, session.beatIndex - 1),
    total_beats: 3,
    current_beat_progress: session.ending ? 1 : Math.min(1, session.turnIndex === 0 ? 0 : 1),
    current_beat_goal: 1,
    turn_index: session.turnIndex,
    max_turns: 4,
    completion_ratio: session.ending ? 1 : Number((((Math.max(0, session.beatIndex - 1) + Math.min(1, session.turnIndex === 0 ? 0 : 1)) / 3)).toFixed(3)),
    display_percent: session.ending ? 100 : Math.round(((Math.max(0, session.beatIndex - 1) + Math.min(1, session.turnIndex === 0 ? 0 : 1)) / 3) * 100),
  }
  const supportSurfaces: PlaySupportSurfaces = {
    inventory: {
      enabled: false,
      disabled_reason: "Inventory is not authored for this placeholder runtime yet.",
    },
    map: {
      enabled: false,
      disabled_reason: "Map data is not available for this placeholder runtime yet.",
    },
  }
  return {
    session_id: session.sessionId,
    story_id: session.storyId,
    status: session.ending ? "completed" : "active",
    turn_index: session.turnIndex,
    beat_index: session.beatIndex,
    beat_title: ["Opening Pressure", "Public Strain", "Final Settlement"][session.beatIndex - 1] ?? "Final Settlement",
    story_title: session.storyTitle,
    narration: session.narration,
    protagonist: session.protagonist,
    feedback: session.feedback,
    progress,
    support_surfaces: supportSurfaces,
    state_bars: session.stateBars,
    suggested_actions: session.ending ? [] : session.suggestedActions,
    ending: session.ending,
  }
}

function nextEndingForStory(storyTitle: string, turnIndex: number): PlayEnding | null {
  if (turnIndex < 4) return null
  if (/blind/i.test(storyTitle)) {
    return { ending_id: "collapse", label: "Collapse", summary: "The crisis outruns coordination." }
  }
  if (/ledger|record/i.test(storyTitle)) {
    return { ending_id: "pyrrhic", label: "Pyrrhic Outcome", summary: "The truth holds, but at a steep civic cost." }
  }
  return { ending_id: "mixed", label: "Mixed Outcome", summary: "The city stabilizes, but not cleanly." }
}

export function createPlaceholderApiClient(): FrontendApiClient {
  const previews = new Map<string, AuthorPreviewResponse>()
  const jobs = new Map<string, PlaceholderAuthorJob>()
  const stories = new Map<string, PublishedStoryCard>()
  const storyPreviews = new Map<string, AuthorPreviewResponse>()
  const sessions = new Map<string, PlaceholderPlaySession>()
  const storyOwners = new Map<string, string>()
  const users = new Map<string, PlaceholderActor>()
  let currentUser: PlaceholderActor | null = null

  for (const story of DEMO_STORIES) {
    stories.set(story.story_id, story)
    storyPreviews.set(story.story_id, buildPreview(story.one_liner))
    storyOwners.set(story.story_id, "public-demo")
  }

  const buildAuthSession = (): AuthSessionResponse => ({
    authenticated: currentUser !== null,
    user: currentUser
      ? {
          user_id: currentUser.user_id,
          display_name: currentUser.display_name,
          email: currentUser.email,
        }
      : null,
  })

  return {
    async getAuthSession() {
      return buildAuthSession()
    },

    async registerAuth(request) {
      const email = request.email.trim().toLowerCase()
      if (users.has(email)) {
        throw new Error("An account with that email already exists.")
      }
      currentUser = {
        user_id: crypto.randomUUID(),
        display_name: request.display_name.trim(),
        email,
        password: request.password,
      }
      users.set(email, currentUser)
      return buildAuthSession()
    },

    async loginAuth(request) {
      const email = request.email.trim().toLowerCase()
      const user = users.get(email)
      if (!user || user.password !== request.password) {
        throw new Error("Invalid email or password.")
      }
      currentUser = user
      return buildAuthSession()
    },

    async logoutAuth() {
      currentUser = null
    },

    async getCurrentActor() {
      if (!currentUser) {
        throw new Error("Sign in required.")
      }
      return {
        user_id: currentUser.user_id,
        display_name: currentUser.display_name,
        email: currentUser.email,
        is_default: false,
      }
    },

    async createStoryPreview(request) {
      const preview = buildPreview(request.prompt_seed)
      previews.set(preview.preview_id, preview)
      return preview
    },

    async createAuthorJob(request) {
      const preview = request.preview_id ? previews.get(request.preview_id) ?? buildPreview(request.prompt_seed) : buildPreview(request.prompt_seed)
      const jobId = crypto.randomUUID()
      jobs.set(jobId, {
        jobId,
        promptSeed: request.prompt_seed,
        preview,
        createdAtMs: Date.now(),
      })
      return this.getAuthorJob(jobId)
    },

    async getAuthorJob(jobId) {
      const job = jobs.get(jobId)
      if (!job) throw new Error(`Unknown placeholder job ${jobId}`)
      const stageState = stageForJob(job.createdAtMs)
      return {
        job_id: job.jobId,
        status: stageState.status,
        prompt_seed: job.promptSeed,
        preview: job.preview,
        progress: {
          stage: stageState.stage,
          stage_index: stageState.stageIndex,
          stage_total: AUTHOR_STAGE_FLOW.length,
        },
        progress_snapshot: progressSnapshot(job.preview, stageState.stage, stageState.stageIndex),
        cache_metrics: {
          session_cache_enabled: false,
          cache_path_used: false,
          total_call_count: stageState.stageIndex,
          previous_response_call_count: Math.max(0, stageState.stageIndex - 1),
          total_input_characters: job.promptSeed.length,
          estimated_input_tokens_from_chars: Math.ceil(job.promptSeed.length / 4),
          provider_usage: {},
          total_tokens: 1200 + stageState.stageIndex * 420,
          cache_metrics_source: "placeholder",
        },
        error: stageState.status === "failed" ? { code: "placeholder_job_failed", message: "Placeholder job failed." } : null,
      }
    },

    async *streamAuthorJobEvents(jobId, lastEventId = 0) {
      const stages = AUTHOR_STAGE_FLOW.slice(Math.max(0, lastEventId))
      let eventId = lastEventId
      for (const stage of stages) {
        eventId += 1
        const job = await this.getAuthorJob(jobId)
        yield {
          id: eventId,
          event: stage === "completed" ? "job_completed" : eventId === 1 ? "job_started" : "stage_changed",
          data: {
            job_id: job.job_id,
            status: stage === "completed" ? "completed" : "running",
            progress_snapshot: progressSnapshot(job.preview, stage, Math.min(eventId + 1, AUTHOR_STAGE_FLOW.length)),
          },
        }
      }
    },

    async getAuthorJobResult(jobId) {
      const job = jobs.get(jobId)
      if (!job) throw new Error(`Unknown placeholder job ${jobId}`)
      const stageState = stageForJob(job.createdAtMs)
      return {
        job_id: jobId,
        status: stageState.status,
        summary: stageState.status === "completed" ? summaryFromPreview(job.preview) : null,
        bundle: stageState.status === "completed" ? { story_bible: { title: job.preview.story.title } } : null,
        progress_snapshot: progressSnapshot(job.preview, stageState.stage, stageState.stageIndex),
        cache_metrics: {
          session_cache_enabled: false,
          cache_path_used: false,
          total_call_count: stageState.stageIndex,
          previous_response_call_count: Math.max(0, stageState.stageIndex - 1),
          total_input_characters: job.promptSeed.length,
          estimated_input_tokens_from_chars: Math.ceil(job.promptSeed.length / 4),
          provider_usage: {},
          total_tokens: 1200 + stageState.stageIndex * 420,
          cache_metrics_source: "placeholder",
        },
      }
    },

    async publishAuthorJob(jobId, visibility = "private") {
      const job = jobs.get(jobId)
      if (!job) throw new Error(`Unknown placeholder job ${jobId}`)
      const result = await this.getAuthorJobResult(jobId)
      if (result.status !== "completed" || !result.summary) {
        throw new Error("Placeholder job must be completed before publish.")
      }
      if (job.publishedStoryId) {
        return stories.get(job.publishedStoryId)!
      }
      const storyId = crypto.randomUUID()
      const card: PublishedStoryCard = {
        story_id: storyId,
        title: result.summary.title,
        one_liner: result.summary.one_liner,
        premise: result.summary.premise,
        theme: result.summary.theme,
        tone: result.summary.tone,
        npc_count: result.summary.npc_count,
        beat_count: result.summary.beat_count,
        topology: "4-slot civic web",
        visibility,
        viewer_can_manage: true,
        published_at: new Date().toISOString(),
      }
      job.publishedStoryId = storyId
      stories.set(storyId, card)
      storyPreviews.set(storyId, job.preview)
      storyOwners.set(storyId, currentUser?.user_id ?? "placeholder-owner")
      return card
    },

    async listStories(params) {
      const visibleStories = Array.from(stories.values())
        .filter((story) => {
          const ownerUserId = storyOwners.get(story.story_id) ?? "local-dev"
          if ((params?.view ?? "accessible") === "mine") {
            return ownerUserId === currentUser?.user_id
          }
          if ((params?.view ?? "accessible") === "public") {
            return story.visibility === "public"
          }
          return ownerUserId === currentUser?.user_id || story.visibility === "public"
        })
        .map((story) => {
          const ownerUserId = storyOwners.get(story.story_id) ?? "local-dev"
          return {
            ...story,
            viewer_can_manage: ownerUserId === currentUser?.user_id,
          }
        })
      return listStoriesResponse(visibleStories, params)
    },

    async getStory(storyId) {
      const story = stories.get(storyId)
      const preview = storyPreviews.get(storyId)
      if (!story || !preview) throw new Error(`Unknown placeholder story ${storyId}`)
      const ownerUserId = storyOwners.get(storyId) ?? "local-dev"
      if (ownerUserId !== currentUser?.user_id && story.visibility !== "public") {
        throw new Error(`Unknown placeholder story ${storyId}`)
      }
      const viewerCanManage = ownerUserId === currentUser?.user_id
      const viewerStory = { ...story, viewer_can_manage: viewerCanManage }
      return {
        story: viewerStory,
        preview,
        presentation: {
          dossier_ref: `Dossier N° ${story.story_id.slice(0, 3).toUpperCase()}`,
          status: "open_for_play",
          status_label: "Open for play",
          classification_label: preview.theme.primary_theme.replace(/_/g, " "),
          engine_label: "LangGraph play runtime",
          visibility: story.visibility,
          viewer_can_manage: viewerCanManage,
        },
        play_overview: {
          protagonist: {
            title: "Civic Lead",
            mandate: "Keep the crisis from breaking the city in public.",
            identity_summary: "You are the central civic actor driving the response. The named NPCs are stakeholders around you.",
          },
          opening_narration: `You step into ${story.title}. The crisis is already moving and the room expects you to act.`,
          runtime_profile: "placeholder_play_runtime",
          runtime_profile_label: "Placeholder Play Runtime",
          max_turns: 4,
        },
      }
    },

    async updateStoryVisibility(storyId, request) {
      const story = stories.get(storyId)
      if (!story) throw new Error(`Unknown placeholder story ${storyId}`)
      const ownerUserId = storyOwners.get(storyId) ?? "local-dev"
      if (ownerUserId !== currentUser?.user_id) throw new Error(`Unknown placeholder story ${storyId}`)
      const updatedStory = {
        ...story,
        visibility: request.visibility,
        viewer_can_manage: true,
      }
      stories.set(storyId, updatedStory)
      return updatedStory
    },

    async deleteStory(storyId) {
      const story = stories.get(storyId)
      if (!story) throw new Error(`Unknown placeholder story ${storyId}`)
      const ownerUserId = storyOwners.get(storyId) ?? "local-dev"
      if (ownerUserId !== currentUser?.user_id) throw new Error(`Unknown placeholder story ${storyId}`)
      stories.delete(storyId)
      storyPreviews.delete(storyId)
      storyOwners.delete(storyId)
      return {
        story_id: storyId,
        deleted: true,
      }
    },

    async createPlaySession(request) {
      const story = stories.get(request.story_id)
      if (!story) throw new Error(`Unknown placeholder story ${request.story_id}`)
      const ownerUserId = storyOwners.get(request.story_id) ?? "local-dev"
      if (ownerUserId !== currentUser?.user_id && story.visibility !== "public") {
        throw new Error(`Unknown placeholder story ${request.story_id}`)
      }
      const sessionId = crypto.randomUUID()
      const session: PlaceholderPlaySession = {
        sessionId,
        storyId: story.story_id,
        storyTitle: story.title,
        ownerUserId: currentUser?.user_id ?? "placeholder-owner",
        turnIndex: 0,
        beatIndex: 1,
        history: [
          {
            speaker: "gm",
            text: `You step into ${story.title}. The crisis is already moving and the room expects you to act.`,
            created_at: new Date().toISOString(),
            turn_index: 0,
          },
        ],
        protagonist: {
          title: "Civic Lead",
          mandate: "Keep the crisis from breaking the city in public.",
          identity_summary: "You are the central civic actor driving the response. The named NPCs are stakeholders around you.",
        },
        feedback: {
          ledgers: {
            success: {
              proof_progress: 0,
              coalition_progress: 0,
              order_progress: 0,
              settlement_progress: 0,
            },
            cost: {
              public_cost: 0,
              relationship_cost: 0,
              procedural_cost: 0,
              coercion_cost: 0,
            },
          },
          last_turn_axis_deltas: {},
          last_turn_stance_deltas: {},
          last_turn_tags: [],
          last_turn_consequences: [],
        },
        narration: `You step into ${story.title}. The crisis is already moving and the room expects you to act.`,
        stateBars: [
          { bar_id: "external_pressure", label: "External Pressure", category: "axis", current_value: 1, min_value: 0, max_value: 5 },
          { bar_id: "public_panic", label: "Public Panic", category: "axis", current_value: 0, min_value: 0, max_value: 5 },
          { bar_id: "political_leverage", label: "Political Leverage", category: "axis", current_value: 1, min_value: 0, max_value: 5 },
        ],
        suggestedActions: [
          { suggestion_id: "s1", label: "Expose the hidden pressure", prompt: "You pull the hidden pressure into the open." },
          { suggestion_id: "s2", label: "Stabilize the coalition", prompt: "You keep the coalition from fracturing in public." },
          { suggestion_id: "s3", label: "Force a public settlement", prompt: "You try to lock one visible outcome into place." },
        ],
        ending: null,
      }
      sessions.set(sessionId, session)
      return buildPlaySnapshot(session)
    },

    async getPlaySession(sessionId) {
      const session = sessions.get(sessionId)
      if (!session) throw new Error(`Unknown placeholder session ${sessionId}`)
      if (session.ownerUserId !== currentUser?.user_id) throw new Error(`Unknown placeholder session ${sessionId}`)
      return buildPlaySnapshot(session)
    },

    async getPlaySessionHistory(sessionId) {
      const session = sessions.get(sessionId)
      if (!session) throw new Error(`Unknown placeholder session ${sessionId}`)
      if (session.ownerUserId !== currentUser?.user_id) throw new Error(`Unknown placeholder session ${sessionId}`)
      return {
        session_id: session.sessionId,
        story_id: session.storyId,
        entries: [...session.history],
      }
    },

    async submitPlayTurn(sessionId, request) {
      const session = sessions.get(sessionId)
      if (!session) throw new Error(`Unknown placeholder session ${sessionId}`)
      if (session.ownerUserId !== currentUser?.user_id) throw new Error(`Unknown placeholder session ${sessionId}`)
      session.turnIndex += 1
      session.beatIndex = Math.min(3, session.turnIndex >= 2 ? 2 : 1 + 0)
      if (session.turnIndex >= 4) {
        session.beatIndex = 3
      }
      session.stateBars = session.stateBars.map((bar) =>
        bar.category === "axis"
          ? {
              ...bar,
              current_value: Math.min(
                bar.max_value,
                Math.max(
                  bar.min_value,
                  bar.current_value +
                    (bar.bar_id === "external_pressure" ? 1 : 0) +
                    (bar.bar_id === "public_panic" && request.input_text.toLowerCase().includes("public") ? 1 : 0),
                ),
              ),
            }
          : {
              ...bar,
              current_value: Math.min(
                bar.max_value,
                Math.max(bar.min_value, bar.current_value + (request.input_text.toLowerCase().includes("trust") ? 1 : -1)),
              ),
            },
      )
      session.feedback = {
        ledgers: {
          success: {
            proof_progress: Math.min(4, session.feedback.ledgers.success.proof_progress + 1),
            coalition_progress: Math.min(4, session.feedback.ledgers.success.coalition_progress + 1),
            order_progress: Math.min(4, session.feedback.ledgers.success.order_progress + (session.turnIndex >= 2 ? 1 : 0)),
            settlement_progress: Math.min(4, session.feedback.ledgers.success.settlement_progress + (session.turnIndex >= 3 ? 1 : 0)),
          },
          cost: {
            public_cost: Math.min(4, session.feedback.ledgers.cost.public_cost + 1),
            relationship_cost: Math.min(4, session.feedback.ledgers.cost.relationship_cost + 1),
            procedural_cost: session.feedback.ledgers.cost.procedural_cost + (request.input_text.toLowerCase().includes("audit") ? 1 : 0),
            coercion_cost: Math.min(4, session.feedback.ledgers.cost.coercion_cost + (request.input_text.toLowerCase().includes("force") ? 1 : 0)),
          },
        },
        last_turn_axis_deltas: {
          external_pressure: 1,
          public_panic: request.input_text.toLowerCase().includes("public") ? 1 : 0,
        },
        last_turn_stance_deltas: {
          npc_relationship: request.input_text.toLowerCase().includes("trust") ? 1 : -1,
        },
        last_turn_tags: ["coalition_strained", "public_record_secured"],
        last_turn_consequences: [
          "A visible relationship shifted under pressure.",
          "The public meaning of the crisis changed.",
        ],
      }
      session.narration = `You say: "${request.input_text}". The room shifts, the pressure redistributes, and everyone waits to see whether this move stabilizes the crisis or hardens its cost.`
      session.ending = nextEndingForStory(session.storyTitle, session.turnIndex)
      session.history.push({
        speaker: "player",
        text: request.input_text,
        created_at: new Date().toISOString(),
        turn_index: session.turnIndex,
      })
      session.history.push({
        speaker: "gm",
        text: session.narration,
        created_at: new Date().toISOString(),
        turn_index: session.turnIndex,
      })
      return buildPlaySnapshot(session)
    },
  }
}
