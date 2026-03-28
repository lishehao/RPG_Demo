export type FrontendApiError = {
  error: {
    code: string
    message: string
  }
}

export type ApiRequestOptions = {
  signal?: AbortSignal
}

export type AuthUserResponse = {
  user_id: string
  display_name: string
  email: string
}

export type AuthSessionResponse = {
  authenticated: boolean
  user: AuthUserResponse | null
}

export type AuthRegisterRequest = {
  display_name: string
  email: string
  password: string
}

export type AuthLoginRequest = {
  email: string
  password: string
}

export type CurrentActorResponse = {
  user_id: string
  display_name: string
  email: string
  is_default: boolean
}

export type StoryLanguage = "en" | "zh"

export type FocusedBrief = {
  language: StoryLanguage
  story_kernel: string
  setting_signal: string
  core_conflict: string
  tone_signal: string
  hard_constraints: string[]
  forbidden_tones: string[]
}

export type AuthorPreviewFlashcard = {
  card_id: string
  kind: "stable" | "draft"
  label: string
  value: string
}

export type AuthorLoadingCard = {
  card_id:
    | "theme"
    | "tone"
    | "structure"
    | "story_premise"
    | "story_stakes"
    | "cast_count"
    | "cast_anchor"
    | "beat_count"
    | "working_title"
    | "opening_beat"
    | "final_beat"
    | "generation_status"
    | "token_budget"
  emphasis: "stable" | "draft" | "live"
  label: string
  value: string
}

export type AuthorPreviewTheme = {
  primary_theme: string
  modifiers: string[]
  router_reason: string
}

export type AuthorPreviewStrategies = {
  story_frame_strategy: string
  cast_strategy: string
  beat_plan_strategy: string
}

export type AuthorPreviewStructure = {
  cast_topology: string
  expected_npc_count: number
  expected_beat_count: number
}

export type AuthorPreviewStory = {
  title: string
  premise: string
  tone: string
  stakes: string
}

export type AuthorPreviewCastSlotSummary = {
  slot_label: string
  public_role: string
  npc_id?: string | null
  name?: string | null
  roster_character_id?: string | null
  roster_public_summary?: string | null
  portrait_url?: string | null
  portrait_variants?: PortraitVariants | null
  template_version?: string | null
}

export type AuthorPreviewBeatSummary = {
  title: string
  goal: string
  milestone_kind: string
}

export type AuthorPreviewRequest = {
  prompt_seed: string
  language?: StoryLanguage
  random_seed?: number | null
}

export type AuthorStorySparkRequest = {
  language?: StoryLanguage
}

export type AuthorStorySparkResponse = {
  prompt_seed: string
  language: StoryLanguage
}

export type AuthorPreviewResponse = {
  preview_id: string
  prompt_seed: string
  language: StoryLanguage
  focused_brief: FocusedBrief
  theme: AuthorPreviewTheme
  strategies: AuthorPreviewStrategies
  structure: AuthorPreviewStructure
  story: AuthorPreviewStory
  cast_slots: AuthorPreviewCastSlotSummary[]
  beats: AuthorPreviewBeatSummary[]
  flashcards: AuthorPreviewFlashcard[]
  stage: string
}

export type AuthorJobProgress = {
  stage: string
  stage_index: number
  stage_total: number
}

export type AuthorJobProgressSnapshot = {
  stage: string
  stage_label: string
  stage_message?: string | null
  stage_index: number
  stage_total: number
  completion_ratio: number
  primary_theme: string
  cast_topology: string
  expected_npc_count: number
  expected_beat_count: number
  preview_title: string
  preview_premise: string
  flashcards: AuthorPreviewFlashcard[]
  loading_cards: AuthorLoadingCard[]
  cast_pool: AuthorLoadingCastPoolEntry[]
  running_node?: string | null
  running_substage?: string | null
  running_slot_index?: number | null
  running_slot_total?: number | null
  running_slot_label?: string | null
  running_capability?: string | null
  running_elapsed_ms?: number | null
}

export type AuthorLoadingCastPoolEntry = {
  npc_id: string
  name: string
  role: string
  roster_character_id?: string | null
  roster_public_summary?: string | null
  portrait_url?: string | null
  portrait_variants?: PortraitVariants | null
  template_version?: string | null
}

export type AuthorCacheMetrics = {
  session_cache_enabled: boolean
  cache_path_used: boolean
  total_call_count: number
  previous_response_call_count: number
  total_input_characters: number
  estimated_input_tokens_from_chars: number
  provider_usage: Record<string, number>
  input_tokens?: number | null
  output_tokens?: number | null
  total_tokens?: number | null
  reasoning_tokens?: number | null
  cached_input_tokens?: number | null
  cache_hit_tokens?: number | null
  cache_write_tokens?: number | null
  cache_creation_input_tokens?: number | null
  cache_type?: string | null
  billing_type?: string | null
  cache_metrics_source: string
}

