/**
 * PracPrep Clerk Configuration & Utilities
 *
 * Handles safe extraction and validation of Clerk Publishable Key
 * from Vite or Node runtime environments without exposing secrets.
 */

export const CLERK_ENV_KEY = "VITE_CLERK_PUBLISHABLE_KEY";

/**
 * Resolves the Clerk Publishable Key safely from import.meta.env or process.env.
 */
export function getClerkPublishableKey(): string {
  // Vite client-side environment
  if (typeof import.meta !== "undefined" && typeof import.meta.env?.[CLERK_ENV_KEY] === "string") {
    const key = import.meta.env[CLERK_ENV_KEY].trim();
    if (key) return key;
  }

  // Node.js test or SSR runtime
  const proc = (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process;
  if (typeof proc?.env?.[CLERK_ENV_KEY] === "string") {
    const key = proc.env[CLERK_ENV_KEY].trim();
    if (key) return key;
  }

  return "";
}

/**
 * Checks whether Clerk is properly configured with a valid publishable key.
 */
export function isClerkConfigured(): boolean {
  const key = getClerkPublishableKey();
  return Boolean(
    key &&
      (key.startsWith("pk_test_") || key.startsWith("pk_live_")) &&
      key.length > 20
  );
}

/**
 * Returns a human-readable diagnostic error message if configuration is missing or invalid.
 */
export function getClerkConfigurationError(): string | null {
  const key = getClerkPublishableKey();
  if (!key) {
    return `Missing ${CLERK_ENV_KEY}. Please ensure your Clerk Publishable Key is configured in .env.local.`;
  }
  if (!key.startsWith("pk_test_") && !key.startsWith("pk_live_")) {
    return `Invalid ${CLERK_ENV_KEY}. Key must begin with "pk_test_" or "pk_live_".`;
  }
  return null;
}
