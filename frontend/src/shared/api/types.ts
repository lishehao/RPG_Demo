export type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    request_id: string | null;
    details?: Record<string, unknown>;
  };
};

export type AdminLoginRequest = {
  email: string;
  password: string;
};

export type AdminUser = {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
};

export type AdminLoginResponse = {
  access_token: string;
  token_type: 'bearer';
  expires_at: string;
  user: AdminUser;
};

export type StorySummary = {
  story_id: string;
  title: string;
  created_at: string;
  has_draft: boolean;
  latest_published_version: number | null;
  latest_published_at: string | null;
};

export type StoryListResponse = {
  stories: StorySummary[];
};

export type StoryDraftResponse = {
  story_id: string;
  title: string;
  created_at: string;
  draft_pack: Record<string, unknown>;
  latest_published_version: number | null;
  latest_published_at: string | null;
};

export type StoryDraftPatchChange = {
  target_type: 'story' | 'beat' | 'scene' | 'npc' | 'opening_guidance';
  field:
    | 'title'
    | 'description'
    | 'style_guard'
    | 'input_hint'
    | 'scene_seed'
    | 'red_line'
    | 'intro_text'
    | 'goal_hint'
    | 'starter_prompt_1'
    | 'starter_prompt_2'
    | 'starter_prompt_3';
  target_id?: string;
  value: string;
};

export type StoryDraftPatchRequest = {
  changes: StoryDraftPatchChange[];
};

export type StoryGenerateRequest = {
  seed_text?: string;
  prompt_text?: string;
  target_minutes?: number;
  npc_count?: number;
  style?: string;
  publish?: boolean;
};

export type StoryGenerateResponse = {
  status: 'ok';
  story_id: string;
  version: number | null;
  pack: Record<string, unknown>;
  pack_hash: string;
  generation: Record<string, unknown>;
};

export type StoryPublishResponse = {
  story_id: string;
  version: number;
  published_at: string;
};

export type OpeningGuidance = {
  intro_text: string;
  goal_hint: string;
  starter_prompts: [string, string, string] | string[];
};

export type SessionCreateRequest = {
  story_id: string;
  version: number;
};

export type SessionCreateResponse = {
  session_id: string;
  story_id: string;
  version: number;
  scene_id: string;
  state_summary: Record<string, unknown>;
  opening_guidance: OpeningGuidance;
};

export type SessionMeta = {
  session_id: string;
  scene_id: string;
  beat_progress: Record<string, unknown>;
  ended: boolean;
  state_summary: Record<string, unknown>;
  opening_guidance: OpeningGuidance;
  state?: Record<string, unknown> | null;
};

export type SessionUiMove = {
  move_id: string;
  label: string;
  risk_hint: string;
};

export type SessionUi = {
  moves: SessionUiMove[];
  input_hint: string;
};

export type SessionRecognized = {
  interpreted_intent: string;
  move_id: string;
  confidence: number;
  route_source: 'button' | 'button_fallback' | 'llm';
  llm_duration_ms?: number | null;
  llm_gateway_mode?: 'worker' | 'unknown' | null;
};

export type SessionResolution = {
  result: string;
  costs_summary: string;
  consequences_summary: string;
};

export type SessionHistoryTurn = {
  turn_index: number;
  scene_id: string;
  narration_text: string;
  recognized: SessionRecognized;
  resolution: SessionResolution;
  ui: SessionUi;
  ended: boolean;
};

export type SessionHistoryResponse = {
  session_id: string;
  history: SessionHistoryTurn[];
};

export type SessionStepRequest = {
  client_action_id: string;
  input?: {
    type?: 'button' | 'text';
    move_id?: string;
    text?: string;
  };
  dev_mode?: boolean;
};

export type SessionStepResponse = {
  session_id: string;
  version: number;
  scene_id: string;
  narration_text: string;
  recognized: SessionRecognized;
  resolution: SessionResolution;
  ui: SessionUi;
  debug?: Record<string, unknown> | null;
};
