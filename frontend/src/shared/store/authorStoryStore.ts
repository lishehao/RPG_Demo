import { create } from 'zustand';
import type { StoryDraftResponse, StorySummary } from '@/shared/api/types';

type AuthorStoryState = {
  stories: StorySummary[];
  currentStory: StoryDraftResponse | null;
  setStories: (stories: StorySummary[]) => void;
  setCurrentStory: (story: StoryDraftResponse | null) => void;
  reset: () => void;
};

export const useAuthorStoryStore = create<AuthorStoryState>((set) => ({
  stories: [],
  currentStory: null,
  setStories: (stories) => set({ stories }),
  setCurrentStory: (currentStory) => set({ currentStory }),
  reset: () => set({ stories: [], currentStory: null }),
}));
