/**
 * Client-side token storage and lifecycle management.
 * Provides safe in-memory fallback and localStorage persistence for the JWT access token.
 */

const TOKEN_STORAGE_KEY = "crpf_tender_access_token";

let memoryToken: string | null = null;

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return memoryToken;
  }
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setAccessToken(token: string): void {
  memoryToken = token;
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } catch {
      // Ignore localStorage quotas or restricted environments
    }
  }
}

export function clearAccessToken(): void {
  memoryToken = null;
  if (typeof window !== "undefined") {
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // Ignore
    }
  }
}

export function hasAccessToken(): boolean {
  return Boolean(getAccessToken());
}
