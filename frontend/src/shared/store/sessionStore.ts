import { create } from 'zustand';
import type { SessionHistoryTurn, SessionMeta, SessionStepResponse } from '@/shared/api/types';

type SessionState = {
  sessionMeta: SessionMeta | null;
  history: SessionHistoryTurn[];
  submitting: boolean;
  scrollAnchor: string | null;
  setSessionMeta: (session: SessionMeta | null) => void;
  setHistory: (history: SessionHistoryTurn[]) => void;
  appendTurn: (turn: SessionStepResponse) => void;
  setSubmitting: (value: boolean) => void;
  setScrollAnchor: (anchor: string | null) => void;
  reset: () => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  sessionMeta: null,
  history: [],
  submitting: false,
  scrollAnchor: null,
  setSessionMeta: (sessionMeta) => set({ sessionMeta }),
  setHistory: (history) => set({ history }),
  appendTurn: (turn) =>
    set((state) => ({
      history: [
        ...state.history,
        {
          turn: turn.turn,
          narration: turn.narration,
          actions: turn.actions,
        },
      ],
    })),
  setSubmitting: (submitting) => set({ submitting }),
  setScrollAnchor: (scrollAnchor) => set({ scrollAnchor }),
  reset: () => set({ sessionMeta: null, history: [], submitting: false, scrollAnchor: null }),
}));
