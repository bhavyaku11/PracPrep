/**
 * PracPrep Authentication Context Definitions & Hook
 *
 * Defines the AuthContext and the useAuth hook with a safe default value
 * allowing components to render gracefully in isolated test environments.
 */

import { createContext, useContext } from "react";
import type {
  AuthResponse,
  LoginPayload,
  RegisterPayload,
  UserProfile,
} from "../types/api.ts";
import { authService } from "../services/authService.ts";
import { notifyUserUpdate } from "../services/settingsStorage.ts";

export type AuthStatus = "initializing" | "authenticated" | "guest" | "unauthenticated";

export interface AuthContextValue {
  user: UserProfile | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  isLoading: boolean;
  isGuest: boolean;
  error: string | null;
  login: (payload: LoginPayload) => Promise<AuthResponse>;
  register: (payload: RegisterPayload) => Promise<AuthResponse>;
  syncClerkSession: (payload: {
    clerkToken: string;
    email?: string;
    fullName?: string;
    university?: string;
  }) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  enterGuestMode: () => void;
  clearError: () => void;
}

export const defaultAuthContext: AuthContextValue = {
  user: null,
  status: "unauthenticated",
  isAuthenticated: false,
  isLoading: false,
  isGuest: false,
  error: null,
  login: async (payload) => authService.login(payload),
  register: async (payload) => authService.register(payload),
  syncClerkSession: async (payload) => authService.syncClerkSession(payload),
  logout: async () => authService.logout(),
  enterGuestMode: () => {
    authService.clearLocalSession();
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem("pracprep_user", JSON.stringify({ isGuest: true }));
        notifyUserUpdate();
      } catch {
        // Safe no-op
      }
    }
  },
  clearError: () => {},
};

export const AuthContext = createContext<AuthContextValue>(defaultAuthContext);

/**
 * Access the global authentication state and lifecycle actions.
 */
export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
