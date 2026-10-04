/**
 * PracPrep Centralized API Client & Token Interceptors
 *
 * Implements a typed, resilient HTTP client connecting the React frontend
 * to the FastAPI REST backend (/api/v1).
 *
 * Capabilities:
 * - Configurable base URL with automatic slash normalization
 * - Automatic Authorization header injection for authenticated requests
 * - Concurrency-safe 401 token refresh interceptor with single-flight mutex
 * - Recursion-safe retry mechanism (exactly one retry per request)
 * - Safe handling of multipart FormData (boundary auto-generation)
 * - Standardized, typed error parsing preserving backend validation details
 * - Decoupled TokenManager with subscriber notifications for session expiration
 */

import type {
  ApiClientConfig,
  ApiErrorDetail,
  RequestOptions,
  TokenManagerInterface,
  TokenResponse,
  ValidationErrorItem,
} from "../types/api.ts";

export * from "../types/api.ts";

const ACCESS_TOKEN_KEY = "pracprep_access_token";
const REFRESH_TOKEN_KEY = "pracprep_refresh_token";

/**
 * In-memory storage fallback for non-browser or storage-restricted environments.
 */
class MemoryStorage {
  private store = new Map<string, string>();

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }
}

/**
 * Resolves the active storage mechanism safely.
 */
function resolveStorage(): {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
} {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const testKey = "__pp_storage_test__";
      window.localStorage.setItem(testKey, testKey);
      window.localStorage.removeItem(testKey);
      return window.localStorage;
    }
    if (typeof globalThis !== "undefined" && globalThis.localStorage) {
      return globalThis.localStorage;
    }
  } catch {
    // Falls back to in-memory store in privacy mode or Node.js environment
  }
  return new MemoryStorage();
}

/**
 * Manages JWT access and refresh tokens with expiration event subscriptions.
 */
export class TokenManager implements TokenManagerInterface {
  private storage: {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
    removeItem(key: string): void;
  };
  private expiredListeners = new Set<() => void>();

  constructor(customStorage?: {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
    removeItem(key: string): void;
  }) {
    this.storage = customStorage ?? resolveStorage();
  }

  getAccessToken(): string | null {
    try {
      return this.storage.getItem(ACCESS_TOKEN_KEY);
    } catch {
      return null;
    }
  }

  setAccessToken(token: string | null): void {
    try {
      if (token) {
        this.storage.setItem(ACCESS_TOKEN_KEY, token);
      } else {
        this.storage.removeItem(ACCESS_TOKEN_KEY);
      }
    } catch {
      // Safe no-op on quota or privacy errors
    }
  }

  getRefreshToken(): string | null {
    try {
      return this.storage.getItem(REFRESH_TOKEN_KEY);
    } catch {
      return null;
    }
  }

  setRefreshToken(token: string | null): void {
    try {
      if (token) {
        this.storage.setItem(REFRESH_TOKEN_KEY, token);
      } else {
        this.storage.removeItem(REFRESH_TOKEN_KEY);
      }
    } catch {
      // Safe no-op
    }
  }

  setTokens(tokens: { accessToken: string; refreshToken?: string | null }): void {
    this.setAccessToken(tokens.accessToken);
    if (tokens.refreshToken !== undefined) {
      this.setRefreshToken(tokens.refreshToken);
    }
  }

  clearTokens(): void {
    try {
      this.storage.removeItem(ACCESS_TOKEN_KEY);
      this.storage.removeItem(REFRESH_TOKEN_KEY);
    } catch {
      // Safe no-op
    }
  }

  hasAccessToken(): boolean {
    return Boolean(this.getAccessToken());
  }

  onAuthExpired(listener: () => void): () => void {
    this.expiredListeners.add(listener);
    return () => {
      this.expiredListeners.delete(listener);
    };
  }

  notifyAuthExpired(): void {
    for (const listener of this.expiredListeners) {
      try {
        listener();
      } catch (err) {
        console.error("Error executing auth expired listener:", err);
      }
    }
  }
}

export const tokenManager = new TokenManager();

/**
 * Standardized API Error abstraction preserving backend status codes and details.
 */
export class ApiError extends Error {
  public readonly status: number;
  public readonly statusText: string;
  public readonly code?: string;
  public readonly detail?: unknown;
  public readonly validationErrors?: ValidationErrorItem[];
  public readonly isAuthError: boolean;
  public readonly isNetworkError: boolean;
  public readonly responseBody?: unknown;

