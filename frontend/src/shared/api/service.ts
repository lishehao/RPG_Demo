import { apiClient } from '@/shared/api/client';
import type {
  AdminLoginRequest,
  AdminLoginResponse,
  SessionCreateRequest,
  SessionCreateResponse,
  SessionHistoryResponse,
  SessionMeta,
  SessionStepRequest,
  SessionStepResponse,
  StoryDraftPatchRequest,
  StoryDraftResponse,
  StoryGenerateRequest,
  StoryGenerateResponse,
  StoryListResponse,
  StoryPublishResponse,
} from '@/shared/api/types';

export const apiService = {
  login: (payload: AdminLoginRequest) =>
    apiClient.post<AdminLoginResponse>('/admin/auth/login', payload, { skipAuth: true }),
  listStories: () => apiClient.get<StoryListResponse>('/stories'),
  getStoryDraft: (storyId: string) => apiClient.get<StoryDraftResponse>(`/stories/${storyId}/draft`),
  patchStoryDraft: (storyId: string, payload: StoryDraftPatchRequest) => apiClient.patch<StoryDraftResponse>(`/stories/${storyId}/draft`, payload),
  generateStory: (payload: StoryGenerateRequest) => apiClient.post<StoryGenerateResponse>('/stories/generate', payload),
  publishStory: (storyId: string) => apiClient.post<StoryPublishResponse>(`/stories/${storyId}/publish`, {}),
  createSession: (payload: SessionCreateRequest) => apiClient.post<SessionCreateResponse>('/sessions', payload),
  getSession: (sessionId: string, devMode = false) =>
    apiClient.get<SessionMeta>(`/sessions/${sessionId}${devMode ? '?dev_mode=true' : ''}`),
  getSessionHistory: (sessionId: string) => apiClient.get<SessionHistoryResponse>(`/sessions/${sessionId}/history`),
  stepSession: (sessionId: string, payload: SessionStepRequest) =>
    apiClient.post<SessionStepResponse>(`/sessions/${sessionId}/step`, payload),
};
