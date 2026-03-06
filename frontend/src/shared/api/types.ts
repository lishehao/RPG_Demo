export type RiskHint = 'low' | 'medium' | 'high';

export type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    request_id: string | null;
  };
};

export type AdminLoginRequest = {
  email: string;
  password: string;
};

export type AdminLoginResponse = {
  token: string;
  access_token: string;
  token_type: 'bearer';
};

export type StoryGenerateRequest = {
  theme: string;
  difficulty: string;
};

export type StoryGenerateResponse = {
  story_id: string;
  title: string;
  published: boolean;
};

export type StoryListItem = {
  story_id: string;
  title: string;
};

export type StoryListResponse = {
  stories: StoryListItem[];
};

export type SessionCreateRequest = {
  story_id: string;
};

export type SessionCreateResponse = {
  session_id: string;
};

export type SessionMeta = {
  session_id: string;
  story_id: string;
  created_at: string;
  state: 'active' | 'completed';
};

export type SessionAction = {
  id: string;
  label: string;
};

export type SessionHistoryTurn = {
  turn: number;
  narration: string;
  actions: SessionAction[];
};

export type SessionHistoryResponse = {
  history: SessionHistoryTurn[];
};

export type SessionStepRequest =
  | {
      move_id: string;
      free_text?: never;
    }
  | {
      move_id?: never;
      free_text: string;
    };

export type SessionStepResponse = {
  turn: number;
  narration: string;
  actions: SessionAction[];
  risk_hint: RiskHint;
};