  constructor(options: {
    message: string;
    status: number;
    statusText?: string;
    code?: string;
    detail?: unknown;
    validationErrors?: ValidationErrorItem[];
    isAuthError?: boolean;
    isNetworkError?: boolean;
    responseBody?: unknown;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.statusText = options.statusText ?? "";
    this.code = options.code;
    this.detail = options.detail;
    this.validationErrors = options.validationErrors;
    this.isNetworkError = options.isNetworkError ?? options.status === 0;
    this.isAuthError =
      options.isAuthError ??
      (options.status === 401 ||
        options.status === 403 ||
        options.code === "AUTH_EXPIRED" ||
        options.code === "UNAUTHORIZED");
    this.responseBody = options.responseBody;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

/**
 * Resolves the default API base URL from Vite or Node environments.
 */
function resolveDefaultBaseUrl(): string {
  if (typeof import.meta !== "undefined" && typeof import.meta.env?.VITE_API_BASE_URL === "string") {
    return import.meta.env.VITE_API_BASE_URL;
  }
  const proc = (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process;
  if (typeof proc?.env?.VITE_API_BASE_URL === "string") {
    return proc.env.VITE_API_BASE_URL;
  }
  return "http://localhost:8000";
}

/**
 * Centralized HTTP Client with automatic auth injection, token refresh, and error normalization.
 */
export class ApiClient {
  private baseUrl: string;
  private apiPrefix: string;
  private tokenManager: TokenManagerInterface;
  private fetchFn: typeof fetch;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(config?: ApiClientConfig) {
    this.baseUrl = (config?.baseUrl ?? resolveDefaultBaseUrl()).replace(/\/+$/, "");
    this.apiPrefix = config?.apiPrefix ?? "/api/v1";
    this.tokenManager = config?.tokenManager ?? tokenManager;
    this.fetchFn = config?.fetchFn ?? ((...args) => globalThis.fetch(...args));
  }

  /**
   * Updates base URL dynamically.
   */
  setBaseUrl(url: string): void {
    this.baseUrl = url.replace(/\/+$/, "");
  }

  /**
   * Retrieves currently configured base URL.
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Retrieves active token manager.
   */
  getTokenManager(): TokenManagerInterface {
    return this.tokenManager;
  }

  /**
   * Builds normalized request URL with query parameters.
   */
  buildUrl(
    endpoint: string,
    params?: Record<string, string | number | boolean | null | undefined>
  ): string {
    let resolvedUrl: string;

    if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
      resolvedUrl = endpoint;
    } else {
      const cleanPrefix = this.apiPrefix.replace(/\/+$/, "");
      const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

      if (this.baseUrl.endsWith(cleanPrefix)) {
        // Base URL already includes the API prefix
        resolvedUrl = `${this.baseUrl}${cleanEndpoint}`;
      } else if (cleanEndpoint.startsWith(cleanPrefix)) {
        // Endpoint itself explicitly starts with the API prefix
        resolvedUrl = `${this.baseUrl}${cleanEndpoint}`;
      } else {
        // Standard concatenation: baseUrl + apiPrefix + cleanEndpoint
        resolvedUrl = `${this.baseUrl}${cleanPrefix}${cleanEndpoint}`;
      }
    }

    if (params && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
          searchParams.append(key, String(value));
        }
      }
      const queryString = searchParams.toString();
      if (queryString) {
        resolvedUrl += (resolvedUrl.includes("?") ? "&" : "?") + queryString;
      }
    }

    return resolvedUrl;
  }

  /**
   * Checks whether the target endpoint is the auth refresh endpoint.
   */
  private isRefreshEndpoint(endpoint: string): boolean {
    return endpoint.includes("/auth/refresh") || endpoint === "auth/refresh";
  }

  /**
   * Concurrency-safe token refresh mechanism.
   * Ensures multiple simultaneous 401s share a single HTTP refresh call.
   */
  private async refreshAccessToken(): Promise<string | null> {
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
      try {
        const refreshToken = this.tokenManager.getRefreshToken();
        if (!refreshToken) {
          this.tokenManager.clearTokens();
          this.tokenManager.notifyAuthExpired();
          return null;
        }

        const refreshUrl = this.buildUrl("/auth/refresh");
        const response = await this.fetchFn(refreshUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!response.ok) {
          this.tokenManager.clearTokens();
          this.tokenManager.notifyAuthExpired();
          return null;
        }

        const data = (await response.json()) as TokenResponse;
        if (data && data.access_token) {
          this.tokenManager.setAccessToken(data.access_token);
          if (data.refresh_token) {
            this.tokenManager.setRefreshToken(data.refresh_token);
          }
          return data.access_token;
        }

        this.tokenManager.clearTokens();
        this.tokenManager.notifyAuthExpired();
        return null;
      } catch {
        this.tokenManager.clearTokens();
        this.tokenManager.notifyAuthExpired();
        return null;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  /**
   * Parses backend error responses into an ApiError.
   */
  private async parseErrorResponse(response: Response): Promise<ApiError> {
    let responseBody: unknown = undefined;
    let message = `HTTP ${response.status}: ${response.statusText || "Request failed"}`;
    let detail: unknown = undefined;
    let validationErrors: ValidationErrorItem[] | undefined = undefined;
    let code: string | undefined = undefined;

    try {
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const parsed = (await response.json()) as ApiErrorDetail;
        responseBody = parsed;

        if (parsed?.error) {
          code = parsed.error.code;
          if (Array.isArray(parsed.error.details) && parsed.error.details.length > 0) {
            validationErrors = parsed.error.details as ValidationErrorItem[];
            detail = parsed.error.details;
            const formatted = validationErrors
              .map((err) => `${err.loc?.join(".") || "field"}: ${err.msg}`)
              .join("; ");
            message = parsed.error.message
              ? `${parsed.error.message}: ${formatted}`
              : `Validation Error: ${formatted}`;
            if (!code) code = "VALIDATION_ERROR";
          } else {
            if (parsed.error.message) {
              message = parsed.error.message;
            }
            detail = parsed.error.details ?? parsed.error;
          }
        } else if (typeof parsed?.detail === "string") {
          message = parsed.detail;
          detail = parsed.detail;
        } else if (Array.isArray(parsed?.detail)) {
          detail = parsed.detail;
          validationErrors = parsed.detail as ValidationErrorItem[];
          code = "VALIDATION_ERROR";
          const formatted = validationErrors
            .map((err) => `${err.loc?.join(".") || "field"}: ${err.msg}`)
            .join("; ");
          message = `Validation Error: ${formatted}`;
        } else if (parsed?.message) {
          message = parsed.message;
        }
      } else {
        const text = await response.text();
        if (text) {
          message = text;
          responseBody = text;
        }
      }
    } catch {
      // Fallback message retained on parsing failure
    }

    if (!code) {
      if (response.status === 401) code = "UNAUTHORIZED";
      else if (response.status === 403) code = "FORBIDDEN";
      else if (response.status === 404) code = "NOT_FOUND";
      else if (response.status === 409) code = "CONFLICT";
      else if (response.status === 422) code = "VALIDATION_ERROR";
      else if (response.status === 429) code = "RATE_LIMIT_EXCEEDED";
      else if (response.status >= 500) code = "SERVER_ERROR";
    }

    return new ApiError({
      message,
      status: response.status,
      statusText: response.statusText,
      code,
      detail,
      validationErrors,
      responseBody,
    });
  }

  /**
   * Main HTTP request dispatching method.
   */
  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const url = this.buildUrl(endpoint, options.params);
    const headers = new Headers(options.headers || {});

    // Accept header default
    if (!headers.has("Accept") && !headers.has("accept")) {
      headers.set("Accept", "application/json");
    }

    // Authorization header handling
    const isPublic = options.requiresAuth === false;
    const isExplicitlyProtected = options.requiresAuth === true;
    const existingAuth = headers.get("Authorization") || headers.get("authorization");

    if (!isPublic && !existingAuth) {
      const token = this.tokenManager.getAccessToken();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      } else if (isExplicitlyProtected) {
        throw new ApiError({
          message: "Authentication required",
          status: 401,
          statusText: "Unauthorized",
          code: "UNAUTHORIZED",
          isAuthError: true,
        });
      }
    }

    // Body serialization & Content-Type handling
    let finalBody: BodyInit | undefined = undefined;
    if (options.body !== undefined && options.body !== null) {
      if (options.body instanceof FormData) {
        // Let fetch automatically construct multipart/form-data boundary
        headers.delete("Content-Type");
        headers.delete("content-type");
        finalBody = options.body;
      } else if (
        typeof options.body === "string" ||
        options.body instanceof Blob ||
        options.body instanceof URLSearchParams
      ) {
        finalBody = options.body as BodyInit;
      } else {
        if (!headers.has("Content-Type") && !headers.has("content-type")) {
          headers.set("Content-Type", "application/json");
        }
        finalBody = JSON.stringify(options.body);
      }
    }

    const {
      params: _params,
      requiresAuth: _requiresAuth,
      _isRetry,
      body: _body,
      headers: _origHeaders,
      ...fetchOptions
    } = options;

    let response: Response;
    try {
      response = await this.fetchFn(url, {
        ...fetchOptions,
        headers,
        body: finalBody,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        throw err;
      }
      const isAbort = (err as Error)?.name === "AbortError";
      throw new ApiError({
        message: (err as Error)?.message || "Network request failed",
        status: 0,
        statusText: isAbort ? "Aborted" : "NetworkError",
        code: isAbort ? "ABORTED" : "NETWORK_ERROR",
        isNetworkError: true,
      });
    }

    // 401 Interceptor and Token Refresh handling
    if (
      response.status === 401 &&
      !_isRetry &&
      !this.isRefreshEndpoint(endpoint) &&
      options.requiresAuth !== false
    ) {
      const refreshedToken = await this.refreshAccessToken();
      if (refreshedToken) {
        // Retry the original request exactly once with updated authorization header
        const retryHeaders = new Headers(headers);
        retryHeaders.set("Authorization", `Bearer ${refreshedToken}`);
        return this.request<T>(endpoint, {
          ...options,
          headers: retryHeaders,
          _isRetry: true,
        });
      }

      throw new ApiError({
        message: "Session expired. Please log in again.",
        status: 401,
        statusText: "Unauthorized",
        code: "AUTH_EXPIRED",
        isAuthError: true,
      });
    }

    if (!response.ok) {
      throw await this.parseErrorResponse(response);
    }

    // 204 No Content handling
    if (response.status === 204) {
      return null as unknown as T;
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }

    return (await response.text()) as unknown as T;
  }

  // Convenience HTTP Methods
  get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  post<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "POST", body });
  }

  put<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "PUT", body });
  }

  patch<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "PATCH", body });
  }

  delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
export default apiClient;
