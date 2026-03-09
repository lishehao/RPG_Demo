import { create } from 'zustand';
import type { AuthorStoryGetResponse, AuthorStoryListItem } from '@/shared/api/types';

type AuthorStoryState = {
  stories: AuthorStoryListItem[];
  currentStory: AuthorStoryGetResponse | null;
  setStories: (stories: AuthorStoryListItem[]) => void;
  setCurrentStory: (story: AuthorStoryGetResponse | null) => void;
  reset: () => void;
};

export const useAuthorStoryStore = create<AuthorStoryState>((set) => ({
  stories: [],
  currentStory: null,
  setStories: (stories) => set({ stories }),
  setCurrentStory: (currentStory) => set({ currentStory }),
  reset: () => set({ stories: [], currentStory: null }),
}));
