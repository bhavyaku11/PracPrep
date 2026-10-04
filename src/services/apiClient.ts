/**
 * PracPrep API Client Service Re-export
 *
 * Exposes the centralized API client and token manager from src/lib/apiClient
 * to maintain compatibility with architecture specifications and service directory conventions.
 */

export * from "../lib/apiClient.ts";
export { default } from "../lib/apiClient.ts";
