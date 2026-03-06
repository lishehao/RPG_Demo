import { create } from 'zustand';
import type { SessionHistoryResponse, SessionHistoryTurn, SessionMeta } from '@/shared/api/types';

type SessionState = {
  sessionMeta: SessionMeta | null;
  history: SessionHistoryTurn[];
  submitting: boolean;
  setSessionMeta: (session: SessionMeta | null) => void;
  setHistory: (history: SessionHistoryTurn[]) => void;
  setHistoryResponse: (response: SessionHistoryResponse) => void;
  setSubmitting: (value: boolean) => void;
  reset: () => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  sessionMeta: null,
  history: [],
  submitting: false,
  setSessionMeta: (sessionMeta) => set({ sessionMeta }),
  setHistory: (history) => set({ history }),
  setHistoryResponse: (response) => set({ history: response.history }),
  setSubmitting: (submitting) => set({ submitting }),
  reset: () => set({ sessionMeta: null, history: [], submitting: false }),
}));
