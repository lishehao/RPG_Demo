import { create } from 'zustand';
import type { StorySummary } from '@/shared/api/types';

type PlayLibraryState = {
  stories: StorySummary[];
  setStories: (stories: StorySummary[]) => void;
  reset: () => void;
};

export const usePlayLibraryStore = create<PlayLibraryState>((set) => ({
  stories: [],
  setStories: (stories) => set({ stories }),
  reset: () => set({ stories: [] }),
}));
