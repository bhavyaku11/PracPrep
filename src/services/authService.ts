/**
 * PracPrep Authentication Service
 *
 * Encapsulates backend communication for user registration, authentication,
 * token lifecycle, session restoration, and logout.
 */

import { apiClient, tokenManager, ApiError } from "./apiClient.ts";
import type {
  AuthResponse,
  LoginPayload,
  LogoutResponse,
  RegisterPayload,
  UserProfile,
} from "../types/api.ts";
import { notifyUserUpdate } from "./settingsStorage.ts";

const USER_SESSION_KEY = "pracprep_user";

/**
 * Persists user session summary to local storage to maintain compatibility
 * with legacy synchronous components and storage facades.
 */
function syncLocalUserSession(user: UserProfile | null): void {
  if (typeof window === "undefined") return;
  try {
    if (user) {
      window.localStorage.setItem(
        USER_SESSION_KEY,
        JSON.stringify({
          isGuest: false,
          name: user.full_name,
          email: user.email,
          university: user.university || undefined,
        })
      );
    } else {
      window.localStorage.removeItem(USER_SESSION_KEY);
    }
    notifyUserUpdate();
  } catch {
    // Safe fallback in storage-restricted environments
  }
}

export const authService = {
  /**
   * Authenticate student with email and password.
   */
  async login(payload: LoginPayload): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>("/auth/login", payload, {
      requiresAuth: false,
    });

    tokenManager.setTokens({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });

    syncLocalUserSession(response.user);
    return response;
  },

  /**
   * Register a new student account.
   */
  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const body = {
      email: payload.email,
      password: payload.password,
      full_name: payload.full_name || payload.fullName || "",
      university: payload.university,
    };

    const response = await apiClient.post<AuthResponse>("/auth/register", body, {
      requiresAuth: false,
    });

    tokenManager.setTokens({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });

    syncLocalUserSession(response.user);
    return response;
  },

  /**
   * Synchronize Clerk authentication session with the PracPrep backend.
   * Exchanges verified Clerk JWT token for PracPrep access and refresh tokens,
   * provisions user and default settings if new, and updates local session.
   */
  async syncClerkSession(payload: {
    clerkToken: string;
    email?: string;
    fullName?: string;
    university?: string;
  }): Promise<AuthResponse> {
    try {
      const response = await apiClient.post<AuthResponse>(
        "/auth/clerk-sync",
        {
          clerk_token: payload.clerkToken,
          email: payload.email,
          full_name: payload.fullName,
          university: payload.university,
        },
        {
          headers: {
            Authorization: `Bearer ${payload.clerkToken}`,
          },
          requiresAuth: false,
        }
      );

      tokenManager.setTokens({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
      });

      syncLocalUserSession(response.user);
      return response;
    } catch (err: unknown) {
      // If the backend is unreachable (offline or local Vite-only dev), gracefully
      // fall back to local-first mode with Clerk user session so the student is never blocked.
      if (err instanceof ApiError && (err.isNetworkError || err.status >= 500)) {
        console.warn("Backend /auth/clerk-sync unreachable; continuing in local-first mode with Clerk credentials.");
        const localUser: UserProfile = {
          id: `clerk_user_${Date.now()}`,
          email: payload.email || "student@university.edu",
          full_name: payload.fullName || "Student",
          university: payload.university || null,
          is_active: true,
          created_at: new Date().toISOString(),
        };
        syncLocalUserSession(localUser);
        return {
          user: localUser,
          access_token: payload.clerkToken,
          refresh_token: payload.clerkToken,
          token_type: "bearer",
          expires_in: 3600,
        };
      }
      throw err;
    }
  },

  /**
   * Update current authenticated user profile.
   */
  async updateProfile(payload: { full_name?: string; fullName?: string; university?: string }): Promise<UserProfile> {
    const body: Record<string, unknown> = {};
    const resolvedName = payload.full_name || payload.fullName;
    if (resolvedName !== undefined) {
      body.full_name = resolvedName;
    }
    if (payload.university !== undefined) {
      body.university = payload.university;
    }

    const updated = await apiClient.patch<UserProfile>("/users/me", body, {
      requiresAuth: true,
    });

    syncLocalUserSession(updated);
    return updated;
  },

  /**
   * Terminate active session locally and notify backend.
   */
  async logout(): Promise<void> {
    try {
      if (tokenManager.hasAccessToken()) {
        await apiClient.post<LogoutResponse>("/auth/logout", undefined, {
          requiresAuth: true,
        });
      }
    } catch (err) {
      // Local cleanup must proceed even if the server is unreachable
      console.warn("Backend logout request completed with non-fatal status:", err);
    } finally {
      tokenManager.clearTokens();
      syncLocalUserSession(null);
    }
  },

  /**
   * Fetch current authenticated user's profile.
   */
  async getCurrentUser(): Promise<UserProfile> {
    const user = await apiClient.get<UserProfile>("/users/me", {
      requiresAuth: true,
    });

    syncLocalUserSession(user);
    return user;
  },

  /**
   * Attempt to restore user session using stored credentials.
   * Returns UserProfile if valid, null if unauthenticated or expired.
   * Throws ApiError on unexpected network or server failures.
   */
  async restoreSession(): Promise<UserProfile | null> {
    const hasToken = tokenManager.hasAccessToken() || Boolean(tokenManager.getRefreshToken());
    if (!hasToken) {
      return null;
    }

    try {
      const user = await this.getCurrentUser();
      return user;
    } catch (err) {
      if (err instanceof ApiError && err.isAuthError) {
        tokenManager.clearTokens();
        syncLocalUserSession(null);
        return null;
      }
      // Re-throw network or server errors so the caller can distinguish them
      throw err;
    }
  },

  /**
   * Clear local authentication credentials without issuing network requests.
   */
  clearLocalSession(): void {
    tokenManager.clearTokens();
    syncLocalUserSession(null);
  },
};

export default authService;
