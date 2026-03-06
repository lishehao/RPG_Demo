import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type AuthState = {
  token: string | null;
  hydrated: boolean;
  setToken: (token: string) => void;
  setHydrated: (hydrated: boolean) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      hydrated: false,
      setToken: (token) => set({ token }),
      setHydrated: (hydrated) => set({ hydrated }),
      logout: () => set({ token: null }),
    }),
    {
      name: 'ember-command-auth',
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    },
  ),
);
