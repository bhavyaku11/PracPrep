/**
 * PracPrep API Infrastructure Types
 *
 * Defines TypeScript contracts for HTTP requests, authentication tokens,
 * user profile responses, and standardized error schemas.
 */

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  university?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse extends TokenResponse {
  user: UserProfile;
}

export interface TokenRefreshRequest {
  refresh_token: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
  fullName?: string;
  university?: string;
}

export interface ProfileUpdatePayload {
  full_name?: string;
  fullName?: string;
  university?: string;
}

export interface LogoutResponse {
  message: string;
}

export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorEnvelope {
  code: string;
  message: string;
  status: number;
  path?: string;
  details?: unknown;
}

export interface ApiErrorDetail {
  detail?: string | ValidationErrorItem[];
  message?: string;
  error?: {
    code?: string;
    message?: string;
    status?: number;
    path?: string;
    details?: unknown;
  };
  [key: string]: unknown;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  params?: Record<string, string | number | boolean | null | undefined>;
  requiresAuth?: boolean;
  _isRetry?: boolean;
}

export interface ApiClientConfig {
  baseUrl?: string;
  apiPrefix?: string;
  tokenManager?: TokenManagerInterface;
  fetchFn?: typeof fetch;
}

export interface TokenManagerInterface {
  getAccessToken(): string | null;
  setAccessToken(token: string | null): void;
  getRefreshToken(): string | null;
  setRefreshToken(token: string | null): void;
  setTokens(tokens: { accessToken: string; refreshToken?: string | null }): void;
  clearTokens(): void;
  hasAccessToken(): boolean;
  onAuthExpired(listener: () => void): () => void;
  notifyAuthExpired(): void;
}
