"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api } from "@/lib/api";
import type { User, UserRole } from "@/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  userId: string | null;
  role: UserRole | null;
  user: User | null;
  hydrated: boolean;
  setAuth: (data: {
    access_token: string;
    refresh_token: string;
    user_id: string;
    role: UserRole;
  }) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;
  setHydrated: () => void;
  fetchMe: () => Promise<User | null>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      userId: null,
      role: null,
      user: null,
      hydrated: false,

      setAuth: (data) =>
        set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          userId: data.user_id,
          role: data.role,
        }),

      setUser: (user) => set({ user }),

      clearAuth: () =>
        set({
          accessToken: null,
          refreshToken: null,
          userId: null,
          role: null,
          user: null,
        }),

      setHydrated: () => set({ hydrated: true }),

      fetchMe: async () => {
        const token = get().accessToken;
        if (!token) return null;
        try {
          const user = await api.me(token);
          set({ user });
          return user;
        } catch {
          get().clearAuth();
          return null;
        }
      },
    }),
    {
      name: "hiremind-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        userId: state.userId,
        role: state.role,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    },
  ),
);
