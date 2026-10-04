/**
 * PracPrep React Authentication Provider Component
 *
 * Implements session restoration, token expiration listeners,
 * and state transitions for authenticated, guest, and unauthenticated sessions.
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  AuthResponse,
  LoginPayload,
  RegisterPayload,
  UserProfile,
} from "../types/api.ts";
import { authService } from "../services/authService.ts";
import { tokenManager, ApiError } from "../lib/apiClient.ts";
import { notifyUserUpdate } from "../services/settingsStorage.ts";
import {
  AuthContext,
  type AuthContextValue,
  type AuthStatus,
} from "./authContextDef.ts";

export type { AuthContextValue, AuthStatus };

export interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [status, setStatus] = useState<AuthStatus>("initializing");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasInitializedRef = useRef(false);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Enter guest mode explicitly, preserving existing guest storage keys.
   */
  const enterGuestMode = useCallback(() => {
    authService.clearLocalSession();
    setUser(null);
    setStatus("guest");
    setError(null);

    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem("pracprep_user", JSON.stringify({ isGuest: true }));
        notifyUserUpdate();
      } catch {
        // Safe no-op
      }
    }
  }, []);

  /**
   * Authenticate student and update context.
   */
  const login = useCallback(async (payload: LoginPayload): Promise<AuthResponse> => {
    setError(null);
    try {
      const response = await authService.login(payload);
      setUser(response.user);
      setStatus("authenticated");
      return response;
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to sign in. Please try again.";
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Register new student and transition directly to authenticated state.
   */
  const register = useCallback(async (payload: RegisterPayload): Promise<AuthResponse> => {
    setError(null);
    try {
      const response = await authService.register(payload);
      setUser(response.user);
      setStatus("authenticated");
      return response;
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to create account. Please try again.";
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Synchronize Clerk authentication session and transition directly to authenticated state.
   */
  const syncClerkSession = useCallback(
    async (payload: {
      clerkToken: string;
      email?: string;
      fullName?: string;
      university?: string;
    }): Promise<AuthResponse> => {
      setError(null);
      try {
        const response = await authService.syncClerkSession(payload);
        setUser(response.user);
        setStatus("authenticated");
        return response;
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : "Failed to sync Clerk session. Please try again.";
        setError(message);
        throw err;
      }
    },
    []
  );

  /**
   * Log out active student and reset context.
   */
  const logout = useCallback(async (): Promise<void> => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setStatus("unauthenticated");
      setError(null);
    }
  }, []);

  /**
   * Listen for token manager session-expiration events.
   */
  useEffect(() => {
    const unsubscribe = tokenManager.onAuthExpired(() => {
      setUser(null);
      setStatus("unauthenticated");
      setError("Your session has expired. Please sign in again.");
    });
    return unsubscribe;
  }, []);

  /**
   * Restore session on initial application load.
   */
  useEffect(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;

    async function initializeSession() {
      // Check if user is navigating directly to /guest or stored session is guest
      if (typeof window !== "undefined") {
        const isGuestRoute = window.location.pathname === "/guest";
        let isStoredGuest = false;
        try {
          const stored = window.localStorage.getItem("pracprep_user");
          if (stored) {
            const parsed = JSON.parse(stored);
            isStoredGuest = Boolean(parsed?.isGuest);
          }
        } catch {
          // Safe no-op
        }

        const hasTokens = tokenManager.hasAccessToken() || Boolean(tokenManager.getRefreshToken());

        if (isGuestRoute || (isStoredGuest && !hasTokens)) {
          setStatus("guest");
          setUser(null);
          return;
        }
      }

      try {
        const restoredUser = await authService.restoreSession();
        if (restoredUser) {
          setUser(restoredUser);
          setStatus("authenticated");
        } else {
          setUser(null);
          setStatus("unauthenticated");
        }
      } catch (err) {
        setUser(null);
        setStatus("unauthenticated");
        if (err instanceof ApiError && err.isNetworkError) {
          console.warn("Unable to reach authentication server during startup. Session unverified.");
        }
      }
    }

    void initializeSession();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isAuthenticated: status === "authenticated",
      isLoading: status === "initializing",
      isGuest: status === "guest",
      error,
      login,
      register,
      syncClerkSession,
      logout,
      enterGuestMode,
      clearError,
    }),
    [user, status, error, login, register, syncClerkSession, logout, enterGuestMode, clearError]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthProvider;