export type AuthorJobCreateRequest = {
  prompt_seed: string
  language?: StoryLanguage
  random_seed?: number | null
  preview_id?: string | null
}

export type AuthorJobStatus = "queued" | "running" | "completed" | "failed"

export type AuthorJobStatusResponse = {
  job_id: string
  status: AuthorJobStatus
  prompt_seed: string
  preview: AuthorPreviewResponse
  progress: AuthorJobProgress
  progress_snapshot?: AuthorJobProgressSnapshot | null
  cache_metrics?: AuthorCacheMetrics | null
  error?: { code: string; message: string } | null
}

export type AuthorStorySummary = {
  language: StoryLanguage
  title: string
  one_liner: string
  premise: string
  tone: string
  theme: string
  npc_count: number
  beat_count: number
}

export type AuthorJobResultResponse = {
  job_id: string
  status: AuthorJobStatus
  summary?: AuthorStorySummary | null
  publishable: boolean
  progress_snapshot?: AuthorJobProgressSnapshot | null
  cache_metrics?: AuthorCacheMetrics | null
}

export type AuthorEditorNpcRef = {
  npc_id: string
  name: string
}

export type AuthorEditorStoryFrameView = {
  title: string
  premise: string
  tone: string
  stakes: string
  style_guard: string
  world_rules: string[]
  truths: Array<{ truth_id: string; text: string; importance: "core" | "optional" }>
  state_axes: Array<{
    axis_id: string
    label: string
    kind: "pressure" | "resource" | "relationship" | "exposure" | "time"
    min_value: number
    max_value: number
    starting_value: number
  }>
  flags: Array<{ flag_id: string; label: string; starting_value: boolean }>
}

export type AuthorEditorCastEntry = {
  npc_id: string
  name: string
  role: string
  agenda: string
  red_line: string
  pressure_signature: string
  roster_character_id?: string | null
  roster_public_summary?: string | null
  portrait_url?: string | null
  portrait_variants?: PortraitVariants | null
  template_version?: string | null
}

export type AuthorEditorBeatView = {
  beat_id: string
  title: string
  goal: string
  milestone_kind: string
  pressure_axis_id?: string | null
  route_pivot_tag?: string | null
  progress_required: number
  focus_npcs: AuthorEditorNpcRef[]
  conflict_npcs: AuthorEditorNpcRef[]
  affordance_tags: string[]
  blocked_affordances: string[]
}

export type AuthorEditorRulePackView = {
  route_unlock_rules: Array<Record<string, unknown>>
  ending_rules: Array<Record<string, unknown>>
  affordance_effect_profiles: Array<Record<string, unknown>>
}

export type AuthorEditorPlayProfileView = {
  protagonist: {
    npc_id: string
    name: string
    role: string
    agenda: string
    red_line: string
    pressure_signature: string
  }
  runtime_profile: string
  runtime_profile_label: string
  closeout_profile: string
  closeout_profile_label: string
  max_turns: number
}

export type AuthorCopilotSuggestion = {
  suggestion_id: string
  label: string
  instruction: string
  rationale: string
}

export type AuthorCopilotWorkspaceView = {
  mode: "primary"
  headline: string
  supporting_text: string
  publish_readiness_text: string
  suggested_instructions: AuthorCopilotSuggestion[]
  active_session_id?: string | null
  undo_available?: boolean
  undo_proposal_id?: string | null
  undo_request_summary?: string | null
}

export type AuthorCopilotLockedBoundaries = {
  language: StoryLanguage
  core_story_kernel: string
  core_conflict: string
  runtime_profile: string
  closeout_profile: string
  cast_topology: string
  beat_count: number
  max_turns: number
}

export type AuthorCopilotMessage = {
  message_id: string
  role: "user" | "assistant"
  content: string
  created_at: string
}

export type AuthorCopilotRewriteBrief = {
  summary: string
  latest_instruction: string
  user_goals: string[]
  preserved_invariants: string[]
  open_questions: string[]
}

export type AuthorCopilotSessionCreateRequest = {
  hidden?: boolean
}

export type AuthorCopilotSessionMessageRequest = {
  content: string
}

