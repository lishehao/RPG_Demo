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
  StoryGenerateRequest,
  StoryGenerateResponse,
  StoryListResponse,
} from '@/shared/api/types';

export const apiService = {
  login: (payload: AdminLoginRequest) =>
    apiClient.post<AdminLoginResponse>('/admin/auth/login', payload, { skipAuth: true }),
  generateStory: (payload: StoryGenerateRequest) =>
    apiClient.post<StoryGenerateResponse>('/stories/generate', payload),
  listStories: () => apiClient.get<StoryListResponse>('/stories'),
  createSession: (payload: SessionCreateRequest) => apiClient.post<SessionCreateResponse>('/sessions', payload),
  getSession: (sessionId: string) => apiClient.get<SessionMeta>(`/sessions/${sessionId}`),
  getSessionHistory: (sessionId: string) => apiClient.get<SessionHistoryResponse>(`/sessions/${sessionId}/history`),
  stepSession: (sessionId: string, payload: SessionStepRequest) =>
    apiClient.post<SessionStepResponse>(`/sessions/${sessionId}/step`, payload),
};