export type AuthorCopilotSessionResponse = {
  session_id: string
  job_id: string
  status: "active" | "proposal_ready" | "applied" | "stale" | "closed"
  hidden: boolean
  base_revision: string
  locked_boundaries: AuthorCopilotLockedBoundaries
  rewrite_brief: AuthorCopilotRewriteBrief
  messages: AuthorCopilotMessage[]
  last_proposal_id?: string | null
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export type AuthorEditorStateResponse = {
  job_id: string
  status: "completed"
  language: StoryLanguage
  revision: string
  publishable: boolean
  focused_brief: FocusedBrief
  summary: AuthorStorySummary
  story_frame_view: AuthorEditorStoryFrameView
  cast_view: AuthorEditorCastEntry[]
  beat_view: AuthorEditorBeatView[]
  rule_pack_view: AuthorEditorRulePackView
  play_profile_view: AuthorEditorPlayProfileView
  copilot_view: AuthorCopilotWorkspaceView
}

export type AuthorCopilotProposalRequest = {
  instruction: string
  retry_from_proposal_id?: string | null
}

export type AuthorCopilotStoryFrameRewrite = {
  title?: string | null
  premise?: string | null
  tone?: string | null
  stakes?: string | null
  style_guard?: string | null
}

export type AuthorCopilotCastRewrite = {
  npc_id: string
  role?: string | null
  agenda?: string | null
  red_line?: string | null
  pressure_signature?: string | null
}

export type AuthorCopilotBeatRewrite = {
  beat_id: string
  title?: string | null
  goal?: string | null
  milestone_kind?: string | null
  pressure_axis_id?: string | null
  route_pivot_tag?: string | null
  progress_required?: number | null
}

export type AuthorCopilotRulePackRewrite = {
  toward?: "mixed" | "pyrrhic" | "collapse" | null
  intensity?: "light" | "medium" | "strong" | null
}

export type AuthorCopilotRewritePlan = {
  story_frame?: AuthorCopilotStoryFrameRewrite | null
  cast: AuthorCopilotCastRewrite[]
  beats: AuthorCopilotBeatRewrite[]
  rule_pack?: AuthorCopilotRulePackRewrite | null
}

export type PortraitVariants = {
  negative?: string | null
  neutral?: string | null
  positive?: string | null
}

export type AuthorCopilotOperation = {
  op: "update_story_frame" | "update_cast_member" | "update_beat" | "adjust_ending_tilt"
  target: string
  changes: Record<string, string | number>
  toward?: "mixed" | "pyrrhic" | "collapse" | null
  intensity?: "light" | "medium" | "strong" | null
}

export type AuthorCopilotProposalResponse = {
  proposal_id: string
  proposal_group_id: string
  session_id?: string | null
  job_id: string
  status: "draft" | "applied" | "superseded" | "undone"
  source: "heuristic" | "llm"
  mode: "bundle_rewrite"
  instruction: string
  base_revision: string
  variant_index: number
  variant_label: string
  supersedes_proposal_id?: string | null
  created_at: string
  updated_at: string
  applied_at?: string | null
  request_summary: string
  rewrite_scope: string
  rewrite_brief: string
  affected_sections: Array<"story_frame" | "cast" | "beats" | "rule_pack">
  stability_guards: string[]
  rewrite_plan: AuthorCopilotRewritePlan
  patch_targets: Array<"story_frame" | "cast" | "beats" | "rule_pack">
  operations: AuthorCopilotOperation[]
  impact_summary: string[]
  warnings: string[]
}

export type AuthorCopilotPreviewResponse = {
  proposal: AuthorCopilotProposalResponse
  editor_state: AuthorEditorStateResponse
}

export type AuthorCopilotApplyResponse = {
  proposal: AuthorCopilotProposalResponse
  editor_state: AuthorEditorStateResponse
}

export type AuthorCopilotUndoResponse = {
  proposal: AuthorCopilotProposalResponse
  editor_state: AuthorEditorStateResponse
}

export type PublishedStoryCard = {
  story_id: string
  language: StoryLanguage
  title: string
  one_liner: string
  premise: string
  theme: string
  tone: string
  npc_count: number
  beat_count: number
  topology: string
  visibility: "private" | "public"
  viewer_can_manage: boolean
  published_at: string
}

export type PublishedStoryListSort = "published_at_desc" | "relevance"
export type PublishedStoryListView = "accessible" | "mine" | "public"

export type ListStoriesParams = {
  q?: string | null
  theme?: string | null
  language?: StoryLanguage | null
  view?: PublishedStoryListView | null
  limit?: number
  cursor?: string | null
  sort?: PublishedStoryListSort | null
}

export type PublishedStoryThemeFacet = {
  theme: string
  count: number
}

export type PublishedStoryListMeta = {
  query?: string | null
  theme?: string | null
  language?: StoryLanguage | null
  view: PublishedStoryListView
  sort: PublishedStoryListSort
  limit: number
  next_cursor?: string | null
  has_more: boolean
  total: number
}

export type PublishedStoryListFacets = {
  themes: PublishedStoryThemeFacet[]
}

export type PublishedStoryListResponse = {
  stories: PublishedStoryCard[]
  meta?: PublishedStoryListMeta | null
  facets?: PublishedStoryListFacets | null
}

export type PublishedStoryPresentation = {
  dossier_ref: string
  status: "open_for_play"
  status_label: string
  classification_label: string
  engine_label: string
  visibility: "private" | "public"
  viewer_can_manage: boolean
}

export type StoryVisibility = "private" | "public"

export type UpdateStoryVisibilityRequest = {
  visibility: StoryVisibility
}

export type DeleteStoryResponse = {
  story_id: string
  deleted: true
}

export type PublishedStoryPlayOverview = {
  protagonist: PlayProtagonist
  opening_narration: string
  runtime_profile: string
  runtime_profile_label: string
  max_turns: number
}

export type PublishedStoryBeatOutline = {
  beat_id: string
  title: string
  goal: string
  milestone_kind: string
}

export type PublishedStoryStructure = {
  topology_label: string
  beat_outline: PublishedStoryBeatOutline[]
}

export type PublishedStoryCastEntry = {
  npc_id: string
  name: string
  role: string
  agenda: string
  red_line: string
  pressure_signature: string
  roster_character_id?: string | null
  roster_public_summary?: string | null
  portrait_url?: string | null
  portrait_variants?: PortraitVariants | null
}

export type PublishedStoryCastManifest = {
  entries: PublishedStoryCastEntry[]
}

export type PublishedStoryDetailResponse = {
  story: PublishedStoryCard
  presentation?: PublishedStoryPresentation | null
  structure: PublishedStoryStructure
  cast_manifest: PublishedStoryCastManifest
  play_overview?: PublishedStoryPlayOverview | null
}

export type PlaySessionCreateRequest = {
  story_id: string
}

export type PlayTurnRequest = {
  input_text: string
  selected_suggestion_id?: string | null
}

export type PlayStateBar = {
  bar_id: string
  label: string
  category: "axis" | "stance"
  current_value: number
  min_value: number
  max_value: number
}

export type PlaySuggestedAction = {
  suggestion_id: string
  label: string
  prompt: string
}

export type PlayEnding = {
  ending_id: string
  label: string
  summary: string
}

export type PlayProtagonist = {
  title: string
  mandate: string
  identity_summary: string
}

export type PlaySuccessLedger = {
  proof_progress: number
  coalition_progress: number
  order_progress: number
  settlement_progress: number
}

export type PlayCostLedger = {
  public_cost: number
  relationship_cost: number
  procedural_cost: number
  coercion_cost: number
}

export type PlayFeedback = {
  ledgers: {
    success: PlaySuccessLedger
    cost: PlayCostLedger
  }
  last_turn_axis_deltas: Record<string, number>
  last_turn_stance_deltas: Record<string, number>
  last_turn_tags: string[]
  last_turn_consequences: string[]
}

export type PlaySessionHistoryEntry = {
  speaker: "gm" | "player"
  text: string
  created_at: string
  turn_index: number
}

export type PlaySessionHistoryResponse = {
  session_id: string
  story_id: string
  language: StoryLanguage
  entries: PlaySessionHistoryEntry[]
}

export type PlaySessionProgress = {
  completed_beats: number
  total_beats: number
  current_beat_progress: number
  current_beat_goal: number
  turn_index: number
  max_turns: number
  completion_ratio: number
  display_percent: number
}

export type PlaySupportSurface = {
  enabled: boolean
  disabled_reason?: string | null
}

export type PlaySupportSurfaces = {
  inventory: PlaySupportSurface
  map: PlaySupportSurface
}

export type PortraitExpression = "negative" | "neutral" | "positive"

export type PlayNpcVisualState = {
  npc_id: string
  name: string
  stance_value: number
  current_expression: PortraitExpression
  current_portrait_url?: string | null
  portrait_variants?: PortraitVariants | null
}

export type PlayNpcEpilogueReaction = {
  npc_id: string
  name: string
  stance_value: number
  current_expression: PortraitExpression
  current_portrait_url?: string | null
  portrait_variants?: PortraitVariants | null
  closing_line: string
}

export type PlaySessionSnapshot = {
  session_id: string
  story_id: string
  language: StoryLanguage
  status: "active" | "completed" | "expired"
  turn_index: number
  beat_index: number
  beat_title: string
  story_title: string
  narration: string
  protagonist?: PlayProtagonist | null
  feedback?: PlayFeedback | null
  progress?: PlaySessionProgress | null
  support_surfaces?: PlaySupportSurfaces | null
  state_bars: PlayStateBar[]
  npc_visuals: PlayNpcVisualState[]
  epilogue_reactions?: PlayNpcEpilogueReaction[] | null
  suggested_actions: PlaySuggestedAction[]
  ending?: PlayEnding | null
}

export type AuthorJobEventName =
  | "job_created"
  | "job_started"
  | "stage_changed"
  | "job_completed"
  | "job_failed"

export type AuthorJobEvent = {
  id: number
  event: AuthorJobEventName
  data: Record<string, unknown>
}
